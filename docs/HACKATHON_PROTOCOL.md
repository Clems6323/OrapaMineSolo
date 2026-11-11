# Orapa Mine — Solver Hackathon Protocol

Version **1** · part of the solver hackathon ([epic #88](https://github.com/Clems6323/OrapaMineSolo/issues/88)).

This document is the **contract** every submission must respect. A submission is a
program in **any language** that plays one hidden grid by exchanging **line-based
JSON** messages with a referee. If you can read JSON from stdin and write JSON to
stdout, you can compete.

> The machine-readable message schemas live in [`schema/hackathon_protocol.schema.json`](../schema/hackathon_protocol.schema.json).
> The piece/colour reference at the end is **generated from the game engine**
> (`tools/piece_reference.py`) so it can never drift from the real geometry.

---

## 1. Transport

- **One JSON object per line**, newline-terminated (`\n`), UTF-8.
- The referee writes messages to your program's **stdin**; your program writes
  commands to its **stdout**.
- **stderr is yours**: log anything you like there. It is captured but never parsed.
- Every message is a JSON object with a **`type`** field that names it.
- One process plays **one grid**: the exchange begins with `hello` and ends with
  `end`, after which both sides close. The official evaluation runs your program
  once per grid; nothing persists between grids.

## 2. Lifecycle

```
referee → hello                         (grid size, inventory, limits)
  loop (your program drives):
    solver → pieces | shoot | query | place | remove | submit | give_up
    referee → inventory | shot | cell | ack | reject | result
referee → end                           (final result for this grid)
```

You decide every move. Interrogate the grid (costs points), build a candidate
board (free), and submit when confident. The grid ends on a correct submit, after
5 wrong submits, on `give_up`, or if you crash / time out.

## 3. Messages

### 3.1 `hello` (referee → solver), first line
```json
{
  "type": "hello",
  "protocol": 1,
  "width": 10,
  "height": 8,
  "extensions": ["diamond", "mystery"],
  "max_proposals": 5,
  "inventory": [
    {"piece": "yellow", "quantity": 1,
     "orientations": [[{"row":0,"col":0,"half":"full"}, {"row":0,"col":1,"half":"ra_nw"}, {"row":1,"col":0,"half":"ra_nw"}], "..."]}
  ],
  "limits": {"move_timeout_ms": 1000, "cpu_time_ms": 10000}
}
```
- `inventory` is the exact multiset of pieces you must place (see §5). Each piece
  lists its **orientations**; the index into that list is the `orient` value you
  pass to `place`.
- The **mystery** piece appears in the inventory with its geometry only — **its
  colour is never given**; you guess it.
- `limits` are informational; the referee enforces them (see §7).

### 3.2 `pieces` → `inventory`
`{"type":"pieces"}` re-requests the inventory. The reply repeats the `hello`
inventory and `{"mystery_color": null}`.

### 3.3 `shoot` → `shot` — **cost: 1 point**
Fire a ray from a **border** cell, travelling **inward**.
```json
{"type":"shoot","entry":{"row":2,"col":0},"direction":"RIGHT"}
```
```json
{"type":"shot","exit":{"row":5,"col":9},"color":"orange","absorbed":false}
```
- `direction` ∈ `UP | DOWN | LEFT | RIGHT` (row/col deltas: UP=−row, DOWN=+row,
  LEFT=−col, RIGHT=+col).
- `exit` is the border cell the ray leaves from, or `null` if it was absorbed
  (black body) or loops forever. `color` is the mixed ray colour (see Appendix B),
  or `null` if the ray touched no colour. `absorbed` is `true` only for a black body.
- A non-border `entry` is rejected.

### 3.4 `query` → `cell` — **cost: 3 points**
Ask what is in one cell.
```json
{"type":"query","cell":{"row":3,"col":4}}
```
```json
{"type":"cell","occupied":true,"color":"blue","kind":null}
```
- Empty → `{"occupied":false,"color":null,"kind":null}`.
- A normal or **mystery** gem → its `color` (mystery reveals its true colour here),
  `kind:null`.
- An extension revealed by nature → `kind` ∈ `diamond | filter | black-body | wormhole`,
  `color:null`.

### 3.5 `place` / `remove` → `ack` | `reject` — free
Build your candidate board. Placement is pure bookkeeping; it costs nothing.
```json
{"type":"place","piece":"yellow","anchor":{"row":3,"col":4},"orient":0}
{"type":"place","piece":"mystery","anchor":{"row":1,"col":7},"orient":0,"color":"red"}
{"type":"remove","cell":{"row":3,"col":4}}
```
- `anchor` is the **top-left cell of the piece's bounding box** in the chosen
  orientation; `orient` indexes the piece's orientation list (see §4, §5).
- `color` is required **only** for the mystery piece (your guess); sending it for
  any other piece is rejected.
- `remove` deletes whatever piece occupies the given cell.
- Reply is `{"type":"ack"}` or `{"type":"reject","reason":"<code>"}` (see §7).

### 3.6 `submit` → `result` — **+5 points per wrong submit**
Propose your candidate board. **Accepted only when every inventory piece is
placed** (a complete board); otherwise it is rejected at no cost.
```json
{"type":"submit"}
```
```json
{"type":"result","won":false,"points":9,"remaining_proposals":4}
```
- `won:true` ends the grid (you solved it). `won:false` costs +5 points and
  consumes one of your **5** proposals.
- When `remaining_proposals` reaches 0 the grid ends.

### 3.7 `give_up` → `result`
`{"type":"give_up"}` ends the grid unsolved. Reply `{"type":"result","won":false,...}`.

### 3.8 `end` (referee → solver), last line
```json
{"type":"end","solved":true,"points":14,"cpu_time_ms":812}
```
Sent when the grid is over (win, 5 wrong submits, give-up, or a fault). Both sides
close afterwards.

## 4. Coordinates, anchor & orientation (normative)

- **Positions** are `{"row":r,"col":c}`, 0-indexed, row 0 = top, col 0 = left.
- A piece's footprint is anchored so its bounding box starts at `(0,0)`.
  The absolute cells it occupies are `anchor + offset` for each offset.
- **Therefore the anchor is the top-left cell of the piece's bounding box in the
  chosen orientation** — not a fixed corner of the gem. It stays the top-left of
  the bbox for every orientation, because each orientation is re-normalized to the
  origin.
- **`orient`** indexes the piece's deterministic orientation list. Index **0 is
  the canonical shape**; the others are its distinct 90°-clockwise rotations and,
  for the chiral red parallelogram, horizontal mirrors. Symmetric pieces have
  fewer orientations, so **the count differs per piece**. An out-of-range `orient`
  is rejected.
- Each occupied cell is either a `full` cell or a right-triangle half-cell
  (`ra_nw | ra_ne | ra_sw | ra_se`, named by the right-angle corner; the
  hypotenuse is the 45° mirror). You only need this to simulate rays on your own
  hypothesis — placement needs just `piece` + `anchor` + `orient`.

The exact footprint of **every orientation of every piece**, with the anchor and a
worked `place` example, is in **Appendix A** (generated from the engine).

## 5. Pieces & the inventory

- Piece identifiers on the wire are **stable lowercase ASCII** ids:
  `red`, `yellow`, `blue`, `white-big`, `white-small`, `diamond`, `filter`,
  `black-body`, `wormhole`, `mystery`.
- The `hello`/`pieces` inventory tells you exactly which pieces and how many to
  place (e.g. `wormhole` has quantity 2). To `submit`, your candidate board must
  contain **exactly** that multiset — no more, no fewer.
- The mystery piece's colour is never revealed by the inventory; you deduce it
  (ray colours, a cell query) and pass your guess in `place`.

## 6. Scoring (how you are ranked)

Per grid the referee records three numbers; submissions are ranked **lexicographically,
all lower-is-better**:

1. **distance to the truth** — Earth-Mover distance between your best complete
   submission and the real grid; **0 = exact solve**. A mystery gem on the right
   cells but the wrong colour adds **1.0** (one cell-equivalent).
2. **points** — `shoot` = 1, `query` = 3, each wrong `submit` = 5.
3. **CPU time** — your program's CPU time, measured by the referee.

A grid you never submit a complete board for scores a worst-case distance of
**1000**. So: solve it (distance 0) first, then with the fewest points, then the
least CPU time.

## 7. Errors, limits & faults

- A rejected command replies `{"type":"reject","reason":"<code>"}` and **does not**
  end the grid; you may try something else. Reason codes:
  - `unknown_piece` — unknown piece id.
  - `illegal_move` — off-board / overlap / bad orientation / wrong colour usage /
    too many of a piece / non-border shot / cell off board / nothing to remove.
  - `incomplete_board` — `submit` before every piece is placed (no cost).
  - `session_finished` — the grid is already over.
- **Malformed line** (not valid JSON, or missing/unknown `type`) → the referee
  logs it and may reject or end the grid; do not emit partial lines.
- **Timeouts**: per-move and total **CPU-time** limits are enforced. Exceeding
  them ends the grid as a fault (worst-case distance).
- **Crash / premature EOF**: ends the grid as a fault.
- Keep output to one complete JSON object per line, flushed; never write to stdout
  anything that is not a protocol message (use stderr for logs).

## 8. Determinism

The hidden grid is fixed for a run. Given the same moves, the referee always
returns the same answers. Distance and points are deterministic; only CPU time
varies. Nothing carries over between grids.

## 9. Worked example (abridged)

```text
→ {"type":"hello","protocol":1,"width":10,"height":8,"extensions":[],
   "max_proposals":5,"inventory":[{"piece":"yellow","quantity":1,"orientations":[...]}],
   "limits":{"move_timeout_ms":1000,"cpu_time_ms":10000}}
← {"type":"query","cell":{"row":2,"col":2}}
→ {"type":"cell","occupied":true,"color":"yellow","kind":null}
← {"type":"shoot","entry":{"row":2,"col":0},"direction":"RIGHT"}
→ {"type":"shot","exit":{"row":0,"col":2},"color":"yellow","absorbed":false}
← {"type":"place","piece":"yellow","anchor":{"row":2,"col":2},"orient":0}
→ {"type":"ack"}
← {"type":"submit"}
→ {"type":"result","won":true,"points":4,"remaining_proposals":5}
→ {"type":"end","solved":true,"points":4,"cpu_time_ms":12}
```

---

## Appendix A — Pieces & orientations (generated)

<!-- GENERATED by tools/piece_reference.py — do not edit by hand -->

Glyphs: `■` full cell · `◤ ◥ ◣ ◢` right-triangle half-cells (filled corner) · `·` empty. The **anchor** is the top-left cell `(0,0)` of the bounding box; `orient` is the index below (0 = canonical).

### `corps-noir` → wire id **`black-body`** (2 orientation(s))

- **orient 0** — cells: (0,0) full, (0,1) full
  ```
  ■■
  ```

- **orient 1** — cells: (0,0) full, (1,0) full
  ```
  ■
  ■
  ```

  Example: `{"type":"place","piece":"black-body","anchor":{"row":3,"col":4},"orient":0}`

### `bleu` → wire id **`blue`** (4 orientation(s))

- **orient 0** — cells: (0,1) ra_se, (0,2) ra_sw, (1,0) ra_se, (1,1) full, (1,2) full, (1,3) ra_sw
  ```
  ·◢◣·
  ◢■■◣
  ```

- **orient 1** — cells: (0,0) ra_sw, (1,0) full, (1,1) ra_sw, (2,0) full, (2,1) ra_nw, (3,0) ra_nw
  ```
  ◣·
  ■◣
  ■◤
  ◤·
  ```

- **orient 2** — cells: (0,0) ra_ne, (0,1) full, (0,2) full, (0,3) ra_nw, (1,1) ra_ne, (1,2) ra_nw
  ```
  ◥■■◤
  ·◥◤·
  ```

- **orient 3** — cells: (0,1) ra_se, (1,0) ra_se, (1,1) full, (2,0) ra_ne, (2,1) full, (3,1) ra_ne
  ```
  ·◢
  ◢■
  ◥■
  ·◥
  ```

  Example: `{"type":"place","piece":"blue","anchor":{"row":3,"col":4},"orient":0}`

### `diamant` → wire id **`diamond`** (4 orientation(s))

- **orient 0** — cells: (0,0) ra_se, (0,1) ra_sw
  ```
  ◢◣
  ```

- **orient 1** — cells: (0,0) ra_sw, (1,0) ra_nw
  ```
  ◣
  ◤
  ```

- **orient 2** — cells: (0,0) ra_ne, (0,1) ra_nw
  ```
  ◥◤
  ```

- **orient 3** — cells: (0,0) ra_se, (1,0) ra_ne
  ```
  ◢
  ◥
  ```

  Example: `{"type":"place","piece":"diamond","anchor":{"row":3,"col":4},"orient":0}`

### `filtre` → wire id **`filter`** (1 orientation(s))

- **orient 0** — cells: (0,0) ra_se, (0,1) ra_sw, (1,0) ra_ne, (1,1) ra_nw
  ```
  ◢◣
  ◥◤
  ```

  Example: `{"type":"place","piece":"filter","anchor":{"row":3,"col":4},"orient":0}`

### `mystère` → wire id **`mystery`** (4 orientation(s)) · colour is the solver's **guess** (`color` required)

- **orient 0** — cells: (0,0) ra_se, (0,1) ra_sw
  ```
  ◢◣
  ```

- **orient 1** — cells: (0,0) ra_sw, (1,0) ra_nw
  ```
  ◣
  ◤
  ```

- **orient 2** — cells: (0,0) ra_ne, (0,1) ra_nw
  ```
  ◥◤
  ```

- **orient 3** — cells: (0,0) ra_se, (1,0) ra_ne
  ```
  ◢
  ◥
  ```

  Example: `{"type":"place","piece":"mystery","anchor":{"row":3,"col":4},"orient":0, color:"red"}`

### `rouge` → wire id **`red`** (4 orientation(s))

- **orient 0** — cells: (0,0) ra_se, (0,1) full, (0,2) ra_nw
  ```
  ◢■◤
  ```

- **orient 1** — cells: (0,0) ra_sw, (1,0) full, (2,0) ra_ne
  ```
  ◣
  ■
  ◥
  ```

- **orient 2** — cells: (0,0) ra_ne, (0,1) full, (0,2) ra_sw
  ```
  ◥■◣
  ```

- **orient 3** — cells: (0,0) ra_se, (1,0) full, (2,0) ra_nw
  ```
  ◢
  ■
  ◤
  ```

  Example: `{"type":"place","piece":"red","anchor":{"row":3,"col":4},"orient":0}`

### `blanc-grand` → wire id **`white-big`** (4 orientation(s))

- **orient 0** — cells: (0,1) ra_se, (0,2) ra_sw, (1,0) ra_se, (1,1) full, (1,2) full, (1,3) ra_sw
  ```
  ·◢◣·
  ◢■■◣
  ```

- **orient 1** — cells: (0,0) ra_sw, (1,0) full, (1,1) ra_sw, (2,0) full, (2,1) ra_nw, (3,0) ra_nw
  ```
  ◣·
  ■◣
  ■◤
  ◤·
  ```

- **orient 2** — cells: (0,0) ra_ne, (0,1) full, (0,2) full, (0,3) ra_nw, (1,1) ra_ne, (1,2) ra_nw
  ```
  ◥■■◤
  ·◥◤·
  ```

- **orient 3** — cells: (0,1) ra_se, (1,0) ra_se, (1,1) full, (2,0) ra_ne, (2,1) full, (3,1) ra_ne
  ```
  ·◢
  ◢■
  ◥■
  ·◥
  ```

  Example: `{"type":"place","piece":"white-big","anchor":{"row":3,"col":4},"orient":0}`

### `blanc-petit` → wire id **`white-small`** (1 orientation(s))

- **orient 0** — cells: (0,0) ra_se, (0,1) ra_sw, (1,0) ra_ne, (1,1) ra_nw
  ```
  ◢◣
  ◥◤
  ```

  Example: `{"type":"place","piece":"white-small","anchor":{"row":3,"col":4},"orient":0}`

### `trou-de-ver` → wire id **`wormhole`** (1 orientation(s))

- **orient 0** — cells: (0,0) full
  ```
  ■
  ```

  Example: `{"type":"place","piece":"wormhole","anchor":{"row":3,"col":4},"orient":0}`

### `jaune` → wire id **`yellow`** (4 orientation(s))

- **orient 0** — cells: (0,0) full, (0,1) ra_nw, (1,0) ra_nw
  ```
  ■◤
  ◤·
  ```

- **orient 1** — cells: (0,0) ra_ne, (0,1) full, (1,1) ra_ne
  ```
  ◥■
  ·◥
  ```

- **orient 2** — cells: (0,1) ra_se, (1,0) ra_se, (1,1) full
  ```
  ·◢
  ◢■
  ```

- **orient 3** — cells: (0,0) ra_sw, (1,0) full, (1,1) ra_sw
  ```
  ◣·
  ■◣
  ```

  Example: `{"type":"place","piece":"yellow","anchor":{"row":3,"col":4},"orient":0}`

## Appendix B — Ray colours (generated)

<!-- GENERATED by tools/piece_reference.py — do not edit by hand -->

Base gem colours (wire tokens): `red`, `yellow`, `blue`, `white`.

A ray's announced colour is the mix of the distinct gem colours it touched (`null` if it touched none). Full table (wire tokens):

| Gem colours touched | Ray colour |
|---------------------|------------|
| red | `red` |
| yellow | `yellow` |
| blue | `blue` |
| white | `white` |
| red + yellow | `orange` |
| red + blue | `purple` |
| red + white | `pink` |
| yellow + blue | `green` |
| yellow + white | `light-yellow` |
| blue + white | `light-blue` |
| red + yellow + blue | `black` |
| red + yellow + white | `light-orange` |
| red + blue + white | `light-purple` |
| yellow + blue + white | `light-green` |
| red + yellow + blue + white | `gray` |
