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

For each door it adds a device of its own holding a **cover** with a position
and opening/closing states, a **phase** sensor, and a **number** for each
timing.

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
- **Toggle** (a tap on a dashboard button) sends exactly one pulse, like the
  controller's own button: stop if moving, otherwise whatever the door does
  next (back up after a stop on the way down).
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
   - **Pulse cover**: the controller's cover whose open/close sends a pulse.
   - **Closed contact**: the binary sensor that is off when the door is closed.
   - **Name** (optional): leave it empty for the pulse cover's name plus
     "Timer", for example "Front Gate Timer".
   - **Type**: garage door or gate.
3. Set the timings, either on the door's device page (the numbers under
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

Each door is a device of its own, named after the entry (for example "Front
Gate Timer"), with the cover, the phase sensor and the six timing numbers on
it. Open it from **Settings → Devices & services → Cover Travel Timers** to see
everything for that door in one place.

When the pulse cover belongs to a device, the door's device is connected via
it, so its page shows "Connected via" the controller, and it starts in the
controller's area (change the area if you like; yours is kept). If the pulse
cover has no device, the door's device stands alone.

Upgrading from 0.2.0 to 0.3.1 (when the entities sat on the controller's
device) moves them onto the door's own device and keeps their entity ids.

## Entity ids

Entity ids follow the pulse cover's id plus `_timer`, whatever the door is
called, so they never clash with the pulse cover:

| Pulse cover | Cover | Phase | Timings |
| --- | --- | --- | --- |
| `cover.front_gate` | `cover.front_gate_timer` | `sensor.front_gate_timer_phase` | `number.front_gate_timer_full_open_time`, ... |

The timing numbers end in `full_open_time`, `full_close_time`,
`sensor_offset`, `motor_allowance`, `close_margin` and `closed_settle_time`.
These are suggestions for new entities: an id already in Home Assistant's
entity registry, including one you have renamed, is kept.


## Which cover a timer follows

The timed cover and the phase sensor carry two attributes, `source_cover` and
`closed_contact`, naming the pulse cover and closed contact they follow. They
never change, so the recorder leaves them out.

To point a door at another cover or contact, open the entry's **Configure**:
the pulse cover and closed contact are at the top, above the timings (the
picker leaves out the timed covers themselves). Saving a new one reloads the
door and connects its device via the new pulse cover's device. The entity ids
stay as they are, even though they were named after the old cover; rename
them yourself if you want them to match. Saving only timings doesn't reload.

## Development

Tests use `pytest-homeassistant-custom-component` and run in CI on Linux:

```sh
pip install -r requirements_test.txt
pytest
```

## Licence

MIT
