# Orapa Mine — Python submission template

A ready-to-fork starter for the solver hackathon. Fork it into your team's GitLab,
edit `main.py`, test locally, and submit by git ref.

## Files

| File | What it is |
|------|------------|
| `orapa_client.py` | The protocol client (stdlib only). **Don't edit** — it talks to the referee for you. |
| `main.py` | The example solver. **This is what you change.** |
| `Dockerfile` | Builds the submission image (entrypoint = `python main.py`). |
| `.gitlab-ci.yml` | Optional CI: compiles the files and builds the image. |

## Write your solver

`main.py` calls `run(solve)`. Your `solve(client)` drives one grid:

```python
client.width, client.height          # grid size
client.inventory                     # pieces to place (id, quantity, orientations)
client.query(row, col)               # -> {"occupied", "color", "kind"}   (costs 3)
client.shoot(row, col, "RIGHT")      # -> {"exit", "color", "absorbed"}   (costs 1)
client.place(piece, row, col, orient, color=None)   # build the board (free)
client.remove(row, col)
client.submit()                      # -> {"won", "points", "remaining_proposals"}
client.give_up()
```

`orient` is the index into that piece's `orientations` list; `anchor` is the
top-left cell of the piece's bounding box. The mystery piece needs a guessed
`color`. See the full rules in the project's `docs/HACKATHON_PROTOCOL.md`.

## Test locally

Use the project's **local test server** — same scoring as the official server,
but on grids you generate yourself:

```bash
# one grid per tier (seed 0)
python -m orapa_mine.solver.localrun -- python main.py

# a specific grid
python -m orapa_mine.solver.localrun --tier small --seed 3 -- python main.py
```

A complete reference solver (queries + rays) is available to study:

```bash
python -m orapa_mine.solver.reference_solver   # as a submission command
```

## Submit

Push to your team's GitLab, then submit the **repo URL + a commit/branch/tag**
on the official server. The platform resolves the commit, builds this Dockerfile,
and runs it in a sandbox on the hidden grids. Scoring (lower is better):
**distance to the truth → points → CPU time**.
