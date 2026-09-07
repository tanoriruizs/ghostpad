"""Virtual Xbox 360 pads (ViGEmBus) driven by the browser controllers."""

from __future__ import annotations

import logging
import threading
from types import MappingProxyType
from typing import Callable, Final, Iterator, Mapping

from protocol import Button, InputFrame

logger = logging.getLogger(__name__)


class DriverUnavailableError(RuntimeError):
    """ViGEmBus / vgamepad is missing or not usable on this machine."""


try:  # pragma: no cover - import guard, exercised only on broken installs
    import vgamepad as vg
except Exception as exc:  # noqa: BLE001 - any import failure is fatal for us
    vg = None  # type: ignore[assignment]
    _IMPORT_ERROR: Exception | None = exc
else:
    _IMPORT_ERROR = None


def _xusb_map() -> Mapping[Button, int]:
    """Buttons whose mapping never depends on the chosen face-button layout."""
    b = vg.XUSB_BUTTON
    return MappingProxyType(
        {
            Button.L: b.XUSB_GAMEPAD_LEFT_SHOULDER,
            Button.R: b.XUSB_GAMEPAD_RIGHT_SHOULDER,
            Button.MINUS: b.XUSB_GAMEPAD_BACK,
            Button.PLUS: b.XUSB_GAMEPAD_START,
            Button.LSTICK: b.XUSB_GAMEPAD_LEFT_THUMB,
            Button.RSTICK: b.XUSB_GAMEPAD_RIGHT_THUMB,
            Button.HOME: b.XUSB_GAMEPAD_GUIDE,
            Button.DPAD_UP: b.XUSB_GAMEPAD_DPAD_UP,
            Button.DPAD_DOWN: b.XUSB_GAMEPAD_DPAD_DOWN,
            Button.DPAD_LEFT: b.XUSB_GAMEPAD_DPAD_LEFT,
            Button.DPAD_RIGHT: b.XUSB_GAMEPAD_DPAD_RIGHT,
        }
    )


def _face_maps() -> Mapping[str, Mapping[Button, int]]:
    """Face-button mappings.

    ``positional`` keeps the physical position: the on-screen button at the
    bottom triggers the Xbox button at the bottom (A). This is what you want
    when Eden is configured with a plain Xbox controller profile.

    ``nintendo`` matches labels one-to-one (Switch A -> Xbox A), useful if you
    remap every button by hand inside Eden.
    """
    b = vg.XUSB_BUTTON
    return MappingProxyType(
        {
            "positional": MappingProxyType(
                {
                    Button.A: b.XUSB_GAMEPAD_B,
                    Button.B: b.XUSB_GAMEPAD_A,
                    Button.X: b.XUSB_GAMEPAD_Y,
                    Button.Y: b.XUSB_GAMEPAD_X,
                }
            ),
            "nintendo": MappingProxyType(
                {
                    Button.A: b.XUSB_GAMEPAD_A,
                    Button.B: b.XUSB_GAMEPAD_B,
                    Button.X: b.XUSB_GAMEPAD_X,
                    Button.Y: b.XUSB_GAMEPAD_Y,
                }
            ),
        }
    )


DEFAULT_LAYOUT: Final[str] = "positional"


RumbleCallback = Callable[[int, int], None]


class VirtualPad:
    """Thin, thread-safe wrapper around a single ``VX360Gamepad``."""

    def __init__(self, slot: int) -> None:
        if vg is None:  # pragma: no cover
            raise DriverUnavailableError(str(_IMPORT_ERROR))
        self.slot = slot
        self._lock = threading.Lock()
        self._shared = _xusb_map()
        self._faces = _face_maps()
        self._rumble: RumbleCallback | None = None
        try:
            self._pad = vg.VX360Gamepad()
        except Exception as exc:  # noqa: BLE001
            raise DriverUnavailableError(
                "No se pudo crear el gamepad virtual. Instala ViGEmBus y reinicia."
            ) from exc
        self._listen_for_rumble()
        self.reset()

    # -- vibración que envía el juego ------------------------------------ #
    def _listen_for_rumble(self) -> None:
        """ViGEmBus nos avisa del rumble que el juego manda a este mando."""

        def on_notification(_client, _target, large_motor, small_motor, _led, _data):
            callback = self._rumble
            if callback is None:
                return
            try:
                callback(int(large_motor), int(small_motor))
            except Exception:  # noqa: BLE001 - nunca romper el hilo del driver
                logger.debug("Fallo entregando rumble del slot %d", self.slot, exc_info=True)

        try:
            self._pad.register_notification(callback_function=on_notification)
        except Exception:  # noqa: BLE001 - sin rumble el mando sigue siendo útil
            logger.info("Este driver no expone rumble; se juega sin vibración.")

    def set_rumble_callback(self, callback: RumbleCallback | None) -> None:
        self._rumble = callback

    def apply(self, frame: InputFrame, layout: str = DEFAULT_LAYOUT) -> None:
        faces = self._faces.get(layout, self._faces[DEFAULT_LAYOUT])
        with self._lock:
            pad = self._pad
            pad.reset()
            for button, xusb in self._shared.items():
                if frame.pressed(button):
                    pad.press_button(button=xusb)
            for button, xusb in faces.items():
                if frame.pressed(button):
                    pad.press_button(button=xusb)
            pad.left_trigger_float(value_float=max(frame.zl, float(frame.pressed(Button.ZL))))
            pad.right_trigger_float(value_float=max(frame.zr, float(frame.pressed(Button.ZR))))
            pad.left_joystick_float(x_value_float=frame.lx, y_value_float=frame.ly)
            pad.right_joystick_float(x_value_float=frame.rx, y_value_float=frame.ry)
            pad.update()

    def reset(self) -> None:
        with self._lock:
            self._pad.reset()
            self._pad.update()


class PadSlotManager:
    """Hands out one virtual pad per player and recycles them on disconnect."""

    def __init__(self, player_count: int) -> None:
        if player_count < 1:
            raise ValueError("player_count must be >= 1")
        self._lock = threading.Lock()
        self._pads: dict[int, VirtualPad] = {
            slot: VirtualPad(slot) for slot in range(1, player_count + 1)
        }
        self._free: list[int] = sorted(self._pads)
        logger.info("Gamepads virtuales creados: %s", ", ".join(map(str, self._free)))

    @property
    def capacity(self) -> int:
        return len(self._pads)

    def acquire(self, preferred: int | None = None) -> tuple[int, VirtualPad] | None:
        with self._lock:
            if preferred in self._free:
                slot = preferred
            elif self._free:
                slot = self._free[0]
            else:
                return None
            self._free.remove(slot)
            return slot, self._pads[slot]

    def release(self, slot: int) -> None:
        with self._lock:
            if slot in self._pads and slot not in self._free:
                self._pads[slot].set_rumble_callback(None)
                self._pads[slot].reset()
                self._free.append(slot)
                self._free.sort()

    def reset_all(self) -> None:
        for pad in self._pads.values():
            pad.reset()

    def __iter__(self) -> Iterator[VirtualPad]:
        return iter(self._pads.values())
