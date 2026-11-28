"""Constants for Cover Travel Timers."""

from enum import StrEnum
from typing import NamedTuple

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


class Tunable(NamedTuple):
    """One timing: its option key, range in seconds and icon."""

    key: str
    minimum: float
    maximum: float
    icon: str


TUNABLES = (
    Tunable(CONF_OPEN_TIME, 1, 300, "mdi:arrow-up-bold"),
    Tunable(CONF_CLOSE_TIME, 1, 300, "mdi:arrow-down-bold"),
    Tunable(CONF_SENSOR_OFFSET, 0, 30, "mdi:ray-start-arrow"),
    Tunable(CONF_MOTOR_ALLOWANCE, 0, 30, "mdi:engine"),
    Tunable(CONF_CLOSE_MARGIN, 0, 120, "mdi:timer-plus-outline"),
    Tunable(CONF_CLOSED_SETTLE, 0, 30, "mdi:timer-sand"),
)
TUNABLE_STEP = 0.1

# State attributes naming the entities a door is tied to.
ATTR_SOURCE_COVER = "source_cover"
ATTR_CLOSED_CONTACT = "closed_contact"

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
