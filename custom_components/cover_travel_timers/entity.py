"""Shared base for Cover Travel Timers entities."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device import async_entity_id_to_device
from homeassistant.helpers.entity import Entity
from homeassistant.util import slugify

from .const import CONF_SOURCE
from .tracker import DoorTracker


class CoverTravelTimersEntity(Entity):
    """An entity that follows one door's tracker.

    Linked to the pulse cover's device, as Home Assistant's helpers do, rather
    than a device of its own; with no such device it has none. Names carry the
    entry's title, since the device's own name is the pulse cover's.

    New entities suggest their entity id from that name (Home Assistant takes
    an entity_id set before the entity is added as its suggestion), so they
    match the cover's, e.g. number.lower_garage_door_full_open_time, rather
    than having the device's area and name put in front. Existing entities keep
    the id in the entity registry.
    """

    _attr_has_entity_name = False
    _attr_should_poll = False

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        domain: str,
        key: str,
        name: str | None = None,
    ) -> None:
        """Attach to the entry's door."""
        self.tracker: DoorTracker = entry.runtime_data
        self._attr_unique_id = f"{entry.entry_id}_{key}"
        self._attr_name = f"{entry.title} {name}" if name else entry.title
        self.entity_id = f"{domain}.{slugify(self._attr_name)}"
        self.device_entry = async_entity_id_to_device(hass, entry.data[CONF_SOURCE])

    async def async_added_to_hass(self) -> None:
        """Update whenever the door's phase, position or timings change."""
        await super().async_added_to_hass()
        self.async_on_remove(self.tracker.async_add_listener(self.async_write_ha_state))
