"""Shared base for Cover Travel Timers entities."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import Entity

from .const import DOMAIN
from .tracker import DoorTracker


class CoverTravelTimersEntity(Entity):
    """An entity that follows one door's tracker."""

    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(self, entry: ConfigEntry, key: str) -> None:
        """Attach to the entry's door."""
        self.tracker: DoorTracker = entry.runtime_data
        self._attr_unique_id = f"{entry.entry_id}_{key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=entry.title,
        )

    async def async_added_to_hass(self) -> None:
        """Update whenever the door's phase or position changes."""
        await super().async_added_to_hass()
        self.async_on_remove(self.tracker.async_add_listener(self.async_write_ha_state))
