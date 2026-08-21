# Mouse Gravity

Mouse Gravity is a Windows Python utility that gives the mouse cursor momentum and pulls it toward a user-defined target point.

The cursor behaves like an object influenced by gravity rather than moving only according to direct mouse input. You can create curved trajectories and orbit-like motion, amplify lateral movement, and move across multiple monitors.

A system tray icon shows when the program is active.

## Features

- Gravity-based cursor movement toward a selected point
- Momentum and drag
- User-controlled orbital movement
- Lateral boost that amplifies real mouse movement rather than continuously adding energy
- Reduced effectiveness when moving away from the gravity target
- Multi-monitor support using the Windows virtual desktop
- Wall collisions that remove momentum perpendicular to the desktop boundary
- Dark purple vortex system tray icon
- Tray menu with an Exit command
- Quadruple-click emergency exit
- Configurable physics and input constants

## Controls

The mouse controls are based on click count.

| Input | Action |
| --- | --- |
| Single click | Toggle lateral boost on or off |
| Double click | Assign a new gravity target |
| Triple click | Remove target and velocity |
| Quadruple click | Exit the program |

Click sequences are recognized within a configurable timeout.

Because the program must determine whether more clicks are coming, single-click and double-click actions have a short delay before they are processed.

## Lateral Boost

Lateral boost is designed to make orbiting easier without continuously creating energy.

When boost is enabled, the program measures your actual physical mouse movement and increases only the component of that movement that is perpendicular to the direction of gravity.

If you stop physically moving the mouse, lateral boost does not continue accelerating the cursor.

This means you can use physical sideways mouse movements to inject orbital momentum while gravity bends the cursor back toward the target.

## Moving Toward and Away From the Target

Physical input is split into three useful directions:

- movement toward the gravity target
- movement away from the gravity target
- movement sideways relative to the gravity target

Moving away from the target is intentionally less effective than moving toward it.

For example:

```python
TOWARD_INPUT_MULTIPLIER = 1.0
AWAY_INPUT_MULTIPLIER = 0.35
```

With those values, outward physical movement contributes only 30% as much radial momentum as inward movement.

Gravity is also continuously pulling inward, so moving away requires noticeably more effort.

## Multi-Monitor Support

The program uses the Windows virtual desktop coordinate system.

This allows the cursor to pass normally between monitors, including layouts where a display is:

- left of the primary display
- right of the primary display
- above the primary display
- below the primary display

Coordinates may therefore be negative.

The current boundary system treats the outer virtual desktop rectangle as the collision boundary.

If the cursor reaches one of those outer boundaries, momentum pointing through that wall is removed.

For example, when hitting the right boundary:

```text
velocity_x = 700
velocity_y = 400
```

becomes approximately:

```text
velocity_x = 0
velocity_y = 400
```

The cursor can therefore slide along the boundary instead of bouncing.

Note that Windows' virtual desktop is a rectangle containing all monitors. If your physical monitors form an irregular layout, portions of that rectangle may not correspond to an actual display.

## Installation

Python is required.

Install the dependencies with:

```powershell
python -m pip install pynput pystray pillow
```

The script currently targets Windows because its multi-monitor boundary detection uses the Windows API through `ctypes`.

## Running

Run the script normally:

```powershell
python mouse_gravity.py
```

Once started:

1. A dark purple vortex icon appears in the Windows system tray.
2. Double-click somewhere to create a gravity target.
3. Move the mouse and observe the cursor being pulled toward that point.
4. Single-click to enable lateral boost.
5. Move sideways relative to the target to add orbital momentum.
6. Single-click again to disable lateral boost.
7. Triple-click to remove the target and stop movement.
8. Quadruple-click to terminate the program.

You can also right-click the tray icon and choose **Exit**.

## Typical Workflow

A simple way to create an orbit is:

1. Double-click near the center of the screen to create the target.
2. Allow gravity to begin pulling the cursor inward.
3. Single-click to enable lateral boost.
4. Physically move the mouse sideways relative to the target.
5. Stop moving the mouse and allow the simulated momentum to continue.
6. Add additional sideways input when the orbit begins collapsing.
7. Single-click to disable boost when you no longer need amplified input.

## Configuration

Most behavior is controlled by constants near the top of the script.

A balanced starting configuration is:

```python
GRAVITY = 1200.0

REFERENCE_DISTANCE = 300.0
GRAVITY_DISTANCE_POWER = 1.25

MIN_GRAVITY_DISTANCE = 40.0
MAX_GRAVITY_ACCELERATION = 5000.0


MAX_SPEED = 2000.0
DRAG = 0.996
STOP_RADIUS = 5.0
FPS = 120

NORMAL_INPUT_STRENGTH = 10.0

TOWARD_INPUT_MULTIPLIER = 1.0
AWAY_INPUT_MULTIPLIER = 0.35

LATERAL_BOOST_MULTIPLIER = 2.0

CLICK_SEQUENCE_TIMEOUT = 0.35
```

See `mouse_gravity_constants.md` for a detailed description of every configurable constant, including:

- data type
- reasonable ranges
- practical limits
- interactions with other values

## Physics Overview

Each physics update performs roughly the following steps:

1. Read the current cursor position.
2. Determine the direction and distance to the gravity target.
3. Apply acceleration toward the target.
4. Measure physical mouse input.
5. Split that input into radial and tangential components.
6. Reduce outward radial input.
7. Amplify tangential input if lateral boost is active.
8. Apply drag to existing velocity.
9. Clamp the velocity to `MAX_SPEED`.
10. Calculate the next cursor position.
11. Remove velocity that points through a desktop wall.
12. Move the cursor.

The result is intentionally not a physically exact gravitational simulation. It is designed to produce controllable, gravity-like cursor movement.

## Gravity

`GRAVITY` determines how quickly the cursor accelerates toward the active target.

Higher values produce a stronger pull.

```python
GRAVITY = 1800.0
```

Lower values make large orbits easier to maintain, while larger values cause trajectories to curve inward more aggressively.

## Momentum

Momentum is stored as horizontal and vertical velocity:

```python
velocity_x
velocity_y
```

The cursor continues moving even after physical mouse input stops.

`DRAG` slowly reduces this velocity over time.

```python
DRAG = 0.992
```

Values closer to `1.0` preserve momentum longer.

## Maximum Speed

The total simulated cursor velocity is limited by:

```python
MAX_SPEED = 1800.0
```

This prevents gravity or mouse input from accelerating the cursor indefinitely.

Increasing this value allows faster and wider orbital motion but can make the program harder to control.

## Target Behavior

The current gravity target is set by double-clicking.

A new double click immediately replaces the previous target after the click sequence has been recognized.

Only one target is active at a time.

When the cursor reaches the target within `STOP_RADIUS`, its simulated velocity is reset.

## Click Recognition

Click behavior uses:

```python
CLICK_SEQUENCE_TIMEOUT = 0.35
```

Clicks occurring within this interval are grouped into a sequence.

A shorter timeout makes controls feel more responsive but requires faster double and quadruple clicks.

A longer timeout makes multi-click actions easier but introduces a larger delay before single-click actions are confirmed.

## System Tray

While running, the program creates a dark purple vortex icon in the Windows notification area.

The tray icon:

- indicates that Mouse Gravity is active
- shows whether lateral boost is currently enabled in its tooltip
- provides an Exit command

The tray Exit option is useful if multi-click recognition behaves unexpectedly.

## Exiting

There are two normal ways to exit.

### Quadruple Click

Quadruple-click anywhere within the configured click-sequence timeout.

The fourth click causes the program to shut down.

### System Tray

Right-click the vortex icon and select:

```text
Exit
```

This stops the physics loop, mouse listener, and tray icon.

## Safety and Recovery

Because this program intentionally takes partial control of mouse movement, keep an alternate way to terminate it available while experimenting.

The system tray Exit option should remain enabled.

You can also run the script from a terminal so that you have a visible process to terminate if necessary.

When changing physics constants, make gradual adjustments. Extremely high gravity, input strength, maximum speed, or momentum retention can make the cursor difficult to control.

## Project Files

A simple project layout is:

```text
mouse_gravity/
├── mouse_gravity.py
├── mouse_gravity_constants.md
└── README.md
```

`mouse_gravity.py`
: Main program.

`mouse_gravity_constants.md`
: Detailed tuning reference for the constants.

`README.md`
: General usage, installation, behavior, and feature documentation.
