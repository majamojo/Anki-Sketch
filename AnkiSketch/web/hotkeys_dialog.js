/*
 * AnkiSketch hotkey settings dialog (runs inside an AnkiWebView).
 * Data comes from window.AnkiSketchHotkeyDialog, written by __init__.py:
 *   actions:  [{id, label, hold}]
 *   bindings: {id: "Alt+Z", ...}   current
 *   defaults: {id: "Alt+Z", ...}
 *   ankiKeys: ["Space", "E", ...]  keys Anki itself uses
 * Sends pycmd("ankisketch_hotkeys:save:" + JSON) or pycmd("ankisketch_hotkeys:cancel").
 * GPL-3.0-or-later.
 */
(function () {
    var data, bindings, capturingId = null;

    function el(tag, attrs, children) {
        var node = document.createElement(tag);
        for (var k in (attrs || {})) {
            if (k === 'text') node.textContent = attrs[k];
            else if (k.slice(0, 2) === 'on') node.addEventListener(k.slice(2), attrs[k]);
            else node.setAttribute(k, attrs[k]);
        }
        (children || []).forEach(function (c) { node.appendChild(c); });
        return node;
    }

    function labelOf(id) {
        for (var i = 0; i < data.actions.length; i++) if (data.actions[i].id === id) return data.actions[i].label;
        return id;
    }

    // Problems per action: other actions on the same key, keys Anki uses.
    function problems() {
        var out = {}, byKey = {};
        data.actions.forEach(function (a) {
            var b = bindings[a.id];
            out[a.id] = { duplicate: [], anki: false };
            if (!b) return;
            (byKey[b] = byKey[b] || []).push(a.id);
            if (data.ankiKeys.indexOf(b) !== -1) out[a.id].anki = true;
        });
        for (var key in byKey) {
            if (byKey[key].length < 2) continue;
            byKey[key].forEach(function (id) {
                out[id].duplicate = byKey[key].filter(function (other) { return other !== id; });
            });
        }
        return out;
    }

    function render() {
        var probs = problems();
        var anyDuplicate = false;
        var rows = data.actions.map(function (a) {
            var p = probs[a.id];
            if (p.duplicate.length) anyDuplicate = true;
            var capturing = capturingId === a.id;
            var keyButton = el('button', {
                class: 'key' + (capturing ? ' capturing' : '') + (bindings[a.id] ? '' : ' unbound'),
                id: 'key_' + a.id,
                title: 'Click, then press the new key combination',
                onclick: function () { capturingId = capturingId === a.id ? null : a.id; render(); }
            });
            keyButton.textContent = capturing ? 'Press keys… (Esc to cancel)' : (bindings[a.id] || 'not set');
            var notes = [];
            if (p.duplicate.length) notes.push(el('div', { class: 'error', text: 'Same key as: ' + p.duplicate.map(labelOf).join(', ') }));
            if (p.anki) notes.push(el('div', { class: 'warning', text: 'Anki also uses this key' }));
            if (a.hold) notes.push(el('div', { class: 'hint', text: 'Active while held' }));
            if (a.qt) notes.push(el('div', { class: 'hint', text: 'Works anywhere in Anki' }));
            return el('tr', {}, [
                el('td', { class: 'label', text: a.label }),
                el('td', {}, [keyButton].concat(notes)),
                el('td', { class: 'row-buttons' }, [
                    el('button', { text: 'Clear', title: 'Leave this action without a hotkey', onclick: function () { bindings[a.id] = ''; capturingId = null; render(); } }),
                    el('button', { text: 'Default', title: 'Default: ' + (data.defaults[a.id] || 'not set'), onclick: function () { bindings[a.id] = data.defaults[a.id] || ''; capturingId = null; render(); } })
                ])
            ]);
        });
        var app = document.getElementById('app');
        app.innerHTML = '';
        app.appendChild(el('table', {}, [el('tbody', {}, rows)]));
        var save = el('button', { id: 'save', class: 'primary', text: 'Save', onclick: function () {
            pycmd('ankisketch_hotkeys:save:' + JSON.stringify(bindings));
        } });
        if (anyDuplicate) { save.disabled = true; save.title = 'Two actions share a key; change one first'; }
        app.appendChild(el('div', { class: 'footer' }, [
            el('button', { id: 'reset_all', text: 'Reset all to defaults', onclick: function () {
                bindings = JSON.parse(JSON.stringify(data.defaults)); capturingId = null; render();
            } }),
            el('span', { class: 'spacer' }),
            el('button', { id: 'cancel', text: 'Cancel', onclick: function () { pycmd('ankisketch_hotkeys:cancel'); } }),
            save
        ]));
    }

    function onKeyDown(e) {
        if (!capturingId) return;
        e.preventDefault();
        e.stopPropagation();
        if (e.repeat) return;
        if (e.code === 'Escape' && !e.ctrlKey && !e.altKey && !e.shiftKey && !e.metaKey) {
            capturingId = null; render(); return;
        }
        var combo = AnkiSketchKeys.comboFromEvent(e);
        if (!combo) {
            // Only modifiers so far: show them while waiting for the key.
            var mods = [];
            if (e.ctrlKey) mods.push('Ctrl');
            if (e.altKey) mods.push('Alt');
            if (e.shiftKey) mods.push('Shift');
            if (e.metaKey) mods.push('Meta');
            var b = document.getElementById('key_' + capturingId);
            if (b) b.textContent = mods.join('+') + '+…';
            return;
        }
        bindings[capturingId] = combo;
        capturingId = null;
        render();
    }

    function init() {
        data = window.AnkiSketchHotkeyDialog;
        bindings = {};
        data.actions.forEach(function (a) { bindings[a.id] = AnkiSketchKeys.normalize(data.bindings[a.id] || ''); });
        data.ankiKeys = data.ankiKeys.map(AnkiSketchKeys.normalize);
        document.addEventListener('keydown', onKeyDown, true);
        render();
    }

    if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init);
    else init();
})();
