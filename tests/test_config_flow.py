"""Config and options flows."""

from homeassistant import config_entries
from homeassistant.const import CONF_DEVICE_CLASS, CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from custom_components.cover_travel_timers.const import (
    CONF_CLOSE_TIME,
    CONF_CONTACT,
    CONF_OPEN_TIME,
    CONF_SOURCE,
    DEFAULTS,
    DOMAIN,
)

from .conftest import CONTACT, SOURCE, setup_door


async def test_user_flow(hass: HomeAssistant) -> None:
    """Adding a door stores the entities and the default timings."""
    hass.states.async_set(CONTACT, "off")
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_NAME: "Garage Travel",
            CONF_SOURCE: SOURCE,
            CONF_CONTACT: CONTACT,
            CONF_DEVICE_CLASS: "garage",
        },
    )
    await hass.async_block_till_done()
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Garage Travel"
    assert result["data"] == {
        CONF_SOURCE: SOURCE,
        CONF_CONTACT: CONTACT,
        CONF_DEVICE_CLASS: "garage",
    }
    assert result["options"] == DEFAULTS
    assert hass.states.get("cover.garage_travel").state == "closed"


async def test_options_flow(hass: HomeAssistant, entry) -> None:
    """Timings save with fractional seconds and apply without a reload."""
    await setup_door(hass, entry, "off")
    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["type"] is FlowResultType.FORM

    new = {**DEFAULTS, CONF_OPEN_TIME: 14.6, CONF_CLOSE_TIME: 20.4}
    result = await hass.config_entries.options.async_configure(result["flow_id"], new)
    await hass.async_block_till_done()
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert entry.options == new
    assert entry.runtime_data.t_open == 14.6
