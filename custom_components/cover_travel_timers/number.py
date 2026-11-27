"""The door's timings as number entities, backed by the entry's options."""

from __future__ import annotations

from homeassistant.components.number import (
    DOMAIN as NUMBER_DOMAIN,
    NumberEntity,
    NumberMode,
)
from homeassistant.const import EntityCategory, UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import CoverTravelTimersConfigEntry
from .const import (
    CONF_CLOSE_MARGIN,
    CONF_CLOSE_TIME,
    CONF_CLOSED_SETTLE,
    CONF_MOTOR_ALLOWANCE,
    CONF_OPEN_TIME,
    CONF_SENSOR_OFFSET,
    TUNABLE_STEP,
    TUNABLES,
    Tunable,
)
from .entity import CoverTravelTimersEntity

NAMES = {
    CONF_OPEN_TIME: "Full open time",
    CONF_CLOSE_TIME: "Full close time",
    CONF_SENSOR_OFFSET: "Sensor offset",
    CONF_MOTOR_ALLOWANCE: "Motor allowance",
    CONF_CLOSE_MARGIN: "Close margin",
    CONF_CLOSED_SETTLE: "Closed settle time",
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: CoverTravelTimersConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Add a number for each timing."""
    async_add_entities(
        CoverTravelTimersNumber(hass, entry, tunable) for tunable in TUNABLES
    )


class CoverTravelTimersNumber(CoverTravelTimersEntity, NumberEntity):
    """One timing. Saving it updates the options, the same as Configure."""

    _attr_entity_category = EntityCategory.CONFIG
    _attr_mode = NumberMode.BOX
    _attr_native_step = TUNABLE_STEP
    _attr_native_unit_of_measurement = UnitOfTime.SECONDS

    def __init__(
        self,
        hass: HomeAssistant,
        entry: CoverTravelTimersConfigEntry,
        tunable: Tunable,
    ) -> None:
        """Set up the number."""
        super().__init__(hass, entry, NUMBER_DOMAIN, tunable.key, NAMES[tunable.key])
        self._entry = entry
        self._key = tunable.key
        self._attr_native_min_value = tunable.minimum
        self._attr_native_max_value = tunable.maximum
        self._attr_icon = tunable.icon

    @property
    def native_value(self) -> float:
        """The timing now in use."""
        return self.tracker.option(self._key)

    async def async_set_native_value(self, value: float) -> None:
        """Save to the options; the update listener hands them to the tracker."""
        self.hass.config_entries.async_update_entry(
            self._entry, options={**self._entry.options, self._key: value}
        )
