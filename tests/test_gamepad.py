import pytest

from gamepad import PadSlotManager, VirtualPad
from protocol import Button, InputFrame


def frame(*buttons, **analog):
    mask = 0
    for button in buttons:
        mask |= 1 << button
    return InputFrame.from_payload({"b": mask, **analog})


def test_positional_layout_keeps_physical_positions(xusb):
    pad = VirtualPad(slot=1)
    pad.apply(frame(Button.A, Button.B, Button.X, Button.Y), "positional")
    assert pad._pad.mask == (
        xusb.XUSB_GAMEPAD_B | xusb.XUSB_GAMEPAD_A | xusb.XUSB_GAMEPAD_Y | xusb.XUSB_GAMEPAD_X
    )


def test_nintendo_layout_matches_labels(xusb):
    pad = VirtualPad(slot=1)
    pad.apply(frame(Button.A), "nintendo")
    assert pad._pad.mask == xusb.XUSB_GAMEPAD_A


def test_unknown_layout_falls_back_to_positional(xusb):
    pad = VirtualPad(slot=1)
    pad.apply(frame(Button.A), "whatever")
    assert pad._pad.mask == xusb.XUSB_GAMEPAD_B


def test_shared_buttons_and_axes_are_forwarded(xusb):
    pad = VirtualPad(slot=1)
    pad.apply(frame(Button.L, Button.PLUS, Button.DPAD_UP, lx=-0.5, ry=0.25, zr=1.0))
    assert pad._pad.mask == (
        xusb.XUSB_GAMEPAD_LEFT_SHOULDER | xusb.XUSB_GAMEPAD_START | xusb.XUSB_GAMEPAD_DPAD_UP
    )
    assert pad._pad.axes["l"] == (-0.5, 0.0)
    assert pad._pad.axes["r"] == (0.0, 0.25)
    assert pad._pad.axes["zr"] == 1.0


def test_digital_zl_press_drives_the_trigger():
    pad = VirtualPad(slot=1)
    pad.apply(frame(Button.ZL))
    assert pad._pad.axes["zl"] == 1.0


def test_rumble_callback_receives_driver_notification():
    pad = VirtualPad(slot=1)
    received = []
    pad.set_rumble_callback(lambda large, small: received.append((large, small)))
    pad._pad.fire_rumble(200, 40)
    assert received == [(200, 40)]


def test_slot_manager_hands_out_slots_in_order():
    pads = PadSlotManager(2)
    assert pads.capacity == 2
    assert pads.acquire()[0] == 1
    assert pads.acquire()[0] == 2
    assert pads.acquire() is None


def test_slot_manager_honours_preferred_slot_and_recycles():
    pads = PadSlotManager(2)
    slot, pad = pads.acquire(preferred=2)
    assert slot == 2
    pad.set_rumble_callback(lambda *_: None)
    pads.release(2)
    assert pad._rumble is None, "release must detach the rumble callback"
    assert pads.acquire(preferred=2)[0] == 2


def test_slot_manager_rejects_zero_players():
    with pytest.raises(ValueError):
        PadSlotManager(0)
