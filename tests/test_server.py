import asyncio

from aiohttp.test_utils import AioHTTPTestCase

import server


class ServerTests(AioHTTPTestCase):
    PIN = "4821"

    async def get_application(self):
        return server.build_app(players=2, pin=self.PIN)

    async def _ws(self, query=""):
        return await self.client.ws_connect(f"/ws{query}")

    async def test_static_page_is_served_without_pin(self):
        async with self.client.get("/") as response:
            assert response.status == 200
            assert "GhostPad" in await response.text()

    async def test_wrong_pin_is_rejected(self):
        ws = await self._ws("?pin=0000")
        message = await ws.receive_json()
        assert message == {"type": "rejected", "reason": "pin"}

    async def test_missing_pin_is_rejected(self):
        ws = await self._ws()
        assert (await ws.receive_json())["reason"] == "pin"

    async def test_players_get_distinct_slots_until_full(self):
        first = await self._ws(f"?pin={self.PIN}")
        second = await self._ws(f"?pin={self.PIN}")
        assert (await first.receive_json())["slot"] == 1
        assert (await second.receive_json())["slot"] == 2
        third = await self._ws(f"?pin={self.PIN}")
        assert (await third.receive_json()) == {"type": "rejected", "reason": "full", "capacity": 2}

    async def test_ping_is_answered_with_pong(self):
        ws = await self._ws(f"?pin={self.PIN}")
        await ws.receive_json()
        await ws.send_json({"type": "ping", "t": 123.5})
        assert await ws.receive_json() == {"type": "pong", "t": 123.5}

    async def test_input_frames_reach_the_virtual_pad(self):
        ws = await self._ws(f"?pin={self.PIN}")
        assert (await ws.receive_json())["slot"] == 1
        await ws.send_json({"b": 1 << 5, "lx": -0.4})
        await asyncio.sleep(0.05)
        pad = next(iter(self.app[server.PADS_KEY]))._pad
        assert pad.mask == 0x0200          # RIGHT_SHOULDER
        assert pad.axes["l"] == (-0.4, 0.0)

    async def test_rumble_is_forwarded_to_the_phone(self):
        ws = await self._ws(f"?pin={self.PIN}")
        await ws.receive_json()
        pad = next(iter(self.app[server.PADS_KEY]))._pad
        pad.fire_rumble(180, 20)
        message = await asyncio.wait_for(ws.receive_json(), timeout=2)
        assert message == {"type": "rumble", "l": 180, "s": 20}

    async def test_slot_is_released_on_disconnect(self):
        ws = await self._ws(f"?pin={self.PIN}")
        await ws.receive_json()
        await ws.close()
        await asyncio.sleep(0.05)
        again = await self._ws(f"?pin={self.PIN}")
        assert (await again.receive_json())["slot"] == 1


def test_pin_resolution():
    assert server.resolve_pin("off") is None
    assert server.resolve_pin("0") is None
    assert server.resolve_pin(" 1234 ") == "1234"
    generated = server.resolve_pin("auto")
    assert generated.isdigit() and len(generated) == server.PIN_LENGTH


def test_public_url_embeds_pin_only_when_set():
    assert server.public_url("10.0.0.5", 8000, None) == "http://10.0.0.5:8000/"
    assert server.public_url("10.0.0.5", 8000, "4821") == "http://10.0.0.5:8000/?pin=4821"
