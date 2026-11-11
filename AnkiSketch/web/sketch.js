/*
 * AnkiSketch — drawing layer for the Anki reviewer.
 * Fork of AnkiDraw (https://github.com/Rytisgit/Anki-StylusDraw) by Rytisgit,
 * itself based on Anki-TouchScreen by Michal Krassowski. GPL-3.0-or-later.
 *
 * Settings come from Python (__init__.py) via window.AnkiSketchConfig,
 * which is written inline just before this script.
 */
var AnkiSketchSettings = window.AnkiSketchConfig.settings;
var visible = true;
var perfectFreehand = false;
var pressureSensitivity = AnkiSketchSettings.pressureSensitivity;
var small_canvas = AnkiSketchSettings.smallCanvas;
var fullscreen_follow = AnkiSketchSettings.follow;
var calligraphy = false;
var strokeDelete = false;
var textWriting = false;
var isDeleting = false;  // Track if currently deleting (for hold mode)
var pen1Color = AnkiSketchSettings.pens[0].color;
var pen1Width = AnkiSketchSettings.pens[0].width;
var pen2Color = AnkiSketchSettings.pens[1].color;
var pen2Width = AnkiSketchSettings.pens[1].width;
var pen3Color = AnkiSketchSettings.pens[2].color;
var pen3Width = AnkiSketchSettings.pens[2].width;
var pen4Color = AnkiSketchSettings.pens[3].color;
var pen4Width = AnkiSketchSettings.pens[3].width;
var pen1Opacity = AnkiSketchSettings.pens[0].opacity;
var pen2Opacity = AnkiSketchSettings.pens[1].opacity;
var pen3Opacity = AnkiSketchSettings.pens[2].opacity;
var pen4Opacity = AnkiSketchSettings.pens[3].opacity;
var fontFamily = AnkiSketchSettings.font.family;
var fontSize = AnkiSketchSettings.font.size;
var fontBold = AnkiSketchSettings.font.bold;
var fontItalic = AnkiSketchSettings.font.italic;
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
var ts_switch_fullscreen_button = document.getElementById('ts_switch_fullscreen_button');
var ts_select_button = document.getElementById('ts_select_button');
var selection_canvas = document.getElementById('selection_canvas');
var selection_ctx = selection_canvas.getContext('2d');
var selectMode = false;     // Select (lasso) tool chosen on the toolbar / by hotkey


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
    activePenIndex = 0
    recolor_selection_to_active_pen();
    update_pen_settings();
}

function activate_pen2()
{
    activePenIndex = 1
    recolor_selection_to_active_pen();
    update_pen_settings();
}

function activate_pen3()
{
    activePenIndex = 2
    recolor_selection_to_active_pen();
    update_pen_settings();
}

function activate_pen4()
{
    activePenIndex = 3
    recolor_selection_to_active_pen();
    update_pen_settings();
}

function reset_drawing_modes()
{
    ts_kanji_button.className = '';
    ts_perfect_freehand_button.className = '';
    ts_stroke_delete_button.className = '';
    ts_text_button.className = '';
    calligraphy = false;
    perfectFreehand = false;
    strokeDelete = false
    textWriting = false;
    selectMode = false;
    ts_select_button.className = '';
    clear_selection();
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
selectMode_activated = false;

function save_drawing_modes_for_delete()
{
    ts_kanji_button_class = ts_kanji_button.className;
    ts_perfect_freehand_button_class = ts_perfect_freehand_button.className;
    ts_text_button_class = ts_text_button.className;
    calligraphy_activated = calligraphy
    perfectFreehand_activated = perfectFreehand
    textWriting_activated = textWriting
    selectMode_activated = selectMode
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
    calligraphy = calligraphy_activated
    perfectFreehand = perfectFreehand_activated
    textWriting = textWriting_activated
    selectMode = selectMode_activated
    ts_select_button.className = selectMode ? 'active' : ''
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


function switch_select_mode()
{
    stop_drawing();
    temp = !selectMode;
    reset_drawing_modes()
    selectMode = temp;
    ts_select_button.className = selectMode ? 'active' : '';
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
    if (visible)
    {
        canvas.style.display='none';
        secondary_canvas.style.display=canvas.style.display;
        selection_canvas.style.display=canvas.style.display;
        clear_selection();
        ts_visibility_button.className = '';
        optionBar.className = 'touch_disable';
    }
    else
    {
        canvas.style.display='block';
        secondary_canvas.style.display=canvas.style.display;
        selection_canvas.style.display=canvas.style.display;
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
    selection_canvas.style.height = canvas.style.height;
    selection_canvas.style.width = canvas.style.width;
    
    /* Increase DOM size and scale */
    ctx.canvas.width *= dpr;
    ctx.canvas.height *= dpr;
    ctx.scale(dpr, dpr);
    secondary_ctx.canvas.width *= dpr;
    secondary_ctx.canvas.height *= dpr;
    secondary_ctx.scale(dpr, dpr);
    scratch_canvas.width = ctx.canvas.width;
    scratch_canvas.height = ctx.canvas.height;
    scratch_ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    resize_selection_canvas(dpr);
    
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
    if(lineHistory.length>0){
        var poppedAction = lineHistory.pop()
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
            case 'X'://Clear actions
                break;
            case 'T'://Text Writing actions
                break;
            case 'M'://Move selection
                move_actions(poppedAction.indices, -poppedAction.dx, -poppedAction.dy)
                break;
            case 'R'://Recolour selection
                poppedAction.changes.forEach(ch => { set_action_color(ch.index, ch.from) })
                break;
            default://how did you get here??
                break;
        }
    }

    if(!lineHistory.length)
    {
        ts_undo_button.className = ""
    }
    prune_selection()
    ts_redraw()
}
function ts_redo() {
    stop_drawing();
    if (redoStack.length < 1) return;
    
    var redoAction = redoStack.pop();
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
        case 'X'://Delete Stroke Lines
            break;
        case 'M'://Move selection
            move_actions(redoAction.indices, redoAction.dx, redoAction.dy)
            break;
        case 'R'://Recolour selection
            redoAction.changes.forEach(ch => { set_action_color(ch.index, ch.to) })
            break;
        default://how did you get here??
            break;
    }
    
    prune_selection()
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
    reset_to_main_pen_settings()
    submitCurrentText()
    isPointerDown = false;
	drawingWithPressurePenOnly = false;
}

function start_drawing() {
    clear_selection()
    submitCurrentText()
    isPointerDown = true;
    reset_redo()
}

function draw_last_line_segment() {
    window.requestAnimationFrame(draw_last_line_segment);
    update_cursor();
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

async function draw_secondary_path_at_some_point_async(startX, startY, midX, midY, endX, endY, lineWidth) {
		secondary_ctx.beginPath();
		secondary_ctx.moveTo((startX + (midX - startX) / 2), (startY + (midY - startY)/ 2));//midpoint calculation for x and y
		secondary_ctx.quadraticCurveTo(midX, midY, (midX + (endX - midX) / 2), (midY + (endY - midY)/ 2));
        secondary_ctx.lineWidth = lineWidth;
		secondary_ctx.stroke();
};

var pleaseRedrawEverything = false;
var fullClear = false;

// ----------------------------------------- Rendering -----------------------------------------
// Each finished stroke is drawn opaque onto a scratch canvas, then copied onto the
// main canvas with that stroke's own opacity. This keeps every stroke's opacity
// (switching pens no longer restyles what's already drawn) without the dark
// overlap marks that drawing semi-transparent segments directly gives on Windows.

var scratch_canvas = document.createElement('canvas');
var scratch_ctx = scratch_canvas.getContext('2d');

var DRAWABLE_TYPES = { L: true, P: true, C: true, T: true };

function solid_color(color) {
    return String(color).replace(/[\d\.]+\)$/g, '1)');
}

function action_opacity(action) {
    var o = parseFloat(action.opacity);
    return isNaN(o) ? 1 : Math.max(0, Math.min(1, o));
}

// Bounding box of an action in canvas (CSS pixel) coordinates, padded for stroke width.
function action_bbox(action) {
    if (action._bbox) return action._bbox;
    var pts = action.points || [];
    if (!pts.length) return null;
    var minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity, maxW = 0;
    for (var k = 0; k < pts.length; k++) {
        var p = pts[k];
        if (p[0] < minX) minX = p[0];
        if (p[0] > maxX) maxX = p[0];
        if (p[1] < minY) minY = p[1];
        if (p[1] > maxY) maxY = p[1];
        if (p.length > 3 && p[3] > maxW) maxW = p[3];
    }
    var width = parseFloat(action.width) || 1;
    var pad;
    switch (action.type) {
        case 'L': pad = Math.max(maxW, width) / 2 + 2; break;
        case 'P': pad = width + 2; break;
        case 'C': pad = width * 3 + 20; break;
        default: pad = 4;
    }
    action._bbox = { x: minX - pad, y: minY - pad, w: (maxX - minX) + 2 * pad, h: (maxY - minY) + 2 * pad };
    return action._bbox;
}

function invalidate_action_geometry(i) {
    var action = lineHistory[i];
    if (action) delete action._bbox;
    stroke_cache[i] = null;
}

// Draw one action, opaque, onto context c.
function draw_action_on(c, action, i) {
    var color = solid_color(action.color);
    c.lineJoin = c.lineCap = 'round';
    c.strokeStyle = c.fillStyle = color;
    c.lineWidth = action.width;
    c.globalCompositeOperation = "source-over";
    switch (action.type) {
        case 'C'://Calligraphy
            var calligraphyStroke = stroke_cache[i] || new Stroke(fitStroke(action.points));
            stroke_cache[i] = calligraphyStroke;
            calligraphyStroke.draw(action.width, c);
            break;
        case 'L'://Simple Lines
            var pts = action.points;
            var q1, q2 = pts[0], q3 = pts[0];
            for (var j = 0; j < pts.length; j++) {
                q1 = q2; q2 = q3; q3 = pts[j];
                c.beginPath();
                c.moveTo((q1[0] + (q2[0] - q1[0]) / 2), (q1[1] + (q2[1] - q1[1]) / 2));
                c.quadraticCurveTo(q2[0], q2[1], (q2[0] + (q3[0] - q2[0]) / 2), (q2[1] + (q3[1] - q2[1]) / 2));
                c.lineWidth = q3[3];
                c.stroke();
            }
            break;
        case 'P'://Perfect Lines
            var path = stroke_cache[i] || new Path2D(getFreeDrawSvgPath(action.points, action.width, true));
            stroke_cache[i] = path;
            c.fill(path);
            break;
        case 'T'://Write Text
            drawTextFromAction(c, action);
            break;
    }
}

// Draw action i onto the main canvas with its own opacity, shifted by (dx, dy).
function composite_action(action, i, dx, dy) {
    var box = action_bbox(action);
    if (!box) return;
    var dpr = window.devicePixelRatio || 1;
    var cw = canvas.width, ch = canvas.height;
    // Source rectangle in device pixels, clamped to the canvas.
    var sx = Math.max(0, Math.floor(box.x * dpr)), sy = Math.max(0, Math.floor(box.y * dpr));
    var ex = Math.min(cw, Math.ceil((box.x + box.w) * dpr)), ey = Math.min(ch, Math.ceil((box.y + box.h) * dpr));
    if (ex <= sx || ey <= sy) return;
    scratch_ctx.save();
    scratch_ctx.setTransform(1, 0, 0, 1, 0, 0);
    scratch_ctx.clearRect(sx, sy, ex - sx, ey - sy);
    scratch_ctx.restore();
    draw_action_on(scratch_ctx, action, i);
    ctx.save();
    ctx.setTransform(1, 0, 0, 1, 0, 0);
    ctx.globalAlpha = action_opacity(action);
    ctx.globalCompositeOperation = "source-over";
    ctx.drawImage(scratch_canvas, sx, sy, ex - sx, ey - sy,
                  sx + Math.round((dx || 0) * dpr), sy + Math.round((dy || 0) * dpr), ex - sx, ey - sy);
    ctx.restore();
}

// Index of the last clear marker; nothing before it is drawn.
function last_clear_index() {
    for (var index = lineHistory.length - 1; index > 0; index--) {
        if (lineHistory[index].type == 'X') return index;
    }
    return 0;
}

async function draw_upto_latest_point_async(startLine, startPoint, startStroke){
	var fullRedraw = false;//keep track if this call started a full redraw to unset pleaseRedrawEverything flag later.
	if (pleaseRedrawEverything) {// erase everything and draw from start
        fullRedraw = true;
        startLine = 0;
        ctx.save();
        ctx.setTransform(1, 0, 0, 1, 0, 0);
        ctx.clearRect(0, 0, ctx.canvas.width, ctx.canvas.height);
        ctx.restore();
	}
    startLine = Math.max(startLine, last_clear_index());
    for (var i = startLine; i < lineHistory.length; i++) {
        var actionToDraw = lineHistory[i];
        if (!actionToDraw.visible || !DRAWABLE_TYPES[actionToDraw.type]) continue;
        var offset = selection_offset_for(i);
        composite_action(actionToDraw, i, offset[0], offset[1]);
    }
    nextLine = lineHistory.length;
    nextPoint = 0;
	if (fullRedraw) {//finished full redraw, now can unset redraw all flag so no more full redraws until necessary
        pleaseRedrawEverything = false;
        fullClear = false;
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
    const lines = action.text.split(/(?<!\\)\n/);
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
            var lines = action.text.split(/(?<!\\)\n/);
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

function pointerDownLine(e) {
    wrapper.classList.add('nopointer');
	if (!e.isPrimary || calligraphy || strokeDelete || textWriting) { return; }
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
        currentAction.points.push([
			e.offsetX,
			e.offsetY,
            (e.pointerType[0] == 'p' && pressureSensitivity) ? e.pressure : 2,//set pressure for perfect draw
			(e.pointerType[0] == 'p' && pressureSensitivity) ? (1.0 + e.pressure * currentAction.width * 2) : currentAction.width]);//set pressure for simple lines
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
    }
}

function pointerMoveLine(e) {
	if (!e.isPrimary || calligraphy || strokeDelete || textWriting) { return; }
	if (e.pointerType[0] != 'p' && drawingWithPressurePenOnly) { return; }
    if (isPointerDown) {
        // Use every pen sample since the last frame (browsers merge them into one
        // pointermove), so fast strokes keep their shape.
        var samples = (e.getCoalescedEvents && e.getCoalescedEvents()) || [];
        if (!samples.length) samples = [e];
        var offX = e.offsetX - e.clientX, offY = e.offsetY - e.clientY;
        var usePressure = e.pointerType[0] == 'p' && pressureSensitivity;
        for (var k = 0; k < samples.length; k++) {
            var ev = samples[k];
            currentAction.points.push([
                ev.clientX + offX,
                ev.clientY + offY,
                usePressure ? ev.pressure : 2,
                usePressure ? (1.0 + ev.pressure * currentAction.width * 2) : currentAction.width]);
            if (!perfectFreehand) draw_latest_preview_segment();
        }
        if(perfectFreehand){
            const box = calculateClearBox(currentAction.points);
            secondary_ctx.clearRect(box.x, box.y, box.width, box.height);
            var path = new Path2D(getFreeDrawSvgPath(currentAction.points, currentAction.width, true)) 
            secondary_ctx.fill(path)
        }
        else {
            draw_preview_tail();
        }
    }
}

// Live preview of a simple line: the curve up to the midpoint of the last two points.
function draw_latest_preview_segment() {
    var pts = currentAction.points;
    var a = pts[pts.length > 2 ? pts.length-3 : 0], b = pts[pts.length > 1 ? pts.length-2 : 0], c = pts[pts.length - 1];
    draw_secondary_path_at_some_point_async(a[0], a[1], b[0], b[1], c[0], c[1], c[3]);
}

// Straight piece from the last midpoint to the pen, so the preview doesn't trail behind it.
function draw_preview_tail() {
    var pts = currentAction.points;
    if (pts.length < 2) return;
    var b = pts[pts.length - 2], c = pts[pts.length - 1];
    secondary_ctx.beginPath();
    secondary_ctx.moveTo(b[0] + (c[0] - b[0]) / 2, b[1] + (c[1] - b[1]) / 2);
    secondary_ctx.lineTo(c[0], c[1]);
    secondary_ctx.lineWidth = c[3];
    secondary_ctx.stroke();
}

function pointerUpLine(e) {
    wrapper.classList.remove('nopointer');
    /* Needed for the last bit of the drawing. */
	if (!e.isPrimary || calligraphy || strokeDelete || textWriting) { return; }
	if (e.pointerType[0] != 'p' && drawingWithPressurePenOnly) { return; }
    var pen = getPenColorAndWidthByIndex(activePenIndex);
    if (isPointerDown) {
        currentAction.points.push([
			e.offsetX,
			e.offsetY,
            (e.pointerType[0] == 'p' && pressureSensitivity) ? e.pressure : 2,
			(e.pointerType[0] == 'p' && pressureSensitivity) ? (1.0 + e.pressure * currentAction.width * 2) : currentAction.width]);

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

var tempColor = ""; // The variable to change
var eraseMode = false // Are we currently drawing the erase line?
var intervalId = null; // To track the interval

// Function to update the variable and display
function updateVariable() {
    variable += 1; // Increment the variable
    status.textContent = `Variable Value: ${variable}`; // Update display
}

// TODO chinese mode?
// TODO save draw info in cards, no need to save redos
// TODO make clear per side of card by marking which items have been cleared
// TODO add merging of front into back for correct behaviour with saving draw info
// TODO add toggle to not apply front card to the back one
// TODO clear history button?

// ----------------------------------------- Selection (lasso) -----------------------------------------
// Draw a loop around strokes to select them (a stroke is selected when more than
// half of its points are inside), or click a stroke to select just that one.
// Then drag inside the dashed box to move, press the delete-selection hotkey to
// delete, or pick a pen to recolour. Moves, deletes and recolours are undoable.

var selectedIndices = [];   // indices into lineHistory
var selectionDrag = null;   // {dx, dy} while dragging the selection
var selectGesture = null;   // {kind: 'lasso'|'move', points, startX, startY, pointerId}
var SELECT_CLICK_TOLERANCE = 6;

function resize_selection_canvas(dpr) {
    selection_canvas.width = canvas.width;
    selection_canvas.height = canvas.height;
    selection_ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    draw_selection_overlay();
}

function selection_offset_for(i) {
    if (selectionDrag && selectedIndices.indexOf(i) !== -1) return [selectionDrag.dx, selectionDrag.dy];
    return [0, 0];
}

function is_selectable(i) {
    var a = lineHistory[i];
    return a && a.visible && DRAWABLE_TYPES[a.type] && a.points && a.points.length && i >= last_clear_index();
}

function clear_selection() {
    if (!selectedIndices.length && !selectGesture && !selectionDrag) return;
    selectedIndices = [];
    selectionDrag = null;
    selectGesture = null;
    draw_selection_overlay();
    ts_redraw();
}

// Drop selected strokes that no longer exist or are hidden (after undo/redo).
function prune_selection() {
    var kept = selectedIndices.filter(is_selectable);
    if (kept.length !== selectedIndices.length) selectedIndices = kept;
    draw_selection_overlay();
}

function selection_bbox() {
    var box = null;
    selectedIndices.forEach(function(i) {
        var b = action_bbox(lineHistory[i]);
        if (!b) return;
        if (!box) { box = { x: b.x, y: b.y, x2: b.x + b.w, y2: b.y + b.h }; return; }
        box.x = Math.min(box.x, b.x); box.y = Math.min(box.y, b.y);
        box.x2 = Math.max(box.x2, b.x + b.w); box.y2 = Math.max(box.y2, b.y + b.h);
    });
    return box;
}

function point_in_polygon(x, y, poly) {
    var inside = false;
    for (var i = 0, j = poly.length - 1; i < poly.length; j = i++) {
        var xi = poly[i][0], yi = poly[i][1], xj = poly[j][0], yj = poly[j][1];
        if (((yi > y) != (yj > y)) && (x < (xj - xi) * (y - yi) / (yj - yi) + xi)) inside = !inside;
    }
    return inside;
}

function strokes_in_lasso(poly) {
    var found = [];
    for (var i = last_clear_index(); i < lineHistory.length; i++) {
        if (!is_selectable(i)) continue;
        var pts = lineHistory[i].points, inside = 0;
        for (var k = 0; k < pts.length; k++) if (point_in_polygon(pts[k][0], pts[k][1], poly)) inside++;
        if (inside * 2 > pts.length) found.push(i);
    }
    return found;
}

function dist_to_segment(px, py, ax, ay, bx, by) {
    var dx = bx - ax, dy = by - ay, len = dx * dx + dy * dy;
    var t = len ? Math.max(0, Math.min(1, ((px - ax) * dx + (py - ay) * dy) / len)) : 0;
    var cx = ax + t * dx, cy = ay + t * dy;
    return Math.sqrt((px - cx) * (px - cx) + (py - cy) * (py - cy));
}

// Topmost stroke under a click.
function stroke_at_point(x, y) {
    for (var i = lineHistory.length - 1; i >= last_clear_index(); i--) {
        if (!is_selectable(i)) continue;
        var a = lineHistory[i], pts = a.points;
        if (a.type == 'T') {
            var b = action_bbox(a);
            if (x >= b.x && x <= b.x + b.w && y >= b.y && y <= b.y + b.h) return i;
            continue;
        }
        var tol = Math.max(parseFloat(a.width) || 1, 2) / 2 + SELECT_CLICK_TOLERANCE;
        if (pts.length == 1 && Math.hypot(pts[0][0] - x, pts[0][1] - y) <= tol) return i;
        for (var k = 1; k < pts.length; k++) {
            if (dist_to_segment(x, y, pts[k-1][0], pts[k-1][1], pts[k][0], pts[k][1]) <= tol) return i;
        }
    }
    return -1;
}

function draw_selection_overlay() {
    selection_ctx.save();
    selection_ctx.setTransform(1, 0, 0, 1, 0, 0);
    selection_ctx.clearRect(0, 0, selection_canvas.width, selection_canvas.height);
    selection_ctx.restore();
    selection_ctx.lineWidth = 1.5;
    selection_ctx.strokeStyle = '#2a7de1';
    selection_ctx.setLineDash([6, 4]);
    if (selectGesture && selectGesture.kind == 'lasso' && selectGesture.points.length > 1) {
        var pts = selectGesture.points;
        selection_ctx.beginPath();
        selection_ctx.moveTo(pts[0][0], pts[0][1]);
        for (var k = 1; k < pts.length; k++) selection_ctx.lineTo(pts[k][0], pts[k][1]);
        selection_ctx.stroke();
    }
    var box = selection_bbox();
    if (box) {
        var dx = selectionDrag ? selectionDrag.dx : 0, dy = selectionDrag ? selectionDrag.dy : 0;
        selection_ctx.fillStyle = 'rgba(42, 125, 225, 0.07)';
        selection_ctx.fillRect(box.x + dx, box.y + dy, box.x2 - box.x, box.y2 - box.y);
        selection_ctx.strokeRect(box.x + dx, box.y + dy, box.x2 - box.x, box.y2 - box.y);
    }
    selection_ctx.setLineDash([]);
}

function move_actions(indices, dx, dy) {
    indices.forEach(function(i) {
        var a = lineHistory[i];
        if (!a || !a.points) return;
        a.points = a.points.map(function(p) { var q = p.slice(); q[0] += dx; q[1] += dy; return q; });
        if (a.type == 'T') { a.x += dx; a.y += dy; }
        invalidate_action_geometry(i);
    });
}

function set_action_color(i, style) {
    var a = lineHistory[i];
    if (!a) return;
    a.color = style.color;
    a.opacity = style.opacity;
}

function delete_selection() {
    if (!selectedIndices.length) return;
    var indices = selectedIndices.slice();
    indices.forEach(function(i) { lineHistory[i].visible = false; });
    selectedIndices = [];
    add_action_to_history({ type: 'D', points: [], deletedList: indices, visible: true });
    draw_selection_overlay();
    ts_redraw();
}

function recolor_selection_to_active_pen() {
    if (!selectedIndices.length) return;
    var pen = getPenColorAndWidthByIndex(activePenIndex);
    var changes = selectedIndices.map(function(i) {
        var a = lineHistory[i];
        return { index: i, from: { color: a.color, opacity: a.opacity }, to: { color: pen[0], opacity: pen[2] } };
    });
    changes.forEach(function(ch) { set_action_color(ch.index, ch.to); });
    add_action_to_history({ type: 'R', changes: changes, visible: true });
    ts_redraw();
}

function select_pointer_down(e) {
    submitCurrentText();
    var x = e.offsetX, y = e.offsetY;
    var box = selection_bbox();
    var pad = SELECT_CLICK_TOLERANCE;
    if (box && x >= box.x - pad && x <= box.x2 + pad && y >= box.y - pad && y <= box.y2 + pad) {
        selectGesture = { kind: 'move', startX: x, startY: y, pointerId: e.pointerId };
        selectionDrag = { dx: 0, dy: 0 };
    } else {
        selectedIndices = [];
        selectGesture = { kind: 'lasso', points: [[x, y]], pointerId: e.pointerId };
    }
    try { secondary_canvas.setPointerCapture(e.pointerId); } catch (err) {}
    draw_selection_overlay();
    ts_redraw();
}

function select_pointer_move(e) {
    if (!selectGesture || e.pointerId !== selectGesture.pointerId) return;
    var x = e.offsetX, y = e.offsetY;
    if (selectGesture.kind == 'lasso') {
        selectGesture.points.push([x, y]);
    } else {
        selectionDrag = { dx: x - selectGesture.startX, dy: y - selectGesture.startY };
        ts_redraw();
    }
    draw_selection_overlay();
}

function select_pointer_up(e) {
    if (!selectGesture || e.pointerId !== selectGesture.pointerId) return;
    var gesture = selectGesture;
    selectGesture = null;
    if (gesture.kind == 'lasso') {
        var pts = gesture.points, extent = 0;
        for (var k = 1; k < pts.length; k++) extent = Math.max(extent, Math.hypot(pts[k][0] - pts[0][0], pts[k][1] - pts[0][1]));
        if (extent < SELECT_CLICK_TOLERANCE) {
            var hit = stroke_at_point(pts[0][0], pts[0][1]);
            selectedIndices = hit >= 0 ? [hit] : [];
        } else {
            selectedIndices = strokes_in_lasso(pts);
        }
    } else {
        var drag = selectionDrag || { dx: 0, dy: 0 };
        selectionDrag = null;
        if (drag.dx || drag.dy) {
            var indices = selectedIndices.slice();
            move_actions(indices, drag.dx, drag.dy);
            add_action_to_history({ type: 'M', indices: indices, dx: drag.dx, dy: drag.dy, visible: true });
        }
        ts_redraw();
    }
    draw_selection_overlay();
}

// ----------------------------------------- Pointer buttons -----------------------------------------
// What each pointer button does is set in AnkiSketch > Hotkeys and buttons:
//   'tool'          use the current tool (pen, calligraphy, text, stroke delete, select)
//   'select'        lasso select / move the selection
//   'stroke_delete' stroke delete while the button is held
//   'none'          nothing (for the right button: Anki's right-click menu)

var POINTER_DEFAULTS = { left: 'tool', right: 'select', middle: 'stroke_delete', pen_eraser: 'stroke_delete' };
var pointerBindings = Object.assign({}, POINTER_DEFAULTS, window.AnkiSketchConfig.pointer || {});
var pointerGesture = null;  // {behaviour, tempDelete, pointerId}

function set_pointer_bindings(bindings) {
    pointerBindings = Object.assign({}, POINTER_DEFAULTS, bindings || {});
}

function pointer_role(e) {
    if (e.pointerType === 'pen' && (e.button === 5 || (e.buttons & 32))) return 'pen_eraser';
    if (e.button === 1) return 'middle';
    if (e.button === 2) return 'right';
    return 'left';
}

function is_drawing_surface(target) {
    return target === canvas || target === secondary_canvas;
}

// Runs before the drawing handlers (capture phase) and decides who gets the gesture.
function route_pointer_down(e) {
    if (!is_drawing_surface(e.target) || !e.isPrimary) return;
    var behaviour = pointerBindings[pointer_role(e)] || 'tool';
    if (behaviour === 'tool' && selectMode) behaviour = 'select';
    pointerGesture = null;
    if (behaviour === 'tool') return;
    if (behaviour === 'none') { e.stopPropagation(); return; }
    if (behaviour === 'select') {
        e.stopPropagation();
        e.preventDefault();
        if (isPointerDown) stop_drawing();
        pointerGesture = { behaviour: 'select', pointerId: e.pointerId };
        select_pointer_down(e);
        return;
    }
    if (behaviour === 'stroke_delete') {
        pointerGesture = { behaviour: 'stroke_delete', pointerId: e.pointerId, tempDelete: !strokeDelete };
        if (!strokeDelete) enter_stroke_delete_mode();
        // fall through to the stroke delete handlers
    }
}

function route_pointer_move(e) {
    if (pointerGesture && pointerGesture.behaviour === 'select') select_pointer_move(e);
}

// Registered after the drawing handlers' pointerup, so it runs once they're done.
function route_pointer_up(e) {
    var gesture = pointerGesture;
    if (!gesture || e.pointerId !== gesture.pointerId) return;
    pointerGesture = null;
    if (gesture.behaviour === 'select') select_pointer_up(e);
    if (gesture.behaviour === 'stroke_delete' && gesture.tempDelete) exit_stroke_delete_mode();
}

wrapper.addEventListener('pointerdown', route_pointer_down, true);
window.addEventListener('pointermove', route_pointer_move);
window.addEventListener('pointerup', route_pointer_up);
window.addEventListener('pointercancel', route_pointer_up);
// No browser right-click menu or middle-click autoscroll on the drawing.
wrapper.addEventListener('contextmenu', function(e) {
    if (is_drawing_surface(e.target) && pointerBindings.right !== 'none') e.preventDefault();
});
wrapper.addEventListener('mousedown', function(e) {
    if (is_drawing_surface(e.target) && e.button === 1 && pointerBindings.middle !== 'none') e.preventDefault();
});
wrapper.addEventListener('auxclick', function(e) {
    if (is_drawing_surface(e.target) && e.button === 1) e.preventDefault();
});

// ----------------------------------------- Cursor -----------------------------------------
// While drawing is on, the pointer is a dot in the current pen's colour and size.

var cursorKey = '';

function svg_cursor(svg, hotX, hotY, fallback) {
    return 'url("data:image/svg+xml;utf8,' + encodeURIComponent(svg) + '") ' + hotX + ' ' + hotY + ', ' + fallback;
}

function pen_dot_cursor(color, width) {
    var d = Math.max(4, Math.min(40, Math.round(parseFloat(width) || 4)));
    var size = d + 4, c = size / 2;
    return svg_cursor("<svg xmlns='http://www.w3.org/2000/svg' width='" + size + "' height='" + size + "'>" +
        "<circle cx='" + c + "' cy='" + c + "' r='" + (d / 2) + "' fill='" + color + "' stroke='white' stroke-width='1'/></svg>",
        Math.round(c), Math.round(c), 'crosshair');
}

function eraser_cursor() {
    return svg_cursor("<svg xmlns='http://www.w3.org/2000/svg' width='20' height='20'>" +
        "<circle cx='10' cy='10' r='7' fill='white' fill-opacity='0.6' stroke='#d32f2f' stroke-width='2'/></svg>",
        10, 10, 'crosshair');
}

function update_cursor() {
    var pen = getPenColorAndWidthByIndex(activePenIndex);
    var key = [selectMode, strokeDelete, textWriting, pen[0], pen[1]].join('|');
    if (key === cursorKey) return;
    cursorKey = key;
    var cursor;
    if (strokeDelete) cursor = eraser_cursor();
    else if (selectMode) cursor = 'crosshair';
    else if (textWriting) cursor = 'text';
    else cursor = pen_dot_cursor(solid_color(pen[0]), pen[1]);
    canvas.style.cursor = cursor;
    secondary_canvas.style.cursor = cursor;
}

if (AnkiSketchSettings.autoHidePointer) wrapper.classList.add('ts_autohide_pointer');

// ----------------------------------------- Keep drawings per card -----------------------------------------
// With "Keep drawings while reviewing" on, each card's drawing is kept in memory and
// comes back when that card is shown again. Leaving the review screen clears it all,
// because Anki reloads this page.

var savedCardDrawings = {};
var currentCardId = null;

function ankisketch_show_card(cardId, keep) {
    if (keep && currentCardId !== null && currentCardId !== cardId) {
        savedCardDrawings[currentCardId] = lineHistory.slice();
    }
    var sameCard = currentCardId === cardId;
    currentCardId = cardId;
    if (keep && sameCard) return;  // e.g. the page re-showed the same card: keep the drawing
    clear_canvas();
    if (keep && savedCardDrawings[cardId]) {
        lineHistory = savedCardDrawings[cardId];
        stroke_cache = [];
        lineHistory.forEach(function(a) { delete a._bbox; });
        ts_undo_button.className = lineHistory.length ? 'active' : '';
        ts_redraw();
    }
}

// ----------------------------------------- Hotkeys -----------------------------------------
// Bindings come from config.json via window.AnkiSketchConfig.hotkeys and can be
// changed in the AnkiSketch > Hotkeys dialog. Actions fire on keydown.

// Press-to-trigger actions. `repeat: true` lets a held key repeat (like undo in OneNote).
var hotkeyActions = {
    pen_1: { run: function() { activate_pen1(); } },
    pen_2: { run: function() { activate_pen2(); } },
    pen_3: { run: function() { activate_pen3(); } },
    pen_4: { run: function() { activate_pen4(); } },
    undo: { run: function() { ts_undo(); }, repeat: true },
    redo: { run: function() { ts_redo(); }, repeat: true },
    perfect_freehand: { run: function() { switch_perfect_freehand(); } },
    calligraphy: { run: function() { switch_calligraphy_mode(); } },
    text: { run: function() { switch_text_writing_mode(); } },
    stroke_delete: { run: function() { finishDelete(); switch_stroke_delete_mode(); } },
    clear: { run: function() { add_clear_marker(); } },
    toggle_visibility: { run: function() { switch_visibility(); } },
    small_canvas: { run: function() { switch_small_canvas(); } },
    select: { run: function() { switch_select_mode(); } },
    delete_selection: { run: function() { delete_selection(); } }
};

// Hold-to-use actions: on while the key is held, off when its key is released.
var hotkeyHoldActions = {
    stroke_delete_hold: {
        down: function() { enter_stroke_delete_mode(); },
        up: function() { finishDelete(); exit_stroke_delete_mode(); },
        active: function() { return isDeleting; }
    }
};

// Toolbar buttons whose tooltip shows the current binding.
var hotkeyButtonTitles = [
    ['ts_visibility_button', 'toggle_visibility', 'Toggle visiblity'],
    ['ts_perfect_freehand_button', 'perfect_freehand', 'Perfect Freehand'],
    ['ts_kanji_button', 'calligraphy', 'Toggle calligrapher'],
    ['ts_text_button', 'text', 'Toggle text writing'],
    ['ts_stroke_delete_button', 'stroke_delete', 'Stroke Delete'],
    ['ts_select_button', 'select', 'Select (lasso)'],
    ['ts_undo_button', 'undo', 'Undo the last stroke'],
    ['ts_redo_button', 'redo', 'Redo the last stroke'],
    ['ts_clear_button', 'clear', 'Clean canvas'],
    ['ts_switch_fullscreen_button', 'small_canvas', 'Toggle fullscreen canvas'],
    ['ts_switch_pen1_button', 'pen_1', 'Switch to Pen 1'],
    ['ts_switch_pen2_button', 'pen_2', 'Switch to Pen 2'],
    ['ts_switch_pen3_button', 'pen_3', 'Switch to Pen 3'],
    ['ts_switch_pen4_button', 'pen_4', 'Switch to Pen 4']
];

var hotkeyBindings = {};

function set_hotkeys(bindings) {
    hotkeyBindings = {};
    for (var id in bindings) {
        hotkeyBindings[id] = AnkiSketchKeys.normalize(bindings[id]);
    }
    update_hotkey_titles();
}

function update_hotkey_titles() {
    hotkeyButtonTitles.forEach(function(entry) {
        var button = document.getElementById(entry[0]);
        if (!button) return;
        var parts = [];
        if (hotkeyBindings[entry[1]]) parts.push(hotkeyBindings[entry[1]]);
        if (entry[1] == 'stroke_delete' && hotkeyBindings.stroke_delete_hold) parts.push('hold ' + hotkeyBindings.stroke_delete_hold);
        button.title = entry[2] + (parts.length ? ' (' + parts.join(', ') + ')' : '');
    });
}

// Plain keys (no Ctrl/Alt/Meta) are left alone while typing in a text field,
// e.g. the text tool's box or Anki's type-in-the-answer field.
function hotkey_blocked_by_typing(e, binding) {
    return AnkiSketchKeys.isTypingTarget(e.target) && !AnkiSketchKeys.hasCommandModifier(binding);
}

function on_hotkey_down(e) {
    var combo = AnkiSketchKeys.comboFromEvent(e);
    if (!combo) return;
    for (var holdId in hotkeyHoldActions) {
        if (hotkeyBindings[holdId] !== combo) continue;
        if (textWriting || hotkey_blocked_by_typing(e, combo)) continue;
        e.preventDefault();
        if (!e.repeat) hotkeyHoldActions[holdId].down();
        return;
    }
    for (var id in hotkeyActions) {
        if (hotkeyBindings[id] !== combo) continue;
        if (hotkey_blocked_by_typing(e, combo)) continue;
        e.preventDefault();
        if (e.repeat && !hotkeyActions[id].repeat) return;
        hotkeyActions[id].run();
        return;
    }
}

function on_hotkey_up(e) {
    var key = AnkiSketchKeys.keyName(e);
    if (!key) return;
    for (var holdId in hotkeyHoldActions) {
        var hold = hotkeyHoldActions[holdId];
        if (hotkeyBindings[holdId] && AnkiSketchKeys.mainKey(hotkeyBindings[holdId]) === key && hold.active()) {
            hold.up();
        }
    }
}

document.addEventListener('keydown', on_hotkey_down);
document.addEventListener('keyup', on_hotkey_up);
set_hotkeys(window.AnkiSketchConfig.hotkeys || {});

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
    for (let lineIndex = 0; lineIndex < lineHistory.length; lineIndex++) {
        const element = lineHistory[lineIndex];
        if(!element.points || !element.type == 'D' || !element.visible) continue;
        if(doLinesIntersect(element.points, currentAction.points)){
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
    ts_redraw()
}

function pointerUpStrokeDelete(e) {
    wrapper.classList.remove('nopointer');
    stop_drawing();
    if (!e.isPrimary || !strokeDelete || !currentAction.points || !currentAction.points.length) { return; }
    finishDelete();
};

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
