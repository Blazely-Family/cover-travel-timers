# Cover Travel Timers

A Home Assistant integration that tracks the position of a garage door or gate
driven by a single-pulse controller that only reports closed / not closed.

Many door controllers take one pulse to move: the first pulse starts the door,
a pulse mid-travel stops it, and the next pulse reverses it. Their Home
Assistant cover usually fakes "opening" and "closing" with a fixed timer and
loses track after a mid-travel stop. Cover Travel Timers follows the door from what is
known for sure:

- the pulses sent to the controller (`cover.open_cover` / `cover.close_cover`
  on its cover, from this integration or from anywhere else in Home Assistant)
- the closed contact (a `binary_sensor` that is off when the door is closed)
- a handful of timings you tune in the UI

It adds a **cover** with a real position and opening/closing states, and a
**phase** sensor.

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
- **Tunables** apply from the next run when you save them; nothing is reloaded.

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
   - **Name**: use a name that differs from the pulse cover's, so the entity
     ids don't clash.
   - **Pulse cover**: the controller's cover whose open/close sends a pulse.
   - **Closed contact**: the binary sensor that is off when the door is closed.
   - **Type**: garage door or gate.
3. Open the new entry's **Configure** to set the timings (seconds, decimals
   allowed):

| Option | Default | What it is |
| --- | --- | --- |
| Full open time | 15 | From a pulse at closed to fully open |
| Full close time | 21 | From a pulse at fully open to the closed contact |
| Sensor offset | 1.5 | How far into an opening the closed contact lets go |
| Motor allowance | 2.5 | Added to a reverse back up after a stop on the way down |
| Close margin | 5 | Added to every closing run before it is called obstructed |
| Closed settle time | 0 | How long the contact must stay closed before the door counts as closed (raise it for a gate that reports closed while still tensioning) |

Add one entry per door.

## Development

Tests use `pytest-homeassistant-custom-component` and run in CI on Linux:

```sh
pip install -r requirements_test.txt
pytest
```

## Licence

MIT
