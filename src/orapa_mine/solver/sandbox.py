"""Bac à sable d'exécution des soumissions (issue #96).

Les soumissions sont du **code non fiable**. Ce module construit l'isolation
autour du sous-processus que l'arbitre (#91) lance : conteneur sans réseau,
racine en lecture seule, limites de ressources, aucune capacité, aucune fuite de
la grille cachée (celle-ci ne transite que par le protocole).

Séparation nette **build / eval** :
- **build** (clone + `docker build`) : réseau autorisé (GitLab + images de base) ;
- **eval** (`docker run`) : **aucun réseau**, racine en lecture seule, limites.

Le module se contente de **construire les commandes** et d'orchestrer ; Docker
n'est pas requis pour l'importer ni le tester (les commandes sont vérifiées au
niveau argv). L'exécution réelle n'a lieu que là où Docker est présent.
"""

from __future__ import annotations

import shutil
import subprocess
from dataclasses import dataclass

from orapa_mine.solver import benchmark
from orapa_mine.solver.referee import GridResult, run_submission


@dataclass(frozen=True)
class SandboxProfile:
    """Enveloppe de ressources d'un conteneur d'évaluation (documentée, figée).

    Les participants peuvent compter sur ces limites ; elles sont imposées par la
    plateforme, jamais par la soumission."""

    memory: str = "512m"       # RAM max (swap désactivé en l'égalant)
    cpus: str = "1.0"          # cœurs CPU
    pids_limit: int = 128      # nombre de processus/threads (anti fork-bomb)
    nofile: int = 256          # descripteurs de fichiers (ulimit -n)
    tmpfs_size: str = "64m"    # /tmp inscriptible (le reste est en lecture seule)
    name: str = "default"


DEFAULT_PROFILE = SandboxProfile()


# --- Construction des commandes ----------------------------------------------


def docker_run_command(image: str, profile: SandboxProfile = DEFAULT_PROFILE,
                       *, name: str | None = None) -> list[str]:
    """`docker run` durci pour la **phase d'évaluation** (aucun réseau).

    Interactif (`-i`) : l'arbitre parle le protocole sur stdin/stdout. Aucun
    montage (`-v`/`--mount`) ni variable d'environnement : la grille cachée ne
    passe que par le protocole, jamais par le système de fichiers."""
    cmd = [
        "docker", "run", "--rm", "-i",
        "--network", "none",                 # aucun réseau pendant l'évaluation
        "--read-only",                        # racine en lecture seule
        "--tmpfs", f"/tmp:rw,size={profile.tmpfs_size},noexec,nosuid",
        "--memory", profile.memory,
        "--memory-swap", profile.memory,      # pas de swap
        "--cpus", profile.cpus,
        "--pids-limit", str(profile.pids_limit),
        "--ulimit", f"nofile={profile.nofile}:{profile.nofile}",
        "--cap-drop", "ALL",                  # aucune capacité Linux
        "--security-opt", "no-new-privileges",
    ]
    if name:
        cmd += ["--name", name]
    cmd.append(image)                         # l'image (son ENTRYPOINT) en dernier
    return cmd


def docker_build_command(context_dir: str, tag: str, *, dockerfile: str = "Dockerfile") -> list[str]:
    """`docker build` de la **phase de build** (réseau autorisé).

    Construit l'image depuis le dépôt cloné ; le réseau (GitLab, registre d'images
    de base) n'est disponible qu'ici, jamais à l'évaluation."""
    return ["docker", "build", "-t", tag, "-f", f"{context_dir}/{dockerfile}", context_dir]


def clone_commands(repo_url: str, ref: str, dest_dir: str) -> list[list[str]]:
    """Commandes de clone + checkout d'un `ref` (branche, tag **ou** commit).

    Phase de build (réseau autorisé). On résout toujours vers un commit immuable
    côté plateforme ; `checkout --detach` accepte branche/tag/SHA."""
    return [
        ["git", "clone", "--no-checkout", repo_url, dest_dir],
        ["git", "-C", dest_dir, "checkout", "--detach", ref],
    ]


def build_plan(repo_url: str, ref: str, dest_dir: str, tag: str,
               *, dockerfile: str = "Dockerfile") -> dict:
    """Plan de build (phase réseau) : les commandes de clone puis de build."""
    return {
        "clone": clone_commands(repo_url, ref, dest_dir),
        "build": docker_build_command(dest_dir, tag, dockerfile=dockerfile),
    }


# --- Exécution (délègue à l'arbitre) -----------------------------------------


def docker_available() -> bool:
    """Vrai si Docker est **utilisable** (CLI présente ET démon joignable).

    On vérifie le démon (`docker info`) : la CLI seule ne suffit pas (démon
    arrêté / hors-ligne). Sert à n'exécuter les tests d'intégration que là où
    Docker fonctionne vraiment."""
    if shutil.which("docker") is None:
        return False
    try:
        return subprocess.run(
            ["docker", "info"], capture_output=True, timeout=15
        ).returncode == 0
    except (OSError, subprocess.SubprocessError):
        return False


def run_sandboxed(
    image: str,
    grid,
    *,
    profile: SandboxProfile = DEFAULT_PROFILE,
    max_proposals: int = 5,
    move_timeout_ms: int = 2000,
    cpu_time_ms: int = 10000,
    total_timeout_ms: int | None = 30000,
    name: str | None = None,
) -> GridResult:
    """Évalue `image` sur `grid` dans un conteneur durci.

    L'arbitre pilote le `docker run` comme n'importe quel sous-processus : le
    conteneur fournit l'isolation dure, l'arbitre les délais/plafonds logiciels.
    Une image qui plante/boucle/déborde est contenue (`dnf_reason`)."""
    command = docker_run_command(image, profile, name=name)
    return run_submission(
        command, grid, max_proposals=max_proposals, move_timeout_ms=move_timeout_ms,
        cpu_time_ms=cpu_time_ms, total_timeout_ms=total_timeout_ms,
    )


def smoke_test(image: str, *, profile: SandboxProfile = DEFAULT_PROFILE,
               tier: str = "small", seed: int = 0) -> tuple[bool, str]:
    """Teste à l'acceptation qu'une image démarre et joue sur un échantillon.

    Rejette tôt (message clair) une soumission qui ne démarre pas (`spawn_failed`)
    ou meurt sans rien faire ; accepte dès qu'elle parle le protocole."""
    grid, _spec, _pieces = benchmark.generate_valid(tier, seed=seed)
    result = run_sandboxed(image, grid, profile=profile)
    if result.dnf_reason == "spawn_failed":
        return False, "image did not start"
    if result.dnf_reason == "eof" and result.moves == 0:
        return False, "submission exited without playing"
    return True, "ok"
