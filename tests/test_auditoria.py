"""Regresiones de la auditoría: fallos reales que traía la 1.0."""

import asyncio
import json

import pytest
from aiohttp import web
from aiohttp.test_utils import AioHTTPTestCase

import server
from protocol import InputFrame, ProtocolError


# --------------------------------------------------------------------------- #
# Un bitmask hostil ya no echa al jugador de la partida
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("raw", ['{"b": 1e999}', '{"b": -1e999}'])
def test_un_bitmask_infinito_es_error_de_protocolo(raw):
    """JSON admite 1e999; Python lo lee como infinito y `int()` reventaba.

    El OverflowError se escapaba de `except ProtocolError`, así que un solo
    frame así cortaba la sesión del jugador en plena partida.
    """
    with pytest.raises(ProtocolError):
        InputFrame.from_payload(json.loads(raw))


def test_los_analogicos_absurdos_se_acotan_sin_romper():
    frame = InputFrame.from_payload(json.loads('{"lx": 1e999, "zr": -1e999}'))
    assert frame.lx == 1.0
    assert frame.zr == 0.0


# --------------------------------------------------------------------------- #
# El mando vuelve a la piscina aunque el teléfono desaparezca
# --------------------------------------------------------------------------- #
class SlotLeakTests(AioHTTPTestCase):
    """El 'assigned' se enviaba fuera del try/finally.

    Si el teléfono se iba justo ahí, el mando quedaba reservado para siempre:
    con dos casos de mala suerte el servidor se declaraba lleno sin remedio y
    solo se recuperaba reiniciándolo.
    """

    async def get_application(self):
        self.app = server.build_app(players=2, pin=None)
        return self.app

    async def asyncSetUp(self):
        await super().asyncSetUp()
        self._original = web.WebSocketResponse.send_json
        self.romper = True
        original = self._original
        prueba = self

        async def send_json(ws_self, data, *args, **kwargs):
            if prueba.romper and isinstance(data, dict) and data.get("type") == "assigned":
                raise ConnectionResetError("el teléfono se fue")
            return await original(ws_self, data, *args, **kwargs)

        web.WebSocketResponse.send_json = send_json

    async def asyncTearDown(self):
        web.WebSocketResponse.send_json = self._original
        await super().asyncTearDown()

    async def _intento_fallido(self):
        ws = await self.client.ws_connect("/ws")
        await ws.close()
        await asyncio.sleep(0.05)

    async def test_el_slot_se_libera_si_falla_el_mensaje_de_bienvenida(self):
        pads = self.app[server.PADS_KEY]
        for _ in range(3):
            await self._intento_fallido()
        assert pads.in_use == 0, "los mandos se quedaron reservados para siempre"

    async def test_el_servidor_sigue_usable_despues_del_tropiezo(self):
        pads = self.app[server.PADS_KEY]
        for _ in range(2):          # tantos fallos como mandos hay
            await self._intento_fallido()

        self.romper = False
        ws = await self.client.ws_connect("/ws")
        assert (await ws.receive_json())["type"] == "assigned"
        assert pads.in_use == 1
        await ws.close()


# --------------------------------------------------------------------------- #
# Recargar la página no debe bloquearte a ti mismo
# --------------------------------------------------------------------------- #
class PinGuardTests(AioHTTPTestCase):
    PIN = "1587"

    async def get_application(self):
        self.app = server.build_app(players=2, pin=self.PIN)
        return self.app

    async def test_conectar_sin_pin_no_cuenta_como_intento(self):
        """Abrir la dirección a mano no es intentar adivinar el PIN.

        Contarlo dejaba fuera a un usuario legítimo por recargar unas veces.
        """
        guard = self.app[server.GUARD_KEY]
        for _ in range(server.PinGuard.MAX_FAILS + 3):
            ws = await self.client.ws_connect("/ws")
            assert (await ws.receive_json())["reason"] == "pin"
            await ws.close()

        assert guard.retry_after("127.0.0.1") == 0

        ws = await self.client.ws_connect(f"/ws?pin={self.PIN}")
        assert (await ws.receive_json())["type"] == "assigned"
        await ws.close()

    async def test_los_pines_equivocados_si_acaban_frenando(self):
        guard = self.app[server.GUARD_KEY]
        for _ in range(server.PinGuard.MAX_FAILS):
            ws = await self.client.ws_connect("/ws?pin=0000")
            await ws.receive_json()
            await ws.close()

        assert guard.retry_after("127.0.0.1") > 0

    async def test_en_espera_ni_el_pin_bueno_entra(self):
        """Durante el castigo se rechaza todo: si no, no serviría de nada."""
        for _ in range(server.PinGuard.MAX_FAILS):
            ws = await self.client.ws_connect("/ws?pin=0000")
            await ws.receive_json()
            await ws.close()

        ws = await self.client.ws_connect(f"/ws?pin={self.PIN}")
        assert (await ws.receive_json())["reason"] == "pin"
        await ws.close()
