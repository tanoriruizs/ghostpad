"""GhostPad - convierte teléfonos en mandos de Xbox virtuales por LAN.

Uso:
    python server.py                    # 4 mandos, puerto 8000, PIN aleatorio
    python server.py --players 2 --pin off
"""

from __future__ import annotations

import argparse
import asyncio
import hmac
import json
import logging
import secrets
import socket
import sys
import time
from collections.abc import Callable
from pathlib import Path
from typing import Final

from aiohttp import WSMsgType, web

from banner import (
    player_connected,
    player_disconnected,
    player_rejected,
    print_banner,
)
from gamepad import DEFAULT_LAYOUT, MAX_PLAYERS, DriverUnavailableError, PadSlotManager
from protocol import InputFrame, ProtocolError

__version__ = "1.1.0"

WEB_ROOT: Final[Path] = Path(__file__).resolve().parent / "web"
PIN_LENGTH: Final[int] = 4

PADS_KEY: Final = web.AppKey("pads", PadSlotManager)
PIN_KEY: Final = web.AppKey("pin", object)
GUARD_KEY: Final = web.AppKey("pin_guard", object)
MAX_FRAME_BYTES: Final[int] = 512
VALID_LAYOUTS: Final[frozenset[str]] = frozenset({"positional", "nintendo"})

logger = logging.getLogger("ghostpad")


# --------------------------------------------------------------------------- #
# Red
# --------------------------------------------------------------------------- #
def detect_lan_ip() -> str:
    """Mejor IP local para que los teléfonos se conecten (sin tráfico real)."""
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as probe:
        try:
            probe.connect(("10.255.255.255", 1))
            return probe.getsockname()[0]
        except OSError:
            return "127.0.0.1"


def public_url(host_ip: str, port: int, pin: str | None) -> str:
    """Dirección que abren los teléfonos; lleva el PIN para que el QR baste."""
    base = f"http://{host_ip}:{port}/"
    return f"{base}?pin={pin}" if pin else base


# --------------------------------------------------------------------------- #
# Fuerza bruta
# --------------------------------------------------------------------------- #
class PinGuard:
    """Frena los intentos repetidos de adivinar el PIN.

    Cuatro dígitos son 10 000 combinaciones: sin freno, un script en la misma
    Wi-Fi las recorre en segundos. Tras varios fallos seguidos la IP queda en
    espera, y cada intento posterior dobla ese tiempo.
    """

    MAX_FAILS: Final[int] = 5
    BASE_COOLDOWN: Final[float] = 2.0
    MAX_COOLDOWN: Final[float] = 300.0
    FORGET_AFTER: Final[float] = 900.0

    def __init__(self, clock: Callable[[], float] = time.monotonic) -> None:
        self._clock = clock
        # ip -> (fallos, instante en que vuelve a poder intentar, último visto)
        self._fails: dict[str, tuple[int, float, float]] = {}

    def retry_after(self, ip: str) -> float:
        """Segundos que le faltan a esa IP para poder reintentar."""
        self._prune()
        _, free_at, _ = self._fails.get(ip, (0, 0.0, 0.0))
        return max(0.0, free_at - self._clock())

    def record_failure(self, ip: str) -> float:
        """Anota un PIN fallido y devuelve la espera que le toca."""
        now = self._clock()
        fails, _, _ = self._fails.get(ip, (0, 0.0, 0.0))
        fails += 1
        wait = 0.0
        if fails >= self.MAX_FAILS:
            # El exponente se acota antes de elevar: con miles de intentos,
            # 2 ** n sería un entero enorme y desbordaría al pasar a float.
            exponente = min(fails - self.MAX_FAILS, 32)
            wait = min(self.BASE_COOLDOWN * 2**exponente, self.MAX_COOLDOWN)
        self._fails[ip] = (fails, now + wait, now)
        return wait

    def record_success(self, ip: str) -> None:
        """Un acierto limpia el historial: quien entra bien no arrastra castigo."""
        self._fails.pop(ip, None)

    def _prune(self) -> None:
        """Olvida IPs inactivas para que el diccionario no crezca sin fin."""
        limit = self._clock() - self.FORGET_AFTER
        for ip in [ip for ip, (_, _, seen) in self._fails.items() if seen < limit]:
            del self._fails[ip]


# --------------------------------------------------------------------------- #
# WebSocket
# --------------------------------------------------------------------------- #
async def websocket_handler(request: web.Request) -> web.WebSocketResponse:
    pads = request.app[PADS_KEY]
    ws = web.WebSocketResponse(heartbeat=20.0, max_msg_size=MAX_FRAME_BYTES * 8)
    await ws.prepare(request)

    peer = request.remote or "?"
    guard: PinGuard = request.app[GUARD_KEY]

    espera = guard.retry_after(peer)
    if espera > 0:
        await ws.send_json({"type": "rejected", "reason": "pin"})
        await ws.close()
        player_rejected("cooldown", peer, espera)
        return ws

    given = request.query.get("pin")
    if not _pin_ok(request.app[PIN_KEY], given):
        # Entrar sin PIN no es adivinarlo: es quien tecleó la dirección a mano
        # en vez de escanear el QR. Solo cuentan los intentos con algo escrito,
        # para que nadie se bloquee a sí mismo recargando la página.
        espera = guard.record_failure(peer) if (given or "").strip() else 0.0
        await ws.send_json({"type": "rejected", "reason": "pin"})
        await ws.close()
        player_rejected("pin", peer, espera)
        return ws
    guard.record_success(peer)

    preferred = _parse_slot(request.query.get("slot"))
    claim = pads.acquire(preferred)
    if claim is None:
        await ws.send_json({"type": "rejected", "reason": "full", "capacity": pads.capacity})
        await ws.close()
        player_rejected("full", peer)
        return ws

    slot, pad = claim
    layout = DEFAULT_LAYOUT
    rumble_task: asyncio.Task[None] | None = None

    # Desde que se reserva el mando, todo va dentro del try: si algo falla
    # antes (p. ej. el teléfono desaparece al enviarle su número), el finally
    # tiene que devolver el slot igual. Sin esto se perdían para siempre.
    try:
        player_connected(slot, peer, pads.in_use, pads.capacity)
        await ws.send_json({"type": "assigned", "slot": slot, "capacity": pads.capacity})

        rumble = _RumbleBridge(ws, asyncio.get_running_loop())
        pad.set_rumble_callback(rumble.push)
        rumble_task = asyncio.create_task(rumble.run())

        async for msg in ws:
            if msg.type is not WSMsgType.TEXT:
                continue
            try:
                payload = json.loads(msg.data)
            except json.JSONDecodeError:
                continue
            if not isinstance(payload, dict):
                continue

            kind = payload.get("type")
            if kind == "ping":
                await ws.send_json({"type": "pong", "t": payload.get("t")})
                continue

            if kind == "config":
                requested = payload.get("layout")
                if requested in VALID_LAYOUTS:
                    layout = requested
                    logger.debug("Jugador %d usa layout '%s'", slot, layout)
                continue

            try:
                frame = InputFrame.from_payload(payload)
            except ProtocolError:
                continue
            pad.apply(frame, layout)
    except asyncio.CancelledError:
        raise
    except ConnectionResetError:
        pass  # el teléfono se fue sin despedirse; no hay nada que registrar
    except Exception:  # noqa: BLE001 - una sesión rota no debe tumbar el servidor
        logger.exception("Error en la sesión del jugador %d", slot)
    finally:
        if rumble_task is not None:
            rumble_task.cancel()
        pads.release(slot)
        player_disconnected(slot, pads.in_use, pads.capacity)

    return ws


class _RumbleBridge:
    """Lleva el rumble del hilo del driver al WebSocket, sin saturarlo.

    ViGEmBus notifica desde su propio hilo y puede repetir el mismo valor muchas
    veces por segundo; aquí se coalesce y se envía como mucho cada 40 ms.
    """

    MIN_INTERVAL = 0.04

    def __init__(self, ws: web.WebSocketResponse, loop: asyncio.AbstractEventLoop) -> None:
        self._ws = ws
        self._loop = loop
        self._pending: tuple[int, int] | None = None
        self._wakeup = asyncio.Event()

    def push(self, large: int, small: int) -> None:
        """Llamado desde el hilo del driver."""
        self._loop.call_soon_threadsafe(self._store, (large, small))

    def _store(self, value: tuple[int, int]) -> None:
        self._pending = value
        self._wakeup.set()

    async def run(self) -> None:
        last: tuple[int, int] | None = None
        while True:
            await self._wakeup.wait()
            self._wakeup.clear()
            value = self._pending
            if value is None or value == last:
                continue
            last = value
            if self._ws.closed:
                return
            try:
                await self._ws.send_json({"type": "rumble", "l": value[0], "s": value[1]})
            except (ConnectionResetError, RuntimeError):
                return
            await asyncio.sleep(self.MIN_INTERVAL)


def _pin_ok(expected: object, given: str | None) -> bool:
    """Comparación en tiempo constante; sin PIN configurado todo pasa."""
    if not expected:
        return True
    return hmac.compare_digest(str(expected), (given or "").strip())


def resolve_pin(option: str) -> str | None:
    """``auto`` genera uno aleatorio, ``off`` lo desactiva, otro valor se usa tal cual."""
    value = option.strip().lower()
    if value in {"off", "none", "0", ""}:
        return None
    if value == "auto":
        return "".join(secrets.choice("0123456789") for _ in range(PIN_LENGTH))
    return option.strip()


def _parse_slot(raw: str | None) -> int | None:
    try:
        return int(raw) if raw is not None else None
    except ValueError:
        return None


# --------------------------------------------------------------------------- #
# App
# --------------------------------------------------------------------------- #
async def index(_: web.Request) -> web.FileResponse:
    return web.FileResponse(WEB_ROOT / "index.html")


@web.middleware
async def _revalidate(request: web.Request, handler):
    """Obliga al teléfono a comprobar si el mando cambió.

    Sin cabecera de caché el navegador aplica su heurística y puede quedarse
    días con el `app.js` anterior: actualizas GhostPad y el teléfono sigue
    ejecutando la versión vieja sin que nadie lo note. Con `no-cache` revalida
    siempre y, gracias al ETag, casi siempre recibe un 304 vacío.
    """
    response = await handler(request)
    if not isinstance(response, web.WebSocketResponse):
        response.headers.setdefault("Cache-Control", "no-cache")
    return response


def build_app(players: int, pin: str | None = None) -> web.Application:
    app = web.Application(middlewares=[_revalidate])
    app[PADS_KEY] = PadSlotManager(players)
    app[PIN_KEY] = pin
    app[GUARD_KEY] = PinGuard()
    app.router.add_get("/", index)
    app.router.add_get("/ws", websocket_handler)
    app.router.add_static("/static", WEB_ROOT, name="static")
    app.on_cleanup.append(_reset_pads)
    return app


async def _reset_pads(app: web.Application) -> None:
    app[PADS_KEY].reset_all()


def _player_count(raw: str) -> int:
    """Valida --players aquí para fallar con un mensaje claro, no con un traceback."""
    try:
        value = int(raw)
    except ValueError:
        raise argparse.ArgumentTypeError(f"'{raw}' no es un número") from None
    if not 1 <= value <= MAX_PLAYERS:
        raise argparse.ArgumentTypeError(f"debe estar entre 1 y {MAX_PLAYERS}")
    return value


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Teléfonos como mandos de Xbox por LAN")
    parser.add_argument("--port", type=int, default=8000, help="Puerto HTTP (def. 8000)")
    parser.add_argument(
        "--players", type=_player_count, default=MAX_PLAYERS,
        help=f"Mandos virtuales creados al arrancar, 1-{MAX_PLAYERS} (def. {MAX_PLAYERS})",
    )
    parser.add_argument("--host", default="0.0.0.0", help="Interfaz de escucha")
    parser.add_argument(
        "--pin", default="auto",
        help="PIN de acceso: 'auto' (aleatorio, def.), 'off' o un valor fijo",
    )
    parser.add_argument("--version", action="version", version=f"GhostPad {__version__}")
    parser.add_argument("--verbose", action="store_true", help="Log detallado")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    # Sin --verbose la consola solo muestra el panel y los avisos de jugadores;
    # el log queda en avisos y errores para no tapar la dirección ni el QR.
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.WARNING,
        format="%(asctime)s  %(levelname)-7s %(message)s",
        datefmt="%H:%M:%S",
    )

    if not WEB_ROOT.is_dir():
        logger.error("Falta la carpeta 'web' junto a server.py")
        return 1

    pin = resolve_pin(args.pin)
    url = public_url(detect_lan_ip(), args.port, pin)
    print_banner(url, args.port, args.players, pin, __version__)
    try:
        app = build_app(args.players, pin)
    except DriverUnavailableError as exc:
        logger.error("%s", exc)
        logger.error(
            "Instala ViGEmBus desde https://github.com/nefarius/ViGEmBus/releases "
            "y reinicia la PC."
        )
        return 2
    except ValueError as exc:
        logger.error("%s", exc)
        return 1

    try:
        web.run_app(
            app,
            host=args.host,
            port=args.port,
            print=None,
            access_log=logger if args.verbose else None,
        )
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
