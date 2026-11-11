Use **AnkiSketch > Hotkeys…** (or the Config button here) to change hotkeys by pressing keys, instead of editing this JSON.

**hotkeys**: one entry per action. A binding is modifiers then one key, joined with `+`:

- Modifiers, in this order: `Ctrl`, `Alt`, `Shift`, `Meta`.
- Keys: letters `A`–`Z`, digits `0`–`9`, `F1`–`F24`, punctuation (`.` `,` `/` `;` `'` `[` `]` `-` `=` `` ` ``), `Space`, `Enter`, `Tab`, `Esc`, `Backspace`, `Delete`, `Insert`, `Home`, `End`, `PageUp`, `PageDown`, `Up`, `Down`, `Left`, `Right`, `Num0`–`Num9`.
- Keys are physical keys: `Shift+1` means Shift and the 1 key, whatever character it types.
- `""` leaves an action unbound.

Actions:

- `pen_1` … `pen_4`: switch pen.
- `undo`, `redo`: repeat while held.
- `perfect_freehand`, `calligraphy`, `text`, `stroke_delete`: toggle that tool.
- `stroke_delete_hold`: stroke delete while held; releasing the key (with or without modifiers) ends it.
- `clear`: clear the drawing (undoable).
- `toggle_visibility`: hide or show the drawing.
- `small_canvas`: switch between full-page and small canvas.
- `play_sound`: replay the card's audio (unbound by default; Anki's own `R` still works).
- `toggle_addon`: turn AnkiSketch on or off. Works anywhere in Anki, not just in review.

Hotkeys fire on key press. Keys without Ctrl, Alt or Meta are ignored while you type in a text field (the text tool, or a type-in-the-answer field).

Avoid keys Anki already uses in review or the main window: Space, Enter, `1`–`4`, `A`, `B`, `D`, `E`, `I`, `O`, `R`, `S`, `T`, `V`, `Y`, `-`, `=`, `/`, `Shift+1`, `Shift+2`, `Shift+8`, `Ctrl+1`–`Ctrl+7`, `Ctrl+Z`, `Esc`, `F5`. The dialog warns about these and about two actions sharing a key.
