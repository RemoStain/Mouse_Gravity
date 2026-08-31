from dataclasses import dataclass


# Hard safety/performance limit for the N-body simulation.
# Five points produce at most 10 unique point-to-point calculations.
MAX_GRAVITY_POINTS = 7


@dataclass
class GravityConfig:
    """
    Runtime configuration for the gravity-point N-body simulation.

    The mouse is used only for point placement and preset positioning.
    These settings affect gravity-point motion, placement, logging, and
    click recognition; they do not control or move the mouse cursor.
    """

    # --------------------------------------------------------
    # Point-to-point gravity
    # --------------------------------------------------------

    # Base gravity acceleration at reference_distance.
    point_gravity: float = 8.0

    # Distance used as the baseline for the gravity falloff equation.
    reference_distance: float = 300.0

    # Exponent controlling how quickly gravity changes with distance.
    gravity_distance_power: float = 1.5

    # Distances below this value use this value for force calculations,
    # preventing excessively large acceleration near another point.
    min_gravity_distance: float = 25.0

    # Hard acceleration cap for point-to-point gravity.
    max_gravity_acceleration: float = 6000.0

    # Distance at which two gravity points are considered merged.
    body_stop_radius: float = 1.0

    # --------------------------------------------------------
    # Point motion
    # --------------------------------------------------------

    # Number of gravity points the user may place.
    multi_point_count: int = 7

    # Velocity damping. Values closer to 1 preserve momentum longer.
    point_drag: float = 0.99

    # Maximum gravity-point speed in pixels per second.
    point_max_speed: float = 1000.0

    # Physics update rate for gravity-point movement.
    point_physics_hz: float = 30.0

    # --------------------------------------------------------
    # Placement bias
    # --------------------------------------------------------

    # Enable special behavior for the most recently manually placed point.

    # Placement presets begin without a biased point. Bias becomes active
    # only after the user manually adds another point.
    place_bias_enabled: bool = True

    # The newest manually placed point attracts other points more strongly.
    last_placed_boost: float = 3.0

    # Additional damping applied to the newest manually placed point.
    last_placed_drag: float = 6.0


    # --------------------------------------------------------
    # N-body placement presets
    # --------------------------------------------------------

    # Distance from the cursor to each spawned point.
    triangle_spawn_radius: float = 300.0
    pentagram_spawn_radius: float = 300.0

    random_spawn_radius: float = 300.0
    random_spawn_number: int = 4

    # Delay after pressing an N-body preset button. This gives the user
    # time to move the cursor to the desired center before spawning.
    n_body_spawn_delay: float = 3.0

    # --------------------------------------------------------
    # Click recognition
    # --------------------------------------------------------

    # Maximum delay between clicks belonging to one click sequence.
    click_sequence_timeout: float = 0.35

    # --------------------------------------------------------
    # Logging
    # --------------------------------------------------------

    logging_enabled_by_default: bool = True
    log_telemetry_hz: int = 5


config = GravityConfig()


# Presets now contain only settings relevant to gravity-point physics.
# Existing preset names are retained where their values can be translated
# meaningfully to the N-body-only branch.
PRESETS = {
    "Balanced": {
        "point_gravity": 3.0,
        "reference_distance": 300.0,
        "gravity_distance_power": 1.0,
        "last_placed_boost": 3.0,
        "last_placed_drag": 6.0,
        "min_gravity_distance": 40.0,
        "max_gravity_acceleration": 5000.0,
        "body_stop_radius": 2.0,
        "point_drag": 0.99,
        "point_max_speed": 100.0,
        "point_physics_hz": 30.0,
    },
    "Stable Orbit": {
        "point_gravity": 4.0,
        "reference_distance": 350.0,
        "gravity_distance_power": 0.9,
        "last_placed_boost": 3.0,
        "last_placed_drag": 6.0,
        "min_gravity_distance": 50.0,
        "max_gravity_acceleration": 4500.0,
        "body_stop_radius": 1.0,
        "point_drag": 0.99,
        "point_max_speed": 100.0,
        "point_physics_hz": 30.0,
    },
    "Heavy Gravity": {
        "point_gravity": 10.0,
        "reference_distance": 250.0,
        "gravity_distance_power": 2.0,
        "last_placed_boost": 3.0,
        "last_placed_drag": 6.0,
        "min_gravity_distance": 50.0,
        "max_gravity_acceleration": 6500.0,
        "body_stop_radius": 2.0,
        "point_drag": 0.99,
        "point_max_speed": 100.0,
        "point_physics_hz": 30.0,
    },
    "Light Gravity": {
        "point_gravity": 2.0,
        "reference_distance": 400.0,
        "gravity_distance_power": 1.2,
        "last_placed_boost": 3.0,
        "last_placed_drag": 6.0,
        "min_gravity_distance": 30.0,
        "max_gravity_acceleration": 4000.0,
        "body_stop_radius": 3.0,
        "point_drag": 0.99,
        "point_max_speed": 100.0,
        "point_physics_hz": 30.0,
    },
    "Eccentic": {
        "point_gravity": 6.0,
        "reference_distance": 300.0,
        "gravity_distance_power": 2.0,
        "last_placed_boost": 3.0,
        "last_placed_drag": 6.0,
        "min_gravity_distance": 40.0,
        "max_gravity_acceleration": 6000.0,
        "body_stop_radius": 1.0,
        "point_drag": 0.99,
        "point_max_speed": 100.0,
        "point_physics_hz": 30.0,
    },
    "Thick Atmosphere": {
        "point_gravity": 8.0,
        "reference_distance": 500.0,
        "gravity_distance_power": 1.25,
        "last_placed_boost": 3.0,
        "last_placed_drag": 6.0,
        "min_gravity_distance": 100.0,
        "max_gravity_acceleration": 4000.0,
        "body_stop_radius": 5.0,
        "point_drag": 0.99,
        "point_max_speed": 100.0,
        "point_physics_hz": 30.0,
    },
    "Sicko Mode": {
        "point_gravity": 250.0,
        "reference_distance": 500.0,
        "gravity_distance_power": 10,
        "last_placed_boost": 4.0,
        "last_placed_drag": 2.5,
        "min_gravity_distance": 10.0,
        "max_gravity_acceleration": 3000.0,
        "body_stop_radius": 1.0,
        "point_drag": 0.9999,
        "point_max_speed": 5000.0,
        "point_physics_hz": 60,
    },
}
