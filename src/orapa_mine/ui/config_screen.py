"""Écran de configuration de partie : difficulté, extensions, taille de grille.

Produit une `Difficulty` (via `self.result`) que l'app lit pour lancer la
partie. Aucune règle de jeu ici.
"""

from __future__ import annotations

import pygame

from orapa_mine.ai.generator import Difficulty
from orapa_mine.model import gems_catalog as cat
from orapa_mine.ui import theme

SIZE = (760, 660)


class ConfigScreen:
    """Menu de configuration cliquable (rectangles + cases à cocher)."""

    def __init__(self) -> None:
        self.size = SIZE
        self.diamant = False
        self.corps_noir = False
        self.sizes = [("Petit", 8, 6), ("Standard", 10, 8), ("Grand", 12, 10)]
        self.size_index = 1
        self.result: Difficulty | None = None

        pygame.font.init()
        self.font_big = pygame.font.SysFont("arial", 40, bold=True)
        self.font = pygame.font.SysFont("arial", 20)
        self.font_small = pygame.font.SysFont("arial", 16)

        cx = self.size[0] // 2
        self.diamant_rect = pygame.Rect(170, 232, 26, 26)
        self.corps_rect = pygame.Rect(170, 274, 26, 26)
        bw, gap = 180, 20
        total = 3 * bw + 2 * gap
        start_x = (self.size[0] - total) // 2
        self.size_rects = [
            pygame.Rect(start_x + i * (bw + gap), 372, bw, 60) for i in range(3)
        ]
        self.start_rect = pygame.Rect(cx - 130, 552, 260, 58)

    # --- Événements --------------------------------------------------------

    def handle_event(self, event: pygame.event.Event) -> None:
        if event.type != pygame.MOUSEBUTTONDOWN or event.button != 1:
            return
        p = event.pos
        if self.diamant_rect.collidepoint(p):
            self.diamant = not self.diamant
        elif self.corps_rect.collidepoint(p):
            self.corps_noir = not self.corps_noir
        elif self.start_rect.collidepoint(p):
            self._begin()
        else:
            for i, rect in enumerate(self.size_rects):
                if rect.collidepoint(p):
                    self.size_index = i

    def _begin(self) -> None:
        pieces = [cat.RED, cat.YELLOW, cat.BLUE, cat.WHITE_BIG, cat.WHITE_SMALL]
        if self.diamant:
            pieces.append(cat.DIAMOND)
        if self.corps_noir:
            pieces.append(cat.BLACK_BODY)
        name, width, height = self.sizes[self.size_index]
        self.result = Difficulty(
            pieces=pieces, width=width, height=height, name=name.lower()
        )

    def update(self, dt: float) -> None:  # noqa: D401 - rien à animer
        pass

    # --- Rendu -------------------------------------------------------------

    def render(self, surface: pygame.Surface) -> None:
        surface.fill(theme.BACKGROUND)
        cx = self.size[0] // 2
        title = self.font_big.render("ORAPA MINE", True, theme.TEXT)
        surface.blit(title, title.get_rect(centerx=cx, y=56))
        sub = self.font.render("Configuration de la partie", True, theme.TEXT_DIM)
        surface.blit(sub, sub.get_rect(centerx=cx, y=108))

        base = self.font_small.render(
            "Base : 1 rouge, 1 jaune, 1 bleu, 2 blanches (5 gemmes)", True, theme.TEXT_DIM
        )
        surface.blit(base, (100, 158))

        surface.blit(self.font.render("Extensions", True, theme.TEXT), (100, 196))
        self._checkbox(surface, self.diamant_rect, self.diamant, "Diamant (dévie sans teinter)")
        self._checkbox(surface, self.corps_rect, self.corps_noir, "Corps noir (absorbe le rayon)")

        surface.blit(self.font.render("Taille de la grille", True, theme.TEXT), (100, 332))
        for i, rect in enumerate(self.size_rects):
            selected = i == self.size_index
            bg = theme.SLOT_SELECTED if selected else theme.SLOT_BG
            pygame.draw.rect(surface, bg, rect, border_radius=8)
            pygame.draw.rect(surface, theme.BOARD_BORDER, rect, width=1, border_radius=8)
            name, w, h = self.sizes[i]
            fg = theme.BACKGROUND if selected else theme.TEXT
            n = self.font.render(name, True, fg)
            d = self.font_small.render(f"{w} × {h}", True, fg if selected else theme.TEXT_DIM)
            surface.blit(n, n.get_rect(centerx=rect.centerx, y=rect.y + 10))
            surface.blit(d, d.get_rect(centerx=rect.centerx, y=rect.y + 34))

        total = 5 + (1 if self.diamant else 0) + (1 if self.corps_noir else 0)
        count = self.font_small.render(f"Total : {total} gemmes à trouver", True, theme.TEXT_DIM)
        surface.blit(count, count.get_rect(centerx=cx, y=470))

        pygame.draw.rect(surface, (54, 120, 90), self.start_rect, border_radius=10)
        pygame.draw.rect(surface, theme.BOARD_BORDER, self.start_rect, width=1, border_radius=10)
        label = self.font.render("Commencer", True, theme.TEXT)
        surface.blit(label, label.get_rect(center=self.start_rect.center))

    def _checkbox(self, surface: pygame.Surface, rect: pygame.Rect, on: bool, text: str) -> None:
        pygame.draw.rect(surface, theme.INPUT_BG, rect, border_radius=4)
        pygame.draw.rect(surface, theme.BOARD_BORDER, rect, width=1, border_radius=4)
        if on:
            inner = rect.inflate(-8, -8)
            pygame.draw.rect(surface, theme.SLOT_SELECTED, inner, border_radius=3)
        label = self.font.render(text, True, theme.TEXT)
        surface.blit(label, (rect.right + 14, rect.y + 2))
