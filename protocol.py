"""Wire protocol between the browser gamepads and the server.

The client sends one compact JSON object per input change:

    {"b": <int bitmask>, "lx": f, "ly": f, "rx": f, "ry": f, "zl": f, "zr": f}

All analog fields are floats in [-1, 1] (sticks) or [0, 1] (triggers).
Everything arriving from the network is treated as hostile and clamped.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum
from typing import Any, Final


class Button(IntEnum):
    """Bit position of every logical Switch button inside the bitmask."""

    A = 0
    B = 1
    X = 2
    Y = 3
    L = 4
    R = 5
    ZL = 6
    ZR = 7
    MINUS = 8
    PLUS = 9
    LSTICK = 10
    RSTICK = 11
    HOME = 12
    CAPTURE = 13
    DPAD_UP = 14
    DPAD_DOWN = 15
    DPAD_LEFT = 16
    DPAD_RIGHT = 17


BUTTON_MASK: Final[int] = (1 << len(Button)) - 1

_STICK_KEYS: Final[tuple[str, ...]] = ("lx", "ly", "rx", "ry")
_TRIGGER_KEYS: Final[tuple[str, ...]] = ("zl", "zr")


class ProtocolError(ValueError):
    """Raised when a client frame cannot be interpreted."""


def _clamp(value: Any, low: float, high: float) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return 0.0
    if number != number:  # NaN
        return 0.0
    return max(low, min(high, number))


@dataclass(frozen=True, slots=True)
class InputFrame:
    """A single validated snapshot of a controller's state."""

    buttons: int = 0
    lx: float = 0.0
    ly: float = 0.0
    rx: float = 0.0
    ry: float = 0.0
    zl: float = 0.0
    zr: float = 0.0

    def pressed(self, button: Button) -> bool:
        return bool(self.buttons & (1 << button))

    @classmethod
    def neutral(cls) -> "InputFrame":
        return cls()

    @classmethod
    def from_payload(cls, payload: Any) -> "InputFrame":
        if not isinstance(payload, dict):
            raise ProtocolError("input frame must be a JSON object")

        try:
            # OverflowError incluido: JSON admite 1e999, que Python lee como
            # infinito, y convertirlo a entero revienta. Sin capturarlo, un solo
            # frame así echaba al jugador de la partida.
            buttons = int(payload.get("b", 0)) & BUTTON_MASK
        except (TypeError, ValueError, OverflowError) as exc:
            raise ProtocolError("field 'b' must be an integer") from exc

        sticks = {key: _clamp(payload.get(key, 0.0), -1.0, 1.0) for key in _STICK_KEYS}
        triggers = {key: _clamp(payload.get(key, 0.0), 0.0, 1.0) for key in _TRIGGER_KEYS}
        return cls(buttons=buttons, **sticks, **triggers)
