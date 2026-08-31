"""
Runtime application for the gravity-point N-body simulation.

The mouse cursor is never programmatically moved by this module. Mouse input
is used only for:

- Double-click placement of gravity points.
- Triple-click clearing of all gravity points.
- Quadruple-click shutdown.
- Reading the cursor position when triangle or pentagram presets spawn.

Gravity points attract each other, move independently across the virtual
desktop, merge when sufficiently close, and are displayed using click-through
Tkinter marker windows.
"""

import ctypes

# DPI awareness must be initialized before mouse/display-dependent modules.
try:
    ctypes.windll.user32.SetProcessDpiAwarenessContext(
        ctypes.c_void_p(-4)
    )
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

# Gravity points are stored oldest-to-newest. New points are always appended,
# allowing collision logic to consistently remove the oldest merged point.
gravity_points: list[GravityPoint] = []

click_count = 0
last_click_time = 0.0
click_timer = None

click_lock = threading.Lock()
state_lock = threading.Lock()

running = threading.Event()
running.set()

# Wakes the physics thread immediately when point state changes. This keeps
# idle CPU usage low without adding noticeable delay after placement.
physics_wake_event = threading.Event()

# Controller is only used to READ the cursor position for placement presets.
# The application never writes to controller.position.
controller = mouse.Controller()

tray_icon = None
listener = None

tk_root = None
settings_ui = None

target_markers = []
target_marker_visible = []
target_marker_positions = []

MARKER_SIZE = 12
MARKER_COLOR = "#00ff00"
MARKER_TRANSPARENT_COLOR = "#010101"

# Marker movement is visual only; 30 FPS is sufficient for these overlays.
MARKER_REFRESH_MS = 33

# When fewer than two points exist there is no point-to-point motion to
# calculate. A low-rate safety poll is retained in case an external state
# change occurs without explicitly setting physics_wake_event.
IDLE_PHYSICS_HZ = 10.0
IDLE_PHYSICS_INTERVAL = 1.0 / IDLE_PHYSICS_HZ

last_frame_error = ""


# ------------------------------------------------------------
# Logging state
# ------------------------------------------------------------

logging_enabled = False
log_handler = None
log_path = None

logging_lock = threading.Lock()

logger = logging.getLogger("nbody_gravity")
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


# Cache frequently used Win32 function lookups.
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


# ------------------------------------------------------------
# Logging
# ------------------------------------------------------------

def get_log_directory() -> Path:
    """
    Return the application's log directory, creating it when necessary.

    Returns:
        Path to the ``logs`` directory beside this script.
    """
    log_directory = Path(__file__).resolve().parent / "logs"

    log_directory.mkdir(
        parents=True,
        exist_ok=True,
    )

    return log_directory


def start_logging() -> None:
    """
    Enable application logging if it is not already active.

    A new timestamped log file is created in the local ``logs`` directory.
    """
    global logging_enabled
    global log_handler
    global log_path

    with logging_lock:
        if log_handler is not None:
            return

        timestamp = datetime.now().strftime(
            "%Y-%m-%d_%H-%M-%S"
        )

        log_path = (
            get_log_directory()
            / f"nbody_gravity_{timestamp}.log"
        )

        log_handler = logging.FileHandler(
            log_path,
            encoding="utf-8",
        )

        log_handler.setLevel(
            logging.DEBUG
        )

        formatter = logging.Formatter(
            "%(asctime)s.%(msecs)03d | %(levelname)-8s | %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )

        log_handler.setFormatter(
            formatter
        )

        logger.addHandler(
            log_handler
        )

        logging_enabled = True

    logger.info(
        "LOGGING | enabled"
    )

    log_configuration()

    print(
        f"Logging enabled: {log_path}"
    )


def stop_logging() -> None:
    """
    Disable logging and close the current log file.
    """
    global logging_enabled
    global log_handler

    with logging_lock:
        if log_handler is None:
            logging_enabled = False
            return

        logger.info(
            "LOGGING | disabled"
        )

        handler = log_handler

        log_handler = None
        logging_enabled = False

        logger.removeHandler(
            handler
        )

        handler.flush()
        handler.close()

    print("Logging disabled.")


def log_configuration() -> None:
    """
    Write the current N-body configuration to the active log.
    """
    logger.info(
        "N-Body Gravity started"
    )

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
        "n_body_spawn_delay=%s",
        config.triangle_spawn_radius,
        config.pentagram_spawn_radius,
        config.n_body_spawn_delay,
    )


def log_candidate_preset(
    preset_name: str,
    values: dict,
) -> None:
    """
    Write a user-created candidate preset to the application log.

    Logging is automatically enabled if necessary.

    Args:
        preset_name: User-selected preset name.
        values: Mapping of config field names to candidate values.
    """
    if not logging_enabled:
        start_logging()

    logger.info(
        "USER_PRESET_BEGIN | name=%s",
        preset_name,
    )

    for field_name, value in values.items():
        logger.info(
            "USER_PRESET_VALUE | name=%s | %s=%s",
            preset_name,
            field_name,
            value,
        )

    logger.info(
        "USER_PRESET_END | name=%s",
        preset_name,
    )


# ------------------------------------------------------------
# Gravity-point state
# ------------------------------------------------------------

def clear_gravity_points() -> None:
    """
    Remove every active gravity point.

    The physics thread is awakened immediately so it can observe the changed
    state without waiting for the idle polling interval.
    """
    with state_lock:
        gravity_points.clear()

    if logging_enabled:
        logger.info(
            "GRAVITY_POINTS | cleared"
        )

    physics_wake_event.set()

    print(
        "Gravity points cleared."
    )


def get_point_status() -> tuple[int, int]:
    """
    Return the current point count and configured placement limit.

    Returns:
        A tuple containing ``points_placed`` and ``point_limit``.
    """
    with state_lock:
        return (
            len(gravity_points),
            min(
                config.multi_point_count,
                MAX_GRAVITY_POINTS,
            ),
        )


# ------------------------------------------------------------
# Target markers
# ------------------------------------------------------------

GWL_EXSTYLE = -20

WS_EX_TRANSPARENT = 0x00000020
WS_EX_TOOLWINDOW = 0x00000080

HWND_TOPMOST = wintypes.HWND(-1)

SWP_NOACTIVATE = 0x0010
SWP_SHOWWINDOW = 0x0040


def _get_marker_hwnd(marker):
    """
    Return the root HWND for a Tkinter marker window.

    Args:
        marker: Tkinter ``Toplevel`` marker.

    Returns:
        Native Windows handle for the marker's root window.
    """
    marker.update_idletasks()

    client_hwnd = marker.winfo_id()

    root_hwnd = GET_ANCESTOR(
        client_hwnd,
        GA_ROOT,
    )

    return (
        root_hwnd
        if root_hwnd
        else client_hwnd
    )


def _make_marker_click_through(marker) -> None:
    """
    Make a marker ignore mouse input while remaining visible.

    Args:
        marker: Tkinter ``Toplevel`` marker.
    """
    hwnd = _get_marker_hwnd(
        marker
    )

    current_style = GET_WINDOW_LONG(
        hwnd,
        GWL_EXSTYLE,
    )

    SET_WINDOW_LONG(
        hwnd,
        GWL_EXSTYLE,
        current_style
        | WS_EX_TRANSPARENT
        | WS_EX_TOOLWINDOW,
    )


def _create_target_marker():
    """
    Create one transparent, topmost, click-through green point marker.

    Returns:
        Tkinter ``Toplevel`` marker window.
    """
    marker = tk.Toplevel(
        tk_root
    )

    marker.withdraw()
    marker.overrideredirect(True)
    marker.attributes(
        "-topmost",
        True,
    )

    marker.configure(
        bg=MARKER_TRANSPARENT_COLOR,
    )

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

    marker.geometry(
        f"{MARKER_SIZE}x{MARKER_SIZE}+0+0"
    )

    # The native window must exist once before its Win32 extended style can
    # be changed. It is hidden immediately afterward.
    marker.deiconify()
    marker.update_idletasks()

    _make_marker_click_through(
        marker
    )

    marker.withdraw()

    return marker


def _ensure_marker_count(required_count: int) -> None:
    """
    Grow the marker pool to cover the required point count.

    Args:
        required_count: Number of markers currently required.
    """
    required_count = min(
        required_count,
        MAX_GRAVITY_POINTS,
    )

    while len(target_markers) < required_count:
        target_markers.append(
            _create_target_marker()
        )

        target_marker_visible.append(
            False
        )

        target_marker_positions.append(
            None
        )


def _show_or_move_marker(
    index: int,
    x: float,
    y: float,
) -> None:
    """
    Show or reposition one marker when its pixel position changes.

    Args:
        index: Marker index.
        x: Point X coordinate.
        y: Point Y coordinate.
    """
    marker = target_markers[
        index
    ]

    marker_x = round(
        x - MARKER_SIZE / 2
    )

    marker_y = round(
        y - MARKER_SIZE / 2
    )

    marker_position = (
        marker_x,
        marker_y,
    )

    if (
        target_marker_visible[index]
        and target_marker_positions[index]
        == marker_position
    ):
        return

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

    target_marker_positions[
        index
    ] = marker_position


def _hide_marker(index: int) -> None:
    """
    Hide one marker when it is currently visible.

    Args:
        index: Marker index.
    """
    if not target_marker_visible[index]:
        return

    target_markers[
        index
    ].withdraw()

    target_marker_visible[
        index
    ] = False

    target_marker_positions[
        index
    ] = None


def update_target_markers() -> None:
    """
    Refresh marker positions at a visual-only update rate.

    Gravity-point coordinates are copied under the shared-state lock. All
    Tkinter and Win32 work then occurs after the lock is released.
    """
    if (
        tk_root is None
        or not running.is_set()
    ):
        return

    with state_lock:
        positions = tuple(
            (point.x, point.y)
            for point in gravity_points
        )

    _ensure_marker_count(
        len(positions)
    )

    for index, position in enumerate(
        positions
    ):
        _show_or_move_marker(
            index,
            *position,
        )

    for index in range(
        len(positions),
        len(target_markers),
    ):
        _hide_marker(
            index
        )

    try:
        tk_root.after(
            MARKER_REFRESH_MS,
            update_target_markers,
        )
    except tk.TclError:
        pass


def destroy_target_markers() -> None:
    """
    Destroy every marker overlay and clear cached marker state.
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

def create_vortex_icon(size: int = 64) -> Image.Image:
    """
    Create the application's vortex-style tray icon.

    Args:
        size: Icon width and height in pixels.

    Returns:
        Generated RGBA PIL image.
    """
    image = Image.new(
        "RGBA",
        (size, size),
        (15, 5, 25, 255),
    )

    draw = ImageDraw.Draw(
        image
    )

    center_x = size / 2
    center_y = size / 2

    for arm in range(4):
        points = []
        arm_offset = arm * (
            math.pi / 2
        )

        for i in range(120):
            t = i / 119

            angle = (
                arm_offset
                + t * math.pi * 3.5
            )

            radius = (
                size * 0.42 * (1 - t)
                + 2
            )

            x = (
                center_x
                + math.cos(angle) * radius
            )

            y = (
                center_y
                + math.sin(angle) * radius
            )

            points.append(
                (x, y)
            )

        purple = (
            90
            + arm * 20
        )

        draw.line(
            points,
            fill=(
                purple,
                20,
                150,
                255,
            ),
            width=3,
        )

    center_radius = (
        size * 0.10
    )

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


def toggle_logging(icon, item) -> None:
    """
    Toggle runtime logging from the tray menu.

    Args:
        icon: Pystray icon instance.
        item: Activated pystray menu item.
    """
    if logging_enabled:
        stop_logging()
    else:
        start_logging()

    icon.update_menu()


def open_log_folder(icon, item) -> None:
    """
    Open the application's log directory in Windows Explorer.

    Args:
        icon: Pystray icon instance.
        item: Activated pystray menu item.
    """
    os.startfile(
        get_log_directory()
    )


def show_settings_window(
    icon=None,
    item=None,
) -> None:
    """
    Schedule display of the Tkinter settings window.

    Args:
        icon: Optional pystray icon instance.
        item: Optional activated pystray menu item.
    """
    if (
        tk_root is None
        or settings_ui is None
    ):
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
    Stop the listener, physics loop, tray icon, and Tkinter application.
    """
    global click_timer

    if not running.is_set():
        return

    if logging_enabled:
        logger.info(
            "SHUTDOWN | beginning shutdown"
        )

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


def tray_exit(icon, item) -> None:
    """
    Exit callback for the tray menu.

    Args:
        icon: Pystray icon instance.
        item: Activated pystray menu item.
    """
    if logging_enabled:
        logger.info(
            "EXIT | tray menu"
        )

    shutdown()


# ------------------------------------------------------------
# N-body placement presets
# ------------------------------------------------------------

def spawn_triangle_preset() -> None:
    """
    Replace active points with an equilateral triangle around the cursor.

    ``triangle_spawn_radius`` is measured from the cursor to each vertex.
    The cursor position is read only when this function executes, allowing
    delayed preset placement.
    """
    cursor_x, cursor_y = controller.position

    radius = (
        config.triangle_spawn_radius
    )

    points = []

    # Start with one point directly above the cursor.
    start_angle = (
        -math.pi / 2
    )

    for index in range(3):
        angle = (
            start_angle
            + index * (2 * math.pi / 3)
        )

        points.append(
            GravityPoint(
                x=(
                    cursor_x
                    + math.cos(angle) * radius
                ),
                y=(
                    cursor_y
                    + math.sin(angle) * radius
                ),
            )
        )

    with state_lock:
        gravity_points.clear()
        gravity_points.extend(
            points
        )

    physics_wake_event.set()

    if logging_enabled:
        logger.info(
            "N_BODY_PRESET | preset=triangle | radius=%s",
            radius,
        )

    print(
        f"Spawned triangle preset at radius {radius}."
    )


def spawn_pentagram_preset() -> None:
    """
    Replace active points with five equally spaced points around the cursor.

    The five vertices correspond to the outer vertices of a pentagram.
    ``pentagram_spawn_radius`` is measured from the cursor to each vertex.
    """
    cursor_x, cursor_y = controller.position

    radius = (
        config.pentagram_spawn_radius
    )

    points = []

    # Start with one point directly above the cursor.
    start_angle = (
        -math.pi / 2
    )

    for index in range(5):
        angle = (
            start_angle
            + index * (2 * math.pi / 5)
        )

        points.append(
            GravityPoint(
                x=(
                    cursor_x
                    + math.cos(angle) * radius
                ),
                y=(
                    cursor_y
                    + math.sin(angle) * radius
                ),
            )
        )

    with state_lock:
        gravity_points.clear()
        gravity_points.extend(
            points
        )

    physics_wake_event.set()

    if logging_enabled:
        logger.info(
            "N_BODY_PRESET | preset=pentagram | radius=%s",
            radius,
        )

    print(
        f"Spawned pentagram preset at radius {radius}."
    )


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
        Place one gravity point. If the configured point limit has already
        been reached, the oldest point is removed first and the new point
        is appended.

    Triple-click:
        Clear all gravity points.

    Args:
        x: Mouse X coordinate captured for the click sequence.
        y: Mouse Y coordinate captured for the click sequence.
    """
    global click_count
    global click_timer

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

            if (
                len(gravity_points)
                >= point_limit
            ):
                # New placements always replace the oldest active point.
                removed_point = gravity_points.pop(0)

            gravity_points.append(
                GravityPoint(
                    x=float(x),
                    y=float(y),
                )
            )

            point_number = len(
                gravity_points
            )

        if (
            removed_point is not None
            and logging_enabled
        ):
            logger.info(
                "GRAVITY_POINT | oldest_removed=%s",
                removed_point,
            )

        if logging_enabled:
            logger.info(
                "GRAVITY_POINT | number=%s | x=%s | y=%s",
                point_number,
                x,
                y,
            )

        print(
            "Gravity point "
            f"{point_number}/{point_limit}: "
            f"{(x, y)}"
        )

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
    Process mouse-button presses for click-sequence recognition.

    Args:
        x: X coordinate of the mouse event.
        y: Y coordinate of the mouse event.
        button: Pynput mouse button associated with the event.
        pressed: True on button press, False on release.

    Returns:
        False when quadruple-click shutdown is requested; otherwise None.
    """
    global click_count
    global last_click_time
    global click_timer

    if not pressed:
        return

    now = time.perf_counter()
    should_exit = False

    with click_lock:
        if (
            now - last_click_time
            > config.click_sequence_timeout
        ):
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
            logger.info(
                "EXIT | quadruple click detected"
            )

        print(
            "Quadruple click detected. Exiting."
        )

        shutdown()
        return False


# ------------------------------------------------------------
# Point physics
# ------------------------------------------------------------

def gravity_loop() -> None:
    """
    Advance active gravity points under mutual attraction.

    Point physics runs at ``config.point_physics_hz``. When fewer than two
    points exist, the thread sleeps at a low polling rate and can be awakened
    immediately through ``physics_wake_event``.

    The mouse cursor is never sampled or modified by this loop.

    Repeated consecutive simulation failures trigger application shutdown.
    """
    global last_frame_error

    previous_time = (
        time.perf_counter()
    )

    consecutive_errors = 0

    while running.is_set():
        frame_start = (
            time.perf_counter()
        )

        current_time = frame_start

        dt = min(
            current_time - previous_time,
            0.1,
        )

        previous_time = current_time

        point_count = 0

        try:
            with state_lock:
                point_limit = min(
                    config.multi_point_count,
                    MAX_GRAVITY_POINTS,
                )

                # If the configured limit is lowered, discard the oldest
                # excess points so the newest placements remain active.
                excess_points = (
                    len(gravity_points)
                    - point_limit
                )

                if excess_points > 0:
                    del gravity_points[
                        :excess_points
                    ]

                point_count = len(
                    gravity_points
                )

                if point_count >= 2:
                    removed_point = update_gravity_points(
                        gravity_points,
                        dt,
                        SCREEN_BOUNDS,
                    )

                    if (
                        removed_point is not None
                        and logging_enabled
                    ):
                        logger.info(
                            "GRAVITY_POINT | merged_oldest_removed=%s",
                            removed_point,
                        )

            consecutive_errors = 0
            last_frame_error = ""

        except Exception as exc:
            consecutive_errors += 1

            if (
                not last_frame_error
                or last_frame_error != str(exc)
            ):
                print(
                    f"Physics error: {exc}"
                )

            last_frame_error = str(
                exc
            )

            if logging_enabled:
                logger.error(
                    "PHYSICS_ERROR | %s",
                    exc,
                    exc_info=True,
                )

            if consecutive_errors >= 5:
                print(
                    "Too many consecutive physics errors. Exiting."
                )

                shutdown()
                break

        elapsed = (
            time.perf_counter()
            - frame_start
        )

        if point_count >= 2:
            frame_interval = (
                1.0
                / max(
                    config.point_physics_hz,
                    1.0,
                )
            )
        else:
            frame_interval = (
                IDLE_PHYSICS_INTERVAL
            )

        wait_time = max(
            0.0,
            frame_interval - elapsed,
        )

        if (
            wait_time > 0
            and running.is_set()
        ):
            physics_wake_event.wait(
                wait_time
            )

            physics_wake_event.clear()


# ------------------------------------------------------------
# Main
# ------------------------------------------------------------

def main() -> None:
    """
    Initialize logging, input listener, physics, Tkinter UI, and tray icon.

    All subsystems are shut down when the Tkinter main loop exits.
    """
    global tray_icon
    global listener
    global tk_root
    global settings_ui

    # LOGGING STARTUP
    section = "Logging Startup"

    try:
        if config.logging_enabled_by_default:
            start_logging()

    except Exception as exc:
        print(
            f"Error {exc} happened during: {section}"
        )

    # MOUSE LISTENER INITIALIZATION
    section = "Mouse Listener Initialization"

    try:
        listener = mouse.Listener(
            on_click=on_click,
        )

        listener.start()

    except Exception as exc:
        print(
            f"Error {exc} happened during: {section}"
        )

    # PHYSICS THREAD INITIALIZATION
    section = "Physics Thread Initialization"

    try:
        physics_thread = threading.Thread(
            target=gravity_loop,
            daemon=True,
            name="NBodyGravityPhysics",
        )

        physics_thread.start()

    except Exception as exc:
        print(
            f"Error {exc} happened during: {section}"
        )

    # POP-UP WINDOW CREATION
    section = "Pop-up Window Creation"

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
        )

        tk_root.after(
            0,
            update_target_markers,
        )

    except Exception as exc:
        print(
            f"Error {exc} happened during: {section}"
        )

    # SYSTEM TRAY ICON POPULATION
    section = "Tray Icon Population"

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
        print(
            f"Error {exc} happened during: {section}"
        )

    try:
        tk_root.mainloop()

    finally:
        running.clear()
        physics_wake_event.set()

        if listener is not None:
            listener.stop()
            listener.join(
                timeout=1
            )

        if tray_icon is not None:
            try:
                tray_icon.stop()
            except Exception:
                pass

        if logging_enabled:
            logger.info(
                "SHUTDOWN | complete"
            )

            stop_logging()

        print(
            "N-Body Gravity stopped."
        )


if __name__ == "__main__":
    main()
