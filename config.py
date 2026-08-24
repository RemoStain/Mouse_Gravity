from dataclasses import dataclass


@dataclass
class MouseGravityConfig:
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
    log_telemetry_hz: int = 10


config = MouseGravityConfig()