"""Écran de configuration de partie : difficulté, extensions, taille de grille.

Produit une `Difficulty` (via `self.result`) que l'app lit pour lancer la
partie. Aucune règle de jeu ici.
"""

from __future__ import annotations

import pygame

from orapa_mine.ai.generator import Difficulty
from orapa_mine.model import gems_catalog as cat
from orapa_mine.model import serialization
from orapa_mine.model.serialization import LoadedGame
from orapa_mine.ui import dialogs, i18n, theme
from orapa_mine.ui.timer_field import TimerField

SIZE = (760, 720)


class ConfigScreen:
    """Menu de configuration cliquable (rectangles + cases à cocher)."""

    def __init__(self) -> None:
        self.size = SIZE
        self.diamant = False
        self.corps_noir = False
        self.wormhole = False
        self.sizes = [("Petit", 8, 6), ("Standard", 10, 8), ("Grand", 12, 10)]
        self.size_index = 1
        self.timer = TimerField()  # minuteur optionnel (0 = désactivé)
        self.result: Difficulty | None = None
        self.loaded: LoadedGame | None = None
        self.creator: Difficulty | None = None  # lancer le mode créateur
        self.error: str | None = None

        pygame.font.init()
        self.font_big = pygame.font.SysFont("arial", 40, bold=True)
        self.font = pygame.font.SysFont("arial", 20)
        self.font_small = pygame.font.SysFont("arial", 16)

        cx = self.size[0] // 2
        self.diamant_rect = pygame.Rect(170, 228, 26, 26)
        self.corps_rect = pygame.Rect(170, 266, 26, 26)
        self.wormhole_rect = pygame.Rect(170, 304, 26, 26)
        bw, gap = 180, 20
        total = 3 * bw + 2 * gap
        start_x = (self.size[0] - total) // 2
        self.size_rects = [
            pygame.Rect(start_x + i * (bw + gap), 384, bw, 60) for i in range(3)
        ]
        # Minuteur (stepper − valeur + éditable), centré sous le total de gemmes.
        self.timer.set_rects(
            pygame.Rect(271, 542, 44, 40),
            pygame.Rect(325, 542, 110, 40),
            pygame.Rect(445, 542, 44, 40),
        )

        bw2, gap2 = 224, 16
        total2 = 3 * bw2 + 2 * gap2
        bx = (self.size[0] - total2) // 2
        self.start_rect = pygame.Rect(bx, 614, bw2, 58)
        self.creator_rect = pygame.Rect(bx + bw2 + gap2, 614, bw2, 58)
        self.load_rect = pygame.Rect(bx + 2 * (bw2 + gap2), 614, bw2, 58)
        fw, fh, fgap = 44, 28, 10
        fx = self.size[0] - 2 * fw - fgap - 24
        self.fr_flag_rect = pygame.Rect(fx, 24, fw, fh)
        self.uk_flag_rect = pygame.Rect(fx + fw + fgap, 24, fw, fh)

    # --- Événements --------------------------------------------------------

    def handle_event(self, event: pygame.event.Event) -> None:
        if event.type == pygame.KEYDOWN:
            self.timer.handle_key(event)
            return
        if event.type != pygame.MOUSEBUTTONDOWN or event.button != 1:
            return
        p = event.pos
        if self.timer.handle_click(p):  # − / + / case du minuteur
            return
        if self.fr_flag_rect.collidepoint(p):
            i18n.set_language("fr")
        elif self.uk_flag_rect.collidepoint(p):
            i18n.set_language("en")
        elif self.diamant_rect.collidepoint(p):
            self.diamant = not self.diamant
        elif self.corps_rect.collidepoint(p):
            self.corps_noir = not self.corps_noir
        elif self.wormhole_rect.collidepoint(p):
            self.wormhole = not self.wormhole
        elif self.start_rect.collidepoint(p):
            self._begin()
        elif self.creator_rect.collidepoint(p):
            self.creator = self._difficulty()
        elif self.load_rect.collidepoint(p):
            self._load()
        else:
            for i, rect in enumerate(self.size_rects):
                if rect.collidepoint(p):
                    self.size_index = i

    def _load(self) -> None:
        path = dialogs.ask_open_path()
        if not path:
            return
        try:
            self.loaded = serialization.from_dict(dialogs.read_json(path))
        except (OSError, ValueError, KeyError) as exc:
            self.error = i18n.t("Chargement impossible : ", "Could not load: ") + str(exc)

    def _difficulty(self) -> Difficulty:
        """Construit la difficulté à partir des cases/boutons sélectionnés."""
        pieces = [cat.RED, cat.YELLOW, cat.BLUE, cat.WHITE_BIG, cat.WHITE_SMALL]
        if self.diamant:
            pieces.append(cat.DIAMOND)
        if self.corps_noir:
            pieces.append(cat.BLACK_BODY)
        if self.wormhole:
            pieces.append(cat.WORMHOLE)
        name, width, height = self.sizes[self.size_index]
        return Difficulty(
            pieces=pieces, width=width, height=height, name=name.lower(),
            timer_minutes=self.timer.minutes,
        )

    def _begin(self) -> None:
        self.result = self._difficulty()

    def update(self, dt: float) -> None:  # noqa: D401 - rien à animer
        pass

    # --- Rendu -------------------------------------------------------------

    def render(self, surface: pygame.Surface) -> None:
        surface.fill(theme.BACKGROUND)
        cx = self.size[0] // 2
        title = self.font_big.render("ORAPA MINE", True, theme.TEXT)
        surface.blit(title, title.get_rect(centerx=cx, y=56))
        sub = self.font.render(i18n.t("Configuration de la partie", "Game setup"), True, theme.TEXT_DIM)
        surface.blit(sub, sub.get_rect(centerx=cx, y=108))

        # Sélecteur de langue : drapeaux France / Royaume-Uni.
        self._draw_flag(surface, self.fr_flag_rect, "fr", active=i18n.LANG == "fr")
        self._draw_flag(surface, self.uk_flag_rect, "uk", active=i18n.LANG == "en")

        base = self.font_small.render(
            i18n.t("Base : 1 rouge, 1 jaune, 1 bleu, 2 blanches (5 gemmes)",
                   "Base: 1 red, 1 yellow, 1 blue, 2 white (5 gems)"), True, theme.TEXT_DIM
        )
        surface.blit(base, (100, 158))

        surface.blit(self.font.render(i18n.t("Extensions", "Extensions"), True, theme.TEXT), (100, 196))
        self._checkbox(surface, self.diamant_rect, self.diamant,
                       i18n.t("Diamant (dévie sans teinter)", "Diamond (deviates without tinting)"))
        self._checkbox(surface, self.corps_rect, self.corps_noir,
                       i18n.t("Corps noir (absorbe le rayon)", "Black body (absorbs the beam)"))
        self._checkbox(surface, self.wormhole_rect, self.wormhole,
                       i18n.t("Trou de ver ×2 (téléporte le rayon)", "Wormhole ×2 (teleports the beam)"))

        surface.blit(self.font.render(i18n.t("Taille de la grille", "Grid size"), True, theme.TEXT), (100, 344))
        for i, rect in enumerate(self.size_rects):
            selected = i == self.size_index
            bg = theme.SLOT_SELECTED if selected else theme.SLOT_BG
            pygame.draw.rect(surface, bg, rect, border_radius=8)
            pygame.draw.rect(surface, theme.BOARD_BORDER, rect, width=1, border_radius=8)
            name, w, h = self.sizes[i]
            fg = theme.BACKGROUND if selected else theme.TEXT
            n = self.font.render(i18n.size_name(name), True, fg)
            d = self.font_small.render(f"{w} × {h}", True, fg if selected else theme.TEXT_DIM)
            surface.blit(n, n.get_rect(centerx=rect.centerx, y=rect.y + 10))
            surface.blit(d, d.get_rect(centerx=rect.centerx, y=rect.y + 34))

        total = 5 + (1 if self.diamant else 0) + (1 if self.corps_noir else 0) + (2 if self.wormhole else 0)
        count = self.font_small.render(
            i18n.t(f"Total : {total} gemmes à trouver", f"Total: {total} gems to find"), True, theme.TEXT_DIM)
        surface.blit(count, count.get_rect(centerx=cx, y=486))

        # Minuteur (optionnel) : label + stepper − valeur + (éditable au clavier).
        timer_label = self.font.render(i18n.t("Minuteur", "Timer"), True, theme.TEXT)
        surface.blit(timer_label, timer_label.get_rect(centerx=cx, y=512))
        self.timer.draw(surface, self.font, i18n.t("Désactivé", "Off"))

        self._button(surface, self.start_rect, (54, 120, 90), i18n.t("Commencer", "Start"))
        self._button(surface, self.creator_rect, (54, 96, 120), i18n.t("Mode créateur", "Creator mode"))
        self._button(surface, self.load_rect, theme.SLOT_BG, i18n.t("Charger…", "Load…"))

        if self.error:
            err = self.font_small.render(self.error, True, theme.LOSE_COLOR)
            surface.blit(err, err.get_rect(centerx=cx, y=684))

    def _button(self, surface: pygame.Surface, rect: pygame.Rect, bg, text: str) -> None:
        pygame.draw.rect(surface, bg, rect, border_radius=10)
        pygame.draw.rect(surface, theme.BOARD_BORDER, rect, width=1, border_radius=10)
        label = self.font.render(text, True, theme.TEXT)
        surface.blit(label, label.get_rect(center=rect.center))

    def _draw_flag(self, surface: pygame.Surface, rect: pygame.Rect, which: str, active: bool) -> None:
        """Dessine un drapeau (France ou Royaume-Uni) cliquable.

        Le drapeau de la langue active est mis en avant (liseré jaune) ;
        l'inactif est assombri.
        """
        if which == "fr":
            self._draw_france(surface, rect)
        else:
            self._draw_uk(surface, rect)
        if not active:
            shade = pygame.Surface(rect.size, pygame.SRCALPHA)
            shade.fill((10, 12, 18, 150))
            surface.blit(shade, rect.topleft)
            pygame.draw.rect(surface, theme.BOARD_BORDER, rect, width=1)
        else:
            pygame.draw.rect(surface, theme.SLOT_SELECTED, rect.inflate(6, 6), width=3, border_radius=3)

    @staticmethod
    def _draw_france(surface: pygame.Surface, rect: pygame.Rect) -> None:
        third = rect.width / 3
        pygame.draw.rect(surface, (0, 85, 164), (rect.x, rect.y, third + 1, rect.height))
        pygame.draw.rect(surface, (240, 240, 245), (rect.x + third, rect.y, third + 1, rect.height))
        pygame.draw.rect(surface, (239, 65, 53), (rect.x + 2 * third, rect.y, third + 1, rect.height))

    @staticmethod
    def _draw_uk(surface: pygame.Surface, rect: pygame.Rect) -> None:
        blue, white, red = (1, 33, 105), (240, 240, 245), (200, 16, 46)
        x, y, w, h = rect
        cx, cy = rect.centerx, rect.centery
        tl, tr, bl, br = rect.topleft, rect.topright, rect.bottomleft, rect.bottomright
        pygame.draw.rect(surface, blue, rect)
        clip = surface.get_clip()
        surface.set_clip(rect)
        # Croix de Saint-André (diagonales) : blanc épais puis rouge fin.
        pygame.draw.line(surface, white, tl, br, max(3, h // 5))
        pygame.draw.line(surface, white, tr, bl, max(3, h // 5))
        pygame.draw.line(surface, red, tl, br, max(2, h // 11))
        pygame.draw.line(surface, red, tr, bl, max(2, h // 11))
        # Croix de Saint-Georges : bande blanche puis rouge, horizontale + verticale.
        pygame.draw.rect(surface, white, (x, cy - h // 5, w, 2 * (h // 5)))
        pygame.draw.rect(surface, white, (cx - w // 8, y, w // 4, h))
        pygame.draw.rect(surface, red, (x, cy - h // 9, w, 2 * (h // 9)))
        pygame.draw.rect(surface, red, (cx - w // 13, y, 2 * (w // 13), h))
        surface.set_clip(clip)

    def _checkbox(self, surface: pygame.Surface, rect: pygame.Rect, on: bool, text: str) -> None:
        pygame.draw.rect(surface, theme.INPUT_BG, rect, border_radius=4)
        pygame.draw.rect(surface, theme.BOARD_BORDER, rect, width=1, border_radius=4)
        if on:
            inner = rect.inflate(-8, -8)
            pygame.draw.rect(surface, theme.SLOT_SELECTED, inner, border_radius=3)
        label = self.font.render(text, True, theme.TEXT)
        surface.blit(label, (rect.right + 14, rect.y + 2))
