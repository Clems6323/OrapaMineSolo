"""Worker d'évaluation du serveur officiel (issue #95).

Draine la file des soumissions : pour chacune, **build** (clone + `docker build`,
réseau autorisé) puis **eval** (bac à sable sans réseau sur les 9 grilles
officielles), et stocke le résultat. La partie Docker est isolée dans
`evaluate_repo` ; `run_pending` l'injecte, donc l'orchestration (file, statuts,
échecs) se teste sans Docker.
"""

from __future__ import annotations

import subprocess
import tempfile
import uuid
from pathlib import Path

from orapa_mine.solver import evaluate, sandbox
from orapa_mine.solver.evaluate import GridEntry
from orapa_mine.server.storage import Store, Submission


class BuildError(Exception):
    """Échec du clone ou du `docker build`."""


class EvalError(Exception):
    """L'image démarre mais échoue au smoke test / à l'évaluation."""


def evaluate_repo(
    repo_url: str,
    ref: str,
    grids: list[GridEntry],
    *,
    profile: sandbox.SandboxProfile = sandbox.DEFAULT_PROFILE,
    workdir: str | None = None,
) -> tuple[str, dict]:
    """Clone `ref`, construit l'image, smoke-test, puis évalue sur `grids`.

    Renvoie `(sha, artefact JSON)`. Dépend de Docker ; utilisé par le worker réel,
    injecté par un faux en test."""
    base = Path(workdir or tempfile.mkdtemp(prefix="orapa-sub-"))
    dest = str(base / "repo")
    tag = f"orapa-sub-{uuid.uuid4().hex[:12]}"

    # --- Phase build (réseau autorisé) ---
    try:
        for cmd in sandbox.clone_commands(repo_url, ref, dest):
            subprocess.run(cmd, check=True, capture_output=True, timeout=120)
        sha = subprocess.run(
            ["git", "-C", dest, "rev-parse", "HEAD"],
            check=True, capture_output=True, text=True, timeout=30,
        ).stdout.strip()
        subprocess.run(
            sandbox.docker_build_command(dest, tag), check=True, capture_output=True, timeout=600
        )
    except (subprocess.SubprocessError, OSError) as exc:
        raise BuildError(str(exc)) from exc

    # --- Smoke test d'acceptation ---
    ok, message = sandbox.smoke_test(tag, profile=profile)
    if not ok:
        raise EvalError(message)

    # --- Phase eval (bac à sable, aucun réseau) ---
    scores = [
        evaluate.score_grid(
            sandbox.run_sandboxed(tag, entry.grid, profile=profile),
            entry.grid_id, entry.tier,
        )
        for entry in grids
    ]
    return sha, evaluate.to_json(evaluate.aggregate(scores))


def process(store: Store, submission: Submission, grids: list[GridEntry], *, evaluate_fn=evaluate_repo) -> None:
    """Évalue une soumission et enregistre son résultat (ou son échec)."""
    try:
        sha, artifact = evaluate_fn(submission.repo_url, submission.ref, grids)
        store.record_result(submission.id, sha, artifact)
    except (BuildError, EvalError) as exc:
        store.record_failure(submission.id, f"{type(exc).__name__}: {exc}")


def run_pending(store: Store, grids: list[GridEntry], *, evaluate_fn=evaluate_repo) -> int:
    """Traite toutes les soumissions en file. Renvoie le nombre traité."""
    pending = store.pending_submissions()
    for submission in pending:
        process(store, submission, grids, evaluate_fn=evaluate_fn)
    return len(pending)


def official_grid_entries(master_seed: int = 2027) -> list[GridEntry]:
    """Les 9 entrées officielles (générées à la demande par l'organisateur)."""
    from orapa_mine.solver import benchmark

    return [
        GridEntry(grid_id=f"{idx:02d}-{spec.tier}", tier=spec.tier, grid=grid)
        for idx, (grid, spec, _pieces) in enumerate(benchmark.official_set(master_seed))
    ]


def main(argv: list[str] | None = None) -> int:  # pragma: no cover - boucle worker
    import argparse
    import time

    from orapa_mine.solver.evaluate import load_grid_set

    parser = argparse.ArgumentParser(description="Worker d'évaluation (#95).")
    parser.add_argument("--db", required=True, help="chemin SQLite partagé")
    parser.add_argument("--grids", required=True, help="dossier des grilles officielles")
    parser.add_argument("--interval", type=float, default=5.0, help="intervalle de scrutation (s)")
    parser.add_argument("--once", action="store_true", help="traiter la file puis sortir")
    args = parser.parse_args(argv)

    store = Store(args.db)
    grids = load_grid_set(args.grids)
    while True:
        done = run_pending(store, grids)
        if args.once:
            print(f"{done} soumission(s) traitée(s)")
            return 0
        time.sleep(args.interval)


if __name__ == "__main__":  # pragma: no cover
    import sys

    raise SystemExit(main(sys.argv[1:]))
