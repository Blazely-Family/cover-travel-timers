"""Config and options flows: one entry per door."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.components.cover import CoverDeviceClass
from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.const import CONF_DEVICE_CLASS, CONF_NAME, UnitOfTime
from homeassistant.core import callback
from homeassistant.helpers import selector

from .const import (
    CONF_CONTACT,
    CONF_SOURCE,
    DEFAULTS,
    DOMAIN,
    TUNABLE_STEP,
    TUNABLES,
    Tunable,
)

DEVICE_CLASSES = [CoverDeviceClass.GARAGE.value, CoverDeviceClass.GATE.value]


def _seconds(tunable: Tunable) -> selector.NumberSelector:
    return selector.NumberSelector(
        selector.NumberSelectorConfig(
            min=tunable.minimum,
            max=tunable.maximum,
            step=TUNABLE_STEP,
            unit_of_measurement=UnitOfTime.SECONDS,
            mode=selector.NumberSelectorMode.BOX,
        )
    )


def _tunables_schema(values: dict[str, Any]) -> vol.Schema:
    return vol.Schema(
        {
            vol.Required(t.key, default=values.get(t.key, DEFAULTS[t.key])): _seconds(t)
            for t in TUNABLES
        }
    )


USER_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_NAME): selector.TextSelector(),
        vol.Required(CONF_SOURCE): selector.EntitySelector(
            selector.EntitySelectorConfig(domain="cover")
        ),
        vol.Required(CONF_CONTACT): selector.EntitySelector(
            selector.EntitySelectorConfig(domain="binary_sensor")
        ),
        vol.Required(CONF_DEVICE_CLASS, default=CoverDeviceClass.GARAGE.value): (
            selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=DEVICE_CLASSES,
                    translation_key=CONF_DEVICE_CLASS,
                    mode=selector.SelectSelectorMode.LIST,
                )
            )
        ),
    }
)


class CoverTravelTimersConfigFlow(ConfigFlow, domain=DOMAIN):
    """Add a door."""

    VERSION = 2  # 2: entities live on the pulse cover's device

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Name the door and pick its pulse cover and closed contact."""
        if user_input is not None:
            await self.async_set_unique_id(user_input[CONF_SOURCE])
            self._abort_if_unique_id_configured()
            name = user_input.pop(CONF_NAME)
            return self.async_create_entry(
                title=name, data=user_input, options=dict(DEFAULTS)
            )
        return self.async_show_form(step_id="user", data_schema=USER_SCHEMA)

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: ConfigEntry,
    ) -> CoverTravelTimersOptionsFlow:
        """Tune the door's timings."""
        return CoverTravelTimersOptionsFlow()


class CoverTravelTimersOptionsFlow(OptionsFlow):
    """The door's timings, in seconds."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Show and save the tunables."""
        if user_input is not None:
            return self.async_create_entry(data=user_input)
        return self.async_show_form(
            step_id="init",
            data_schema=_tunables_schema(dict(self.config_entry.options)),
        )
