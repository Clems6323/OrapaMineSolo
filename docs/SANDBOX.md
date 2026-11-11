# Execution sandbox & security

Part of the solver hackathon ([epic #88](https://github.com/Clems6323/OrapaMineSolo/issues/88)).
Submissions are **untrusted code**. Running them must not endanger the host, leak
the hidden grids, or let anyone cheat. This is implemented by
`orapa_mine.solver.sandbox` around the referee (#91).

## Threat model

A submission is an arbitrary program a team pushed to their GitLab. It may try to:
reach the network, read files outside its directory, exhaust CPU/RAM, fork-bomb,
flood stdout, run forever, or probe for the hidden grids. None of this may harm
the host or reveal the grids, and a misbehaving submission must simply score a
DNF (sentinel distance 1000), never crash the platform.

## Two phases, two network policies

| Phase | What runs | Network |
|-------|-----------|---------|
| **build** | clone the repo at the resolved commit, `docker build` | **allowed** (internal GitLab + base-image registry) |
| **eval** | run the built image on the grids | **none** |

The grids are never present during build; the network is never present during
eval. `sandbox.build_plan` produces the build-phase commands; `docker_run_command`
produces the eval-phase command.

## Hardened eval container

`docker_run_command(image, profile)` runs the image with:

- `--network none` — no network during evaluation;
- `--read-only` root + a small `--tmpfs /tmp` (`noexec,nosuid`) — the only writable path;
- `--memory` / `--memory-swap` equal — a hard RAM cap, no swap;
- `--cpus` — bounded CPU;
- `--pids-limit` — caps processes/threads (defuses fork bombs);
- `--ulimit nofile` — caps open file descriptors;
- `--cap-drop ALL` + `--security-opt no-new-privileges` — no Linux capabilities, no privilege escalation;
- `-i` only — the referee speaks the protocol over stdin/stdout; **no `-v`/`--mount`/`-e`**, so the hidden grid reaches the solver *only* through the protocol, never the filesystem or environment.

The default profile (`SandboxProfile`) is documented and fixed so timing is
comparable across submissions, and participants can rely on the limits.

## Defence in depth (referee limits)

On top of container isolation, the referee (#91) enforces a **per-move timeout**,
a **total time budget**, and an **output-size cap**, and turns any crash, hang,
flood, malformed line, or illegal move into a clean DNF. So even without perfect
container limits, a misbehaving solver is contained and scored, never fatal.

## Abuse → outcome

| Attempt | Mitigation | Outcome |
|---------|-----------|---------|
| Network call during eval | `--network none` | call fails; solver continues or DNF |
| Fork bomb | `--pids-limit` | capped; eventual move timeout → DNF |
| Memory bomb | `--memory` (no swap) | OOM-killed → DNF |
| Infinite output | referee output cap | `output_overflow` DNF |
| Infinite loop / hang | move & total timeouts | `move_timeout` / `timeout` DNF |
| Write outside /tmp | `--read-only` root | write fails |
| Read the hidden grid | not mounted; protocol-only | nothing to read |
| Privilege escalation | `--cap-drop ALL`, `no-new-privileges` | denied |

## Pre-acceptance smoke test

`smoke_test(image)` runs the image on one sample grid and rejects early, with a
clear message, a submission that does not start (`spawn_failed`) or exits without
playing. A working submission is accepted.

## Throughput (~100 teams)

Each evaluation is an independent, isolated `docker run`, so a bounded pool of
workers can evaluate many submissions in parallel without the host thrashing; the
official server (#95) owns the queue and the pool. Keep base images warm to lower
per-run startup cost.

## Scope & testing

This module **builds the commands and orchestrates**; it needs no Docker to be
imported or unit-tested (the argv are asserted directly). The real build + run is
exercised by an integration test that **skips unless Docker is actually usable**
(`docker_available()` checks the daemon, not just the CLI).
