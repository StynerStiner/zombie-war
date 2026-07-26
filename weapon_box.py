"""
weapon_box.py
=============
The glowing supply crates scattered around the rainforest.

Touching one instantly opens it and the game assigns a RANDOM weapon — the
player never gets to choose.  Boxes bob up and down, pulse with light, and
fade away if they are ignored for too long.
"""

import math
import random

import pygame

from settings import BOX_SIZE, BOX_LIFETIME, PLAY_RECT, get_font


class WeaponBox:
    """One weapon crate sitting in the jungle."""

    def __init__(self, x, y, lifetime=BOX_LIFETIME):
        self.pos = pygame.math.Vector2(x, y)
        self.size = BOX_SIZE
        self.age = 0.0
        self.lifetime = float(lifetime)
        self.opened = False
        self.alive = True
        self.spawn_pop = 0.0        # 0 -> 1 grow-in animation
        self.bob_offset = random.uniform(0, math.tau)

    # ------------------------------------------------------------------
    @property
    def rect(self):
        """Collision rectangle (slightly generous so pickup feels good)."""
        half = self.size / 2 + 4
        return pygame.Rect(self.pos.x - half, self.pos.y - half, half * 2, half * 2)

    @property
    def time_left(self):
        return max(0.0, self.lifetime - self.age)

    @property
    def expiring(self):
        return self.time_left < 5.0

    # ------------------------------------------------------------------
    def update(self, dt):
        self.age += dt
        self.spawn_pop = min(1.0, self.spawn_pop + dt * 4.0)
        if self.age >= self.lifetime:
            self.alive = False

    def collides_with(self, player):
        """Circle/rect style overlap test against the player."""
        return self.rect.colliderect(player.rect)

    def open(self):
        """Mark the crate as taken."""
        self.opened = True
        self.alive = False

    # ------------------------------------------------------------------
    def draw(self, surface):
        pulse = (math.sin(self.age * 4.0 + self.bob_offset) + 1) * 0.5
        bob = math.sin(self.age * 2.4 + self.bob_offset) * 3.0
        scale = 0.4 + 0.6 * self.spawn_pop          # pop-in when it appears

        # Blink faster right before the crate disappears.
        if self.expiring and int(self.age * 8) % 2 == 0:
            pulse = 0.15

        cx = self.pos.x
        cy = self.pos.y + bob
        size = int(self.size * scale)
        half = size / 2

        # --- ground shadow ---------------------------------------------
        shadow = pygame.Surface((size + 10, (size // 2) + 6), pygame.SRCALPHA)
        pygame.draw.ellipse(shadow, (0, 0, 0, 90), shadow.get_rect())
        surface.blit(shadow, (cx - (size + 10) / 2, self.pos.y + half - 4))

        # --- glow --------------------------------------------------------
        from effects import radial_glow
        glow_r = int(size * 1.5 + pulse * 10)
        glow = radial_glow(glow_r, (255, 220, 110), 80 + int(50 * pulse))
        surface.blit(glow, (cx - glow_r, cy - glow_r))

        # --- crate body ----------------------------------------------------
        body = pygame.Rect(cx - half, cy - half, size, size)
        pygame.draw.rect(surface, (126, 92, 52), body, border_radius=4)
        pygame.draw.rect(surface, (166, 126, 70), body.inflate(-6, -6), border_radius=3)
        pygame.draw.rect(surface, (72, 52, 30), body, 2, border_radius=4)

        # Metal banding.
        pygame.draw.line(surface, (90, 96, 100), (body.left + 2, cy), (body.right - 2, cy), 3)
        pygame.draw.line(surface, (90, 96, 100), (cx, body.top + 2), (cx, body.bottom - 2), 3)

        # --- ammo symbol on the lid -----------------------------------------
        symbol_color = (255, 226, min(255, 120 + int(80 * pulse)))
        pygame.draw.circle(surface, (250, 224, 130), (int(cx), int(cy)), max(3, size // 6))
        pygame.draw.circle(surface, (120, 84, 40), (int(cx), int(cy)), max(3, size // 6), 1)

        # --- sparkles -------------------------------------------------------
        for i in range(3):
            ang = self.age * 2.2 + i * (math.tau / 3)
            sx = cx + math.cos(ang) * (half + 9)
            sy = cy + math.sin(ang) * (half + 9) * 0.7
            r = 2 + int(pulse * 2)
            pygame.draw.circle(surface, symbol_color, (int(sx), int(sy)), r)

        # --- "?" hint so players know it is a mystery weapon -----------------
        font = get_font(15, bold=True)
        hint = font.render("?", True, (255, 246, 200))
        surface.blit(hint, (cx - hint.get_width() / 2, cy - half - 20))


# ---------------------------------------------------------------------------
def random_box_position(player_pos=None, rng=random, min_player_distance=90):
    """
    Pick a random spot in the rainforest for a new crate, never right on top
    of the player (that would feel like a free gift instead of a search).
    """
    margin = BOX_SIZE
    for _ in range(24):
        x = rng.randint(PLAY_RECT.left + margin, PLAY_RECT.right - margin)
        y = rng.randint(PLAY_RECT.top + margin, PLAY_RECT.bottom - margin)
        if player_pos is None:
            return x, y
        if pygame.math.Vector2(x, y).distance_to(player_pos) >= min_player_distance:
            return x, y
    # Fallback after too many tries: anywhere is better than nowhere.
    return (rng.randint(PLAY_RECT.left + margin, PLAY_RECT.right - margin),
            rng.randint(PLAY_RECT.top + margin, PLAY_RECT.bottom - margin))
