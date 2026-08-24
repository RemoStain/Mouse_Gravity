# Mouse Gravity Constants Reference

This file describes the configurable values used by Mouse Gravity, including their purpose, expected data type, reasonable values, practical limits, and interactions with other settings.

The values are kept in the separate settings/configuration module rather than being owned by the main physics script. The settings window reads the centrally defined list of exposed variables and can update those values while Mouse Gravity is running.

Changing a value in the settings window changes the value used by the running program; closing the window does not stop the physics loop. The window can be reopened from the system tray.


## Runtime Settings

The settings module is the single source of truth for user-adjustable physics and input values.

The settings UI should be generated from the central exposed-settings definition near the top of that module. This avoids maintaining a second hard-coded list inside the UI.

A setting should only be exposed when changing it at runtime is supported by the program.

Windows API metric identifiers and derived screen bounds are implementation constants, not user-tuning values, and should not be included in the editable settings list.

The current baseline values used throughout this document are:

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
AWAY_INPUT_MULTIPLIER = 0.355
LATERAL_BOOST_MULTIPLIER = 2.0

CLICK_SEQUENCE_TIMEOUT = 0.35
```

---

## Physics Constants

### `GRAVITY`

```python
GRAVITY = 1200.0
```

**Type:** `float`

**Meaning:**  
Controls the acceleration pulling the cursor toward the current gravity target.

The value is effectively measured in pixels per second squared. A larger value makes the cursor gain inward velocity more quickly.

**Reasonable values:**

- `500.0` to `1000.0` — weak pull
- `1000.0` to `2500.0` — moderate to strong pull
- `2500.0` to `5000.0` — very strong pull
- Above `5000.0` — usually difficult to control

**Practical limits:**

- Minimum: `0.0`
- No strict mathematical maximum
- Negative values should not be used unless intentionally creating repulsion

At `0.0`, there is no gravitational pull.

**Interactions:**

- Higher `GRAVITY` makes `AWAY_INPUT_MULTIPLIER` feel weaker because outward movement must overcome a stronger inward acceleration.
- Higher `GRAVITY` generally requires a higher `MAX_SPEED` if you want wide or fast orbits.
- Higher `GRAVITY` may require a higher `NORMAL_INPUT_STRENGTH` if physical mouse movement feels too weak.
- Higher `GRAVITY` combined with high `DRAG` retention can create very energetic motion.
- A larger `STOP_RADIUS` can prevent very strong gravity from causing jitter around the target.

---

### `GRAVITY_DISTANCE_POWER`

```python
GRAVITY_DISTANCE_POWER = 1.25
```

**Type:** `float`

**Meaning:**  
Controls how strongly distance from the target affects gravitational pull.

The gravity calculation is:

```python
gravity_strength = (
    GRAVITY
    * (REFERENCE_DISTANCE / gravity_distance)
    ** GRAVITY_DISTANCE_POWER
)
```

Higher values make gravity increase more sharply as the cursor gets closer to the target.

Lower values make gravity behave more uniformly across distance.

**Reasonable values:**

- `0.0` — constant gravity; distance has no effect
- `0.5` — mild proximity effect
- `1.0` — moderate inverse-distance behavior
- `1.0` to `1.3` — good range for controlled eccentric-orbit behavior
- `1.5` — strong proximity effect
- `2.0` — inverse-square behavior; very strong close-range pull
- Above `2.0` — usually too aggressive for controllable cursor movement

**Practical limits:**

- Usually: `0.0` to `2.0`
- `0.0` disables distance scaling entirely
- Negative values reverse the intended relationship, making gravity weaker near the target and stronger farther away
- There is no strict mathematical upper limit, but large values can produce extreme close-range acceleration

**Interactions:**

- Higher `GRAVITY_DISTANCE_POWER` increases the importance of `MIN_GRAVITY_DISTANCE`.
- Higher values make `MAX_GRAVITY_ACCELERATION` more likely to be reached.
- Higher values can create tighter spirals and make close approaches harder to control.
- Lower values produce smoother, broader trajectories.
- `GRAVITY` controls the overall strength, while `GRAVITY_DISTANCE_POWER` controls how strongly that strength changes with distance.
- `REFERENCE_DISTANCE` determines the distance where gravity is approximately equal to `GRAVITY`.

For example, when the cursor is at half of `REFERENCE_DISTANCE`:

```text
GRAVITY_DISTANCE_POWER    Gravity multiplier

0.0                       1.00x
0.5                       1.41x
1.0                       2.00x
1.2                       2.30x
1.5                       2.83x
2.0                       4.00x
```

A good starting value is:

```python
GRAVITY_DISTANCE_POWER = 1.25
```

This preserves the effect of stronger gravity near the target without producing the very aggressive close-range pull of inverse-square gravity.

---

### `REFERENCE_DISTANCE`

```python
REFERENCE_DISTANCE = 300.0
```

**Type:** `float`

**Meaning:**  
Defines the distance, in pixels, where gravitational acceleration is approximately equal to `GRAVITY`.

At:

```text
distance = REFERENCE_DISTANCE
```

the ratio:

```python
REFERENCE_DISTANCE / gravity_distance
```

is `1.0`, so the resulting gravity strength is approximately:

```python
GRAVITY
```

**Reasonable values:**

- `100.0` to `200.0` — proximity effects concentrated near the target
- `200.0` to `400.0` — normal
- `400.0` to `800.0` — distance scaling affects a much larger portion of the screen

**Practical limits:**

- Must be greater than `0.0`
- No strict maximum
- Very large values can make gravity unusually strong across the entire desktop

**Interactions:**

- Increasing `REFERENCE_DISTANCE` increases gravity at distances below that value.
- Decreasing it makes gravity weaker at larger distances.
- Its effect becomes much stronger as `GRAVITY_DISTANCE_POWER` increases.
- `GRAVITY` remains the approximate acceleration at exactly `REFERENCE_DISTANCE`.

For example:

```python
GRAVITY = 1400.0
REFERENCE_DISTANCE = 300.0
GRAVITY_DISTANCE_POWER = 1.0
```

produces approximately:

```text
Distance    Gravity

600 px      700
300 px      1400
150 px      2800
75 px       5600
```

before any minimum-distance or maximum-acceleration limits are applied.

---

### `MIN_GRAVITY_DISTANCE`

```python
MIN_GRAVITY_DISTANCE = 40.0
```

**Type:** `float`

**Meaning:**  
Sets the minimum distance used by the gravity calculation.

The actual cursor may move closer than this value, but the gravity formula behaves as though the cursor were still this far away.

For example:

```python
gravity_distance = max(
    distance,
    MIN_GRAVITY_DISTANCE,
)
```

This prevents gravity from approaching extreme values near the target.

**Reasonable values:**

- `10.0` to `25.0` — very strong close approaches
- `30.0` to `60.0` — normal
- `60.0` to `120.0` — heavily softened close-range gravity

**Practical limits:**

- Must be greater than `0.0`
- Should normally be greater than `STOP_RADIUS`
- Very small values can create extreme acceleration near the target

**Interactions:**

- Becomes increasingly important as `GRAVITY_DISTANCE_POWER` increases.
- Lower values allow stronger acceleration during close passes.
- Higher values flatten the gravity curve near the target.
- `MAX_GRAVITY_ACCELERATION` provides an additional safety cap.
- If `MIN_GRAVITY_DISTANCE` is large, changing `GRAVITY_DISTANCE_POWER` may have less noticeable effect close to the target.

---

### `MAX_GRAVITY_ACCELERATION`

```python
MAX_GRAVITY_ACCELERATION = 5000.0
```

**Type:** `float`

**Meaning:**  
Maximum gravitational acceleration that can be applied, regardless of distance.

The calculated gravity is capped with:

```python
gravity_strength = min(
    gravity_strength,
    MAX_GRAVITY_ACCELERATION,
)
```

This prevents very close approaches from generating excessive acceleration.

**Reasonable values:**

- `2000.0` to `4000.0` — heavily controlled
- `4000.0` to `8000.0` — normal
- `8000.0` to `15000.0` — aggressive
- Above `15000.0` — usually unnecessary

**Practical limits:**

- Should be greater than `0.0`
- Usually should be greater than `GRAVITY`
- No strict maximum

**Interactions:**

- Higher `GRAVITY_DISTANCE_POWER` causes this cap to be reached more often.
- Smaller `MIN_GRAVITY_DISTANCE` also makes the cap more important.
- Lowering this value reduces violent close-range spiraling without changing distant gravity as much.
- If this value is too low, the distance-based gravity curve becomes effectively flattened near the target.

---

### `MAX_SPEED`

```python
MAX_SPEED = 2000.0
```

**Type:** `float`

**Meaning:**  
Maximum simulated cursor velocity, in approximately pixels per second.

After gravity and user input modify velocity, the total speed is clamped to this value.

**Reasonable values:**

- `500.0` to `1000.0` — slow
- `1000.0` to `2500.0` — normal
- `2500.0` to `5000.0` — fast
- Above `5000.0` — increasingly difficult to control

**Practical limits:**

- Should be greater than `0.0`
- No strict upper limit
- Extremely high values can cause large cursor jumps between frames

**Interactions:**

- Increasing `GRAVITY` without increasing `MAX_SPEED` causes the cursor to reach the speed cap more often.
- Large `LATERAL_BOOST_MULTIPLIER` values may have little additional effect once `MAX_SPEED` is reached.
- Low `MAX_SPEED` makes orbits smaller and more constrained.
- High `MAX_SPEED` combined with low `FPS` can make motion appear jumpy.

---

### `DRAG`

```python
DRAG = 0.996
```

**Type:** `float`

**Meaning:**  
Controls how much velocity is retained after each physics update.

Every frame:

```python
velocity_x *= DRAG
velocity_y *= DRAG
```

A value closer to `1.0` means less momentum is lost.

**Reasonable values:**

- `0.90` to `0.96` — very heavy damping
- `0.97` to `0.99` — noticeable damping
- `0.990` to `0.997` — good for orbital motion
- `0.998` to `0.9999` — very persistent momentum

**Practical limits:**

- Normally: `0.0 < DRAG <= 1.0`
- `1.0` means no velocity loss
- Above `1.0` adds energy every frame and should normally be avoided
- `0.0` destroys all velocity every frame

**Interactions:**

- Higher `DRAG` makes gravity, user input, and lateral boosts accumulate for longer.
- Higher `DRAG` makes orbiting easier but also makes the system harder to stop.
- With high `GRAVITY`, values very close to `1.0` can produce high sustained speeds.
- Lowering `DRAG` can compensate for a large `NORMAL_INPUT_STRENGTH`.
- `MAX_SPEED` becomes more important as `DRAG` approaches `1.0`.

**Important:**  
Because drag is applied once per frame, its effective strength depends on `FPS`. Changing `FPS` changes how often drag is applied.

---

### `STOP_RADIUS`

```python
STOP_RADIUS = 5.0
```

**Type:** `float`

**Meaning:**  
Distance from the gravity target, in pixels, at which the cursor is considered to have reached the target.

Inside this radius, velocity is cleared and the cursor is placed directly on the target.

**Reasonable values:**

- `1.0` to `2.0` — precise, but may jitter
- `3.0` to `5.0` — normal
- `5.0` to `15.0` — forgiving
- Above `15.0` — noticeably large dead zone

**Practical limits:**

- Minimum: `0.0`
- Should generally remain much smaller than the desired orbit radius

**Interactions:**

- Higher `GRAVITY` may require a slightly larger `STOP_RADIUS` to avoid jitter near the target.
- Large `STOP_RADIUS` can destroy small orbits because the cursor will be considered to have reached the target too early.
- High user-input strength is easier to manage with a slightly larger `STOP_RADIUS`.

---

### `FPS`

```python
FPS = 120
```

**Type:** `int`

**Meaning:**  
Target number of physics updates per second.

The loop sleeps for approximately:

```python
1 / FPS
```

between updates.

**Reasonable values:**

- `30` — low CPU use, visibly coarse
- `60` — standard
- `90` to `144` — smooth
- `120` — good default
- `240` — very smooth but unnecessary for many systems

**Practical limits:**

- Must be greater than `0`
- Real execution rate is limited by Windows, Python, scheduler timing, and system load
- Extremely high values increase CPU usage without guaranteeing equivalent timing precision

**Interactions:**

- `DRAG` is applied once per frame, so changing `FPS` changes the effective amount of damping per second.
- Higher `FPS` makes large `MAX_SPEED` values appear smoother.
- Higher `FPS` reduces the movement distance per individual frame.
- Gravity uses `dt`, so gravitational acceleration itself is mostly frame-rate independent.
- User-input detection may become more sensitive at high `FPS` because physical movement is measured over shorter intervals.

---

## Mouse Input Constants

### `NORMAL_INPUT_STRENGTH`

```python
NORMAL_INPUT_STRENGTH = 10.0
```

**Type:** `float`

**Meaning:**  
Controls how strongly actual physical mouse movement modifies the simulated velocity.

This affects both radial and tangential user input before their individual multipliers are applied.

**Reasonable values:**

- `5.0` to `15.0` — subtle influence
- `15.0` to `35.0` — normal
- `35.0` to `75.0` — strong
- Above `75.0` — very sensitive

**Practical limits:**

- Minimum: `0.0`
- No strict maximum
- Negative values reverse the effect of physical input and should normally be avoided

**Interactions:**

- Multiplied by `TOWARD_INPUT_MULTIPLIER` for inward movement.
- Multiplied by `AWAY_INPUT_MULTIPLIER` for outward movement.
- Multiplied by `LATERAL_BOOST_MULTIPLIER` for tangential movement while boost is active.
- Higher `GRAVITY` may require higher input strength to preserve user control.
- High values combined with high `DRAG` can retain large amounts of injected momentum.
- `MAX_SPEED` limits the final effect.

---

### `LATERAL_BOOST_MULTIPLIER`

```python
LATERAL_BOOST_MULTIPLIER = 2.0
```

**Type:** `float`

**Meaning:**  
Multiplier applied to the tangential component of actual physical mouse movement when lateral boost is enabled.

It does **not** continuously add energy by itself. If the user does not physically move the mouse, this multiplier contributes nothing.

For example:

```python
NORMAL_INPUT_STRENGTH = 10.0
LATERAL_BOOST_MULTIPLIER = 2.0
```

produces an effective boosted tangential input strength of:

```text
10 × 2 = 20
```

**Reasonable values:**

- `1.0` — no boost
- `2.0` to `3.0` — mild boost
- `3.0` to `6.0` — strong boost
- `6.0` to `10.0` — very aggressive
- Above `10.0` — small physical movements can produce large velocity changes

**Practical limits:**

- Minimum normally: `1.0`
- `0.0` disables tangential user influence while boost is active
- Negative values reverse the boosted lateral direction and should normally be avoided

**Interactions:**

- Directly multiplies `NORMAL_INPUT_STRENGTH`.
- High values are constrained by `MAX_SPEED`.
- High values combined with high `DRAG` make orbital momentum persist much longer.
- This value has no direct effect on inward or outward radial movement.
- Stronger `GRAVITY` can support faster orbiting before the cursor escapes outward.

---

### `TOWARD_INPUT_MULTIPLIER`

```python
TOWARD_INPUT_MULTIPLIER = 1.0
```

**Type:** `float`

**Meaning:**  
Controls how effective physical mouse movement is when the user moves toward the gravity target.

A value of `1.0` means normal radial input strength.

**Reasonable values:**

- `0.5` — reduced inward control
- `1.0` — normal
- `1.0` to `2.0` — enhanced inward control

**Practical limits:**

- Usually `>= 0.0`
- Negative values reverse inward input and are not recommended

**Interactions:**

Effective inward input strength is:

```text
NORMAL_INPUT_STRENGTH × TOWARD_INPUT_MULTIPLIER
```

For the defaults:

```text
10 × 1.0 = 10
```

- Raising this makes moving with gravity easier.
- Lowering `AWAY_INPUT_MULTIPLIER` relative to this value increases the asymmetry between inward and outward movement.
- Gravity itself already assists inward movement, so even equal inward/outward multipliers do not produce equal effort.

---

### `AWAY_INPUT_MULTIPLIER`

```python
AWAY_INPUT_MULTIPLIER = 0.35
```

**Type:** `float`

**Meaning:**  
Controls how effective physical mouse movement is when attempting to move directly away from the target.

This is intentionally lower than `TOWARD_INPUT_MULTIPLIER` so that moving against gravity requires more physical effort.

**Reasonable values:**

- `0.1` to `0.2` — very difficult to pull away
- `0.25` to `0.4` — noticeably resistant
- `0.5` to `0.75` — moderate resistance
- `1.0` — equal input scaling inward and outward

**Practical limits:**

- Normally: `0.0` to `1.0`
- `0.0` means physical radial movement cannot directly add outward momentum
- Above `1.0` makes outward physical input stronger than normal
- Negative values make outward movement behave incorrectly for the intended model

**Interactions:**

Effective outward input strength is:

```text
NORMAL_INPUT_STRENGTH × AWAY_INPUT_MULTIPLIER
```

With:

```python
NORMAL_INPUT_STRENGTH = 10.0
AWAY_INPUT_MULTIPLIER = 0.35
```

the effective outward strength is:

```text
3.5
```

compared with inward strength:

```text
10.0
```

assuming:

```python
TOWARD_INPUT_MULTIPLIER = 1.0
```

Gravity also continuously opposes outward movement, so the real difference in required effort is greater than the multiplier ratio alone suggests.

A useful relationship is:

```text
AWAY_INPUT_MULTIPLIER < TOWARD_INPUT_MULTIPLIER
```

If the design requirement is that moving away should always be harder than moving toward the target.

---

## Click Recognition

Click recognition is independent of the settings-window lifecycle. Closing the settings window does not disable click handling, gravity, or the tray icon.


### `CLICK_SEQUENCE_TIMEOUT`

```python
CLICK_SEQUENCE_TIMEOUT = 0.35
```

**Type:** `float`

**Meaning:**  
Maximum delay, in seconds, used to group consecutive clicks into a single click sequence.

The current controls are:

```text
1 click   = toggle lateral boost
2 clicks  = assign new gravity target
3 clicks  = remove the active gravity target and clear velocity
4 clicks  = exit
```

The program delays processing shorter click sequences because it must determine whether additional clicks are coming.

**Reasonable values:**

- `0.20` to `0.25` — requires fast clicking
- `0.30` to `0.40` — normal
- `0.40` to `0.60` — forgiving
- Above `0.60` — controls may feel noticeably delayed

**Practical limits:**

- Must be greater than `0.0`
- Very small values make double and quadruple clicks difficult
- Very large values make single-click actions feel slow

**Interactions:**

- Does not affect cursor physics.
- Directly controls how responsive single-click boost toggling feels.
- Increasing it makes quadruple-click detection easier but increases the delay before a single or double click is finalized.

---

## Windows Virtual Desktop Constants

These constants come from the Windows API and should **not** normally be changed.

### `SM_XVIRTUALSCREEN`

```python
SM_XVIRTUALSCREEN = 76
```

**Type:** `int`

Windows system-metric identifier for the left edge of the entire virtual desktop.

Do not change this value.

---

### `SM_YVIRTUALSCREEN`

```python
SM_YVIRTUALSCREEN = 77
```

**Type:** `int`

Windows system-metric identifier for the top edge of the entire virtual desktop.

Do not change this value.

---

### `SM_CXVIRTUALSCREEN`

```python
SM_CXVIRTUALSCREEN = 78
```

**Type:** `int`

Windows system-metric identifier for the total width of the virtual desktop.

Do not change this value.

---

### `SM_CYVIRTUALSCREEN`

```python
SM_CYVIRTUALSCREEN = 79
```

**Type:** `int`

Windows system-metric identifier for the total height of the virtual desktop.

Do not change this value.

---

## Derived Screen Bounds

These values are calculated from Windows rather than manually configured:

```python
SCREEN_LEFT = user32.GetSystemMetrics(SM_XVIRTUALSCREEN)
SCREEN_TOP = user32.GetSystemMetrics(SM_YVIRTUALSCREEN)

SCREEN_WIDTH = user32.GetSystemMetrics(SM_CXVIRTUALSCREEN)
SCREEN_HEIGHT = user32.GetSystemMetrics(SM_CYVIRTUALSCREEN)

SCREEN_RIGHT = SCREEN_LEFT + SCREEN_WIDTH - 1
SCREEN_BOTTOM = SCREEN_TOP + SCREEN_HEIGHT - 1
```

**Type:** `int`

These describe the rectangular bounds of the complete Windows virtual desktop.

They can contain negative coordinates when a monitor is positioned to the left of or above the primary monitor.

These values should not be manually changed.

Note that the virtual desktop is a bounding rectangle. If the physical monitors form an irregular shape, some locations inside this rectangle may not correspond to an actual display.

---

# Recommended Starting Configuration

The current balanced baseline is:

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

These are starting values rather than required values. The settings window is intended to make experimentation possible without editing the physics source.

# Important Relationships

The most important constants should generally be tuned together.

### Gravity vs. user control

Increasing:

```python
GRAVITY
```

makes all outward movement harder.

If control becomes too weak, increase:

```python
NORMAL_INPUT_STRENGTH
```

rather than immediately reducing gravity.

---

### Momentum persistence

The primary momentum controls are:

```python
DRAG
MAX_SPEED
```

Higher `DRAG` retains momentum longer.

Higher `MAX_SPEED` allows that retained momentum to reach larger values.

Using both at very high values can make the cursor difficult to regain control over.

---

### Orbit creation

Orbital behavior primarily depends on:

```python
GRAVITY
NORMAL_INPUT_STRENGTH
LATERAL_BOOST_MULTIPLIER
DRAG
MAX_SPEED
```

`GRAVITY` bends the trajectory toward the target.

`LATERAL_BOOST_MULTIPLIER` helps the user inject sideways momentum.

`DRAG` determines how long that momentum survives.

`MAX_SPEED` determines how energetic the orbit is allowed to become.

---

### Inward vs. outward effort

The intended relationship is:

```text
AWAY_INPUT_MULTIPLIER < TOWARD_INPUT_MULTIPLIER
```

A stronger inequality produces greater resistance when moving away.

For example:

```python
TOWARD_INPUT_MULTIPLIER = 1.0
AWAY_INPUT_MULTIPLIER = 0.35
```

means outward physical input has only 30% of the radial effect of inward physical input, before accounting for gravity itself.

---

### Frame rate and drag

`DRAG` is currently frame-dependent.

For example, the same `DRAG` value at `120 FPS` does not produce exactly the same damping behavior at `60 FPS` because drag is applied a different number of times per second.

because drag is applied half as many times per second at 60 FPS.

If `FPS` will remain fixed, this is usually not a problem.

If you want to experiment heavily with different frame rates, the drag calculation should eventually be converted to a time-based formula so that damping remains consistent regardless of FPS.
