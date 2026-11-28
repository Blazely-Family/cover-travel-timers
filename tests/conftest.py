"""Fixtures for Cover Travel Timers tests."""

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from homeassistant.const import CONF_DEVICE_CLASS
from homeassistant.core import HomeAssistant

from custom_components.cover_travel_timers.const import (
    CONF_CONTACT,
    CONF_SOURCE,
    DEFAULTS,
    DOMAIN,
)

SOURCE = "cover.garage_controller"
CONTACT = "binary_sensor.garage_contact"
COVER = "cover.garage_controller_timer"
PHASE = "sensor.garage_controller_timer_phase"


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    """Load custom_components/ in every test."""
    yield


@pytest.fixture
def entry() -> MockConfigEntry:
    """A garage door with the default timings."""
    return MockConfigEntry(
        domain=DOMAIN,
        version=3,
        title="Garage Travel",
        unique_id=SOURCE,
        data={CONF_SOURCE: SOURCE, CONF_CONTACT: CONTACT, CONF_DEVICE_CLASS: "garage"},
        options=dict(DEFAULTS),
    )


async def setup_door(hass: HomeAssistant, entry: MockConfigEntry, contact: str) -> None:
    """Set the contact, then load the door."""
    hass.states.async_set(CONTACT, contact)
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
