"""
ally.py
=======
Your teammate: a friendly survivor who follows you through the rainforest and
shoots zombies on his own.

Behaviour
---------
* Keeps a comfortable distance behind you - close enough to help, far enough
  not to stand on top of you.
* Automatically fires at the nearest landed zombie inside his range.
* Has his own health.  Zombies that bump into him hurt him, and when he runs
  out he is DOWNED for a while, then gets back up next to you.
* His kills score points for the team, but they do NOT use up your weapon's
  three kills - that rule is about the weapon in *your* hands.
"""

import math

import pygame

from settings import PLAY_RECT, get_font
from weapon import Projectile

# How he fights.  Deliberately weaker than any weapon the player can find, so
# he is a helper and never does the whole job for you.
ALLY_STATS = {
    "damage": 14,
    "fire_rate": 0.62,          # seconds between shots
    "speed": 720,               # projectile speed
    "range": 430,
    "bullet_radius": 3,
    "color": (170, 255, 200),
    "trail": (90, 200, 150),
    "pierce": False,
}

FOLLOW_DISTANCE = 104           # preferred distance from the player
TOO_CLOSE = 62
ALLY_SPEED = 250
ALLY_MAX_HEALTH = 90
ALLY_REVIVE_SECONDS = 12.0
REGEN_DELAY = 6.0               # seconds without damage before he heals
REGEN_RATE = 4.0                # health per second


class Teammate:
    """A friendly AI survivor fighting alongside the player."""

    def __init__(self, x, y, name="BUDDY"):
        self.pos = pygame.math.Vector2(x, y)
        self.name = name
        self.radius = 14
        self.max_health = ALLY_MAX_HEALTH
        self.health = ALLY_MAX_HEALTH
        self.aim = pygame.math.Vector2(1, 0)
        self.cooldown = 0.0
        self.walk_phase = 0.0
        self.moving = False
        self.hit_flash = 0.0
        self.since_damage = 0.0
        self.downed = False
        self.revive_timer = 0.0
        self.kills = 0

    # ------------------------------------------------------------------
    @property
    def health_ratio(self):
        return max(0.0, min(1.0, self.health / float(self.max_health)))

    @property
    def alive(self):
        return not self.downed

    # ------------------------------------------------------------------
    # Update
    # ------------------------------------------------------------------
    def update(self, dt, player, zombies, projectiles, effects, audio, find_target):
        """
        Follow the player, shoot at zombies, and handle being downed.

        `find_target` is a callable(origin, max_range) -> zombie or None, so the
        teammate uses exactly the same targeting logic as the touch auto-aim.
        """
        self.hit_flash = max(0.0, self.hit_flash - dt * 3.0)

        # ---- downed: wait, then get back up beside the player ----------
        if self.downed:
            self.revive_timer -= dt
            if self.revive_timer <= 0:
                self.downed = False
                self.health = self.max_health
                self.since_damage = 0.0
                # Reappear just behind the player.
                offset = pygame.math.Vector2(-player.aim.x, -player.aim.y) * 46
                self.pos = pygame.math.Vector2(player.pos) + offset
                self._clamp()
                effects.pickup_burst(self.pos.x, self.pos.y, (150, 255, 190))
                effects.message(self.pos.x, self.pos.y - 40, "BUDDY IS BACK!",
                                (150, 255, 190), size=18, life=1.6)
                audio.play("box", 0.5)
            return

        self.cooldown = max(0.0, self.cooldown - dt)
        self.since_damage += dt

        # ---- slow self-healing when left alone -------------------------
        if self.since_damage > REGEN_DELAY and self.health < self.max_health:
            self.health = min(self.max_health, self.health + REGEN_RATE * dt)

        # ---- movement: hold station near the player --------------------
        to_player = player.pos - self.pos
        distance = to_player.length()
        move = pygame.math.Vector2(0, 0)
        if distance > FOLLOW_DISTANCE:
            move = to_player.normalize()
        elif distance < TOO_CLOSE and distance > 0.001:
            move = -to_player.normalize()          # give the player some room

        # Advance on a zombie that is just outside his firing range - bullet
        # knock-back shoves targets away, and without this he would stand
        # still watching a wounded zombie drift out of reach.
        target_in_range = find_target(self.pos, ALLY_STATS["range"])
        if target_in_range is None and distance < 230:
            hunt = find_target(self.pos, ALLY_STATS["range"] + 320)
            if hunt is not None:
                toward = pygame.math.Vector2(hunt.pos.x, hunt.draw_y) - self.pos
                if toward.length_squared() > 0:
                    move += toward.normalize() * 0.85

        # Back away from a zombie that is right on top of him.
        threat = find_target(self.pos, 70)
        if threat is not None:
            away = self.pos - pygame.math.Vector2(threat.pos.x, threat.draw_y)
            if away.length_squared() > 0:
                move += away.normalize() * 1.2

        self.moving = move.length_squared() > 0
        if self.moving:
            if move.length() > 1:
                move = move.normalize()
            self.pos += move * ALLY_SPEED * dt
            self.walk_phase += dt * 10.0
            self._clamp()

        # ---- shooting ---------------------------------------------------
        target = find_target(self.pos, ALLY_STATS["range"])
        if target is not None:
            direction = pygame.math.Vector2(target.pos.x, target.draw_y) - self.pos
            if direction.length_squared() > 0:
                self.aim = direction.normalize()
            if self.cooldown <= 0:
                self.cooldown = ALLY_STATS["fire_rate"]
                muzzle = self.pos + self.aim * 18
                shot = Projectile(muzzle.x, muzzle.y, self.aim, "Ally Rifle", ALLY_STATS)
                shot.owner = "ally"
                projectiles.append(shot)
                audio.play("rifle", 0.35)
        elif self.moving:
            self.aim = move.normalize() if move.length_squared() > 0 else self.aim

    def _clamp(self):
        self.pos.x = max(PLAY_RECT.left + self.radius,
                         min(PLAY_RECT.right - self.radius, self.pos.x))
        self.pos.y = max(PLAY_RECT.top + self.radius,
                         min(PLAY_RECT.bottom - self.radius, self.pos.y))

    # ------------------------------------------------------------------
    def take_damage(self, amount, effects, audio):
        """Returns True if this hit downed him."""
        if self.downed:
            return False
        self.health -= amount
        self.hit_flash = 1.0
        self.since_damage = 0.0
        if self.health <= 0:
            self.health = 0
            self.downed = True
            self.revive_timer = ALLY_REVIVE_SECONDS
            effects.death_burst(self.pos.x, self.pos.y, (120, 200, 150), amount=18)
            effects.message(self.pos.x, self.pos.y - 40, "BUDDY IS DOWN!",
                            (255, 150, 120), size=18, life=2.0)
            audio.play("expire", 0.5)
            return True
        return False

    # ------------------------------------------------------------------
    # Drawing
    # ------------------------------------------------------------------
    def draw(self, surface):
        x, y = self.pos.x, self.pos.y

        # ---- downed: a slumped marker with a countdown -----------------
        if self.downed:
            pygame.draw.ellipse(surface, (26, 40, 30),
                                (x - 20, y - 8, 40, 18))
            pygame.draw.circle(surface, (96, 132, 108), (int(x), int(y)), 11)
            pygame.draw.circle(surface, (40, 60, 48), (int(x), int(y)), 11, 2)
            font = get_font(13, bold=True)
            text = "BUDDY {}s".format(int(self.revive_timer) + 1)
            img = font.render(text, True, (200, 220, 205))
            shadow = font.render(text, True, (8, 16, 12))
            rect = img.get_rect(center=(int(x), int(y - 26)))
            surface.blit(shadow, (rect.x + 1, rect.y + 1))
            surface.blit(img, rect)
            return

        bob = math.sin(self.walk_phase) * (2.0 if self.moving else 0.5)
        body_y = y + bob
        perp = pygame.math.Vector2(-self.aim.y, self.aim.x)

        # ---- shadow ------------------------------------------------------
        shadow = pygame.Surface((self.radius * 3, self.radius * 2), pygame.SRCALPHA)
        pygame.draw.ellipse(shadow, (0, 0, 0, 80), shadow.get_rect())
        surface.blit(shadow, (x - self.radius * 1.5, y + self.radius * 0.35))

        # ---- boots -------------------------------------------------------
        step = math.sin(self.walk_phase)
        for side in (-1, 1):
            foot = pygame.math.Vector2(x, y + 5) + perp * (side * 6)
            if self.moving:
                foot += self.aim * (step * side * 4)
            pygame.draw.circle(surface, (40, 38, 32), (int(foot.x), int(foot.y)), 4)

        # ---- body: green jacket (distinct from the player's blue) --------
        body_color = (74, 150, 96) if self.hit_flash <= 0 else (230, 140, 120)
        pygame.draw.circle(surface, body_color, (int(x), int(body_y)), self.radius)
        pygame.draw.circle(surface, (22, 52, 34), (int(x), int(body_y)), self.radius, 2)

        # ---- arms + rifle -------------------------------------------------
        hands = pygame.math.Vector2(x, body_y) + self.aim * 14
        for side in (-1, 1):
            shoulder = pygame.math.Vector2(x, body_y) + perp * (side * 9)
            pygame.draw.line(surface, (226, 190, 148), shoulder, hands, 4)
        tip = pygame.math.Vector2(x, body_y) + self.aim * 26
        pygame.draw.line(surface, (52, 58, 54), hands, tip, 5)

        # ---- head + green cap ---------------------------------------------
        head = pygame.math.Vector2(x, body_y) + self.aim * 1.5
        hx, hy = int(head.x), int(head.y)
        chin = head + self.aim * 5
        pygame.draw.circle(surface, (232, 194, 152), (int(chin.x), int(chin.y)), 4)
        pygame.draw.circle(surface, (46, 92, 58), (hx, hy), 8)
        pygame.draw.circle(surface, (150, 230, 170), (hx, hy), 8, 2)

        # ---- name tag -------------------------------------------------------
        font = get_font(12, bold=True)
        img = font.render(self.name, True, (24, 46, 32))
        pad_w, pad_h = img.get_width() + 10, img.get_height() + 4
        tag_y = body_y - self.radius - 30
        tag = pygame.Surface((pad_w, pad_h), pygame.SRCALPHA)
        pygame.draw.rect(tag, (150, 230, 170, 230), tag.get_rect(), border_radius=5)
        pygame.draw.rect(tag, (28, 62, 40, 255), tag.get_rect(), 1, border_radius=5)
        tag.blit(img, (5, 2))
        surface.blit(tag, (x - pad_w / 2, tag_y))

        # ---- health bar -------------------------------------------------------
        if self.health_ratio < 1.0:
            bw = 34
            bx, by = int(x - bw / 2), int(body_y + self.radius + 8)
            pygame.draw.rect(surface, (16, 24, 18), (bx - 1, by - 1, bw + 2, 6))
            pygame.draw.rect(surface, (150, 230, 170),
                             (bx, by, int(bw * self.health_ratio), 4))
