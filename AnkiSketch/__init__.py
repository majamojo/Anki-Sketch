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
    web/Caligrapher.js, web/PerfectFreehand.js   stroke libraries
"""

__addon_name__ = "AnkiSketch"
__version__ = "0.1.0"

import json
from pathlib import Path

from aqt import mw, gui_hooks
from aqt.reviewer import Reviewer
from aqt.utils import showWarning

from aqt.qt import QAction, QMenu, QColorDialog, QMessageBox, QInputDialog, QLabel,\
   QPushButton, QDialog, QVBoxLayout, QComboBox, QHBoxLayout, QSpinBox, QCheckBox, QFontDialog, QFont
from aqt.qt import QKeySequence,QColor
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
    if ts_state_on:
        ts_on()

def execute_js(code):
    web_object = mw.reviewer.web
    web_object.eval(code)

def resize_js():
    execute_js("if (typeof resize === 'function') { setTimeout(resize, 101); }");
    
def clear_blackboard():
    if ts_state_on:
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
        + f'<script src="{WEB_BASE}/sketch.js"></script>'
        + f'<script src="{WEB_BASE}/Caligrapher.js"></script>'
        + f'<script src="{WEB_BASE}/PerfectFreehand.js"></script>'
    )

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

@slot()
def ts_change_pen_color(pen_number):
    """
    Open color picker and set chosen color for the specified pen.
    """
    # Get current color from global variable
    current_color = globals()[f"ts_pen{pen_number}_color"]
    qcolor_old = QColor(current_color)
    qcolor = QColorDialog.getColor(qcolor_old)
    
    if qcolor.isValid():
        # Update the global variable
        globals()[f"ts_pen{pen_number}_color"] = qcolor.name()
        
        # Reload the reviewer to apply the new color
        execute_js(f"pen{pen_number}Color = '{qcolor.name()}';")
        execute_js("if (typeof update_pen_settings === 'function') { update_pen_settings(); }")

@slot()
def ts_change_pen_width(pen_number):
    """
    Open width picker and set chosen width for the specified pen.
    """
    # Get current width from global variable
    current_width = globals()[f"ts_pen{pen_number}_width"]
    value, accepted = QInputDialog.getDouble(mw, "AnkiSketch", f"Enter the pen {pen_number} width:", current_width)
    
    if accepted:
        # Update the global variable
        globals()[f"ts_pen{pen_number}_width"] = value
        
        # Reload the reviewer to apply the new width
        execute_js(f"pen{pen_number}Width = '{value}';")
        execute_js("if (typeof update_pen_settings === 'function') { update_pen_settings(); }")

@slot()
def ts_change_pen_opacity(pen_number):
    """
    Open opacity picker and set chosen opacity for the specified pen.
    """
    # Get current opacity from global variable
    current_opacity = globals()[f"ts_pen{pen_number}_opacity"]
    value, accepted = QInputDialog.getDouble(mw, "AnkiSketch", f"Enter the pen {pen_number} opacity (0-1):", current_opacity, 0, 1, 2)
    
    if accepted:
        # Update the global variable
        globals()[f"ts_pen{pen_number}_opacity"] = value
        
        # Reload the reviewer to apply the new opacity
        execute_js(f"pen{pen_number}Opacity = '{value}';")
        execute_js("if (typeof update_pen_settings === 'function') { update_pen_settings(); }")
        execute_js("if (typeof ts_redraw === 'function') { ts_redraw(); }")

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

def ts_setup_menu():
    """
    Initialize menu. 
    """
    global ts_menu_switch, ts_menu_auto_hide, ts_menu_auto_hide_pointer, ts_menu_small_default, ts_menu_zen_mode, ts_menu_follow, ts_menu_pressure

    # Own menu (AnkiDraw uses mw.addon_view_menu; keep separate so both can be installed).
    menu = QMenu("""Anki&Sketch""", mw)
    mw.anki_sketch_menu = menu
    mw.form.menubar.insertMenu(mw.form.menuTools.menuAction(), menu)

    ts_menu_switch = QAction("""&Enable AnkiSketch""", mw, checkable=True)
    ts_menu_pressure = QAction("""Enable &pressure sensitivity""", mw, checkable=True)
    ts_menu_auto_hide = QAction("""Auto &hide toolbar when drawing""", mw, checkable=True)
    ts_menu_auto_hide_pointer = QAction("""Auto &hide pointer when drawing""", mw, checkable=True)
    ts_menu_follow = QAction("""&Follow when scrolling (speedup draw)""", mw, checkable=True)
    ts_menu_small_default = QAction("""&Small Canvas by default (speedup draw)""", mw, checkable=True)
    ts_menu_zen_mode = QAction("""Enable Zen Mode(hide toolbar until disabled)""", mw, checkable=True)
    ts_toolbar_settings = QAction("""&Toolbar and canvas location settings""", mw)
    ts_font_settings = QAction("""Select &Font for text writing""", mw)    

    ts_toggle_seq = QKeySequence("Ctrl+r")
    ts_menu_switch.setShortcut(ts_toggle_seq)

    ts_pen_color_menu = QMenu("Set pen 1-4 color", mw)
    ts_menu_pen1_color = QAction("Set Pen 1 Color", mw)
    ts_menu_pen2_color = QAction("Set Pen 2 Color", mw)
    ts_menu_pen3_color = QAction("Set Pen 3 Color", mw)
    ts_menu_pen4_color = QAction("Set Pen 4 Color", mw)
    ts_pen_color_menu.addAction(ts_menu_pen1_color)
    ts_pen_color_menu.addAction(ts_menu_pen2_color)
    ts_pen_color_menu.addAction(ts_menu_pen3_color)
    ts_pen_color_menu.addAction(ts_menu_pen4_color)

    ts_pen_width_menu = QMenu("Set pen 1-4 width", mw)
    ts_menu_pen1_width = QAction("Set Pen 1 width", mw)
    ts_menu_pen2_width = QAction("Set Pen 2 width", mw)
    ts_menu_pen3_width = QAction("Set Pen 3 width", mw)
    ts_menu_pen4_width = QAction("Set Pen 4 width", mw)
    ts_pen_width_menu.addAction(ts_menu_pen1_width)
    ts_pen_width_menu.addAction(ts_menu_pen2_width)
    ts_pen_width_menu.addAction(ts_menu_pen3_width)
    ts_pen_width_menu.addAction(ts_menu_pen4_width)

    ts_pen_opacity_menu = QMenu("Set pen 1-4 opacity", mw)
    ts_menu_pen1_opacity = QAction("Set Pen 1 Opacity", mw)
    ts_menu_pen2_opacity = QAction("Set Pen 2 Opacity", mw)
    ts_menu_pen3_opacity = QAction("Set Pen 3 Opacity", mw)
    ts_menu_pen4_opacity = QAction("Set Pen 4 Opacity", mw)
    ts_pen_opacity_menu.addAction(ts_menu_pen1_opacity)
    ts_pen_opacity_menu.addAction(ts_menu_pen2_opacity)
    ts_pen_opacity_menu.addAction(ts_menu_pen3_opacity)
    ts_pen_opacity_menu.addAction(ts_menu_pen4_opacity)

    menu.addAction(ts_menu_switch)
    menu.addAction(ts_menu_pressure)
    menu.addAction(ts_menu_auto_hide)
    menu.addAction(ts_menu_auto_hide_pointer)
    menu.addAction(ts_menu_follow)
    menu.addAction(ts_menu_small_default)
    menu.addAction(ts_menu_zen_mode)
    menu.addMenu(ts_pen_color_menu)
    menu.addMenu(ts_pen_width_menu)
    menu.addMenu(ts_pen_opacity_menu)
    menu.addAction(ts_toolbar_settings)
    menu.addAction(ts_font_settings)

    ts_menu_pen1_color.triggered.connect(lambda: ts_change_pen_color(1))
    ts_menu_pen2_color.triggered.connect(lambda: ts_change_pen_color(2))
    ts_menu_pen3_color.triggered.connect(lambda: ts_change_pen_color(3))
    ts_menu_pen4_color.triggered.connect(lambda: ts_change_pen_color(4))
    ts_menu_pen1_width.triggered.connect(lambda: ts_change_pen_width(1))
    ts_menu_pen2_width.triggered.connect(lambda: ts_change_pen_width(2))
    ts_menu_pen3_width.triggered.connect(lambda: ts_change_pen_width(3))
    ts_menu_pen4_width.triggered.connect(lambda: ts_change_pen_width(4))
    ts_menu_pen1_opacity.triggered.connect(lambda: ts_change_pen_opacity(1))
    ts_menu_pen2_opacity.triggered.connect(lambda: ts_change_pen_opacity(2))
    ts_menu_pen3_opacity.triggered.connect(lambda: ts_change_pen_opacity(3))
    ts_menu_pen4_opacity.triggered.connect(lambda: ts_change_pen_opacity(4))
    ts_menu_switch.triggered.connect(ts_switch)
    ts_menu_pressure.triggered.connect(ts_change_pressure_sensitivity_settings)
    ts_menu_auto_hide.triggered.connect(ts_change_auto_hide_settings)
    ts_menu_auto_hide_pointer.triggered.connect(ts_change_auto_hide_pointer_settings)
    ts_menu_follow.triggered.connect(ts_change_follow_settings)
    ts_menu_small_default.triggered.connect(ts_change_small_default_settings)
    ts_menu_zen_mode.triggered.connect(ts_change_zen_mode_settings)
    ts_toolbar_settings.triggered.connect(ts_change_toolbar_settings)
    ts_font_settings.triggered.connect(ts_change_font_settings)

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
    gui_hooks.reviewer_did_show_question.append(lambda card: clear_blackboard())
    gui_hooks.reviewer_did_show_answer.append(lambda card: resize_js())
    gui_hooks.webview_will_set_content.append(on_webview_will_set_content)
    ts_setup_menu()

ts_onload()
