import tkinter as tk
from tkinter import messagebox, ttk

from config import config


# ------------------------------------------------------------
# Settings exposed through the GUI
#
# Add/remove/reorder names here to control what appears
# in the settings window.
# ------------------------------------------------------------

SETTINGS_FIELDS = [
    "gravity",
    "reference_distance",
    "gravity_distance_power",
    "min_gravity_distance",
    "max_gravity_acceleration",

    "max_speed",
    "drag",
    "stop_radius",
    "fps",

    "normal_input_strength",
    "toward_input_multiplier",
    "away_input_multiplier",
    "lateral_boost_multiplier",

    "click_sequence_timeout",

    "log_telemetry_hz",
]


class SettingsWindow:
    def __init__(
        self,
        root,
        state_lock,
        logger,
    ):
        self.root = root
        self.state_lock = state_lock
        self.logger = logger

        self.variables = {}

        self.window = tk.Toplevel(root)

        self.window.title(
            "Mouse Gravity Settings"
        )

        self.window.geometry(
            "450x600"
        )

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
            lambda event: canvas.configure(
                scrollregion=canvas.bbox(
                    "all"
                )
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


        # ----------------------------------------------------
        # Build configurable fields
        # ----------------------------------------------------

        for row, field_name in enumerate(
            SETTINGS_FIELDS
        ):
            self._create_setting_row(
                field_name,
                row,
            )


        # ----------------------------------------------------
        # Buttons
        # ----------------------------------------------------

        button_frame = ttk.Frame(
            self.window,
            padding=10,
        )

        button_frame.pack(
            fill="x",
        )

        ttk.Button(
            button_frame,
            text="Apply",
            command=self.apply,
        ).pack(
            side="left",
            padx=5,
        )

        ttk.Button(
            button_frame,
            text="Reload Current Values",
            command=self.reload,
        ).pack(
            side="left",
            padx=5,
        )

        ttk.Button(
            button_frame,
            text="Close",
            command=self.hide,
        ).pack(
            side="right",
            padx=5,
        )


    # --------------------------------------------------------
    # Create one configuration field
    # --------------------------------------------------------

    def _create_setting_row(
        self,
        field_name,
        row,
    ):
        if not hasattr(config, field_name):
            raise AttributeError(
                f"Config has no setting named "
                f"{field_name!r}"
            )

        current_value = getattr(
            config,
            field_name,
        )

        variable = tk.StringVar(
            value=str(current_value),
        )

        self.variables[field_name] = variable


        # Human-readable label
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


    # --------------------------------------------------------
    # Convert text back to original config type
    # --------------------------------------------------------

    def _convert_value(
        self,
        field_name,
        text,
    ):
        current_value = getattr(
            config,
            field_name,
        )

        expected_type = type(
            current_value
        )


        if expected_type is bool:
            normalized = (
                text.strip().lower()
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
                "must be true or false"
            )


        return expected_type(
            text
        )


    # --------------------------------------------------------
    # Apply values
    # --------------------------------------------------------

    def apply(self):
        new_values = {}


        # Validate everything before changing anything.
        try:
            for field_name, variable in (
                self.variables.items()
            ):
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


        # Apply atomically.
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
                    "CONFIG_CHANGE | "
                    "%s | "
                    "old=%s | "
                    "new=%s",
                    field_name,
                    old_value,
                    new_value,
                )


    # --------------------------------------------------------
    # Reload values from live configuration
    # --------------------------------------------------------

    def reload(self):
        with self.state_lock:

            for (
                field_name,
                variable,
            ) in self.variables.items():

                current_value = getattr(
                    config,
                    field_name,
                )

                variable.set(
                    str(current_value)
                )


    # --------------------------------------------------------
    # Show
    # --------------------------------------------------------

    def show(self):
        self.reload()

        self.window.deiconify()
        self.window.lift()
        self.window.focus_force()


    # --------------------------------------------------------
    # Hide
    # --------------------------------------------------------

    def hide(self):
        self.window.withdraw()