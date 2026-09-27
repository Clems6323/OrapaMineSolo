# AGENTS.md

Ce fichier suit la convention [agents.md](https://agents.md) pour rester
compatible avec d'autres outils agentiques que Claude Code (Codex, Cursor,
etc.). Pour Claude Code, la référence canonique et la plus détaillée est
**`CLAUDE.md`** — lis-le en premier s'il est disponible.

## Résumé du projet

Jeu *Orapa Mine* en solo contre l'ordinateur, en Python + Pygame. Logique
de jeu pure dans `src/orapa_mine/model/` (sans dépendance UI), interface
graphique Pygame dans `src/orapa_mine/ui/`.

## Règles d'or

1. Lire `docs/RULES.md` avant de toucher à `model/beam.py` ou
   `ai/generator.py` : plusieurs constantes de règles sont marquées
   `TODO-VALIDATION` (non confirmées avec le livret officiel).
2. `model/` ne doit jamais importer `pygame`.
3. TDD sur `model/` : écrire les tests avant l'implémentation, en
   particulier pour la simulation de trajectoire du rayon.
4. Type hints obligatoires, `dataclass(frozen=True)` pour les objets valeur.
5. Gestion des dépendances avec **uv** uniquement (pas de `pip`/`venv`
   manuel).

## Setup

```bash
uv sync
```

## Build / Test

```bash
uv run pytest
```

## Lancer le jeu

```bash
uv run python -m orapa_mine.main
```

## Style

- Docstrings et noms de variables en français.
- Pas de nouvelle dépendance externe sans raison documentée dans
  `docs/ARCHITECTURE.md` (ajoutée avec `uv add <paquet>`).

## PR / commits

Projet personnel, pas de convention stricte de commit imposée. Préférer des
commits atomiques par module (`model/gems.py`, puis `model/beam.py`, etc.)
pour faciliter la revue.
