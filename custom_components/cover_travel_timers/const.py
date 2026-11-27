"""Constants for Cover Travel Timers."""

from enum import StrEnum

DOMAIN = "cover_travel_timers"

CONF_SOURCE = "source_entity"
CONF_CONTACT = "closed_contact"

CONF_OPEN_TIME = "full_open_time"
CONF_CLOSE_TIME = "full_close_time"
CONF_SENSOR_OFFSET = "sensor_offset"
CONF_MOTOR_ALLOWANCE = "motor_allowance"
CONF_CLOSE_MARGIN = "close_margin"
CONF_CLOSED_SETTLE = "closed_settle_time"

DEFAULTS: dict[str, float] = {
    CONF_OPEN_TIME: 15.0,
    CONF_CLOSE_TIME: 21.0,
    CONF_SENSOR_OFFSET: 1.5,
    CONF_MOTOR_ALLOWANCE: 2.5,
    CONF_CLOSE_MARGIN: 5.0,
    CONF_CLOSED_SETTLE: 0.0,
}

# After a stop the controller ignores a pulse sent straight away, so the
# door is left to settle this long before the next pulse counts.
STOP_SETTLE = 2.0


class Phase(StrEnum):
    """Where the door is in its travel."""

    CLOSED = "closed"
    OPENING = "opening"
    OPEN = "open"
    CLOSING = "closing"
    STOPPING = "stopping"
    STOPPED_OPENING = "stopped_opening"
    STOPPED_CLOSING = "stopped_closing"
    OBSTRUCTED = "obstructed"
