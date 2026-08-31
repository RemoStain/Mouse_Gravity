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
        x: Horizontal position on the virtual desktop.
        y: Vertical position on the virtual desktop.
        velocity_x: Horizontal velocity in pixels per second.
        velocity_y: Vertical velocity in pixels per second.
    """

    x: float
    y: float
    velocity_x: float = 0.0
    velocity_y: float = 0.0


def _gravity_strength(distance: float, last_placed_boost:bool=False) -> float:
    """
    Return the configured point-to-point gravity magnitude.

    The configured minimum gravity distance prevents the acceleration from
    growing without bound at very short distances. The final result is also
    capped by max_gravity_acceleration.

    Args:
        distance: Distance between the two gravity points.

    Returns:
        Gravity acceleration magnitude for the supplied distance.
    """
    gravity_distance = max(
        distance,
        config.min_gravity_distance,
    )

    if last_placed_boost:
        gravity_strength = (
        (config.point_gravity * config.last_placed_boost)
        * (config.reference_distance / gravity_distance)
        ** config.gravity_distance_power
    )
    else:
        gravity_strength = (
            config.point_gravity
            * (config.reference_distance / gravity_distance)
            ** config.gravity_distance_power
        )

    # print(f"Last Placed (Gravity Strength): {last_placed_boost}")
    # print(f"Gravity Strength: {gravity_strength}")

    return min(
        gravity_strength,
        config.max_gravity_acceleration,
    )


def point_gravity_vector(
    source_x: float,
    source_y: float,
    target_x: float,
    target_y: float,
    last_placed:bool,
) -> tuple[float, float, bool]:
    """
    Calculate acceleration from one gravity point toward another.

    Points that move within body_stop_radius are considered merged. The
    caller decides which point is removed so point age/order can be handled
    consistently in one place.

    Args:
        source_x: X coordinate of the point being accelerated.
        source_y: Y coordinate of the point being accelerated.
        target_x: X coordinate of the attracting point.
        target_y: Y coordinate of the attracting point.

    Returns:
        A tuple containing:
            acceleration_x,
            acceleration_y,
            should_merge.
    """
    dx = target_x - source_x
    dy = target_y - source_y

    distance = math.hypot(dx, dy)

    if distance <= config.body_stop_radius:
        return 0.0, 0.0, True

    # print(f"Last Placed: {last_placed}")

    gravity_strength = _gravity_strength(distance, last_placed)
    inverse_distance = 1.0 / distance

    return (
        dx * inverse_distance * gravity_strength,
        dy * inverse_distance * gravity_strength,
        False,
    )


def update_gravity_points(
    points: list[GravityPoint],
    dt: float,
    bounds: tuple[float, float, float, float],
    place_bias: bool = False
) -> GravityPoint | None:
    """
    Advance all gravity points under mutual attraction.

    Each unique pair is evaluated once. Accelerations are accumulated before
    any point is moved, so the result does not depend on update order.

    If two points enter body_stop_radius, the older point is removed. Point
    age is represented by list order: earlier entries are older than later
    entries. This matches normal placement behavior where newly created
    points are appended to the list.

    Args:
        points: Mutable gravity-point list in oldest-to-newest order.
        dt: Elapsed simulation time in seconds.
        bounds: Virtual desktop bounds as left, top, right, bottom.

    Returns:
        The removed gravity point if two points merged, otherwise None.
    """

    global last_placed
    point_count = len(points)

    if point_count < 2:
        return None

    # Flat lists avoid repeatedly allocating small nested vectors.
    acceleration_x = [0.0] * point_count
    acceleration_y = [0.0] * point_count

    # With the hard five-point limit this evaluates at most 10 pairs.
    for i in range(point_count - 1):
        point = points[i]

        

        for j in range(i + 1, point_count):
            other = points[j]
            # print(f"Point being evaluated:{point}")
            # print(f"Point being evaluated (verify with position in list):{points[i]}")

            # print(f"Last point in group: {points[-1]}")

            if points[j] == points[-1] and place_bias:
                last_placed = True
                # print("Last Placed SHOULD BE TRUE HERE WTF")
            else:
                last_placed = False
                # print("Last Placed SHOULD BE FALSE HERE")


            # print(f"Index: {i}, {j}")
            # print(f"Last Placed (pre PG-Vector): {last_placed}")

            pair_ax, pair_ay, should_merge = point_gravity_vector(
                point.x,
                point.y,
                other.x,
                other.y,
                last_placed
            )

            # print(f"Last Placed (after PG-Vector): {last_placed}")


            if should_merge:
                # i is always older than j because points are stored in
                # insertion order. Remove the oldest point on collision.
                return points.pop(i)

            acceleration_x[i] += pair_ax
            acceleration_y[i] += pair_ay

            # Equal-mass points receive equal and opposite acceleration.
            acceleration_x[j] -= pair_ax
            acceleration_y[j] -= pair_ay

    screen_left, screen_top, screen_right, screen_bottom = bounds

    
    max_speed_squared = config.point_max_speed * config.point_max_speed

    for index, point in enumerate(points):

        # FIND A BETTER WAY TO DO THIS
        if point == points[-1] and place_bias:
            last_placed = True
        else:
            last_placed = False

        # Scale drag by elapsed time so damping remains approximately stable
        # if the physics update rate changes.
        if last_placed:
            drag_factor = (config.point_drag / config.last_placed_drag) ** (dt * config.point_physics_hz)
            
        else:
            drag_factor = config.point_drag ** (dt * config.point_physics_hz)

        # print(f"Index (Drag Calculation): {index}")
        # print(f"Last Placed (Drag Calculation): {last_placed}")

        point.velocity_x += acceleration_x[index] * dt
        point.velocity_y += acceleration_y[index] * dt

        point.velocity_x *= drag_factor
        point.velocity_y *= drag_factor

        speed_squared = (
            point.velocity_x * point.velocity_x
            + point.velocity_y * point.velocity_y
        )

        # Avoid sqrt unless the speed actually requires clamping.
        if speed_squared > max_speed_squared:
            speed = math.sqrt(speed_squared)
            scale = config.point_max_speed / speed

            point.velocity_x *= scale
            point.velocity_y *= scale

        point.x += point.velocity_x * dt
        point.y += point.velocity_y * dt

        # Gravity points stop at virtual-desktop edges rather than moving
        # permanently off-screen.
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
