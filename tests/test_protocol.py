import math

import pytest

from protocol import BUTTON_MASK, Button, InputFrame, ProtocolError


def test_neutral_frame_has_nothing_pressed():
    frame = InputFrame.neutral()
    assert frame.buttons == 0
    assert (frame.lx, frame.ly, frame.rx, frame.ry, frame.zl, frame.zr) == (0, 0, 0, 0, 0, 0)


def test_buttons_are_read_from_bitmask():
    frame = InputFrame.from_payload({"b": (1 << Button.A) | (1 << Button.ZR)})
    assert frame.pressed(Button.A)
    assert frame.pressed(Button.ZR)
    assert not frame.pressed(Button.B)


def test_unknown_high_bits_are_dropped():
    frame = InputFrame.from_payload({"b": 0xFFFFFFFF})
    assert frame.buttons == BUTTON_MASK


@pytest.mark.parametrize("raw, expected", [(5, 1.0), (-5, -1.0), (0.25, 0.25), ("0.5", 0.5)])
def test_sticks_are_clamped_to_unit_range(raw, expected):
    frame = InputFrame.from_payload({"lx": raw})
    assert frame.lx == expected


@pytest.mark.parametrize("raw, expected", [(2, 1.0), (-1, 0.0), (0.4, 0.4)])
def test_triggers_are_clamped_to_zero_one(raw, expected):
    frame = InputFrame.from_payload({"zl": raw})
    assert frame.zl == expected


@pytest.mark.parametrize("garbage", [float("nan"), "abc", None, [], {}])
def test_garbage_analog_values_become_zero(garbage):
    frame = InputFrame.from_payload({"ly": garbage, "zr": garbage})
    assert frame.ly == 0.0 and frame.zr == 0.0
    assert not math.isnan(frame.ly)


def test_missing_fields_default_to_neutral():
    assert InputFrame.from_payload({}) == InputFrame.neutral()


@pytest.mark.parametrize("payload", [[1, 2], "frame", 42, None])
def test_non_object_payload_is_rejected(payload):
    with pytest.raises(ProtocolError):
        InputFrame.from_payload(payload)


def test_non_integer_bitmask_is_rejected():
    with pytest.raises(ProtocolError):
        InputFrame.from_payload({"b": "abc"})
