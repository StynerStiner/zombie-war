"""
effects.py
==========
All the small visual flourishes, drawn with plain Pygame shapes:

* Particle     - dust when a zombie lands, sparks when one is hit, embers
* FloatingText - the score number that drifts upward after a kill
* ShockRing    - expanding ring for landings, deaths and pickups
* EffectManager- owns the lists and updates/draws them each frame

Nothing here needs image files, so the game always looks the same on any
machine.
"""

import math
import random

import pygame

from settings import get_font


# ---------------------------------------------------------------------------
# Soft radial glow (shared by special zombies, weapon boxes and pickups)
# ---------------------------------------------------------------------------
_GLOW_CACHE = {}


def radial_glow(radius, color, max_alpha=80, rings=9):
    """
    A soft circular glow that fades out toward its edge.

    A single translucent circle looks like a hard bubble, so the glow is built
    from concentric circles instead.  Results are cached (and the alpha is
    quantised) because these are rebuilt every frame by every glowing object.
    """
    r = max(2, int(radius))
    alpha = max(8, min(255, int(round(max_alpha / 8.0) * 8)))
    key = (r, tuple(color), alpha, rings)
    surf = _GLOW_CACHE.get(key)
    if surf is not None:
        return surf

    surf = pygame.Surface((r * 2, r * 2), pygame.SRCALPHA)
    # pygame.draw REPLACES pixels rather than blending them, so the bands are
    # painted biggest-and-faintest first: each smaller circle overwrites the
    # middle with a stronger alpha, producing a real radial falloff.
    for i in range(rings):
        rr = int(r * (1.0 - i / float(rings)))
        if rr < 1:
            continue
        band_alpha = max(1, int(alpha * (i + 1) / float(rings)))
        pygame.draw.circle(surf, tuple(color) + (band_alpha,), (r, r), rr)
    if len(_GLOW_CACHE) < 400:          # simple bound so the cache cannot grow forever
        _GLOW_CACHE[key] = surf
    return surf


# ---------------------------------------------------------------------------
class Particle:
    """A little coloured dot with gravity, drag and a fade-out."""

    __slots__ = ("pos", "vel", "life", "max_life", "radius", "color",
                 "gravity", "drag", "shrink", "glow")

    def __init__(self, x, y, vel, life, radius, color,
                 gravity=0.0, drag=1.6, shrink=True, glow=False):
        self.pos = pygame.math.Vector2(x, y)
        self.vel = pygame.math.Vector2(vel)
        self.life = float(life)
        self.max_life = float(life)
        self.radius = float(radius)
        self.color = color
        self.gravity = float(gravity)
        self.drag = float(drag)
        self.shrink = shrink
        self.glow = glow

    @property
    def alive(self):
        return self.life > 0

    def update(self, dt):
        self.life -= dt
        self.vel.y += self.gravity * dt
        # Simple exponential-ish drag so particles settle instead of flying off.
        damp = max(0.0, 1.0 - self.drag * dt)
        self.vel *= damp
        self.pos += self.vel * dt

    def draw(self, surface):
        if self.life <= 0:
            return
        t = max(0.0, min(1.0, self.life / self.max_life))
        radius = self.radius * (t if self.shrink else 1.0)
        r = int(radius)
        if r < 1:
            return
        alpha = int(235 * t)
        size = r * (3 if self.glow else 1) * 2 + 2
        surf = pygame.Surface((size, size), pygame.SRCALPHA)
        c = size // 2
        if self.glow:
            pygame.draw.circle(surf, self.color + (max(0, alpha // 4),), (c, c), r * 3)
            pygame.draw.circle(surf, self.color + (max(0, alpha // 2),), (c, c), r * 2)
        pygame.draw.circle(surf, self.color + (alpha,), (c, c), r)
        surface.blit(surf, (self.pos.x - c, self.pos.y - c))


# ---------------------------------------------------------------------------
class FloatingText:
    """Score numbers and messages that drift upward and fade out."""

    def __init__(self, x, y, text, color, size=22, rise=54.0, life=1.1, bold=True):
        self.pos = pygame.math.Vector2(x, y)
        self.text = str(text)
        self.color = color
        self.size = size
        self.rise = rise
        self.life = float(life)
        self.max_life = float(life)
        self.font = get_font(size, bold=bold)
        self.surf = self.font.render(self.text, True, color)
        self.outline = self.font.render(self.text, True, (10, 16, 12))

    @property
    def alive(self):
        return self.life > 0

    def update(self, dt):
        self.life -= dt
        self.pos.y -= self.rise * dt
        self.rise *= max(0.0, 1.0 - 1.2 * dt)       # slow down as it rises

    def draw(self, surface):
        if self.life <= 0:
            return
        t = max(0.0, min(1.0, self.life / self.max_life))
        alpha = int(255 * min(1.0, t * 1.6))        # hold, then fade
        x = self.pos.x - self.surf.get_width() // 2
        y = self.pos.y - self.surf.get_height() // 2

        outline = self.outline.copy()
        outline.set_alpha(alpha)
        for dx, dy in ((-2, 0), (2, 0), (0, -2), (0, 2)):
            surface.blit(outline, (x + dx, y + dy))

        body = self.surf.copy()
        body.set_alpha(alpha)
        surface.blit(body, (x, y))


# ---------------------------------------------------------------------------
class ShockRing:
    """An expanding circle outline (landing thump, death pop, box opening)."""

    def __init__(self, x, y, color, max_radius=60, life=0.45, width=3, squash=1.0):
        self.pos = pygame.math.Vector2(x, y)
        self.color = color
        self.max_radius = float(max_radius)
        self.life = float(life)
        self.max_life = float(life)
        self.width = int(width)
        self.squash = float(squash)     # <1.0 gives a flat "ground" ring

    @property
    def alive(self):
        return self.life > 0

    def update(self, dt):
        self.life -= dt

    def draw(self, surface):
        if self.life <= 0:
            return
        t = 1.0 - max(0.0, self.life / self.max_life)     # 0 -> 1 over the life
        radius = max(1, int(self.max_radius * t))
        alpha = max(0, int(200 * (1.0 - t)))
        h = max(1, int(radius * self.squash))
        size_w, size_h = radius * 2 + 4, h * 2 + 4
        surf = pygame.Surface((size_w, size_h), pygame.SRCALPHA)
        rect = pygame.Rect(2, 2, radius * 2, h * 2)
        try:
            pygame.draw.ellipse(surf, self.color + (alpha,), rect, self.width)
        except ValueError:
            return
        surface.blit(surf, (self.pos.x - size_w / 2, self.pos.y - size_h / 2))


# ---------------------------------------------------------------------------
class EffectManager:
    """Holds every active effect and keeps the lists tidy."""

    MAX_PARTICLES = 420        # hard cap so the game never chugs

    def __init__(self):
        self.particles = []
        self.texts = []
        self.rings = []

    # -- bookkeeping ---------------------------------------------------
    def clear(self):
        self.particles.clear()
        self.texts.clear()
        self.rings.clear()

    def update(self, dt):
        for group in (self.particles, self.texts, self.rings):
            for item in group:
                item.update(dt)
            group[:] = [i for i in group if i.alive]

    def draw(self, surface):
        for ring in self.rings:
            ring.draw(surface)
        for particle in self.particles:
            particle.draw(surface)

    def draw_texts(self, surface):
        """Text is drawn last so it always sits on top of the action."""
        for text in self.texts:
            text.draw(surface)

    def _add_particle(self, particle):
        if len(self.particles) < self.MAX_PARTICLES:
            self.particles.append(particle)

    # -- effect recipes -------------------------------------------------
    def dust_burst(self, x, y, amount=18, color=(150, 138, 108), power=170):
        """Ring of dust kicked up when a zombie slams into the ground."""
        for _ in range(amount):
            angle = random.uniform(0, math.tau)
            speed = random.uniform(power * 0.35, power)
            vel = (math.cos(angle) * speed, math.sin(angle) * speed * 0.45)
            self._add_particle(Particle(
                x, y + random.uniform(-3, 5), vel,
                life=random.uniform(0.35, 0.75),
                radius=random.uniform(2.5, 6.0),
                color=color, gravity=90, drag=2.6))
        self.rings.append(ShockRing(x, y, (210, 200, 170), max_radius=54,
                                    life=0.45, width=3, squash=0.42))

    def hit_spark(self, x, y, color=(200, 255, 210), amount=8, power=190):
        """Pale green spark when a zombie takes damage (arcade, not gory)."""
        for _ in range(amount):
            angle = random.uniform(0, math.tau)
            speed = random.uniform(power * 0.3, power)
            self._add_particle(Particle(
                x, y, (math.cos(angle) * speed, math.sin(angle) * speed),
                life=random.uniform(0.18, 0.36),
                radius=random.uniform(1.5, 3.5),
                color=color, drag=4.0))

    def death_burst(self, x, y, color, amount=22, special=False):
        """Zombie pops into a puff of coloured shapes."""
        for _ in range(amount):
            angle = random.uniform(0, math.tau)
            speed = random.uniform(70, 260)
            self._add_particle(Particle(
                x, y, (math.cos(angle) * speed, math.sin(angle) * speed),
                life=random.uniform(0.35, 0.8),
                radius=random.uniform(2.0, 5.5),
                color=color, gravity=140, drag=2.0, glow=special))
        self.rings.append(ShockRing(x, y, color, max_radius=70 if special else 46,
                                    life=0.5, width=3))
        if special:
            self.rings.append(ShockRing(x, y, (255, 255, 255), max_radius=110,
                                        life=0.65, width=2))

    def muzzle_smoke(self, x, y, direction):
        vel = (direction.x * random.uniform(20, 60), direction.y * random.uniform(20, 60))
        self._add_particle(Particle(x, y, vel, life=0.3, radius=3.5,
                                    color=(190, 190, 180), drag=2.5))

    def impact(self, x, y, color):
        for _ in range(5):
            angle = random.uniform(0, math.tau)
            speed = random.uniform(40, 130)
            self._add_particle(Particle(
                x, y, (math.cos(angle) * speed, math.sin(angle) * speed),
                life=random.uniform(0.12, 0.28), radius=random.uniform(1.5, 3.0),
                color=color, drag=5.0))

    def pickup_burst(self, x, y, color=(255, 226, 130)):
        for _ in range(20):
            angle = random.uniform(0, math.tau)
            speed = random.uniform(60, 220)
            self._add_particle(Particle(
                x, y, (math.cos(angle) * speed, math.sin(angle) * speed),
                life=random.uniform(0.3, 0.7), radius=random.uniform(2, 4),
                color=color, gravity=60, drag=2.2, glow=True))
        self.rings.append(ShockRing(x, y, color, max_radius=80, life=0.5, width=3))

    def player_hurt(self, x, y):
        for _ in range(10):
            angle = random.uniform(0, math.tau)
            speed = random.uniform(60, 180)
            self._add_particle(Particle(
                x, y, (math.cos(angle) * speed, math.sin(angle) * speed),
                life=random.uniform(0.2, 0.4), radius=random.uniform(2, 4),
                color=(255, 120, 110), drag=3.5))

    def floating_score(self, x, y, points, color=(255, 236, 150), big=False):
        self.texts.append(FloatingText(
            x, y, "+{}".format(points), color,
            size=30 if big else 22, rise=70 if big else 54,
            life=1.3 if big else 1.0))

    def message(self, x, y, text, color, size=24, life=1.4):
        self.texts.append(FloatingText(x, y, text, color, size=size, rise=26, life=life))
