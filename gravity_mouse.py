import math
import threading
import time

import logging
import os
import threading
from datetime import datetime
from pathlib import Path

from PIL import Image, ImageDraw
from pynput import mouse
import pystray

import ctypes

# ------------------------------------------------------------
# Physics settings
# ------------------------------------------------------------

GRAVITY = 1500.0

GRAVITY_DISTANCE_POWER = 1.1
REFERENCE_DISTANCE = 300.0

MIN_GRAVITY_DISTANCE = 40.0
MAX_GRAVITY_ACCELERATION = 6000.0

MAX_SPEED = 3000.0
DRAG = 0.996
STOP_RADIUS = 5.0
FPS = 120

# How strongly actual mouse movement affects orbital momentum
TOWARD_INPUT_MULTIPLIER = (
    1.0  # pixels per second per pixel of user input toward the target
)
AWAY_INPUT_MULTIPLIER = (
    0.35  # pixels per second per pixel of user input away from the target
)

LATERAL_BOOST_MULTIPLIER = (
    2.0  # pixels per second per pixel of user input perpendicular to the target
)
NORMAL_INPUT_STRENGTH = (
    10.0  # pixels per second per pixel of user input in any direction
)


# ------------------------------------------------------------
# Click settings
# ------------------------------------------------------------

CLICK_SEQUENCE_TIMEOUT = 0.35  # seconds


# ------------------------------------------------------------
# Shared state
# ------------------------------------------------------------

target = None  # (x, y) tuple of the current gravity target, or None if no target is set

velocity_x = 0.0  # pixels per second, horizontal component of the cursor's velocity
velocity_y = 0.0  # pixels per second, vertical component of the cursor's velocity

lateral_boost = False  # True if lateral boost is active, False otherwise
orbit_direction = (
    1  # 1 for clockwise, -1 for counterclockwise, 0 if no orbit direction is set
)

click_count = 0  # Number of clicks detected in the current click sequence
last_click_time = 0.0  # Time of the last click in the current click sequence
click_timer = (
    None  # Timer object for the current click sequence, or None if no timer is active
)

click_lock = (
    threading.Lock()
)  # Lock for synchronizing access to click_count, last_click_time, and click_timer
state_lock = (
    threading.Lock()
)  # Lock for synchronizing access to target, velocity_x, velocity_y, lateral_boost, and orbit_direction

running = (
    threading.Event()
)  # Event to signal whether the program is running or should exit
running.set()  # Set the running event to True to indicate that the program is running

controller = mouse.Controller()  # Controller object for controlling the mouse cursor

tray_icon = (
    None  # Tray icon object for the system tray, or None if no tray icon is created
)
listener = None  # Mouse listener object for detecting mouse clicks, or None if no listener is created

# ------------------------------------------------------------
# Logging settings
# ------------------------------------------------------------

LOGGING_ENABLED_BY_DEFAULT = False

# Number of physics snapshots written per second.
LOG_TELEMETRY_HZ = 10


# ------------------------------------------------------------
# Logging state
# ------------------------------------------------------------

logging_enabled = False
log_handler = None
log_path = None

logging_lock = threading.Lock()

logger = logging.getLogger("mouse_gravity")
logger.setLevel(logging.DEBUG)
logger.propagate = False


# ------------------------------------------------------------
# Virtual desktop bounds
# ------------------------------------------------------------

user32 = ctypes.windll.user32

SM_XVIRTUALSCREEN = 76
SM_YVIRTUALSCREEN = 77
SM_CXVIRTUALSCREEN = 78
SM_CYVIRTUALSCREEN = 79

SCREEN_LEFT = user32.GetSystemMetrics(SM_XVIRTUALSCREEN)
SCREEN_TOP = user32.GetSystemMetrics(SM_YVIRTUALSCREEN)

SCREEN_WIDTH = user32.GetSystemMetrics(SM_CXVIRTUALSCREEN)
SCREEN_HEIGHT = user32.GetSystemMetrics(SM_CYVIRTUALSCREEN)

SCREEN_RIGHT = SCREEN_LEFT + SCREEN_WIDTH - 1
SCREEN_BOTTOM = SCREEN_TOP + SCREEN_HEIGHT - 1

print(
    f"Virtual desktop: "
    f"{SCREEN_LEFT}, {SCREEN_TOP} -> "
    f"{SCREEN_RIGHT}, {SCREEN_BOTTOM}"
)


# ------------------------------------------------------------
# Logging
# ------------------------------------------------------------


def get_log_directory():
    """
    Return the directory where Mouse Gravity logs are stored.
    """
    return Path(__file__).resolve().parent


def start_logging():
    global logging_enabled
    global log_handler
    global log_path

    with logging_lock:
        if log_handler is not None:
            return

        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")

        log_path = get_log_directory() / f"logs/mouse_gravity_{timestamp}.log"

        log_handler = logging.FileHandler(
            log_path,
            encoding="utf-8",
        )

        log_handler.setLevel(logging.DEBUG)

        formatter = logging.Formatter(
            "%(asctime)s.%(msecs)03d | " "%(levelname)-8s | " "%(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )

        log_handler.setFormatter(formatter)

        logger.addHandler(log_handler)

        logging_enabled = True

    logger.info("LOGGING | enabled")

    log_configuration()

    print(f"Logging enabled: {log_path}")


def stop_logging():
    global logging_enabled
    global log_handler

    with logging_lock:
        if log_handler is None:
            logging_enabled = False
            return

        logger.info("LOGGING | disabled")

        handler = log_handler

        log_handler = None
        logging_enabled = False

        logger.removeHandler(handler)

        handler.flush()
        handler.close()

    print("Logging disabled.")


def log_configuration():
    """
    Record all important tuning constants at startup.
    """
    logger.info("Mouse Gravity started")

    logger.info(
        "CONFIG  | "
        "GRAVITY=%s | "
        "REFERENCE_DISTANCE=%s | "
        "GRAVITY_DISTANCE_POWER=%s | "
        "MIN_GRAVITY_DISTANCE=%s | "
        "MAX_GRAVITY_ACCELERATION=%s",
        GRAVITY,
        REFERENCE_DISTANCE,
        GRAVITY_DISTANCE_POWER,
        MIN_GRAVITY_DISTANCE,
        MAX_GRAVITY_ACCELERATION,
    )

    logger.info(
        "CONFIG | " "MAX_SPEED=%s | " "DRAG=%s | " "STOP_RADIUS=%s | " "FPS=%s",
        MAX_SPEED,
        DRAG,
        STOP_RADIUS,
        FPS,
    )

    logger.info(
        "CONFIG | "
        "NORMAL_INPUT_STRENGTH=%s | "
        "TOWARD_INPUT_MULTIPLIER=%s | "
        "AWAY_INPUT_MULTIPLIER=%s | "
        "LATERAL_BOOST_MULTIPLIER=%s",
        NORMAL_INPUT_STRENGTH,
        TOWARD_INPUT_MULTIPLIER,
        AWAY_INPUT_MULTIPLIER,
        LATERAL_BOOST_MULTIPLIER,
    )

    logger.info(
        "CONFIG | " "CLICK_SEQUENCE_TIMEOUT=%s | " "LOG_TELEMETRY_HZ=%s",
        CLICK_SEQUENCE_TIMEOUT,
        LOG_TELEMETRY_HZ,
    )

    logger.info(
        "DESKTOP | "
        "left=%s | "
        "top=%s | "
        "right=%s | "
        "bottom=%s | "
        "width=%s | "
        "height=%s",
        SCREEN_LEFT,
        SCREEN_TOP,
        SCREEN_RIGHT,
        SCREEN_BOTTOM,
        SCREEN_WIDTH,
        SCREEN_HEIGHT,
    )


# ------------------------------------------------------------
# Tray icon
# ------------------------------------------------------------


def create_vortex_icon(size=64, boost_active=False):
    """
    Create a vortex icon with optional boost indicator.

    Args:
        size (int): The size of the icon in pixels (width and height).
        boost_active (bool): Whether the lateral boost is active.

    Returns:
        PIL.Image: The generated vortex icon image.
    """
    image = Image.new(
        "RGBA",
        (size, size),
        (15, 5, 25, 255),
    )

    draw = ImageDraw.Draw(image)

    center_x = size / 2
    center_y = size / 2

    # Vortex
    for arm in range(4):
        points = []
        arm_offset = arm * (math.pi / 2)

        for i in range(120):
            t = i / 119

            angle = arm_offset + t * math.pi * 3.5

            radius = size * 0.42 * (1 - t) + 2

            x = center_x + math.cos(angle) * radius
            y = center_y + math.sin(angle) * radius

            points.append((x, y))

        purple = 90 + arm * 20

        draw.line(
            points,
            fill=(purple, 20, 150, 255),
            width=3,
        )

    # Dark center
    center_radius = size * 0.10

    draw.ellipse(
        (
            center_x - center_radius,
            center_y - center_radius,
            center_x + center_radius,
            center_y + center_radius,
        ),
        fill=(5, 0, 10, 255),
    )

    # --------------------------------------------------------
    # Green boost arrow
    # --------------------------------------------------------

    if boost_active:
        badge_background = (200, 200, 200, 255)
        green = (0, 150, 35, 255)
        outline = (0, 50, 10, 255)

        # --------------------------------------------------------
        # Badge
        # --------------------------------------------------------

        box_left = int(size * 0.50)
        box_top = int(size * -0.04)
        box_right = int(size * 1.02)
        box_bottom = int(size * 0.50)

        draw.rectangle(
            (
                box_left,
                box_top,
                box_right,
                box_bottom,
            ),
            fill=badge_background,
        )

        # --------------------------------------------------------
        # Badge dimensions
        # --------------------------------------------------------

        badge_width = box_right - box_left
        badge_height = box_bottom - box_top

        center_x = box_left + badge_width / 2

        # --------------------------------------------------------
        # Arrow proportions
        #
        # These are all relative to the badge.
        # --------------------------------------------------------

        ARROW_TOP_MARGIN = 0.05
        ARROW_BOTTOM_MARGIN = 0.05

        ARROW_HEAD_WIDTH = 0.70
        ARROW_HEAD_HEIGHT = 0.40

        ARROW_SHAFT_WIDTH = 0.30

        # --------------------------------------------------------
        # Calculate arrow dimensions
        # --------------------------------------------------------

        arrow_top = box_top + badge_height * ARROW_TOP_MARGIN

        arrow_bottom = box_bottom - badge_height * ARROW_BOTTOM_MARGIN

        head_half_width = badge_width * ARROW_HEAD_WIDTH / 2

        head_height = badge_height * ARROW_HEAD_HEIGHT

        shaft_half_width = badge_width * ARROW_SHAFT_WIDTH / 2

        head_bottom = arrow_top + head_height

        # --------------------------------------------------------
        # Arrow
        # --------------------------------------------------------

        arrow_points = [
            # Tip
            (
                center_x,
                arrow_top,
            ),
            # Right side of arrowhead
            (
                center_x + head_half_width,
                head_bottom,
            ),
            # Right shoulder
            (
                center_x + shaft_half_width,
                head_bottom,
            ),
            # Bottom-right shaft
            (
                center_x + shaft_half_width,
                arrow_bottom,
            ),
            # Bottom-left shaft
            (
                center_x - shaft_half_width,
                arrow_bottom,
            ),
            # Left shoulder
            (
                center_x - shaft_half_width,
                head_bottom,
            ),
            # Left side of arrowhead
            (
                center_x - head_half_width,
                head_bottom,
            ),
        ]

        draw.polygon(
            arrow_points,
            fill=green,
            outline=outline,
            width=max(
                1,
                int(badge_width * 0.05),
            ),
        )
    return image


def toggle_logging(icon, item):
    if logging_enabled:
        stop_logging()
    else:
        start_logging()

    icon.update_menu()


def open_log_folder(icon, item):
    """
    Open the directory containing Mouse Gravity logs
    in Windows File Explorer.
    """
    log_directory = get_log_directory()

    os.startfile(log_directory)


def update_tray_status():
    """
    Update the tray icon's title and icon based on the current boost state.
    """
    if tray_icon is None:
        return

    with state_lock:
        boost_active = lateral_boost

    boost_state = "ON" if boost_active else "OFF"

    tray_icon.title = f"Mouse Gravity: ACTIVE | Boost: {boost_state}"

    tray_icon.icon = create_vortex_icon(boost_active=boost_active)


# ------------------------------------------------------------
# Shutdown
# ------------------------------------------------------------


def shutdown():
    global click_timer

    if not running.is_set():
        return

    if logging_enabled:
        logger.info("SHUTDOWN | beginning shutdown")

    running.clear()

    with click_lock:
        if click_timer is not None:
            click_timer.cancel()
            click_timer = None

    if tray_icon is not None:
        tray_icon.stop()


def tray_exit(icon, item):
    """
    Callback function for the "Exit" menu item in the tray icon's context menu.
    Args:
        icon (pystray.Icon): The tray icon object.
        item (pystray.MenuItem): The menu item that was clicked.
    """
    logger.info("EXIT | tray menu")
    shutdown()


# ------------------------------------------------------------
# Click handling
# ------------------------------------------------------------


def process_click_sequence(x, y):
    """
    Process the click sequence based on the number of clicks detected.

    Args:
        x (int): The x-coordinate of the mouse click.
        y (int): The y-coordinate of the mouse click.
    """
    global click_count
    global lateral_boost
    global target
    global orbit_direction
    global click_timer
    global velocity_x
    global velocity_y

    with click_lock:
        count = click_count
        click_count = 0
        click_timer = None

    if not running.is_set():
        return

    # --------------------------------------------------------
    # Single click
    #
    # Toggle lateral boost.
    # --------------------------------------------------------

    if count == 1:

        with state_lock:
            lateral_boost = not lateral_boost
            boost_state = lateral_boost

        state = "ON" if boost_state else "OFF"

        print(f"Lateral boost: {state}")

        logger.info(
            "BOOST | state=%s",
            state,
        )

        update_tray_status()

    # --------------------------------------------------------
    # Double click
    #
    # Assign a new gravity target.
    # --------------------------------------------------------

    elif count == 2:

        with state_lock:
            target = (x, y)

        logger.info(
            "TARGET | x=%s | y=%s",
            x,
            y,
        )

        current_x, current_y = controller.position

        dx = x - current_x
        dy = y - current_y

        distance = math.hypot(dx, dy)

        if distance > 0:

            radial_x = dx / distance
            radial_y = dy / distance

            tangent_x = -radial_y
            tangent_y = radial_x

            tangent_velocity = velocity_x * tangent_x + velocity_y * tangent_y

            with state_lock:
                orbit_direction = -1 if tangent_velocity < 0 else 1

        print(f"New target: {(x, y)}")

    # --------------------------------------------------------
    # Triple click
    #
    # Remove target.
    # --------------------------------------------------------

    elif count == 3:

        target = None
        velocity_x = 0.0
        velocity_y = 0.0
        orbit_direction = 0

        logger.info("REMOVE TARGET | triple click detected")

        print("Target removed.")


def on_click(x, y, button, pressed):
    """
    Callback function for mouse click events.

    Args:
        x (int): The x-coordinate of the mouse click.
        y (int): The y-coordinate of the mouse click.
        button (pynput.mouse.Button): The mouse button that was clicked.
        pressed (bool): True if the button was pressed, False if released.
    """
    global click_count
    global last_click_time
    global click_timer

    if not pressed:
        return

    now = time.perf_counter()
    should_exit = False

    with click_lock:

        if now - last_click_time > CLICK_SEQUENCE_TIMEOUT:
            click_count = 0

        click_count += 1
        last_click_time = now

        if click_timer is not None:
            click_timer.cancel()
            click_timer = None

        # Quadruple click
        if click_count >= 4:
            click_count = 0
            should_exit = True

        else:
            click_timer = threading.Timer(
                CLICK_SEQUENCE_TIMEOUT,
                process_click_sequence,
                args=(x, y),
            )

            click_timer.daemon = True
            click_timer.start()

    # IMPORTANT:
    # shutdown() must happen AFTER releasing click_lock.
    if should_exit:

        logger.info("EXIT | quadruple click detected")

        print("Quadruple click detected. Exiting.")
        shutdown()
        return False


# ------------------------------------------------------------
# Mouse physics
# ------------------------------------------------------------


def gravity_loop():
    """
    Main loop for simulating mouse gravity physics.
    This function runs in a separate thread and continuously updates the mouse cursor's position
    based on the current target, user input, and physics parameters.
    """
    global velocity_x
    global velocity_y

    previous_time = time.perf_counter()

    expected_x, expected_y = controller.position

    telemetry_interval = (
        1.0 / LOG_TELEMETRY_HZ
        if LOG_TELEMETRY_HZ > 0
        else None
    )

    last_telemetry_time = time.perf_counter()


    while running.is_set():

        current_time = time.perf_counter()

        dt = current_time - previous_time
        previous_time = current_time

        dt = min(dt, 0.05)

        with state_lock:
            current_target = target
            boost_active = lateral_boost

        # ----------------------------------------------------
        # Detect physical mouse input
        # ----------------------------------------------------

        actual_x, actual_y = controller.position

        user_dx = actual_x - expected_x
        user_dy = actual_y - expected_y

        if current_target is not None:

            target_x, target_y = current_target

            dx = target_x - actual_x
            dy = target_y - actual_y

            distance = math.hypot(dx, dy)

            if distance > STOP_RADIUS:

                radial_x = dx / distance
                radial_y = dy / distance

                # ------------------------------------------------
                # Distance-dependent gravity
                #
                # Gravity becomes stronger as the cursor gets
                # closer to the target.
                # ------------------------------------------------

                gravity_distance = max(
                    distance,
                    MIN_GRAVITY_DISTANCE,
                )

                gravity_strength = (
                    GRAVITY
                    * (REFERENCE_DISTANCE / gravity_distance) ** GRAVITY_DISTANCE_POWER
                )

                gravity_strength = min(
                    gravity_strength,
                    MAX_GRAVITY_ACCELERATION,
                )

                acceleration_x = radial_x * gravity_strength
                acceleration_y = radial_y * gravity_strength

                velocity_x += acceleration_x * dt
                velocity_y += acceleration_y * dt

                # ------------------------------------------------
                # User movement
                # ------------------------------------------------

                # Radial unit vector points toward the target.
                radial_x = dx / distance
                radial_y = dy / distance

                # Tangent is perpendicular to the radial direction.
                tangent_x = -radial_y
                tangent_y = radial_x

                # ------------------------------------------------
                # Split physical mouse movement into:
                #
                # 1. radial movement
                # 2. tangential movement
                # ------------------------------------------------

                radial_input = user_dx * radial_x + user_dy * radial_y

                tangential_input = user_dx * tangent_x + user_dy * tangent_y

                # ------------------------------------------------
                # Radial input
                #
                # Positive radial_input means the user moved
                # toward the target.
                #
                # Negative means the user moved away.
                # ------------------------------------------------

                if radial_input >= 0:
                    radial_strength = NORMAL_INPUT_STRENGTH * TOWARD_INPUT_MULTIPLIER

                else:
                    radial_strength = NORMAL_INPUT_STRENGTH * AWAY_INPUT_MULTIPLIER

                velocity_x += radial_x * radial_input * radial_strength

                velocity_y += radial_y * radial_input * radial_strength

                # ------------------------------------------------
                # Tangential input
                #
                # Lateral boost only amplifies actual sideways
                # mouse movement.
                # ------------------------------------------------

                tangential_strength = NORMAL_INPUT_STRENGTH

                if boost_active:
                    tangential_strength *= LATERAL_BOOST_MULTIPLIER

                velocity_x += tangent_x * tangential_input * tangential_strength

                velocity_y += tangent_y * tangential_input * tangential_strength

                # ------------------------------------------------
                # Drag
                # ------------------------------------------------

                velocity_x *= DRAG
                velocity_y *= DRAG

                # ------------------------------------------------
                # Maximum speed
                # ------------------------------------------------

                speed = math.hypot(
                    velocity_x,
                    velocity_y,
                )

                if speed > MAX_SPEED:

                    scale = MAX_SPEED / speed

                    velocity_x *= scale
                    velocity_y *= scale

                # ------------------------------------------------
                # Proposed movement
                # ------------------------------------------------

                new_x = actual_x + velocity_x * dt

                new_y = actual_y + velocity_y * dt

                # ------------------------------------------------
                # Logging
                # ------------------------------------------------

                if (
                    logging_enabled
                    and telemetry_interval is not None
                    and current_time - last_telemetry_time >= telemetry_interval
                ):
                    last_telemetry_time = current_time

                    speed = math.hypot(
                        velocity_x,
                        velocity_y,
                    )

                    logger.debug(
                        "PHYSICS | "
                        "cursor=(%.1f, %.1f) | "
                        "target=(%.1f, %.1f) | "
                        "distance=%.2f | "
                        "gravity=%.2f | "
                        "velocity=(%.2f, %.2f) | "
                        "speed=%.2f | "
                        "user_input=(%.2f, %.2f) | "
                        "radial_input=%.2f | "
                        "tangential_input=%.2f | "
                        "boost=%s",
                        actual_x,
                        actual_y,
                        target_x,
                        target_y,
                        distance,
                        gravity_strength,
                        velocity_x,
                        velocity_y,
                        speed,
                        user_dx,
                        user_dy,
                        radial_input,
                        tangential_input,
                        boost_active,
                    )

                # ------------------------------------------------
                # Virtual desktop edge collisions
                # ------------------------------------------------

                if new_x <= SCREEN_LEFT:
                    new_x = SCREEN_LEFT

                    if velocity_x < 0:
                        logger.info(
                            "COLLISION | wall=LEFT | " "lost_velocity_x=%.2f",
                            velocity_x,
                        )

                        velocity_x = 0.0

                elif new_x >= SCREEN_RIGHT:
                    new_x = SCREEN_RIGHT

                    if velocity_x > 0:
                        logger.info(
                            "COLLISION | wall=RIGHT | " "lost_velocity_x=%.2f",
                            velocity_x,
                        )

                        velocity_x = 0.0

                if new_y <= SCREEN_TOP:
                    new_y = SCREEN_TOP

                    if velocity_y < 0:
                        logger.info(
                            "COLLISION | wall=TOP | " "lost_velocity_y=%.2f",
                            velocity_y,
                        )

                        velocity_y = 0.0

                elif new_y >= SCREEN_BOTTOM:
                    new_y = SCREEN_BOTTOM

                    if velocity_y > 0:
                        logger.info(
                            "COLLISION | wall=BOTTOM | " "lost_velocity_y=%.2f",
                            velocity_y,
                        )

                        velocity_y = 0.0

                controller.position = (
                    round(new_x),
                    round(new_y),
                )

                expected_x, expected_y = controller.position

            else:

                velocity_x = 0.0
                velocity_y = 0.0

                controller.position = current_target

                expected_x, expected_y = controller.position

        else:
            expected_x, expected_y = controller.position

        time.sleep(1 / FPS)


# ------------------------------------------------------------
# Main
# ------------------------------------------------------------


def main():
    """
    Main function to start the Mouse Gravity program.
    This function initializes the mouse listener, starts the gravity loop in a separate thread,
    and creates the system tray icon.
    """
    global tray_icon
    global listener

    if LOGGING_ENABLED_BY_DEFAULT:
        start_logging()

    print(
        "Mouse Gravity started. \nSingle click to toggle lateral boost \nDouble click to set a target \nTriple click to remove target \nQuadruple click to exit."
    )
    listener = mouse.Listener(on_click=on_click)

    listener.start()

    physics_thread = threading.Thread(
        target=gravity_loop,
        daemon=True,
    )

    physics_thread.start()

    tray_icon = pystray.Icon(
        "mouse_gravity",
        create_vortex_icon(boost_active=False),
        "Mouse Gravity: ACTIVE | Boost: OFF",
        menu=pystray.Menu(
            pystray.MenuItem(
                "Mouse Gravity: ACTIVE",
                lambda: None,
                enabled=False,
            ),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem(
                "Enable Logging",
                toggle_logging,
                checked=lambda item: logging_enabled,
            ),
            pystray.MenuItem(
                "Open Log Folder",
                open_log_folder,
            ),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem(
                "Exit",
                tray_exit,
            ),
        ),
    )

    try:
        tray_icon.run()

    finally:
        running.clear()

        if listener is not None:
            listener.stop()
            listener.join(timeout=1)

        if logging_enabled:
            logger.info("SHUTDOWN | complete")
            stop_logging()

        print("Mouse Gravity stopped.")


if __name__ == "__main__":
    main()