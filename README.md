# Cover Travel Timers

A Home Assistant integration that tracks the position of a garage door or gate
driven by a single-pulse controller that only reports closed / not closed.

Many door controllers take one pulse to move: the first pulse starts the door,
a pulse mid-travel stops it, and the next pulse reverses it. Cover Travel
Timers follows the door from what is known for sure:

- the pulses sent to the controller (`cover.open_cover` / `cover.close_cover`
  on its cover, from this integration or from anywhere else in Home Assistant)
- the closed contact (a `binary_sensor` that is off when the door is closed)
- a handful of timings you tune in the UI

For each door it adds a **cover** with a position and opening/closing states, a
**phase** sensor, and a **number** for each timing, all on the controller's own
device.

## When to use this vs your door integration's own travel timers

Some door integrations already simulate travel from fixed timers. The UniFi
Access integration, for example, has door open and close time settings that
show its cover as opening or closing for that long after a command. For a door
with no position sensor, or one you only ever run end to end, that is all you
need.

Cover Travel Timers is for pulse-driven doors that also have a closed contact,
when you want the cover to keep track through:

- **stop and reverse**: a pulse mid-travel stops the door, and the next pulse
  sends it back the other way from where it stopped
- **fob, remote or app starts** that Home Assistant didn't send, picked up from
  the closed contact
- **obstructed**: a closing run that never reaches the closed contact
- **sub-second timing**, so runs aren't rounded to whole seconds
- **a closed settle time**, for gates that report closed while still tensioning

It takes its commands from your door integration's cover and adds a separate,
timed cover beside it. Once you use the timed cover (and hide the original),
the door integration's own timers no longer affect what you see. You can leave
them as they are.

## How it tracks the door

| Phase | Means | Next pulse |
| --- | --- | --- |
| `closed` | The closed contact is closed | Opening |
| `opening` | Running up for the full open time | Stop |
| `open` | Finished an opening run | Closing |
| `closing` | Running down until the closed contact | Stop |
| `stopping` | Just stopped; settling for 2 s (the controller ignores a pulse straight after a stop) | Ignored |
| `stopped_opening` | Stopped on the way up | Closing |
| `stopped_closing` | Stopped on the way down | Opening (reverse) |
| `obstructed` | A closing run ended without the closed contact | Opening |

- **Closed only ever comes from the contact.** The contact closing always resets
  the door to closed, from any phase.
- **Every closing run**, from any position, gets the full close time plus the
  close margin before it is called obstructed. Doors ease into the closed
  position, so a short rise can take much longer to come back down.
- **Fob, remote or app starts**: if the contact lets go while the door is
  closed and no pulse was sent, it is treated as a full open that is already
  the sensor offset into its travel.
- **Stop**: many controllers ignore a cover stop, so the cover's Stop sends a
  pulse in the direction of travel. Open and Close only send a pulse when that
  pulse would move the door the way you asked.
- **Timing** is sub-second; nothing is rounded to whole seconds.
- **After a restart** the contact is trusted first: closed if it is closed.
  Otherwise a door at rest keeps its last phase and position, a door that was
  opening is open, and anything else is open with an unknown position.

## Install

### HACS

1. HACS → three-dot menu → **Custom repositories**.
2. Repository `https://github.com/Blazely-Family/cover-travel-timers`, type
   **Integration**, then **Add**.
3. Find **Cover Travel Timers** in HACS, **Download**, then restart Home Assistant.

### Manual

Copy `custom_components/cover_travel_timers` into your Home Assistant
`config/custom_components/` folder and restart.

## Set up a door

1. **Settings → Devices & services → Add integration → Cover Travel Timers.**
2. Fill in:
   - **Name**: for example "Lower Garage Door". Use a name that differs from
     the pulse cover's, so the two covers are easy to tell apart.
   - **Pulse cover**: the controller's cover whose open/close sends a pulse.
   - **Closed contact**: the binary sensor that is off when the door is closed.
   - **Type**: garage door or gate.
3. Set the timings, either on the controller's device page (the numbers under
   **Configuration**) or with the entry's **Configure** button. Both edit the
   same values:

| Timing | Default | What it is |
| --- | --- | --- |
| Full open time | 15 | From a pulse at closed to fully open |
| Full close time | 21 | From a pulse at fully open to the closed contact |
| Sensor offset | 1.5 | How far into an opening the closed contact lets go |
| Motor allowance | 2.5 | Added to a reverse back up after a stop on the way down |
| Close margin | 5 | Added to every closing run before it is called obstructed |
| Closed settle time | 0 | How long the contact must stay closed before the door counts as closed (raise it for a gate that reports closed while still tensioning) |

All are in seconds, and decimals are allowed. A change applies from the door's
next run, and nothing is reloaded, so a door that is moving keeps its state.

4. Optionally hide the original cover (its entity settings → **Visible** off)
   and use the timed one on your dashboards and in automations.

Add one entry per door.

## Device

The entities join the pulse cover's existing device, the way Home Assistant's
own helpers (such as *Change device type of a switch*) do, rather than creating
a device of their own. If the pulse cover has no device, the entities have
none either. Home Assistant shows the device's name in front of each entity's
name, and drops the repeat when the door's name already starts with it. For
example, a device "Lower Garage" with a door "Lower Garage Door" shows
"Lower Garage Door" and "Lower Garage Door Phase".

Upgrading from 0.1.0 moves the existing entities to the pulse cover's device,
keeps their entity ids, and removes the integration's old device.

## Development

Tests use `pytest-homeassistant-custom-component` and run in CI on Linux:

```sh
pip install -r requirements_test.txt
pytest
```

## Licence

MIT
