# Participate — Orapa Mine solver hackathon

Write an algorithm that solves any proposed Orapa Mine grid with the **fewest
query points and the least CPU time**. See the full concept in
[epic #88](https://github.com/Clems6323/OrapaMineSolo/issues/88).

## 1. Fork the template

Start from [`templates/python/`](../templates/python) — fork it into your team's
GitLab. It contains the protocol client (`orapa_client.py`, stdlib only), an
example solver (`main.py`), a `Dockerfile`, and optional CI. Any language works
as long as it speaks the protocol; Python is the shortest path.

## 2. Learn the protocol

Your program exchanges **one JSON object per line** with a referee over
stdin/stdout. The full contract, with a generated piece/anchor/orientation
reference, is in [`docs/HACKATHON_PROTOCOL.md`](HACKATHON_PROTOCOL.md). In Python
the client wraps it as plain calls — see the template `README`.

## 3. Test locally

The **local test server** runs your solver on grids you generate yourself, with
the exact same scoring as the official server (no leaderboard, no persistence):

```bash
# one grid per size tier
python -m orapa_mine.solver.localrun -- python main.py

# a specific grid, reproducible by seed
python -m orapa_mine.solver.localrun --tier large --seed 7 -- python main.py
```

Generate standalone practice grids and inspect/validate them with the benchmark
CLI (see [`docs/BENCHMARK.md`](BENCHMARK.md)):

```bash
python -m orapa_mine.solver.benchmark generate --tier small --seed 1 --out g.json
python -m orapa_mine.solver.benchmark validate g.json
```

A full **reference solver** (queries + rays, always solves a valid grid, but
spends many points) is there to study and beat:

```bash
python -m orapa_mine.solver.reference_solver
```

## 4. Scoring

Per grid: **distance to the truth** (0 = exact solve; a mystery gem on the right
cell but wrong colour adds 1.0), **points** (ray = 1, cell query = 3, wrong
submit = 5), and **CPU time**. A board may be submitted only when **all** pieces
are placed, and you get **5 attempts** per grid. Submissions are ranked
**lexicographically, all ascending**: total distance, then total points, then
total CPU time. A grid with no complete submission scores a distance of 1000.

## 5. Submit

Push to your team's GitLab and submit the **repo URL + a commit/branch/tag** on
the official server (after signing in with your team handle). The platform
resolves the commit, builds your `Dockerfile`, and runs it sandboxed on the
hidden official grids. Develop locally, submit the same package unchanged.
