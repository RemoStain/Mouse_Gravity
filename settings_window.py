"""
Settings window for the Mouse Gravity application.

This module contains the Tkinter interface used to:

- Edit runtime configuration values.
- Load and review gravity presets.
- Reset settings to defaults.
- Save candidate presets to the log.
- Switch between single-point and multi-point gravity modes.
- Clear placed gravity points.
- Schedule N-body gravity presets after a configurable delay.

The settings window communicates with gravity_mouse.py through callbacks.
This avoids importing gravity_mouse.py here and prevents circular imports.
"""

import tkinter as tk
from tkinter import messagebox, simpledialog, ttk

from config import (
    config,
    MAX_GRAVITY_POINTS,
    PRESETS,
    MouseGravityConfig,
)


# ------------------------------------------------------------
# Settings fields
# ------------------------------------------------------------

# Settings displayed in classic single-target mode.
CLASSIC_FIELDS = [
    "gravity",
    # "reference_distance",
    "gravity_distance_power",
    "min_gravity_distance",
    "max_gravity_acceleration",
    "max_speed",
    "drag",
    "stop_radius",
    "fps",
    # "normal_input_strength",
    # "toward_input_multiplier",
    # "away_input_multiplier",
    # "click_sequence_timeout",
    # "log_telemetry_hz",
]


# Settings displayed in multi-point / N-body mode.
MULTI_FIELDS = [
    *CLASSIC_FIELDS,
    "multi_point_count",
    "point_gravity_multiplier",
    "point_drag",
    "point_max_speed",
    "triangle_spawn_radius",
    "pentagram_spawn_radius",
    "n_body_spawn_delay",
]


# ------------------------------------------------------------
# UI colors
# ------------------------------------------------------------

PRESET_NORMAL_BG = "#f0f0f0"
PRESET_SELECTED_BG = "#d6c4f0"

APPLY_NORMAL_BG = "#f0f0f0"
APPLY_DIRTY_BG = "#fff2a8"

BUTTON_ACTIVE_BG = "#e2e2e2"


class SettingsWindow:
    """
    Tkinter settings window for Mouse Gravity.

    The window has two gravity layouts:

    1. Single-point gravity.
    2. Multi-point / N-body gravity.

    Runtime simulation operations are handled through callbacks supplied
    by gravity_mouse.py. This keeps the UI separate from the physics
    implementation and avoids circular imports.

    Args:
        root:
            Hidden Tkinter root window.

        state_lock:
            Lock used to safely update shared runtime configuration.

        logger:
            Application logger.

        save_preset_callback:
            Callback used to save a user-created preset to the log.

        set_gravity_mode_callback:
            Callback used to switch between "single" and "multi" modes.

        clear_gravity_points_callback:
            Callback used to remove all placed multi-point gravity sources.

        get_point_status_callback:
            Callback returning:
                (points_placed, configured_point_limit)

        spawn_triangle_callback:
            Callback that immediately spawns an equilateral triangle of
            gravity points around the cursor's current position.

        spawn_pentagram_callback:
            Callback that immediately spawns five gravity points around
            the cursor's current position.
    """

    def __init__(
        self,
        root,
        state_lock,
        logger,
        save_preset_callback,
        set_gravity_mode_callback,
        clear_gravity_points_callback,
        get_point_status_callback,
        spawn_triangle_callback,
        spawn_pentagram_callback,
    ):
        self.root = root
        self.state_lock = state_lock
        self.logger = logger

        # ----------------------------------------------------
        # Runtime callbacks
        # ----------------------------------------------------

        self.save_preset_callback = save_preset_callback

        self.set_gravity_mode_callback = (
            set_gravity_mode_callback
        )

        self.clear_gravity_points_callback = (
            clear_gravity_points_callback
        )

        self.get_point_status_callback = (
            get_point_status_callback
        )

        self.spawn_triangle_callback = (
            spawn_triangle_callback
        )

        self.spawn_pentagram_callback = (
            spawn_pentagram_callback
        )

        # ----------------------------------------------------
        # UI state
        # ----------------------------------------------------

        self.variables = {}
        self.preset_buttons = {}

        self.selected_preset = None

        self.apply_button = None

        self.dirty = False

        self.gravity_mode = "single"

        # Tkinter after() identifier for a pending N-body spawn.
        #
        # Only one N-body spawn timer is allowed at a time. If another
        # preset button is pressed, the existing timer is cancelled.
        self.n_body_spawn_after_id = None

        # ----------------------------------------------------
        # Window
        # ----------------------------------------------------

        self.window = tk.Toplevel(
            root
        )

        self.window.title(
            "Mouse Gravity Settings"
        )

        self.loaded_preset_var = (
            tk.StringVar(
                value="Preset: None"
            )
        )

        self.point_status_var = (
            tk.StringVar(
                value="Points placed: 0"
            )
        )

        self.n_body_status_var = (
            tk.StringVar(
                value=""
            )
        )

        self.window.protocol(
            "WM_DELETE_WINDOW",
            self.hide,
        )

        self._build()

        self._refresh_point_status()

    # --------------------------------------------------------
    # Build window
    # --------------------------------------------------------

    def _build(self):
        """
        Build the complete settings window.

        The mode-specific settings section is rebuilt whenever the user
        switches between single-point and multi-point gravity.

        Presets and the Apply / Close controls remain visible in both modes.
        """

        self.main_frame = ttk.Frame(
            self.window,
            padding=15,
        )

        self.main_frame.pack(
            fill="both",
            expand=True,
        )

        # ----------------------------------------------------
        # Title
        # ----------------------------------------------------

        ttk.Label(
            self.main_frame,
            text="Mouse Gravity Settings",
            font=(
                "TkDefaultFont",
                12,
                "bold",
            ),
        ).pack(
            pady=(0, 10),
        )

        # ----------------------------------------------------
        # Gravity mode switch
        # ----------------------------------------------------

        self.mode_button = ttk.Button(
            self.main_frame,
            text="Switch to Multi-Point Gravity",
            command=self.toggle_gravity_layout,
        )

        self.mode_button.pack(
            fill="x",
            pady=(0, 10),
        )

        # This frame contains the settings layout for the currently
        # selected gravity mode.
        self.layout_frame = ttk.Frame(
            self.main_frame,
        )

        self.layout_frame.pack(
            fill="both",
            expand=True,
        )

        self._build_settings_layout(
            CLASSIC_FIELDS
        )

        # ----------------------------------------------------
        # Bottom controls
        # ----------------------------------------------------

        bottom_frame = ttk.Frame(
            self.window,
            padding=(
                15,
                0,
                15,
                15,
            ),
        )

        bottom_frame.pack(
            fill="x",
        )

        # ----------------------------------------------------
        # Presets
        # ----------------------------------------------------

        preset_frame = ttk.LabelFrame(
            bottom_frame,
            text="Presets",
            padding=8,
        )

        preset_frame.pack(
            fill="x",
            pady=(8, 4),
        )

        # Preset buttons can exceed the width of the settings window.
        # A horizontal canvas keeps them on a single row.
        preset_canvas = tk.Canvas(
            preset_frame,
            height=42,
            highlightthickness=0,
        )

        preset_scrollbar = ttk.Scrollbar(
            preset_frame,
            orient="horizontal",
            command=preset_canvas.xview,
        )

        preset_buttons_frame = ttk.Frame(
            preset_canvas,
        )

        preset_canvas.create_window(
            (0, 0),
            window=preset_buttons_frame,
            anchor="nw",
        )

        preset_buttons_frame.bind(
            "<Configure>",
            lambda event: preset_canvas.configure(
                scrollregion=(
                    preset_canvas.bbox(
                        "all"
                    )
                )
            ),
        )

        preset_canvas.configure(
            xscrollcommand=(
                preset_scrollbar.set
            ),
        )

        preset_canvas.pack(
            fill="x",
            expand=True,
        )

        preset_scrollbar.pack(
            fill="x",
            pady=(2, 4),
        )

        for preset_name in PRESETS:
            button = tk.Button(
                preset_buttons_frame,
                text=preset_name,
                bg=PRESET_NORMAL_BG,
                activebackground=BUTTON_ACTIVE_BG,
                relief="raised",
                command=lambda name=preset_name: (
                    self.load_preset(name)
                ),
            )

            button.pack(
                side="left",
                padx=4,
                pady=2,
            )

            self.preset_buttons[
                preset_name
            ] = button

        # ----------------------------------------------------
        # Preset utility controls
        # ----------------------------------------------------

        preset_utility_frame = ttk.Frame(
            preset_frame,
        )

        preset_utility_frame.pack(
            fill="x",
            pady=(4, 0),
        )

        self.defaults_button = tk.Button(
            preset_utility_frame,
            text="Defaults",
            command=self.reset_to_defaults,
            bg=PRESET_NORMAL_BG,
            activebackground=BUTTON_ACTIVE_BG,
        )

        self.defaults_button.pack(
            side="left",
            padx=(4, 8),
        )

        ttk.Button(
            preset_utility_frame,
            text="Save Preset to Log",
            command=self.save_preset_to_log,
        ).pack(
            side="left",
            padx=4,
        )

        ttk.Label(
            bottom_frame,
            textvariable=(
                self.loaded_preset_var
            ),
        ).pack(
            pady=(2, 8),
        )

        # ----------------------------------------------------
        # Apply / Close
        # ----------------------------------------------------

        action_frame = ttk.Frame(
            bottom_frame,
        )

        action_frame.pack(
            fill="x",
        )

        self.apply_button = tk.Button(
            action_frame,
            text="Apply",
            command=self.apply,
            bg=APPLY_NORMAL_BG,
            activebackground=BUTTON_ACTIVE_BG,
        )

        self.apply_button.pack(
            side="left",
        )

        ttk.Button(
            action_frame,
            text="Close",
            command=self.hide,
        ).pack(
            side="right",
        )

    def _build_settings_layout(
        self,
        fields,
    ):
        """
        Rebuild the scrollable settings section.

        Args:
            fields:
                Iterable of config attribute names to display.
        """

        # Remove the previous mode-specific layout.
        for widget in (
            self.layout_frame.winfo_children()
        ):
            widget.destroy()

        # ----------------------------------------------------
        # Scrollable settings area
        # ----------------------------------------------------

        canvas = tk.Canvas(
            self.layout_frame,
            highlightthickness=0,
        )

        scrollbar = ttk.Scrollbar(
            self.layout_frame,
            orient="vertical",
            command=canvas.yview,
        )

        self.settings_frame = ttk.Frame(
            canvas,
        )

        self.settings_frame.bind(
            "<Configure>",
            lambda event: canvas.configure(
                scrollregion=(
                    canvas.bbox(
                        "all"
                    )
                )
            ),
        )

        canvas_window = (
            canvas.create_window(
                (0, 0),
                window=self.settings_frame,
                anchor="nw",
            )
        )

        # Keep the settings frame the same width as the visible canvas.
        canvas.bind(
            "<Configure>",
            lambda event: (
                canvas.itemconfigure(
                    canvas_window,
                    width=event.width,
                )
            ),
        )

        canvas.configure(
            yscrollcommand=(
                scrollbar.set
            ),
        )

        canvas.pack(
            side="left",
            fill="both",
            expand=True,
        )

        scrollbar.pack(
            side="right",
            fill="y",
        )

        row = 0

        # ----------------------------------------------------
        # Multi-point controls
        # ----------------------------------------------------

        if self.gravity_mode == "multi":
            row = (
                self._build_multi_point_controls(
                    row
                )
            )

        # ----------------------------------------------------
        # Config fields
        # ----------------------------------------------------

        for field_name in fields:
            self._create_setting_row(
                field_name,
                row,
            )

            row += 1

    def _build_multi_point_controls(
        self,
        row,
    ):
        """
        Build controls specific to multi-point and N-body gravity.

        Args:
            row:
                Starting grid row.

        Returns:
            int:
                The next unused grid row.
        """

        # ----------------------------------------------------
        # Multi-point heading
        # ----------------------------------------------------

        ttk.Label(
            self.settings_frame,
            text="Multi-Point Gravity",
            font=(
                "TkDefaultFont",
                11,
                "bold",
            ),
        ).grid(
            row=row,
            column=0,
            columnspan=2,
            sticky="w",
            padx=5,
            pady=(4, 8),
        )

        row += 1

        ttk.Label(
            self.settings_frame,
            text=(
                "Double-click to place up to "
                f"{MAX_GRAVITY_POINTS} points. "
                "Points weakly attract each other."
            ),
            wraplength=420,
            justify="left",
        ).grid(
            row=row,
            column=0,
            columnspan=2,
            sticky="w",
            padx=5,
            pady=(0, 6),
        )

        row += 1

        # ----------------------------------------------------
        # Point status
        # ----------------------------------------------------

        ttk.Label(
            self.settings_frame,
            textvariable=(
                self.point_status_var
            ),
        ).grid(
            row=row,
            column=0,
            columnspan=2,
            sticky="w",
            padx=5,
            pady=(0, 6),
        )

        row += 1

        ttk.Button(
            self.settings_frame,
            text="Clear Gravity Points",
            command=(
                self.clear_gravity_points_callback
            ),
        ).grid(
            row=row,
            column=0,
            columnspan=2,
            sticky="w",
            padx=5,
            pady=(0, 10),
        )

        row += 1

        # ----------------------------------------------------
        # N-body presets
        # ----------------------------------------------------

        ttk.Label(
            self.settings_frame,
            text="N-Body Presets",
            font=(
                "TkDefaultFont",
                10,
                "bold",
            ),
        ).grid(
            row=row,
            column=0,
            columnspan=2,
            sticky="w",
            padx=5,
            pady=(4, 4),
        )

        row += 1

        ttk.Label(
            self.settings_frame,
            text=(
                "Press a preset, then move the cursor "
                "to the desired center position before "
                "the spawn timer expires."
            ),
            wraplength=420,
            justify="left",
        ).grid(
            row=row,
            column=0,
            columnspan=2,
            sticky="w",
            padx=5,
            pady=(0, 6),
        )

        row += 1

        # ----------------------------------------------------
        # N-body preset buttons
        # ----------------------------------------------------

        n_body_button_frame = (
            ttk.Frame(
                self.settings_frame
            )
        )

        n_body_button_frame.grid(
            row=row,
            column=0,
            columnspan=2,
            sticky="w",
            padx=5,
            pady=(0, 6),
        )

        ttk.Button(
            n_body_button_frame,
            text="Equilateral Triangle",
            command=lambda: (
                self.schedule_n_body_spawn(
                    "Equilateral Triangle",
                    self.spawn_triangle_callback,
                )
            ),
        ).pack(
            side="left",
            padx=(0, 5),
        )

        ttk.Button(
            n_body_button_frame,
            text="Pentagram",
            command=lambda: (
                self.schedule_n_body_spawn(
                    "Pentagram",
                    self.spawn_pentagram_callback,
                )
            ),
        ).pack(
            side="left",
            padx=5,
        )

        row += 1

        # Displays countdown/spawn status.
        ttk.Label(
            self.settings_frame,
            textvariable=(
                self.n_body_status_var
            ),
        ).grid(
            row=row,
            column=0,
            columnspan=2,
            sticky="w",
            padx=5,
            pady=(0, 10),
        )

        # row += 1

        ttk.Button(
            n_body_button_frame,
            text="Abort",
            command=lambda: (
                self.cancel_n_body_spawn(
                    True
                )
            ),
        ).pack(
            side="right",
            padx=5,
        )

        row += 1

        ttk.Separator(
            self.settings_frame,
            orient="horizontal",
        ).grid(
            row=row,
            column=0,
            columnspan=2,
            sticky="ew",
            padx=5,
            pady=(0, 8),
        )

        return row + 1

    # --------------------------------------------------------
    # Gravity mode
    # --------------------------------------------------------

    def toggle_gravity_layout(self):
        """
        Switch between single-point and multi-point gravity.

        Existing gravity targets are cleared by the runtime mode callback.

        Any pending N-body spawn is cancelled when switching modes.
        """

        self.cancel_n_body_spawn()

        if self.gravity_mode == "single":
            self.gravity_mode = "multi"

            self.mode_button.configure(
                text=(
                    "Switch to "
                    "Single-Point Gravity"
                )
            )

            self.set_gravity_mode_callback(
                "multi"
            )

            self._build_settings_layout(
                MULTI_FIELDS
            )

        else:
            self.gravity_mode = "single"

            self.mode_button.configure(
                text=(
                    "Switch to "
                    "Multi-Point Gravity"
                )
            )

            self.set_gravity_mode_callback(
                "single"
            )

            self._build_settings_layout(
                CLASSIC_FIELDS
            )

        self.reload()

    # --------------------------------------------------------
    # N-body spawn scheduling
    # --------------------------------------------------------

    def schedule_n_body_spawn(
        self,
        preset_name,
        callback,
    ):
        """
        Schedule an N-body preset after the configured delay.

        The cursor position is not captured when the button is pressed.
        The runtime callback reads the cursor position when the timer
        finishes, allowing the user to move the cursor during the delay.

        If another N-body preset is already waiting, it is cancelled.

        Args:
            preset_name:
                Human-readable name displayed in the status label.

            callback:
                Runtime function that performs the actual spawn.
        """

        # Read directly from the entry rather than config.
        #
        # This lets the user change the timer and immediately press an
        # N-body button without having to press Apply first.
        delay_variable = (
            self.variables.get(
                "n_body_spawn_delay"
            )
        )

        if delay_variable is None:
            delay_seconds = (
                config.n_body_spawn_delay
            )

        else:
            try:
                delay_seconds = float(
                    delay_variable.get()
                )

            except ValueError:
                messagebox.showerror(
                    "Invalid Spawn Delay",
                    (
                        "N Body Spawn Delay "
                        "must be a valid number."
                    ),
                    parent=self.window,
                )

                return

        if delay_seconds < 0:
            messagebox.showerror(
                "Invalid Spawn Delay",
                (
                    "N Body Spawn Delay "
                    "cannot be negative."
                ),
                parent=self.window,
            )

            return

        # Only one delayed N-body spawn can be active.
        self.cancel_n_body_spawn(
            clear_status=False
        )

        delay_ms = round(
            delay_seconds * 1000
        )

        self.n_body_status_var.set(
            f"{preset_name} spawning in "
            f"{delay_seconds:g} seconds..."
        )

        self.n_body_spawn_after_id = (
            self.window.after(
                delay_ms,
                lambda: (
                    self._run_n_body_spawn(
                        preset_name,
                        callback,
                    )
                ),
            )
        )

        self.logger.info(
            "N_BODY_SPAWN_SCHEDULED | "
            "preset=%s | delay=%s",
            preset_name,
            delay_seconds,
        )

    def _run_n_body_spawn(
        self,
        preset_name,
        callback,
    ):
        """
        Execute a scheduled N-body spawn.

        Args:
            preset_name:
                Human-readable preset name.

            callback:
                Runtime spawn callback.
        """

        # The scheduled timer has completed.
        self.n_body_spawn_after_id = None

        try:
            callback()

        except Exception as exc:
            self.logger.error(
                "N_BODY_SPAWN_ERROR | "
                "preset=%s | error=%s",
                preset_name,
                exc,
                exc_info=True,
            )

            self.n_body_status_var.set(
                f"{preset_name} failed to spawn."
            )

            messagebox.showerror(
                "N-Body Spawn Error",
                str(exc),
                parent=self.window,
            )

            return

        self.n_body_status_var.set(
            f"{preset_name} spawned."
        )

        self.logger.info(
            "N_BODY_SPAWN_COMPLETE | "
            "preset=%s",
            preset_name,
        )

    def cancel_n_body_spawn(
        self,
        clear_status=True,
    ):
        """
        Cancel a pending N-body spawn timer.

        Args:
            clear_status:
                If True, clear the N-body status label.
        """

        if (
            self.n_body_spawn_after_id
            is not None
        ):
            try:
                self.window.after_cancel(
                    self.n_body_spawn_after_id
                )

            except tk.TclError:
                pass

            self.n_body_spawn_after_id = (
                None
            )

            self.logger.info(
                "N_BODY_SPAWN_CANCELLED"
            )

        if clear_status:
            self.n_body_status_var.set(
                ""
            )

    # --------------------------------------------------------
    # Preset / dirty state
    # --------------------------------------------------------

    def _highlight_preset(
        self,
        preset_name,
    ):
        """
        Highlight the selected configuration preset.

        Args:
            preset_name:
                Name of the selected preset.
        """

        self.selected_preset = (
            preset_name
        )

        for (
            name,
            button,
        ) in self.preset_buttons.items():

            if name == preset_name:
                button.configure(
                    bg=PRESET_SELECTED_BG,
                    relief="sunken",
                )

            else:
                button.configure(
                    bg=PRESET_NORMAL_BG,
                    relief="raised",
                )

        self.defaults_button.configure(
            bg=PRESET_NORMAL_BG,
            relief="raised",
        )

    def _mark_dirty(
        self,
        *args,
    ):
        """
        Update the Apply button when fields differ from config.

        Tkinter variable traces provide positional arguments, so *args is
        accepted even though those values are not needed.
        """

        has_changes = False

        for (
            field_name,
            variable,
        ) in self.variables.items():

            try:
                input_value = (
                    self._convert_value(
                        field_name,
                        variable.get(),
                    )
                )

            except ValueError:
                # Invalid text is still an unapplied change.
                has_changes = True
                break

            current_value = getattr(
                config,
                field_name,
            )

            if (
                input_value
                != current_value
            ):
                has_changes = True
                break

        self.dirty = has_changes

        if self.apply_button is not None:
            self.apply_button.configure(
                bg=(
                    APPLY_DIRTY_BG
                    if has_changes
                    else APPLY_NORMAL_BG
                ),
                relief="raised",
            )

        if has_changes:
            self.selected_preset = None

            for button in (
                self.preset_buttons.values()
            ):
                button.configure(
                    bg=PRESET_NORMAL_BG,
                    relief="raised",
                )

            if hasattr(
                self,
                "defaults_button",
            ):
                self.defaults_button.configure(
                    bg=PRESET_NORMAL_BG,
                    relief="raised",
                )

            self.loaded_preset_var.set(
                "Preset: Custom"
            )

    # --------------------------------------------------------
    # Settings fields
    # --------------------------------------------------------

    def _create_setting_row(
        self,
        field_name,
        row,
    ):
        """
        Create one label and entry for a config setting.

        Args:
            field_name:
                Attribute name on config.

            row:
                Grid row where the controls are placed.

        Raises:
            AttributeError:
                If the requested field does not exist on config.
        """

        if not hasattr(
            config,
            field_name,
        ):
            raise AttributeError(
                (
                    "Config has no setting named "
                    f"{field_name!r}"
                )
            )

        # Keep StringVars when rebuilding layouts so typed values are not
        # lost just because the user switches gravity modes.
        if (
            field_name
            not in self.variables
        ):
            variable = tk.StringVar(
                value=str(
                    getattr(
                        config,
                        field_name,
                    )
                ),
            )

            variable.trace_add(
                "write",
                self._mark_dirty,
            )

            self.variables[
                field_name
            ] = variable

        variable = self.variables[
            field_name
        ]

        display_name = (
            field_name
            .replace("_", " ")
            .title()
        )

        ttk.Label(
            self.settings_frame,
            text=display_name,
        ).grid(
            row=row,
            column=0,
            sticky="w",
            padx=5,
            pady=4,
        )

        ttk.Entry(
            self.settings_frame,
            textvariable=variable,
            width=18,
        ).grid(
            row=row,
            column=1,
            sticky="ew",
            padx=5,
            pady=4,
        )

        self.settings_frame.columnconfigure(
            1,
            weight=1,
        )

    def _convert_value(
        self,
        field_name,
        text,
    ):
        """
        Convert entry text to the config field's existing type.

        Args:
            field_name:
                Config attribute being converted.

            text:
                Raw text from the Tkinter entry.

        Returns:
            Value converted to the config field's type.

        Raises:
            ValueError:
                If the value cannot be converted.
        """

        current_value = getattr(
            config,
            field_name,
        )

        expected_type = type(
            current_value
        )

        if expected_type is bool:
            normalized = (
                text
                .strip()
                .lower()
            )

            if normalized in {
                "true",
                "1",
                "yes",
                "on",
            }:
                return True

            if normalized in {
                "false",
                "0",
                "no",
                "off",
            }:
                return False

            raise ValueError(
                (
                    f"{field_name} must be "
                    "true or false"
                )
            )

        try:
            return expected_type(
                text
            )

        except ValueError as exc:
            raise ValueError(
                (
                    f"{field_name} must be a valid "
                    f"{expected_type.__name__}"
                )
            ) from exc

    # --------------------------------------------------------
    # Presets
    # --------------------------------------------------------

    def load_preset(
        self,
        preset_name,
    ):
        """
        Load a configuration preset into the input fields.

        Loading a preset does not immediately update the runtime config.
        The user must press Apply.

        Args:
            preset_name:
                Name of the preset in PRESETS.
        """

        preset = PRESETS.get(
            preset_name
        )

        if preset is None:
            return

        for (
            field_name,
            value,
        ) in preset.items():

            if (
                field_name
                not in self.variables
            ):
                continue

            self.variables[
                field_name
            ].set(
                str(value)
            )

        self.logger.info(
            "PRESET_LOADED | preset=%s",
            preset_name,
        )

        self.loaded_preset_var.set(
            f"Preset: {preset_name}"
        )

        self._highlight_preset(
            preset_name
        )

    def reset_to_defaults(self):
        """
        Load MouseGravityConfig default values into the input fields.

        The defaults are not applied to the simulation until Apply is pressed.
        """

        defaults = (
            MouseGravityConfig()
        )

        for (
            field_name,
            variable,
        ) in self.variables.items():

            if not hasattr(
                defaults,
                field_name,
            ):
                continue

            variable.set(
                str(
                    getattr(
                        defaults,
                        field_name,
                    )
                )
            )

        self.loaded_preset_var.set(
            "Preset: Defaults"
        )

        self.logger.info(
            "DEFAULTS_LOADED"
        )

        self.selected_preset = (
            "Defaults"
        )

        for button in (
            self.preset_buttons.values()
        ):
            button.configure(
                bg=PRESET_NORMAL_BG,
                relief="raised",
            )

        self.defaults_button.configure(
            bg=PRESET_SELECTED_BG,
            relief="sunken",
        )

    def save_preset_to_log(self):
        """
        Save the current settings as a candidate preset in the log.

        This does not automatically modify config.py or PRESETS.
        """

        values = {}

        try:
            for (
                field_name,
                variable,
            ) in self.variables.items():

                values[field_name] = (
                    self._convert_value(
                        field_name,
                        variable.get(),
                    )
                )

        except ValueError as exc:
            messagebox.showerror(
                "Invalid Setting",
                str(exc),
                parent=self.window,
            )

            return

        preset_name = (
            simpledialog.askstring(
                "Save Preset",
                (
                    "Enter a name "
                    "for this preset:"
                ),
                parent=self.window,
            )
        )

        if preset_name is None:
            return

        preset_name = (
            preset_name.strip()
        )

        if not preset_name:
            messagebox.showerror(
                "Invalid Preset Name",
                (
                    "Preset name "
                    "cannot be empty."
                ),
                parent=self.window,
            )

            return

        self.save_preset_callback(
            preset_name,
            values,
        )

        self.loaded_preset_var.set(
            (
                "Saved for review: "
                f"{preset_name}"
            )
        )

        messagebox.showinfo(
            "Preset Saved",
            (
                f'"{preset_name}" was saved '
                "to the log for later review."
            ),
            parent=self.window,
        )

    # --------------------------------------------------------
    # Apply / reload
    # --------------------------------------------------------

    def apply(self):
        """
        Validate and apply all settings currently stored in the UI.

        Multi-point and N-body-specific settings receive additional
        validation before the shared config object is changed.
        """

        new_values = {}

        try:
            for (
                field_name,
                variable,
            ) in self.variables.items():

                new_values[field_name] = (
                    self._convert_value(
                        field_name,
                        variable.get(),
                    )
                )

        except ValueError as exc:
            messagebox.showerror(
                "Invalid Setting",
                str(exc),
                parent=self.window,
            )

            return

        # ----------------------------------------------------
        # Multi-point validation
        # ----------------------------------------------------

        point_count = new_values.get(
            "multi_point_count",
            config.multi_point_count,
        )

        if not (
            1
            <= point_count
            <= MAX_GRAVITY_POINTS
        ):
            messagebox.showerror(
                "Invalid Setting",
                (
                    "Multi Point Count must be "
                    f"between 1 and "
                    f"{MAX_GRAVITY_POINTS}."
                ),
                parent=self.window,
            )

            return

        point_gravity_multiplier = (
            new_values.get(
                "point_gravity_multiplier",
                config.point_gravity_multiplier,
            )
        )

        if (
            point_gravity_multiplier
            < 0
        ):
            messagebox.showerror(
                "Invalid Setting",
                (
                    "Point Gravity Multiplier "
                    "cannot be negative."
                ),
                parent=self.window,
            )

            return

        triangle_radius = (
            new_values.get(
                "triangle_spawn_radius",
                config.triangle_spawn_radius,
            )
        )

        if triangle_radius < 0:
            messagebox.showerror(
                "Invalid Setting",
                (
                    "Triangle Spawn Radius "
                    "cannot be negative."
                ),
                parent=self.window,
            )

            return

        pentagram_radius = (
            new_values.get(
                "pentagram_spawn_radius",
                config.pentagram_spawn_radius,
            )
        )

        if pentagram_radius < 0:
            messagebox.showerror(
                "Invalid Setting",
                (
                    "Pentagram Spawn Radius "
                    "cannot be negative."
                ),
                parent=self.window,
            )

            return

        spawn_delay = new_values.get(
            "n_body_spawn_delay",
            config.n_body_spawn_delay,
        )

        if spawn_delay < 0:
            messagebox.showerror(
                "Invalid Setting",
                (
                    "N Body Spawn Delay "
                    "cannot be negative."
                ),
                parent=self.window,
            )

            return

        # ----------------------------------------------------
        # Apply changes
        # ----------------------------------------------------

        with self.state_lock:
            for (
                field_name,
                new_value,
            ) in new_values.items():

                old_value = getattr(
                    config,
                    field_name,
                )

                if (
                    old_value
                    == new_value
                ):
                    continue

                setattr(
                    config,
                    field_name,
                    new_value,
                )

                self.logger.info(
                    (
                        "CONFIG_CHANGE | "
                        "%s | old=%s | new=%s"
                    ),
                    field_name,
                    old_value,
                    new_value,
                )

        self.dirty = False

        if (
            self.apply_button
            is not None
        ):
            self.apply_button.configure(
                bg=APPLY_NORMAL_BG,
                relief="raised",
            )

    def reload(self):
        """
        Reload all existing UI variables from the active config object.
        """

        with self.state_lock:
            for (
                field_name,
                variable,
            ) in self.variables.items():

                variable.set(
                    str(
                        getattr(
                            config,
                            field_name,
                        )
                    )
                )

        self.dirty = False

        if (
            self.apply_button
            is not None
        ):
            self.apply_button.configure(
                bg=APPLY_NORMAL_BG,
                relief="raised",
            )

    # --------------------------------------------------------
    # Point status
    # --------------------------------------------------------

    def _refresh_point_status(self):
        """
        Periodically update the number of placed gravity points.

        This information does not require physics-frame-frequency updates,
        so it refreshes twice per second to reduce UI work.
        """

        try:
            (
                placed,
                limit,
            ) = (
                self.get_point_status_callback()
            )

            self.point_status_var.set(
                (
                    "Points placed: "
                    f"{placed}/{limit}"
                )
            )

            self.window.after(
                500,
                self._refresh_point_status,
            )

        except tk.TclError:
            # The Tk root may already be shutting down.
            pass

    # --------------------------------------------------------
    # Show / hide
    # --------------------------------------------------------

    def show(self):
        """
        Reload current values and display the settings window.
        """

        self.reload()

        self.window.deiconify()

        self.window.lift()

        self.window.focus_force()

    def hide(self):
        """
        Hide the settings window without destroying it.

        A pending N-body spawn is intentionally not cancelled here. This
        allows the user to press a preset button, hide the settings window,
        move the cursor to the desired location, and allow the timer to finish.
        """

        self.window.withdraw()