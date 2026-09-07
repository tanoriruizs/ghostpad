"""GhostPad - convierte teléfonos en mandos de Xbox virtuales por LAN.

Uso:
    python server.py                    # 2 jugadores, puerto 8000, PIN aleatorio
    python server.py --players 4 --pin off
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
from pathlib import Path
from typing import Final

from aiohttp import WSMsgType, web

from gamepad import DEFAULT_LAYOUT, DriverUnavailableError, PadSlotManager
from protocol import InputFrame, ProtocolError

__version__ = "1.0.0"

WEB_ROOT: Final[Path] = Path(__file__).resolve().parent / "web"
PIN_LENGTH: Final[int] = 4

PADS_KEY: Final = web.AppKey("pads", PadSlotManager)
PIN_KEY: Final = web.AppKey("pin", object)
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
# Consola
# --------------------------------------------------------------------------- #
LOGO: Final[str] = r"""
 ██████╗ ██╗  ██╗ ██████╗ ███████╗████████╗██████╗  █████╗ ██████╗
██╔════╝ ██║  ██║██╔═══██╗██╔════╝╚══██╔══╝██╔══██╗██╔══██╗██╔══██╗
██║  ███╗███████║██║   ██║███████╗   ██║   ██████╔╝███████║██║  ██║
██║   ██║██╔══██║██║   ██║╚════██║   ██║   ██╔═══╝ ██╔══██║██║  ██║
╚██████╔╝██║  ██║╚██████╔╝███████║   ██║   ██║     ██║  ██║██████╔╝
 ╚═════╝ ╚═╝  ╚═╝ ╚═════╝ ╚══════╝   ╚═╝   ╚═╝     ╚═╝  ╚═╝╚═════╝
"""


class _Ansi:
    """Códigos de color; se vacían si la consola no los soporta."""

    def __init__(self, enabled: bool) -> None:
        pick = (lambda code: code) if enabled else (lambda _: "")
        self.reset = pick("\033[0m")
        self.bold = pick("\033[1m")
        self.dim = pick("\033[2m")
        self.cyan = pick("\033[36m")
        self.bright_cyan = pick("\033[96m")
        self.green = pick("\033[92m")
        self.yellow = pick("\033[93m")
        self.white = pick("\033[97m")


def _ansi_console() -> _Ansi:
    """Activa ANSI en consolas Windows antiguas vía colorama, si está disponible."""
    if not sys.stdout.isatty():
        return _Ansi(False)
    try:
        import colorama  # type: ignore[import-not-found]

        colorama.just_fix_windows_console()
    except Exception:  # noqa: BLE001 - sin colorama, Windows Terminal y *nix ya soportan ANSI
        pass
    return _Ansi(True)


def print_banner(host_ip: str, port: int, players: int, pin: str | None) -> None:
    url = public_url(host_ip, port, pin)
    c = _ansi_console()
    width = 68

    def row(label: str, value: str, color: str) -> str:
        return f"  {c.dim}{label:<22}{c.reset}{color}{c.bold}{value}{c.reset}"

    print(f"{c.bright_cyan}{LOGO}{c.reset}")
    print(f"  {c.dim}v{__version__} · tu teléfono como mando de Xbox, desde el navegador{c.reset}")
    print(f"  {c.cyan}{'─' * width}{c.reset}")
    print(row("Dirección", url, c.white))
    print(row("PIN de acceso", pin or "desactivado", c.yellow if pin else c.dim))
    print(row("Jugadores", str(players), c.green))
    print(row("Puerto", str(port), c.white))
    print(f"  {c.cyan}{'─' * width}{c.reset}")
    print(f"  {c.dim}Escanea el QR con cada teléfono (misma Wi-Fi). Ctrl+C para salir.{c.reset}\n")
    _print_qr(url)
    print()


def _print_qr(url: str) -> None:
    try:
        import qrcode  # type: ignore[import-not-found]
    except ImportError:
        return
    code = qrcode.QRCode(border=1)
    code.add_data(url)
    code.print_ascii(invert=True)


# --------------------------------------------------------------------------- #
# WebSocket
# --------------------------------------------------------------------------- #
async def websocket_handler(request: web.Request) -> web.WebSocketResponse:
    pads = request.app[PADS_KEY]
    ws = web.WebSocketResponse(heartbeat=20.0, max_msg_size=MAX_FRAME_BYTES * 8)
    await ws.prepare(request)

    if not _pin_ok(request.app[PIN_KEY], request.query.get("pin")):
        await ws.send_json({"type": "rejected", "reason": "pin"})
        await ws.close()
        return ws

    preferred = _parse_slot(request.query.get("slot"))
    claim = pads.acquire(preferred)
    if claim is None:
        await ws.send_json({"type": "rejected", "reason": "full", "capacity": pads.capacity})
        await ws.close()
        return ws

    slot, pad = claim
    layout = DEFAULT_LAYOUT
    peer = request.remote or "?"
    logger.info("Jugador %d conectado desde %s", slot, peer)
    await ws.send_json({"type": "assigned", "slot": slot, "capacity": pads.capacity})

    rumble = _RumbleBridge(ws, asyncio.get_running_loop())
    pad.set_rumble_callback(rumble.push)
    rumble_task = asyncio.create_task(rumble.run())

    try:
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
                    logger.info("Jugador %d usa layout '%s'", slot, layout)
                continue

            try:
                frame = InputFrame.from_payload(payload)
            except ProtocolError:
                continue
            pad.apply(frame, layout)
    except asyncio.CancelledError:
        raise
    except Exception:  # noqa: BLE001 - una sesión rota no debe tumbar el servidor
        logger.exception("Error en la sesión del jugador %d", slot)
    finally:
        rumble_task.cancel()
        pads.release(slot)
        logger.info("Jugador %d desconectado", slot)

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


def build_app(players: int, pin: str | None = None) -> web.Application:
    app = web.Application()
    app[PADS_KEY] = PadSlotManager(players)
    app[PIN_KEY] = pin
    app.router.add_get("/", index)
    app.router.add_get("/ws", websocket_handler)
    app.router.add_static("/static", WEB_ROOT, name="static")
    app.on_cleanup.append(_reset_pads)
    return app


async def _reset_pads(app: web.Application) -> None:
    app[PADS_KEY].reset_all()


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Teléfonos como mandos de Xbox por LAN")
    parser.add_argument("--port", type=int, default=8000, help="Puerto HTTP (def. 8000)")
    parser.add_argument("--players", type=int, default=2, help="Mandos virtuales (def. 2)")
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
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s  %(levelname)-7s %(message)s",
        datefmt="%H:%M:%S",
    )

    if not WEB_ROOT.is_dir():
        logger.error("Falta la carpeta 'web' junto a server.py")
        return 1

    pin = resolve_pin(args.pin)
    print_banner(detect_lan_ip(), args.port, args.players, pin)
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
        web.run_app(app, host=args.host, port=args.port, print=None)
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
