import tkinter as tk
from tkinter import messagebox, simpledialog, ttk

from config import config, PRESETS, MouseGravityConfig


# ------------------------------------------------------------
# Settings exposed through the GUI
#
# Add/remove/reorder names here to control what appears
# in the settings window.
# ------------------------------------------------------------

SETTINGS_FIELDS = [
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
    # "lateral_boost_multiplier",
    # "click_sequence_timeout",
    # "log_telemetry_hz",
]

PRESET_NORMAL_BG = "#f0f0f0"
PRESET_SELECTED_BG = "#d6c4f0"

APPLY_NORMAL_BG = "#f0f0f0"
APPLY_DIRTY_BG = "#fff2a8"

BUTTON_ACTIVE_BG = "#e2e2e2"


class SettingsWindow:
    """
    A window for configuring the mouse gravity settings.
    """

    def __init__(
        self,
        root,
        state_lock,
        logger,
        save_preset_callback,
    ):
        self.root = root
        self.state_lock = state_lock
        self.logger = logger
        self.save_preset_callback = save_preset_callback

        self.variables = {}

        self.window = tk.Toplevel(root)

        self.window.title("Mouse Gravity Settings")

        self.preset_buttons = {}

        self.selected_preset = None

        self.apply_button = None

        self.dirty = False

        self.loaded_preset_var = tk.StringVar(value="Preset: None")

        self.window.protocol(
            "WM_DELETE_WINDOW",
            self.hide,
        )

        self._build()

    # --------------------------------------------------------
    # Build window
    # --------------------------------------------------------

    def _build(self):
        main_frame = ttk.Frame(
            self.window,
            padding=15,
        )

        main_frame.pack(
            fill="both",
            expand=True,
        )

        # ----------------------------------------------------
        # Title
        # ----------------------------------------------------

        ttk.Label(
            main_frame,
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
        # Scrollable settings area
        # ----------------------------------------------------

        canvas = tk.Canvas(
            main_frame,
            highlightthickness=0,
        )

        scrollbar = ttk.Scrollbar(
            main_frame,
            orient="vertical",
            command=canvas.yview,
        )

        self.settings_frame = ttk.Frame(
            canvas,
        )

        self.settings_frame.bind(
            "<Configure>",
            lambda event: canvas.configure(scrollregion=canvas.bbox("all")),
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

        # ----------------------------------------------------
        # Build configurable fields
        # ----------------------------------------------------

        for row, field_name in enumerate(SETTINGS_FIELDS):
            self._create_setting_row(
                field_name,
                row,
            )

        # ----------------------------------------------------
        # Bottom controls
        # ----------------------------------------------------

        bottom_frame = ttk.Frame(
            self.window,
            padding=(15, 0, 15, 15),
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

        # ----------------------------------------------------
        # Scrollable preset row
        # ----------------------------------------------------

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

        preset_canvas_window = preset_canvas.create_window(
            (0, 0),
            window=preset_buttons_frame,
            anchor="nw",
        )

        def update_preset_scrollregion(event=None):
            preset_canvas.configure(scrollregion=preset_canvas.bbox("all"))

        preset_buttons_frame.bind(
            "<Configure>",
            update_preset_scrollregion,
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

        # ----------------------------------------------------
        # Preset buttons
        # ----------------------------------------------------

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

        # ----------------------------------------------------
        # Preset utility row
        # ----------------------------------------------------

        preset_utility_frame = ttk.Frame(
            preset_frame,
        )

        preset_utility_frame.pack(
            fill="x",
            pady=(4, 0),
        )

        ttk.Button(
            preset_utility_frame,
            text="Defaults",
            command=self.reset_to_defaults,
        ).pack(
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

        # ----------------------------------------------------
        # Preset status
        # ----------------------------------------------------

        ttk.Label(
            bottom_frame,
            textvariable=self.loaded_preset_var,
        ).pack(
            pady=(2, 8),
        )

        # ----------------------------------------------------
        # Apply / Close row
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

    def _highlight_preset(self, preset_name):
        """
        Visually mark the currently loaded preset.
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

    def _mark_dirty(self, *args):
        """
        Update the unapplied-change state.

        If the values in the input boxes differ from the live config:
        - mark the form as dirty
        - tint the Apply button
        - clear any selected preset/default highlight

        If the values match the live config again:
        - clear the dirty state
        - restore the Apply button appearance
        """
        has_changes = False

        for field_name, variable in self.variables.items():
            try:
                input_value = self._convert_value(
                    field_name,
                    variable.get(),
                )
            except ValueError:
                # Invalid text still counts as an unapplied change.
                has_changes = True
                break

            current_value = getattr(
                config,
                field_name,
            )

            if input_value != current_value:
                has_changes = True
                break

        self.dirty = has_changes

        if self.apply_button is not None:
            self.apply_button.configure(
                bg=(APPLY_DIRTY_BG if has_changes else APPLY_NORMAL_BG),
                relief=("raised" if has_changes else "raised"),
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

            self.loaded_preset_var.set("Preset: Custom")

    # --------------------------------------------------------
    # Create one configuration field
    # --------------------------------------------------------

    def _create_setting_row(
        self,
        field_name,
        row,
    ):
        """
        Create a label and entry box for a single config field.

        The entry box is linked to a StringVar, which is stored
        in self.variables for later retrieval.

        Args:
            field_name (str): The name of the config field.
            row (int): The row index in the grid layout.
        """

        # Check that the field exists in the config dataclass
        if not hasattr(config, field_name):
            raise AttributeError(f"Config has no setting named " f"{field_name!r}")

        current_value = getattr(
            config,
            field_name,
        )

        # Create a StringVar to hold the value of the entry box
        variable = tk.StringVar(
            value=str(current_value),
        )

        # Whenever the variable changes, mark the form as dirty
        variable.trace_add(
            "write",
            self._mark_dirty,
        )

        self.variables[field_name] = variable

        # Human-readable label
        display_name = field_name.replace("_", " ").title()

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

    # --------------------------------------------------------
    # Convert text back to original config type
    # --------------------------------------------------------

    def _convert_value(
        self,
        field_name,
        text,
    ):
        """
        Convert the text from the entry box back to the original
        type of the config field.

        Args:
            field_name (str): The name of the config field.
            text (str): The text from the entry box.

        Returns:
            The value converted to the original type of the config field.

        Raises:
            ValueError: If the text cannot be converted to the expected type.
        """
        current_value = getattr(
            config,
            field_name,
        )

        expected_type = type(current_value)

        if expected_type is bool:
            normalized = text.strip().lower()

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

            raise ValueError("must be true or false")

        return expected_type(text)

    def load_preset(self, preset_name):
        """
        Load preset values into the input fields.

        This does not modify the live config until Apply is pressed.
        """
        preset = PRESETS.get(preset_name)

        if preset is None:
            return

        for field_name, value in preset.items():

            # Only update fields that are exposed in the GUI.
            if field_name not in self.variables:
                continue

            self.variables[field_name].set(str(value))

        self.logger.info(
            "PRESET_LOADED | preset=%s",
            preset_name,
        )
        self.loaded_preset_var.set(f"Preset: {preset_name}")

        self._highlight_preset(preset_name)

    def reset_to_defaults(self):
        """
        Load the dataclass default values into the input boxes.

        This does not change the live config until Apply is pressed.
        """
        defaults = MouseGravityConfig()

        for field_name, variable in self.variables.items():
            if not hasattr(defaults, field_name):
                continue

            variable.set(str(getattr(defaults, field_name)))

        self.loaded_preset_var.set("Preset: Defaults")

        self.logger.info("DEFAULTS_LOADED")

        self.selected_preset = "Defaults"

        for button in self.preset_buttons.values():
            button.configure(
                bg=PRESET_NORMAL_BG,
                relief="raised",
            )

    def save_preset_to_log(self):
        """
        Save the values currently shown in the settings fields
        as a candidate preset in the run log.

        This does not apply the settings.
        """

        # --------------------------------------------------------
        # Validate all visible values
        # --------------------------------------------------------

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

        # --------------------------------------------------------
        # Ask user for a name
        # --------------------------------------------------------

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

        # --------------------------------------------------------
        # Send values to logger
        # --------------------------------------------------------

        self.save_preset_callback(
            preset_name,
            values,
        )

        # --------------------------------------------------------
        # Update UI
        # --------------------------------------------------------

        self.loaded_preset_var.set(f"Saved for review: {preset_name}")

        messagebox.showinfo(
            "Preset Saved",
            (f'"{preset_name}" was saved to the log ' "for later review."),
            parent=self.window,
        )

    # --------------------------------------------------------
    # Apply values
    # --------------------------------------------------------

    def apply(self):
        """
        Apply the values currently shown in the settings fields
        to the live config.

        This will validate the values first, and if any are invalid,
        it will show an error message and not apply any changes.

        Raises:
            ValueError: If any of the values cannot be converted to the expected type.
        """
        new_values = {}

        # Validate everything before changing anything.
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

        # Apply the new values to the live config.
        with self.state_lock:

            for (
                field_name,
                new_value,
            ) in new_values.items():

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
                    "CONFIG_CHANGE | " "%s | " "old=%s | " "new=%s",
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

    # --------------------------------------------------------
    # Reload values from live configuration
    # --------------------------------------------------------

    def reload(self):
        """
        Reload the values from the live config into the input boxes.

        This does not change the live config.
        """
        with self.state_lock:

            for (
                field_name,
                variable,
            ) in self.variables.items():

                current_value = getattr(
                    config,
                    field_name,
                )

                variable.set(str(current_value))
        self.dirty = False

        if self.apply_button is not None:
            self.apply_button.configure(
                bg=APPLY_NORMAL_BG,
                relief="raised",
            )

    # --------------------------------------------------------
    # Show
    # --------------------------------------------------------

    def show(self):
        """
        Show the settings window and bring it to the front.
        """
        self.reload()

        self.window.deiconify()
        self.window.lift()
        self.window.focus_force()

    # --------------------------------------------------------
    # Hide
    # --------------------------------------------------------

    def hide(self):
        """
        Hide the settings window.
        """
        self.window.withdraw()