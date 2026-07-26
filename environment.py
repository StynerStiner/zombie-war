"""
environment.py
==============
Builds the rainforest arena entirely from Pygame shapes — no image files
required.

* A pre-rendered ground surface (soil, grass patches, puddles, rocks, ferns,
  fallen logs and flowers).  Rendered ONCE, then blitted each frame: fast.
* Trees whose canopies are drawn on top of the action for depth.
* Drifting fog banks and a dark vignette for jungle atmosphere.
"""

import math
import random

import pygame

from settings import (SCREEN_WIDTH, SCREEN_HEIGHT, PLAY_RECT, HUD_HEIGHT,
                      JUNGLE_DARK, JUNGLE_MID, DIRT)


class Rainforest:
    """The jungle clearing the whole game takes place in."""

    def __init__(self, seed=None):
        self.rng = random.Random(seed)
        self.ground = self._build_ground()
        self.trees = self._build_trees()
        self.fog_layers = self._build_fog()
        self.vignette = self._build_vignette()
        self.fog_time = 0.0

    # ------------------------------------------------------------------
    # Static ground
    # ------------------------------------------------------------------
    def _build_ground(self):
        rng = self.rng
        surf = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT))
        surf.fill(JUNGLE_MID)

        # Broad colour variation so the floor is not a flat green slab.
        # Kept dark and subtle: the characters must stay easy to see.
        for _ in range(90):
            x = rng.randint(-60, SCREEN_WIDTH)
            y = rng.randint(HUD_HEIGHT - 40, SCREEN_HEIGHT)
            w = rng.randint(60, 170)
            h = rng.randint(34, 90)
            shade = rng.choice([JUNGLE_DARK, (20, 52, 32), (34, 74, 44), (16, 46, 30)])
            patch = pygame.Surface((w, h), pygame.SRCALPHA)
            pygame.draw.ellipse(patch, shade + (rng.randint(30, 60),), patch.get_rect())
            surf.blit(patch, (x, y))

        # A worn dirt trail winding through the clearing.
        trail_y = HUD_HEIGHT + 140
        x = -40
        while x < SCREEN_WIDTH + 60:
            wobble = math.sin(x * 0.006) * 90 + math.sin(x * 0.017) * 34
            w = rng.randint(70, 130)
            h = rng.randint(40, 70)
            blob = pygame.Surface((w, h), pygame.SRCALPHA)
            pygame.draw.ellipse(blob, DIRT + (rng.randint(60, 110),), blob.get_rect())
            surf.blit(blob, (x, trail_y + wobble + rng.randint(120, 220)))
            x += rng.randint(30, 70)

        # Small grass tufts.
        for _ in range(560):
            x = rng.randint(0, SCREEN_WIDTH)
            y = rng.randint(HUD_HEIGHT, SCREEN_HEIGHT)
            color = rng.choice([(52, 116, 64), (38, 92, 52), (66, 138, 74)])
            length = rng.randint(4, 11)
            lean = rng.randint(-4, 4)
            pygame.draw.line(surf, color, (x, y), (x + lean, y - length), 2)

        # Ferns: little fans of leaves.
        for _ in range(70):
            cx = rng.randint(10, SCREEN_WIDTH - 10)
            cy = rng.randint(HUD_HEIGHT + 20, SCREEN_HEIGHT - 10)
            leaves = rng.randint(5, 8)
            size = rng.randint(12, 26)
            base_color = rng.choice([(46, 112, 60), (34, 90, 50), (58, 130, 68)])
            for i in range(leaves):
                ang = math.pi + (i / max(1, leaves - 1)) * math.pi
                ex = cx + math.cos(ang) * size
                ey = cy + math.sin(ang) * size * 0.8
                pygame.draw.line(surf, base_color, (cx, cy), (ex, ey), 3)
                pygame.draw.circle(surf, base_color, (int(ex), int(ey)), 3)

        # Rocks with a highlight and a shadow (kept muted so they never get
        # mistaken for a zombie or a pickup).
        for _ in range(22):
            cx = rng.randint(20, SCREEN_WIDTH - 20)
            cy = rng.randint(HUD_HEIGHT + 30, SCREEN_HEIGHT - 20)
            r = rng.randint(6, 15)
            pygame.draw.ellipse(surf, (12, 26, 18), (cx - r, cy - r // 2 + 3, r * 2, r))
            pygame.draw.circle(surf, (74, 82, 76), (cx, cy), r)
            pygame.draw.circle(surf, (96, 104, 96), (cx - r // 3, cy - r // 3), max(2, r // 3))
            pygame.draw.circle(surf, (48, 56, 50), (cx, cy), r, 2)

        # Fallen mossy logs.
        for _ in range(7):
            x = rng.randint(40, SCREEN_WIDTH - 160)
            y = rng.randint(HUD_HEIGHT + 60, SCREEN_HEIGHT - 60)
            w = rng.randint(90, 170)
            h = rng.randint(16, 24)
            log = pygame.Rect(x, y, w, h)
            pygame.draw.rect(surf, (78, 58, 38), log, border_radius=h // 2)
            pygame.draw.rect(surf, (54, 40, 26), log, 2, border_radius=h // 2)
            for _ in range(rng.randint(3, 7)):     # moss
                mx = rng.randint(log.left + 6, log.right - 6)
                my = rng.randint(log.top + 2, log.bottom - 2)
                pygame.draw.circle(surf, (64, 122, 62), (mx, my), rng.randint(2, 5))

        # A few jungle flowers for a splash of colour (sparse, so they never
        # get confused with bullets or pickups).
        for _ in range(18):
            cx = rng.randint(10, SCREEN_WIDTH - 10)
            cy = rng.randint(HUD_HEIGHT + 20, SCREEN_HEIGHT - 10)
            color = rng.choice([(158, 72, 96), (168, 126, 60), (132, 84, 150)])
            for i in range(5):
                ang = i * (math.tau / 5)
                pygame.draw.circle(surf, color,
                                   (int(cx + math.cos(ang) * 3), int(cy + math.sin(ang) * 3)), 2)

        # Puddles of rainwater.
        for _ in range(12):
            cx = rng.randint(30, SCREEN_WIDTH - 30)
            cy = rng.randint(HUD_HEIGHT + 40, SCREEN_HEIGHT - 30)
            w, h = rng.randint(30, 80), rng.randint(14, 30)
            puddle = pygame.Surface((w, h), pygame.SRCALPHA)
            pygame.draw.ellipse(puddle, (90, 140, 150, 90), puddle.get_rect())
            pygame.draw.ellipse(puddle, (150, 200, 210, 70), puddle.get_rect(), 2)
            surf.blit(puddle, (cx, cy))

        return surf.convert()

    # ------------------------------------------------------------------
    # Trees (canopies drawn above the gameplay)
    # ------------------------------------------------------------------
    def _build_trees(self):
        """Trees hug the edges so they never block the middle of the fight."""
        rng = self.rng
        trees = []
        edge_spots = []

        # Left and right edges.
        y = HUD_HEIGHT + 10
        while y < SCREEN_HEIGHT + 40:
            edge_spots.append((rng.randint(-10, 46), y + rng.randint(-20, 20)))
            edge_spots.append((rng.randint(SCREEN_WIDTH - 46, SCREEN_WIDTH + 10),
                               y + rng.randint(-20, 20)))
            y += rng.randint(90, 140)

        # Top and bottom edges.
        x = -10
        while x < SCREEN_WIDTH + 40:
            edge_spots.append((x + rng.randint(-20, 20), HUD_HEIGHT + rng.randint(-6, 26)))
            edge_spots.append((x + rng.randint(-20, 20),
                               SCREEN_HEIGHT - rng.randint(-8, 26)))
            x += rng.randint(110, 170)

        for (tx, ty) in edge_spots:
            trees.append({
                "x": tx, "y": ty,
                "trunk_r": rng.randint(9, 15),
                "canopy_r": rng.randint(42, 74),
                "color": rng.choice([(30, 78, 44), (24, 66, 38), (38, 92, 50)]),
                "sway": rng.uniform(0, math.tau),
                "blobs": [(rng.uniform(-0.7, 0.7), rng.uniform(-0.7, 0.7), rng.uniform(0.45, 0.8))
                          for _ in range(rng.randint(4, 6))],
            })
        return trees

    def draw_trunks(self, surface):
        """Trunks sit underneath the characters."""
        for t in self.trees:
            x, y, r = int(t["x"]), int(t["y"]), t["trunk_r"]
            pygame.draw.ellipse(surface, (0, 0, 0, 60), (x - r, y - r // 2, r * 2, r))
            pygame.draw.circle(surface, (74, 54, 36), (x, y), r)
            pygame.draw.circle(surface, (52, 38, 26), (x, y), r, 2)
            pygame.draw.circle(surface, (94, 70, 46), (x - r // 3, y - r // 3), max(2, r // 3))

    def draw_canopies(self, surface, time_s):
        """Leafy tops drawn over everything for a layered jungle feel."""
        for t in self.trees:
            sway = math.sin(time_s * 0.7 + t["sway"]) * 5.0
            cx = t["x"] + sway
            cy = t["y"] - 6
            r = t["canopy_r"]
            canopy = pygame.Surface((r * 3, r * 3), pygame.SRCALPHA)
            mid = r * 1.5
            base = t["color"]
            pygame.draw.circle(canopy, base + (215,), (int(mid), int(mid)), r)
            for (ox, oy, scale) in t["blobs"]:
                pygame.draw.circle(
                    canopy,
                    (min(255, base[0] + 16), min(255, base[1] + 24), min(255, base[2] + 14), 215),
                    (int(mid + ox * r), int(mid + oy * r)), int(r * scale * 0.62))
            # Sun highlight on the upper-left of each canopy.
            pygame.draw.circle(canopy, (110, 176, 104, 90),
                               (int(mid - r * 0.35), int(mid - r * 0.35)), int(r * 0.42))
            surface.blit(canopy, (cx - mid, cy - mid))

    # ------------------------------------------------------------------
    # Fog + vignette
    # ------------------------------------------------------------------
    def _build_fog(self):
        """
        Two translucent fog sheets that scroll at different speeds.

        Each bank is built from concentric ellipses so it fades out softly at
        the edges - a single hard-edged ellipse looks like a stain, not fog.
        """
        rng = self.rng
        layers = []
        for layer_index, (blobs, alpha, speed) in enumerate(((9, 22, 12.0), (7, 16, 24.0))):
            w, h = SCREEN_WIDTH, SCREEN_HEIGHT
            surf = pygame.Surface((w, h), pygame.SRCALPHA)
            for _ in range(blobs):
                cx = rng.randint(0, w)
                cy = rng.randint(HUD_HEIGHT, h)
                rx = rng.randint(150, 300)
                ry = rng.randint(60, 130)
                blob = pygame.Surface((rx * 2, ry * 2), pygame.SRCALPHA)
                # Biggest+faintest ring first: pygame.draw overwrites pixels,
                # so each smaller ellipse repaints the middle a little denser.
                rings = 9
                for ring in range(rings):
                    scale = 1.0 - ring / float(rings)
                    rect = pygame.Rect(0, 0, int(rx * 2 * scale), int(ry * 2 * scale))
                    if rect.width < 2 or rect.height < 2:
                        continue
                    rect.center = (rx, ry)
                    band = max(1, int(alpha * (ring + 1) / float(rings)))
                    pygame.draw.ellipse(blob, (208, 226, 214, band), rect)
                # Draw each bank three times (left copy, normal, right copy) so
                # the sheet tiles seamlessly: without this a blob clipped by the
                # edge leaves a hard vertical seam where the loop wraps.
                for wrap in (-w, 0, w):
                    surf.blit(blob, (cx - rx + wrap, cy - ry))
            layers.append({"surf": surf.convert_alpha(), "speed": speed, "x": 0.0,
                           "index": layer_index})
        return layers

    def _build_vignette(self):
        """Darkened edges: keeps the eye on the action and the HUD readable."""
        surf = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
        steps = 46
        for i in range(steps):
            # Strongest at the very edge, fading to nothing toward the middle.
            strength = ((steps - i) / float(steps)) ** 2.2
            alpha = int(26 * strength)
            if alpha <= 0:
                continue
            rect = pygame.Rect(i * 5, i * 5,
                               SCREEN_WIDTH - i * 10, SCREEN_HEIGHT - i * 10)
            if rect.width <= 0 or rect.height <= 0:
                break
            pygame.draw.rect(surf, (0, 0, 0, alpha), rect, 6, border_radius=26)
        return surf.convert_alpha()

    # ------------------------------------------------------------------
    def update(self, dt):
        self.fog_time += dt
        for layer in self.fog_layers:
            layer["x"] = (layer["x"] + layer["speed"] * dt) % SCREEN_WIDTH

    def draw_ground(self, surface):
        surface.blit(self.ground, (0, 0))

    def draw_fog(self, surface):
        for layer in self.fog_layers:
            x = -layer["x"]
            surface.blit(layer["surf"], (x, 0))
            surface.blit(layer["surf"], (x + SCREEN_WIDTH, 0))

    def draw_vignette(self, surface):
        surface.blit(self.vignette, (0, 0))

    def draw_boundary(self, surface):
        """A subtle line showing where the walkable clearing ends."""
        pygame.draw.rect(surface, (16, 40, 26), PLAY_RECT, 2, border_radius=8)
