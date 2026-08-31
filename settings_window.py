"""
Settings window for the gravity-point N-body application.

This module provides the Tkinter interface used to:

- Edit gravity-point runtime configuration.
- Load predefined N-body physics presets.
- Reset settings to defaults.
- Save candidate presets to the application log.
- Clear currently placed gravity points.
- Schedule triangle and pentagram point-placement presets.

The settings window communicates with gravity_mouse.py exclusively through
callbacks. This keeps UI code separate from runtime simulation code and
avoids circular imports.
"""

import tkinter as tk
from tkinter import messagebox, simpledialog, ttk

from config import (
    GravityConfig,
    MAX_GRAVITY_POINTS,
    PRESETS,
    config,
)


# ------------------------------------------------------------
# Settings fields
# ------------------------------------------------------------

N_BODY_FIELDS = [
    "point_gravity",
    "reference_distance",
    "gravity_distance_power",
    "min_gravity_distance",
    "max_gravity_acceleration",
    "body_stop_radius",
    "multi_point_count",
    "point_drag",
    "point_max_speed",
    "point_physics_hz",
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
    Tkinter settings window for the N-body gravity-point simulation.

    The application has only one simulation mode. Mouse input is used for
    placing gravity points and selecting preset centers, but the simulation
    never programmatically moves the cursor.

    Args:
        root:
            Hidden Tkinter root window.

        state_lock:
            Lock protecting shared runtime configuration and gravity state.

        logger:
            Application logger.

        save_preset_callback:
            Callback used to write a candidate user preset to the log.

        clear_gravity_points_callback:
            Callback used to remove all active gravity points.

        get_point_status_callback:
            Callback returning ``(points_placed, configured_point_limit)``.

        spawn_triangle_callback:
            Callback that spawns three points in an equilateral triangle
            around the cursor's current position.

        spawn_pentagram_callback:
            Callback that spawns five points around the cursor's current
            position.
    """

    def __init__(
        self,
        root,
        state_lock,
        logger,
        save_preset_callback,
        clear_gravity_points_callback,
        get_point_status_callback,
        spawn_triangle_callback,
        spawn_pentagram_callback,
    ):
        self.root = root
        self.state_lock = state_lock
        self.logger = logger

        self.save_preset_callback = save_preset_callback
        self.clear_gravity_points_callback = clear_gravity_points_callback
        self.get_point_status_callback = get_point_status_callback
        self.spawn_triangle_callback = spawn_triangle_callback
        self.spawn_pentagram_callback = spawn_pentagram_callback

        self.variables = {}
        self.preset_buttons = {}
        self.selected_preset = None
        self.apply_button = None
        self.dirty = False

        # Tkinter after() identifier for a pending N-body preset spawn.
        # Only one delayed spawn may be active at a time.
        self.n_body_spawn_after_id = None

        self.window = tk.Toplevel(root)
        self.window.title("N-Body Gravity Settings")

        self.loaded_preset_var = tk.StringVar(
            value="Preset: None"
        )

        self.point_status_var = tk.StringVar(
            value="Points placed: 0"
        )

        self.n_body_status_var = tk.StringVar(
            value=""
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
        Build the complete N-body settings window.
        """
        self.main_frame = ttk.Frame(
            self.window,
            padding=15,
        )

        self.main_frame.pack(
            fill="both",
            expand=True,
        )

        ttk.Label(
            self.main_frame,
            text="N-Body Gravity Settings",
            font=(
                "TkDefaultFont",
                12,
                "bold",
            ),
        ).pack(
            pady=(0, 10),
        )

        self.layout_frame = ttk.Frame(
            self.main_frame,
        )

        self.layout_frame.pack(
            fill="both",
            expand=True,
        )

        self._build_settings_layout()

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
            text="Physics Presets",
            padding=8,
        )

        preset_frame.pack(
            fill="x",
            pady=(8, 4),
        )

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
                scrollregion=preset_canvas.bbox("all")
            ),
        )

        preset_canvas.configure(
            xscrollcommand=preset_scrollbar.set,
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
                command=lambda name=preset_name: self.load_preset(name),
            )

            button.pack(
                side="left",
                padx=4,
                pady=2,
            )

            self.preset_buttons[preset_name] = button

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
            textvariable=self.loaded_preset_var,
        ).pack(
            pady=(2, 8),
        )

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

    def _build_settings_layout(self):
        """
        Build the scrollable point controls and configuration fields.
        """
        for widget in self.layout_frame.winfo_children():
            widget.destroy()

        canvas = tk.Canvas(
            self.layout_frame,
            highlightthickness=0,
        )

        scrollbar = ttk.Scrollbar(
            self.layout_frame,
            orient="vertical",
            command=canvas.yview,
        )

        self.settings_frame = ttk.Frame(canvas)

        self.settings_frame.bind(
            "<Configure>",
            lambda event: canvas.configure(
                scrollregion=canvas.bbox("all")
            ),
        )

        canvas_window = canvas.create_window(
            (0, 0),
            window=self.settings_frame,
            anchor="nw",
        )

        canvas.bind(
            "<Configure>",
            lambda event: canvas.itemconfigure(
                canvas_window,
                width=event.width,
            ),
        )

        canvas.configure(
            yscrollcommand=scrollbar.set,
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

        row = self._build_point_controls(0)

        for field_name in N_BODY_FIELDS:
            self._create_setting_row(
                field_name,
                row,
            )
            row += 1

    def _build_point_controls(self, row):
        """
        Build point-management and delayed placement-preset controls.

        Args:
            row: Starting grid row.

        Returns:
            The next unused grid row.
        """
        ttk.Label(
            self.settings_frame,
            text="Gravity Points",
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
                "Double-click to place gravity points. "
                f"A maximum of {MAX_GRAVITY_POINTS} points is supported. "
                "Triple-click clears all points; quadruple-click exits."
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

        ttk.Label(
            self.settings_frame,
            textvariable=self.point_status_var,
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
            command=self.clear_gravity_points_callback,
        ).grid(
            row=row,
            column=0,
            columnspan=2,
            sticky="w",
            padx=5,
            pady=(0, 10),
        )

        row += 1

        ttk.Label(
            self.settings_frame,
            text="Placement Presets",
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
                "Press a preset, then move the cursor to the desired "
                "center position before the spawn timer expires."
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

        button_frame = ttk.Frame(
            self.settings_frame
        )

        button_frame.grid(
            row=row,
            column=0,
            columnspan=2,
            sticky="w",
            padx=5,
            pady=(0, 6),
        )

        ttk.Button(
            button_frame,
            text="Equilateral Triangle",
            command=lambda: self.schedule_n_body_spawn(
                "Equilateral Triangle",
                self.spawn_triangle_callback,
            ),
        ).pack(
            side="left",
            padx=(0, 5),
        )

        ttk.Button(
            button_frame,
            text="Pentagram",
            command=lambda: self.schedule_n_body_spawn(
                "Pentagram",
                self.spawn_pentagram_callback,
            ),
        ).pack(
            side="left",
            padx=5,
        )

        ttk.Button(
            button_frame,
            text="Abort",
            command=lambda: self.cancel_n_body_spawn(True),
        ).pack(
            side="left",
            padx=5,
        )

        row += 1

        ttk.Label(
            self.settings_frame,
            textvariable=self.n_body_status_var,
        ).grid(
            row=row,
            column=0,
            columnspan=2,
            sticky="w",
            padx=5,
            pady=(0, 10),
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
    # N-body spawn scheduling
    # --------------------------------------------------------

    def schedule_n_body_spawn(self, preset_name, callback):
        """
        Schedule a placement preset after the configured delay.

        The cursor position is intentionally read by the runtime callback
        only when the delay finishes. This allows the user to move the
        cursor after pressing a preset button.

        Args:
            preset_name: Human-readable preset name for UI/log messages.
            callback: Runtime function that creates the point pattern.
        """
        delay_variable = self.variables.get(
            "n_body_spawn_delay"
        )

        if delay_variable is None:
            delay_seconds = config.n_body_spawn_delay
        else:
            try:
                delay_seconds = float(
                    delay_variable.get()
                )
            except ValueError:
                messagebox.showerror(
                    "Invalid Spawn Delay",
                    "N Body Spawn Delay must be a valid number.",
                    parent=self.window,
                )
                return

        if delay_seconds < 0:
            messagebox.showerror(
                "Invalid Spawn Delay",
                "N Body Spawn Delay cannot be negative.",
                parent=self.window,
            )
            return

        self.cancel_n_body_spawn(
            clear_status=False
        )

        self.n_body_status_var.set(
            f"{preset_name} spawning in {delay_seconds:g} seconds..."
        )

        self.n_body_spawn_after_id = self.window.after(
            round(delay_seconds * 1000),
            lambda: self._run_n_body_spawn(
                preset_name,
                callback,
            ),
        )

        self.logger.info(
            "N_BODY_SPAWN_SCHEDULED | preset=%s | delay=%s",
            preset_name,
            delay_seconds,
        )

    def _run_n_body_spawn(self, preset_name, callback):
        """
        Execute a scheduled placement preset.

        Args:
            preset_name: Human-readable preset name.
            callback: Runtime function that creates the point pattern.
        """
        self.n_body_spawn_after_id = None

        try:
            callback()

        except Exception as exc:
            self.logger.error(
                "N_BODY_SPAWN_ERROR | preset=%s | error=%s",
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
            "N_BODY_SPAWN_COMPLETE | preset=%s",
            preset_name,
        )

    def cancel_n_body_spawn(self, clear_status=True):
        """
        Cancel a pending placement-preset timer.

        Args:
            clear_status: Clear the status label when True.
        """
        if self.n_body_spawn_after_id is not None:
            try:
                self.window.after_cancel(
                    self.n_body_spawn_after_id
                )
            except tk.TclError:
                pass

            self.n_body_spawn_after_id = None

            self.logger.info(
                "N_BODY_SPAWN_CANCELLED"
            )

        if clear_status:
            self.n_body_status_var.set("")

    # --------------------------------------------------------
    # Preset / dirty state
    # --------------------------------------------------------

    def _highlight_preset(self, preset_name):
        """
        Highlight the selected physics preset.

        Args:
            preset_name: Name of the selected preset.
        """
        self.selected_preset = preset_name

        for name, button in self.preset_buttons.items():
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

    def _mark_dirty(self, *args):
        """
        Update Apply-button state when entry values differ from config.

        Tkinter variable traces pass positional arguments, so ``*args`` is
        accepted even though those values are not used.
        """
        has_changes = False

        for field_name, variable in self.variables.items():
            try:
                input_value = self._convert_value(
                    field_name,
                    variable.get(),
                )
            except ValueError:
                has_changes = True
                break

            if input_value != getattr(
                config,
                field_name,
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

            for button in self.preset_buttons.values():
                button.configure(
                    bg=PRESET_NORMAL_BG,
                    relief="raised",
                )

            if hasattr(self, "defaults_button"):
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

    def _create_setting_row(self, field_name, row):
        """
        Create one label/entry pair for a config setting.

        Args:
            field_name: Attribute name on ``config``.
            row: Grid row for the controls.

        Raises:
            AttributeError: If ``field_name`` does not exist on config.
        """
        if not hasattr(config, field_name):
            raise AttributeError(
                f"Config has no setting named {field_name!r}"
            )

        if field_name not in self.variables:
            variable = tk.StringVar(
                value=str(
                    getattr(
                        config,
                        field_name,
                    )
                )
            )

            variable.trace_add(
                "write",
                self._mark_dirty,
            )

            self.variables[field_name] = variable

        variable = self.variables[field_name]

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

    def _convert_value(self, field_name, text):
        """
        Convert an entry string to the config field's existing type.

        Args:
            field_name: Config attribute being converted.
            text: Raw entry text.

        Returns:
            The converted value.

        Raises:
            ValueError: If the value cannot be converted.
        """
        current_value = getattr(
            config,
            field_name,
        )

        expected_type = type(
            current_value
        )

        try:
            return expected_type(text)

        except ValueError as exc:
            raise ValueError(
                f"{field_name} must be a valid {expected_type.__name__}"
            ) from exc

    # --------------------------------------------------------
    # Presets
    # --------------------------------------------------------

    def load_preset(self, preset_name):
        """
        Load a physics preset into the input fields without applying it.

        Args:
            preset_name: Name of the preset in ``PRESETS``.
        """
        preset = PRESETS.get(
            preset_name
        )

        if preset is None:
            return

        for field_name, value in preset.items():
            if field_name not in self.variables:
                continue

            self.variables[field_name].set(
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
        Load default GravityConfig values into the input fields.

        Defaults are not applied to the running simulation until Apply is
        pressed.
        """
        defaults = GravityConfig()

        for field_name, variable in self.variables.items():
            if not hasattr(defaults, field_name):
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

        self.selected_preset = "Defaults"

        for button in self.preset_buttons.values():
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
        Save the current UI settings as a candidate preset in the log.

        This operation does not modify ``config.py`` or ``PRESETS``.
        """
        values = {}

        try:
            for field_name, variable in self.variables.items():
                values[field_name] = self._convert_value(
                    field_name,
                    variable.get(),
                )

        except ValueError as exc:
            messagebox.showerror(
                "Invalid Setting",
                str(exc),
                parent=self.window,
            )
            return

        preset_name = simpledialog.askstring(
            "Save Preset",
            "Enter a name for this preset:",
            parent=self.window,
        )

        if preset_name is None:
            return

        preset_name = preset_name.strip()

        if not preset_name:
            messagebox.showerror(
                "Invalid Preset Name",
                "Preset name cannot be empty.",
                parent=self.window,
            )
            return

        self.save_preset_callback(
            preset_name,
            values,
        )

        self.loaded_preset_var.set(
            f"Saved for review: {preset_name}"
        )

        messagebox.showinfo(
            "Preset Saved",
            f'"{preset_name}" was saved to the log for later review.',
            parent=self.window,
        )

    # --------------------------------------------------------
    # Apply / reload
    # --------------------------------------------------------

    def apply(self):
        """
        Validate and apply all settings currently stored in the UI.
        """
        new_values = {}

        try:
            for field_name, variable in self.variables.items():
                new_values[field_name] = self._convert_value(
                    field_name,
                    variable.get(),
                )

        except ValueError as exc:
            messagebox.showerror(
                "Invalid Setting",
                str(exc),
                parent=self.window,
            )
            return

        point_count = new_values.get(
            "multi_point_count",
            config.multi_point_count,
        )

        if not 1 <= point_count <= MAX_GRAVITY_POINTS:
            messagebox.showerror(
                "Invalid Setting",
                (
                    "Multi Point Count must be between 1 and "
                    f"{MAX_GRAVITY_POINTS}."
                ),
                parent=self.window,
            )
            return

        non_negative_fields = {
            "point_gravity",
            "gravity_distance_power",
            "min_gravity_distance",
            "max_gravity_acceleration",
            "body_stop_radius",
            "point_max_speed",
            "point_physics_hz",
            "triangle_spawn_radius",
            "pentagram_spawn_radius",
            "n_body_spawn_delay",
        }

        for field_name in non_negative_fields:
            value = new_values.get(
                field_name,
                getattr(config, field_name),
            )

            if value < 0:
                messagebox.showerror(
                    "Invalid Setting",
                    (
                        field_name
                        .replace("_", " ")
                        .title()
                        + " cannot be negative."
                    ),
                    parent=self.window,
                )
                return

        if new_values.get(
            "point_physics_hz",
            config.point_physics_hz,
        ) <= 0:
            messagebox.showerror(
                "Invalid Setting",
                "Point Physics Hz must be greater than zero.",
                parent=self.window,
            )
            return

        point_drag = new_values.get(
            "point_drag",
            config.point_drag,
        )

        if not 0 < point_drag <= 1:
            messagebox.showerror(
                "Invalid Setting",
                "Point Drag must be greater than 0 and at most 1.",
                parent=self.window,
            )
            return

        with self.state_lock:
            for field_name, new_value in new_values.items():
                old_value = getattr(
                    config,
                    field_name,
                )

                if old_value == new_value:
                    continue

                setattr(
                    config,
                    field_name,
                    new_value,
                )

                self.logger.info(
                    "CONFIG_CHANGE | %s | old=%s | new=%s",
                    field_name,
                    old_value,
                    new_value,
                )

        self.dirty = False

        if self.apply_button is not None:
            self.apply_button.configure(
                bg=APPLY_NORMAL_BG,
                relief="raised",
            )

    def reload(self):
        """
        Reload all existing input variables from the active config object.
        """
        with self.state_lock:
            for field_name, variable in self.variables.items():
                variable.set(
                    str(
                        getattr(
                            config,
                            field_name,
                        )
                    )
                )

        self.dirty = False

        if self.apply_button is not None:
            self.apply_button.configure(
                bg=APPLY_NORMAL_BG,
                relief="raised",
            )

    # --------------------------------------------------------
    # Point status
    # --------------------------------------------------------

    def _refresh_point_status(self):
        """
        Refresh the point count twice per second.

        Point-count display does not need physics-frame-frequency updates,
        so a low refresh rate avoids unnecessary UI work.
        """
        try:
            placed, limit = self.get_point_status_callback()

            self.point_status_var.set(
                f"Points placed: {placed}/{limit}"
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
        Reload current config values and display the settings window.
        """
        self.reload()
        self.window.deiconify()
        self.window.lift()
        self.window.focus_force()

    def hide(self):
        """
        Hide the settings window without destroying it.

        A pending placement preset is intentionally left active so the user
        can hide the window and reposition the cursor before the timer ends.
        """
        self.window.withdraw()
