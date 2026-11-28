"""Cover Travel Timers: position tracking for pulse-driven doors and gates."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .const import CONF_CONTACT, CONF_SOURCE
from .device import async_door_device
from .tracker import DoorTracker

PLATFORMS = [Platform.COVER, Platform.NUMBER, Platform.SENSOR]

type CoverTravelTimersConfigEntry = ConfigEntry[DoorTracker]


async def async_setup_entry(
    hass: HomeAssistant, entry: CoverTravelTimersConfigEntry
) -> bool:
    """Set up one door."""
    # Also follows a renamed entry or a pulse cover that moved devices.
    device = async_door_device(hass, entry)
    entry.runtime_data = DoorTracker(
        hass, entry.data[CONF_SOURCE], entry.data[CONF_CONTACT], entry.options
    )
    entry.runtime_data.device_id = device.id
    entry.async_on_unload(entry.add_update_listener(_async_options_updated))
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(
    hass: HomeAssistant, entry: CoverTravelTimersConfigEntry
) -> bool:
    """Unload one door."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def async_migrate_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Move a door's entities onto its own device.

    Version 1 had its own device, version 2 put the entities on the pulse
    cover's device, version 3 has its own device again, connected via the
    pulse cover's.
    """
    if entry.version > 3:
        return False
    if entry.version < 3:
        async_door_device(hass, entry)
        hass.config_entries.async_update_entry(entry, version=3)
    return True


async def _async_options_updated(
    hass: HomeAssistant, entry: CoverTravelTimersConfigEntry
) -> None:
    """New timings apply from the next run; no reload, so no lost state."""
    entry.runtime_data.async_set_options(entry.options)
