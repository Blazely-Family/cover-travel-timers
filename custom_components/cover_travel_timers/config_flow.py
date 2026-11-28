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
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import entity_registry as er, selector

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


def _sources_schema(
    hass: HomeAssistant, source: str | None = None, contact: str | None = None
) -> dict[vol.Marker, Any]:
    """Pickers for the pulse cover and closed contact (defaults when editing).

    The pulse-cover picker leaves out this integration's own timed covers: a
    timer can't drive another timer.
    """
    own_covers = [
        e.entity_id
        for e in er.async_get(hass).entities.values()
        if e.platform == DOMAIN and e.domain == "cover"
    ]
    return {
        vol.Required(CONF_SOURCE, default=source or vol.UNDEFINED): (
            selector.EntitySelector(
                selector.EntitySelectorConfig(
                    domain="cover", exclude_entities=own_covers
                )
            )
        ),
        vol.Required(CONF_CONTACT, default=contact or vol.UNDEFINED): (
            selector.EntitySelector(
                selector.EntitySelectorConfig(domain="binary_sensor")
            )
        ),
    }


def _user_schema(hass: HomeAssistant) -> vol.Schema:
    return vol.Schema(
        {
            **_sources_schema(hass),
            vol.Optional(CONF_NAME): selector.TextSelector(),
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
            name = user_input.pop(CONF_NAME, "").strip() or self._default_name(
                user_input[CONF_SOURCE]
            )
            return self.async_create_entry(
                title=name, data=user_input, options=dict(DEFAULTS)
            )
        return self.async_show_form(step_id="user", data_schema=_user_schema(self.hass))

    def _default_name(self, source: str) -> str:
        """The pulse cover's name plus " Timer"."""
        state = self.hass.states.get(source)
        return f"{state.name if state else source} Timer"

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: ConfigEntry,
    ) -> CoverTravelTimersOptionsFlow:
        """Tune the door's timings."""
        return CoverTravelTimersOptionsFlow()


class CoverTravelTimersOptionsFlow(OptionsFlow):
    """The door's pulse cover, closed contact and timings."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Show and save the sources and timings.

        Timings alone apply live from the next run. A new pulse cover or
        contact is saved to the entry and the entry reloads, which moves the
        entities to the new pulse cover's device; entity ids are kept.
        """
        entry = self.config_entry
        errors: dict[str, str] = {}
        if user_input is not None:
            source = user_input.pop(CONF_SOURCE)
            contact = user_input.pop(CONF_CONTACT)
            changed = (source, contact) != (
                entry.data[CONF_SOURCE],
                entry.data[CONF_CONTACT],
            )
            other = self.hass.config_entries.async_entry_for_domain_unique_id(
                DOMAIN, source
            )
            if other is not None and other.entry_id != entry.entry_id:
                errors[CONF_SOURCE] = "already_configured"
            elif changed:
                self.hass.config_entries.async_update_entry(
                    entry,
                    data={**entry.data, CONF_SOURCE: source, CONF_CONTACT: contact},
                    options=user_input,
                    unique_id=source,
                )
                self.hass.config_entries.async_schedule_reload(entry.entry_id)
                return self.async_create_entry(data=user_input)
            else:
                return self.async_create_entry(data=user_input)
            values = {**user_input, CONF_SOURCE: source, CONF_CONTACT: contact}
        else:
            values = {**entry.data, **entry.options}
        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    **_sources_schema(
                        self.hass, values[CONF_SOURCE], values[CONF_CONTACT]
                    ),
                    **_tunables_schema(values).schema,
                }
            ),
            errors=errors,
        )
