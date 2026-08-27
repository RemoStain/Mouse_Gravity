import math
from dataclasses import dataclass
from typing import Sequence

from config import config


@dataclass
class GravityPoint:
    """
    A movable gravity source used by multi-point mode.

    Positions and velocities are stored as floats so the point can move
    smoothly even though the visible marker is rendered at integer pixels.
    """

    x: float
    y: float
    velocity_x: float = 0.0
    velocity_y: float = 0.0


def _gravity_strength(
    distance: float,
    multiplier: float = 1.0,
) -> float:
    """
    Return the configured gravity magnitude for a known distance.

    Keeping this calculation separate avoids recalculating distance in
    single-point mode and keeps the gravity law consistent everywhere.
    """
    gravity_distance = max(
        distance,
        config.min_gravity_distance,
    )

    gravity_strength = (
        config.gravity
        * (config.reference_distance / gravity_distance)
        ** config.gravity_distance_power
    )

    gravity_strength = min(
        gravity_strength,
        config.max_gravity_acceleration,
    )

    return gravity_strength * multiplier


def gravity_vector(
    source_x: float,
    source_y: float,
    target_x: float,
    target_y: float,
    multiplier: float = 1.0,
) -> tuple[float, float, float]:
    """
    Calculate acceleration from one position toward another.

    Args:
        source_x: X coordinate of the object being accelerated.
        source_y: Y coordinate of the object being accelerated.
        target_x: X coordinate of the gravity source.
        target_y: Y coordinate of the gravity source.
        multiplier: Optional force multiplier.

    Returns:
        A tuple containing acceleration_x, acceleration_y, and the
        gravity magnitude.
    """
    dx = target_x - source_x
    dy = target_y - source_y

    distance = math.hypot(dx, dy)

    # Stop applying gravity inside the configured target radius.
    if distance <= config.stop_radius:
        return 0.0, 0.0, 0.0

    gravity_strength = _gravity_strength(
        distance,
        multiplier,
    )

    inverse_distance = 1.0 / distance

    return (
        dx * inverse_distance * gravity_strength,
        dy * inverse_distance * gravity_strength,
        gravity_strength,
    )


def single_point_gravity(
    cursor_x: float,
    cursor_y: float,
    target_x: float,
    target_y: float,
) -> tuple[float, float, float, float, float, float]:
    """
    Calculate classic single-target gravity without duplicate distance work.

    Returns:
        acceleration_x,
        acceleration_y,
        radial_x,
        radial_y,
        distance,
        gravity_strength
    """
    dx = target_x - cursor_x
    dy = target_y - cursor_y

    distance = math.hypot(dx, dy)

    if distance <= config.stop_radius:
        return 0.0, 0.0, 0.0, 0.0, distance, 0.0

    gravity_strength = _gravity_strength(distance)
    inverse_distance = 1.0 / distance

    radial_x = dx * inverse_distance
    radial_y = dy * inverse_distance

    return (
        radial_x * gravity_strength,
        radial_y * gravity_strength,
        radial_x,
        radial_y,
        distance,
        gravity_strength,
    )


def multi_point_gravity(
    cursor_x: float,
    cursor_y: float,
    points: Sequence[GravityPoint],
) -> tuple[float, float]:
    """
    Return the combined acceleration from all active gravity points.

    The live point objects can be passed directly. With a maximum of five
    points, the caller can safely hold the shared-state lock for this very
    small calculation instead of allocating point snapshots every frame.
    """
    total_x = 0.0
    total_y = 0.0

    for point in points:
        acceleration_x, acceleration_y, _ = gravity_vector(
            cursor_x,
            cursor_y,
            point.x,
            point.y,
        )

        total_x += acceleration_x
        total_y += acceleration_y

    return total_x, total_y


def update_gravity_points(
    points: list[GravityPoint],
    dt: float,
    bounds: tuple[float, float, float, float],
) -> None:
    """
    Advance the gravity points under weak mutual attraction.

    Point-to-point physics is intended to run at a lower frequency than
    cursor physics. All pair accelerations are calculated before any point
    is moved, so the result does not depend on list order.

    Args:
        points: Mutable gravity points to update.
        dt: Elapsed simulation time for this point-physics step.
        bounds: Virtual desktop bounds as left, top, right, bottom.
    """
    point_count = len(points)

    if point_count < 2:
        return

    # Two flat lists are cheaper than allocating nested [x, y] lists.
    acceleration_x = [0.0] * point_count
    acceleration_y = [0.0] * point_count

    # Each unique pair is evaluated once. With the hard five-point limit,
    # this loop performs at most 10 pair calculations per point update.
    for i in range(point_count - 1):
        point = points[i]

        for j in range(i + 1, point_count):
            other = points[j]

            pair_ax, pair_ay, _ = gravity_vector(
                point.x,
                point.y,
                other.x,
                other.y,
                multiplier=config.point_gravity_multiplier,
            )

            acceleration_x[i] += pair_ax
            acceleration_y[i] += pair_ay

            # Equal-mass points receive equal and opposite acceleration.
            acceleration_x[j] -= pair_ax
            acceleration_y[j] -= pair_ay

    screen_left, screen_top, screen_right, screen_bottom = bounds

    # point_drag historically behaved like a per-cursor-frame multiplier.
    # Scale it by dt so lowering the point-physics rate does not materially
    # change the amount of damping per second.
    drag_factor = config.point_drag ** (dt * config.fps)
    max_speed_squared = config.point_max_speed * config.point_max_speed

    for index, point in enumerate(points):
        point.velocity_x += acceleration_x[index] * dt
        point.velocity_y += acceleration_y[index] * dt

        point.velocity_x *= drag_factor
        point.velocity_y *= drag_factor

        speed_squared = (
            point.velocity_x * point.velocity_x
            + point.velocity_y * point.velocity_y
        )

        # Avoid a square root unless the speed actually needs clamping.
        if speed_squared > max_speed_squared:
            speed = math.sqrt(speed_squared)
            scale = config.point_max_speed / speed

            point.velocity_x *= scale
            point.velocity_y *= scale

        point.x += point.velocity_x * dt
        point.y += point.velocity_y * dt

        # Points stop at virtual desktop edges rather than disappearing
        # off-screen.
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
