"""The door's travel, tracked from pulses and the closed contact.

The controller takes a single pulse and only reports closed / not closed, so
the door is tracked from what is known for sure:

- the pulses sent to it (open_cover / close_cover on the source cover, from
  this integration or anything else in Home Assistant)
- the closed contact
- the tunables in the options flow

Position is seconds of openness: 0 is closed, the full open time is fully
open. Opening adds real seconds; closing removes them scaled by open/close
time.

    closed  --pulse--> opening (full open time)  --done--> open
    open    --pulse--> closing                   --closed contact--> closed
    opening --pulse--> stopping --> stopped_opening --pulse--> closing
    closing --pulse--> stopping --> stopped_closing --pulse--> opening
    a closing run that ends without the closed contact: obstructed
    obstructed --pulse--> opening (position unknown, full open time)
    the closed contact always resets to closed (the recovery path)
    the door leaving closed with no pulse (fob, app): a full open, already
    the sensor offset into its travel

Closed only ever comes from the contact. The door eases into the closed
position, so every closing run, from any position, gets the full close time
plus the close margin before it is called obstructed.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from datetime import datetime
import logging
from typing import Any

from homeassistant.const import (
    ATTR_ENTITY_ID,
    EVENT_CALL_SERVICE,
    SERVICE_CLOSE_COVER,
    SERVICE_OPEN_COVER,
    STATE_OFF,
    STATE_ON,
)
from homeassistant.core import (
    CALLBACK_TYPE,
    Event,
    EventStateChangedData,
    HomeAssistant,
    callback,
)
from homeassistant.helpers.event import async_call_later, async_track_state_change_event
from homeassistant.util import dt as dt_util

from .const import (
    CONF_CLOSE_MARGIN,
    CONF_CLOSE_TIME,
    CONF_CLOSED_SETTLE,
    CONF_MOTOR_ALLOWANCE,
    CONF_OPEN_TIME,
    CONF_SENSOR_OFFSET,
    DEFAULTS,
    STOP_SETTLE,
    Phase,
)

_LOGGER = logging.getLogger(__name__)

COVER_DOMAIN = "cover"
PULSE_SERVICES = (SERVICE_OPEN_COVER, SERVICE_CLOSE_COVER)
MOVING = (Phase.OPENING, Phase.CLOSING)


class DoorTracker:
    """State machine for one door."""

    def __init__(
        self,
        hass: HomeAssistant,
        source: str,
        contact: str,
        options: Mapping[str, Any],
    ) -> None:
        """Set up the tracker; call async_start to begin listening."""
        self.hass = hass
        self.source = source
        self.contact = contact
        self.options = options
        self.phase: Phase | None = None
        self._start_pos: float | None = None
        self._since: datetime = dt_util.utcnow()
        self._run_timer: CALLBACK_TYPE | None = None
        self._settle_timer: CALLBACK_TYPE | None = None
        self._listeners: list[Callable[[], None]] = []

    # Tunables, read live so option changes apply to the next run.

    def _opt(self, key: str) -> float:
        return float(self.options.get(key, DEFAULTS[key]))

    @property
    def t_open(self) -> float:
        """Full open time, s."""
        return max(self._opt(CONF_OPEN_TIME), 0.1)

    @property
    def t_close(self) -> float:
        """Full close time, s."""
        return max(self._opt(CONF_CLOSE_TIME), 0.1)

    # Position.

    @property
    def position(self) -> float | None:
        """Seconds of openness now, or None when unknown."""
        if self._start_pos is None:
            return None
        elapsed = (dt_util.utcnow() - self._since).total_seconds()
        if self.phase == Phase.OPENING:
            return min(self._start_pos + elapsed, self.t_open)
        if self.phase == Phase.CLOSING:
            return max(self._start_pos - elapsed * self.t_open / self.t_close, 0.0)
        return self._start_pos

    @property
    def percent(self) -> int | None:
        """Position as 0-100, or None when unknown."""
        pos = self.position
        if pos is None:
            return None
        return round(min(max(pos / self.t_open, 0.0), 1.0) * 100)

    # Commands. Each sends one pulse, and only when that pulse moves the door
    # the asked way. The controller ignores a cover stop, so stop resends a
    # pulse in the direction of travel.

    async def async_open(self) -> None:
        """Pulse if the next pulse sends the door up."""
        if self.phase in (Phase.CLOSED, Phase.OBSTRUCTED, Phase.STOPPED_CLOSING):
            await self._send(SERVICE_OPEN_COVER)

    async def async_close(self) -> None:
        """Pulse if the next pulse sends the door down."""
        if self.phase in (Phase.OPEN, Phase.STOPPED_OPENING):
            await self._send(SERVICE_CLOSE_COVER)

    async def async_stop(self) -> None:
        """Pulse if the door is moving."""
        if self.phase == Phase.OPENING:
            await self._send(SERVICE_OPEN_COVER)
        elif self.phase == Phase.CLOSING:
            await self._send(SERVICE_CLOSE_COVER)

    async def _send(self, service: str) -> None:
        # The call_service event this fires is what moves the state machine,
        # the same as a call from anywhere else.
        await self.hass.services.async_call(
            COVER_DOMAIN, service, {ATTR_ENTITY_ID: self.source}, blocking=True
        )

    # Listeners (the entities).

    @callback
    def async_add_listener(self, update: Callable[[], None]) -> CALLBACK_TYPE:
        """Call update whenever the phase or position changes."""
        self._listeners.append(update)
        return lambda: self._listeners.remove(update)

    @callback
    def _notify(self) -> None:
        for update in list(self._listeners):
            update()

    # Lifecycle.

    @callback
    def async_start(self) -> CALLBACK_TYPE:
        """Listen for pulses and the contact; returns the unsubscribe."""
        unsubs = [
            self.hass.bus.async_listen(
                EVENT_CALL_SERVICE,
                self._on_call_service,
                event_filter=self._is_pulse,
            ),
            async_track_state_change_event(self.hass, self.contact, self._on_contact),
        ]

        @callback
        def stop() -> None:
            for unsub in unsubs:
                unsub()
            self._cancel_run()
            self._cancel_settle()

        return stop

    @callback
    def async_restore(self, phase: str | None, position: float | None) -> None:
        """Set the starting state: trust the contact, then the last state."""
        contact = self.hass.states.get(self.contact)
        contact_state = contact.state if contact else None
        last = Phase(phase) if phase in set(Phase) else None
        resting = (Phase.OPEN, Phase.STOPPED_OPENING, Phase.STOPPED_CLOSING)

        if contact_state == STATE_OFF or (
            contact_state != STATE_ON and last == Phase.CLOSED
        ):
            self._set(Phase.CLOSED, 0.0)
        elif last in resting:
            self._set(last, position)
        elif last == Phase.OBSTRUCTED:
            self._set(Phase.OBSTRUCTED, None)
        elif last == Phase.OPENING:
            # It finished its run while Home Assistant was down.
            self._set(Phase.OPEN, self.t_open)
        else:
            # Not closed, and no telling where: open, position unknown.
            self._set(Phase.OPEN, None)
        self._notify()

    # Inputs.

    @callback
    def _is_pulse(self, data: Mapping[str, Any]) -> bool:
        """Only open/close calls that target the source cover are pulses."""
        if (
            data.get("domain") != COVER_DOMAIN
            or data.get("service") not in PULSE_SERVICES
        ):
            return False
        ids = (data.get("service_data") or {}).get(ATTR_ENTITY_ID, [])
        if isinstance(ids, str):
            ids = [ids]
        return self.source in ids

    @callback
    def _on_call_service(self, event: Event) -> None:
        self._pulse()

    @callback
    def _on_contact(self, event: Event[EventStateChangedData]) -> None:
        old = event.data["old_state"]
        new = event.data["new_state"]
        if new is None:
            return
        if new.state == STATE_OFF:
            settle = self._opt(CONF_CLOSED_SETTLE)
            self._cancel_settle()
            if settle > 0:
                self._settle_timer = async_call_later(
                    self.hass, settle, self._on_closed_settled
                )
            else:
                self._closed()
        elif new.state == STATE_ON:
            self._cancel_settle()
            if (
                old is not None
                and old.state == STATE_OFF
                and self.phase == Phase.CLOSED
            ):
                self._left_closed()

    @callback
    def _on_closed_settled(self, _now: datetime) -> None:
        self._settle_timer = None
        self._closed()

    # Transitions.

    @callback
    def _closed(self) -> None:
        """The closed contact is the one hard truth: reset."""
        self._cancel_run()
        self._set(Phase.CLOSED, 0.0)
        self._notify()

    @callback
    def _left_closed(self) -> None:
        """Left closed with no pulse first (fob, app): a full open, backdated."""
        offset = min(self._opt(CONF_SENSOR_OFFSET), self.t_open)
        self._run(Phase.OPENING, offset, self.t_open - offset)

    @callback
    def _pulse(self) -> None:
        phase = self.phase
        _LOGGER.debug("%s: pulse while %s", self.source, phase)
        if phase in (Phase.CLOSED, Phase.OBSTRUCTED):
            # Obstructed: position unknown, so trust a full open (the safe
            # direction); the contact recovers.
            self._run(Phase.OPENING, 0.0, self.t_open)
        elif phase in (Phase.OPEN, Phase.STOPPED_OPENING):
            # Closed comes only from the contact; the run is just the
            # obstruction check.
            start = self._start_pos if phase == Phase.STOPPED_OPENING else None
            if start is None:
                start = self.t_open
            self._run(
                Phase.CLOSING,
                start,
                self.t_close + self._opt(CONF_CLOSE_MARGIN),
            )
        elif phase in MOVING:
            self._stop()
        elif phase == Phase.STOPPED_CLOSING:
            # Reverse: back up from where it stopped.
            start = self._start_pos if self._start_pos is not None else 0.0
            self._run(
                Phase.OPENING,
                start,
                self.t_open - start + self._opt(CONF_MOTOR_ALLOWANCE),
            )
        # STOPPING: the controller doesn't take a pulse straight after a stop.

    @callback
    def _stop(self) -> None:
        direction = self.phase
        self._cancel_run()
        pos = self.position
        self._set(Phase.STOPPING, None if pos is None else round(pos, 1))
        self._notify()

        @callback
        def settled(_now: datetime) -> None:
            self._run_timer = None
            self._set(
                Phase.STOPPED_OPENING
                if direction == Phase.OPENING
                else Phase.STOPPED_CLOSING,
                self._start_pos,
            )
            self._notify()

        self._run_timer = async_call_later(self.hass, STOP_SETTLE, settled)

    @callback
    def _run(self, phase: Phase, start: float, duration: float) -> None:
        self._cancel_run()
        self._set(phase, start)
        self._run_timer = async_call_later(
            self.hass, max(duration, 0.0), self._on_run_done
        )
        self._notify()

    @callback
    def _on_run_done(self, _now: datetime) -> None:
        self._run_timer = None
        if self.phase == Phase.OPENING:
            self._set(Phase.OPEN, self.t_open)
        elif self.phase == Phase.CLOSING:
            # Should have closed by now but the contact hasn't said so.
            self._set(Phase.OBSTRUCTED, None)
        self._notify()

    # Helpers.

    @callback
    def _set(self, phase: Phase, position: float | None) -> None:
        self.phase = phase
        self._start_pos = position
        self._since = dt_util.utcnow()

    @callback
    def _cancel_run(self) -> None:
        if self._run_timer:
            self._run_timer()
            self._run_timer = None

    @callback
    def _cancel_settle(self) -> None:
        if self._settle_timer:
            self._settle_timer()
            self._settle_timer = None
