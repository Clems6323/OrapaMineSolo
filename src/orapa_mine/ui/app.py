"""Application Pygame : boucle principale et machine à états des écrans.

Enchaîne trois écrans — configuration → jeu → fin — sans mélanger la logique
de jeu et le rendu (voir docs/ARCHITECTURE.md). Chaque écran expose
`handle_event` / `update` / `render` et signale ses transitions via des
attributs simples (`result`, `finished`, `restart`, `quit`).
"""

from __future__ import annotations

import random

import pygame

from orapa_mine.ai.generator import Difficulty, generate_hidden_grid
from orapa_mine.model import gems_catalog as cat
from orapa_mine.model.game import GameState
from orapa_mine.ui.config_screen import ConfigScreen
from orapa_mine.ui.creator_screen import CreatorScreen
from orapa_mine.ui.end_screen import EndScreen
from orapa_mine.ui.game_screen import GameScreen

FPS = 60


class OrapaMineApp:
    """Point d'entrée de l'application graphique (boucle Pygame)."""

    def __init__(self, seed: int | None = None) -> None:
        self.seed = seed
        pygame.init()
        pygame.display.set_caption("Orapa Mine — solo")
        self.clock = pygame.time.Clock()
        self.screen: pygame.Surface | None = None
        self.current: object = ConfigScreen()
        self._resize(self.current.size)  # type: ignore[attr-defined]
        self.running = False

    def _resize(self, size: tuple[int, int]) -> None:
        self.screen = pygame.display.set_mode(size)

    def run(self) -> None:
        self.running = True
        while self.running:
            dt = self.clock.tick(FPS) / 1000.0
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    self.running = False
                else:
                    self.current.handle_event(event)  # type: ignore[attr-defined]
            self.current.update(dt)  # type: ignore[attr-defined]
            self.current.render(self.screen)  # type: ignore[attr-defined]
            pygame.display.flip()
            self._handle_transitions()
        pygame.quit()

    def _handle_transitions(self) -> None:
        screen = self.current
        if isinstance(screen, CreatorScreen) and screen.pending_resize:
            self._resize(screen.size)
            screen.pending_resize = False
        if isinstance(screen, ConfigScreen) and screen.loaded is not None:
            self._start_loaded(screen.loaded)
        elif isinstance(screen, ConfigScreen) and screen.creator is not None:
            self._start_creator(screen.creator)
        elif isinstance(screen, ConfigScreen) and screen.result is not None:
            self._start_game(screen.result)
        elif isinstance(screen, CreatorScreen) and screen.play is not None:
            self._start_from_grid(screen.play, screen.palette_pieces)
        elif isinstance(screen, CreatorScreen) and screen.back:
            self.current = ConfigScreen()
            self._resize(self.current.size)
        elif isinstance(screen, GameScreen) and screen.finished is not None:
            outcome, score = screen.finished
            self._show_end(
                outcome == "win", score, screen.game.hidden_grid, screen.palette_pieces
            )
        elif isinstance(screen, EndScreen):
            if screen.restart:
                self.current = ConfigScreen()
                self._resize(self.current.size)
            elif screen.quit:
                self.running = False

    def _start_game(self, difficulty: Difficulty) -> None:
        rng = random.Random(self.seed)
        grid = generate_hidden_grid(difficulty=difficulty, rng=rng)
        game = GameState(hidden_grid=grid)
        self.current = GameScreen(game, palette_pieces=difficulty.pieces)
        self._resize(self.current.size)

    def _start_creator(self, difficulty: Difficulty) -> None:
        # Reprend la sélection du menu comme valeurs de départ ; l'utilisateur
        # peut ensuite les changer directement dans le mode créateur.
        sizes = [(w, h) for _, w, h in CreatorScreen._SIZES]
        try:
            size_index = sizes.index((difficulty.width, difficulty.height))
        except ValueError:
            size_index = 1
        self.current = CreatorScreen(
            size_index=size_index,
            diamant=cat.DIAMOND in difficulty.pieces,
            corps_noir=cat.BLACK_BODY in difficulty.pieces,
            wormhole=cat.WORMHOLE in difficulty.pieces,
        )
        self._resize(self.current.size)

    def _start_from_grid(self, grid, palette_pieces) -> None:
        game = GameState(hidden_grid=grid)
        self.current = GameScreen(game, palette_pieces=palette_pieces)
        self._resize(self.current.size)

    def _start_loaded(self, loaded) -> None:
        screen = GameScreen(loaded.game, palette_pieces=loaded.palette_pieces)
        screen.hypothesis = loaded.hypothesis
        counts: dict[str, int] = {}
        for gem in loaded.hypothesis.gems:
            counts[gem.piece.name] = counts.get(gem.piece.name, 0) + 1
        screen.placed_counts = counts
        self.current = screen
        self._resize(self.current.size)

    def _show_end(self, won: bool, score: int, hidden_grid, palette_pieces) -> None:
        self.current = EndScreen(
            won=won, score=score, hidden_grid=hidden_grid, palette_pieces=palette_pieces
        )
        self._resize(self.current.size)
