# Mouse Gravity

Mouse Gravity is a Windows Python utility that gives the mouse cursor momentum and pulls it toward a user-defined gravity target.

The cursor behaves like an object influenced by gravity rather than moving only according to direct mouse input. It supports curved trajectories, orbit-like motion, amplified lateral input, multi-monitor movement, live settings changes, and tray-based control.

## Features

- Gravity-based cursor movement toward a selected point
- Distance-scaled gravity with close-range safety limits
- Momentum and drag
- User-controlled orbital movement
- Lateral boost that amplifies real mouse movement rather than continuously adding energy
- Reduced effectiveness when moving away from the gravity target
- Multi-monitor support using the Windows virtual desktop
- Wall collisions that remove momentum perpendicular to the desktop boundary
- Runtime-adjustable settings
- Settings window that can be reopened from the system tray
- System tray status/control menu
- Quadruple-click emergency exit
- Configuration kept outside the main physics script

## Controls

Mouse controls are based on click count.

| Input | Action |
| --- | --- |
| Double click | Assign or replace the gravity target |
| Triple click | Remove the gravity target and clear velocity |
| Quadruple click | Exit the program |

Click sequences are grouped using `CLICK_SEQUENCE_TIMEOUT`.

Because the program must determine whether more clicks are coming, shorter click actions are processed after the configured sequence timeout.

## Settings Window

The program includes a settings window for changing the exposed configuration values without editing the physics code.

The settings window:

- displays the configurable variables defined by the settings module
- shows the current value of each setting
- allows values to be changed while the program is running
- can be closed without terminating Mouse Gravity
- can be reopened from the system tray

Closing the settings window only closes the window. The gravity loop, mouse listener, and tray icon continue running.

The list of settings available to the window is defined centrally in the settings module so that adding or removing a configurable value does not require manually rebuilding the settings UI.

## System Tray

While running, Mouse Gravity places its icon in the Windows notification area.

The tray menu provides access to the program even when the settings window has been closed.

The tray is used to:

- indicate that Mouse Gravity is running
- toggle the current lateral-boost state
- open or reopen the settings window
- toggle logging
- exit the program

Using the tray Exit command shuts down the running components cleanly.

## Configuration Architecture

Physics and input tuning values are no longer intended to be scattered through `mouse_gravity.py`.

The configuration is kept in a separate settings module. The main gravity code reads those settings instead of owning the tuning values itself.

This separation has two purposes:

1. Physics code can change without mixing in configuration management.
2. The settings window can edit the same values that the gravity loop reads.

The settings module also contains the central list or mapping that determines which values are exposed to the settings window.

A current baseline configuration is:

```python
GRAVITY = 1500.0

REFERENCE_DISTANCE = 300.0
GRAVITY_DISTANCE_POWER = 1.1

MIN_GRAVITY_DISTANCE = 40.0
MAX_GRAVITY_ACCELERATION = 6000.0

MAX_SPEED = 2500.0
DRAG = 0.996
STOP_RADIUS = 5.0
FPS = 120

NORMAL_INPUT_STRENGTH = 10.0

TOWARD_INPUT_MULTIPLIER = 1.0
AWAY_INPUT_MULTIPLIER = 0.35

LATERAL_BOOST_MULTIPLIER = 2.0

CLICK_SEQUENCE_TIMEOUT = 0.35
```

```

See `mouse_gravity_constants.md` for the purpose, type, useful range, limits, and interactions of each setting.

## Gravity Model

Gravity is distance-scaled rather than constant.

Conceptually, the acceleration is calculated as:

```python
gravity_distance = max(distance, MIN_GRAVITY_DISTANCE)

gravity_strength = (
    GRAVITY
    * (REFERENCE_DISTANCE / gravity_distance)
    ** GRAVITY_DISTANCE_POWER
)

gravity_strength = min(
    gravity_strength,
    MAX_GRAVITY_ACCELERATION,
)
```

This allows gravity to become stronger near the target without allowing close-range acceleration to grow without limit.

### Main gravity settings

`GRAVITY`
: Baseline gravitational acceleration.

`REFERENCE_DISTANCE`
: Distance at which gravity is approximately equal to `GRAVITY`.

`GRAVITY_DISTANCE_POWER`
: Controls how strongly gravity changes with distance.

`MIN_GRAVITY_DISTANCE`
: Prevents the distance term from becoming excessively small.

`MAX_GRAVITY_ACCELERATION`
: Caps the final gravitational acceleration.

## Target Behavior

A double click assigns the current gravity target.

Assigning a new target replaces the previous target.

Only one gravity target is active at a time.

The target remains gravitationally active after it is assigned. Mouse input modifies the simulated velocity, but it does not replace the target's gravity.

A triple click removes the active target and clears the current simulated velocity.

When the cursor enters `STOP_RADIUS`, its simulated velocity is cleared and the cursor is treated as having reached the target.

## Lateral Boost

Lateral boost is intended to make orbit creation easier without continuously injecting energy.

When boost is enabled, the program measures actual physical mouse movement and increases only the component perpendicular to the direction of gravity.

If the user stops physically moving the mouse, lateral boost stops contributing additional velocity.

This makes it possible to add tangential momentum with the physical mouse and then let gravity curve that momentum around the target.

## Moving Toward and Away From the Target

Physical input is separated into radial and tangential components relative to the active target.

Radial input is further divided into:

- movement toward the target
- movement away from the target

The current baseline values are:

```python
TOWARD_INPUT_MULTIPLIER = 1.0
AWAY_INPUT_MULTIPLIER = 0.35
```

Outward physical movement therefore contributes less radial input than inward movement, while gravity simultaneously continues pulling toward the target.

Tangential input is multiplied by `LATERAL_BOOST_MULTIPLIER` when lateral boost is enabled.

## Physics Update

Each physics update performs approximately these steps:

1. Read the actual cursor position.
2. Compare it with the position the simulation expected.
3. Treat the difference as physical user input.
4. Determine the direction and distance to the active gravity target.
5. Apply gravitational acceleration toward the target.
6. Split physical mouse input into radial and tangential components.
7. Apply separate inward and outward input multipliers.
8. Apply lateral boost to tangential input when enabled.
9. Apply drag to simulated velocity.
10. Clamp total velocity to `MAX_SPEED`.
11. Calculate the next simulated cursor position.
12. Remove velocity pointing through an outer virtual-desktop wall.
13. Move the cursor.
14. Store the resulting position as the expected position for the next update.

Tracking the expected position is important because the program itself moves the cursor. Only the difference between the actual position and the expected simulated position should be treated as new physical mouse input.

## Momentum

Momentum is stored as horizontal and vertical simulated velocity.

```python
velocity_x
velocity_y
```

The cursor can therefore continue moving after physical mouse movement stops.

`DRAG` reduces retained velocity over time.

Values closer to `1.0` preserve momentum longer.

`MAX_SPEED` prevents gravity and mouse input from accelerating the simulated cursor indefinitely.

## Multi-Monitor Support

Mouse Gravity uses the Windows virtual desktop coordinate system.

This allows movement across monitors positioned:

- left of the primary display
- right of the primary display
- above the primary display
- below the primary display

Virtual-desktop coordinates may be negative.

The current collision boundary is the outer rectangle of the complete virtual desktop.

When the cursor reaches a boundary, only velocity pointing through that wall is removed. Tangential velocity is retained so the cursor can slide along the edge instead of bouncing.

Because the Windows virtual desktop is a bounding rectangle, irregular physical monitor layouts can contain coordinate regions that do not correspond to an actual display.

## Installation

Python is required.

Install the external dependencies with:

```powershell
python -m pip install pynput pystray pillow
```

The settings window uses Tkinter, which is included with normal Windows Python installations.

The program currently targets Windows because virtual-desktop boundary detection uses the Windows API through `ctypes`.

## Running

Run the main script:

```powershell
python mouse_gravity.py
```

Typical use:

1. Start Mouse Gravity.
2. Use the settings window to review or adjust the exposed values.
3. Double-click to create a gravity target.
4. Move the mouse and observe the target pulling the cursor.
5. Use the tray menu to toggle lateral boost if desired.
6. Triple-click to clear the target and velocity.
7. Close the settings window if it is not needed.
8. Reopen the settings window from the tray icon when required.
9. Quadruple-click or use the tray Exit command to terminate the program.

## Typical Orbit Workflow

1. Double-click near the desired center of motion.
2. Allow gravity to begin pulling inward.
3. Physically move sideways relative to the target.
4. Stop moving the mouse and allow the stored velocity to continue.
5. Add more tangential input if the orbit begins collapsing.
6. Disable lateral boost when normal input sensitivity is preferred.

## Click Recognition

`CLICK_SEQUENCE_TIMEOUT` controls how close together clicks must occur to be treated as one sequence.

A shorter value makes single-click actions resolve sooner but requires faster multi-click input.

A longer value makes double, triple, and quadruple actions easier to perform but delays shorter click actions.

## Safety and Recovery

Mouse Gravity intentionally takes partial control of cursor movement.

Keep the tray Exit command available while experimenting with aggressive physics settings.

The quadruple-click exit is an additional emergency shutdown path.

Increase gravity, input strength, speed limits, and momentum retention gradually. Extreme values can make the cursor difficult to regain control over.

## Project Structure

The project is separated by responsibility

A representative layout is:

```text
mouse_gravity/
├── mouse_gravity.py
├── settings.py
├── settings_window.py
├── mouse_gravity_constants.md
└── README.md
```

`mouse_gravity.py`
: Main program, physics loop, mouse input handling, target state, and tray lifecycle.

`settings.py`
: Configuration values and the central definition of which settings are exposed for editing.

`settings_window.py`
: Settings-window UI and runtime value editing.

`mouse_gravity_constants.md`
: Detailed tuning reference for configurable values.

`README.md`
: Installation, controls, architecture, behavior, and usage.
