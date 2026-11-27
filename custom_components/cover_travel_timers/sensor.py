"""The door's phase as an enum sensor."""

from __future__ import annotations

from homeassistant.components.sensor import (
    DOMAIN as SENSOR_DOMAIN,
    SensorDeviceClass,
    SensorEntity,
)
from homeassistant.const import CONF_DEVICE_CLASS
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import CoverTravelTimersConfigEntry
from .const import Phase
from .entity import CoverTravelTimersEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: CoverTravelTimersConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Add the door's phase sensor."""
    async_add_entities([CoverTravelTimersPhaseSensor(hass, entry)])


class CoverTravelTimersPhaseSensor(CoverTravelTimersEntity, SensorEntity):
    """closed, opening, open, closing, stopping, stopped_*, obstructed."""

    _attr_device_class = SensorDeviceClass.ENUM
    _attr_options = [phase.value for phase in Phase]
    _attr_translation_key = "phase"

    def __init__(
        self, hass: HomeAssistant, entry: CoverTravelTimersConfigEntry
    ) -> None:
        """Set up the sensor."""
        super().__init__(hass, entry, SENSOR_DOMAIN, "phase", "Phase")
        self._kind = entry.data[CONF_DEVICE_CLASS]  # garage or gate

    @property
    def native_value(self) -> str | None:
        """The current phase."""
        return self.tracker.phase

    @property
    def icon(self) -> str:
        """The door's own icon, closed or open."""
        closed = self.tracker.phase == Phase.CLOSED
        return f"mdi:{self._kind}" if closed else f"mdi:{self._kind}-open"
