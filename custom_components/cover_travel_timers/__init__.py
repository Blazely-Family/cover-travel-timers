"""Cover Travel Timers: position tracking for pulse-driven doors and gates."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.helpers.device import async_entity_id_to_device_id

from .const import CONF_CONTACT, CONF_SOURCE
from .tracker import DoorTracker

PLATFORMS = [Platform.COVER, Platform.NUMBER, Platform.SENSOR]

type CoverTravelTimersConfigEntry = ConfigEntry[DoorTracker]


async def async_setup_entry(
    hass: HomeAssistant, entry: CoverTravelTimersConfigEntry
) -> bool:
    """Set up one door."""
    _async_link_to_source_device(hass, entry)
    entry.runtime_data = DoorTracker(
        hass, entry.data[CONF_SOURCE], entry.data[CONF_CONTACT], entry.options
    )
    entry.async_on_unload(entry.add_update_listener(_async_options_updated))
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(
    hass: HomeAssistant, entry: CoverTravelTimersConfigEntry
) -> bool:
    """Unload one door."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def async_migrate_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Version 1 had a device of its own; version 2 uses the pulse cover's."""
    if entry.version > 2:
        return False
    if entry.version == 1:
        _async_link_to_source_device(hass, entry)
        hass.config_entries.async_update_entry(entry, version=2)
    return True


async def _async_options_updated(
    hass: HomeAssistant, entry: CoverTravelTimersConfigEntry
) -> None:
    """New timings apply from the next run; no reload, so no lost state."""
    entry.runtime_data.async_set_options(entry.options)


@callback
def _async_link_to_source_device(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Move this entry's entities to the pulse cover's device; drop our own devices.

    The entities keep their registry entries, and so their entity ids: they are
    relinked before any device of ours is removed, so the removal takes nothing
    with it. Runs at every setup, so it also follows a pulse cover that moved.
    """
    device_reg = dr.async_get(hass)
    entity_reg = er.async_get(hass)
    source_device_id = async_entity_id_to_device_id(hass, entry.data[CONF_SOURCE])

    for entity in er.async_entries_for_config_entry(entity_reg, entry.entry_id):
        if entity.device_id != source_device_id:
            entity_reg.async_update_entity(entity.entity_id, device_id=source_device_id)
    for device in dr.async_entries_for_config_entry(device_reg, entry.entry_id):
        device_reg.async_remove_device(device.id)
