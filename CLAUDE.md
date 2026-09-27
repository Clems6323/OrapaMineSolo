# CLAUDE.md — Orapa Mine (version solo, contre l'ordinateur)

Ce fichier est le point d'entrée pour Claude Code sur ce projet. Lis-le en
entier avant de coder quoi que ce soit.

## Objectif du projet

Implémenter en Python, avec interface graphique, une version **solo** du
jeu de société *Orapa Mine* (Gigamic/Miraludo) : l'ordinateur génère une
grille de gemmes cachées, l'utilisateur envoie des rayons depuis le bord du
plateau et doit déduire la position exacte de toutes les gemmes à partir des
points de sortie et couleurs annoncés.

Ce n'est **pas** un simple portage 1:1 — c'est une adaptation solo (l'ordi
remplace le "Directeur" humain), donc certaines libertés (score, chrono,
niveaux de difficulté) sont acceptables tant que le cœur de la mécanique
(tracé du rayon, déviations, mélange des couleurs) respecte les règles
réelles.

## ⚠️ Lire en premier : `docs/RULES.md`

Les règles officielles n'ont pas pu être récupérées automatiquement (le PDF
Gigamic bloque les accès automatisés). `docs/RULES.md` contient une synthèse
fiable reconstruite à partir de plusieurs sources secondaires, mais certains
points sont marqués `TODO-VALIDATION` (dimensions exactes de la grille,
table complète de mélange des couleurs, contraintes de placement).

**Avant d'implémenter `model/beam.py` ou `ai/generator.py`**, si l'utilisateur
peut fournir une photo/scan/PDF du vrai livret de règles, demande-le et
mets à jour `docs/RULES.md` en conséquence. Sinon, implémente selon les
hypothèses documentées, en gardant les constantes concernées (table de
couleurs, dimensions de grille, règles de placement) **isolées et facilement
modifiables** (voir `docs/ARCHITECTURE.md`).

## Stack technique

- Python 3.11+, stdlib uniquement pour la logique de jeu (`model/`).
- Interface graphique : **Pygame** (voir justification dans
  `docs/ARCHITECTURE.md`) — dessin custom de la grille, des gemmes et de
  l'animation du rayon.
- Gestion de projet et dépendances : **uv** (voir section "Commandes
  utiles" ci-dessous). Ne pas utiliser `pip`/`venv` directement.
- Tests : `pytest` (lancé via `uv run pytest`).
- Pas de framework web, pas de base de données : c'est un jeu local
  mono-utilisateur.

## Structure du projet

Voir `docs/ARCHITECTURE.md` pour le détail. En résumé :
- `src/orapa_mine/model/` : logique de jeu pure (gemmes, grille, rayon,
  état de partie). **Ne doit jamais importer `pygame`.**
- `src/orapa_mine/ai/` : génération de la grille cachée par l'ordinateur.
- `src/orapa_mine/ui/` : tout ce qui touche à Pygame (boucle de jeu,
  rendu, animation du rayon, gestion des événements clavier/souris).
- `tests/` : tests unitaires de `model/` (priorité absolue avant l'UI).

## Méthode de travail attendue

1. **Commence par `model/gems.py` et `model/grid.py`**, avec leurs tests.
2. **Puis `model/beam.py`** (le cœur du jeu — le plus risqué niveau règles) :
   écris d'abord les tests correspondant aux scénarios de `docs/RULES.md`
   (trajectoire simple, une déviation, deux déviations, absorption, sortie
   par l'entrée), puis implémente jusqu'à ce qu'ils passent.
3. **Puis `ai/generator.py`** (génération aléatoire valide).
4. **Puis `model/game.py`** (tours, historique, victoire).
5. **Enfin `ui/app.py`** une fois la logique testée et fiable : boucle
   Pygame (`init` → boucle d'événements → `render` → `flip`), dessin de la
   grille sur un `Surface`, puis animation du rayon (le faire progresser
   case par case plutôt que l'afficher d'un coup — c'est ce qui rendra le
   jeu agréable visuellement).
6. Utilise la skill `.claude/skills/orapa-mine-rules/SKILL.md` comme
   référence rapide dès que tu travailles sur la simulation de rayon.
7. Lance `uv run pytest` après chaque étape logique avant de passer à la
   suivante.

## Conventions de code

- Type hints partout (`from __future__ import annotations` en tête de
  fichier).
- `dataclass(frozen=True)` pour les objets valeur (Gem, Position, BeamResult).
- Noms de variables et docstrings **en français**, cohérent avec le thème du
  jeu et la langue de l'utilisateur ; noms de fichiers/modules en anglais
  standard.
- Pas de dépendance externe sauf accord explicite (voir `pyproject.toml`
  pour l'extra optionnel `pygame`, non activé par défaut).

## Ce qu'il ne faut PAS faire

- Ne pas mélanger logique de jeu et code Pygame dans les mêmes fonctions
  (pas de calcul de trajectoire dans la boucle de rendu : `ui/app.py`
  appelle `model.beam.fire_beam` et se contente d'afficher le résultat).
- Ne pas coder en dur la table de mélange des couleurs ou la taille de
  grille au milieu du code — elles doivent rester des constantes isolées et
  documentées, car marquées `TODO-VALIDATION`.
- Ne pas afficher la grille cachée du "Directeur" dans l'UI de jeu normale
  (uniquement dans un mode debug explicite, utile pour toi pendant le dev).
- Ne pas utiliser `pip install` ou `python -m venv` directement : ce projet
  est géré avec **uv** (voir ci-dessous), qui gère l'environnement virtuel
  et le lockfile automatiquement.

## Commandes utiles (avec uv)

```bash
# installer les dépendances (crée .venv automatiquement, lit pyproject.toml)
uv sync

# ajouter une dépendance
uv add <paquet>

# lancer les tests
uv run pytest

# lancer le jeu
uv run python -m orapa_mine.main
```
