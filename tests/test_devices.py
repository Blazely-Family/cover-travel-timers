"""Device linking, timing numbers and the version 1 migration."""

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from homeassistant.const import ATTR_ENTITY_ID, CONF_DEVICE_CLASS
from homeassistant.core import HomeAssistant
from homeassistant.helpers import (
    area_registry as ar,
    device_registry as dr,
    entity_registry as er,
)

from custom_components.cover_travel_timers.const import (
    CONF_CONTACT,
    CONF_OPEN_TIME,
    CONF_SOURCE,
    DEFAULTS,
    DOMAIN,
)

from .conftest import CONTACT, COVER, PHASE, SOURCE, setup_door

NUMBERS = [
    "number.garage_controller_timer_full_open_time",
    "number.garage_controller_timer_full_close_time",
    "number.garage_controller_timer_sensor_offset",
    "number.garage_controller_timer_motor_allowance",
    "number.garage_controller_timer_close_margin",
    "number.garage_controller_timer_closed_settle_time",
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
    # The id follows the door's name; HA puts the device name in front of the name.
    cover = next(e for e in entities if e.domain == "cover")
    assert cover.entity_id == COVER
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
    state = hass.states.get("number.garage_controller_timer_full_open_time")
    assert float(state.state) == DEFAULTS[CONF_OPEN_TIME]
    assert state.attributes["unit_of_measurement"] == "s"
    assert state.attributes["mode"] == "box"
    assert state.attributes["step"] == 0.1
    entity = er.async_get(hass).async_get(
        "number.garage_controller_timer_full_open_time"
    )
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
        {
            ATTR_ENTITY_ID: "number.garage_controller_timer_full_open_time",
            "value": 14.6,
        },
        blocking=True,
    )
    await hass.async_block_till_done()

    assert entry.options[CONF_OPEN_TIME] == 14.6
    assert entry.runtime_data is tracker  # same tracker: not reloaded
    assert tracker.t_open == 14.6
    assert (
        float(hass.states.get("number.garage_controller_timer_full_open_time").state)
        == 14.6
    )


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
    assert (
        float(hass.states.get("number.garage_controller_timer_full_open_time").state)
        == 16.2
    )


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
        ("cover", "cover", "garage_controller_timer"),
        ("sensor", "phase", "garage_controller_timer_phase"),
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


async def test_new_ids_follow_the_pulse_cover(hass: HomeAssistant) -> None:
    """Brand-new entities get ids from the pulse cover's, plus _timer.

    Like the lower garage: the controller's device is "Lower Garage", in the
    "Lower Garage" area, and the door is "Lower Garage Door".
    """
    area = ar.async_get(hass).async_create("Lower Garage")
    controller = MockConfigEntry(domain="test")
    controller.add_to_hass(hass)
    device_reg = dr.async_get(hass)
    device = device_reg.async_get_or_create(
        config_entry_id=controller.entry_id,
        identifiers={("test", "lower_garage")},
        name="Lower Garage",
    )
    device_reg.async_update_device(device.id, area_id=area.id)
    er.async_get(hass).async_get_or_create(
        "cover",
        "test",
        "lower_garage",
        suggested_object_id="lower_garage",
        config_entry=controller,
        device_id=device.id,
    )
    entry = MockConfigEntry(
        domain=DOMAIN,
        version=2,
        title="Lower Garage Door",
        unique_id="cover.lower_garage",
        data={
            CONF_SOURCE: "cover.lower_garage",
            CONF_CONTACT: CONTACT,
            CONF_DEVICE_CLASS: "garage",
        },
        options=dict(DEFAULTS),
    )
    await setup_door(hass, entry, "off")

    assert sorted(e.entity_id for e in our_entities(hass, entry)) == sorted(
        [
            "cover.lower_garage_timer",
            "sensor.lower_garage_timer_phase",
            "number.lower_garage_timer_full_open_time",
            "number.lower_garage_timer_full_close_time",
            "number.lower_garage_timer_sensor_offset",
            "number.lower_garage_timer_motor_allowance",
            "number.lower_garage_timer_close_margin",
            "number.lower_garage_timer_closed_settle_time",
        ]
    )
    state = hass.states.get("number.lower_garage_timer_full_open_time")
    assert state.name == "Lower Garage Door Full open time"


async def test_existing_ids_are_kept(
    hass: HomeAssistant, entry: MockConfigEntry
) -> None:
    """An id already in the entity registry (e.g. renamed by the user) stays."""
    entry.add_to_hass(hass)
    er.async_get(hass).async_get_or_create(
        "number",
        DOMAIN,
        f"{entry.entry_id}_{CONF_OPEN_TIME}",
        suggested_object_id="my_open_time",
        config_entry=entry,
    )
    hass.states.async_set(CONTACT, "off")
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert hass.states.get("number.my_open_time") is not None
    assert hass.states.get("number.garage_controller_timer_full_open_time") is None


async def test_timer_names_its_cover_and_contact(
    hass: HomeAssistant, entry: MockConfigEntry
) -> None:
    """The cover and phase sensor say which pulse cover and contact they follow."""
    await setup_door(hass, entry, "off")
    for entity_id in (COVER, PHASE):
        attributes = hass.states.get(entity_id).attributes
        assert attributes["source_cover"] == SOURCE
        assert attributes["closed_contact"] == CONTACT
    # The timing numbers stay plain.
    assert "source_cover" not in hass.states.get(NUMBERS[0]).attributes


async def test_source_attributes_are_not_recorded(
    hass: HomeAssistant, entry: MockConfigEntry
) -> None:
    """The names never change, so the recorder leaves them out."""
    await setup_door(hass, entry, "off")
    for platform in ("cover", "sensor"):
        entity = next(
            e
            for e in hass.data["entity_components"][platform].entities
            if e.entity_id in (COVER, PHASE)
        )
        assert {"source_cover", "closed_contact"} <= entity._unrecorded_attributes


def _controller(hass: HomeAssistant, key: str, name: str) -> dr.DeviceEntry:
    """A pulse cover cover.<key> on a device of its own integration."""
    controller = MockConfigEntry(domain="test")
    controller.add_to_hass(hass)
    device = dr.async_get(hass).async_get_or_create(
        config_entry_id=controller.entry_id,
        identifiers={("test", key)},
        name=name,
    )
    er.async_get(hass).async_get_or_create(
        "cover",
        "test",
        key,
        suggested_object_id=key,
        config_entry=controller,
        device_id=device.id,
    )
    return device


async def test_configure_repoints_to_another_cover(
    hass: HomeAssistant, entry: MockConfigEntry, source_device: dr.DeviceEntry
) -> None:
    """A new pulse cover and contact in Configure: entities move, ids stay."""
    other = _controller(hass, "other_door", "Other door")
    await setup_door(hass, entry, "off")
    hass.states.async_set("binary_sensor.other_contact", "on")

    result = await hass.config_entries.options.async_init(entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {
            CONF_SOURCE: "cover.other_door",
            CONF_CONTACT: "binary_sensor.other_contact",
            **DEFAULTS,
        },
    )
    await hass.async_block_till_done()

    assert entry.data[CONF_SOURCE] == "cover.other_door"
    assert entry.data[CONF_CONTACT] == "binary_sensor.other_contact"
    assert entry.unique_id == "cover.other_door"
    entities = our_entities(hass, entry)
    assert len(entities) == 8
    assert {e.device_id for e in entities} == {other.id}
    # Ids stay as they were; the attributes name the new sources.
    attributes = hass.states.get(COVER).attributes
    assert attributes["source_cover"] == "cover.other_door"
    assert attributes["closed_contact"] == "binary_sensor.other_contact"
    # Now following the new contact (open), and pulses on the new cover.
    assert hass.states.get(PHASE).state == "open"
    await hass.services.async_call(
        "cover", "close_cover", {"entity_id": "cover.other_door"}, blocking=True
    )
    await hass.async_block_till_done()
    assert hass.states.get(PHASE).state == "closing"


async def test_configure_refuses_a_cover_with_a_door(
    hass: HomeAssistant, entry: MockConfigEntry
) -> None:
    """Another door's pulse cover can't be picked."""
    taken = MockConfigEntry(
        domain=DOMAIN,
        version=2,
        unique_id="cover.taken",
        data={
            CONF_SOURCE: "cover.taken",
            CONF_CONTACT: "binary_sensor.taken",
            CONF_DEVICE_CLASS: "garage",
        },
    )
    taken.add_to_hass(hass)
    await setup_door(hass, entry, "off")
    result = await hass.config_entries.options.async_init(entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {CONF_SOURCE: "cover.taken", CONF_CONTACT: CONTACT, **DEFAULTS},
    )
    assert result["errors"] == {CONF_SOURCE: "already_configured"}
    assert entry.data[CONF_SOURCE] == SOURCE


async def test_pulse_cover_picker_leaves_out_timers(
    hass: HomeAssistant, entry: MockConfigEntry
) -> None:
    """Timed covers from this integration aren't offered as pulse covers."""
    await setup_door(hass, entry, "off")
    result = await hass.config_entries.options.async_init(entry.entry_id)
    for key in result["data_schema"].schema:
        if key == CONF_SOURCE:
            picker = result["data_schema"].schema[key]
            assert COVER in picker.config["exclude_entities"]
            assert key.default() == SOURCE
            break
    else:
        raise AssertionError("no pulse cover picker")
