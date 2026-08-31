"""
Runtime application for the gravity-point N-body simulation.

Mouse input is used only to:

- Double-click to place a gravity point.
- Triple-click to clear all gravity points.
- Quadruple-click to exit.
- Position N-body placement presets.

The application never programmatically moves the mouse cursor.
"""

import ctypes

# DPI awareness must be initialized before display-dependent modules.
try:
    ctypes.windll.user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))
except Exception:
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
    except Exception:
        ctypes.windll.user32.SetProcessDPIAware()

from ctypes import wintypes
from datetime import datetime
from pathlib import Path

import logging
import math
import os
import random
import threading
import time
import tkinter as tk

import pystray
from PIL import Image, ImageDraw
from pynput import mouse

from config import MAX_GRAVITY_POINTS, config
from gravity import GravityPoint, update_gravity_points
from settings_window import SettingsWindow


# ------------------------------------------------------------
# Shared state
# ------------------------------------------------------------

# Points are stored oldest-to-newest.
gravity_points: list[GravityPoint] = []

# True only when the newest point was manually placed.
# Placement presets begin with no biased point.
place_bias_active = False

click_count = 0
last_click_time = 0.0
click_timer = None

click_lock = threading.Lock()
state_lock = threading.Lock()

running = threading.Event()
running.set()

physics_wake_event = threading.Event()

# Used only to READ the cursor position.
controller = mouse.Controller()

tray_icon = None
listener = None

tk_root = None
settings_ui = None

last_frame_error = ""


# ------------------------------------------------------------
# Marker state
# ------------------------------------------------------------

target_markers = []
target_marker_visible = []
target_marker_positions = []

MARKER_SIZE = 12
MARKER_COLOR = "#00ff00"
MARKER_TRANSPARENT_COLOR = "#010101"

MARKER_REFRESH_MS = 33

IDLE_PHYSICS_HZ = 10.0
IDLE_PHYSICS_INTERVAL = 1.0 / IDLE_PHYSICS_HZ


# ------------------------------------------------------------
# Logging
# ------------------------------------------------------------

logging_enabled = False
log_handler = None
log_path = None

logging_lock = threading.Lock()

logger = logging.getLogger("nbody_gravity")
logger.setLevel(logging.DEBUG)
logger.propagate = False


def get_log_directory() -> Path:
    """
    Return the application's log directory.

    The directory is created beside this script if it does not exist.

    Returns:
        Path to the log directory.
    """
    log_directory = Path(__file__).resolve().parent / "logs"

    log_directory.mkdir(
        parents=True,
        exist_ok=True,
    )

    return log_directory


def start_logging() -> None:
    """
    Start logging to a timestamped file.

    Calling this function while logging is already enabled has no effect.
    """
    global logging_enabled
    global log_handler
    global log_path

    with logging_lock:
        if log_handler is not None:
            return

        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")

        log_path = get_log_directory() / f"nbody_gravity_{timestamp}.log"

        log_handler = logging.FileHandler(
            log_path,
            encoding="utf-8",
        )

        log_handler.setLevel(logging.DEBUG)

        log_handler.setFormatter(
            logging.Formatter(
                "%(asctime)s.%(msecs)03d | " "%(levelname)-8s | " "%(message)s",
                datefmt="%Y-%m-%d %H:%M:%S",
            )
        )

        logger.addHandler(log_handler)

        logging_enabled = True

    logger.info("LOGGING | enabled")

    log_configuration()

    print(f"Logging enabled: {log_path}")


def stop_logging() -> None:
    """
    Stop logging and close the current log file.
    """
    global logging_enabled
    global log_handler

    with logging_lock:
        if log_handler is None:
            logging_enabled = False
            return

        logger.info("LOGGING | disabled")

        handler = log_handler

        logger.removeHandler(handler)

        handler.flush()
        handler.close()

        log_handler = None
        logging_enabled = False

    print("Logging disabled.")


def log_configuration() -> None:
    """
    Write the current simulation configuration to the log.
    """
    logger.info("N-Body Gravity started")

    logger.info(
        "CONFIG | "
        "point_gravity=%s | "
        "reference_distance=%s | "
        "gravity_distance_power=%s | "
        "min_gravity_distance=%s | "
        "max_gravity_acceleration=%s | "
        "body_stop_radius=%s",
        config.point_gravity,
        config.reference_distance,
        config.gravity_distance_power,
        config.min_gravity_distance,
        config.max_gravity_acceleration,
        config.body_stop_radius,
    )

    logger.info(
        "CONFIG | " "last_placed_boost=%s | " "last_placed_drag=%s",
        config.last_placed_boost,
        config.last_placed_drag,
    )

    logger.info(
        "CONFIG | "
        "multi_point_count=%s | "
        "point_drag=%s | "
        "point_max_speed=%s | "
        "point_physics_hz=%s",
        config.multi_point_count,
        config.point_drag,
        config.point_max_speed,
        config.point_physics_hz,
    )

    logger.info(
        "CONFIG | "
        "triangle_spawn_radius=%s | "
        "pentagram_spawn_radius=%s | "
        "random_spawn_radius=%s | "
        "random_spawn_number=%s | "
        "n_body_spawn_delay=%s",
        config.triangle_spawn_radius,
        config.pentagram_spawn_radius,
        config.random_spawn_radius,
        config.random_spawn_number,
        config.n_body_spawn_delay,
    )


def log_candidate_preset(
    preset_name: str,
    values: dict,
) -> None:
    """
    Save a user-created preset to the log for later review.

    Args:
        preset_name:
            User-selected preset name.

        values:
            Mapping of config fields to their proposed values.
    """
    if not logging_enabled:
        start_logging()

    logger.info(
        "USER_PRESET_BEGIN | name=%s",
        preset_name,
    )

    for field_name, value in values.items():
        logger.info(
            "USER_PRESET_VALUE | " "name=%s | " "%s=%s",
            preset_name,
            field_name,
            value,
        )

    logger.info(
        "USER_PRESET_END | name=%s",
        preset_name,
    )


# ------------------------------------------------------------
# Virtual desktop
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

SCREEN_BOUNDS = (
    SCREEN_LEFT,
    SCREEN_TOP,
    SCREEN_RIGHT,
    SCREEN_BOTTOM,
)

print(
    "Virtual desktop: "
    f"{SCREEN_LEFT}, {SCREEN_TOP} -> "
    f"{SCREEN_RIGHT}, {SCREEN_BOTTOM}"
)


# ------------------------------------------------------------
# Win32 marker functions
# ------------------------------------------------------------

GET_ANCESTOR = user32.GetAncestor
GET_ANCESTOR.argtypes = [
    wintypes.HWND,
    wintypes.UINT,
]
GET_ANCESTOR.restype = wintypes.HWND

SET_WINDOW_POS = user32.SetWindowPos
SET_WINDOW_POS.argtypes = [
    wintypes.HWND,
    wintypes.HWND,
    ctypes.c_int,
    ctypes.c_int,
    ctypes.c_int,
    ctypes.c_int,
    wintypes.UINT,
]
SET_WINDOW_POS.restype = wintypes.BOOL

GET_WINDOW_LONG = user32.GetWindowLongW
GET_WINDOW_LONG.argtypes = [
    wintypes.HWND,
    ctypes.c_int,
]
GET_WINDOW_LONG.restype = ctypes.c_long

SET_WINDOW_LONG = user32.SetWindowLongW
SET_WINDOW_LONG.argtypes = [
    wintypes.HWND,
    ctypes.c_int,
    ctypes.c_long,
]
SET_WINDOW_LONG.restype = ctypes.c_long

GA_ROOT = 2

GWL_EXSTYLE = -20

WS_EX_TRANSPARENT = 0x00000020
WS_EX_TOOLWINDOW = 0x00000080

HWND_TOPMOST = wintypes.HWND(-1)

SWP_NOACTIVATE = 0x0010
SWP_SHOWWINDOW = 0x0040


# ------------------------------------------------------------
# Gravity-point state
# ------------------------------------------------------------


def clear_gravity_points() -> None:
    """
    Remove all active gravity points and disable placement bias.
    """
    global place_bias_active

    with state_lock:
        gravity_points.clear()
        place_bias_active = False

    physics_wake_event.set()

    if logging_enabled:
        logger.info("GRAVITY_POINTS | cleared")

        logger.info("PLACE_BIAS | " "active=False | " "reason=points_cleared")

    print("Gravity points cleared.")


def get_point_status() -> tuple[int, int]:
    """
    Return the current point count and configured point limit.

    Returns:
        Tuple containing points placed and maximum allowed points.
    """
    with state_lock:
        return (
            len(gravity_points),
            min(
                config.multi_point_count,
                MAX_GRAVITY_POINTS,
            ),
        )


def replace_gravity_points(
    points: list[GravityPoint],
    preset_name: str,
) -> None:
    """
    Replace the current simulation with a preset point group.

    Placement bias is disabled because preset-generated points should
    initially have equal influence.

    Args:
        points:
            New gravity-point list.

        preset_name:
            Preset name used for logging.
    """
    global place_bias_active

    with state_lock:
        gravity_points.clear()
        gravity_points.extend(points)

        place_bias_active = False

    physics_wake_event.set()

    if logging_enabled:
        logger.info(
            "PLACE_BIAS | " "active=False | " "reason=preset_spawn | " "preset=%s",
            preset_name,
        )


# ------------------------------------------------------------
# Target markers
# ------------------------------------------------------------


def _get_marker_hwnd(marker):
    """
    Return the native root window handle for a Tkinter marker.
    """
    marker.update_idletasks()

    client_hwnd = marker.winfo_id()

    root_hwnd = GET_ANCESTOR(
        client_hwnd,
        GA_ROOT,
    )

    return root_hwnd if root_hwnd else client_hwnd


def _make_marker_click_through(
    marker,
) -> None:
    """
    Make a marker ignore mouse input.
    """
    hwnd = _get_marker_hwnd(marker)

    style = GET_WINDOW_LONG(
        hwnd,
        GWL_EXSTYLE,
    )

    SET_WINDOW_LONG(
        hwnd,
        GWL_EXSTYLE,
        style | WS_EX_TRANSPARENT | WS_EX_TOOLWINDOW,
    )


def _create_target_marker():
    """
    Create one transparent, click-through gravity-point marker.
    """
    marker = tk.Toplevel(tk_root)

    marker.withdraw()
    marker.overrideredirect(True)
    marker.attributes(
        "-topmost",
        True,
    )

    marker.configure(bg=MARKER_TRANSPARENT_COLOR)

    marker.wm_attributes(
        "-transparentcolor",
        MARKER_TRANSPARENT_COLOR,
    )

    canvas = tk.Canvas(
        marker,
        width=MARKER_SIZE,
        height=MARKER_SIZE,
        bg=MARKER_TRANSPARENT_COLOR,
        highlightthickness=0,
        bd=0,
    )

    canvas.pack()

    canvas.create_oval(
        1,
        1,
        MARKER_SIZE - 1,
        MARKER_SIZE - 1,
        fill=MARKER_COLOR,
        outline=MARKER_COLOR,
    )

    marker.geometry(f"{MARKER_SIZE}x" f"{MARKER_SIZE}+0+0")

    # Windows must create the native window before its extended
    # styles can be changed.
    marker.deiconify()
    marker.update_idletasks()

    _make_marker_click_through(marker)

    marker.withdraw()

    return marker


def _ensure_marker_count(
    required_count: int,
) -> None:
    """
    Ensure enough marker windows exist for all gravity points.
    """
    required_count = min(
        required_count,
        MAX_GRAVITY_POINTS,
    )

    while len(target_markers) < required_count:
        target_markers.append(_create_target_marker())

        target_marker_visible.append(False)

        target_marker_positions.append(None)


def _show_or_move_marker(
    index: int,
    x: float,
    y: float,
) -> None:
    """
    Display or reposition one marker.
    """
    marker_x = round(x - MARKER_SIZE / 2)

    marker_y = round(y - MARKER_SIZE / 2)

    position = (
        marker_x,
        marker_y,
    )

    if target_marker_visible[index] and target_marker_positions[index] == position:
        return

    marker = target_markers[index]

    if not target_marker_visible[index]:
        marker.deiconify()
        marker.update_idletasks()

        target_marker_visible[index] = True

    SET_WINDOW_POS(
        _get_marker_hwnd(marker),
        HWND_TOPMOST,
        marker_x,
        marker_y,
        MARKER_SIZE,
        MARKER_SIZE,
        SWP_NOACTIVATE | SWP_SHOWWINDOW,
    )

    target_marker_positions[index] = position


def _hide_marker(
    index: int,
) -> None:
    """
    Hide one currently visible marker.
    """
    if not target_marker_visible[index]:
        return

    target_markers[index].withdraw()

    target_marker_visible[index] = False

    target_marker_positions[index] = None


def update_target_markers() -> None:
    """
    Refresh marker positions at the visual update rate.
    """
    if tk_root is None or not running.is_set():
        return

    with state_lock:
        positions = tuple((point.x, point.y) for point in gravity_points)

    _ensure_marker_count(len(positions))

    for index, position in enumerate(positions):
        _show_or_move_marker(
            index,
            *position,
        )

    for index in range(
        len(positions),
        len(target_markers),
    ):
        _hide_marker(index)

    try:
        tk_root.after(
            MARKER_REFRESH_MS,
            update_target_markers,
        )

    except tk.TclError:
        pass


def destroy_target_markers() -> None:
    """
    Destroy every marker window.
    """
    for marker in target_markers:
        try:
            marker.destroy()

        except tk.TclError:
            pass

    target_markers.clear()
    target_marker_visible.clear()
    target_marker_positions.clear()


# ------------------------------------------------------------
# Tray icon
# ------------------------------------------------------------


def create_vortex_icon(
    size: int = 64,
) -> Image.Image:
    """
    Create the vortex-style system tray icon.

    Args:
        size:
            Icon width and height.

    Returns:
        Generated PIL image.
    """
    image = Image.new(
        "RGBA",
        (size, size),
        (15, 5, 25, 255),
    )

    draw = ImageDraw.Draw(image)

    center_x = size / 2
    center_y = size / 2

    for arm in range(4):
        points = []

        arm_offset = arm * math.pi / 2

        for index in range(120):
            t = index / 119

            angle = arm_offset + t * math.pi * 3.5

            radius = size * 0.42 * (1 - t) + 2

            points.append(
                (
                    center_x + math.cos(angle) * radius,
                    center_y + math.sin(angle) * radius,
                )
            )

        draw.line(
            points,
            fill=(
                90 + arm * 20,
                20,
                150,
                255,
            ),
            width=3,
        )

    center_radius = size * 0.10

    draw.ellipse(
        (
            center_x - center_radius,
            center_y - center_radius,
            center_x + center_radius,
            center_y + center_radius,
        ),
        fill=(
            5,
            0,
            10,
            255,
        ),
    )

    return image


def toggle_logging(
    icon,
    item,
) -> None:
    """
    Toggle logging from the tray menu.
    """
    if logging_enabled:
        stop_logging()
    else:
        start_logging()

    icon.update_menu()


def open_log_folder(
    icon,
    item,
) -> None:
    """
    Open the log directory in Windows Explorer.
    """
    os.startfile(get_log_directory())


def show_settings_window(
    icon=None,
    item=None,
) -> None:
    """
    Display the Tkinter settings window.
    """
    if tk_root is None or settings_ui is None:
        return

    tk_root.after(
        0,
        settings_ui.show,
    )


# ------------------------------------------------------------
# Shutdown
# ------------------------------------------------------------


def shutdown() -> None:
    """
    Stop all application components.
    """
    global click_timer

    if not running.is_set():
        return

    if logging_enabled:
        logger.info("SHUTDOWN | beginning shutdown")

    running.clear()
    physics_wake_event.set()

    with click_lock:
        if click_timer is not None:
            click_timer.cancel()
            click_timer = None

    if tray_icon is not None:
        tray_icon.stop()

    if tk_root is not None:
        try:
            tk_root.after(
                0,
                destroy_target_markers,
            )

            tk_root.after(
                0,
                tk_root.destroy,
            )

        except tk.TclError:
            pass


def tray_exit(
    icon,
    item,
) -> None:
    """
    Exit from the tray menu.
    """
    if logging_enabled:
        logger.info("EXIT | tray menu")

    shutdown()


# ------------------------------------------------------------
# Placement presets
# ------------------------------------------------------------


def _radial_points(
    center_x: float,
    center_y: float,
    radius: float,
    count: int,
) -> list[GravityPoint]:
    """
    Create evenly spaced points around a center position.

    Args:
        center_x:
            Center X coordinate.

        center_y:
            Center Y coordinate.

        radius:
            Distance from the center to each point.

        count:
            Number of points.

    Returns:
        Generated gravity points.
    """
    start_angle = -math.pi / 2

    return [
        GravityPoint(
            x=(center_x + math.cos(angle) * radius),
            y=(center_y + math.sin(angle) * radius),
        )
        for index in range(count)
        for angle in [start_angle + index * (2 * math.pi / count)]
    ]


def spawn_triangle_preset() -> None:
    """
    Spawn an equilateral triangle around the current cursor position.
    """
    cursor_x, cursor_y = controller.position

    radius = config.triangle_spawn_radius

    replace_gravity_points(
        _radial_points(
            cursor_x,
            cursor_y,
            radius,
            3,
        ),
        "triangle",
    )

    if logging_enabled:
        logger.info(
            "N_BODY_PRESET | " "preset=triangle | " "radius=%s",
            radius,
        )

    print(f"Spawned triangle preset at radius {radius}.")


def spawn_pentagram_preset() -> None:
    """
    Spawn five equally spaced points around the current cursor position.
    """
    cursor_x, cursor_y = controller.position

    radius = config.pentagram_spawn_radius

    replace_gravity_points(
        _radial_points(
            cursor_x,
            cursor_y,
            radius,
            5,
        ),
        "pentagram",
    )

    if logging_enabled:
        logger.info(
            "N_BODY_PRESET | " "preset=pentagram | " "radius=%s",
            radius,
        )

    print(f"Spawned pentagram preset at radius {radius}.")


def spawn_random_point_preset() -> None:
    """
    Spawn randomly positioned points around the current cursor.

    Each point is placed at ``random_spawn_radius`` from the cursor.
    """
    cursor_x, cursor_y = controller.position

    radius = config.random_spawn_radius

    points = []

    for _ in range(config.random_spawn_number):
        angle = 2 * math.pi * random.random()

        points.append(
            GravityPoint(
                x=(cursor_x + radius * math.cos(angle)),
                y=(cursor_y + radius * math.sin(angle)),
            )
        )

    replace_gravity_points(
        points,
        "random",
    )

    if logging_enabled:
        logger.info(
            "N_BODY_PRESET | " "preset=random | " "radius=%s | " "count=%s",
            radius,
            len(points),
        )

    print("Spawned random points preset " f"at radius {radius}.")


# ------------------------------------------------------------
# Click handling
# ------------------------------------------------------------


def process_click_sequence(
    x: float,
    y: float,
) -> None:
    """
    Resolve a completed click sequence.

    Double-click:
        Place a gravity point.

    Triple-click:
        Clear all gravity points.

    Args:
        x:
            Click X coordinate.

        y:
            Click Y coordinate.
    """
    global click_count
    global click_timer
    global place_bias_active

    with click_lock:
        count = click_count

        click_count = 0
        click_timer = None

    if not running.is_set():
        return

    if count == 2:
        with state_lock:
            point_limit = min(
                config.multi_point_count,
                MAX_GRAVITY_POINTS,
            )

            removed_point = None

            if len(gravity_points) >= point_limit:
                removed_point = gravity_points.pop(0)

            gravity_points.append(
                GravityPoint(
                    x=float(x),
                    y=float(y),
                )
            )

            # The newest manually placed point becomes biased.
            place_bias_active = True

            point_number = len(gravity_points)

        if removed_point is not None and logging_enabled:
            logger.info(
                "GRAVITY_POINT | " "oldest_removed=%s",
                removed_point,
            )

        if logging_enabled:
            logger.info(
                "GRAVITY_POINT | " "number=%s | " "x=%.2f | " "y=%.2f",
                point_number,
                x,
                y,
            )

            logger.info(
                "PLACE_BIAS | " "active=True | " "point_index=%s",
                point_number - 1,
            )

        print("Gravity point " f"{point_number}/" f"{point_limit}: " f"{(x, y)}")

        physics_wake_event.set()

    elif count == 3:
        clear_gravity_points()


def on_click(
    x,
    y,
    button,
    pressed,
):
    """
    Track mouse clicks and recognize multi-click commands.

    Args:
        x:
            Mouse X coordinate.

        y:
            Mouse Y coordinate.

        button:
            Pynput mouse button.

        pressed:
            True for button press and False for release.

    Returns:
        False when quadruple-click shutdown is triggered.
    """
    global click_count
    global last_click_time
    global click_timer

    if not pressed:
        return

    now = time.perf_counter()
    should_exit = False

    with click_lock:
        if now - last_click_time > config.click_sequence_timeout:
            click_count = 0

        click_count += 1
        last_click_time = now

        if click_timer is not None:
            click_timer.cancel()
            click_timer = None

        if click_count >= 4:
            click_count = 0
            should_exit = True

        else:
            click_timer = threading.Timer(
                config.click_sequence_timeout,
                process_click_sequence,
                args=(
                    x,
                    y,
                ),
            )

            click_timer.daemon = True
            click_timer.start()

    if should_exit:
        if logging_enabled:
            logger.info("EXIT | " "quadruple click detected")

        print("Quadruple click detected. Exiting.")

        shutdown()

        return False


# ------------------------------------------------------------
# Physics
# ------------------------------------------------------------


def _create_telemetry_snapshot():
    """
    Create an immutable snapshot of the current point state.

    The caller must hold ``state_lock``.

    Returns:
        Tuple containing point telemetry records.
    """
    biased_index = (
        len(gravity_points) - 1 if (place_bias_active and gravity_points) else None
    )

    return tuple(
        (
            index,
            point.x,
            point.y,
            point.velocity_x,
            point.velocity_y,
            index == biased_index,
        )
        for index, point in enumerate(gravity_points)
    )


def _log_telemetry(
    snapshot,
) -> None:
    """
    Write a point-state snapshot to the debug log.

    Args:
        snapshot:
            Snapshot returned by ``_create_telemetry_snapshot``.
    """
    for (
        index,
        x,
        y,
        velocity_x,
        velocity_y,
        biased,
    ) in snapshot:

        logger.debug(
            "POINT_TELEMETRY | "
            "index=%s | "
            "x=%.2f | "
            "y=%.2f | "
            "vx=%.2f | "
            "vy=%.2f | "
            "speed=%.2f | "
            "biased=%s",
            index,
            x,
            y,
            velocity_x,
            velocity_y,
            math.hypot(
                velocity_x,
                velocity_y,
            ),
            biased,
        )


def gravity_loop() -> None:
    """
    Advance gravity points under mutual attraction.

    Physics runs at ``config.point_physics_hz`` whenever at least two
    points exist. With fewer points, the thread uses a lower idle rate.

    Point telemetry is copied while holding ``state_lock`` and logged only
    after releasing the lock, preventing file I/O from blocking physics
    state access.

    Five consecutive physics errors trigger application shutdown.
    """
    global last_frame_error

    previous_time = time.perf_counter()

    last_telemetry_time = previous_time

    consecutive_errors = 0

    while running.is_set():
        frame_start = time.perf_counter()

        dt = min(
            frame_start - previous_time,
            0.1,
        )

        previous_time = frame_start

        point_count = 0
        telemetry_snapshot = None

        try:
            with state_lock:
                point_limit = min(
                    config.multi_point_count,
                    MAX_GRAVITY_POINTS,
                )

                excess_points = len(gravity_points) - point_limit

                if excess_points > 0:
                    del gravity_points[:excess_points]

                point_count = len(gravity_points)

                if point_count >= 2:
                    removed_point = update_gravity_points(
                        gravity_points,
                        dt,
                        SCREEN_BOUNDS,
                        place_bias=place_bias_active,
                    )

                    if removed_point is not None and logging_enabled:
                        logger.info(
                            "GRAVITY_POINT | " "merged_oldest_removed=%s",
                            removed_point,
                        )

                telemetry_hz = config.log_telemetry_hz

                if (
                    logging_enabled
                    and telemetry_hz > 0
                    and (frame_start - last_telemetry_time) >= (1.0 / telemetry_hz)
                ):
                    telemetry_snapshot = _create_telemetry_snapshot()

                    last_telemetry_time = frame_start

            # Log only after releasing the shared-state lock.
            if telemetry_snapshot is not None:
                _log_telemetry(telemetry_snapshot)

            consecutive_errors = 0
            last_frame_error = ""

        except Exception as exc:
            consecutive_errors += 1

            if last_frame_error != str(exc):
                print(f"Physics error: {exc}")

            last_frame_error = str(exc)

            if logging_enabled:
                logger.error(
                    "PHYSICS_ERROR | %s",
                    exc,
                    exc_info=True,
                )

            if consecutive_errors >= 5:
                print("Too many consecutive " "physics errors. Exiting.")

                shutdown()
                break

        elapsed = time.perf_counter() - frame_start

        if point_count >= 2:
            frame_interval = 1.0 / max(
                config.point_physics_hz,
                1.0,
            )

        else:
            frame_interval = IDLE_PHYSICS_INTERVAL

        wait_time = max(
            0.0,
            frame_interval - elapsed,
        )

        if wait_time > 0 and running.is_set():
            physics_wake_event.wait(wait_time)

            physics_wake_event.clear()


# ------------------------------------------------------------
# Main
# ------------------------------------------------------------


def main() -> None:
    """
    Initialize and run the N-body gravity application.
    """
    global tray_icon
    global listener
    global tk_root
    global settings_ui

    # --------------------------------------------------------
    # Logging
    # --------------------------------------------------------

    try:
        if config.logging_enabled_by_default:
            start_logging()

    except Exception as exc:
        print("Error during logging startup: " f"{exc}")

    # --------------------------------------------------------
    # Mouse listener
    # --------------------------------------------------------

    try:
        listener = mouse.Listener(
            on_click=on_click,
        )

        listener.start()

    except Exception as exc:
        print("Error during mouse listener startup: " f"{exc}")

    # --------------------------------------------------------
    # Physics thread
    # --------------------------------------------------------

    try:
        physics_thread = threading.Thread(
            target=gravity_loop,
            daemon=True,
            name="NBodyGravityPhysics",
        )

        physics_thread.start()

    except Exception as exc:
        print("Error during physics startup: " f"{exc}")

    # --------------------------------------------------------
    # Tkinter
    # --------------------------------------------------------

    try:
        tk_root = tk.Tk()
        tk_root.withdraw()

        settings_ui = SettingsWindow(
            root=tk_root,
            state_lock=state_lock,
            logger=logger,
            save_preset_callback=log_candidate_preset,
            clear_gravity_points_callback=clear_gravity_points,
            get_point_status_callback=get_point_status,
            spawn_triangle_callback=spawn_triangle_preset,
            spawn_pentagram_callback=spawn_pentagram_preset,
            spawn_random_callback=spawn_random_point_preset,
        )

        tk_root.after(
            0,
            update_target_markers,
        )

    except Exception as exc:
        print("Error during settings-window startup: " f"{exc}")

    # --------------------------------------------------------
    # System tray
    # --------------------------------------------------------

    try:
        tray_icon = pystray.Icon(
            "nbody_gravity",
            create_vortex_icon(),
            menu=pystray.Menu(
                pystray.MenuItem(
                    "N-Body Gravity: ACTIVE",
                    lambda icon, item: None,
                    enabled=False,
                ),
                pystray.Menu.SEPARATOR,
                pystray.MenuItem(
                    "Open Settings",
                    show_settings_window,
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

        tray_icon.run_detached()

    except Exception as exc:
        print("Error during tray startup: " f"{exc}")

    # --------------------------------------------------------
    # Main event loop
    # --------------------------------------------------------

    try:
        tk_root.mainloop()

    finally:
        running.clear()
        physics_wake_event.set()

        if listener is not None:
            listener.stop()
            listener.join(timeout=1)

        if tray_icon is not None:
            try:
                tray_icon.stop()
            except Exception:
                pass

        if logging_enabled:
            logger.info("SHUTDOWN | complete")

            stop_logging()

        print("N-Body Gravity stopped.")


if __name__ == "__main__":
    main()