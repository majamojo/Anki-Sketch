# -*- coding: utf-8 -*-
# Copyright: Michal Krassowski <krassowski.michal@gmail.com>
# License: GNU GPL, version 3 or later; http://www.gnu.org/copyleft/gpl.html
"""
AnkiSketch: draw on the card during review.

Fork of AnkiDraw by Rytisgit (https://github.com/Rytisgit/Anki-StylusDraw),
which was initially based on the Anki-TouchScreen addon, with updated ui,
pressure pen/stylus capabilities, perfect freehand (line smoothing) and
calligrapher functionality.

It adds an AnkiSketch menu with options like:

    switching AnkiSketch
    modifying some of the colors
    thickness
    toolbar settings

Copyright: Michal Krassowski <krassowski.michal@gmail.com>
License: GNU GPL, version 3 or later; http://www.gnu.org/copyleft/gpl.html,
Important parts of Javascript code inspired by http://creativejs.com/tutorials/painting-with-pixels/index.html

Layout:
    __init__.py         Qt menu, settings, injection into the reviewer
    web/canvas.html     toolbar and canvases (inlined into the reviewer body)
    web/sketch.css      styles (served via setWebExports)
    web/sketch.js       drawing logic (served via setWebExports)
    web/hotkeys.js      key-combination helpers shared by the reviewer and the hotkey dialog
    web/hotkeys_dialog.*  hotkey settings dialog (AnkiSketch > Hotkeys)
    web/Caligrapher.js, web/PerfectFreehand.js   stroke libraries
    config.json         hotkeys (documented in config.md)
"""

__addon_name__ = "AnkiSketch"
__version__ = "0.1.0"

import json
from pathlib import Path

from aqt import mw, gui_hooks
from aqt.reviewer import Reviewer
from aqt.utils import showWarning
from aqt.webview import AnkiWebView

from aqt.qt import QAction, QMenu, QColorDialog, QMessageBox, QInputDialog, QLabel,\
   QPushButton, QDialog, QVBoxLayout, QComboBox, QHBoxLayout, QSpinBox, QCheckBox, QFontDialog, QFont
from aqt.qt import QKeySequence,QColor
from aqt.qt import Qt, QGridLayout, QDoubleSpinBox, QDialogButtonBox
from aqt.qt import pyqtSlot as slot

ADDON_DIR = Path(__file__).parent
# Folder name under addons21 (for a dev install, whatever the folder is called).
ADDON_PACKAGE = mw.addonManager.addonFromModule(__name__)
WEB_BASE = f"/_addons/{ADDON_PACKAGE}/web"
mw.addonManager.setWebExports(__name__, r"web/.*\.(js|css)")

with open(ADDON_DIR / "web" / "canvas.html", encoding="utf8") as f:
    canvas_html = f.read()

# Settings are stored per profile under this prefix so they never clash with
# AnkiDraw's own "ts_*" keys. On first load, AnkiDraw's values (if any) are
# used as the starting point.
PROFILE_KEY_PREFIX = "anki_sketch."

# Hotkey actions, in the order shown in the Hotkeys dialog.
# (id, label, hold) — "hold" actions are on only while the key is held.
# Defaults live in config.json; config.md documents the format.
HOTKEY_ACTIONS = [
    ("pen_1", "Pen 1", False),
    ("pen_2", "Pen 2", False),
    ("pen_3", "Pen 3", False),
    ("pen_4", "Pen 4", False),
    ("undo", "Undo", False),
    ("redo", "Redo", False),
    ("perfect_freehand", "Perfect freehand mode", False),
    ("calligraphy", "Calligraphy mode", False),
    ("text", "Text mode", False),
    ("stroke_delete", "Stroke delete mode", False),
    ("stroke_delete_hold", "Stroke delete (hold)", True),
    ("select", "Select tool (lasso)", False),
    ("delete_selection", "Delete selection", False),
    ("clear", "Clear drawing", False),
    ("toggle_visibility", "Hide / show drawing", False),
    ("small_canvas", "Small / full canvas", False),
    ("toggle_addon", "Turn AnkiSketch on / off", False),
]
HOTKEY_IDS = [a[0] for a in HOTKEY_ACTIONS]
# Handled by a Qt shortcut (works anywhere in Anki), not by the reviewer's JS.
QT_HOTKEY_IDS = {"toggle_addon"}

# Keys Anki itself uses in review or the main window (same format as bindings).
# Only used to warn in the Hotkeys dialog.
ANKI_KEYS = [
    "Space", "Enter", "1", "2", "3", "4", "A", "B", "D", "E", "I", "O", "R", "S", "T", "V", "Y",
    "-", "=", "/", "Shift+1", "Shift+2", "Shift+8", "Ctrl+1", "Ctrl+2", "Ctrl+3", "Ctrl+4",
    "Ctrl+5", "Ctrl+6", "Ctrl+7", "Ctrl+Z", "Esc", "F5",
]

def hotkey_defaults():
    defaults = mw.addonManager.addonConfigDefaults(ADDON_PACKAGE) or {}
    return dict(defaults.get("hotkeys") or {})

def hotkey_bindings():
    """
    Current bindings: config.json defaults, overridden by the user's saved values.
    (Anki's getConfig only merges top-level keys, so new actions added in an
    update would otherwise be missing.)
    """
    bindings = hotkey_defaults()
    conf = mw.addonManager.getConfig(__name__) or {}
    for key, value in (conf.get("hotkeys") or {}).items():
        if key in HOTKEY_IDS and isinstance(value, str):
            bindings[key] = value
    return bindings

def save_hotkey_bindings(bindings):
    conf = mw.addonManager.getConfig(__name__) or {}
    conf["hotkeys"] = {key: str(bindings.get(key, "")) for key in HOTKEY_IDS}
    mw.addonManager.writeConfig(__name__, conf)
    apply_hotkeys()

QT_KEY_NAMES = {
    "PageUp": "PgUp", "PageDown": "PgDown", "NumEnter": "Enter", "NumAdd": "+",
    "NumSubtract": "-", "NumMultiply": "*", "NumDivide": "/", "NumDecimal": ".",
}

def qt_key_sequence(binding):
    """
    Turn a binding ("Ctrl+R", "Alt+PageUp", "Num5") into a QKeySequence.
    """
    if not binding:
        return QKeySequence()
    parts = binding.split("+")
    key = parts[-1]
    if key.startswith("Num") and key[3:].isdigit():
        key = key[3:]
    key = QT_KEY_NAMES.get(key, key)
    return QKeySequence("+".join([p for p in parts[:-1] if p] + [key]))

def apply_hotkeys():
    """
    Push the current bindings to the Qt shortcut and to an open reviewer.
    """
    bindings = hotkey_bindings()
    try:
        ts_menu_switch.setShortcut(qt_key_sequence(bindings.get("toggle_addon", "")))
    except NameError:
        pass  # menu not built yet
    if mw.state == "review" and ts_state_on:
        execute_js(f"if (typeof set_hotkeys === 'function') {{ set_hotkeys({json_for_script(js_hotkeys(bindings))}); }}")

# What each pointer button does; edited in the same dialog as hotkeys.
POINTER_BUTTONS = [
    ("left", "Left button / pen tip"),
    ("right", "Right button / pen side button"),
    ("middle", "Middle button"),
    ("pen_eraser", "Pen eraser end"),
]
POINTER_BEHAVIOURS = [
    ("tool", "Draw (current tool)"),
    ("select", "Select (lasso)"),
    ("stroke_delete", "Stroke delete"),
    ("none", "Nothing"),
]

def pointer_defaults():
    defaults = mw.addonManager.addonConfigDefaults(ADDON_PACKAGE) or {}
    return dict(defaults.get("pointer_buttons") or {})

def pointer_bindings():
    bindings = pointer_defaults()
    conf = mw.addonManager.getConfig(__name__) or {}
    valid = {b[0] for b in POINTER_BEHAVIOURS}
    for key, value in (conf.get("pointer_buttons") or {}).items():
        if key in bindings and value in valid:
            bindings[key] = value
    return bindings

def save_pointer_bindings(bindings):
    conf = mw.addonManager.getConfig(__name__) or {}
    valid = {b[0] for b in POINTER_BEHAVIOURS}
    current = pointer_bindings()
    conf["pointer_buttons"] = {
        key: (bindings.get(key) if bindings.get(key) in valid else current.get(key, "tool"))
        for key, _label in POINTER_BUTTONS
    }
    mw.addonManager.writeConfig(__name__, conf)
    if mw.state == "review" and ts_state_on:
        execute_js(f"if (typeof set_pointer_bindings === 'function') {{ set_pointer_bindings({json_for_script(pointer_bindings())}); }}")

def js_hotkeys(bindings):
    return {key: value for key, value in bindings.items() if key not in QT_HOTKEY_IDS}

ts_profile_loaded = False

saved_value_defaults = {
    'ts_state_on': True,
    'ts_opacity': 0.8,
    'ts_auto_hide': True,
    'ts_auto_hide_pointer': True,
    'ts_default_small_canvas': False,
    'ts_zen_mode': False,
    'ts_follow': False,
    'ts_pressure_sensitivity': True,
    'ts_orient_vertical': True,
    'ts_y_offset': 2,
    'ts_small_width': 500,
    'ts_small_height': 500,
    'ts_background_color': "#FFFFFF00",
    'ts_x_offset': 2,
    'ts_location': 1,
    'ts_pen1_color': "#272828",
    'ts_pen2_color': "#149beb",
    'ts_pen3_color': "#ced51a",
    'ts_pen4_color': "#da13a8",
    'ts_pen1_width': 4,
    'ts_pen2_width': 6,
    'ts_pen3_width': 20,
    'ts_pen4_width': 8,
    'ts_pen1_opacity': 0.8,
    'ts_pen2_opacity': 0.9,
    'ts_pen3_opacity': 0.5,
    'ts_pen4_opacity': 0.7,
    'ts_font_family': "Arial",
    'ts_font_size': 20,
    'ts_font_bold': False,
    'ts_font_italic': False,
    'ts_keep_drawings': False,
}

# Create the variables in the global scope
for key, value in saved_value_defaults.items():
    globals()[key] = value

def ts_save():
    """
    Saves configurable variables into profile, so they can
    be used to restore previous state after Anki restart.
    """
    # Save all default variables to profile
    for key, value in globals().items():
        if key in saved_value_defaults:
            mw.pm.profile[PROFILE_KEY_PREFIX + key] = value

def ts_load():
    """
    Load configuration from profile, set states of checkable menu objects
    and turn on night mode if it were enabled on previous session.
    """
    global ts_profile_loaded
    
    # Load each variable from profile or use default
    for key, default in saved_value_defaults.items():
        globals()[key] = mw.pm.profile.get(
            PROFILE_KEY_PREFIX + key, mw.pm.profile.get(key, default))

    ts_profile_loaded = True
    ts_menu_auto_hide.setChecked(ts_auto_hide)
    ts_menu_auto_hide_pointer.setChecked(ts_auto_hide_pointer)
    ts_menu_small_default.setChecked(ts_default_small_canvas)
    ts_menu_zen_mode.setChecked(ts_zen_mode)
    ts_menu_follow.setChecked(ts_follow)
    ts_menu_pressure.setChecked(ts_pressure_sensitivity)
    ts_menu_keep_drawings.setChecked(ts_keep_drawings)
    if ts_state_on:
        ts_on()

def execute_js(code):
    web_object = mw.reviewer.web
    web_object.eval(code)

def resize_js():
    execute_js("if (typeof resize === 'function') { setTimeout(resize, 101); }");
    
def clear_blackboard(card=None):
    if ts_state_on:
        if card is not None:
            keep = "true" if ts_keep_drawings else "false"
            execute_js(f"if (typeof ankisketch_show_card === 'function') {{ ankisketch_show_card({int(card.id)}, {keep}); }}")
        else:
            execute_js("if (typeof clear_canvas === 'function') { clear_canvas(); }")
        # is qFade the reason for having to wait?
        execute_js("if (typeof resize === 'function') { setTimeout(resize, 101); }");

def get_css_for_toolbar_location(location, x_offset, y_offset, orient_column, canvas_width, canvas_height, background_color):
    orient = "column" if orient_column else "row"
    switch = {
        0: f"""
                        --button-bar-pt: {y_offset}px;
                        --button-bar-pr: unset;
                        --button-bar-pb: unset;
                        --button-bar-pl: {x_offset}px;
                        --button-bar-orientation: {orient};
                        --small-canvas-height: {canvas_height};
                        --small-canvas-width: {canvas_width};
                        --background-color: {background_color};
                    """,
        1: f"""
                        --button-bar-pt: {y_offset}px;
                        --button-bar-pr: {x_offset}px;
                        --button-bar-pb: unset;
                        --button-bar-pl: unset;
                        --button-bar-orientation: {orient};
                        --small-canvas-height: {canvas_height};
                        --small-canvas-width: {canvas_width};
                        --background-color: {background_color};
                    """,
        2: f"""
                        --button-bar-pt: unset;
                        --button-bar-pr: unset;
                        --button-bar-pb: {y_offset}px;
                        --button-bar-pl: {x_offset}px;
                        --button-bar-orientation: {orient};
                        --small-canvas-height: {canvas_height};
                        --small-canvas-width: {canvas_width};
                        --background-color: {background_color};
                    """,
        3: f"""
                        --button-bar-pt: unset;
                        --button-bar-pr: {x_offset}px;
                        --button-bar-pb: {y_offset}px;
                        --button-bar-pl: unset;
                        --button-bar-orientation: {orient};
                        --small-canvas-height: {canvas_height};
                        --small-canvas-width: {canvas_width};
                        --background-color: {background_color};
                    """,
    }
    return switch.get(location, """
                        --button-bar-pt: 2px;
                        --button-bar-pr: 2px;
                        --button-bar-pb: unset;
                        --button-bar-pl: unset;
                        --button-bar-orientation: column;
                        --small-canvas-height: 500;
                        --small-canvas-width: 500;
                        --background-color: #FFFFFF00;
                    """)

def get_css_for_auto_hide(auto_hide, zen):
    return "none" if auto_hide or zen else "flex"

def get_css_for_zen_mode(hide):
    return "none" if hide else "flex"

def get_css_for_auto_hide_pointer(auto_hide):
    return "none" if auto_hide else "default"

def sketch_root_css():
    """
    CSS variables that depend on settings. Everything else is in web/sketch.css.
    """
    return (
        ":root {"
        + get_css_for_toolbar_location(ts_location, ts_x_offset, ts_y_offset, ts_orient_vertical,
                                       ts_small_width, ts_small_height, ts_background_color)
        + f"--ts-bar-display: {get_css_for_zen_mode(ts_zen_mode)};"
        + f"--ts-bar-autohide-display: {get_css_for_auto_hide(ts_auto_hide, ts_zen_mode)};"
        + f"--ts-nopointer-cursor: {get_css_for_auto_hide_pointer(ts_auto_hide_pointer)};"
        + "}"
    )

def sketch_js_config():
    """
    Settings passed to web/sketch.js as window.AnkiSketchConfig.
    """
    return {
        "settings": {
            "pressureSensitivity": bool(ts_pressure_sensitivity),
            "autoHidePointer": bool(ts_auto_hide_pointer),
            "smallCanvas": bool(ts_default_small_canvas),
            "follow": bool(ts_follow),
            "pens": [
                {
                    "color": str(globals()[f"ts_pen{n}_color"]),
                    "width": globals()[f"ts_pen{n}_width"],
                    "opacity": globals()[f"ts_pen{n}_opacity"],
                }
                for n in range(1, 5)
            ],
            "font": {
                "family": str(ts_font_family),
                "size": ts_font_size,
                "bold": bool(ts_font_bold),
                "italic": bool(ts_font_italic),
            },
        },
        "hotkeys": js_hotkeys(hotkey_bindings()),
        "pointer": pointer_bindings(),
    }

def json_for_script(value):
    # Safe to place inside <script>: no "</script>" or HTML comment openers.
    return json.dumps(value).replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026")

def sketch_body_html():
    """
    HTML appended to the reviewer body: toolbar + canvases, styles, settings, scripts.
    Order matches the old AnkiDraw injection (html, css, js, libraries).
    """
    return (
        canvas_html
        + f'<link rel="stylesheet" type="text/css" href="{WEB_BASE}/sketch.css">'
        + f"<style>{sketch_root_css()}</style>"
        + f"<script>window.AnkiSketchConfig = {json_for_script(sketch_js_config())};</script>"
        + f'<script src="{WEB_BASE}/hotkeys.js"></script>'
        + f'<script src="{WEB_BASE}/sketch.js"></script>'
        + f'<script src="{WEB_BASE}/Caligrapher.js"></script>'
        + f'<script src="{WEB_BASE}/PerfectFreehand.js"></script>'
    )

HOTKEY_DIALOG_CMD = "ankisketch_hotkeys:"

class HotkeyDialog(QDialog):
    """
    Hotkey settings: one row per action, click a key button then press keys.
    Runs in a web view so keys are captured exactly as the reviewer sees them.
    """
    def __init__(self, parent=None):
        super().__init__(parent or mw)
        self.setWindowTitle("AnkiSketch Hotkeys and Buttons")
        self.resize(640, 820)
        self.web = AnkiWebView(parent=self, title="AnkiSketch hotkeys")
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.web)
        self.setLayout(layout)
        self.web.set_bridge_command(self.on_bridge_cmd, self)
        payload = {
            "actions": [
                {"id": action_id, "label": label, "hold": hold, "qt": action_id in QT_HOTKEY_IDS}
                for action_id, label, hold in HOTKEY_ACTIONS
            ],
            "bindings": hotkey_bindings(),
            "defaults": hotkey_defaults(),
            "ankiKeys": ANKI_KEYS,
            "pointerButtons": [{"id": k, "label": label} for k, label in POINTER_BUTTONS],
            "pointerBehaviours": [{"id": k, "label": label} for k, label in POINTER_BEHAVIOURS],
            "pointer": pointer_bindings(),
            "pointerDefaults": pointer_defaults(),
        }
        body = (
            "<div id=app></div>"
            f"<script>window.AnkiSketchHotkeyDialog = {json_for_script(payload)};</script>"
        )
        self.web.stdHtml(
            body,
            css=[f"{WEB_BASE}/hotkeys_dialog.css"],
            js=[f"{WEB_BASE}/hotkeys.js", f"{WEB_BASE}/hotkeys_dialog.js"],
            context=self,
        )

    def on_bridge_cmd(self, cmd):
        if not cmd.startswith(HOTKEY_DIALOG_CMD):
            return
        cmd = cmd[len(HOTKEY_DIALOG_CMD):]
        if cmd.startswith("save:"):
            data = json.loads(cmd[len("save:"):])
            if isinstance(data, dict):
                hotkeys = data.get("hotkeys") or {}
                save_hotkey_bindings({k: v for k, v in hotkeys.items() if k in HOTKEY_IDS and isinstance(v, str)})
                save_pointer_bindings(data.get("pointer") or {})
            self.accept()
        elif cmd == "cancel":
            self.reject()

    def done(self, result):
        if self.web:
            self.web.cleanup()
            self.web = None
        super().done(result)

@slot()
def ts_open_hotkey_dialog():
    HotkeyDialog(mw).exec()
    return True

def on_webview_will_set_content(web_content, context):
    if not isinstance(context, Reviewer):
        return
    if not ts_state_on:
        return
    web_content.body += sketch_body_html()


@slot()
def ts_change_font_settings():
    """
    Open Qt's font dialog and set chosen font.
    """
    global ts_font_family, ts_font_size, ts_font_bold, ts_font_italic
    current_font = QFont()
    current_font.setFamily(ts_font_family)
    current_font.setPointSize(ts_font_size)
    current_font.setBold(ts_font_bold)
    current_font.setItalic(ts_font_italic)
    
    font, ok = QFontDialog.getFont(current_font, mw)
    
    if ok:
        ts_font_family = font.family()
        ts_font_size = font.pointSize()
        ts_font_bold = font.bold()
        ts_font_italic = font.italic()
        
        execute_js(f"fontFamily = '{ts_font_family}';")
        execute_js(f"fontSize = {ts_font_size};")
        execute_js(f"fontBold = {str(ts_font_bold).lower()};")
        execute_js(f"fontItalic = {str(ts_font_italic).lower()};")
        
        execute_js("if (typeof ts_redraw === 'function') { ts_redraw(); }")

def ts_set_pen(pen_number, color=None, width=None, opacity=None):
    """
    Change one pen and apply it to the open reviewer straight away.
    Only new strokes use it; what's already drawn keeps its own style.
    """
    js = []
    if color is not None:
        globals()[f"ts_pen{pen_number}_color"] = color
        js.append(f"pen{pen_number}Color = {json.dumps(color)};")
    if width is not None:
        globals()[f"ts_pen{pen_number}_width"] = float(width)
        js.append(f"pen{pen_number}Width = {float(width)};")
    if opacity is not None:
        globals()[f"ts_pen{pen_number}_opacity"] = float(opacity)
        js.append(f"pen{pen_number}Opacity = {float(opacity)};")
    if mw.state == "review" and ts_state_on and js:
        execute_js("".join(js) + " if (typeof update_pen_settings === 'function') { update_pen_settings(); }")

class PenDialog(QDialog):
    """
    Pens 1-4 in one window: colour, width and opacity per pen.
    Changes apply as you make them.
    """
    def __init__(self, parent=None):
        super().__init__(parent or mw)
        self.setWindowTitle("AnkiSketch Pens")
        grid = QGridLayout()
        for col, text in enumerate(["", "Colour", "Width", "Opacity"]):
            grid.addWidget(QLabel(f"<b>{text}</b>"), 0, col)
        self.color_buttons = {}
        for n in range(1, 5):
            row = n
            grid.addWidget(QLabel(f"Pen {n}"), row, 0)

            color_button = QPushButton()
            color_button.setMinimumWidth(90)
            color_button.clicked.connect(lambda _checked=False, n=n: self.pick_color(n))
            self.color_buttons[n] = color_button
            self.show_color(n)
            grid.addWidget(color_button, row, 1)

            width = QDoubleSpinBox()
            width.setRange(0.5, 200)
            width.setDecimals(1)
            width.setSingleStep(0.5)
            width.setValue(float(globals()[f"ts_pen{n}_width"]))
            width.valueChanged.connect(lambda value, n=n: ts_set_pen(n, width=value))
            grid.addWidget(width, row, 2)

            opacity = QDoubleSpinBox()
            opacity.setRange(0, 1)
            opacity.setDecimals(2)
            opacity.setSingleStep(0.05)
            opacity.setValue(float(globals()[f"ts_pen{n}_opacity"]))
            opacity.valueChanged.connect(lambda value, n=n: ts_set_pen(n, opacity=value))
            grid.addWidget(opacity, row, 3)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(self.reject)
        layout = QVBoxLayout()
        layout.addLayout(grid)
        layout.addWidget(buttons)
        self.setLayout(layout)

    def show_color(self, n):
        color = globals()[f"ts_pen{n}_color"]
        self.color_buttons[n].setText(color)
        text_color = "#000" if QColor(color).lightness() > 128 else "#fff"
        self.color_buttons[n].setStyleSheet(f"background-color: {color}; color: {text_color};")

    def pick_color(self, n):
        qcolor = QColorDialog.getColor(QColor(globals()[f"ts_pen{n}_color"]), self)
        if qcolor.isValid():
            ts_set_pen(n, color=qcolor.name())
            self.show_color(n)

@slot()
def ts_open_pen_dialog():
    PenDialog(mw).exec()

class CustomDialog(QDialog):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("AnkiSketch Toolbar And Canvas")

        self.combo_box = QComboBox()
        self.combo_box.addItem("Top-Left")
        self.combo_box.addItem("Top-Right")
        self.combo_box.addItem("Bottom-Left")
        self.combo_box.addItem("Bottom-Right")

        combo_label = QLabel("Location:")

        range_label = QLabel("Offset:")

        start_range_label = QLabel("X Offset:")
        self.start_spin_box = QSpinBox()
        self.start_spin_box.setRange(0, 1000)

        small_width_label = QLabel("Non-Fullscreen Canvas Width:")
        self.small_width_spin_box = QSpinBox()
        self.small_width_spin_box.setRange(0, 9999)

        small_height_label = QLabel("Non-Fullscreen Canvas Height:")
        self.small_height_spin_box = QSpinBox()
        self.small_height_spin_box.setRange(0, 9999)

        end_range_label = QLabel("Y Offset:")
        self.end_spin_box = QSpinBox()
        self.end_spin_box.setRange(0, 1000)

        range_layout = QVBoxLayout()

        small_height_layout = QHBoxLayout()
        small_height_layout.addWidget(small_height_label)
        small_height_layout.addWidget(self.small_height_spin_box)

        small_width_layout = QHBoxLayout()
        small_width_layout.addWidget(small_width_label)
        small_width_layout.addWidget(self.small_width_spin_box)

        color_layout = QHBoxLayout()
        self.color_button = QPushButton("Select Color")
        self.color_button.clicked.connect(self.select_color)

        self.color_label = QLabel("Background color: #FFFFFF00")  # Initial color label

        color_layout.addWidget(self.color_label)
        color_layout.addWidget(self.color_button)

        start_layout = QHBoxLayout()
        start_layout.addWidget(start_range_label)
        start_layout.addWidget(self.start_spin_box)

        end_layout = QHBoxLayout()
        end_layout.addWidget(end_range_label)
        end_layout.addWidget(self.end_spin_box)
        range_layout.addLayout(start_layout)
        range_layout.addLayout(end_layout)
        range_layout.addLayout(small_width_layout)
        range_layout.addLayout(small_height_layout)
        

        checkbox_label2 = QLabel("Orient vertically:")
        self.checkbox2 = QCheckBox()

        checkbox_layout2 = QHBoxLayout()
        checkbox_layout2.addWidget(checkbox_label2)
        checkbox_layout2.addWidget(self.checkbox2)

        accept_button = QPushButton("Accept")
        cancel_button = QPushButton("Cancel")
        reset_button = QPushButton("Default")

        accept_button.clicked.connect(self.accept)
        cancel_button.clicked.connect(self.reject)
        reset_button.clicked.connect(self.reset_to_default)

        button_layout = QHBoxLayout()
        button_layout.addWidget(accept_button)
        button_layout.addWidget(reset_button)
        button_layout.addWidget(cancel_button)
        

        dialog_layout = QVBoxLayout()
        dialog_layout.addWidget(combo_label)
        dialog_layout.addWidget(self.combo_box)
        dialog_layout.addWidget(range_label)
        dialog_layout.addLayout(range_layout)
        dialog_layout.addLayout(checkbox_layout2)
        dialog_layout.addLayout(color_layout)
        dialog_layout.addLayout(button_layout)
        
        self.setLayout(dialog_layout)

    def set_values(self, combo_index, start_value, end_value, checkbox_state2, width, height, background_color):
        self.combo_box.setCurrentIndex(combo_index)
        self.start_spin_box.setValue(start_value)
        self.small_height_spin_box.setValue(height)
        self.small_width_spin_box.setValue(width)
        self.end_spin_box.setValue(end_value)
        self.checkbox2.setChecked(checkbox_state2)
        self.color_label.setText(f"Background color: {background_color}")

    def reset_to_default(self):
        self.combo_box.setCurrentIndex(1)
        self.start_spin_box.setValue(2)
        self.end_spin_box.setValue(2)
        self.small_height_spin_box.setValue(500)
        self.small_width_spin_box.setValue(500)
        self.checkbox2.setChecked(True)
        self.color_label.setText("Background color: #FFFFFF00")  # Reset color label

    def select_color(self):
        color_dialog = QColorDialog()
        qcolor_old = QColor(self.color_label.text()[-9:-2])
        color = color_dialog.getColor(qcolor_old, options=QColorDialog.ColorDialogOption.ShowAlphaChannel)
        if color.isValid():
            self.color_label.setText(f"Background color: {(color.name()+color.name(QColor.NameFormat.HexArgb)[1:3]).upper()}")  # Update color label

@slot()
def ts_change_toolbar_settings():
    global ts_orient_vertical, ts_y_offset, ts_x_offset, ts_location, ts_small_width, ts_small_height, ts_background_color
    
    dialog = CustomDialog()
    dialog.set_values(ts_location, ts_x_offset, ts_y_offset, ts_orient_vertical, ts_small_width, ts_small_height, ts_background_color) 
    result = dialog.exec()

    if result == QDialog.DialogCode.Accepted:
        ts_location = dialog.combo_box.currentIndex()
        ts_x_offset = dialog.start_spin_box.value()
        ts_y_offset = dialog.end_spin_box.value()
        ts_small_height = dialog.small_height_spin_box.value()
        ts_background_color = dialog.color_label.text()[-9:]
        ts_small_width = dialog.small_width_spin_box.value()
        ts_orient_vertical = dialog.checkbox2.isChecked()
        ts_switch()
        ts_switch()

@slot()
def ts_change_auto_hide_settings():
    """
    Switch auto hide toolbar setting.
    """
    global ts_auto_hide
    ts_auto_hide = not ts_auto_hide
    ts_switch()
    ts_switch()

@slot()
def ts_change_follow_settings():
    """
    Switch whiteboard follow screen.
    """
    global ts_follow
    ts_follow = not ts_follow
    execute_js("fullscreen_follow = " + str(ts_follow).lower() + ";")
    execute_js("if (typeof resize === 'function') { resize(); }")

@slot()
def ts_change_small_default_settings():
    """
    Switch default small canvas mode setting.
    """
    global ts_default_small_canvas
    ts_default_small_canvas = not ts_default_small_canvas
    ts_switch()
    ts_switch()

@slot()
def ts_change_zen_mode_settings():
    """
    Switch default zen mode setting.
    """
    global ts_zen_mode
    ts_zen_mode = not ts_zen_mode
    ts_switch()
    ts_switch()

@slot()
def ts_change_pressure_sensitivity_settings():
    """
    Switch pressure sensitivity setting.
    """
    global ts_pressure_sensitivity
    ts_pressure_sensitivity = not ts_pressure_sensitivity
    execute_js("pressureSensitivity = " + str(ts_pressure_sensitivity).lower() + ";")
    execute_js("if (typeof resize === 'function') { resize(); }")
    
@slot()
def ts_change_auto_hide_pointer_settings():
    """
    Switch auto hide pointer setting.
    """
    global ts_auto_hide_pointer
    ts_auto_hide_pointer = not ts_auto_hide_pointer
    ts_switch()
    ts_switch()

@slot()
def ts_change_keep_drawings_settings():
    """
    Switch keeping each card's drawing while reviewing.
    """
    global ts_keep_drawings
    ts_keep_drawings = not ts_keep_drawings

def checkProfile():
    if not ts_profile_loaded:
        showWarning("No profile loaded. AnkiSketch may not work correctly.")
        return False
    return True

def ts_on():
    """
    Turn on
    """
    if not checkProfile(): return

    global ts_state_on
    ts_state_on = True
    ts_menu_switch.setChecked(True)
    return True

def ts_off():
    """
    Turn off
    """
    if not checkProfile(): return

    global ts_state_on
    ts_state_on = False
    ts_menu_switch.setChecked(False)
    return True

@slot()
def ts_switch():
    """
    Switch AnkiSketch.
    """
    if ts_state_on:
        ts_off()
    else:
        ts_on()
    # Reload current screen.
    if mw.state == "review":
        mw.moveToState("review")
    elif mw.state == "deckBrowser":
        mw.deckBrowser.refresh()
    elif mw.state == "overview":
        mw.overview.refresh()

class StickyMenu(QMenu):
    """
    Menu whose on/off items toggle without closing it, so several can be
    changed in one go. Items that open a window still close the menu.
    """
    def _toggle_active(self):
        action = self.activeAction()
        if action is not None and action.isEnabled() and action.isCheckable() and action.menu() is None:
            action.trigger()
            return True
        return False

    def mouseReleaseEvent(self, event):
        if self._toggle_active():
            return
        super().mouseReleaseEvent(event)

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter, Qt.Key.Key_Space) and self._toggle_active():
            return
        super().keyPressEvent(event)

def ts_setup_menu():
    """
    Initialize menu. 
    """
    global ts_menu_switch, ts_menu_auto_hide, ts_menu_auto_hide_pointer, ts_menu_small_default, ts_menu_zen_mode, ts_menu_follow, ts_menu_pressure, ts_menu_keep_drawings

    # Own menu (AnkiDraw uses mw.addon_view_menu; keep separate so both can be installed).
    menu = StickyMenu("""&AnkiSketch""", mw)
    mw.anki_sketch_menu = menu
    mw.form.menubar.insertMenu(mw.form.menuTools.menuAction(), menu)

    ts_menu_switch = QAction("""&Enable AnkiSketch""", mw, checkable=True)
    ts_menu_pressure = QAction("""Enable &pressure sensitivity""", mw, checkable=True)
    ts_menu_auto_hide = QAction("""Auto &hide toolbar when drawing""", mw, checkable=True)
    ts_menu_auto_hide_pointer = QAction("""Auto hide &pointer when drawing""", mw, checkable=True)
    ts_menu_follow = QAction("""&Follow when scrolling (speedup draw)""", mw, checkable=True)
    ts_menu_small_default = QAction("""&Small Canvas by default (speedup draw)""", mw, checkable=True)
    ts_menu_zen_mode = QAction("""Enable Zen Mode(hide toolbar until disabled)""", mw, checkable=True)
    ts_menu_keep_drawings = QAction("""&Keep drawings while reviewing""", mw, checkable=True)
    ts_menu_keep_drawings.setToolTip("Each card keeps its drawing when you come back to it in the same review session. Leaving the review screen clears them.")
    ts_pen_settings = QAction("""&Modify pens…""", mw)
    ts_toolbar_settings = QAction("""&Toolbar and canvas location settings…""", mw)
    ts_font_settings = QAction("""Select &Font for text writing…""", mw)
    ts_hotkey_settings = QAction("""&Hotkeys and buttons…""", mw)

    ts_menu_switch.setShortcut(qt_key_sequence(hotkey_bindings().get("toggle_addon", "")))
    menu.setToolTipsVisible(True)

    menu.addAction(ts_menu_switch)
    menu.addAction(ts_menu_pressure)
    menu.addAction(ts_menu_auto_hide)
    menu.addAction(ts_menu_auto_hide_pointer)
    menu.addAction(ts_menu_follow)
    menu.addAction(ts_menu_small_default)
    menu.addAction(ts_menu_zen_mode)
    menu.addAction(ts_menu_keep_drawings)
    menu.addSeparator()
    menu.addAction(ts_pen_settings)
    menu.addAction(ts_toolbar_settings)
    menu.addAction(ts_font_settings)
    menu.addAction(ts_hotkey_settings)

    ts_menu_switch.triggered.connect(ts_switch)
    ts_menu_pressure.triggered.connect(ts_change_pressure_sensitivity_settings)
    ts_menu_auto_hide.triggered.connect(ts_change_auto_hide_settings)
    ts_menu_auto_hide_pointer.triggered.connect(ts_change_auto_hide_pointer_settings)
    ts_menu_follow.triggered.connect(ts_change_follow_settings)
    ts_menu_small_default.triggered.connect(ts_change_small_default_settings)
    ts_menu_zen_mode.triggered.connect(ts_change_zen_mode_settings)
    ts_menu_keep_drawings.triggered.connect(ts_change_keep_drawings_settings)
    ts_pen_settings.triggered.connect(ts_open_pen_dialog)
    ts_toolbar_settings.triggered.connect(ts_change_toolbar_settings)
    ts_font_settings.triggered.connect(ts_change_font_settings)
    ts_hotkey_settings.triggered.connect(ts_open_hotkey_dialog)

#
# ONLOAD SECTION
#
def ts_onload():
    """
    Add hooks and initialize menu.
    Call to this function is placed on the end of this file.
    """
    gui_hooks.profile_will_close.append(ts_save)
    gui_hooks.profile_did_open.append(ts_load)
    gui_hooks.reviewer_did_show_question.append(clear_blackboard)
    gui_hooks.reviewer_did_show_answer.append(lambda card: resize_js())
    gui_hooks.webview_will_set_content.append(on_webview_will_set_content)
    mw.addonManager.setConfigAction(__name__, ts_open_hotkey_dialog)
    ts_setup_menu()

ts_onload()
