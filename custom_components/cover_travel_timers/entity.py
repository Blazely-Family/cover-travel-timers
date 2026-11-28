"""Shared base for Cover Travel Timers entities."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, split_entity_id
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.entity import Entity

from .const import (
    ATTR_CLOSED_CONTACT,
    ATTR_SOURCE_COVER,
    CONF_CONTACT,
    CONF_SOURCE,
)
from .tracker import DoorTracker


class CoverTravelTimersEntity(Entity):
    """An entity that follows one door's tracker.

    All of a door's entities sit on its own device (see device.py), named
    after the entry: the cover is the device itself, the rest are its parts.

    New entities suggest their entity id from the pulse cover's, plus _timer
    (Home Assistant takes an entity_id set before the entity is added as its
    suggestion): cover.lower_garage gives cover.lower_garage_timer,
    sensor.lower_garage_timer_phase and number.lower_garage_timer_<timing>.
    These never clash with the pulse cover. Existing entities keep the id in
    the entity registry.
    """

    _attr_has_entity_name = True
    # Set by subclasses that name the pulse cover and closed contact.
    _names_sources = False
    _unrecorded_attributes = frozenset({ATTR_SOURCE_COVER, ATTR_CLOSED_CONTACT})
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
        self._attr_name = name  # None: the cover, named after the device
        source_object_id = split_entity_id(entry.data[CONF_SOURCE])[1]
        object_id = (
            f"{source_object_id}_timer_{key}" if name else f"{source_object_id}_timer"
        )
        self.entity_id = f"{domain}.{object_id}"
        self.device_entry = dr.async_get(hass).async_get(self.tracker.device_id)
        if self._names_sources:
            # Which cover and contact this door is tied to. They never change,
            # so they are left out of the recorder.
            self._attr_extra_state_attributes = {
                ATTR_SOURCE_COVER: entry.data[CONF_SOURCE],
                ATTR_CLOSED_CONTACT: entry.data[CONF_CONTACT],
            }

    async def async_added_to_hass(self) -> None:
        """Update whenever the door's phase, position or timings change."""
        await super().async_added_to_hass()
        self.async_on_remove(self.tracker.async_add_listener(self.async_write_ha_state))
