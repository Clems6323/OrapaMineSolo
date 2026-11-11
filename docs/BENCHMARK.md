# Orapa Mine — Hackathon grids

Part of the solver hackathon ([epic #88](https://github.com/Clems6323/OrapaMineSolo/issues/88)).
Everything here is produced by `orapa_mine.solver.benchmark` (pure Python, no pygame).

## Size tiers & extension budget

Submissions are scored on **9 grids = 3 per size tier**. Each grid's number of
extensions is drawn at random in `[0, max]`, and the extensions themselves are
chosen at random among the five (`diamond`, `filter`, `black-body`, `wormhole`,
`mystery`).

| Tier | Size (w×h) | Extensions (random count) |
|------|-----------|---------------------------|
| `small` | 8×6 | 0 – 2 |
| `standard` | 10×8 | 0 – 4 |
| `large` | 12×10 | 0 – 5 |

The per-tier maximum follows `ai.generator.MAX_EXTENSIONS_BY_SIZE`.

## Validity

A grid is **valid** only if `benchmark.is_valid` returns true, i.e. it has no
`grid_problems`:

- **placement rules** (`touche`, `cachée`) — no two gems share a flat face, and
  every gem has a clear line of sight to a border (from `ai.generator`);
- **solvable without ambiguity** (`ambiguous`) — no *other* complete board built
  from the same inventory produces the **same cell-query answers and the same
  border-ray signature**. A solver has both cell queries and rays, so a grid is
  rejected only when two boards coincide on both. (`unsolvable` is a defensive
  code that should never occur.)

`generate_valid` retries (seed + 1) until the grid is valid, so the official set
never contains an ambiguous grid.

## Generating your own practice grids

Participants develop against grids they generate themselves — the official 9 are
never shipped in advance.

```bash
# a random small grid, reproducible by its seed
uv run --no-sync python -m orapa_mine.solver.benchmark generate \
    --tier small --seed 1 --out my_grid.json

# pin the extensions, or the count
… generate --tier standard --seed 7 --extensions mystery,diamond --out g.json
… generate --tier large    --seed 9 --count 3                    --out g.json

# check any grid
uv run --no-sync python -m orapa_mine.solver.benchmark validate my_grid.json
```

In code:

```python
from orapa_mine.solver import benchmark as bm
grid, spec, pieces = bm.generate_valid("standard", seed=7)   # Grid, GridSpec, palette
```

The saved JSON reuses the game's save format (`model.serialization`) plus a
`benchmark` block (`tier`, `extensions`, `seed`) for reproducibility.

## Creating & freezing the official set (organizer, at kickoff)

```bash
uv run --no-sync python -m orapa_mine.solver.benchmark official \
    --seed 2027 --out-dir official_grids/
```

This writes nine reproducible grids (`00-small.json` … `08-large.json`). Keep the
directory **private** until the hackathon ends; the master seed makes the set
fully reproducible and auditable. Change `--seed` to roll a fresh set.
