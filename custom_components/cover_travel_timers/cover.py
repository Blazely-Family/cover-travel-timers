"""The door as a cover with a tracked position."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from homeassistant.components.cover import (
    DOMAIN as COVER_DOMAIN,
    CoverDeviceClass,
    CoverEntity,
    CoverEntityFeature,
)
from homeassistant.const import CONF_DEVICE_CLASS
from homeassistant.core import CALLBACK_TYPE, HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.helpers.restore_state import (
    ExtraStoredData,
    RestoredExtraData,
    RestoreEntity,
)

from . import CoverTravelTimersConfigEntry
from .const import Phase
from .entity import CoverTravelTimersEntity

# How often the position is written while the door moves.
MOVING_REFRESH = timedelta(seconds=1)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: CoverTravelTimersConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Add the door's cover."""
    async_add_entities([CoverTravelTimersCover(hass, entry)])


class CoverTravelTimersCover(CoverTravelTimersEntity, CoverEntity, RestoreEntity):
    """Open/close/stop sent as pulses; position from the tracker."""

    _names_sources = True
    _attr_supported_features = (
        CoverEntityFeature.OPEN | CoverEntityFeature.CLOSE | CoverEntityFeature.STOP
    )

    def __init__(
        self, hass: HomeAssistant, entry: CoverTravelTimersConfigEntry
    ) -> None:
        """Set up the cover."""
        super().__init__(hass, entry, COVER_DOMAIN, "cover")
        self._attr_device_class = CoverDeviceClass(entry.data[CONF_DEVICE_CLASS])
        self._refresh: CALLBACK_TYPE | None = None

    async def async_added_to_hass(self) -> None:
        """Restore the last state, then start tracking."""
        await super().async_added_to_hass()
        self.async_on_remove(self.tracker.async_add_listener(self._moving_refresh))
        self.async_on_remove(self._stop_refresh)
        last = await self.async_get_last_extra_data()
        data = last.as_dict() if last else {}
        self.tracker.async_restore(data.get("phase"), data.get("position"))
        self.async_on_remove(self.tracker.async_start())

    @property
    def extra_restore_state_data(self) -> ExtraStoredData:
        """What the tracker needs after a restart."""
        return RestoredExtraData(
            {"phase": self.tracker.phase, "position": self.tracker.position}
        )

    @property
    def current_cover_position(self) -> int | None:
        """0 closed to 100 fully open, None when unknown."""
        return self.tracker.percent

    @property
    def is_closed(self) -> bool | None:
        """Closed only ever comes from the closed contact."""
        if self.tracker.phase is None:
            return None
        return self.tracker.phase == Phase.CLOSED

    @property
    def is_opening(self) -> bool:
        """The door is on its way up."""
        return self.tracker.phase == Phase.OPENING

    @property
    def is_closing(self) -> bool:
        """The door is on its way down."""
        return self.tracker.phase == Phase.CLOSING

    async def async_open_cover(self, **kwargs: Any) -> None:
        """Open."""
        await self.tracker.async_open()

    async def async_close_cover(self, **kwargs: Any) -> None:
        """Close."""
        await self.tracker.async_close()

    async def async_stop_cover(self, **kwargs: Any) -> None:
        """Stop."""
        await self.tracker.async_stop()

    async def async_toggle(self, **kwargs: Any) -> None:
        """One pulse, whatever the door does next (a tap on a dashboard button).

        Home Assistant's default toggle sends Close after a stop on the way
        down, which this cover ignores (the next pulse goes up), so a tap
        would do nothing.
        """
        await self.tracker.async_toggle()

    @callback
    def _moving_refresh(self) -> None:
        """Keep the position current while the door moves."""
        if self.tracker.phase in (Phase.OPENING, Phase.CLOSING):
            if self._refresh is None:
                self._refresh = async_track_time_interval(
                    self.hass, self._write_position, MOVING_REFRESH
                )
        else:
            self._stop_refresh()

    @callback
    def _write_position(self, _now: datetime) -> None:
        self.async_write_ha_state()

    @callback
    def _stop_refresh(self) -> None:
        if self._refresh is not None:
            self._refresh()
            self._refresh = None
