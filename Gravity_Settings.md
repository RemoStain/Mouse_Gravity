# Gravity Settings

This document describes the runtime values used by the N-body simulation and, more importantly, how they interact.

The values are defined in `GravityConfig` in `config.py`.

## Core Gravity Equation

For a normal point-to-point interaction, gravity magnitude is approximately:

```text
gravity_strength =
    point_gravity
    × (reference_distance / effective_distance) ^ gravity_distance_power
```

where:

```text
effective_distance = max(actual_distance, min_gravity_distance)
```

The result is then capped:

```text
gravity_strength <= max_gravity_acceleration
```

The scalar magnitude becomes an acceleration vector using the normalized direction between two points:

```text
dx = target_x - source_x
dy = target_y - source_y

distance = sqrt(dx² + dy²)

direction_x = dx / distance
direction_y = dy / distance

acceleration_x = direction_x × gravity_strength
acceleration_y = direction_y × gravity_strength
```

# Core Gravity Values

## `point_gravity`

Current default:

```python
point_gravity = 8.0
```

Primary scale factor for point-to-point attraction.

At exactly `reference_distance`:

```text
(reference_distance / reference_distance) ^ power = 1
```

so, before capping:

```text
gravity_strength = point_gravity
```

Doubling `point_gravity` doubles normal acceleration at every distance unless the result is already limited by `max_gravity_acceleration`.

Its visible effect is strongly influenced by:

- `reference_distance`
- `gravity_distance_power`
- `min_gravity_distance`
- `max_gravity_acceleration`
- `point_drag`
- `point_max_speed`
- `last_placed_boost`

---

## `reference_distance`

Current default:

```python
reference_distance = 300.0
```

Defines the distance where `point_gravity` acts as the base gravity value.

At 300 px, with a 300 px reference distance:

```text
gravity_strength = point_gravity
```

Increasing `reference_distance` increases gravity at a fixed real distance.

Example:

```text
point_gravity = 8
gravity_distance_power = 1.5
distance = 300
```

With:

```text
reference_distance = 300
```

gravity is:

```text
8
```

With:

```text
reference_distance = 600
```

gravity becomes:

```text
8 × (600 / 300)^1.5
= 8 × 2^1.5
≈ 22.63
```

The influence of `reference_distance` becomes more pronounced as `gravity_distance_power` increases.

---

## `gravity_distance_power`

Current default:

```python
gravity_distance_power = 1.5
```

Controls how sharply gravity changes with distance.

Relevant term:

```text
(reference_distance / distance) ^ gravity_distance_power
```

Lower values create a flatter force curve. Higher values create a much steeper curve.

When a point is farther than `reference_distance`, high powers make gravity fall off quickly. When a point is closer than `reference_distance`, high powers make gravity rise quickly.

Example with:

```text
point_gravity = 8
reference_distance = 300
distance = 150
```

The distance ratio is:

```text
300 / 150 = 2
```

Then:

```text
power = 1   -> 8 × 2   = 16
power = 2   -> 8 × 4   = 32
power = 10  -> 8 × 1024 = 8192
```

The final result may still be limited by `max_gravity_acceleration`.

---

## `min_gravity_distance`

Current default:

```python
min_gravity_distance = 25.0
```

Sets the smallest distance allowed in the force equation.

If two points are 5 px apart and this value is 25:

```text
effective_distance = 25
```

This prevents the gravity equation from exploding as distance approaches zero.

It does not change the actual point positions.

### Relationship to `body_stop_radius`

These values solve different problems:

- `body_stop_radius` controls merging.
- `min_gravity_distance` limits force growth.

Normally it is useful for:

```text
body_stop_radius < min_gravity_distance
```

so close-range force is stabilized before the points merge.

---

## `max_gravity_acceleration`

Current default:

```python
max_gravity_acceleration = 6000.0
```

Hard cap on calculated gravity magnitude.

Conceptually:

```text
gravity_strength = min(
    calculated_gravity,
    max_gravity_acceleration
)
```

This becomes important with high `point_gravity`, large `reference_distance`, high `gravity_distance_power`, or very small separation.

Once the calculated force reaches this cap, further increases to those values no longer increase acceleration at that distance.

# Placement Bias

Placement bias gives the newest manually placed point special behavior.

Preset-generated point groups begin without bias. After a new manual point is added, the newest point becomes the biased point.

## `place_bias_enabled`

Recommended config setting:

```python
place_bias_enabled = True
```

Controls whether manual placement is allowed to activate placement bias.

This should remain separate from runtime state:

```text
place_bias_active
```

That lets presets begin unbiased even while the feature is globally enabled.

---

## `last_placed_boost`

Current default:

```python
last_placed_boost = 3.0
```

Multiplies the acceleration older points receive toward the newest manually placed point.

If the normal pair acceleration is:

```text
10 px/s²
```

and:

```text
last_placed_boost = 3
```

then the older point receives approximately:

```text
30 px/s²
```

The biased point itself receives the normal opposing acceleration, not the boosted one.

This makes it behave like a stronger gravity source rather than simply making the whole pair more energetic.

Approximate relationship:

```text
biased attraction ≈ normal gravity × last_placed_boost
```

So:

```text
point_gravity = 8
last_placed_boost = 3
```

can make older points experience attraction similar to a source with an effective gravity near 24 for that interaction.

---

## `last_placed_drag`

Current default:

```python
last_placed_drag = 6.0
```

Adds extra damping to the newest biased point.

The biased point uses approximately:

```text
biased_drag_base = point_drag / last_placed_drag
```

then:

```text
drag_factor = biased_drag_base ^ (dt × point_physics_hz)
```

This value is not in the same 0-to-1 range as `point_drag`.

Example:

```text
point_drag = 0.99
last_placed_drag = 6
```

produces:

```text
0.99 / 6 = 0.165
```

before time scaling, which is much stronger damping than ordinary point drag.

The combination:

```text
high last_placed_boost
high last_placed_drag
```

makes the newest point pull strongly while retaining relatively little motion, creating a heavy-anchor effect.

# Motion Values

## `point_drag`

Current default:

```python
point_drag = 0.99
```

Controls how quickly normal point velocity decays.

The simulation uses time-scaled drag:

```text
drag_factor = point_drag ^ (dt × point_physics_hz)
```

then:

```text
velocity *= drag_factor
```

Values closer to 1 preserve more momentum.

Examples:

```text
0.9999 -> very persistent motion
0.999  -> persistent motion
0.99   -> noticeably damped motion
```

Changing drag can alter the simulation more visibly than changing gravity once points already have substantial velocity.

---

## `point_max_speed`

Current default:

```python
point_max_speed = 1000.0
```

Maximum total speed in pixels per second.

```text
speed = sqrt(vx² + vy²)
```

If speed exceeds the limit, the velocity vector is scaled down while preserving direction.

A low `point_max_speed` can hide differences between strong gravity presets because many points reach the cap quickly.

A high value lets gravity settings express themselves more fully, but also increases the chance of overshooting merges or boundaries between physics frames.

---

## `point_physics_hz`

Current default:

```python
point_physics_hz = 30.0
```

Target number of physics updates per second.

Approximate frame interval:

```text
1 / point_physics_hz
```

At 30 Hz:

```text
≈ 0.0333 seconds per update
```

Higher values provide smaller integration steps and generally smoother motion, but use more CPU.

This value also appears in drag scaling, helping damping remain reasonably consistent when physics frequency changes.

At seven points:

```text
21 pairs/update × 30 Hz = 630 pair evaluations/second
```

At 60 Hz:

```text
21 × 60 = 1260 pair evaluations/second
```

# Point Count

## `multi_point_count`

Current default:

```python
multi_point_count = 7
```

Configured placement limit.

The actual limit is bounded by:

```python
MAX_GRAVITY_POINTS
```

so the effective limit is:

```text
min(multi_point_count, MAX_GRAVITY_POINTS)
```

Pair count grows as:

```text
n(n - 1) / 2
```

| Points | Unique pairs |
|---:|---:|
| 2 | 1 |
| 3 | 3 |
| 4 | 6 |
| 5 | 10 |
| 6 | 15 |
| 7 | 21 |

---

## `MAX_GRAVITY_POINTS`

Current value:

```python
MAX_GRAVITY_POINTS = 7
```

Hard safety/performance limit independent of user-editable configuration.

# Merging

## `body_stop_radius`

Current default:

```python
body_stop_radius = 1.0
```

If:

```text
distance <= body_stop_radius
```

that pair is treated as merged and the older point is removed.

Because points are stored oldest-to-newest and pair loops evaluate `i < j`, removing `points[i]` consistently removes the older member of the pair.

### Relationship to speed and physics frequency

A very small merge radius combined with high speed and a low physics frequency can allow points to cross between frames without ever being sampled inside the radius.

To make merging more reliable, increase one or both of:

```text
body_stop_radius
point_physics_hz
```

This becomes increasingly relevant as `point_gravity` and `point_max_speed` increase.

# Placement Presets

## `triangle_spawn_radius`

Current default:

```python
triangle_spawn_radius = 300.0
```

Distance from the cursor to each of the three triangle vertices.

The points are separated by 120 degrees.

Larger values produce greater initial separation and generally lower initial attraction.

---

## `pentagram_spawn_radius`

Current default:

```python
pentagram_spawn_radius = 300.0
```

Distance from the cursor to each of five outer vertices, spaced 72 degrees apart.

The simulation stores only the vertices; it does not draw connecting star lines.

---

## `random_spawn_radius`

Current default:

```python
random_spawn_radius = 300.0
```

Distance from the cursor to each randomly generated point.

Using one random angle per point:

```text
x = cursor_x + radius × cos(angle)
y = cursor_y + radius × sin(angle)
```

places every point on the circumference of a circle.

This is radial randomness, not uniform randomness across the circle's area.

---

## `random_spawn_number`

Current default:

```python
random_spawn_number = 4
```

Number of points created by the random preset.

It should remain at or below `MAX_GRAVITY_POINTS`, or be clamped before spawning.

---

## `n_body_spawn_delay`

Current default:

```python
n_body_spawn_delay = 3.0
```

Delay in seconds between pressing a placement-preset button and spawning the pattern.

The cursor position is read when the delay ends, so the user can move the cursor after pressing the button and choose the final center position.

This value does not affect physics.

# Input

## `click_sequence_timeout`

Current default:

```python
click_sequence_timeout = 0.35
```

Maximum time between clicks that belong to the same multi-click command.

Increasing it makes slower double/triple/quadruple clicks easier but delays recognition of the completed sequence.

Decreasing it makes commands resolve faster but requires faster clicking.

# Logging

## `logging_enabled_by_default`

Current default:

```python
logging_enabled_by_default = True
```

Controls whether logging starts automatically with the application.

---

## `log_telemetry_hz`

Current default:

```python
log_telemetry_hz = 5
```

Number of point-state telemetry snapshots per second.

Telemetry can include:

```text
point index
x
y
vx
vy
speed
biased state
```

At seven points and 5 Hz:

```text
7 × 5 = 35 point telemetry records per second
```

For long runs, lower values such as 1 or 2 reduce disk activity and log size.

A value of 0 can be used to disable telemetry if the runtime only logs when the value is greater than zero.

# Important Parameter Interactions

## Stronger long-range attraction

Increase:

```text
point_gravity
reference_distance
```

or reduce:

```text
gravity_distance_power
```

Lower powers preserve more force at long range.

## Stronger close-range attraction

Increase:

```text
gravity_distance_power
```

especially with a large `reference_distance`.

Use `min_gravity_distance` and `max_gravity_acceleration` to prevent excessive close-range acceleration.

## More persistent orbital motion

Move:

```text
point_drag
```

closer to 1.

You may also need to increase `point_max_speed` if points frequently hit the speed cap.

## More heavily damped motion

Decrease normal `point_drag`.

For only the newest biased point, increase `last_placed_drag`.

## Stronger anchor behavior

Increase both:

```text
last_placed_boost
last_placed_drag
```

The first increases how strongly the newest point attracts older points. The second reduces how much motion the newest point retains.

## Prevent extreme close-range behavior

Increase:

```text
min_gravity_distance
```

and/or decrease:

```text
max_gravity_acceleration
```

## Prevent missed merges

Increase:

```text
body_stop_radius
```

or:

```text
point_physics_hz
```

particularly when `point_max_speed` is large.

# Recommended Tuning Order

When creating a new preset, tune values in roughly this order:

1. `point_gravity`
2. `reference_distance`
3. `gravity_distance_power`
4. `min_gravity_distance`
5. `max_gravity_acceleration`
6. `point_drag`
7. `point_max_speed`
8. `body_stop_radius`
9. `last_placed_boost`
10. `last_placed_drag`

It is easier to tune the base system first and adjust placement bias afterward. That reduces the number of interacting variables being changed at the same time.
