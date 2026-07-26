"""
weapon.py
=========
Weapon and Projectile classes.

The player never chooses a weapon: `random_weapon()` is what a weapon box
calls, and it returns one of the six weapons at random.  Every weapon dies
after KILLS_PER_WEAPON (3) kills, which is tracked by the Player.
"""

import math
import random

import pygame

from settings import WEAPONS, WEAPON_NAMES, KILLS_PER_WEAPON


# ---------------------------------------------------------------------------
# Projectile
# ---------------------------------------------------------------------------
class Projectile:
    """A single bullet, pellet, bolt, flame puff or plasma bolt."""

    def __init__(self, x, y, direction, weapon_name, stats):
        self.pos = pygame.math.Vector2(x, y)
        self.start = pygame.math.Vector2(x, y)
        self.dir = pygame.math.Vector2(direction)
        if self.dir.length_squared() == 0:          # never allow a zero vector
            self.dir = pygame.math.Vector2(1, 0)
        self.dir = self.dir.normalize()

        self.weapon_name = weapon_name
        self.speed = float(stats["speed"])
        self.damage = float(stats["damage"])
        self.max_range = float(stats["range"])
        self.pierce = bool(stats["pierce"])
        self.radius = float(stats["bullet_radius"])
        self.color = stats["color"]
        self.trail_color = stats["trail"]

        self.is_flame = (weapon_name == "Flamethrower")
        self.is_energy = (weapon_name == "Energy Blaster")
        self.is_bolt = (weapon_name == "Crossbow")

        self.alive = True
        self.age = 0.0
        self.owner = "player"     # "player" or "ally" - decides whose kill it is
        self.hit_ids = set()      # zombies already damaged (for piercing shots)
        self.angle = math.degrees(math.atan2(-self.dir.y, self.dir.x))

    # -- logic ---------------------------------------------------------
    def update(self, dt, bounds):
        """Move the projectile; kill it when it runs out of range or leaves the arena."""
        self.age += dt
        self.pos += self.dir * self.speed * dt

        travelled = self.pos.distance_to(self.start)
        if travelled >= self.max_range:
            self.alive = False

        # Flames slow down, swell and fade instead of flying forever.
        if self.is_flame:
            self.speed = max(60.0, self.speed - 520.0 * dt)
            self.radius += 26.0 * dt
            self.damage = max(2.0, self.damage - 6.0 * dt)

        if not bounds.collidepoint(int(self.pos.x), int(self.pos.y)):
            self.alive = False

    def life_ratio(self):
        """0.0 at the muzzle -> 1.0 at maximum range (used for fading flames)."""
        if self.max_range <= 0:
            return 1.0
        return min(1.0, self.pos.distance_to(self.start) / self.max_range)

    # -- drawing -------------------------------------------------------
    def draw(self, surface):
        x, y = int(self.pos.x), int(self.pos.y)
        r = max(1, int(self.radius))

        if self.is_flame:
            fade = 1.0 - self.life_ratio()
            alpha = max(0, min(255, int(220 * fade)))
            size = r * 3
            puff = pygame.Surface((size * 2, size * 2), pygame.SRCALPHA)
            pygame.draw.circle(puff, (255, 70, 30, alpha // 3), (size, size), size)
            pygame.draw.circle(puff, (255, 140, 40, alpha // 2), (size, size), int(size * 0.7))
            pygame.draw.circle(puff, (255, 226, 140, alpha), (size, size), max(1, int(size * 0.36)))
            surface.blit(puff, (x - size, y - size))
            return

        if self.is_energy:
            glow = pygame.Surface((r * 6, r * 6), pygame.SRCALPHA)
            pygame.draw.circle(glow, (90, 170, 255, 70), (r * 3, r * 3), r * 3)
            pygame.draw.circle(glow, (140, 220, 255, 120), (r * 3, r * 3), r * 2)
            surface.blit(glow, (x - r * 3, y - r * 3))
            pygame.draw.circle(surface, self.color, (x, y), r)
            pygame.draw.circle(surface, (255, 255, 255), (x, y), max(1, r // 2))
            return

        if self.is_bolt:
            tail = self.pos - self.dir * 18
            pygame.draw.line(surface, self.trail_color, (tail.x, tail.y), (x, y), 3)
            pygame.draw.circle(surface, self.color, (x, y), max(2, r - 1))
            return

        # Standard bullet: a bright dot with a short streak behind it.
        tail = self.pos - self.dir * (8 + r * 2)
        pygame.draw.line(surface, self.trail_color, (tail.x, tail.y), (x, y), max(1, r - 1))
        pygame.draw.circle(surface, self.color, (x, y), r)


# ---------------------------------------------------------------------------
# Weapon
# ---------------------------------------------------------------------------
class Weapon:
    """One randomly assigned weapon carried by the player."""

    def __init__(self, name):
        if name not in WEAPONS:                 # defensive: unknown name -> pistol
            name = "Pistol"
        self.name = name
        self.stats = dict(WEAPONS[name])        # copy so runtime edits stay local
        self.ammo = int(self.stats["ammo"])
        self.max_ammo = self.ammo
        self.cooldown = 0.0                     # seconds until the next shot is allowed
        self.kills = 0                          # kills scored with THIS weapon
        self.muzzle_flash = 0.0                 # timer for the muzzle flash effect
        self.recoil = 0.0                       # small visual kick

    # -- properties ----------------------------------------------------
    @property
    def is_auto(self):
        return bool(self.stats["auto"])

    @property
    def kills_left(self):
        """Kills remaining before this weapon disappears."""
        return max(0, KILLS_PER_WEAPON - self.kills)

    @property
    def expired(self):
        """True when the 3-kill rule is met or the ammo is gone."""
        return self.kills >= KILLS_PER_WEAPON or self.ammo <= 0

    @property
    def description(self):
        return self.stats.get("desc", "")

    # -- logic ---------------------------------------------------------
    def update(self, dt):
        self.cooldown = max(0.0, self.cooldown - dt)
        self.muzzle_flash = max(0.0, self.muzzle_flash - dt)
        self.recoil = max(0.0, self.recoil - dt * 6.0)

    def can_fire(self):
        return self.cooldown <= 0.0 and self.ammo > 0

    def fire(self, origin, aim_dir, rng=random):
        """
        Create the projectiles for one shot.

        Returns a list of Projectile objects (empty when the weapon is not
        ready to fire).  The caller adds them to the world.
        """
        if not self.can_fire():
            return []

        direction = pygame.math.Vector2(aim_dir)
        if direction.length_squared() == 0:
            direction = pygame.math.Vector2(1, 0)
        direction = direction.normalize()

        shots = []
        pellets = int(self.stats["pellets"])
        spread = float(self.stats["spread"])
        muzzle = pygame.math.Vector2(origin) + direction * 20

        for _ in range(pellets):
            angle = rng.uniform(-spread, spread) if spread > 0 else 0.0
            shot_dir = direction.rotate(angle)
            # Slight speed variation keeps shotgun pellets and flames organic.
            proj = Projectile(muzzle.x, muzzle.y, shot_dir, self.name, self.stats)
            if pellets > 1 or self.name == "Flamethrower":
                proj.speed *= rng.uniform(0.88, 1.12)
                proj.max_range *= rng.uniform(0.85, 1.1)
            shots.append(proj)

        self.ammo -= 1
        self.cooldown = float(self.stats["fire_rate"])
        self.muzzle_flash = 0.06
        self.recoil = 1.0
        return shots

    def register_kill(self):
        """Called by the game whenever this weapon kills a zombie."""
        self.kills += 1
        return self.kills >= KILLS_PER_WEAPON

    # -- drawing -------------------------------------------------------
    def draw_in_hands(self, surface, origin, aim_dir):
        """Draw a small top-down silhouette of the weapon in the player's hands."""
        direction = pygame.math.Vector2(aim_dir)
        if direction.length_squared() == 0:
            direction = pygame.math.Vector2(1, 0)
        direction = direction.normalize()
        perp = pygame.math.Vector2(-direction.y, direction.x)

        kick = self.recoil * 3.0
        base = pygame.math.Vector2(origin) + direction * (10 - kick)

        length, width, color = 22, 5, (54, 58, 62)
        if self.name == "Shotgun":
            length, width, color = 30, 7, (68, 52, 40)
        elif self.name == "Assault Rifle":
            length, width, color = 32, 6, (48, 54, 50)
        elif self.name == "Crossbow":
            length, width, color = 26, 5, (96, 74, 48)
        elif self.name == "Flamethrower":
            length, width, color = 26, 9, (120, 66, 40)
        elif self.name == "Energy Blaster":
            length, width, color = 28, 8, (58, 92, 128)

        tip = base + direction * length
        pts = [
            base + perp * width * 0.5,
            tip + perp * width * 0.5,
            tip - perp * width * 0.5,
            base - perp * width * 0.5,
        ]
        pygame.draw.polygon(surface, color, [(p.x, p.y) for p in pts])
        pygame.draw.polygon(surface, (24, 26, 28), [(p.x, p.y) for p in pts], 1)

        # Crossbow limbs.
        if self.name == "Crossbow":
            mid = base + direction * (length * 0.62)
            a = mid + perp * 11
            b = mid - perp * 11
            pygame.draw.line(surface, (72, 56, 36), (a.x, a.y), (b.x, b.y), 3)

        # Energy blaster emitter ring.
        if self.name == "Energy Blaster":
            pygame.draw.circle(surface, (150, 230, 255), (int(tip.x), int(tip.y)), 4)

        # Muzzle flash.
        if self.muzzle_flash > 0:
            flash = pygame.Surface((36, 36), pygame.SRCALPHA)
            flash_color = self.stats["color"]
            pygame.draw.circle(flash, flash_color + (170,), (18, 18), 11)
            pygame.draw.circle(flash, (255, 255, 255, 220), (18, 18), 5)
            surface.blit(flash, (tip.x - 18, tip.y - 18))


# ---------------------------------------------------------------------------
# Random assignment (the player can never pick)
# ---------------------------------------------------------------------------
def random_weapon(rng=random, avoid=None):
    """
    Return a brand-new random Weapon.

    `avoid` is an optional weapon name we try (but are not guaranteed) not to
    repeat, so consecutive boxes feel more varied.  The choice is still random
    and never controlled by the player.
    """
    names = WEAPON_NAMES
    if avoid in names and len(names) > 1 and rng.random() < 0.8:
        names = [n for n in names if n != avoid]
    return Weapon(rng.choice(names))
