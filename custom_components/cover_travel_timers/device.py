"""Each door's own device, connected via the pulse cover's device."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_DEVICE_CLASS
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.helpers.device import async_entity_id_to_device

from .const import CONF_SOURCE, DOMAIN

MANUFACTURER = "Cover Travel Timers"
MODELS = {"garage": "Garage door timer", "gate": "Gate timer"}


@callback
def async_door_device(hass: HomeAssistant, entry: ConfigEntry) -> dr.DeviceEntry:
    """Create or update the door's device and put all its entities on it.

    The device is named after the entry and is connected via the pulse
    cover's device when that has one, so Home Assistant shows "Connected via
    <controller>". Entities keep their registry entries, and so their ids.
    """
    device_reg = dr.async_get(hass)
    entity_reg = er.async_get(hass)
    source = async_entity_id_to_device(hass, entry.data[CONF_SOURCE])

    device = device_reg.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, entry.entry_id)},
        name=entry.title,
        manufacturer=MANUFACTURER,
        model=MODELS.get(entry.data[CONF_DEVICE_CLASS]),
        via_device_id=source.id if source is not None else None,
    )
    if device.area_id is None and source is not None and source.area_id:
        # Start in the controller's area; an area you set yourself is kept.
        device = device_reg.async_update_device(device.id, area_id=source.area_id)

    for entity in er.async_entries_for_config_entry(entity_reg, entry.entry_id):
        if entity.device_id != device.id:
            entity_reg.async_update_entity(entity.entity_id, device_id=device.id)
    for other in dr.async_entries_for_config_entry(device_reg, entry.entry_id):
        if other.id != device.id:
            device_reg.async_remove_device(other.id)
    return device
