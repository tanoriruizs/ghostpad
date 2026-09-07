"""Fixtures compartidas.

``vgamepad`` sólo funciona en Windows con ViGEmBus instalado. Para que la suite
corra en cualquier máquina (y en CI) se registra un doble mínimo del módulo
antes de importar ``gamepad``: misma API, sin driver.
"""

from __future__ import annotations

import sys
import types
from enum import IntEnum
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


class _XusbButton(IntEnum):
    XUSB_GAMEPAD_DPAD_UP = 0x0001
    XUSB_GAMEPAD_DPAD_DOWN = 0x0002
    XUSB_GAMEPAD_DPAD_LEFT = 0x0004
    XUSB_GAMEPAD_DPAD_RIGHT = 0x0008
    XUSB_GAMEPAD_START = 0x0010
    XUSB_GAMEPAD_BACK = 0x0020
    XUSB_GAMEPAD_LEFT_THUMB = 0x0040
    XUSB_GAMEPAD_RIGHT_THUMB = 0x0080
    XUSB_GAMEPAD_LEFT_SHOULDER = 0x0100
    XUSB_GAMEPAD_RIGHT_SHOULDER = 0x0200
    XUSB_GAMEPAD_GUIDE = 0x0400
    XUSB_GAMEPAD_A = 0x1000
    XUSB_GAMEPAD_B = 0x2000
    XUSB_GAMEPAD_X = 0x4000
    XUSB_GAMEPAD_Y = 0x8000


class FakeVX360Gamepad:
    """Registra lo que el servidor haría con el driver real."""

    def __init__(self) -> None:
        self.mask = 0
        self.axes: dict[str, object] = {}
        self.updates = 0
        self._callback = None

    def reset(self) -> None:
        self.mask = 0
        self.axes = {}

    def press_button(self, button) -> None:
        self.mask |= int(button)

    def left_trigger_float(self, value_float) -> None:
        self.axes["zl"] = value_float

    def right_trigger_float(self, value_float) -> None:
        self.axes["zr"] = value_float

    def left_joystick_float(self, x_value_float, y_value_float) -> None:
        self.axes["l"] = (x_value_float, y_value_float)

    def right_joystick_float(self, x_value_float, y_value_float) -> None:
        self.axes["r"] = (x_value_float, y_value_float)

    def update(self) -> None:
        self.updates += 1

    def register_notification(self, callback_function) -> None:
        self._callback = callback_function

    def unregister_notification(self) -> None:
        self._callback = None

    # -- ayuda para tests: simula rumble desde el driver --------------------
    def fire_rumble(self, large: int, small: int) -> None:
        if self._callback:
            self._callback(None, None, large, small, 0, None)


def _install_fake_vgamepad() -> None:
    if "vgamepad" in sys.modules:
        return
    fake = types.ModuleType("vgamepad")
    fake.XUSB_BUTTON = _XusbButton
    fake.VX360Gamepad = FakeVX360Gamepad
    sys.modules["vgamepad"] = fake


_install_fake_vgamepad()


@pytest.fixture
def xusb():
    return _XusbButton
