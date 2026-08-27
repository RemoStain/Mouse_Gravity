from dataclasses import dataclass


# Hard safety/performance limit for multi-point mode.
# With five points there are at most 10 point-to-point pairs.
MAX_GRAVITY_POINTS = 5


@dataclass
class MouseGravityConfig:
    """
    Configuration for the mouse gravity simulation.
    """

    # --------------------------------------------------------
    # Gravity
    # --------------------------------------------------------

    gravity: float = 2000.0
    reference_distance: float = 300.0
    gravity_distance_power: float = 1.5
    min_gravity_distance: float = 25.0
    max_gravity_acceleration: float = 6000.0

    # --------------------------------------------------------
    # Momentum
    # --------------------------------------------------------

    max_speed: float = 2500.0
    drag: float = 0.9999
    stop_radius: float = 5.0
    fps: int = 120

    # --------------------------------------------------------
    # Physical mouse input
    # --------------------------------------------------------

    normal_input_strength: float = 7.0
    toward_input_multiplier: float = 1.0
    away_input_multiplier: float = 0.35
    lateral_boost_enabled_by_default: bool = False
    lateral_boost_multiplier: float = 2.0

    # --------------------------------------------------------
    # Multi-point gravity
    # --------------------------------------------------------

    # Number of points the user can place in multi-point mode.
    # This is validated against MAX_GRAVITY_POINTS in the UI.
    multi_point_count: int = 5

    # Gravity points attract each other at a much weaker strength
    # than they attract the cursor.
    point_gravity_multiplier: float = 0.002
    point_drag: float = 0.9
    point_max_speed: float = 100.0


    # --------------------------------------------------------
    # N-body placement presets
    # --------------------------------------------------------

    # Distance from the cursor to each spawned point.
    triangle_spawn_radius: float = 200.0
    pentagram_spawn_radius: float = 200.0

    # Delay after pressing an N-body preset button.
    # This gives the user time to move the cursor to the desired center point.
    n_body_spawn_delay: float = 3.0

    # --------------------------------------------------------
    # Click recognition
    # --------------------------------------------------------

    click_sequence_timeout: float = 0.35

    # --------------------------------------------------------
    # Logging
    # --------------------------------------------------------

    logging_enabled_by_default: bool = True
    log_telemetry_hz: int = 5


config = MouseGravityConfig()


PRESETS = {
    "Balanced": {
        "gravity": 1500.0,
        "reference_distance": 300.0,
        "gravity_distance_power": 1.0,
        "min_gravity_distance": 40.0,
        "max_gravity_acceleration": 5000.0,
        "max_speed": 2000.0,
        "drag": 0.999,
        "stop_radius": 2.0,
        "fps": 120,
        "normal_input_strength": 10.0,
        "toward_input_multiplier": 1.0,
        "away_input_multiplier": 0.4,
        "lateral_boost_multiplier": 4.0,
    },
    "Stable Orbit": {
        "gravity": 2000.0,
        "reference_distance": 350.0,
        "gravity_distance_power": 0.9,
        "min_gravity_distance": 50.0,
        "max_gravity_acceleration": 4500.0,
        "max_speed": 3200.0,
        "drag": 0.9995,
        "stop_radius": 1.0,
        "fps": 120,
        "normal_input_strength": 10.0,
        "toward_input_multiplier": 1.0,
        "away_input_multiplier": 0.25,
        "lateral_boost_multiplier": 4.0,
    },
    "Heavy Gravity": {
        "gravity": 5000.0,
        "reference_distance": 250.0,
        "gravity_distance_power": 2.0,
        "min_gravity_distance": 50.0,
        "max_gravity_acceleration": 6500.0,
        "max_speed": 2200.0,
        "drag": 0.995,
        "stop_radius": 2.0,
        "fps": 120,
        "normal_input_strength": 10.0,
        "toward_input_multiplier": 1.0,
        "away_input_multiplier": 0.2,
        "lateral_boost_multiplier": 2.0,
    },
    "Light Gravity": {
        "gravity": 1000.0,
        "reference_distance": 400.0,
        "gravity_distance_power": 1.2,
        "min_gravity_distance": 30.0,
        "max_gravity_acceleration": 4000.0,
        "max_speed": 1800.0,
        "drag": 0.9998,
        "stop_radius": 3.0,
        "fps": 120,
        "normal_input_strength": 10.0,
        "toward_input_multiplier": 1.0,
        "away_input_multiplier": 0.5,
        "lateral_boost_multiplier": 3.0,
    },
    "Eccentic": {
        "gravity": 2500.0,
        "reference_distance": 300.0,
        "gravity_distance_power": 1.5,
        "min_gravity_distance": 40.0,
        "max_gravity_acceleration": 6000.0,
        "max_speed": 3000.0,
        "drag": 0.9999,
        "stop_radius": 5.0,
        "fps": 120,
        "normal_input_strength": 10.0,
        "toward_input_multiplier": 1.0,
        "away_input_multiplier": 0.35,
        "lateral_boost_multiplier": 2.0,
    },
    "Thick Atmosphere": {
        "gravity": 2000.0,
        "reference_distance": 300.0,
        "gravity_distance_power": 1.5,
        "min_gravity_distance": 40.0,
        "max_gravity_acceleration": 6000.0,
        "max_speed": 1500.0,
        "drag": 0.9,
        "stop_radius": 5.0,
        "fps": 120,
        "normal_input_strength": 10.0,
        "toward_input_multiplier": 1.0,
        "away_input_multiplier": 0.35,
        "lateral_boost_multiplier": 2.0,
    },
}
