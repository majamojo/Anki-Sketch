/*
 * AnkiSketch hotkey helpers, shared by the reviewer (sketch.js) and the
 * hotkey settings dialog. GPL-3.0-or-later.
 *
 * A binding is a string like "Alt+Z", "Ctrl+Shift+1", "." or "F2":
 * modifiers in the order Ctrl, Alt, Shift, Meta, then one key name.
 * Key names come from KeyboardEvent.code (the physical key), so a binding
 * means the same key whatever Shift or Alt does to the typed character.
 * An empty string means "not bound".
 */
var AnkiSketchKeys = (function () {
    var CODE_NAMES = {
        Comma: ",", Period: ".", Slash: "/", Semicolon: ";", Quote: "'",
        BracketLeft: "[", BracketRight: "]", Backslash: "\\", Minus: "-",
        Equal: "=", Backquote: "`", IntlBackslash: "IntlBackslash",
        Space: "Space", Enter: "Enter", NumpadEnter: "NumEnter", Tab: "Tab",
        Escape: "Esc", Backspace: "Backspace", Delete: "Delete", Insert: "Insert",
        Home: "Home", End: "End", PageUp: "PageUp", PageDown: "PageDown",
        ArrowUp: "Up", ArrowDown: "Down", ArrowLeft: "Left", ArrowRight: "Right",
        NumpadAdd: "NumAdd", NumpadSubtract: "NumSubtract", NumpadMultiply: "NumMultiply",
        NumpadDivide: "NumDivide", NumpadDecimal: "NumDecimal"
    };
    var MODIFIER_CODES = ["ShiftLeft", "ShiftRight", "ControlLeft", "ControlRight",
        "AltLeft", "AltRight", "MetaLeft", "MetaRight", "OSLeft", "OSRight",
        "CapsLock", "NumLock", "ScrollLock", "Fn", "FnLock", "AltGraph"];
    var MODIFIER_ALIASES = {
        ctrl: "Ctrl", control: "Ctrl", alt: "Alt", option: "Alt", shift: "Shift",
        meta: "Meta", cmd: "Meta", command: "Meta", win: "Meta", super: "Meta"
    };
    var MODIFIER_ORDER = ["Ctrl", "Alt", "Shift", "Meta"];

    // Name of the physical key pressed, or null for a bare modifier key.
    function keyName(e) {
        var c = e.code || "";
        var m;
        if (MODIFIER_CODES.indexOf(c) !== -1) return null;
        if ((m = /^Key([A-Z])$/.exec(c))) return m[1];
        if ((m = /^Digit([0-9])$/.exec(c))) return m[1];
        if ((m = /^Numpad([0-9])$/.exec(c))) return "Num" + m[1];
        if (/^F([1-9]|1[0-9]|2[0-4])$/.test(c)) return c;
        if (CODE_NAMES.hasOwnProperty(c)) return CODE_NAMES[c];
        if (c) return c;
        // No code (rare): fall back to the typed key.
        if (!e.key || ["Shift", "Control", "Alt", "Meta", "AltGraph"].indexOf(e.key) !== -1) return null;
        return e.key.length === 1 ? e.key.toUpperCase() : e.key;
    }

    // Binding string for a keyboard event, or null for a bare modifier.
    function comboFromEvent(e) {
        var key = keyName(e);
        if (!key) return null;
        var parts = [];
        if (e.ctrlKey) parts.push("Ctrl");
        if (e.altKey) parts.push("Alt");
        if (e.shiftKey) parts.push("Shift");
        if (e.metaKey) parts.push("Meta");
        parts.push(key);
        return parts.join("+");
    }

    // Canonical form of a binding typed by hand, e.g. "alt + z" -> "Alt+Z".
    function normalize(binding) {
        if (!binding) return "";
        var s = String(binding).trim();
        if (!s) return "";
        // Split on "+" but keep a trailing "+" key (e.g. "Ctrl++").
        var parts = s.split("+").map(function (p) { return p.trim(); });
        var key = parts.pop();
        if (key === "" && parts.length && parts[parts.length - 1] === "") { parts.pop(); key = "+"; }
        var mods = [];
        parts.forEach(function (p) {
            var name = MODIFIER_ALIASES[p.toLowerCase()];
            if (name && mods.indexOf(name) === -1) mods.push(name);
        });
        mods.sort(function (a, b) { return MODIFIER_ORDER.indexOf(a) - MODIFIER_ORDER.indexOf(b); });
        if (key.length === 1) key = key.toUpperCase();
        else if (/^f([1-9]|1[0-9]|2[0-4])$/i.test(key)) key = key.toUpperCase();
        else if (/^esc(ape)?$/i.test(key)) key = "Esc";
        else if (/^space$/i.test(key)) key = "Space";
        return mods.concat([key]).join("+");
    }

    // The key part of a binding ("Shift+D" -> "D").
    function mainKey(binding) {
        var n = normalize(binding);
        if (!n) return "";
        if (n === "+" || /\+\+$/.test(n)) return "+";
        return n.split("+").pop();
    }

    // True if the binding uses Ctrl, Alt or Meta (so it can't be plain typing).
    function hasCommandModifier(binding) {
        return /(^|\+)(Ctrl|Alt|Meta)\+/.test(normalize(binding));
    }

    // True if the element takes typed text (inputs, text areas, editable content).
    function isTypingTarget(el) {
        if (!el || el === document.body) return false;
        if (el.isContentEditable) return true;
        var tag = (el.tagName || "").toLowerCase();
        if (tag === "textarea") return true;
        if (tag === "input") {
            var type = (el.type || "text").toLowerCase();
            return ["button", "checkbox", "radio", "range", "color", "file", "submit", "reset", "image", "hidden"].indexOf(type) === -1;
        }
        return false;
    }

    return {
        keyName: keyName,
        comboFromEvent: comboFromEvent,
        normalize: normalize,
        mainKey: mainKey,
        hasCommandModifier: hasCommandModifier,
        isTypingTarget: isTypingTarget
    };
})();
