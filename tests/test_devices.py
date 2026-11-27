"""Device linking, timing numbers and the version 1 migration."""

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from homeassistant.const import ATTR_ENTITY_ID, CONF_DEVICE_CLASS
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from custom_components.cover_travel_timers.const import (
    CONF_CONTACT,
    CONF_OPEN_TIME,
    CONF_SOURCE,
    DEFAULTS,
    DOMAIN,
)

from .conftest import CONTACT, COVER, PHASE, SOURCE, setup_door

NUMBERS = [
    "number.garage_travel_full_open_time",
    "number.garage_travel_full_close_time",
    "number.garage_travel_sensor_offset",
    "number.garage_travel_motor_allowance",
    "number.garage_travel_close_margin",
    "number.garage_travel_closed_settle_time",
]


@pytest.fixture
def source_device(hass: HomeAssistant) -> dr.DeviceEntry:
    """The pulse cover, on a device of its own integration."""
    controller = MockConfigEntry(domain="test")
    controller.add_to_hass(hass)
    device = dr.async_get(hass).async_get_or_create(
        config_entry_id=controller.entry_id,
        identifiers={("test", "garage")},
        name="Garage controller",
    )
    er.async_get(hass).async_get_or_create(
        "cover",
        "test",
        "garage",
        suggested_object_id="garage_controller",
        config_entry=controller,
        device_id=device.id,
    )
    return device


def our_entities(hass: HomeAssistant, entry: MockConfigEntry) -> list[er.RegistryEntry]:
    return er.async_entries_for_config_entry(er.async_get(hass), entry.entry_id)


async def test_entities_join_the_pulse_cover_device(
    hass: HomeAssistant, entry: MockConfigEntry, source_device: dr.DeviceEntry
) -> None:
    """Every entity sits on the pulse cover's device; no device of our own."""
    await setup_door(hass, entry, "off")

    entities = our_entities(hass, entry)
    assert len(entities) == 8  # cover, phase, six timings
    assert {e.device_id for e in entities} == {source_device.id}
    # Home Assistant puts the device name in front of the id and the name.
    cover = next(e for e in entities if e.domain == "cover")
    assert cover.entity_id == "cover.garage_controller_garage_travel"
    assert hass.states.get(cover.entity_id).name == "Garage controller Garage Travel"
    assert not dr.async_entries_for_config_entry(dr.async_get(hass), entry.entry_id)
    # The pulse cover's device is still only the controller's.
    assert dr.async_get(hass).async_get(source_device.id).name == "Garage controller"


async def test_no_source_device_means_no_device(
    hass: HomeAssistant, entry: MockConfigEntry
) -> None:
    """A pulse cover without a device: the entities have none either."""
    await setup_door(hass, entry, "off")
    assert {e.device_id for e in our_entities(hass, entry)} == {None}
    assert not dr.async_entries_for_config_entry(dr.async_get(hass), entry.entry_id)


async def test_numbers_show_the_options(
    hass: HomeAssistant, entry: MockConfigEntry
) -> None:
    """Each number shows its timing, as a config entity in seconds."""
    await setup_door(hass, entry, "off")
    state = hass.states.get("number.garage_travel_full_open_time")
    assert float(state.state) == DEFAULTS[CONF_OPEN_TIME]
    assert state.attributes["unit_of_measurement"] == "s"
    assert state.attributes["mode"] == "box"
    assert state.attributes["step"] == 0.1
    entity = er.async_get(hass).async_get("number.garage_travel_full_open_time")
    assert entity.entity_category == "config"


async def test_number_saves_to_the_options(
    hass: HomeAssistant, entry: MockConfigEntry
) -> None:
    """Setting a number updates the options and the tracker, with no reload."""
    await setup_door(hass, entry, "off")
    tracker = entry.runtime_data

    await hass.services.async_call(
        "number",
        "set_value",
        {ATTR_ENTITY_ID: "number.garage_travel_full_open_time", "value": 14.6},
        blocking=True,
    )
    await hass.async_block_till_done()

    assert entry.options[CONF_OPEN_TIME] == 14.6
    assert entry.runtime_data is tracker  # same tracker: not reloaded
    assert tracker.t_open == 14.6
    assert float(hass.states.get("number.garage_travel_full_open_time").state) == 14.6


async def test_configure_updates_the_number(
    hass: HomeAssistant, entry: MockConfigEntry
) -> None:
    """Saving Configure shows up on the number."""
    await setup_door(hass, entry, "off")
    result = await hass.config_entries.options.async_init(entry.entry_id)
    await hass.config_entries.options.async_configure(
        result["flow_id"], {**DEFAULTS, CONF_OPEN_TIME: 16.2}
    )
    await hass.async_block_till_done()
    assert float(hass.states.get("number.garage_travel_full_open_time").state) == 16.2


async def test_migrate_from_own_device(
    hass: HomeAssistant, source_device: dr.DeviceEntry
) -> None:
    """Version 1: entities move to the pulse cover's device, ids kept, old device gone."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        version=1,
        title="Garage Travel",
        unique_id=SOURCE,
        data={CONF_SOURCE: SOURCE, CONF_CONTACT: CONTACT, CONF_DEVICE_CLASS: "garage"},
        options=dict(DEFAULTS),
    )
    entry.add_to_hass(hass)
    device_reg = dr.async_get(hass)
    entity_reg = er.async_get(hass)
    old = device_reg.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, entry.entry_id)},
        name="Garage Travel",
    )
    for domain, key, object_id in (
        ("cover", "cover", "garage_travel"),
        ("sensor", "phase", "garage_travel_phase"),
    ):
        entity_reg.async_get_or_create(
            domain,
            DOMAIN,
            f"{entry.entry_id}_{key}",
            suggested_object_id=object_id,
            config_entry=entry,
            device_id=old.id,
        )

    hass.states.async_set(CONTACT, "off")
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.version == 2
    assert device_reg.async_get(old.id) is None
    assert not dr.async_entries_for_config_entry(device_reg, entry.entry_id)
    for entity_id in (COVER, PHASE):
        assert entity_reg.async_get(entity_id).device_id == source_device.id
    assert hass.states.get(COVER).state == "closed"
    assert hass.states.get(PHASE).state == "closed"
    assert len(our_entities(hass, entry)) == 8


async def test_title_starting_with_the_device_name(
    hass: HomeAssistant, entry: MockConfigEntry
) -> None:
    """A title that starts with the device's name isn't doubled up."""
    controller = MockConfigEntry(domain="test")
    controller.add_to_hass(hass)
    device = dr.async_get(hass).async_get_or_create(
        config_entry_id=controller.entry_id,
        identifiers={("test", "garage")},
        name="Garage",
    )
    er.async_get(hass).async_get_or_create(
        "cover",
        "test",
        "garage",
        suggested_object_id="garage_controller",
        config_entry=controller,
        device_id=device.id,
    )
    await setup_door(hass, entry, "off")
    assert hass.states.get(COVER).name == "Garage Travel"
    assert hass.states.get(PHASE).name == "Garage Travel Phase"
    assert hass.states.get(NUMBERS[0]).name == "Garage Travel Full open time"
