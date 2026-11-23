# -*- coding: utf-8 -*-
# Copyright: Michal Krassowski <krassowski.michal@gmail.com>
# License: GNU GPL, version 3 or later; http://www.gnu.org/copyleft/gpl.html
"""
Initially based on the Anki-TouchScreen addon, updated ui and added pressure pen/stylus capabilities, perfect freehand(line smoothing) and calligrapher functionality.


It adds an AnkiDraw menu entity with options like:

    switching AnkiDraw
    modifying some of the colors
    thickness
    toolbar settings


If you want to contribute visit GitHub page: https://github.com/Rytisgit/Anki-StylusDraw
Also, feel free to send me bug reports or feature requests.

Copyright: Michal Krassowski <krassowski.michal@gmail.com>
License: GNU GPL, version 3 or later; http://www.gnu.org/copyleft/gpl.html,
Important parts of Javascript code inspired by http://creativejs.com/tutorials/painting-with-pixels/index.html
"""

__addon_name__ = "AnkiDraw"
__version__ = "1.7"

import sys
from pathlib import Path

from aqt import mw
from aqt.utils import showWarning

from anki.lang import _
from anki.hooks import addHook

from aqt.qt import QAction, QMenu, QColorDialog, QMessageBox, QInputDialog, QLabel,\
   QPushButton, QDialog, QVBoxLayout, QComboBox, QHBoxLayout, QSpinBox, QCheckBox, QFontDialog, QFont, QSlider, Qt
from aqt.qt import QKeySequence,QColor
from aqt.qt import pyqtSlot as slot

# Load extra JS libraries from external files to simplify the __init__.py
file = Path(__file__)
with open(file.with_name("Caligrapher.js"), encoding="utf8") as f:
    caligrapher_js = f.read()
with open(file.with_name("PerfectFreehand.js"), encoding="utf8") as f:
    perfect_freehand_js = f.read()
# This declarations are there only to be sure that in case of troubles
# with "profileLoaded" hook everything will work.

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
    'ts_fixed_pressure': 0.5,
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

ts_default_review_html = mw.reviewer.revHtml
ts_default_VISIBILITY = "true"
ts_default_PerfFreehand = "false"
ts_default_Calligraphy = "false"

def ts_save():
    """
    Saves configurable variables into profile, so they can
    be used to restore previous state after Anki restart.
    """
    # Save all default variables to profile
    for key, value in globals().items():
        if key in saved_value_defaults:
            mw.pm.profile[key] = value

def ts_disable_pen_press_and_hold():
    """
    Stop Windows from showing the pen press-and-hold circle (and turning a long
    press into a right click) over Anki, so holding the pen still to draw a
    straight line works without the ring appearing.
    """
    if sys.platform != "win32":
        return
    try:
        import ctypes
        from ctypes import wintypes
        user32 = ctypes.windll.user32

        hwnds = [int(mw.winId())]
        enum_proc = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
        def collect(hwnd, _):
            hwnds.append(hwnd)
            return True
        user32.EnumChildWindows(wintypes.HWND(hwnds[0]), enum_proc(collect), 0)

        # Windows 8+ pointer input feedback
        set_feedback = getattr(user32, "SetWindowFeedbackSetting", None)
        if set_feedback:
            set_feedback.argtypes = [wintypes.HWND, ctypes.c_int, wintypes.DWORD, wintypes.UINT, ctypes.c_void_p]
            set_feedback.restype = wintypes.BOOL
        FEEDBACK_PEN_PRESSANDHOLD = 5
        FEEDBACK_PEN_RIGHTTAP = 6
        off = wintypes.BOOL(False)

        # Legacy tablet service flag, still honoured for WM_GESTURE based input
        user32.SetPropW.argtypes = [wintypes.HWND, wintypes.LPCWSTR, wintypes.HANDLE]
        TABLET_DISABLE_PRESSANDHOLD = 0x00000001

        for hwnd in hwnds:
            if set_feedback:
                for feedback in (FEEDBACK_PEN_PRESSANDHOLD, FEEDBACK_PEN_RIGHTTAP):
                    set_feedback(hwnd, feedback, 0, ctypes.sizeof(off), ctypes.byref(off))
            user32.SetPropW(hwnd, "MicrosoftTabletPenServiceProperty", TABLET_DISABLE_PRESSANDHOLD)
    except Exception as e:
        print("AnkiDraw: could not disable pen press-and-hold feedback:", e)

def ts_load():
    """
    Load configuration from profile, set states of checkable menu objects
    and turn on night mode if it were enabled on previous session.
    """
    global ts_profile_loaded
    
    # Load each variable from profile or use default
    for key, default in saved_value_defaults.items():
        globals()[key] = mw.pm.profile.get(key, default)

    ts_profile_loaded = True
    ts_disable_pen_press_and_hold()
    ts_menu_auto_hide.setChecked(ts_auto_hide)
    ts_menu_auto_hide_pointer.setChecked(ts_auto_hide_pointer)
    ts_menu_small_default.setChecked(ts_default_small_canvas)
    ts_menu_zen_mode.setChecked(ts_zen_mode)
    ts_menu_follow.setChecked(ts_follow)
    ts_menu_pressure.setChecked(ts_pressure_sensitivity)
    if ts_state_on:
        ts_on()

    assure_plugged_in()

def execute_js(code):
    web_object = mw.reviewer.web
    web_object.eval(code)

def assure_plugged_in():
    global ts_default_review_html
    if not mw.reviewer.revHtml == custom:
        ts_default_review_html = mw.reviewer.revHtml
        mw.reviewer.revHtml = custom

def resize_js():
    execute_js("if (typeof resize === 'function') { setTimeout(resize, 101); }");
    
def clear_blackboard():
    assure_plugged_in()

    if ts_state_on:
        execute_js("if (typeof clear_canvas === 'function') { clear_canvas(); }")
        # is qFade the reason for having to wait?
        execute_js("if (typeof resize === 'function') { setTimeout(resize, 101); }");

def blackboard_html():
    return u"""
<div id="canvas_wrapper">
    <textarea id="AnkiDrawTextBox" style="width: 0;height: 0;opacity: 0;"></textarea>
    <canvas id="secondary_canvas" width="100" height="100" ></canvas>
    <canvas id="main_canvas" width="100" height="100"></canvas>
    
    <div id="pencil_button_bar">
        <!-- SVG icons from https://github.com/tabler/tabler-icons/ -->
        <button id="ts_visibility_button" class="active" data-hotkey="visibility"
              onclick="switch_visibility();" >
        <svg stroke="currentColor" fill="none" stroke-width="2" viewBox="0 0 24 24" stroke-linecap="round" stroke-linejoin="round" xmlns="http://www.w3.org/2000/svg"><path d="M4 20h4l10.5 -10.5a1.5 1.5 0 0 0 -4 -4l-10.5 10.5v4"></path><path d="M13.5 6.5l4 4"></path></svg>
        </button>

        <button id="ts_perfect_freehand_button" data-hotkey="perfect_freehand"
              onclick="switch_perfect_freehand()" >
        <svg stroke="currentColor" fill="none" stroke-width="2" viewBox="0 0 24 24" stroke-linecap="round" stroke-linejoin="round" xmlns="http://www.w3.org/2000/svg"><path d="M8 20l10.5 -10.5a2.828 2.828 0 1 0 -4 -4l-10.5 10.5v4h4z"></path><path d="M13.5 6.5l4 4"></path><path d="M16 18h4m-2 -2v4"></path></svg>
        </button>

        <button id="ts_kanji_button" data-hotkey="calligraphy"
              onclick="switch_calligraphy_mode();" >
        <svg stroke="currentColor" fill="none" stroke-width="2" viewBox="0 0 24 24" stroke-linecap="round" stroke-linejoin="round" xmlns="http://www.w3.org/2000/svg"><path d="M3 21v-4a4 4 0 1 1 4 4h-4"></path><path d="M21 3a16 16 0 0 0 -12.8 10.2"></path><path d="M21 3a16 16 0 0 1 -10.2 12.8"></path><path d="M10.6 9a9 9 0 0 1 4.4 4.4"></path></svg>
        </button>

        <button id="ts_text_button" data-hotkey="text"
              onclick="switch_text_writing_mode();" >
        <svg stroke="currentColor" fill="none" stroke-width="2" viewBox="0 0 24 24" stroke-linecap="round" stroke-linejoin="round" xmlns="http://www.w3.org/2000/svg"><path d="M19 10h-14" />  <path d="M5 6h14" />  <path d="M14 14h-9" />  <path d="M5 18h6" />  <path d="M18 15v6" />  <path d="M15 18h6" /></svg>        </button>

        <button id="ts_stroke_delete_button" data-hotkey="stroke_delete"
            onclick="switch_stroke_delete_mode()" >
        <svg stroke="currentColor" fill="none" stroke-width="2" viewBox="0 0 24 24" stroke-linecap="round" stroke-linejoin="round" xmlns="http://www.w3.org/2000/svg"><path d="M3 3l18 18" /><path d="M19 20h-10.5l-4.21 -4.3a1 1 0 0 1 0 -1.41l5 -4.993m2.009 -2.01l3 -3a1 1 0 0 1 1.41 0l5 5a1 1 0 0 1 0 1.41c-1.417 1.431 -2.406 2.432 -2.97 3m-2.02 2.043l-4.211 4.256" /><path d="M18 13.3l-6.3 -6.3" /></svg>
        </button>

        <button id="ts_select_button" data-hotkey="select"
            onclick="switch_select_mode()" >
        <svg stroke="currentColor" fill="none" stroke-width="2" viewBox="0 0 24 24" stroke-linecap="round" stroke-linejoin="round" xmlns="http://www.w3.org/2000/svg"><path d="M4.028 13.252c-.657 -.972 -1.028 -2.078 -1.028 -3.252c0 -3.866 4.03 -7 9 -7s9 3.134 9 7s-4.03 7 -9 7c-1.913 0 -3.686 -.464 -5.144 -1.255" /><path d="M5 15m-2 0a2 2 0 1 0 4 0a2 2 0 1 0 -4 0" /><path d="M5 17c0 1.42 .316 2.805 1 4" /></svg>
        </button>

        <button id="ts_delete_selection_button" data-hotkey="delete_selection"
            onclick="delete_selection()" >
        <svg stroke="currentColor" fill="none" stroke-width="2" viewBox="0 0 24 24" stroke-linecap="round" stroke-linejoin="round" xmlns="http://www.w3.org/2000/svg"><path d="M4 7l16 0" /><path d="M10 11l0 6" /><path d="M14 11l0 6" /><path d="M5 7l1 12a2 2 0 0 0 2 2h8a2 2 0 0 0 2 -2l1 -12" /><path d="M9 7v-3a1 1 0 0 1 1 -1h4a1 1 0 0 1 1 1v3" /></svg>
        </button>

        <button id="ts_undo_button" data-hotkey="undo"
              onclick="ts_undo();" >
        <svg stroke="currentColor" fill="none" stroke-width="2" viewBox="0 0 24 24" stroke-linecap="round" stroke-linejoin="round" xmlns="http://www.w3.org/2000/svg"><path d="M4.05 11a8 8 0 1 1 .5 4m-.5 5v-5h5"></path></svg>
        </button>
        <button id="ts_redo_button" data-hotkey="redo"
              onclick="ts_redo();" >
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" xmlns="http://www.w3.org/2000/svg"><path d="M19.95 11a8 8 0 1 0 -.5 4m.5 5v-5h-5"></path></svg>
        </button>
        <button class="active" data-hotkey="clear"
              onclick="add_clear_marker();" >
        <svg stroke="currentColor" fill="none" stroke-width="2" viewBox="0 0 24 24" stroke-linecap="round" stroke-linejoin="round" xmlns="http://www.w3.org/2000/svg"><path d="M4 7h16"></path><path d="M5 7l1 12a2 2 0 0 0 2 2h8a2 2 0 0 0 2 -2l1 -12"></path><path d="M9 7v-3a1 1 0 0 1 1 -1h4a1 1 0 0 1 1 1v3"></path><path d="M10 12l4 4m0 -4l-4 4"></path></svg>

        <button id="ts_switch_fullscreen_button" class="active" data-hotkey="fullscreen"
              onclick="switch_small_canvas();" >
        <svg stroke="currentColor" fill="none" stroke-width="2" viewBox="0 0 24 24" stroke-linecap="round" stroke-linejoin="round" xmlns="http://www.w3.org/2000/svg"><path d="M9.00002 3.99998H4.00004L4 9M20 8.99999V4L15 3.99997M15 20H20L20 15M4 15L4 20L9.00002 20"></path></svg>
        </button>

        <button id="ts_switch_pen1_button" class="active" data-hotkey="pen1"
              onclick="activate_pen1();" >
        <svg stroke="currentColor" fill="none" stroke-width="1.8" viewBox="0 0 24 24" stroke-linecap="round" stroke-linejoin="round" xmlns="http://www.w3.org/2000/svg"><path d="M18.333 2c1.96 0 3.56 1.537 3.662 3.472l.005 .195v12.666c0 1.96 -1.537 3.56 -3.472 3.662l-.195 .005h-12.666a3.667 3.667 0 0 1 -3.662 -3.472l-.005 -.195v-12.666c0 -1.96 1.537 -3.56 3.472 -3.662l.195 -.005h12.666zm-5.339 5.886c-.083 -.777 -1.008 -1.16 -1.617 -.67l-.084 .077l-2 2l-.083 .094a1 1 0 0 0 0 1.226l.083 .094l.094 .083a1 1 0 0 0 1.226 0l.094 -.083l.293 -.293v5.586l.007 .117a1 1 0 0 0 1.986 0l.007 -.117v-8l-.006 -.114z" /></svg>
        </button>

        <button id="ts_switch_pen2_button" class="active" data-hotkey="pen2"
              onclick="activate_pen2();" >
        <svg stroke="currentColor" fill="none" stroke-width="1.8" viewBox="0 0 24 24" stroke-linecap="round" stroke-linejoin="round" xmlns="http://www.w3.org/2000/svg"><path d="M18.333 2c1.96 0 3.56 1.537 3.662 3.472l.005 .195v12.666c0 1.96 -1.537 3.56 -3.472 3.662l-.195 .005h-12.666a3.667 3.667 0 0 1 -3.662 -3.472l-.005 -.195v-12.666c0 -1.96 1.537 -3.56 3.472 -3.662l.195 -.005h12.666zm-5.333 5h-3l-.117 .007a1 1 0 0 0 0 1.986l.117 .007h3v2h-2l-.15 .005a2 2 0 0 0 -1.844 1.838l-.006 .157v2l.005 .15a2 2 0 0 0 1.838 1.844l.157 .006h3l.117 -.007a1 1 0 0 0 0 -1.986l-.117 -.007h-3v-2h2l.15 -.005a2 2 0 0 0 1.844 -1.838l.006 -.157v-2l-.005 -.15a2 2 0 0 0 -1.838 -1.844l-.157 -.006z" /></path></svg>
        </button>

        <button id="ts_switch_pen3_button" class="active" data-hotkey="pen3"
              onclick="activate_pen3();" >
        <svg stroke="currentColor" fill="none" stroke-width="1.8" viewBox="0 0 24 24" stroke-linecap="round" stroke-linejoin="round" xmlns="http://www.w3.org/2000/svg"><path d="M18.333 2c1.96 0 3.56 1.537 3.662 3.472l.005 .195v12.666c0 1.96 -1.537 3.56 -3.472 3.662l-.195 .005h-12.666a3.667 3.667 0 0 1 -3.662 -3.472l-.005 -.195v-12.666c0 -1.96 1.537 -3.56 3.472 -3.662l.195 -.005h12.666zm-5.333 5h-2l-.15 .005a2 2 0 0 0 -1.85 1.995a1 1 0 0 0 1.974 .23l.02 -.113l.006 -.117h2v2h-2l-.133 .007c-1.111 .12 -1.154 1.73 -.128 1.965l.128 .021l.133 .007h2v2h-2l-.007 -.117a1 1 0 0 0 -1.993 .117a2 2 0 0 0 1.85 1.995l.15 .005h2l.15 -.005a2 2 0 0 0 1.844 -1.838l.006 -.157v-2l-.005 -.15a1.988 1.988 0 0 0 -.17 -.667l-.075 -.152l-.019 -.032l.02 -.03a2.01 2.01 0 0 0 .242 -.795l.007 -.174v-2l-.005 -.15a2 2 0 0 0 -1.838 -1.844l-.157 -.006z" /></svg>
        </button>

        <button id="ts_switch_pen4_button" class="active" data-hotkey="pen4"
              onclick="activate_pen4();" >
        <svg stroke="currentColor" fill="none" stroke-width="1.8" viewBox="0 0 24 24" stroke-linecap="round" stroke-linejoin="round" xmlns="http://www.w3.org/2000/svg"><path d="M18.333 2c1.96 0 3.56 1.537 3.662 3.472l.005 .195v12.666c0 1.96 -1.537 3.56 -3.472 3.662l-.195 .005h-12.666a3.667 3.667 0 0 1 -3.662 -3.472l-.005 -.195v-12.666c0 -1.96 1.537 -3.56 3.472 -3.662l.195 -.005h12.666zm-4.333 5a1 1 0 0 0 -.993 .883l-.007 .117v3h-2v-3l-.007 -.117a1 1 0 0 0 -1.986 0l-.007 .117v3l.005 .15a2 2 0 0 0 1.838 1.844l.157 .006h2v3l.007 .117a1 1 0 0 0 1.986 0l.007 -.117v-8l-.007 -.117a1 1 0 0 0 -.993 -.883z" /></svg>
        </button>

        <button id="ts_play_sound_button" class="active" data-hotkey="sound"
              onclick="PlaySound();" >
        <svg stroke="currentColor" fill="none" stroke-width="2" viewBox="0 0 24 24" stroke-linecap="round" stroke-linejoin="round" xmlns="http://www.w3.org/2000/svg"><path d="M6 10a7 7 0 1 1 13 3.6a10 10 0 0 1 -2 2a8 8 0 0 0 -2 3a4.5 4.5 0 0 1 -6.8 1.4" /><path d="M10 10a3 3 0 1 1 5 2.2" /></svg>
        </button>

    </div>
    <div id="ts_tooltip"></div>
    <div id="ts_toast"></div>
</div>
"""

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

def blackboard_css():
    return u"""
<style>
:root {
  """ + get_css_for_toolbar_location( ts_location, ts_x_offset, ts_y_offset, ts_orient_vertical, ts_small_width, ts_small_height, ts_background_color) + """
}
body {
  overflow-x: hidden; /* Hide horizontal scrollbar */
}
/*
    canvas needs touch-action: none so that it doesn't fire bogus
    pointercancel events. See:
    https://stackoverflow.com/questions/59010779/pointer-event-issue-pointercancel-with-pressure-input-pen
*/
#main_canvas, #secondary_canvas {
   z-index: 998;/* add toggle?*/
  touch-action: none;/*add toggle*/
  
  position:var(--canvas-bar-position);
  top: var(--canvas-bar-pt);
  right: var(--canvas-bar-pr);
  bottom: var(--canvas-bar-pb);
  left: var(--canvas-bar-pl);
  }
  #canvas_wrapper, #secondary_canvas {
   z-index: 999;
  }
#main_canvas, #secondary_canvas {
  background: var(--background-color);
  border-style: none;
  border-width: 1px;
}
#pencil_button_bar {
  position: fixed;
  display: """+get_css_for_zen_mode(ts_zen_mode)+""";
  flex-direction: var(--button-bar-orientation);
  opacity: .5;
  top: var(--button-bar-pt);
  right: var(--button-bar-pr);
  bottom: var(--button-bar-pb);
  left: var(--button-bar-pl);
  z-index: 8000;
  transition: .5s;
} #pencil_button_bar:hover { 
  opacity: 1;
} #pencil_button_bar > button {
  margin: 2px;
} #pencil_button_bar > button > svg {
  width: 2em;
} #pencil_button_bar > button:hover > svg {
  filter: drop-shadow(0 0 4px #000);
} #pencil_button_bar > button.active > svg > path {
  stroke: #000;
} .night_mode #pencil_button_bar > button.active > svg > path {
  stroke: #eee;
} #pencil_button_bar > button > svg > path {
  stroke: #888;
} .night_mode #pencil_button_bar > button > svg > path {
  /*stroke: #888;*/
}
.nopointer {
  cursor: """+get_css_for_auto_hide_pointer(ts_auto_hide_pointer)+""" !important;
} 
.touch_disable > button:not(:first-child){
    display: none;
}
.nopointer #pencil_button_bar
{
  display: """+get_css_for_auto_hide(ts_auto_hide, ts_zen_mode)+""";
}
#ts_tooltip, #ts_toast {
  position: fixed;
  z-index: 9000;
  pointer-events: none;
  font: 13px/1.3 sans-serif;
  color: #fff;
  background: rgba(30, 30, 30, 0.92);
  border-radius: 6px;
  white-space: nowrap;
}
#ts_tooltip {
  display: none;
  padding: 5px 8px;
}
#ts_tooltip .ts_key {
  margin-left: 6px;
  padding: 1px 5px;
  border-radius: 3px;
  background: rgba(255, 255, 255, 0.18);
  font-family: monospace;
}
#ts_toast {
  top: 12px;
  right: 12px;
  padding: 7px 12px;
  font-size: 14px;
  opacity: 0;
  transform: translateY(-6px);
  transition: opacity .2s, transform .2s;
}
#ts_toast.show {
  opacity: 1;
  transform: translateY(0);
}
</style>"""

def blackboard_js():
    return u"""
<script>
// Set from python qt ui
var visible = """ + ts_default_VISIBILITY + """;
var perfectFreehand = """ + ts_default_PerfFreehand +""";
var pressureSensitivity = """ + str(ts_pressure_sensitivity).lower() + """;
var fixedPressure = """ + str(ts_fixed_pressure) + """; // pressure used for every stroke when pressureSensitivity is off
var small_canvas = """ +  str(ts_default_small_canvas).lower() + """;
var fullscreen_follow = """ + str(ts_follow).lower() + """;
var calligraphy = """ + ts_default_Calligraphy + """;
var strokeDelete = false;
var textWriting = false;
var isDeleting = false;  // Track if currently deleting (for hold mode)
var selectMode = false;  // Lasso select tool
var pen1Color = """ + "\'" + str(ts_pen1_color) + "\'" + """;
var pen1Width = """ + str(ts_pen1_width) + """;
var pen2Color = """ + "\'" + str(ts_pen2_color) + "\'" + """;
var pen2Width = """ + str(ts_pen2_width) + """;
var pen3Color = """ + "\'" + str(ts_pen3_color) + "\'" + """;
var pen3Width = """ + str(ts_pen3_width) + """;
var pen4Color = """ + "\'" + str(ts_pen4_color) + "\'" + """;
var pen4Width = """ + str(ts_pen4_width) + """;
var pen1Opacity = """ + str(ts_pen1_opacity) + """;
var pen2Opacity = """ + str(ts_pen2_opacity) + """;
var pen3Opacity = """ + str(ts_pen3_opacity) + """;
var pen4Opacity = """ + str(ts_pen4_opacity) + """;
var fontFamily = """ + "\'" + str(ts_font_family) + "\'" + """;
var fontSize = """ + str(ts_font_size) + """;
var fontBold = """ + str(ts_font_bold).lower() + """;
var fontItalic = """ + str(ts_font_italic).lower() + """;
var activePenIndex = 0;
var convertDotStrokes = true

function getPenColorAndWidthByIndex(index){
    switch (index) {
        case 0:
            return [hexToRgba(pen1Color, pen1Opacity), pen1Width, pen1Opacity];
        break;
        case 1:
            return [hexToRgba(pen2Color, pen2Opacity), pen2Width, pen2Opacity];
        break;
        case 2:
            return [hexToRgba(pen3Color, pen3Opacity), pen3Width, pen3Opacity];
        break;
        case 3:
            return [hexToRgba(pen4Color, pen4Opacity), pen4Width, pen4Opacity];
        break;
        default:
            console.error("error too large index for pen selection")
            break;
    }
}

// Helper function to convert hex color to RGBA with opacity
function hexToRgba(hex, opacity) {
    // Remove the hash if present
    hex = hex.replace(/^#/, '');
    
    // Parse the hex values
    let r, g, b;
    if (hex.length === 3) {
        r = parseInt(hex[0] + hex[0], 16);
        g = parseInt(hex[1] + hex[1], 16);
        b = parseInt(hex[2] + hex[2], 16);
    } else if (hex.length === 6 || hex.length === 8) {
        r = parseInt(hex.substring(0, 2), 16);
        g = parseInt(hex.substring(2, 4), 16);
        b = parseInt(hex.substring(4, 6), 16);
    } else {
        return hex; // Return as-is if not a valid hex color
    }
    
    return `rgba(${r}, ${g}, ${b}, ${opacity})`;
}

// HTML references
var canvas = document.getElementById('main_canvas');
var wrapper = document.getElementById('canvas_wrapper');
var textBox = document.getElementById('AnkiDrawTextBox');
var optionBar = document.getElementById('pencil_button_bar');
var ts_undo_button = document.getElementById('ts_undo_button');
var ts_redo_button = document.getElementById('ts_redo_button');
var ctx = canvas.getContext('2d');
var secondary_canvas = document.getElementById('secondary_canvas');
var secondary_ctx = secondary_canvas.getContext('2d');
var ts_visibility_button = document.getElementById('ts_visibility_button');
var ts_kanji_button = document.getElementById('ts_kanji_button');
var ts_text_button = document.getElementById('ts_text_button');
var ts_perfect_freehand_button = document.getElementById('ts_perfect_freehand_button');
var ts_stroke_delete_button = document.getElementById('ts_stroke_delete_button');
var ts_select_button = document.getElementById('ts_select_button');
var ts_delete_selection_button = document.getElementById('ts_delete_selection_button');
var ts_tooltip = document.getElementById('ts_tooltip');
var ts_toast = document.getElementById('ts_toast');
var ts_switch_fullscreen_button = document.getElementById('ts_switch_fullscreen_button');


var ts_visibility_button_path1 = document.querySelector('#ts_visibility_button > svg > path');
var ts_visibility_button_path2 = document.querySelector('#ts_visibility_button > svg > path:nth-child(2)');

var ts_switch_pen1_button_path = document.querySelector('#ts_switch_pen1_button > svg > path');
var ts_switch_pen2_button_path = document.querySelector('#ts_switch_pen2_button > svg > path');
var ts_switch_pen3_button_path = document.querySelector('#ts_switch_pen3_button > svg > path');
var ts_switch_pen4_button_path = document.querySelector('#ts_switch_pen4_button > svg > path');

// Arrays to save point values from strokes
var stroke_cache = [ ];
var lineHistory = [ ] // contains history of currentAction Items, defined below
var redoStack = [ ]
let textCursorVisible = true;
let cursorBlinkInterval;

// Current stroke in progress
var currentAction = {
    points: [],
    color: '',
    width: '',
    opacity: '',
    visible: true,
    type: '', // 'simple' 'L', 'perfect' 'P', 'calligraphy' 'C', Delete 'D', Clear 'X'
    deletedList: [] // used only for delete actions
};

var index = 0;

canvas.onselectstart = function() { return false; };
secondary_canvas.onselectstart = function() { return false; };
wrapper.onselectstart = function() { return false; };

function PlaySound(){
    var selectors = document.querySelectorAll(".soundLink, .replaybutton")
    if (selectors) { selectors[index++ % selectors.length].click(); }
}
function recolor_based_on_active_pen()
{   
    var color = getPenColorAndWidthByIndex(activePenIndex)[0]

    ts_visibility_button_path1.style.stroke = color
    ts_visibility_button_path2.style.stroke = color

    ts_switch_pen1_button_path.style.stroke = pen1Color
    ts_switch_pen2_button_path.style.stroke = pen2Color
    ts_switch_pen3_button_path.style.stroke = pen3Color
    ts_switch_pen4_button_path.style.stroke = pen4Color
}

function activate_pen1()
{
    exit_select_mode()
    activePenIndex = 0
    update_pen_settings();
}

function activate_pen2()
{
    exit_select_mode()
    activePenIndex = 1
    update_pen_settings();
}

function activate_pen3()
{
    exit_select_mode()
    activePenIndex = 2
    update_pen_settings();
}

function activate_pen4()
{
    exit_select_mode()
    activePenIndex = 3
    update_pen_settings();
}

function reset_drawing_modes()
{
    ts_kanji_button.className = '';
    ts_perfect_freehand_button.className = '';
    ts_stroke_delete_button.className = '';
    ts_text_button.className = '';
    ts_select_button.className = '';
    calligraphy = false;
    perfectFreehand = false;
    strokeDelete = false
    textWriting = false;
    selectMode = false;
    reset_to_main_pen_settings()
    ts_redraw()
}

ts_kanji_button_class = '';
ts_perfect_freehand_button_class = '';
ts_stroke_delete_button_class = '';
ts_text_button_class = '';
calligraphy_activated = false;
perfectFreehand_activated = false;
strokeDelete_activated = false
textWriting_activated = false;
ts_select_button_class = '';
selectMode_activated = false;

function save_drawing_modes_for_delete()
{
    ts_kanji_button_class = ts_kanji_button.className;
    ts_perfect_freehand_button_class = ts_perfect_freehand_button.className;
    ts_text_button_class = ts_text_button.className;
    ts_select_button_class = ts_select_button.className;
    calligraphy_activated = calligraphy
    perfectFreehand_activated = perfectFreehand
    textWriting_activated = textWriting
    selectMode_activated = selectMode
    // Stroke delete takes over the pointer, so the lasso must not run alongside it
    selectMode = false
    ts_select_button.className = ''
    reset_to_main_pen_settings()
    ts_redraw()
}

function restore_drawing_modes_for_delete()
{
    ts_kanji_button.className = ts_kanji_button_class
    ts_perfect_freehand_button.className = ts_perfect_freehand_button_class
    ts_text_button.className = ts_text_button_class
    ts_select_button.className = ts_select_button_class
    calligraphy = calligraphy_activated
    perfectFreehand = perfectFreehand_activated
    textWriting = textWriting_activated
    selectMode = selectMode_activated
    reset_to_main_pen_settings()
    ts_redraw()
}

function switch_perfect_freehand()
{
    stop_drawing();
    temp = !perfectFreehand;
    reset_drawing_modes()
    perfectFreehand = temp;
    if(perfectFreehand)
    {
        ts_perfect_freehand_button.className = 'active';
    }
    else{
        ts_perfect_freehand_button.className = '';
    }
}

function switch_calligraphy_mode()
{
    stop_drawing();
    temp = !calligraphy;
    reset_drawing_modes()
    calligraphy = temp;
    if(calligraphy)
    {
        ts_kanji_button.className = 'active';
    }
    else{
        ts_kanji_button.className = '';
    }
}
function switch_text_writing_mode()
{
    stop_drawing();
    // In toggle mode, toggle the textWriting boolean
    temp = !textWriting;
    reset_drawing_modes()
    textWriting = temp;
    if(textWriting)
    {
        textBox.focus()
        ts_text_button.className = 'active';
    }
    else{
        textBox.blur()
        ts_text_button.className = '';
    }
}
function switch_select_mode()
{
    stop_drawing();
    var temp = !selectMode;
    reset_drawing_modes()
    selectMode = temp;
    ts_select_button.className = selectMode ? 'active' : '';
}

function exit_select_mode()
{
    if(!selectMode) return;
    selectMode = false;
    ts_select_button.className = '';
}

function switch_stroke_delete_mode()
{
    stop_drawing();
    
    // In toggle mode, toggle the strokeDelete boolean
    strokeDelete = !strokeDelete;
    if(strokeDelete || isDeleting)
    {
        save_drawing_modes_for_delete()
        ts_stroke_delete_button.className = 'active';
    }
    else{
        restore_drawing_modes_for_delete()
        ts_stroke_delete_button.className = '';
    }
}
function enter_stroke_delete_mode()
{
    stop_drawing();
    strokeDelete = true;
    isDeleting = true;
    if(strokeDelete || isDeleting)
    {
        save_drawing_modes_for_delete()
        ts_stroke_delete_button.className = 'active';
    }
    else{
        restore_drawing_modes_for_delete()
        ts_stroke_delete_button.className = '';
    }
}
function exit_stroke_delete_mode()
{
    stop_drawing();
    strokeDelete = false;
    isDeleting = false
    if(strokeDelete || isDeleting)
    {
        save_drawing_modes_for_delete()
        ts_stroke_delete_button.className = 'active';
    }
    else{
        restore_drawing_modes_for_delete()
        ts_stroke_delete_button.className = '';
    }
}


function switch_small_canvas()
{
    stop_drawing();
    
    small_canvas = !small_canvas;
    if(!small_canvas)
    {
        ts_switch_fullscreen_button.className = 'active';
    }
    else{
        ts_switch_fullscreen_button.className = '';
    }
    resize();
}

function switch_visibility()
{
	stop_drawing();
    clear_selection();
    if (visible)
    {
        canvas.style.display='none';
        secondary_canvas.style.display=canvas.style.display;
        ts_visibility_button.className = '';
        optionBar.className = 'touch_disable';
    }
    else
    {
        canvas.style.display='block';
        secondary_canvas.style.display=canvas.style.display;
        ts_visibility_button.className = 'active';
        optionBar.className = '';
    }
    visible = !visible;
}

//Initialize event listeners at the start;
canvas.addEventListener("pointerdown", pointerDownLine);
canvas.addEventListener("pointermove", pointerMoveLine);
secondary_canvas.addEventListener("pointerdown", pointerDownLine);
secondary_canvas.addEventListener("pointermove", pointerMoveLine);
window.addEventListener("pointerup", pointerUpLine);
canvas.addEventListener("pointerdown", pointerDownCaligraphy);
canvas.addEventListener("pointermove", pointerMoveCaligraphy);
secondary_canvas.addEventListener("pointerdown", pointerDownCaligraphy);
secondary_canvas.addEventListener("pointermove", pointerMoveCaligraphy);
window.addEventListener("pointerup", pointerUpCaligraphy);
canvas.addEventListener("pointerdown", pointerDownStrokeDelete);
canvas.addEventListener("pointermove", pointerMoveStrokeDelete);
secondary_canvas.addEventListener("pointerdown", pointerDownStrokeDelete);
secondary_canvas.addEventListener("pointermove", pointerMoveStrokeDelete);
window.addEventListener("pointerup", pointerUpStrokeDelete);

window.addEventListener("pointerup", pointerDownLineText);
window.addEventListener("pointerdown", pointerDownLineText);

function resize() {
    
    var card = document.getElementsByClassName('card')[0]
    
    // Run again until card is loaded
    if (!card){
        window.setTimeout(resize, 100)
        return;
        
    }
    // Check size of page without canvas
    canvas_wrapper.style.display='none';
    canvas.style["border-style"] = "none";
    secondary_canvas.style["border-style"] = "none";
    document.documentElement.style.setProperty('--canvas-bar-pt', '0px');
    document.documentElement.style.setProperty('--canvas-bar-pr', '0px');
    document.documentElement.style.setProperty('--canvas-bar-pb', 'unset');
    document.documentElement.style.setProperty('--canvas-bar-pl', 'unset');
    document.documentElement.style.setProperty('--canvas-bar-position', 'absolute');
    
    if(!small_canvas && !fullscreen_follow){
        ctx.canvas.width = Math.max(card.scrollWidth, document.documentElement.clientWidth);
        ctx.canvas.height = Math.max(document.documentElement.scrollHeight, document.documentElement.clientHeight);        
    }
    else if(small_canvas){
        ctx.canvas.width = Math.min(document.documentElement.clientWidth, 
        getComputedStyle(document.documentElement).getPropertyValue('--small-canvas-width'));
        ctx.canvas.height = Math.min(document.documentElement.clientHeight, 
        getComputedStyle(document.documentElement).getPropertyValue('--small-canvas-height'));
        canvas.style["border-style"] = "dashed";
        secondary_canvas.style["border-style"] = "dashed";
        document.documentElement.style.setProperty('--canvas-bar-pt', 
        getComputedStyle(document.documentElement).getPropertyValue('--button-bar-pt'));
        document.documentElement.style.setProperty('--canvas-bar-pr', 
        getComputedStyle(document.documentElement).getPropertyValue('--button-bar-pr'));
        document.documentElement.style.setProperty('--canvas-bar-pb', 
        getComputedStyle(document.documentElement).getPropertyValue('--button-bar-pb'));
        document.documentElement.style.setProperty('--canvas-bar-pl', 
        getComputedStyle(document.documentElement).getPropertyValue('--button-bar-pl'));
        document.documentElement.style.setProperty('--canvas-bar-position', 'fixed');
    }
    else{
        document.documentElement.style.setProperty('--canvas-bar-position', 'fixed');
        ctx.canvas.width = document.documentElement.clientWidth-1;
        ctx.canvas.height = document.documentElement.clientHeight-1;
    }
    secondary_ctx.canvas.width = ctx.canvas.width;
    secondary_ctx.canvas.height = ctx.canvas.height;
    canvas_wrapper.style.display='block';
    
    
    
    /* Get DPR with 1 as fallback */
    var dpr = window.devicePixelRatio || 1;
    
    /* CSS size is the same */
    canvas.style.height = ctx.canvas.height + 'px';
    wrapper.style.width = ctx.canvas.width + 'px';
    secondary_canvas.style.height = canvas.style.height;
    secondary_canvas.style.width = canvas.style.width;
    
    /* Increase DOM size and scale */
    ctx.canvas.width *= dpr;
    ctx.canvas.height *= dpr;
    ctx.scale(dpr, dpr);
    secondary_ctx.canvas.width *= dpr;
    secondary_ctx.canvas.height *= dpr;
    secondary_ctx.scale(dpr, dpr);
    
	update_pen_settings()
    
}


window.addEventListener('resize', resize);
window.addEventListener('load', resize);
window.requestAnimationFrame(draw_last_line_segment);

var isPointerDown = false;
var mouseX = 0;
var mouseY = 0;

function update_pen_settings(){
    stop_drawing()
    var pen = getPenColorAndWidthByIndex(activePenIndex);

    if(ctx.lineJoin != 'round'){
        ctx.lineJoin = ctx.lineCap = 'round';
        secondary_ctx.lineJoin = secondary_ctx.lineCap = ctx.lineJoin;
    }   
    if(ctx.lineWidth != pen[1]) {
        ctx.lineWidth = pen[1]; // pen Width
        secondary_ctx.lineWidth = ctx.lineWidth
    }
    if(ctx.strokeStyle != pen[0]){
        ctx.strokeStyle = ctx.fillStyle = pen[0]; // pen color
        
        
    } 
    var pencolorNoAlpha = pen[0].replace(/[\d\.]+\)$/g, '1)');
    if(secondary_ctx.strokeStyle != pencolorNoAlpha){
        secondary_ctx.strokeStyle = secondary_ctx.fillStyle = pencolorNoAlpha;
    }
    
    if(secondary_canvas.style.opacity != pen[2]) secondary_canvas.style.opacity = pen[2]
    if(canvas.style.opacity != pen[2]) canvas.style.opacity = pen[2]
    
    recolor_based_on_active_pen()
    ts_redraw()
}

function reset_to_main_pen_settings(){
    var pen = getPenColorAndWidthByIndex(activePenIndex);
    if(ctx.lineJoin != 'round'){
        ctx.lineJoin = ctx.lineCap = 'round';
        secondary_ctx.lineJoin = secondary_ctx.lineCap = ctx.lineJoin;
    }   
    if(ctx.lineWidth != pen[1]) {
        ctx.lineWidth = pen[1]; // pen Width
        secondary_ctx.lineWidth = ctx.lineWidth
    }
    if(ctx.strokeStyle != pen[0]){
        ctx.strokeStyle = ctx.fillStyle = pen[0]; // pen color
    } 
    var pencolorNoAlpha = pen[0].replace(/[\d\.]+\)$/g, '1)');
    if(secondary_ctx.strokeStyle != pencolorNoAlpha){
        secondary_ctx.strokeStyle = secondary_ctx.fillStyle = pencolorNoAlpha;
    }
    
    if(secondary_canvas.style.opacity != pen[2]) secondary_canvas.style.opacity = pen[2]
    if(canvas.style.opacity != pen[2]) canvas.style.opacity = pen[2]
    
}

function update_line_draw_settings(color, width, opacity){
    ctx.lineJoin = ctx.lineCap = 'round';
    if(ctx.lineWidth != width)ctx.lineWidth = width
    if(ctx.fillStyle != color)ctx.fillStyle = ctx.strokeStyle = color
}

function get_no_alpha(line_color){
    return ctx.strokeStyle.replace(/[\d\.]+\)$/g, '1)');
}

function ts_undo(){
	stop_drawing();
    clear_selection();
    if(!lineHistory.length) show_toast('Nothing to undo');
    if(lineHistory.length>0){
        var poppedAction = lineHistory.pop()
        show_toast('Undo: ' + describe_action(poppedAction))
        redoStack.push(poppedAction)
        ts_redo_button.className = "active";
        stroke_cache[lineHistory.length] = null;
        switch (poppedAction.type) {
            case 'C'://Calligraphy
                break;
            case 'L'://Simple Lines
                break;
            case 'P'://Perfect Lines
                break;
            case 'D'://Delete Stroke Lines
                poppedAction.deletedList.forEach( deletedIndex => { lineHistory[deletedIndex].visible = true } )
                break;
            case 'M'://Moved selection
                translate_actions(poppedAction.movedList, -poppedAction.dx, -poppedAction.dy)
                break;
            case 'X'://Clear actions
                break;
            case 'T'://Text Writing actions
                break;
            default://how did you get here??
                break;
        }
    }

    if(!lineHistory.length)
    {
        ts_undo_button.className = ""
    }
    ts_redraw()
}
function ts_redo() {
    stop_drawing();
    clear_selection();
    if (redoStack.length < 1) { show_toast('Nothing to redo'); return; }
    
    var redoAction = redoStack.pop();
    show_toast('Redo: ' + describe_action(redoAction))
    readd_action_to_history(redoAction)
    ts_undo_button.className = "active";
    switch (redoAction.type) {
        case 'C'://Calligraphy
            break;
        case 'L'://Simple Lines
            break;
        case 'D'://Delete Stroke Lines
            redoAction.deletedList.forEach( deletedIndex => { lineHistory[deletedIndex].visible = false } )
            break;
        case 'M'://Moved selection
            translate_actions(redoAction.movedList, redoAction.dx, redoAction.dy)
            break;
        case 'X'://Delete Stroke Lines
            break;
        default://how did you get here??
            break;
    }
    
    ts_redraw();
    if (redoStack.length === 0) {
        ts_redo_button.className = "";
    }
}

function ts_redraw() {
	pleaseRedrawEverything = true;
}

function ts_clear() {
	pleaseRedrawEverything = true;
    fullClear = true;
}

function clear_canvas()
{
	//don't continue to put points into an empty array(pointermove) if clearing while drawing on the canvas
	stop_drawing();
    clear_selection();
    reset_history();
    reset_redo()
	ts_clear();
}

function add_clear_marker()
{
	//don't continue to put points into an empty array(pointermove) if clearing while drawing on the canvas
	stop_drawing();
    clear_selection();
    if(lineHistory.length && lineHistory[lineHistory.length-1].type != 'X')add_action_to_history({ type: 'X'})
	ts_clear();
}

function add_action_to_history(action){
    ts_undo_button.className = "active"
    lineHistory.push(action)
    currentAction = {}
    reset_redo()
}

function readd_action_to_history(action){
    ts_undo_button.className = "active"
    lineHistory.push(action)
    currentAction = {}
}

function reset_redo(){
    redoStack = [];
    ts_redo_button.className = "";
}

function reset_history(){
    lineHistory = [];
    stroke_cache = [];
    ts_undo_button.className = "";
}

function stop_drawing() {
    straight_line_cancel()
    reset_to_main_pen_settings()
    submitCurrentText()
    isPointerDown = false;
	drawingWithPressurePenOnly = false;
}

function start_drawing() {
    submitCurrentText()
    isPointerDown = true;
    reset_redo()
}

function draw_last_line_segment() {
    window.requestAnimationFrame(draw_last_line_segment);
    draw_upto_latest_point_async(nextLine, nextPoint, nextStroke);
}

var nextLine = 0;
var nextPoint = 0;
var nextStroke = 0;
var p1,p2,p3;

function is_last_path_and_currently_drawn(i){
    return (lineHistory.length-1 < i)//the path is complete unless its the last of the array and the pointer is still down
}

function all_drawing_finished(i){
    return (lineHistory.length-1 >= i)//the path is complete unless its the last of the array and the pointer is still down
}

async function draw_path_at_some_point_async(startX, startY, midX, midY, endX, endY, lineWidth) {
		ctx.beginPath();
		ctx.moveTo((startX + (midX - startX) / 2), (startY + (midY - startY)/ 2));//midpoint calculation for x and y
		ctx.quadraticCurveTo(midX, midY, (midX + (endX - midX) / 2), (midY + (endY - midY)/ 2));
        ctx.lineWidth = lineWidth;
		ctx.stroke();
};
async function draw_secondary_path_at_some_point_async(startX, startY, midX, midY, endX, endY, lineWidth) {
		secondary_ctx.beginPath();
		secondary_ctx.moveTo((startX + (midX - startX) / 2), (startY + (midY - startY)/ 2));//midpoint calculation for x and y
		secondary_ctx.quadraticCurveTo(midX, midY, (midX + (endX - midX) / 2), (midY + (endY - midY)/ 2));
        secondary_ctx.lineWidth = lineWidth;
		secondary_ctx.stroke();
};

var pleaseRedrawEverything = false;
var fullClear = false;

async function draw_upto_latest_point_async(startLine, startPoint, startStroke){
	var fullRedraw = false;//keep track if this call started a full redraw to unset pleaseRedrawEverything flag later.
	if (pleaseRedrawEverything) {// erase everything and draw from start
        fullRedraw = true;
        startLine = 0;
        startPoint = 0;
        ctx.clearRect(0, 0, ctx.canvas.width, ctx.canvas.height);
	}
    for (let index = lineHistory.length-1; index > 0; index--) {//go thrught the history in reverse
        if(lineHistory[index].type == 'X'){// the first clear we find is where we should start from 
            if(index>startLine)startLine = index // if it's later than what we intend to draw
            break;
        }
    }
    for(var i = startLine; i < lineHistory.length; i++){ //Draw
        actionToDraw = lineHistory[i]
        if(!actionToDraw.visible) {
            nextPoint = 0;
            continue;
        }

        // While a selection is being dragged, draw it at its dragged position
        var shiftedForDrag = selectionDrag && selectionDrag.indexSet.has(i);
        if (shiftedForDrag) {
            ctx.save();
            ctx.translate(selectionDrag.dx, selectionDrag.dy);
        }
        update_line_draw_settings(actionToDraw.color, actionToDraw.width, actionToDraw.opacity)
        switch (actionToDraw.type) {
            case 'C'://Calligraphy
                    var calligraphyStroke = !stroke_cache[i] ? new Stroke(fitStroke(actionToDraw.points)) : stroke_cache[i]
                    stroke_cache[i] = calligraphyStroke
                    calligraphyStroke.draw(actionToDraw.width, ctx);
                break;
            case 'L'://Simple Lines
                ///0,0,0; 0,0,1; 0,1,2 or x+1,x+2,x+3
                //take the 2 previous points in addition to current one at the start of the loop.
                p2 = actionToDraw.points[startPoint > 1 ? startPoint-2 : 0];
                p3 = actionToDraw.points[startPoint > 0 ? startPoint-1 : 0];
                for(var j = startPoint; j < actionToDraw.points.length; j++){
                    nextPoint = j + 1;
                    p1 = p2;
                    p2 = p3;
                    p3 = actionToDraw.points[j];
                    var save = ctx.strokeStyle
                    //sadly this doesnt work well with windows, as it leaves circle outlines due to alpha blending, so abandon per stroke opacty dreams
                    // update_line_draw_settings(get_no_alpha(save), actionToDraw.width, actionToDraw.opacity)
                    // ctx.globalCompositeOperation = "destination-out";
                    // draw_path_at_some_point_async(p1[0],p1[1],p2[0],p2[1],p3[0],p3[1],p3[3]);

                    update_line_draw_settings(get_no_alpha(save), actionToDraw.width, actionToDraw.opacity)

                    ctx.globalCompositeOperation = "source-over";
                    draw_path_at_some_point_async(p1[0],p1[1],p2[0],p2[1],p3[0],p3[1],p3[3]);
                }
                
                break;
            case 'P'://Perfect Lines
                var path = !stroke_cache[i] ? new Path2D(getFreeDrawSvgPath(actionToDraw.points, actionToDraw.width, true)) : stroke_cache[i]
                stroke_cache[i] = path
                var save = ctx.strokeStyle
                // update_line_draw_settings(get_no_alpha(save), actionToDraw.width, actionToDraw.opacity)
                // ctx.globalCompositeOperation = "destination-out";
                // ctx.fill(path);

                update_line_draw_settings(get_no_alpha(save), actionToDraw.width, actionToDraw.opacity)
                ctx.globalCompositeOperation = "source-over";
                ctx.fill(path);
                break;
            case 'D'://Delete Stroke Lines
                break;
            case 'X'://Clear Screen
                break;
            case 'M'://Move selection
                break;
            case 'T'://Write Text
                var save = ctx.strokeStyle
                // update_line_draw_settings(get_no_alpha(save), actionToDraw.width, actionToDraw.opacity)
                // ctx.globalCompositeOperation = "destination-out";
                // drawTextFromAction(ctx, actionToDraw)

                update_line_draw_settings(get_no_alpha(save), actionToDraw.width, actionToDraw.opacity)
                ctx.globalCompositeOperation = "source-over";
                drawTextFromAction(ctx, actionToDraw)
                break;
            default://how did you get here??
                break;
        }
        if (shiftedForDrag) ctx.restore();
        //post loop cleanup
        if(all_drawing_finished(i)){
            nextLine = lineHistory.length;
            nextPoint = 0;
        }
        else{
            if(lineHistory.length == 0){
                nextLine = 0;
            }
            else{
                nextLine = lineHistory.length-1;
            }
        }
    }
    if(!strokeDelete)reset_to_main_pen_settings()
    
	if (fullRedraw) {//finished full redraw, now can unset redraw all flag so no more full redraws until necessary
        pleaseRedrawEverything = false;
        fullRedraw = false;
        nextPoint = lineHistory.length == 0 ? 0 : nextPoint;//reset next point if out of lines
        nextLine = lineHistory.length == 0 ? 0 : lineHistory.length
        if(fullClear){// start again from 0.
            nextLine = 0;
            fullClear = false;
        }
	}
}

var drawingWithPressurePenOnly = false; // hack for drawing with 2 main pointers when using a presure sensitive pen

function calculateClearBox(pointsArray) {
    if (!pointsArray.length) return {x: 0, y: 0, width: 0, height: 0};
    
    let minX = Infinity, minY = Infinity;
    let maxX = -Infinity, maxY = -Infinity;
    
    pointsArray.forEach(point => {
        if (point[0] < minX) minX = point[0];
        if (point[0] > maxX) maxX = point[0];
        if (point[1] < minY) minY = point[1];
        if (point[1] > maxY) maxY = point[1];
    });
    
    // Add some padding for line caps/width
    const padding = 1;
    
    return {
        x: minX - padding,
        y: minY - padding,
        width: (maxX - minX) + padding * 2,
        height: (maxY - minY) + padding * 2
    };
}
function drawCursor(x, y) {
    secondary_ctx.beginPath();
    secondary_ctx.moveTo(x, y);
    secondary_ctx.lineTo(x, y + fontSize);
    secondary_ctx.strokeStyle = 'red';
    secondary_ctx.lineWidth = 2;
    secondary_ctx.stroke();
}

function startCursorBlink() {
    clearInterval(cursorBlinkInterval);
    drawTextOnCanvas()
    cursorBlinkInterval = setInterval(() => {
        textCursorVisible = !textCursorVisible;
        drawTextOnCanvas();
    }, 500);
}

function createBoxWithDiagonalPoints(action) {
    const lines = action.text.split(/(?<!\\\\)\\n/);
    const allBoxPoints = [];
    
    const padding = 1;
    const spacing = 8;
    const lineHeight = calculateLineHeight(action.fontSize);

    var fontString = "";
    if (action.fontBold) fontString += "bold ";
    if (action.fontItalic) fontString += "italic ";
    fontString += action.fontSize + "px " + action.fontFamily;

    ctx.font = fontString;
    let currentY = action.y;
    
    // Process each line separately
    for (let i = 0; i < lines.length; i++) {
        const lineText = lines[i];
        
        const textWidth = ctx.measureText(lineText).width;
        
        // Calculate box for this line
        const x = action.x - padding;
        const y = currentY - padding;
        const width = textWidth + padding * 2;
        const height = action.fontSize + padding * 2;
        
        // Start with box corner points for this line
        const points = [
            [x, y],
            [x + width, y],  
            [x + width, y + height],
            [x, y + height]
        ];
        
        // Calculate diagonal lines for this box
        const diagonalLength = Math.sqrt(width * width + height * height);
        
        // Generate lines in both directions
        const directions = [
            // Direction 1: y = x + b (top-left to bottom-right)
            (i) => ({
                startX: x + i,
                startY: y,
                endX: x + i + diagonalLength,
                endY: y + diagonalLength,
                isOpposite: false
            }),
            // Direction 2: y = -x + b (top-right to bottom-left)  
            (i) => ({
                startX: x + diagonalLength - i,
                startY: y,
                endX: x - i,
                endY: y + diagonalLength,
                isOpposite: true
            })
        ];
        
        directions.forEach(getLine => {
            for (let j = -diagonalLength; j < diagonalLength; j += spacing) {
                const line = getLine(j);
                const intersection = lineIntersectsRect(
                    line.startX, line.startY, line.endX, line.endY, 
                    x, y, width, height,
                    line.isOpposite
                );
                
                if (intersection) {
                    const [segmentStart, segmentEnd] = intersection;
                    points.push(segmentStart, segmentEnd);
                }
            }
        });
        
        // Add this line's box points to the combined array
        allBoxPoints.push(...points);
        
        // Move Y position down for next line
        currentY += lineHeight;
    }
    
    return allBoxPoints;
}

// Updated unified intersection function
function lineIntersectsRect(x1, y1, x2, y2, rectX, rectY, rectW, rectH, isOpposite = false) {
    // Line equation: y = mx + b where m = 1 for normal, m = -1 for opposite
    const m = isOpposite ? -1 : 1;
    const b = y1 - m * x1;
    
    const intersections = [];
    
    // Intersection with left edge (x = rectX)
    const yAtLeft = m * rectX + b;
    if (yAtLeft >= rectY && yAtLeft <= rectY + rectH) {
        if (x1 <= rectX && rectX <= x2 || x2 <= rectX && rectX <= x1) {
            intersections.push([rectX, yAtLeft]);
        }
    }
    
    // Intersection with right edge (x = rectX + rectW)
    const yAtRight = m * (rectX + rectW) + b;
    if (yAtRight >= rectY && yAtRight <= rectY + rectH) {
        if (x1 <= rectX + rectW && rectX + rectW <= x2 || 
            x2 <= rectX + rectW && rectX + rectW <= x1) {
            intersections.push([rectX + rectW, yAtRight]);
        }
    }
    
    // Intersection with top edge (y = rectY)
    const xAtTop = (rectY - b) / m;
    if (xAtTop >= rectX && xAtTop <= rectX + rectW) {
        if (y1 <= rectY && rectY <= y2 || y2 <= rectY && rectY <= y1) {
            intersections.push([xAtTop, rectY]);
        }
    }
    
    // Intersection with bottom edge (y = rectY + rectH)
    const xAtBottom = (rectY + rectH - b) / m;
    if (xAtBottom >= rectX && xAtBottom <= rectX + rectW) {
        if (y1 <= rectY + rectH && rectY + rectH <= y2 || 
            y2 <= rectY + rectH && rectY + rectH <= y1) {
            intersections.push([xAtBottom, rectY + rectH]);
        }
    }
    
    if (intersections.length >= 2) {
        intersections.sort((a, b) => a[0] - b[0]);
        return [intersections[0], intersections[1]];
    }
    
    return null;
}

function submitCurrentText() {
    if (currentAction && currentAction.text && currentAction.text.length > 0) {

        // Create and save box around the text
        currentAction.points = createBoxWithDiagonalPoints(currentAction);
        // Save the text entry
        add_action_to_history(currentAction)
        
        // Clear current entry
        textBox.blur()
        secondary_ctx.clearRect(0, 0, canvas.width, canvas.height);   
    }
    textBox.value = ""
}


function pointerDownLineText(e) {
    if (!e.isPrimary || !textWriting) { return; }
    const rect = canvas.getBoundingClientRect();
    // Account for canvas scaling (DPR) and CSS size
    // The canvas has been scaled with ctx.scale(dpr, dpr), so we need
    // to divide by dpr to get the logical coordinates used by the drawing context
    const dpr = window.devicePixelRatio || 1;
    const scaleX = (canvas.width / dpr) / rect.width;
    const scaleY = (canvas.height / dpr) / rect.height;
    
    const clickX = (e.clientX - rect.left) * scaleX;
    const clickY = (e.clientY - rect.top) * scaleY;
    
    submitCurrentText();
    
    var pen = getPenColorAndWidthByIndex(activePenIndex);
    currentAction = {
        points: [],
        x: clickX,
        y: clickY,
        text: "",
        color: pen[0],
        width: pen[1],
        opacity: pen[2],
        visible: true,
        type: 'T', // 'text'
        fontFamily: fontFamily,
        fontSize: fontSize,
        fontBold: fontBold,
        fontItalic: fontItalic
    };
    textBox.focus()
};
// Prevent arrow key cursor movement
textBox.addEventListener('keydown', e => {
    if(!textWriting)return
    if (['ArrowLeft', 'ArrowRight', 'ArrowUp', 'ArrowDown'].includes(e.key)) {
        e.preventDefault();
    }
    else if (e.key === 'Escape') {
        submitCurrentText();
    }
    else if (e.altKey){
        e.preventDefault()
    }
});
textBox.addEventListener('input', () => {
    if (!currentAction || !textWriting) return;
    
    currentAction.text = textBox.value
    drawTextOnCanvas();
});

textBox.addEventListener('focus', () => startCursorBlink());
textBox.addEventListener('blur', () => {clearInterval(cursorBlinkInterval); submitCurrentText();});
// Prevent canvas click from stealing focus
canvas_wrapper.addEventListener('pointerdown', e => {
    if(!textWriting)return;
    e.preventDefault(); // Prevent focus loss    
    // Ensure textarea stays focused
    textBox.focus();
});

// Helper functions for calculations
function calculateLineHeight(fontSize) {
    // Line height = font size + appropriate spacing
    // For small fonts: add more relative spacing
    // For large fonts: add less relative spacing
    if (fontSize < 12) {
        return fontSize + 8; // More spacing for small text
    } else if (fontSize < 24) {
        return fontSize + 6; // Medium spacing
    } else {
        return fontSize + 4; // Less spacing for large text
    }
}

function calculateCursorOffset(fontSize) {
    // Cursor offset should be proportional to font size
    return Math.max(1, Math.floor(fontSize / 15));
}

function drawTextOnCanvas() {
    if(!textWriting)return;
    secondary_ctx.clearRect(0, 0, canvas.width, canvas.height);
        
    // Draw current entry text (dynamic)
    if (currentAction) {
        var lines = drawTextFromAction(secondary_ctx, currentAction)
        
        // Draw cursor if visible
        if (textCursorVisible) {
            const textWidth = lines ? secondary_ctx.measureText(lines[lines.length-1]).width + calculateCursorOffset(currentAction.fontSize) : 0;
            var currentLine = lines ? lines.length-1 : 0
            drawCursor(currentAction.x + textWidth, currentAction.y + currentLine * calculateLineHeight(currentAction.fontSize));
        }
    }
}

function drawTextFromAction(paramCtx, action){
    var lines = null
    if (action && action.type == 'T') {
        if(action.text){
            var lines = action.text.split(/(?<!\\\\)\\n/);//this is an escaped string as javascript is passed as a string into the python code
            for(var i = 0; i< lines.length; i++){
                var fontString = "";
                if (action.fontBold) fontString += "bold ";
                if (action.fontItalic) fontString += "italic ";
                fontString += action.fontSize + "px " + action.fontFamily;
                
                paramCtx.font = fontString;
                paramCtx.textBaseline = 'top';
                paramCtx.fillText(lines[i], action.x , action.y + i * calculateLineHeight(action.fontSize));
            }
        }
    }
    return lines
}

// [x, y, pressure, width] for simple and perfect freehand strokes.
// Pressure > 1 tells perfect freehand to simulate pressure from speed.
function stroke_point(e, penWidth) {
    var pressure;
    if (!pressureSensitivity) pressure = fixedPressure;            // same pressure for every input
    else if (e.pointerType[0] == 'p') pressure = e.pressure;       // real pen pressure
    else pressure = 2;                                             // mouse/touch: simulated
    var width = pressure > 1 ? penWidth : 1.0 + pressure * penWidth * 2;
    return [e.offsetX, e.offsetY, pressure, width];
}

function pointerDownLine(e) {
    wrapper.classList.add('nopointer');
	if (!e.isPrimary || calligraphy || strokeDelete || textWriting || selectMode) { return; }
	if (e.pointerType[0] == 'p' && pressureSensitivity) { drawingWithPressurePenOnly = true }
	else if ( drawingWithPressurePenOnly) { return; }
    var pen = getPenColorAndWidthByIndex(activePenIndex);
    if(!isPointerDown){
        e.preventDefault();
        currentAction = {
            points: [],
            color: pen[0],
            width: pen[1],
            opacity: pen[2],
            visible: true,
            type: perfectFreehand ? 'P' : 'L', // 'simple', 'perfect'
        };
        currentAction.points.push(stroke_point(e, currentAction.width));
        if(perfectFreehand){
            const box = calculateClearBox(currentAction.points);
            secondary_ctx.clearRect(box.x, box.y, box.width, box.height);
            var path = new Path2D(getFreeDrawSvgPath(currentAction.points, currentAction.width, true)) 
            secondary_ctx.fill(path)
        }
        else{
            draw_secondary_path_at_some_point_async(currentAction.points[0][0],currentAction.points[0][1],currentAction.points[0][0],currentAction.points[0][1],currentAction.points[0][0],currentAction.points[0][1],currentAction.points[0][3])
        }
        start_drawing();
        straight_line_track(e.offsetX, e.offsetY);
    }
}

function pointerMoveLine(e) {
	if (!e.isPrimary || calligraphy || strokeDelete || textWriting || selectMode) { return; }
	if (e.pointerType[0] != 'p' && drawingWithPressurePenOnly) { return; }
    var pen = getPenColorAndWidthByIndex(activePenIndex);
    if (isPointerDown) {
        if (straightLine.snapped) {
            // Already snapped: the end of the straight line follows the pen
            set_straight_line_end(e.offsetX, e.offsetY);
            draw_straight_line_preview();
            return;
        }
        currentAction.points.push(stroke_point(e, currentAction.width));
        if(perfectFreehand){
            const box = calculateClearBox(currentAction.points);
            secondary_ctx.clearRect(box.x, box.y, box.width, box.height);
            var path = new Path2D(getFreeDrawSvgPath(currentAction.points, currentAction.width, true)) 
            secondary_ctx.fill(path)
        }
        else{
            p1 = currentAction.points.length > 2 ? currentAction.points.length-3 : 0;
            p2 = currentAction.points.length > 1 ? currentAction.points.length-2 : 0;
            p3 = currentAction.points.length - 1;
            draw_secondary_path_at_some_point_async(currentAction.points[p1][0],currentAction.points[p1][1],currentAction.points[p2][0],currentAction.points[p2][1],currentAction.points[p3][0],currentAction.points[p3][1],currentAction.points[p3][3])
        }
        straight_line_track(e.offsetX, e.offsetY);
    }
}

function pointerUpLine(e) {
    wrapper.classList.remove('nopointer');
    /* Needed for the last bit of the drawing. */
	if (!e.isPrimary || calligraphy || strokeDelete || textWriting || selectMode) { return; }
	if (e.pointerType[0] != 'p' && drawingWithPressurePenOnly) { return; }
    var pen = getPenColorAndWidthByIndex(activePenIndex);
    if (isPointerDown && straightLine.snapped) {
        set_straight_line_end(e.offsetX, e.offsetY);
        add_action_to_history(currentAction)
        secondary_ctx.clearRect(0, 0, ctx.canvas.width, ctx.canvas.height);//clear the guide line in second canvas
    }
    else if (isPointerDown) {
        currentAction.points.push(stroke_point(e, currentAction.width));

        if(perfectFreehand){
            const box = calculateClearBox(currentAction.points);
            secondary_ctx.clearRect(box.x, box.y, box.width, box.height);
            var path = new Path2D(getFreeDrawSvgPath(currentAction.points, currentAction.width,true)) 
            secondary_ctx.fill(path)
        }
        else{
            p1 = currentAction.points.length > 2 ? currentAction.points.length-3 : 0;
            p2 = currentAction.points.length > 1 ? currentAction.points.length-2 : 0;
            p3 = currentAction.points.length - 1;
            draw_secondary_path_at_some_point_async(currentAction.points[p1][0],currentAction.points[p1][1],currentAction.points[p2][0],currentAction.points[p2][1],currentAction.points[p3][0],currentAction.points[p3][1],currentAction.points[p3][3])
        }
        add_action_to_history(currentAction)
        secondary_ctx.clearRect(0, 0, ctx.canvas.width, ctx.canvas.height);//clear the guide line in second canvas
    } 
	stop_drawing();
    
}

// ----------------------------------------- Straight lines -----------------------------------------
// Hold the pen still at the end of a stroke and it snaps to a straight line from where the
// stroke started. Keep moving after the snap to adjust the end point, then lift to commit.

var STRAIGHT_LINE_HOLD_MS = 600;   // how long the pen has to stay still
var STRAIGHT_LINE_TOLERANCE = 6;   // px of jitter still counted as "still"
var STRAIGHT_LINE_MIN_LENGTH = 12; // ignore holds on tiny strokes and dots
var straightLine = { timer: null, anchor: null, snapped: false, pressure: 2, width: 1 };

function straight_line_cancel() {
    clearTimeout(straightLine.timer);
    straightLine.timer = null;
    straightLine.anchor = null;
    straightLine.snapped = false;
}

function straight_line_track(x, y) {
    if (straightLine.snapped) return;
    if (straightLine.anchor && getDist([x, y], straightLine.anchor) <= STRAIGHT_LINE_TOLERANCE) return;
    straightLine.anchor = [x, y];
    clearTimeout(straightLine.timer);
    straightLine.timer = setTimeout(straight_line_snap, STRAIGHT_LINE_HOLD_MS);
}

function straight_line_snap() {
    straightLine.timer = null;
    if (!isPointerDown || !currentAction || !currentAction.points || currentAction.points.length < 2) return;
    if (currentAction.type != 'L' && currentAction.type != 'P') return;
    var pts = currentAction.points;
    var end = pts[pts.length - 1];
    if (getDist(pts[0], end) < STRAIGHT_LINE_MIN_LENGTH) return;
    // Keep the stroke's average pressure and width so the line looks like the pen
    var pressure = 0, width = 0;
    pts.forEach(p => { pressure += p[2]; width += p[3]; });
    straightLine.pressure = pressure / pts.length;
    straightLine.width = width / pts.length;
    straightLine.snapped = true;
    set_straight_line_end(end[0], end[1]);
    draw_straight_line_preview();
}

function set_straight_line_end(x, y) {
    var start = currentAction.points[0];
    var length = getDist(start, [x, y]);
    var steps = Math.max(1, Math.ceil(length / 4)); // evenly spaced points keep perfect freehand smooth
    var points = [];
    for (var i = 0; i <= steps; i++) {
        var t = i / steps;
        points.push([start[0] + (x - start[0]) * t, start[1] + (y - start[1]) * t, straightLine.pressure, straightLine.width]);
    }
    currentAction.points = points;
}

function draw_straight_line_preview() {
    var pts = currentAction.points;
    secondary_ctx.clearRect(0, 0, ctx.canvas.width, ctx.canvas.height);
    if (currentAction.type == 'P') {
        secondary_ctx.fill(new Path2D(getFreeDrawSvgPath(pts, currentAction.width, true)));
    } else {
        secondary_ctx.beginPath();
        secondary_ctx.moveTo(pts[0][0], pts[0][1]);
        secondary_ctx.lineTo(pts[pts.length - 1][0], pts[pts.length - 1][1]);
        secondary_ctx.lineWidth = straightLine.width;
        secondary_ctx.stroke();
    }
}

var tempColor = ""; // The variable to change
var eraseMode = false // Are we currently drawing the erase line?
var intervalId = null; // To track the interval

// Function to update the variable and display
function updateVariable() {
    variable += 1; // Increment the variable
    status.textContent = `Variable Value: ${variable}`; // Update display
}

document.addEventListener('keydown', function(e) {
    // For hold mode, start deleting when shift+d is pressed
    if(textWriting)return;
    if ((e.key === 'Delete' || e.key === 'Backspace') && selectedIndices.length) {
        e.preventDefault();
        delete_selection();
        return;
    }
    if ((e.keyCode == 68 || e.key == "d") && e.shiftKey) {
        e.preventDefault();
        // Only activate if this is NOT a repeat event (first press)
        if (!e.repeat) {
            enter_stroke_delete_mode();
        }
    }

});

document.addEventListener('keyup', function(e) {
    // For hold mode, stop deleting when shift+d is released
    if ((e.keyCode == 68 || e.key == "d") && isDeleting) {
        finishDelete()
        exit_stroke_delete_mode();
    }
});
// TODO chinese mode?
// TODO save draw info in cards, no need to save redos
// TODO make clear per side of card by marking which items have been cleared
// TODO add merging of front into back for correct behaviour with saving draw info
// TODO add toggle to not apply front card to the back one
// TODO clear history button?
// ----------------------------------------- Hotkeys and tooltips -----------------------------------------
// Single source of truth: the keyup handler below and the toolbar tooltips both read this table,
// so a tooltip always shows the key that actually triggers the button.
var ts_hotkeys = {
    visibility:       { name: 'Toggle visibility',          key: ',',  action: switch_visibility },
    perfect_freehand: { name: 'Perfect Freehand',            key: 'x',  alt: true, action: switch_perfect_freehand },
    calligraphy:      { name: 'Calligrapher',                key: 'c',  alt: true, action: switch_calligraphy_mode },
    text:             { name: 'Text writing',                key: 't',  alt: true, action: switch_text_writing_mode },
    stroke_delete:    { name: 'Stroke delete (circle to erase inside)', key: 'd', alt: true, extra: 'hold Shift + D',
                        action: function() { finishDelete(); switch_stroke_delete_mode(); } },
    select:           { name: 'Select (lasso, then drag to move)', key: 's', alt: true, action: switch_select_mode },
    delete_selection: { name: 'Delete selection',            label: 'Delete / Backspace' },
    undo:             { name: 'Undo',                        key: 'z',  alt: true, action: ts_undo },
    redo:             { name: 'Redo',                        key: 'y',  alt: true, action: ts_redo },
    clear:            { name: 'Clear canvas',                key: '.',  action: add_clear_marker },
    fullscreen:       { name: 'Toggle fullscreen canvas',    key: 'b',  alt: true, action: switch_small_canvas },
    pen1:             { name: 'Pen 1',                       key: '1',  alt: true, action: activate_pen1 },
    pen2:             { name: 'Pen 2',                       key: '2',  alt: true, action: activate_pen2 },
    pen3:             { name: 'Pen 3',                       key: '3',  alt: true, action: activate_pen3 },
    pen4:             { name: 'Pen 4',                       key: '4',  alt: true, action: activate_pen4 },
    sound:            { name: 'Replay card audio',           label: 'R' }, // handled by Anki itself
};

function hotkey_label(hk) {
    if (hk.label) return hk.label;
    var names = { ',': ', (comma)', '.': '. (dot)' };
    var label = (hk.alt ? 'Alt + ' : '') + (names[hk.key] || hk.key.toUpperCase());
    return hk.extra ? label + ', or ' + hk.extra : label;
}

function hotkey_matches(hk, e) {
    if (!hk.key || e.ctrlKey || e.metaKey || !!hk.alt !== e.altKey) return false;
    if (hk.alt) {
        // keyCode keeps Alt shortcuts working on layouts where Alt changes e.key
        return e.keyCode === hk.key.toUpperCase().charCodeAt(0) || (e.key && e.key.toLowerCase() === hk.key);
    }
    return e.key === hk.key;
}

document.addEventListener('keyup', function(e) {
    for (var id in ts_hotkeys) {
        var hk = ts_hotkeys[id];
        if (!hk.action || !hotkey_matches(hk, e)) continue;
        if (!hk.alt && textWriting) continue; // plain keys are being typed into a text box
        if (hk.alt) e.preventDefault();
        hk.action();
    }
});

function show_tooltip(button) {
    var hk = ts_hotkeys[button.dataset.hotkey];
    if (!hk) return;
    ts_tooltip.textContent = hk.name;
    var key = document.createElement('span');
    key.className = 'ts_key';
    key.textContent = hotkey_label(hk);
    ts_tooltip.appendChild(key);
    ts_tooltip.style.display = 'block';

    var r = button.getBoundingClientRect();
    var w = ts_tooltip.offsetWidth, h = ts_tooltip.offsetHeight, gap = 8, left, top;
    var vertical = getComputedStyle(optionBar).flexDirection.indexOf('column') === 0;
    if (vertical) { // bar on the left or right edge: show beside it, towards the middle of the screen
        left = (r.left > window.innerWidth / 2) ? r.left - w - gap : r.right + gap;
        top = r.top + (r.height - h) / 2;
    } else { // bar along the top or bottom: show below or above it
        left = r.left + (r.width - w) / 2;
        top = (r.top < window.innerHeight / 2) ? r.bottom + gap : r.top - h - gap;
    }
    ts_tooltip.style.left = Math.max(4, Math.min(left, window.innerWidth - w - 4)) + 'px';
    ts_tooltip.style.top = Math.max(4, Math.min(top, window.innerHeight - h - 4)) + 'px';
}

function hide_tooltip() {
    ts_tooltip.style.display = 'none';
}

optionBar.querySelectorAll('button[data-hotkey]').forEach(function(button) {
    button.addEventListener('pointerenter', function() { show_tooltip(button); });
    button.addEventListener('pointerleave', hide_tooltip);
});

// Brief message in the top right corner, e.g. after undo
var toastTimer = null;
function show_toast(message) {
    ts_toast.textContent = message;
    ts_toast.style.right = '12px';
    // Don't cover the toolbar when it sits in the top right corner
    var bar = optionBar.getBoundingClientRect();
    if (bar.width && bar.right > window.innerWidth - 80 && bar.top < 80) {
        ts_toast.style.right = (window.innerWidth - bar.left + 8) + 'px';
    }
    ts_toast.classList.add('show');
    clearTimeout(toastTimer);
    toastTimer = setTimeout(function() { ts_toast.classList.remove('show'); }, 1200);
}

function describe_action(action) {
    switch (action.type) {
        case 'L':
        case 'P': return 'stroke';
        case 'C': return 'calligraphy stroke';
        case 'T': return 'text "' + (action.text.length > 20 ? action.text.slice(0, 20) + '...' : action.text) + '"';
        case 'D': return 'delete (' + action.deletedList.length + (action.deletedList.length == 1 ? ' item)' : ' items)');
        case 'M': return 'move (' + action.movedList.length + (action.movedList.length == 1 ? ' item)' : ' items)');
        case 'X': return 'clear canvas';
        default: return 'last action';
    }
}

// ----------------------------------------- Stroke Delete -----------------------------------------


function doLinesIntersect(line1, line2) {
    function lineLine(x1, y1, x2, y2, x3, y3, x4, y4) {
        // calculate the distance to intersection point
        var uA = ((x4-x3)*(y1-y3) - (y4-y3)*(x1-x3)) / ((y4-y3)*(x2-x1) - (x4-x3)*(y2-y1));
        var uB = ((x2-x1)*(y1-y3) - (y2-y1)*(x1-x3)) / ((y4-y3)*(x2-x1) - (x4-x3)*(y2-y1));

        // if uA and uB are between 0-1, lines are colliding
        if (uA >= 0 && uA <= 1 && uB >= 0 && uB <= 1) {
            return true;
        }
    return false;
    }
    // Iterate over all points in the two arrays
    for (let i = 0; i < line1.length - 1; i++) {
        for (let j = 0; j < line2.length - 1; j++) {
            if (lineLine(line1[i][0], line1[i][1], line1[i + 1][0], line1[i + 1][1], line2[j][0], line2[j][1], line2[j + 1][0], line2[j + 1][1])) {
                return true; // Lines intersect
            }
        }
    }

    return false; // No intersections
}

function pointerDownStrokeDelete(e) {
    wrapper.classList.add('nopointer');
    if (!e.isPrimary || !strokeDelete) { return; }
    submitCurrentText()
    e.preventDefault();
    // Use solid red for delete mode, not transparent
    var pen = getPenColorAndWidthByIndex(activePenIndex);
    currentAction = {
        points: [],
        color: "rgba(255, 0, 0, 1)",
        width: 4,
        opacity: '1',
        visible: true,
        type: 'D', // 'simple', 'perfect', or 'calligraphy'
    };
    secondary_ctx.strokeStyle = secondary_ctx.fillStyle = currentAction.color;
    secondary_ctx.lineWidth = currentAction.width;

    start_drawing();
};

function pointerMoveStrokeDelete(e) {
    if (!e.isPrimary || !strokeDelete) { return; }
    if(isPointerDown) {
        var mousePos = [e.offsetX, e.offsetY];
        if(currentAction.points.length != 0) {
            if(getDist(mousePos,currentAction.points[currentAction.points.length-1])>=MIN_MOUSE_DIST)
                currentAction.points.push(mousePos);
            secondary_ctx.lineWidth = 4;
            drawCurrentPath();
        } else
            currentAction.points.push(mousePos);
    } 
};

function finishDelete(){
    if (!strokeDelete || !currentAction.points || !currentAction.points.length) { return; }
    stop_drawing();
    var pen = getPenColorAndWidthByIndex(activePenIndex)
    secondary_ctx.strokeStyle = pen[0] // active pen Color;
    secondary_ctx.fillStyle = pen[0] //active pen Color;
    secondary_ctx.lineWidth = pen[1] //active pen Color;
    marked_lines = []
    // A closed delete stroke (circle, or any loop) also erases everything inside it
    var loop = get_closed_loop(currentAction.points);
    for (let lineIndex = 0; lineIndex < lineHistory.length; lineIndex++) {
        const element = lineHistory[lineIndex];
        if(!is_selectable_index(lineIndex)) continue;
        if(doLinesIntersect(element.points, currentAction.points) || (loop && count_points_inside(element.points, loop) > 0)){
            element.visible = false;//mark as deleted
            marked_lines.push(lineIndex)//add reference for easy undo
        }
    }
    if(marked_lines.length){
        currentAction.deletedList = marked_lines;//add list of lines which were deleted to the list
        currentAction.type = 'D'
        add_action_to_history(currentAction);
    }
    secondary_ctx.clearRect(0, 0, ctx.canvas.width, ctx.canvas.height);//clear the guide line in second canvas
    refresh_selection()
    ts_redraw()
}

function pointerUpStrokeDelete(e) {
    wrapper.classList.remove('nopointer');
    stop_drawing();
    if (!e.isPrimary || !strokeDelete || !currentAction.points || !currentAction.points.length) { return; }
    finishDelete();
};

// ----------------------------------------- Selection -----------------------------------------
// Lasso tool (Alt + s) selects strokes and text. A selection can be dragged from any tool:
// hovering over it shows the move cursor. Delete / Backspace or the bin button removes it.

var selectedIndices = [];
var selectionDrag = null;  // { start, dx, dy, indexSet } while dragging
var lassoPoints = null;    // points of the lasso being drawn
var lastPointerType = '';

function canvas_point(e) {
    // Same space as e.offsetX on the canvas, but also valid while the pointer is outside it
    var rect = secondary_canvas.getBoundingClientRect();
    return [e.clientX - rect.left - secondary_canvas.clientLeft, e.clientY - rect.top - secondary_canvas.clientTop];
}

function is_canvas_target(e) {
    return e.target === canvas || e.target === secondary_canvas;
}

function last_clear_index() {
    for (var i = lineHistory.length - 1; i >= 0; i--) {
        if (lineHistory[i].type == 'X') return i;
    }
    return -1;
}

// Only drawn things that are on screen can be selected or deleted
function is_selectable_index(i) {
    var a = lineHistory[i];
    return !!a && a.visible && ['L', 'P', 'C', 'T'].indexOf(a.type) >= 0 &&
        !!a.points && a.points.length > 0 && i > last_clear_index();
}

function action_half_width(a) {
    if (a.type == 'T') return 2;
    var w = a.width || 1;
    if (a.type == 'L') a.points.forEach(p => { if (p[3] > w) w = p[3]; });
    return w / 2;
}

function action_bounds(a) {
    var b = { minX: Infinity, minY: Infinity, maxX: -Infinity, maxY: -Infinity };
    a.points.forEach(p => {
        if (p[0] < b.minX) b.minX = p[0];
        if (p[0] > b.maxX) b.maxX = p[0];
        if (p[1] < b.minY) b.minY = p[1];
        if (p[1] > b.maxY) b.maxY = p[1];
    });
    var pad = action_half_width(a);
    b.minX -= pad; b.minY -= pad; b.maxX += pad; b.maxY += pad;
    return b;
}

function selection_box() {
    if (!selectedIndices.length) return null;
    var box = { minX: Infinity, minY: Infinity, maxX: -Infinity, maxY: -Infinity };
    selectedIndices.forEach(i => {
        var b = action_bounds(lineHistory[i]);
        box.minX = Math.min(box.minX, b.minX); box.minY = Math.min(box.minY, b.minY);
        box.maxX = Math.max(box.maxX, b.maxX); box.maxY = Math.max(box.maxY, b.maxY);
    });
    var pad = 6, dx = selectionDrag ? selectionDrag.dx : 0, dy = selectionDrag ? selectionDrag.dy : 0;
    return { minX: box.minX - pad + dx, minY: box.minY - pad + dy, maxX: box.maxX + pad + dx, maxY: box.maxY + pad + dy };
}

function point_in_box(pt, box) {
    return !!box && pt[0] >= box.minX && pt[0] <= box.maxX && pt[1] >= box.minY && pt[1] <= box.maxY;
}

function point_in_polygon(pt, poly) {
    var inside = false;
    for (var i = 0, j = poly.length - 1; i < poly.length; j = i++) {
        var xi = poly[i][0], yi = poly[i][1], xj = poly[j][0], yj = poly[j][1];
        if (((yi > pt[1]) != (yj > pt[1])) && (pt[0] < (xj - xi) * (pt[1] - yi) / (yj - yi) + xi)) inside = !inside;
    }
    return inside;
}

function count_points_inside(points, poly) {
    var n = 0;
    points.forEach(p => { if (point_in_polygon(p, poly)) n++; });
    return n;
}

function segments_intersect(a, b, c, d) {
    var den = (d[1] - c[1]) * (b[0] - a[0]) - (d[0] - c[0]) * (b[1] - a[1]);
    if (den === 0) return false;
    var uA = ((d[0] - c[0]) * (a[1] - c[1]) - (d[1] - c[1]) * (a[0] - c[0])) / den;
    var uB = ((b[0] - a[0]) * (a[1] - c[1]) - (b[1] - a[1]) * (a[0] - c[0])) / den;
    return uA >= 0 && uA <= 1 && uB >= 0 && uB <= 1;
}

// Returns the polygon enclosed by a stroke, or null if the stroke isn't a closed shape.
// Closed means the ends meet up, or the stroke crosses itself (the biggest loop is used).
function get_closed_loop(points) {
    if (!points || points.length < 4) return null;
    var minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity;
    points.forEach(p => {
        minX = Math.min(minX, p[0]); maxX = Math.max(maxX, p[0]);
        minY = Math.min(minY, p[1]); maxY = Math.max(maxY, p[1]);
    });
    var size = Math.hypot(maxX - minX, maxY - minY);
    if (size < 20) return null;
    if (getDist(points[0], points[points.length - 1]) <= Math.max(20, size * 0.15)) return points;
    var best = null;
    for (var i = 0; i < points.length - 1; i++) {
        for (var j = points.length - 2; j > i + 1; j--) {
            if (best && j - i <= best[1] - best[0]) break;
            if (segments_intersect(points[i], points[i + 1], points[j], points[j + 1])) { best = [i, j]; break; }
        }
    }
    return best ? points.slice(best[0] + 1, best[1] + 1) : null;
}

function distance_to_segment(p, a, b) {
    var dx = b[0] - a[0], dy = b[1] - a[1];
    var len2 = dx * dx + dy * dy;
    var t = len2 ? Math.max(0, Math.min(1, ((p[0] - a[0]) * dx + (p[1] - a[1]) * dy) / len2)) : 0;
    return Math.hypot(p[0] - (a[0] + t * dx), p[1] - (a[1] + t * dy));
}

function action_hit(a, pt) {
    if (a.type == 'T') return point_in_box(pt, action_bounds(a));
    var tol = action_half_width(a) + 6, pts = a.points;
    if (pts.length == 1) return getDist(pt, pts[0]) <= tol;
    for (var i = 0; i < pts.length - 1; i++) {
        if (distance_to_segment(pt, pts[i], pts[i + 1]) <= tol) return true;
    }
    return false;
}

function select_with_lasso(points) {
    var minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity;
    points.forEach(p => {
        minX = Math.min(minX, p[0]); maxX = Math.max(maxX, p[0]);
        minY = Math.min(minY, p[1]); maxY = Math.max(maxY, p[1]);
    });
    var found = [];
    if (maxX - minX < 8 && maxY - minY < 8) {
        // A tap selects the topmost thing under the pen
        for (var i = lineHistory.length - 1; i >= 0; i--) {
            if (is_selectable_index(i) && action_hit(lineHistory[i], points[0])) { found.push(i); break; }
        }
    } else {
        for (var i = 0; i < lineHistory.length; i++) {
            if (!is_selectable_index(i)) continue;
            var pts = lineHistory[i].points;
            if (count_points_inside(pts, points) * 2 >= pts.length) found.push(i); // mostly inside the lasso
        }
    }
    set_selection(found);
}

function set_selection(indices) {
    selectedIndices = indices;
    ts_delete_selection_button.className = selectedIndices.length ? 'active' : '';
    if (!selectedIndices.length) set_canvas_cursor('');
    draw_selection_overlay();
}

function clear_selection() {
    selectionDrag = null;
    if (!selectedIndices.length) return;
    set_selection([]);
}

// Drop things from the selection that were deleted some other way
function refresh_selection() {
    if (selectedIndices.length) set_selection(selectedIndices.filter(is_selectable_index));
}

function set_canvas_cursor(cursor) {
    if (secondary_canvas.style.cursor !== cursor) secondary_canvas.style.cursor = canvas.style.cursor = cursor;
}

function draw_selection_overlay() {
    secondary_ctx.clearRect(0, 0, ctx.canvas.width, ctx.canvas.height);
    var box = selection_box();
    if (!box) return;
    secondary_ctx.save();
    secondary_ctx.setLineDash([6, 4]);
    secondary_ctx.lineWidth = 1.5;
    secondary_ctx.strokeStyle = 'rgba(30, 144, 255, 1)';
    secondary_ctx.fillStyle = 'rgba(30, 144, 255, 0.08)';
    secondary_ctx.fillRect(box.minX, box.minY, box.maxX - box.minX, box.maxY - box.minY);
    secondary_ctx.strokeRect(box.minX, box.minY, box.maxX - box.minX, box.maxY - box.minY);
    secondary_ctx.restore();
}

function draw_lasso() {
    secondary_ctx.clearRect(0, 0, ctx.canvas.width, ctx.canvas.height);
    if (!lassoPoints || lassoPoints.length < 2) return;
    secondary_ctx.save();
    secondary_ctx.setLineDash([5, 5]);
    secondary_ctx.lineWidth = 1.5;
    secondary_ctx.strokeStyle = 'rgba(30, 144, 255, 1)';
    secondary_ctx.beginPath();
    secondary_ctx.moveTo(lassoPoints[0][0], lassoPoints[0][1]);
    lassoPoints.forEach(p => secondary_ctx.lineTo(p[0], p[1]));
    secondary_ctx.closePath();
    secondary_ctx.stroke();
    secondary_ctx.restore();
}

function translate_actions(indices, dx, dy) {
    indices.forEach(i => {
        var a = lineHistory[i];
        a.points.forEach(p => { p[0] += dx; p[1] += dy; });
        if (a.type == 'T') { a.x += dx; a.y += dy; }
        stroke_cache[i] = null; // cached Path2D / calligraphy shapes are at the old position
    });
}

function delete_selection() {
    if (!selectedIndices.length) return;
    stop_drawing();
    var deleted = selectedIndices.slice();
    deleted.forEach(i => { lineHistory[i].visible = false; });
    add_action_to_history({ type: 'D', points: [], deletedList: deleted, color: 'rgba(255, 0, 0, 1)', width: 4, opacity: '1', visible: true });
    clear_selection();
    ts_redraw();
}

// These run in the capture phase on window, before the drawing tools' own handlers,
// so a drag on the selection never also starts a stroke.
function selectionPointerDown(e) {
    hide_tooltip();
    if (!e.isPrimary) return;
    lastPointerType = e.pointerType;
    if (selectionDrag || lassoPoints) { e.stopPropagation(); e.preventDefault(); return; } // duplicate pointer
    if (!is_canvas_target(e) || e.button > 0) return;
    var pt = canvas_point(e);
    if (point_in_box(pt, selection_box())) {
        e.stopPropagation();
        e.preventDefault();
        submitCurrentText();
        selectionDrag = { start: pt, dx: 0, dy: 0, indexSet: new Set(selectedIndices) };
        ts_redraw();
        draw_selection_overlay();
        return;
    }
    clear_selection();
    if (selectMode) {
        e.stopPropagation();
        e.preventDefault();
        submitCurrentText();
        wrapper.classList.add('nopointer');
        lassoPoints = [pt];
    }
}

function selectionPointerMove(e) {
    if (!e.isPrimary) return;
    if (selectionDrag) {
        e.stopPropagation();
        e.preventDefault();
        var pt = canvas_point(e);
        selectionDrag.dx = pt[0] - selectionDrag.start[0];
        selectionDrag.dy = pt[1] - selectionDrag.start[1];
        ts_redraw();
        draw_selection_overlay();
        return;
    }
    if (lassoPoints) {
        e.stopPropagation();
        e.preventDefault();
        var pt = canvas_point(e);
        if (getDist(pt, lassoPoints[lassoPoints.length - 1]) >= 3) {
            lassoPoints.push(pt);
            draw_lasso();
        }
        return;
    }
    if (selectedIndices.length && is_canvas_target(e) && !isPointerDown) {
        set_canvas_cursor(point_in_box(canvas_point(e), selection_box()) ? 'move' : '');
    }
}

function selectionPointerUp(e) {
    if (!e.isPrimary) return;
    if (selectionDrag) {
        e.stopPropagation();
        var drag = selectionDrag;
        selectionDrag = null;
        if (Math.abs(drag.dx) + Math.abs(drag.dy) >= 1) {
            translate_actions(selectedIndices, drag.dx, drag.dy);
            add_action_to_history({ type: 'M', movedList: selectedIndices.slice(), dx: drag.dx, dy: drag.dy, visible: true });
        }
        ts_redraw();
        draw_selection_overlay();
        return;
    }
    if (lassoPoints) {
        e.stopPropagation();
        wrapper.classList.remove('nopointer');
        var points = lassoPoints;
        lassoPoints = null;
        select_with_lasso(points);
    }
}

window.addEventListener('pointerdown', selectionPointerDown, true);
window.addEventListener('pointermove', selectionPointerMove, true);
window.addEventListener('pointerup', selectionPointerUp, true);
window.addEventListener('pointercancel', selectionPointerUp, true);

// Windows turns a long pen press into a right click; don't let that interrupt drawing
wrapper.addEventListener('contextmenu', function(e) {
    if (is_canvas_target(e) && lastPointerType === 'pen') e.preventDefault();
});

// ----------------------------------------- Perfect Freehand -----------------------------------------

// The rest of the code gets loaded in from PerfectFreehand.js

function med(A, B) {
  return [(A[0] + B[0]) / 2, (A[1] + B[1]) / 2];
}

// Trim SVG path data so number are each two decimal points. This
// improves SVG exports, and prevents rendering errors on points
// with long decimals.
const TO_FIXED_PRECISION = /(\s?[A-Z]?,?-?[0-9]*\.[0-9]{0,2})(([0-9]|e|-)*)/g;

function getSvgPathFromStroke(points){
  if (!points.length) {
    return "";
  }

  const max = points.length - 1;

  return points
    .reduce(
      (acc, point, i, arr) => {
        if (i === max) {
          acc.push(point, med(point, arr[0]), "L", arr[0], "Z");
        } else {
          acc.push(point, med(point, arr[i + 1]));
        }
        return acc;
      },
      ["M", points[0], "Q"],
    )
    .join(" ")
    .replace(TO_FIXED_PRECISION, "$1");
}

function getFreeDrawSvgPath(inputPoints, width, complete) {
  // Consider changing the options for simulated pressure vs real pressure

  const options = {
    simulatePressure: inputPoints[0][2] > 1,
    size: width,
    thinning: 0.6,
    smoothing: 0.5,
    streamline: 0.5,
    easing: (t) => Math.sin((t * Math.PI) / 2), // https://easings.net/#easeOutSine
    last: complete, // LastCommittedPoint is added on pointerup
  };

  return getSvgPathFromStroke(getStroke(inputPoints, options));
}
/*
 -------------------------------- Caligrapher ------------------------------------------
 Created By: August Toman-Yih
 Git Repository: https://github.com/atomanyih/Calligrapher
*/
/* ------------------------------        script.js        -----------------------------*/

// The rest of the code gets loaded in from Caligrapher.js

//Modified to work with current canvas and board
//share the same canvas with pressure drawing
 /*var canvas = document.getElementById('canvas'),
    width = canvas.width,
    height = canvas.height,
    context = canvas.getContext("2d");
	*/

//FIXME REORGANIZE EBERYTING
//--- constants ---//
RESOLUTION = 4; 
WEIGHT = 15;
MIN_MOUSE_DIST = 5;
SPLIT_THRESHOLD = 8;
SQUARE_SIZE = 300;

function drawCurrentPath() {
    secondary_ctx.beginPath();
    secondary_ctx.moveTo(currentAction.points[0][0],currentAction.points[0][1]);
    for(var i = 1; i<currentAction.points.length; i++) {
        secondary_ctx.lineTo(currentAction.points[i][0],currentAction.points[i][1]);
    } 
    secondary_ctx.stroke();
}

function pointerDownCaligraphy(e) {
    wrapper.classList.add('nopointer');
    if (!e.isPrimary || !calligraphy) { return; }
    e.preventDefault();//don't paint anything when clicking on buttons, especially for undo to work
    var pen = getPenColorAndWidthByIndex(activePenIndex);
    currentAction = {
        points: [],
        color: pen[0],
        width: pen[1],
        opacity: pen[2],
        visible: true,
        type: 'C', // 'simple', 'perfect', or 'calligraphy'
    };
    start_drawing();
};

function pointerMoveCaligraphy(e) {
    if (!e.isPrimary || !calligraphy) { return; }
    if(isPointerDown) {
        var mousePos = [e.offsetX, e.offsetY];
        if(currentAction.points.length != 0) {
            if(getDist(mousePos,currentAction.points[currentAction.points.length-1])>=MIN_MOUSE_DIST)
                currentAction.points.push(mousePos);
            drawCurrentPath();
        } else
            currentAction.points.push(mousePos);
    } 
};

function pointerUpCaligraphy(e) {
    wrapper.classList.remove('nopointer');
    stop_drawing();
    if (!e.isPrimary || !calligraphy || !currentAction.points || !currentAction.points.length) { return; }
    
    add_action_to_history(currentAction)
    secondary_ctx.clearRect(0, 0, ctx.canvas.width, ctx.canvas.height);//clear the guide line in second canvas
};
</script>
"""

def custom(*args, **kwargs):
    global ts_state_on
    default = ts_default_review_html(*args, **kwargs)
    if not ts_state_on:
        return default
    output = (
        default +
        blackboard_html() +
        blackboard_css() +
        blackboard_js() +
        "<script>" +
        caligrapher_js +
        perfect_freehand_js+
        "</script>"
    )
    return output
mw.reviewer.revHtml = custom


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
    value, accepted = QInputDialog.getDouble(mw, "AnkiDraw", f"Enter the pen {pen_number} width:", current_width)
    
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
    value, accepted = QInputDialog.getDouble(mw, "AnkiDraw", f"Enter the pen {pen_number} opacity (0-1):", current_opacity, 0, 1, 2)
    
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

        self.setWindowTitle("AnkiDraw Toolbar And Canvas")

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

def ts_apply_pressure_settings():
    ts_menu_pressure.setChecked(ts_pressure_sensitivity)
    execute_js("pressureSensitivity = " + str(ts_pressure_sensitivity).lower() + ";")
    execute_js("fixedPressure = " + str(ts_fixed_pressure) + ";")
    execute_js("if (typeof resize === 'function') { resize(); }")

@slot()
def ts_change_pressure_sensitivity_settings():
    """
    Switch pressure sensitivity setting.
    """
    global ts_pressure_sensitivity
    ts_pressure_sensitivity = not ts_pressure_sensitivity
    ts_apply_pressure_settings()

class PenPressureDialog(QDialog):
    def __init__(self, pressure_enabled, fixed_pressure):
        super().__init__(mw)
        self.setWindowTitle("AnkiDraw Pen Pressure")

        self.pressure_checkbox = QCheckBox("Use pen pressure sensitivity")
        self.pressure_checkbox.setChecked(pressure_enabled)

        self.slider_label = QLabel()
        self.slider = QSlider(Qt.Orientation.Horizontal)
        self.slider.setRange(1, 100)
        self.slider.setValue(round(fixed_pressure * 100))

        self.hint = QLabel("When pressure sensitivity is off, every stroke (pen, mouse or touch) "
                           "is drawn as if pressed this hard. Higher means thicker lines.")
        self.hint.setWordWrap(True)

        self.pressure_checkbox.toggled.connect(self.update_state)
        self.slider.valueChanged.connect(self.update_state)

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

        layout = QVBoxLayout()
        layout.addWidget(self.pressure_checkbox)
        layout.addWidget(self.slider_label)
        layout.addWidget(self.slider)
        layout.addWidget(self.hint)
        layout.addLayout(button_layout)
        self.setLayout(layout)
        self.setMinimumWidth(360)
        self.update_state()

    def update_state(self):
        fixed = not self.pressure_checkbox.isChecked()
        for widget in (self.slider_label, self.slider, self.hint):
            widget.setEnabled(fixed)
        self.slider_label.setText(f"Fixed pressure: {self.slider.value()}%")

    def reset_to_default(self):
        self.pressure_checkbox.setChecked(saved_value_defaults['ts_pressure_sensitivity'])
        self.slider.setValue(round(saved_value_defaults['ts_fixed_pressure'] * 100))

@slot()
def ts_change_pen_pressure_settings():
    global ts_pressure_sensitivity, ts_fixed_pressure
    dialog = PenPressureDialog(ts_pressure_sensitivity, ts_fixed_pressure)
    if dialog.exec() == QDialog.DialogCode.Accepted:
        ts_pressure_sensitivity = dialog.pressure_checkbox.isChecked()
        ts_fixed_pressure = dialog.slider.value() / 100
        ts_apply_pressure_settings()
    
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
        showWarning("No profile loaded. AnkiPenDown may not work correctly.")
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
    Switch AnkiDraw.
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

    try:
        mw.addon_view_menu
    except AttributeError:
        mw.addon_view_menu = QMenu("""&AnkiDraw""", mw)
        mw.form.menubar.insertMenu(mw.form.menuTools.menuAction(),
                                    mw.addon_view_menu)

    # mw.ts_menu = QMenu(_('&AnkiDraw'), mw)

    # mw.addon_view_menu.addMenu(mw.ts_menu)

    ts_menu_switch = QAction("""&Enable Ankidraw""", mw, checkable=True)
    ts_menu_pressure = QAction("""Enable &pressure sensitivity""", mw, checkable=True)
    ts_menu_auto_hide = QAction("""Auto &hide toolbar when drawing""", mw, checkable=True)
    ts_menu_auto_hide_pointer = QAction("""Auto &hide pointer when drawing""", mw, checkable=True)
    ts_menu_follow = QAction("""&Follow when scrolling (speedup draw)""", mw, checkable=True)
    ts_menu_small_default = QAction("""&Small Canvas by default (speedup draw)""", mw, checkable=True)
    ts_menu_zen_mode = QAction("""Enable Zen Mode(hide toolbar until disabled)""", mw, checkable=True)
    ts_toolbar_settings = QAction("""&Toolbar and canvas location settings""", mw)
    ts_pressure_settings = QAction("""Pen p&ressure settings...""", mw)
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

    mw.addon_view_menu.addAction(ts_menu_switch)
    mw.addon_view_menu.addAction(ts_menu_pressure)
    mw.addon_view_menu.addAction(ts_menu_auto_hide)
    mw.addon_view_menu.addAction(ts_menu_auto_hide_pointer)
    mw.addon_view_menu.addAction(ts_menu_follow)
    mw.addon_view_menu.addAction(ts_menu_small_default)
    mw.addon_view_menu.addAction(ts_menu_zen_mode)
    mw.addon_view_menu.addMenu(ts_pen_color_menu)
    mw.addon_view_menu.addMenu(ts_pen_width_menu)
    mw.addon_view_menu.addMenu(ts_pen_opacity_menu)
    mw.addon_view_menu.addAction(ts_pressure_settings)
    mw.addon_view_menu.addAction(ts_toolbar_settings)
    mw.addon_view_menu.addAction(ts_font_settings)

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
    ts_pressure_settings.triggered.connect(ts_change_pen_pressure_settings)
    ts_font_settings.triggered.connect(ts_change_font_settings)

#
# ONLOAD SECTION
#
def ts_onload():
    """
    Add hooks and initialize menu.
    Call to this function is placed on the end of this file.
    """
    addHook("unloadProfile", ts_save)
    addHook("profileLoaded", ts_load)
    addHook("showQuestion", clear_blackboard)
    addHook("showAnswer", resize_js)
    ts_setup_menu()

ts_onload()