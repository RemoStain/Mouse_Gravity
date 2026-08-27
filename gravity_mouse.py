import ctypes
# DPI awareness must be initialized before mouse/display-dependent modules.
try:
    ctypes.windll.user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))
except Exception:
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
    except Exception:
        ctypes.windll.user32.SetProcessDPIAware()

from ctypes import wintypes

import logging
import math
import os
import threading
import time
import tkinter as tk

from datetime import datetime
from pathlib import Path


import pystray
from PIL import Image, ImageDraw
from pynput import mouse

from config import config, MAX_GRAVITY_POINTS
from gravity import (
    GravityPoint,
    multi_point_gravity,
    single_point_gravity,
    update_gravity_points,
)
from settings_window import SettingsWindow


# ------------------------------------------------------------
# Shared state
# ------------------------------------------------------------

GRAVITY_MODE_SINGLE = "single"
GRAVITY_MODE_MULTI = "multi"

gravity_mode = GRAVITY_MODE_SINGLE

target = None
gravity_points = []

velocity_x = 0.0
velocity_y = 0.0

orbit_direction = 1

click_count = 0
last_click_time = 0.0
click_timer = None

click_lock = threading.Lock()
state_lock = threading.Lock()

running = threading.Event()
running.set()

# Wakes the physics thread immediately when state changes while the
# simulation is idle. This lets idle CPU usage stay very low without
# adding noticeable response delay when a target is placed.
physics_wake_event = threading.Event()

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

# Marker movement is visual only; 30 FPS is sufficient and cuts the
# overlay/UI work roughly in half compared with 60 FPS.
MARKER_REFRESH_MS = 33

# Cursor physics remains responsive at config.fps while point-to-point
# motion is much less time-sensitive.
POINT_PHYSICS_HZ = 30.0
POINT_PHYSICS_INTERVAL = 1.0 / POINT_PHYSICS_HZ

# When no target exists, the physics thread only performs a low-rate
# safety poll. State changes wake it immediately through physics_wake_event.
IDLE_PHYSICS_HZ = 20.0
IDLE_PHYSICS_INTERVAL = 1.0 / IDLE_PHYSICS_HZ

last_frame_error = ""


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

SCREEN_BOUNDS = (
    SCREEN_LEFT,
    SCREEN_TOP,
    SCREEN_RIGHT,
    SCREEN_BOTTOM,
)


print(
    f"Virtual desktop: "
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


def get_log_directory():
    log_directory = Path(__file__).resolve().parent / "logs"

    log_directory.mkdir(
        parents=True,
        exist_ok=True,
    )

    return log_directory


def start_logging():
    global logging_enabled
    global log_handler
    global log_path

    with logging_lock:
        if log_handler is not None:
            return

        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")

        log_path = get_log_directory() / f"mouse_gravity_{timestamp}.log"

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
    logger.info("Mouse Gravity started")

    logger.info(
        "CONFIG | "
        "gravity=%s | "
        "reference_distance=%s | "
        "gravity_distance_power=%s | "
        "min_gravity_distance=%s | "
        "max_gravity_acceleration=%s",
        config.gravity,
        config.reference_distance,
        config.gravity_distance_power,
        config.min_gravity_distance,
        config.max_gravity_acceleration,
    )

    logger.info(
        "CONFIG | " "max_speed=%s | " "drag=%s | " "stop_radius=%s | " "fps=%s",
        config.max_speed,
        config.drag,
        config.stop_radius,
        config.fps,
    )

    logger.info(
        "CONFIG | "
        "normal_input_strength=%s | "
        "toward_input_multiplier=%s | "
        "away_input_multiplier=%s | ",
        config.normal_input_strength,
        config.toward_input_multiplier,
        config.away_input_multiplier,
    )

    logger.info(
        "CONFIG | "
        "multi_point_count=%s | "
        "point_gravity_multiplier=%s | "
        "point_drag=%s | "
        "point_max_speed=%s",
        config.multi_point_count,
        config.point_gravity_multiplier,
        config.point_drag,
        config.point_max_speed,
    )


def log_candidate_preset(
    preset_name: str,
    values: dict,
):
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
# Gravity mode state
# ------------------------------------------------------------


def set_gravity_mode(mode):
    """
    Switch between single-point and multi-point gravity modes.

    Switching modes clears existing targets and wakes the physics thread
    so the change is reflected immediately even when the simulation was idle.
    """
    global gravity_mode
    global target
    global velocity_x
    global velocity_y
    global orbit_direction

    if mode not in {
        GRAVITY_MODE_SINGLE,
        GRAVITY_MODE_MULTI,
    }:
        raise ValueError(f"Unknown gravity mode: {mode}")

    with state_lock:
        gravity_mode = mode
        target = None
        gravity_points.clear()

        velocity_x = 0.0
        velocity_y = 0.0
        orbit_direction = 0

    if logging_enabled:
        logger.info(
            "GRAVITY_MODE | mode=%s",
            mode,
        )

    physics_wake_event.set()

    print(f"Gravity mode: {mode}")

    update_tray_status()


def clear_gravity_points():
    """
    Clear all multi-point targets and reset cursor/orbit momentum.
    """
    global velocity_x
    global velocity_y
    global orbit_direction

    with state_lock:
        gravity_points.clear()
        velocity_x = 0.0
        velocity_y = 0.0
        orbit_direction = 0

    if logging_enabled:
        logger.info("GRAVITY_POINTS | cleared")

    physics_wake_event.set()

    print("Gravity points cleared.")


def get_point_status():
    """
    Return the number of placed points and the configured placement limit.
    """
    with state_lock:
        return (
            len(gravity_points),
            config.multi_point_count,
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
    Return the root HWND for a Tkinter Toplevel.

    GetAncestor with GA_ROOT is more reliable than GetParent for
    locating Tkinter's actual Windows top-level wrapper.
    """
    marker.update_idletasks()

    client_hwnd = marker.winfo_id()

    root_hwnd = GET_ANCESTOR(
        client_hwnd,
        GA_ROOT,
    )

    return root_hwnd if root_hwnd else client_hwnd


def _make_marker_click_through(marker):
    """
    Make the marker ignore mouse input while remaining visible.
    """
    hwnd = _get_marker_hwnd(marker)

    current_style = GET_WINDOW_LONG(
        hwnd,
        GWL_EXSTYLE,
    )

    SET_WINDOW_LONG(
        hwnd,
        GWL_EXSTYLE,
        current_style | WS_EX_TRANSPARENT | WS_EX_TOOLWINDOW,
    )


def _create_target_marker():
    """
    Create one small, transparent, click-through green marker window.
    """
    marker = tk.Toplevel(
        tk_root,
    )

    marker.withdraw()
    marker.overrideredirect(True)
    marker.attributes("-topmost", True)

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

    marker.geometry(f"{MARKER_SIZE}x{MARKER_SIZE}+0+0")

    # The window must exist once before its Win32 extended style can
    # be changed. It is hidden again immediately afterward.
    marker.deiconify()
    marker.update_idletasks()

    _make_marker_click_through(marker)

    marker.withdraw()

    return marker


def _ensure_marker_count(required_count):
    """
    Grow the marker pool up to the hard five-point maximum.
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
    index,
    x,
    y,
):
    """
    Show or reposition one marker only when its pixel position changes.

    Static single-point targets therefore generate no repeated Win32
    positioning calls after the first update.
    """
    marker = target_markers[index]

    marker_x = round(x - MARKER_SIZE / 2)

    marker_y = round(y - MARKER_SIZE / 2)

    marker_position = (
        marker_x,
        marker_y,
    )

    if (
        target_marker_visible[index]
        and target_marker_positions[index] == marker_position
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

    target_marker_positions[index] = marker_position


def _hide_marker(index):
    """
    Hide one marker only if it is currently visible.
    """
    if not target_marker_visible[index]:
        return

    target_markers[index].withdraw()
    target_marker_visible[index] = False
    target_marker_positions[index] = None
    # if gravity_points:
    #     gravity_points.pop(index)
    #     logger.info(
    #         "GRAVITY POINTS"
    #         " | "
    #         "REMOVED"
    #         " | "
    #         "Gravity Point: %s",
    #         index
    #         )


def update_target_markers():
    """
    Refresh target-marker positions at a low visual-only frame rate.

    Marker state is copied while holding the lock, then all Tk/Win32 work
    happens after the lock is released.
    """
    if tk_root is None or not running.is_set():
        return

    with state_lock:
        if gravity_mode == GRAVITY_MODE_SINGLE:
            positions = (target,) if target is not None else ()
        else:
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


def destroy_target_markers():
    """
    Destroy all marker overlays and clear their cached UI state.
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


def create_vortex_icon(size=64):
    """
    Create a swirling vortex tray icon.

    Args:
        size (int): The size of the icon in pixels (width and height).

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
            fill=(
                purple,
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
):
    if logging_enabled:
        stop_logging()
    else:
        start_logging()

    icon.update_menu()


def open_log_folder(
    icon,
    item,
):
    """
    Open the directory where Mouse Gravity logs are stored.
    """
    os.startfile(get_log_directory())



def update_tray_status():
    if tray_icon is None:
        return

    with state_lock:
        current_mode = gravity_mode

    mode_name = "MULTI" if current_mode == GRAVITY_MODE_MULTI else "SINGLE"

    tray_icon.title = "Mouse Gravity: ACTIVE | " f"Mode: {mode_name}"

    tray_icon.icon = create_vortex_icon()


def show_settings_window(
    icon=None,
    item=None,
):
    if tk_root is None or settings_ui is None:
        return

    tk_root.after(
        0,
        settings_ui.show,
    )


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
):
    """
    Callback function for the "Exit" menu item in the tray icon's context menu.
    Args:
        icon (pystray.Icon): The tray icon object.
        item (pystray.MenuItem): The menu item that was clicked.
    """
    if logging_enabled:
        logger.info("EXIT | tray menu")

    shutdown()


# ------------------------------------------------------------
# n-Body Presets
# ------------------------------------------------------------


def spawn_triangle_preset():
    """
    Spawn three gravity points in an equilateral triangle around
    the current cursor position.

    triangle_spawn_radius is the distance from the cursor to each
    gravity point.
    """
    global velocity_x
    global velocity_y
    global orbit_direction

    cursor_x, cursor_y = controller.position

    radius = config.triangle_spawn_radius

    points = []

    # Start with one point directly above the cursor.
    start_angle = -math.pi / 2

    for index in range(3):
        angle = start_angle + index * (2 * math.pi / 3)

        points.append(
            GravityPoint(
                x=(cursor_x + math.cos(angle) * radius),
                y=(cursor_y + math.sin(angle) * radius),
            )
        )

    with state_lock:
        gravity_points.clear()
        gravity_points.extend(points)

        velocity_x = 0.0
        velocity_y = 0.0
        orbit_direction = 0

    physics_wake_event.set()

    if logging_enabled:
        logger.info(
            "N_BODY_PRESET | " "preset=triangle | " "radius=%s",
            radius,
        )

    print(f"Spawned triangle preset at radius {radius}.")


def spawn_pentagram_preset():
    """
    Spawn five gravity points at the vertices of a pentagram
    centered on the current cursor position.

    pentagram_spawn_radius is the distance from the cursor to
    each gravity point.
    """
    global velocity_x
    global velocity_y
    global orbit_direction

    cursor_x, cursor_y = controller.position

    radius = config.pentagram_spawn_radius

    points = []

    # Start with one point directly above the cursor.
    start_angle = -math.pi / 2

    for index in range(5):
        angle = start_angle + index * (2 * math.pi / 5)

        points.append(
            GravityPoint(
                x=(cursor_x + math.cos(angle) * radius),
                y=(cursor_y + math.sin(angle) * radius),
            )
        )

    with state_lock:
        gravity_points.clear()
        gravity_points.extend(points)

        velocity_x = 0.0
        velocity_y = 0.0
        orbit_direction = 0

    physics_wake_event.set()

    if logging_enabled:
        logger.info(
            "N_BODY_PRESET | " "preset=pentagram | " "radius=%s",
            radius,
        )

    print(f"Spawned pentagram preset at radius {radius}.")


# ------------------------------------------------------------
# Click handling
# ------------------------------------------------------------


def process_click_sequence(
    x,
    y,
):
    """
    Resolve a completed click sequence into target placement or clearing.

    Double-click places a target. In multi-point mode placement stops at
    the smaller of the configured limit and the hard five-point maximum.

    Triple-click clears the active target set.

    Args:
        x (float): The x coordinate of the mouse.
        y (float): The y coordinate of the mouse.

    """
    global click_count
    global click_timer
    global target
    global velocity_x
    global velocity_y
    global orbit_direction

    with click_lock:
        count = click_count
        click_count = 0
        click_timer = None

    if not running.is_set():
        return

    if count == 2:

        with state_lock:
            current_mode = gravity_mode

        # ----------------------------------------------------
        # Classic single-target mode
        # ----------------------------------------------------

        if current_mode == GRAVITY_MODE_SINGLE:
            with state_lock:
                target = (
                    x,
                    y,
                )

            if logging_enabled:
                logger.info(
                    "TARGET | x=%s | y=%s",
                    x,
                    y,
                )

            current_x, current_y = controller.position

            dx = x - current_x
            dy = y - current_y

            distance = math.hypot(
                dx,
                dy,
            )

            if distance > 0:
                radial_x = dx / distance
                radial_y = dy / distance

                tangent_x = -radial_y
                tangent_y = radial_x

                tangent_velocity = velocity_x * tangent_x + velocity_y * tangent_y

                with state_lock:
                    orbit_direction = -1 if tangent_velocity < 0 else 1

            print(f"New target: {(x, y)}")

        # ----------------------------------------------------
        # Multi-point mode
        # ----------------------------------------------------

        else:
            with state_lock:
                point_limit = min(
                    config.multi_point_count,
                    MAX_GRAVITY_POINTS,
                )

                if len(gravity_points) >= point_limit:
                    point_number = None
                else:
                    gravity_points.append(
                        GravityPoint(
                            x=float(x),
                            y=float(y),
                        )
                    )

                    point_number = len(gravity_points)

            if point_number is None:
                print(
                    "All gravity points are already placed. "
                    "Clear them or increase Multi Point Count."
                )
                return

            if logging_enabled:
                logger.info(
                    "GRAVITY_POINT | " "number=%s | " "x=%s | " "y=%s",
                    point_number,
                    x,
                    y,
                )

            print(
                "Gravity point "
                f"{point_number}/"
                f"{min(config.multi_point_count, MAX_GRAVITY_POINTS)}: "
                f"{(x, y)}"
            )

        physics_wake_event.set()

    elif count == 3:
        with state_lock:
            if gravity_mode == GRAVITY_MODE_SINGLE:
                target = None
            else:
                gravity_points.clear()

            velocity_x = 0.0
            velocity_y = 0.0
            orbit_direction = 0

        if logging_enabled:
            logger.info("REMOVE GRAVITY | triple click detected")

        physics_wake_event.set()

        print("Gravity target(s) removed.")


def on_click(
    x,
    y,
    button,
    pressed,
):
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
            logger.info("EXIT | quadruple click detected")

        print("Quadruple click detected. Exiting.")

        shutdown()
        return False


# ------------------------------------------------------------
# Physics helpers
# ------------------------------------------------------------


def apply_user_input(
    user_dx,
    user_dy,
    radial_x,
    radial_y,
):
    """
    Apply physical mouse movement to the simulated cursor velocity.

    The input is split into movement toward/away from the effective
    gravity direction and movement perpendicular to that direction.
    """
    global velocity_x
    global velocity_y

    # --------------------------------------------------------
    # User movement
    # --------------------------------------------------------

    # Radial unit vector points toward the target or, in multi-point
    # mode, toward the direction of the combined gravity field.
    #
    # Tangent is perpendicular to the radial direction.
    tangent_x = -radial_y
    tangent_y = radial_x

    # --------------------------------------------------------
    # Split physical mouse movement into:
    #
    # 1. radial movement
    # 2. tangential movement
    # --------------------------------------------------------

    radial_input = user_dx * radial_x + user_dy * radial_y

    tangential_input = user_dx * tangent_x + user_dy * tangent_y

    # --------------------------------------------------------
    # Radial input
    #
    # Positive radial_input means the user moved toward
    # the effective gravity direction.
    #
    # Negative means the user moved away.
    # --------------------------------------------------------

    if radial_input >= 0:
        radial_strength = config.normal_input_strength * config.toward_input_multiplier
    else:
        radial_strength = config.normal_input_strength * config.away_input_multiplier

    velocity_x += radial_x * radial_input * radial_strength

    velocity_y += radial_y * radial_input * radial_strength

    # --------------------------------------------------------
    # Tangential input
    # --------------------------------------------------------

    tangential_strength = config.normal_input_strength

    velocity_x += tangent_x * tangential_input * tangential_strength

    velocity_y += tangent_y * tangential_input * tangential_strength

    return (
        radial_input,
        tangential_input,
    )


def clamp_cursor_to_desktop(
    new_x,
    new_y,
):
    """
    Clamp cursor movement to the virtual desktop and remove velocity
    that would continue pushing the cursor through a screen edge.
    """
    global velocity_x
    global velocity_y

    # --------------------------------------------------------
    # Virtual desktop edge collisions
    # --------------------------------------------------------

    def bounce_velocity(v1: float = 0.0):
        # print(v1)

        # Store the sign we want
        if v1 < 0:
            v2_sign = 1
        else:
            v2_sign = -1

        # Since we stored the sign, we need to remove it from v1
        v1 = abs(v1)

        # Divide v1 by gravity, or 2000, whichever is lower
        v2 = v1 / min(config.gravity, 2000)
        
        # Ensure the bouce velocity is at least 1
        v2 = max(v2, 1.0)

        # Recombine with the sign to get a slightly bouncy v2 effect
        # print(v2 * v2_sign)
        return v2 * v2_sign

    # TESTING BOUNCE BEHAVIOUR
    # 0.1 is too much bounce, I just want to change the vector more than just removing one axis
    # 0.05 is still to much for some situations, maybe take the axis value and divide it by the some relative gravity setting and flip the sign?
    # bounce_velocity still needs tweaks, but is okay for now

    if new_x <= SCREEN_LEFT:
        new_x = SCREEN_LEFT

        if velocity_x < 0:
            v2 = bounce_velocity(velocity_x)
            if logging_enabled:
                logger.info(
                    "COLLISION | wall=LEFT | "
                    "velocity_x_1=%.2f"
                    "|"
                    "velocity_x_2=%.2f",
                    velocity_x,
                    v2,
                )

            velocity_x = v2

    elif new_x >= SCREEN_RIGHT:
        new_x = SCREEN_RIGHT

        if velocity_x > 0:
            v2 = bounce_velocity(velocity_x)
            if logging_enabled:
                logger.info(
                    "COLLISION | wall=RIGHT | "
                    "velocity_x_1=%.2f"
                    "|"
                    "velocity_x_2=%.2f",
                    velocity_x,
                    v2,
                )

            velocity_x = v2

    if new_y <= SCREEN_TOP:
        new_y = SCREEN_TOP

        if velocity_y < 0:
            v2 = bounce_velocity(velocity_y)
            if logging_enabled:
                logger.info(
                    "COLLISION | wall=TOP | "
                    "velocity_y_1=%.2f"
                    "|"
                    "velocity_y_2=%.2f",
                    velocity_y,
                    v2,
                )

            velocity_y = v2

    elif new_y >= SCREEN_BOTTOM:
        new_y = SCREEN_BOTTOM

        if velocity_y > 0:
            v2 = bounce_velocity(velocity_y)
            if logging_enabled:
                logger.info(
                    "COLLISION | wall=BOTTOM | "
                    "velocity_y_1=%.2f"
                    " | "
                    "velocity_y_2=%.2f",
                    velocity_y,
                    v2,
                )

            velocity_y = v2

    return (
        new_x,
        new_y,
    )


# ------------------------------------------------------------
# Mouse physics
# ------------------------------------------------------------


def gravity_loop():
    """
    Main loop for simulating mouse gravity physics.

    Cursor physics runs at ``config.fps`` while an active target exists.
    Gravity-point mutual attraction runs at 30 Hz because the point motion
    is much slower and does not need cursor-rate updates. When no target
    exists, the thread mostly sleeps and is awakened immediately by target
    placement or a mode change.

    This separation keeps cursor motion responsive while substantially
    reducing background CPU usage so other applications can run normally.

    Raises:
        Exception: Physics or mouse-control errors are logged. Repeated
        consecutive failures trigger shutdown.
    """
    global velocity_x
    global velocity_y
    global last_frame_error
    global gravity_points

    previous_time = time.perf_counter()
    last_point_update_time = previous_time

    expected_x, expected_y = controller.position

    telemetry_interval = (
        1.0 / config.log_telemetry_hz if config.log_telemetry_hz > 0 else None
    )

    last_telemetry_time = time.perf_counter()

    # Stop the program if too many physics frames fail in a row.
    consecutive_errors = 0

    # --------------------------------------------------------
    # Main loop
    # --------------------------------------------------------

    while running.is_set():
        frame_start = time.perf_counter()
        current_time = frame_start

        dt = current_time - previous_time
        previous_time = current_time

        # Prevent a long pause or debugger stop from causing one enormous
        # physics step when execution resumes.
        dt = min(
            dt,
            0.05,
        )

        with state_lock:
            current_mode = gravity_mode
            current_target = target

            if current_mode == GRAVITY_MODE_MULTI:
                # Enforce the configured limit immediately if the user
                # lowers it while points already exist.
                point_limit = min(
                    config.multi_point_count,
                    MAX_GRAVITY_POINTS,
                )

                if len(gravity_points) > point_limit:
                    del gravity_points[point_limit:]

                simulation_active = bool(gravity_points)
            else:
                simulation_active = current_target is not None

        # ----------------------------------------------------
        # Idle throttling
        # ----------------------------------------------------

        if not simulation_active:
            # There is no gravity to calculate and user input does not need
            # to be sampled until a target exists.
            expected_x, expected_y = controller.position

            consecutive_errors = 0
            last_frame_error = ""

            elapsed = time.perf_counter() - frame_start
            wait_time = max(
                0.0,
                IDLE_PHYSICS_INTERVAL - elapsed,
            )

            if wait_time > 0:
                physics_wake_event.wait(wait_time)
                physics_wake_event.clear()

            continue

        # ----------------------------------------------------
        # Detect physical mouse input
        # ----------------------------------------------------

        actual_x, actual_y = controller.position

        user_dx = actual_x - expected_x
        user_dy = actual_y - expected_y

        # ----------------------------------------------------
        # Gravity and physics
        # ----------------------------------------------------

        try:
            has_gravity = False

            acceleration_x = 0.0
            acceleration_y = 0.0

            radial_x = 0.0
            radial_y = 0.0

            radial_input = 0.0
            tangential_input = 0.0
            gravity_strength = 0.0
            distance = 0.0
            point_count = 0

            # ------------------------------------------------
            # Classic mode
            # ------------------------------------------------

            if current_mode == GRAVITY_MODE_SINGLE and current_target is not None:
                target_x, target_y = current_target

                # Distance-dependent gravity is calculated in gravity.py.
                # The function preserves the original minimum-distance and
                # maximum-acceleration clamps.
                (
                    acceleration_x,
                    acceleration_y,
                    radial_x,
                    radial_y,
                    distance,
                    gravity_strength,
                ) = single_point_gravity(
                    actual_x,
                    actual_y,
                    target_x,
                    target_y,
                )

                if distance <= config.stop_radius:
                    velocity_x = 0.0
                    velocity_y = 0.0

                    controller.position = (
                        round(target_x),
                        round(target_y),
                    )

                    expected_x, expected_y = controller.position

                    consecutive_errors = 0
                    last_frame_error = ""

                    # Use the normal frame limiter below instead of sleeping
                    # a full frame here and then sleeping again.
                    has_gravity = False
                else:
                    has_gravity = True

            # ------------------------------------------------
            # Multi-point mode
            # ------------------------------------------------

            elif current_mode == GRAVITY_MODE_MULTI:
                with state_lock:
                    point_count = len(gravity_points)

                    point_elapsed = current_time - last_point_update_time

                    # Point-to-point attraction only needs a 30 Hz update.
                    # The cursor still reads the latest positions every
                    # cursor frame.

                    # THIS IS WHERE THE GRAVITY_POINTS CAN BE REMOVED
                    if point_count >= 2 and point_elapsed >= POINT_PHYSICS_INTERVAL:
                        removed_point = update_gravity_points(
                            gravity_points,
                            min(point_elapsed, 0.1),
                            SCREEN_BOUNDS,
                        )

                        if removed_point is not None and logging_enabled:
                            logger.info(
                                "GRAVITY POINTS"
                                " | "
                                "REMOVED"
                                " | "
                                "Gravity Point: %s",
                                removed_point,
                            )

                        last_point_update_time = current_time

                    elif point_count < 2 and point_elapsed >= POINT_PHYSICS_INTERVAL:
                        # Keep the point timer current even when there is
                        # nothing to integrate.
                        last_point_update_time = current_time

                    if gravity_points:
                        # With at most five points this calculation is small
                        # enough to perform directly under the lock. This
                        # avoids allocating new GravityPoint snapshots 120
                        # times per second.
                        (
                            acceleration_x,
                            acceleration_y,
                        ) = multi_point_gravity(
                            actual_x,
                            actual_y,
                            gravity_points,
                        )

                gravity_magnitude = math.hypot(
                    acceleration_x,
                    acceleration_y,
                )

                # The combined force vector becomes the effective radial
                # direction for physical mouse input.
                if gravity_magnitude > 0:
                    radial_x = acceleration_x / gravity_magnitude

                    radial_y = acceleration_y / gravity_magnitude

                    gravity_strength = gravity_magnitude
                    has_gravity = True

            # ------------------------------------------------
            # Apply cursor physics
            # ------------------------------------------------

            if has_gravity:
                # Velocity update based on acceleration and time step.
                velocity_x += acceleration_x * dt
                velocity_y += acceleration_y * dt

                (
                    radial_input,
                    tangential_input,
                ) = apply_user_input(
                    user_dx,
                    user_dy,
                    radial_x,
                    radial_y,
                )

                # ------------------------------------------------
                # Drag
                # ------------------------------------------------

                # Scale drag by elapsed time so missed/slow frames do not
                # materially change damping per second.
                drag_factor = config.drag ** (dt * config.fps)

                velocity_x *= drag_factor
                velocity_y *= drag_factor

                # ------------------------------------------------
                # Maximum speed
                # ------------------------------------------------

                # Speed^2 is Vx^2 + Vy^2
                speed_squared = velocity_x * velocity_x + velocity_y * velocity_y

                max_speed_squared = config.max_speed * config.max_speed

                # NOTE TO ME: do I want this?
                # I'm trying to a bounce and this might be messing it up
                # Avoid sqrt unless clamping is actually required.
                if speed_squared > max_speed_squared:
                    speed = math.sqrt(speed_squared)

                    scale = config.max_speed / speed

                    velocity_x *= scale
                    velocity_y *= scale

                # ------------------------------------------------
                # Proposed movement
                # ------------------------------------------------

                new_x = actual_x + velocity_x * dt

                new_y = actual_y + velocity_y * dt

                (
                    new_x,
                    new_y,
                ) = clamp_cursor_to_desktop(
                    new_x,
                    new_y,
                )

                controller.position = (
                    round(new_x),
                    round(new_y),
                )

                expected_x, expected_y = controller.position

                # ------------------------------------------------
                # Logging
                # ------------------------------------------------

                if (
                    logging_enabled
                    and telemetry_interval is not None
                    and (current_time - last_telemetry_time >= telemetry_interval)
                ):
                    last_telemetry_time = current_time

                    speed = math.hypot(
                        velocity_x,
                        velocity_y,
                    )

                    logger.debug(
                        "physics | "
                        "mode=%s | "
                        "cursor=(%.1f, %.1f) | "
                        "points=%s | "
                        "gravity=%.2f | "
                        "velocity=(%.2f, %.2f) | "
                        "speed=%.2f | "
                        "user_input=(%.2f, %.2f) | "
                        "radial_input=%.2f | "
                        "tangential_input=%.2f | ",
                        current_mode,
                        actual_x,
                        actual_y,
                        point_count,
                        gravity_strength,
                        velocity_x,
                        velocity_y,
                        speed,
                        user_dx,
                        user_dy,
                        radial_input,
                        tangential_input,
                    )

            else:
                expected_x, expected_y = controller.position

            # A successful frame clears the consecutive-error tracker.
            consecutive_errors = 0
            last_frame_error = ""

        except Exception as exc:
            consecutive_errors += 1

            try:
                if not last_frame_error or last_frame_error != str(exc):
                    print(f"An error has occurred: {exc}.")

                    print("Skipping frame.")

                elif telemetry_interval is not None and (
                    current_time - last_telemetry_time >= telemetry_interval
                ):
                    print(f"An error is still occurring: {exc}.")

                if consecutive_errors >= 5:
                    print("Too many consecutive errors: " f"{consecutive_errors}")

                    print("Exiting...")

                    if logging_enabled:
                        logger.info("EXIT | Error Override")

                    shutdown()

                last_frame_error = str(exc)

                if (
                    logging_enabled
                    and telemetry_interval is not None
                    and (current_time - last_telemetry_time >= telemetry_interval)
                ):
                    last_telemetry_time = current_time

                    logger.error(
                        "An ERROR occurred: %s",
                        exc,
                        exc_info=True,
                    )
            except Exception as e:
                print(
                    f"An error: {e} - has occurred during the error handling code. Oh the irony."
                )
                raise e

        finally:
            # Account for time already spent calculating the frame instead
            # of always sleeping a full frame duration afterward.
            frame_interval = 1.0 / max(config.fps, 1)

            elapsed = time.perf_counter() - frame_start

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


def main():
    global tray_icon
    global listener
    global tk_root
    global settings_ui

    # Don't need this, just initialize with first section name
    # # section = ""

    # LOGGING STARTUP
    section = "Logging Startup"

    try:
        if config.logging_enabled_by_default:
            start_logging()
    except Exception as exc:
        print(f"Error {exc} happened during: {section}")

    # MOUSE LISTENER INITIALIZATION
    section = "Mouse Listener Initialization"

    try:
        listener = mouse.Listener(
            on_click=on_click,
        )

        listener.start()
    except Exception as exc:
        print(f"Error {exc} happened during: {section}")

    # PHYSICS THREAD INITIALIZATION
    section = "Physics Thread Initialization"

    try:
        physics_thread = threading.Thread(
            target=gravity_loop,
            daemon=True,
            name="MouseGravityPhysics",
        )

        physics_thread.start()
    except Exception as exc:
        print(f"Error {exc} happened during: {section}")

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
            set_gravity_mode_callback=set_gravity_mode,
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
        print(f"Error {exc} happened during: {section}")

    # SYSTEM TRAY ICON POPULATION
    section = "Tray Icon Population"

    try:
        tray_icon = pystray.Icon(
            "mouse_gravity",
            create_vortex_icon(),
            "Mouse Gravity: ACTIVE | Mode: SINGLE",
            menu=pystray.Menu(
                pystray.MenuItem(
                    "Mouse Gravity: ACTIVE",
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
        print(f"Error {exc} happened during: {section}")

    try:
        tk_root.mainloop()

    finally:
        running.clear()

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

        print("Mouse Gravity stopped.")


if __name__ == "__main__":
    main()
