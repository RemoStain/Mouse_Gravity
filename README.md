# N-Body Gravity

N-Body Gravity is a Windows desktop simulation that places movable gravity points on the virtual desktop and lets them attract one another.

The mouse cursor is used only as an input device for placing points and positioning presets. The program does not move the cursor itself.

## Features

- Place gravity points with a double-click.
- Clear all gravity points with a triple-click.
- Exit with a quadruple-click.
- Automatically replace the oldest point when the point limit is reached.
- Simulate mutual attraction between gravity points.
- Give the most recently manually placed point additional influence through placement bias.
- Merge points when they move within the configured merge radius.
- Stop points at the edges of the virtual desktop.
- Spawn predefined point arrangements:
  - Equilateral triangle
  - Five-point radial / pentagram layout
  - Random radial placement
- Display each gravity point as a small click-through green marker.
- Change gravity values at runtime through the settings window.
- Load predefined physics presets.
- Save candidate presets to the log for later review.
- Enable or disable logging from the system tray.
- Record periodic point telemetry for debugging.

## Project Files

```text
.
├── config.py
├── gravity.py
├── gravity_mouse.py
├── settings_window.py
├── README.md
├── Gravity_Settings.md
└── logs/
```

### `gravity_mouse.py`

Main runtime module. It handles mouse click commands, preset spawning, runtime placement-bias state, marker overlays, the physics thread, logging, telemetry, tray controls, startup, and shutdown.

### `gravity.py`

Contains the N-body physics: `GravityPoint`, gravity-strength calculations, pair acceleration, placement-bias behavior, drag, speed limiting, merging, movement integration, and desktop boundaries.

### `config.py`

Contains `GravityConfig`, default values, the hard point limit, and named physics presets.

### `settings_window.py`

Tkinter interface for changing runtime settings, loading presets, saving candidate presets, clearing points, and scheduling point-placement presets.

## Requirements

The current branch targets Windows.

External Python packages:

```text
pynput
pystray
Pillow
```

Install them with:

```powershell
python -m pip install pynput pystray pillow
```

## Running

From the project directory:

```powershell
python gravity_mouse.py
```

The application runs primarily from the system tray.

## Mouse Controls

| Input | Action |
|---|---|
| Double-click | Place a gravity point |
| Triple-click | Clear all gravity points |
| Quadruple-click | Exit |

A click sequence must complete within `click_sequence_timeout`.

## Point Ordering

Gravity points are stored in placement order:

```text
oldest -------------------------- newest
points[0]                         points[-1]
```

When the point limit is reached and a new point is manually placed, the oldest point is removed first.

## Placement Bias

Preset-generated groups begin with no preferred point. After the user manually places a new point, the newest point can become the biased point.

The biased point can:

- Pull older points more strongly through `last_placed_boost`.
- Receive stronger damping through `last_placed_drag`.

This makes the newest manually placed point behave more like a heavy anchor in the existing system.

See `Gravity_Settings.md` for the detailed behavior.

## Placement Presets

### Equilateral Triangle

Creates three equally spaced points around the cursor. Their distance from the cursor is controlled by `triangle_spawn_radius`.

### Pentagram

Creates five equally spaced outer vertices around the cursor. Their distance from the cursor is controlled by `pentagram_spawn_radius`.

### Random Spawn

Creates `random_spawn_number` points at `random_spawn_radius` from the cursor using random angles.

## Physics Overview

Each physics update:

1. Evaluates each unique point pair once.
2. Accumulates pair accelerations.
3. Applies placement bias if active.
4. Updates velocity from acceleration.
5. Applies drag.
6. Limits speed to `point_max_speed`.
7. Updates position.
8. Clamps points to the virtual desktop.
9. Removes the older point when a pair merges.

For `n` points, the number of unique pair calculations is:

```text
n(n - 1) / 2
```

With the current hard limit of seven points:

```text
7 × 6 / 2 = 21 pairs per physics update
```

## Settings

The settings window exposes values for gravity strength, distance scaling, falloff, placement bias, drag, speed limits, merge distance, preset radii, random spawn count, and preset delay.

Detailed explanations and parameter relationships are in `Gravity_Settings.md`.

## Physics Presets

`PRESETS` in `config.py` stores named collections of physics values. Loading a preset fills the settings UI; the running configuration changes only when **Apply** is pressed.

The current branch includes presets such as:

- Balanced
- Stable Orbit
- Heavy Gravity
- Light Gravity
- Eccentic
- Thick Atmosphere
- Sicko Mode

## Logging

Logging can start automatically through `logging_enabled_by_default` or be toggled from the system tray.

Logs are stored in:

```text
logs/
```

with timestamped filenames such as:

```text
nbody_gravity_2026-08-31_16-45-00.log
```

Logged information can include:

- Startup configuration
- Config changes
- Point placement
- Oldest-point replacement
- Merges
- Placement-bias changes
- Preset spawning
- Candidate presets
- Physics errors
- Shutdown
- Point telemetry

### Telemetry

Telemetry can record point index, position, velocity, total speed, and whether the point is biased.

The frequency is controlled by `log_telemetry_hz`.

Higher values produce larger logs and more disk activity.

## Performance

The pair calculation count grows quadratically, but the hard point limit keeps the simulation small.

At seven points and 30 physics updates per second:

```text
21 × 30 = 630 pair evaluations per second
```

This is intentionally low enough to run alongside normal desktop applications.

## Notes

- Marker windows are visual overlays only.
- Marker refresh rate is separate from physics frequency.
- The program uses Windows virtual-desktop coordinates and supports multi-monitor layouts.
- Point positions and velocities remain floating-point values even though markers render at integer pixel coordinates.
