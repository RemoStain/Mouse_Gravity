from dataclasses import dataclass


@dataclass
class MouseGravityConfig:
    """
    Configuration for the mouse gravity simulation.

    Attributes:
        gravity (float): The gravitational force applied to the mouse cursor.
        reference_distance (float): The reference distance for gravity calculations.
        gravity_distance_power (float): The power to which the distance is raised for gravity calculations.
        min_gravity_distance (float): The minimum distance at which gravity is applied.
        max_gravity_acceleration (float): The maximum acceleration due to gravity.
        max_speed (float): The maximum speed of the mouse cursor.
        drag (float): The drag factor applied to the mouse cursor's movement.
        stop_radius (float): The radius within which the mouse cursor will stop moving.
        fps (int): The frames per second for the simulation.
        normal_input_strength (float): The strength of normal mouse input.
        toward_input_multiplier (float): Multiplier for input towards the center of gravity.
        away_input_multiplier (float): Multiplier for input away from the center of gravity.
        lateral_boost_enabled_by_default (bool): Whether lateral boost is enabled by default.
        lateral_boost_multiplier (float): Multiplier for lateral boost input.
        click_sequence_timeout (float): Timeout for recognizing click sequences.
        logging_enabled_by_default (bool): Whether logging is enabled by default.
        log_telemetry_hz (int): Frequency of telemetry logging in Hertz.
    """

    # --------------------------------------------------------
    # Gravity
    # --------------------------------------------------------

    gravity: float = 2000.0

    reference_distance: float = 300.0
    gravity_distance_power: float = 1.5

    min_gravity_distance: float = 40.0
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

    normal_input_strength: float = 10.0

    toward_input_multiplier: float = 1.0
    away_input_multiplier: float = 0.35

    lateral_boost_enabled_by_default: bool = False
    lateral_boost_multiplier: float = 2.0

    # --------------------------------------------------------
    # Click recognition
    # --------------------------------------------------------

    click_sequence_timeout: float = 0.35

    # --------------------------------------------------------
    # Logging
    # --------------------------------------------------------

    logging_enabled_by_default: bool = True
    log_telemetry_hz: int = 1


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