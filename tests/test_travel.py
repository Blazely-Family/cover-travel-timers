"""The door's travel: open, close, stop and reverse, fob starts, restarts."""

from datetime import timedelta

from freezegun.api import FrozenDateTimeFactory
import pytest
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    async_fire_time_changed_exact,
    mock_restore_cache_with_extra_data,
)

from homeassistant.const import ATTR_ENTITY_ID, EVENT_CALL_SERVICE
from homeassistant.core import Event, HomeAssistant, State, callback

from custom_components.cover_travel_timers.const import CONF_CLOSED_SETTLE

from .conftest import CONTACT, COVER, PHASE, SOURCE, setup_door


@pytest.fixture
def pulses(hass: HomeAssistant) -> dict[str, list]:
    """Record every open/close call sent to the pulse cover."""
    sent: dict[str, list] = {"open": [], "close": []}

    @callback
    def record(event: Event) -> None:
        data = event.data
        ids = data["service_data"].get(ATTR_ENTITY_ID)
        if data["domain"] == "cover" and ids in (SOURCE, [SOURCE]):
            sent[data["service"].removesuffix("_cover")].append(event)

    hass.bus.async_listen(EVENT_CALL_SERVICE, record)
    return sent


async def tick(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory, seconds: float
) -> None:
    """Let time pass."""
    freezer.tick(timedelta(seconds=seconds))
    async_fire_time_changed_exact(hass)  # no 0.5 s bump: timing is sub-second
    await hass.async_block_till_done()


async def press(hass: HomeAssistant, service: str) -> None:
    """Press a button on the tracked cover."""
    await hass.services.async_call(
        "cover", service, {ATTR_ENTITY_ID: COVER}, blocking=True
    )
    await hass.async_block_till_done()


def phase(hass: HomeAssistant) -> str:
    return hass.states.get(PHASE).state


def cover(hass: HomeAssistant) -> State:
    return hass.states.get(COVER)


async def test_full_open(hass, entry, pulses, freezer) -> None:
    """A pulse at closed runs the full open time; the contact letting go doesn't restart it."""
    await setup_door(hass, entry, "off")
    assert phase(hass) == "closed"
    assert cover(hass).state == "closed"

    await press(hass, "open_cover")
    assert len(pulses["open"]) == 1
    assert phase(hass) == "opening"
    assert cover(hass).state == "opening"

    await tick(hass, freezer, 1.5)
    hass.states.async_set(CONTACT, "on")
    await hass.async_block_till_done()
    assert phase(hass) == "opening"

    await tick(hass, freezer, 6)  # 7.5 s of 15
    assert cover(hass).attributes["current_position"] == 50

    await tick(hass, freezer, 7.4)
    assert phase(hass) == "opening"
    await tick(hass, freezer, 0.2)  # sub-second: done at 15.0 s, not rounded
    assert phase(hass) == "open"
    assert cover(hass).state == "open"
    assert cover(hass).attributes["current_position"] == 100


async def test_full_close(hass, entry, pulses, freezer) -> None:
    """Closing only ends at the closed contact."""
    await setup_door(hass, entry, "on")
    assert cover(hass).state == "open"

    await press(hass, "close_cover")
    assert len(pulses["close"]) == 1
    assert phase(hass) == "closing"

    await tick(hass, freezer, 10.5)  # half of 21 s
    assert cover(hass).attributes["current_position"] == 50

    await tick(hass, freezer, 12)  # past the close time: still closing (margin)
    assert phase(hass) == "closing"
    assert cover(hass).attributes["current_position"] == 0

    hass.states.async_set(CONTACT, "off")
    await hass.async_block_till_done()
    assert phase(hass) == "closed"
    assert cover(hass).state == "closed"


async def test_close_without_contact_is_obstructed(
    hass, entry, pulses, freezer
) -> None:
    """Full close time plus close margin with no contact: obstructed."""
    await setup_door(hass, entry, "on")
    await press(hass, "close_cover")

    await tick(hass, freezer, 25.9)
    assert phase(hass) == "closing"
    await tick(hass, freezer, 0.2)
    assert phase(hass) == "obstructed"
    assert cover(hass).attributes.get("current_position") is None

    # A pulse from obstructed opens (the safe direction).
    await press(hass, "open_cover")
    assert phase(hass) == "opening"


async def test_stop_then_reverse(hass, entry, pulses, freezer) -> None:
    """Stop resends the travel direction's pulse; the next pulse reverses."""
    await setup_door(hass, entry, "on")
    await press(hass, "close_cover")
    await tick(hass, freezer, 7)  # 7 s of 21: a third of the way down

    await press(hass, "stop_cover")
    assert len(pulses["close"]) == 2  # stop = same-direction pulse
    assert phase(hass) == "stopping"
    assert cover(hass).attributes["current_position"] == 67

    # Nothing is offered until the door has settled.
    await press(hass, "open_cover")
    assert len(pulses["open"]) == 0

    await tick(hass, freezer, 2)
    assert phase(hass) == "stopped_closing"
    assert cover(hass).attributes["current_position"] == 67

    # Reverse: back up from 10 s of openness, plus the motor allowance.
    await press(hass, "open_cover")
    assert len(pulses["open"]) == 1
    assert phase(hass) == "opening"
    await tick(hass, freezer, 7.4)  # 15 - 10 + 2.5 = 7.5 s
    assert phase(hass) == "opening"
    assert cover(hass).attributes["current_position"] == 100
    await tick(hass, freezer, 0.2)
    assert phase(hass) == "open"


async def test_stop_on_the_way_up_then_close(hass, entry, pulses, freezer) -> None:
    """After a stop going up, the next pulse closes with the full close time and margin."""
    await setup_door(hass, entry, "off")
    await press(hass, "open_cover")
    await tick(hass, freezer, 3)
    await press(hass, "stop_cover")
    assert len(pulses["open"]) == 2
    await tick(hass, freezer, 2)
    assert phase(hass) == "stopped_opening"
    assert cover(hass).attributes["current_position"] == 20

    await press(hass, "close_cover")
    assert phase(hass) == "closing"
    await tick(hass, freezer, 25.9)  # short rise, still the full 21 + 5
    assert phase(hass) == "closing"
    await tick(hass, freezer, 0.2)
    assert phase(hass) == "obstructed"


async def test_fob_start(hass, entry, pulses, freezer) -> None:
    """The contact letting go with no pulse: a full open, the sensor offset in."""
    await setup_door(hass, entry, "off")
    hass.states.async_set(CONTACT, "on")
    await hass.async_block_till_done()

    assert phase(hass) == "opening"
    assert cover(hass).attributes["current_position"] == 10  # 1.5 of 15 s
    assert not pulses["open"]

    await tick(hass, freezer, 13.4)
    assert phase(hass) == "opening"
    await tick(hass, freezer, 0.2)
    assert phase(hass) == "open"


async def test_pulse_from_elsewhere(hass, entry, pulses, freezer) -> None:
    """A call to the pulse cover from anywhere counts, not only from this cover."""
    await setup_door(hass, entry, "off")
    await hass.services.async_call(
        "cover", "open_cover", {ATTR_ENTITY_ID: SOURCE}, blocking=True
    )
    await hass.async_block_till_done()
    assert phase(hass) == "opening"


async def test_buttons_only_pulse_the_asked_way(hass, entry, pulses) -> None:
    """Open while open, close while closed and stop at rest send nothing."""
    await setup_door(hass, entry, "off")
    await press(hass, "close_cover")
    await press(hass, "stop_cover")
    assert not pulses["open"] and not pulses["close"]
    assert phase(hass) == "closed"


async def test_closed_settle_time(hass, entry, pulses, freezer) -> None:
    """With a settle time, the contact must stay closed that long."""
    await setup_door(hass, entry, "on")
    hass.config_entries.async_update_entry(  # applies live, no reload
        entry, options={**entry.options, CONF_CLOSED_SETTLE: 1.5}
    )
    await press(hass, "close_cover")
    await tick(hass, freezer, 20)

    hass.states.async_set(CONTACT, "off")
    await hass.async_block_till_done()
    assert phase(hass) == "closing"
    await tick(hass, freezer, 1)
    hass.states.async_set(CONTACT, "on")  # bounced
    await hass.async_block_till_done()
    hass.states.async_set(CONTACT, "off")
    await hass.async_block_till_done()
    await tick(hass, freezer, 1.4)
    assert phase(hass) == "closing"
    await tick(hass, freezer, 0.2)
    assert phase(hass) == "closed"


async def test_restore_trusts_the_contact(hass, entry: MockConfigEntry, pulses) -> None:
    """After a restart: the contact first, then the last state."""
    mock_restore_cache_with_extra_data(
        hass,
        [(State(COVER, "open"), {"phase": "stopped_closing", "position": 9.0})],
    )
    await setup_door(hass, entry, "on")
    assert phase(hass) == "stopped_closing"
    assert cover(hass).attributes["current_position"] == 60


async def test_restore_closed_contact_wins(hass, entry, pulses) -> None:
    """A closed contact beats whatever was saved."""
    mock_restore_cache_with_extra_data(
        hass, [(State(COVER, "open"), {"phase": "open", "position": 15.0})]
    )
    await setup_door(hass, entry, "off")
    assert phase(hass) == "closed"


async def test_restore_mid_run(hass, entry, pulses) -> None:
    """Restarted mid-close with the contact still open: open, position unknown."""
    mock_restore_cache_with_extra_data(
        hass, [(State(COVER, "closing"), {"phase": "closing", "position": 7.0})]
    )
    await setup_door(hass, entry, "on")
    assert phase(hass) == "open"
    assert cover(hass).attributes.get("current_position") is None


async def test_toggle_is_one_pulse(hass, entry, pulses, freezer) -> None:
    """Tapping toggle steps through close, stop, reverse, like the wall button."""
    await setup_door(hass, entry, "on")
    await press(hass, "toggle")  # open -> close
    assert phase(hass) == "closing"
    assert len(pulses["close"]) == 1

    await tick(hass, freezer, 5)
    await press(hass, "toggle")  # moving -> stop, same direction
    assert phase(hass) == "stopping"
    assert len(pulses["close"]) == 2

    await press(hass, "toggle")  # settling: nothing
    assert len(pulses["open"]) == 0 and len(pulses["close"]) == 2

    await tick(hass, freezer, 2)
    assert phase(hass) == "stopped_closing"
    await press(hass, "toggle")  # stopped on the way down -> back up
    assert phase(hass) == "opening"
    assert len(pulses["open"]) == 1


async def test_toggle_from_closed(hass, entry, pulses, freezer) -> None:
    """Closed: toggle opens."""
    await setup_door(hass, entry, "off")
    await press(hass, "toggle")
    assert phase(hass) == "opening"
    assert len(pulses["open"]) == 1
