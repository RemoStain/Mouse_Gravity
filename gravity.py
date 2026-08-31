import math
from dataclasses import dataclass

from config import config


@dataclass
class GravityPoint:
    """
    A movable gravity source used by the N-body simulation.

    Positions and velocities are stored as floats so points can move
    smoothly even though their visible markers are rendered at integer
    pixel coordinates.

    Attributes:
        x:
            Horizontal position on the virtual desktop.

        y:
            Vertical position on the virtual desktop.

        velocity_x:
            Horizontal velocity in pixels per second.

        velocity_y:
            Vertical velocity in pixels per second.
    """

    x: float
    y: float
    velocity_x: float = 0.0
    velocity_y: float = 0.0


def _gravity_strength(
    distance: float,
) -> float:
    """
    Return the configured point-to-point gravity magnitude.

    The minimum gravity distance prevents acceleration from growing
    excessively large when two points are very close together.

    The resulting acceleration is also capped by
    ``max_gravity_acceleration``.

    Args:
        distance:
            Distance between the two gravity points.

    Returns:
        The gravity acceleration magnitude for the supplied distance.
    """
    gravity_distance = max(
        distance,
        config.min_gravity_distance,
    )

    gravity_strength = (
        config.point_gravity
        * (config.reference_distance / gravity_distance)
        ** config.gravity_distance_power
    )

    return min(
        gravity_strength,
        config.max_gravity_acceleration,
    )


def point_gravity_vector(
    source_x: float,
    source_y: float,
    target_x: float,
    target_y: float,
) -> tuple[float, float, bool]:
    """
    Calculate acceleration from one gravity point toward another.

    The returned acceleration represents the normal point-to-point
    gravitational interaction. Placement bias is applied later by
    ``update_gravity_points()`` so the biased point can behave as a
    stronger gravity source without receiving the same boosted
    acceleration itself.

    Points within ``body_stop_radius`` are considered merged.

    Args:
        source_x:
            X coordinate of the point being accelerated.

        source_y:
            Y coordinate of the point being accelerated.

        target_x:
            X coordinate of the attracting point.

        target_y:
            Y coordinate of the attracting point.

    Returns:
        A tuple containing:

        - acceleration_x
        - acceleration_y
        - should_merge
    """
    dx = target_x - source_x
    dy = target_y - source_y

    distance = math.hypot(
        dx,
        dy,
    )

    if distance <= config.body_stop_radius:
        return (
            0.0,
            0.0,
            True,
        )

    gravity_strength = _gravity_strength(distance)

    inverse_distance = 1.0 / distance

    return (
        dx * inverse_distance * gravity_strength,
        dy * inverse_distance * gravity_strength,
        False,
    )


def update_gravity_points(
    points: list[GravityPoint],
    dt: float,
    bounds: tuple[
        float,
        float,
        float,
        float,
    ],
    place_bias: bool = False,
) -> GravityPoint | None:
    """
    Advance all gravity points under mutual attraction.

    Each unique point pair is evaluated once. All accelerations are
    accumulated before any point is moved, so point movement does not
    depend on list traversal order.

    Point order represents placement age:

    - ``points[0]`` is the oldest point.
    - ``points[-1]`` is the newest point.

    When ``place_bias`` is active, the newest point behaves like a heavier
    gravity source:

    - Older points are attracted toward it using
      ``last_placed_boost``.
    - The newest point receives only the normal reaction acceleration.
    - The newest point receives additional damping using
      ``last_placed_drag``.

    This gives the newly placed point more influence over the system
    without multiplying its own acceleration by the same amount.

    If two points move within ``body_stop_radius``, the older of the two
    is removed.

    Args:
        points:
            Mutable gravity-point list stored oldest-to-newest.

        dt:
            Elapsed simulation time in seconds.

        bounds:
            Virtual desktop bounds represented as:

            ``(left, top, right, bottom)``

        place_bias:
            Whether the newest point should receive placement-bias
            behavior.

    Returns:
        The removed gravity point if two points merged.

        Returns ``None`` when no merge occurred.
    """
    point_count = len(points)

    if point_count < 2:
        return None

    # The newest point is the biased point when placement bias is active.
    #
    # Using an index instead of:
    #
    #     point == points[-1]
    #
    # is important because GravityPoint is a dataclass. Dataclass equality
    # compares field values, meaning two separate points with identical
    # coordinates and velocities could otherwise compare as equal.
    biased_index = point_count - 1 if place_bias else None

    # Store acceleration separately for each axis.
    #
    # With the hard seven-point limit, the simulation evaluates at most
    # 21 unique point pairs per physics update.
    acceleration_x = [0.0] * point_count

    acceleration_y = [0.0] * point_count

    # --------------------------------------------------------
    # Calculate pair accelerations
    # --------------------------------------------------------

    for i in range(point_count - 1):
        point = points[i]

        for j in range(
            i + 1,
            point_count,
        ):
            other = points[j]

            (
                pair_ax,
                pair_ay,
                should_merge,
            ) = point_gravity_vector(
                point.x,
                point.y,
                other.x,
                other.y,
            )

            # ------------------------------------------------
            # Merge handling
            # ------------------------------------------------

            if should_merge:
                # Because i is always less than j, points[i] is always
                # older than points[j].
                #
                # Remove the oldest member of the colliding pair.
                return points.pop(i)

            # ------------------------------------------------
            # Placement bias
            # ------------------------------------------------

            if j == biased_index:
                # The newest point behaves like a heavier gravity source.
                #
                # The older point receives boosted acceleration toward the
                # newest point.
                acceleration_x[i] += pair_ax * config.last_placed_boost

                acceleration_y[i] += pair_ay * config.last_placed_boost

                # The biased point receives only the normal opposing
                # acceleration.
                acceleration_x[j] -= pair_ax

                acceleration_y[j] -= pair_ay

            else:
                # Normal equal-mass interaction.
                acceleration_x[i] += pair_ax

                acceleration_y[i] += pair_ay

                acceleration_x[j] -= pair_ax

                acceleration_y[j] -= pair_ay

    # --------------------------------------------------------
    # Desktop bounds
    # --------------------------------------------------------

    (
        screen_left,
        screen_top,
        screen_right,
        screen_bottom,
    ) = bounds

    max_speed_squared = config.point_max_speed * config.point_max_speed

    # --------------------------------------------------------
    # Integrate movement
    # --------------------------------------------------------

    for index, point in enumerate(points):
        is_biased_point = index == biased_index

        # ----------------------------------------------------
        # Velocity integration
        # ----------------------------------------------------

        point.velocity_x += acceleration_x[index] * dt

        point.velocity_y += acceleration_y[index] * dt

        # ----------------------------------------------------
        # Drag
        # ----------------------------------------------------

        if is_biased_point:
            # Additional damping gives the newest point more inertia.
            #
            # last_placed_drag values greater than 1 reduce the effective
            # drag multiplier.
            drag_factor = (config.point_drag / config.last_placed_drag) ** (
                dt * config.point_physics_hz
            )

        else:
            drag_factor = config.point_drag ** (dt * config.point_physics_hz)

        point.velocity_x *= drag_factor

        point.velocity_y *= drag_factor

        # ----------------------------------------------------
        # Speed limit
        # ----------------------------------------------------

        speed_squared = (
            point.velocity_x * point.velocity_x + point.velocity_y * point.velocity_y
        )

        # Avoid calculating a square root unless the velocity actually
        # needs to be clamped.
        if speed_squared > max_speed_squared:
            speed = math.sqrt(speed_squared)

            scale = config.point_max_speed / speed

            point.velocity_x *= scale

            point.velocity_y *= scale

        # ----------------------------------------------------
        # Position integration
        # ----------------------------------------------------

        point.x += point.velocity_x * dt

        point.y += point.velocity_y * dt

        # ----------------------------------------------------
        # Desktop-edge collisions
        # ----------------------------------------------------

        if point.x <= screen_left:
            point.x = screen_left

            if point.velocity_x < 0:
                point.velocity_x = 0.0

        elif point.x >= screen_right:
            point.x = screen_right

            if point.velocity_x > 0:
                point.velocity_x = 0.0

        if point.y <= screen_top:
            point.y = screen_top

            if point.velocity_y < 0:
                point.velocity_y = 0.0

        elif point.y >= screen_bottom:
            point.y = screen_bottom

            if point.velocity_y > 0:
                point.velocity_y = 0.0

    return None