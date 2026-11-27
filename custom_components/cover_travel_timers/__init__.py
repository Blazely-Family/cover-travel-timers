"""Cover Travel Timers: position tracking for pulse-driven doors and gates."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .const import CONF_CONTACT, CONF_SOURCE
from .tracker import DoorTracker

PLATFORMS = [Platform.COVER, Platform.SENSOR]

type CoverTravelTimersConfigEntry = ConfigEntry[DoorTracker]


async def async_setup_entry(
    hass: HomeAssistant, entry: CoverTravelTimersConfigEntry
) -> bool:
    """Set up one door."""
    entry.runtime_data = DoorTracker(
        hass, entry.data[CONF_SOURCE], entry.data[CONF_CONTACT], entry.options
    )
    entry.async_on_unload(entry.add_update_listener(_async_options_updated))
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def _async_options_updated(
    hass: HomeAssistant, entry: CoverTravelTimersConfigEntry
) -> None:
    """New tunables apply from the next run; no reload, so no lost state."""
    entry.runtime_data.options = entry.options


async def async_unload_entry(
    hass: HomeAssistant, entry: CoverTravelTimersConfigEntry
) -> bool:
    """Unload one door."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
