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
    activePenIndex = 0
    update_pen_settings();
}

function activate_pen2()
{
    activePenIndex = 1
    update_pen_settings();
}

function activate_pen3()
{
    activePenIndex = 2
    update_pen_settings();
}

function activate_pen4()
{
    activePenIndex = 3
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

function save_drawing_modes_for_delete()
{
    ts_kanji_button_class = ts_kanji_button.className;
    ts_perfect_freehand_button_class = ts_perfect_freehand_button.className;
    ts_text_button_class = ts_text_button.className;
    calligraphy_activated = calligraphy
    perfectFreehand_activated = perfectFreehand
    textWriting_activated = textWriting
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
    reset_history();
    reset_redo()
	ts_clear();
}

function add_clear_marker()
{
	//don't continue to put points into an empty array(pointermove) if clearing while drawing on the canvas
	stop_drawing();
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
            var path = new Path2D(getFreeDrawSvgPath(currentAction.points, currentAction.width, true)) 
            secondary_ctx.fill(path)
        }
        else{
            p1 = currentAction.points.length > 2 ? currentAction.points.length-3 : 0;
            p2 = currentAction.points.length > 1 ? currentAction.points.length-2 : 0;
            p3 = currentAction.points.length - 1;
            draw_secondary_path_at_some_point_async(currentAction.points[p1][0],currentAction.points[p1][1],currentAction.points[p2][0],currentAction.points[p2][1],currentAction.points[p3][0],currentAction.points[p3][1],currentAction.points[p3][3])
        }
    }
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

document.addEventListener('keydown', function(e) {
    // For hold mode, start deleting when shift+d is pressed
    if(textWriting)return;
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
document.addEventListener('keyup', function(e) {
    // alt + z
    if ((e.keyCode == 90 || e.key == "z") && e.altKey) {
		e.preventDefault();
        ts_undo();
    }
    // alt + y
    if ((e.keyCode == 89 || e.keyCode == "y") && e.altKey) {
        e.preventDefault();
        ts_redo();
    }
    // /
    if (e.key === ".") {
        add_clear_marker();
    }
	// ,
    if (e.key === ",") {
        switch_visibility();
    }
    if ((e.keyCode == 84 || e.key == "t") && e.altKey) {
        e.preventDefault();
        switch_text_writing_mode();
    }
    if ((e.keyCode == 68 || e.key == "d") && e.altKey) {
        e.preventDefault();
        finishDelete()
        switch_stroke_delete_mode();
    }
    // alt + c
    if ((e.keyCode === 67 || e.key === "c") && e.altKey) {
        e.preventDefault();
        switch_calligraphy_mode();
    }
        // alt + x
    if ((e.keyCode === 88 || e.key === "x") && e.altKey) {
        e.preventDefault();
        switch_perfect_freehand();
    }
    // alt + b
    if ((e.keyCode === 66 || e.key === "b") && e.altKey) {
        e.preventDefault();
        switch_small_canvas();
    }
        // alt + 1
    if ((e.keyCode === 49 || e.key === "1") && e.altKey) {
        e.preventDefault();
        activate_pen1();
    }
        // alt + 2
    if ((e.keyCode === 50 || e.key === "2") && e.altKey) {
        e.preventDefault();
        activate_pen2();
    }
        // alt + 3
    if ((e.keyCode === 51 || e.key === "3") && e.altKey) {
        e.preventDefault();
        activate_pen3();
    }
        // alt + 4
    if ((e.keyCode === 52 || e.key === "4") && e.altKey) {
        e.preventDefault();
        activate_pen4();
    }
})

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
