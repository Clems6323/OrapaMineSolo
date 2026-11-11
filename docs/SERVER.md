# Official hosted server

Part of the solver hackathon ([epic #88](https://github.com/Clems6323/OrapaMineSolo/issues/88)).
The server where teams sign in, submit by git ref, and are ranked. Built with
**Streamlit** (UI) + an **evaluation worker**, sharing a SQLite store, reusing the
sandbox (#96), grids (#92) and scoring (#93).

## Architecture

```
            ┌──────────────┐   add_submission    ┌─────────────┐
 team ────▶ │ Streamlit UI │ ──────────────────▶ │  SQLite     │
 (browser)  │  (app.py)    │ ◀── leaderboard ─── │  (storage)  │
            └──────────────┘                      └─────┬───────┘
                                                        │ pending
                                                        ▼
                                             ┌────────────────────┐
                                             │   worker.py        │
                                             │  build (network)   │  clone + docker build
                                             │  eval  (sandbox)   │  run on the 9 grids, no network
                                             └────────────────────┘
```

- **UI** (`server/app.py`): team sign-up/sign-in (pseudo + password), the public
  leaderboard, a submission form (repo URL + ref), and a **minimal** team page.
- **Store** (`server/storage.py`): teams (PBKDF2-hashed passwords), submissions,
  results; the leaderboard keeps each team's **best** result.
- **Worker** (`server/worker.py`): drains the queue — clone + `docker build`
  (network), then sandboxed evaluation on the official grids (no network), and
  records the result or a failure.

## Authentication

Each team registers a **pseudo + password** and must sign in before submitting.
Passwords are stored as PBKDF2-HMAC-SHA256 (per-row salt). The leaderboard is
public; submitting requires a signed-in team.

## Submission = git ref

A signed-in team submits a **GitLab repo URL + ref** (branch/tag/commit). The
worker resolves it to an immutable commit SHA, builds the repo's `Dockerfile`,
smoke-tests it, then evaluates it on the hidden official grids. Teams start from
the [template](../templates/python) (`docs/PARTICIPATE.md`).

## Ranking & anti-cheat

Ranking is **total distance → total points → total CPU time** (all ascending;
see `docs/BENCHMARK.md` and `#93`). Team pages show **only** the overall result
and per-grid `distance/points/CPU/DNF reason` — **never** a transcript, move log,
or grid contents, so teams cannot reconstruct and memorise the hidden grids.

## Deploy (internal server or cloud)

```bash
# 1. Freeze the hidden official grids (keep ./data/official_grids private):
python -m orapa_mine.solver.benchmark official --seed 2027 --out-dir ./data/official_grids

# 2. Bring up the UI + worker:
docker compose -f deploy/docker-compose.yml up -d --build
# UI on http://<host>:8501
```

The worker needs the Docker daemon (it builds and runs submission images). Mounting
`/var/run/docker.sock` grants it high privilege — for stronger isolation, run the
worker on a dedicated host or against a remote/rootless Docker daemon. The
submissions themselves are sandboxed (`docs/SANDBOX.md`): no network during eval,
resource caps, no access to the hidden grids except through the protocol.

## Scale (~100 teams)

Each evaluation is an independent sandboxed `docker run`; run several worker
replicas (or raise the pool) to drain submissions in parallel. SQLite suffices for
~100 teams; move to Postgres if you need many concurrent writers.

## Scope note

The storage, auth, queue/worker orchestration and ranking are pure Python and
unit-tested (`tests/test_server.py`). The Streamlit UI and the Docker build/run in
`evaluate_repo` require those tools at runtime and are exercised by deployment, not
the unit suite (the worker is tested with an injected evaluator).
