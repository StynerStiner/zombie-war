"""
player.py
=========
The survivor the user controls.

Top-down character drawn from simple shapes: shadow, boots, body, backpack,
arms that point at the mouse, head and a jungle hat.  Movement is fully
delta-time based so the speed is identical on a 30 FPS or a 240 FPS machine.
"""

import math

import pygame

from settings import (PLAYER_MAX_HEALTH, PLAYER_SPEED, PLAYER_RADIUS,
                      PLAYER_HURT_IFRAMES, PLAY_RECT, get_font)


class Player:
    """The player character: movement, health, and the currently held weapon."""

    def __init__(self, x, y):
        self.pos = pygame.math.Vector2(x, y)
        self.radius = PLAYER_RADIUS
        self.speed = PLAYER_SPEED
        self.max_health = PLAYER_MAX_HEALTH
        self.health = PLAYER_MAX_HEALTH

        self.weapon = None              # None = unarmed, must find a weapon box
        self.total_kills = 0

        self.aim = pygame.math.Vector2(1, 0)    # unit vector toward the mouse
        self.vel = pygame.math.Vector2(0, 0)
        self.walk_phase = 0.0           # drives the little walking bob
        self.moving = False

        self.hurt_timer = 0.0           # invulnerability countdown
        self.flash_timer = 0.0          # red flash when damaged
        self.alive = True

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------
    @property
    def rect(self):
        return pygame.Rect(self.pos.x - self.radius, self.pos.y - self.radius,
                           self.radius * 2, self.radius * 2)

    @property
    def has_weapon(self):
        return self.weapon is not None

    @property
    def weapon_name(self):
        return self.weapon.name if self.weapon else "None"

    @property
    def kills_left(self):
        """Kills remaining before the current weapon disappears."""
        return self.weapon.kills_left if self.weapon else 0

    @property
    def health_ratio(self):
        return max(0.0, min(1.0, self.health / float(self.max_health)))

    # ------------------------------------------------------------------
    # Update
    # ------------------------------------------------------------------
    def update(self, dt, keys, mouse_pos, move_override=None):
        """
        Move with WASD / arrows and aim at the mouse.

        `move_override` is the touch-screen thumb-stick vector (length 0..1).
        When it is supplied it replaces the keyboard, and its length controls
        the walking speed so a small thumb movement means a gentle step.
        """
        move = pygame.math.Vector2(0, 0)
        if keys[pygame.K_a] or keys[pygame.K_LEFT]:
            move.x -= 1
        if keys[pygame.K_d] or keys[pygame.K_RIGHT]:
            move.x += 1
        if keys[pygame.K_w] or keys[pygame.K_UP]:
            move.y -= 1
        if keys[pygame.K_s] or keys[pygame.K_DOWN]:
            move.y += 1

        if move_override is not None and move_override.length_squared() > 0:
            move = pygame.math.Vector2(move_override)
            if move.length() > 1.0:
                move.scale_to_length(1.0)

        self.moving = move.length_squared() > 0
        if self.moving:
            if move.length() > 1.0:
                move = move.normalize()         # diagonals are not faster
            self.pos += move * self.speed * dt
            self.walk_phase += dt * 11.0
        else:
            # Ease the walk animation back to a standing pose.
            self.walk_phase += dt * 2.0
        self.vel = move * self.speed

        # Keep the player inside the rainforest clearing.
        self.pos.x = max(PLAY_RECT.left + self.radius,
                         min(PLAY_RECT.right - self.radius, self.pos.x))
        self.pos.y = max(PLAY_RECT.top + self.radius,
                         min(PLAY_RECT.bottom - self.radius, self.pos.y))

        # Aim toward the mouse cursor.
        aim = pygame.math.Vector2(mouse_pos) - self.pos
        if aim.length_squared() > 4:
            self.aim = aim.normalize()

        # Timers.
        self.hurt_timer = max(0.0, self.hurt_timer - dt)
        self.flash_timer = max(0.0, self.flash_timer - dt)
        if self.weapon:
            self.weapon.update(dt)

    # ------------------------------------------------------------------
    # Combat
    # ------------------------------------------------------------------
    def shoot(self, projectiles):
        """
        Try to fire.  Returns True if a shot actually went off so the game can
        play a sound and add a muzzle puff.
        """
        if not self.weapon:
            return False
        shots = self.weapon.fire(self.pos, self.aim)
        if not shots:
            return False
        projectiles.extend(shots)
        return True

    def take_damage(self, amount, source_pos=None):
        """
        Lose health.  Returns True when the hit actually landed (the player is
        briefly invulnerable after each hit so a crowd cannot instantly kill).
        """
        if self.hurt_timer > 0 or not self.alive:
            return False
        self.health -= amount
        self.hurt_timer = PLAYER_HURT_IFRAMES
        self.flash_timer = 0.28

        # Small knock-back away from the attacker.
        if source_pos is not None:
            away = self.pos - pygame.math.Vector2(source_pos)
            if away.length_squared() > 0:
                self.pos += away.normalize() * 14
                self.pos.x = max(PLAY_RECT.left + self.radius,
                                 min(PLAY_RECT.right - self.radius, self.pos.x))
                self.pos.y = max(PLAY_RECT.top + self.radius,
                                 min(PLAY_RECT.bottom - self.radius, self.pos.y))

        if self.health <= 0:
            self.health = 0
            self.alive = False
        return True

    def give_weapon(self, weapon):
        """Equip a randomly chosen weapon; the 3-kill counter restarts."""
        self.weapon = weapon
        self.weapon.kills = 0
        return weapon

    def drop_weapon(self):
        """The weapon expires (3 kills reached, or ammo gone)."""
        self.weapon = None

    def heal(self, amount):
        self.health = min(self.max_health, self.health + amount)

    # ------------------------------------------------------------------
    # Drawing
    # ------------------------------------------------------------------
    def draw(self, surface):
        x, y = self.pos.x, self.pos.y
        bob = math.sin(self.walk_phase) * (2.4 if self.moving else 0.6)
        step = math.sin(self.walk_phase)

        # --- "this is you" spotlight ring on the ground -------------------
        # Drawn first, under everything, so the player is instantly findable
        # in a crowd of zombies.
        from effects import radial_glow
        pulse = (math.sin(self.walk_phase * 0.7) + 1) * 0.5
        halo_r = int(self.radius * 2.4)
        surface.blit(radial_glow(halo_r, (120, 200, 255), 60 + int(24 * pulse)),
                     (x - halo_r, y - halo_r))
        ring_r = int(self.radius + 9)
        ring = pygame.Surface((ring_r * 2 + 4, ring_r * 2 + 4), pygame.SRCALPHA)
        pygame.draw.circle(ring, (150, 225, 255, 190 + int(50 * pulse)),
                           (ring_r + 2, ring_r + 2), ring_r, 3)
        surface.blit(ring, (x - ring_r - 2, y - ring_r - 2))

        # --- shadow -----------------------------------------------------
        shadow = pygame.Surface((self.radius * 3, self.radius * 2), pygame.SRCALPHA)
        pygame.draw.ellipse(shadow, (0, 0, 0, 90), shadow.get_rect())
        surface.blit(shadow, (x - self.radius * 1.5, y + self.radius * 0.35))

        perp = pygame.math.Vector2(-self.aim.y, self.aim.x)

        # --- boots (they swing while walking) ---------------------------
        for side in (-1, 1):
            foot = pygame.math.Vector2(x, y + 6 + bob * 0.3)
            foot += perp * (side * 7)
            foot += self.aim * (step * side * 5 if self.moving else 0)
            pygame.draw.circle(surface, (44, 40, 34), (int(foot.x), int(foot.y)), 5)

        body_y = y + bob

        centre = pygame.math.Vector2(x, body_y)

        # --- backpack (sits behind the shoulders) -------------------------
        pack = centre - self.aim * 10
        pygame.draw.circle(surface, (84, 60, 38), (int(pack.x), int(pack.y)), 9)
        pygame.draw.circle(surface, (40, 28, 18), (int(pack.x), int(pack.y)), 9, 2)

        # --- torso ---------------------------------------------------------
        # Blue jacket + orange cap: complementary to the green jungle, so the
        # player never disappears into the background or among the zombies.
        body_color = (62, 98, 152)
        if self.flash_timer > 0:                 # flash red when hurt
            body_color = (232, 96, 84)
        elif self.hurt_timer > 0 and int(self.hurt_timer * 22) % 2 == 0:
            body_color = (150, 190, 235)
        pygame.draw.circle(surface, body_color, (int(x), int(body_y)), self.radius)
        pygame.draw.circle(surface, (18, 30, 52), (int(x), int(body_y)), self.radius, 2)

        # Shoulders: slightly darker discs that widen the silhouette.
        shoulder_l = centre + perp * 11
        shoulder_r = centre - perp * 11
        for shoulder in (shoulder_l, shoulder_r):
            pygame.draw.circle(surface, (46, 76, 122),
                               (int(shoulder.x), int(shoulder.y)), 6)
            pygame.draw.circle(surface, (18, 30, 52),
                               (int(shoulder.x), int(shoulder.y)), 6, 1)

        # Khaki chest strap across the jacket.
        strap_a = centre + perp * self.radius * 0.85
        strap_b = centre - perp * self.radius * 0.85
        pygame.draw.line(surface, (176, 148, 96), strap_a, strap_b, 3)

        # --- arms ----------------------------------------------------------
        hands = centre + self.aim * 15
        arm_color = (232, 196, 152)
        pygame.draw.line(surface, arm_color, shoulder_l, hands, 5)
        pygame.draw.line(surface, arm_color, shoulder_r, hands, 5)

        # --- weapon --------------------------------------------------------
        if self.weapon:
            self.weapon.draw_in_hands(surface, (x, body_y), self.aim)

        # --- head + orange cap (seen from above) ----------------------------
        head = centre + self.aim * 1.5
        hx, hy = int(head.x), int(head.y)
        pygame.draw.circle(surface, (236, 200, 158), (hx, hy), 9)    # head / face
        pygame.draw.circle(surface, (120, 82, 48), (hx, hy), 9, 2)   # jaw outline
        # Cap brim: a wedge pointing the way the player is looking.
        brim = [head + self.aim * 12 + perp * 5,
                head + self.aim * 12 - perp * 5,
                head - perp * 8,
                head + perp * 8]
        pygame.draw.polygon(surface, (206, 108, 44), [(p.x, p.y) for p in brim])
        pygame.draw.circle(surface, (240, 138, 56), (hx, hy), 8)     # cap dome
        pygame.draw.circle(surface, (108, 48, 18), (hx, hy), 8, 2)   # cap outline

        # --- "YOU" name tag with an arrow pointing down at the player -----
        self._draw_you_tag(surface, x, body_y)

        # --- unarmed warning ring ---------------------------------------
        if not self.weapon:
            pulse = (math.sin(self.walk_phase * 0.9) + 1) * 0.5
            radius = int(self.radius + 8 + pulse * 4)
            ring = pygame.Surface((radius * 2 + 4, radius * 2 + 4), pygame.SRCALPHA)
            pygame.draw.circle(ring, (255, 210, 90, 70 + int(60 * pulse)),
                               (radius + 2, radius + 2), radius, 2)
            surface.blit(ring, (x - radius - 2, body_y - radius - 2))

    def _draw_you_tag(self, surface, x, body_y):
        """A bright 'YOU' label with a little arrow aimed at the player."""
        font = get_font(15, bold=True)
        label = "YOU"
        body = font.render(label, True, (12, 22, 30))
        pad_w, pad_h = body.get_width() + 14, body.get_height() + 6
        tag_y = body_y - self.radius - 42

        tag = pygame.Surface((pad_w, pad_h), pygame.SRCALPHA)
        pygame.draw.rect(tag, (150, 225, 255, 235), tag.get_rect(), border_radius=6)
        pygame.draw.rect(tag, (26, 60, 84, 255), tag.get_rect(), 2, border_radius=6)
        tag.blit(body, (7, 3))
        surface.blit(tag, (x - pad_w / 2, tag_y))

        # Downward arrow between the label and the player's hat.
        tip_y = tag_y + pad_h + 7
        pygame.draw.polygon(surface, (150, 225, 255),
                            [(x - 6, tag_y + pad_h), (x + 6, tag_y + pad_h), (x, tip_y)])
        pygame.draw.polygon(surface, (26, 60, 84),
                            [(x - 6, tag_y + pad_h), (x + 6, tag_y + pad_h), (x, tip_y)], 1)

    def draw_pointer_to(self, surface, target_pos, color=(255, 214, 110),
                        label="WEAPON"):
        """
        Draw an arrow beside the player pointing at something important
        (used to guide an unarmed player to the nearest weapon box).
        """
        direction = pygame.math.Vector2(target_pos) - self.pos
        distance = direction.length()
        if distance < 60:
            return                              # close enough to see it already
        direction = direction / distance
        perp = pygame.math.Vector2(-direction.y, direction.x)

        base = self.pos + direction * (self.radius + 26)
        tip = self.pos + direction * (self.radius + 44)
        pygame.draw.polygon(surface, color, [
            (tip.x, tip.y),
            (base.x + perp.x * 8, base.y + perp.y * 8),
            (base.x - perp.x * 8, base.y - perp.y * 8)])
        pygame.draw.polygon(surface, (60, 42, 10), [
            (tip.x, tip.y),
            (base.x + perp.x * 8, base.y + perp.y * 8),
            (base.x - perp.x * 8, base.y - perp.y * 8)], 1)

        font = get_font(13, bold=True)
        text = font.render("{} {}m".format(label, int(distance / 10)), True, color)
        shadow = font.render("{} {}m".format(label, int(distance / 10)), True, (10, 16, 12))
        pos = self.pos + direction * (self.radius + 60)
        rect = text.get_rect(center=(int(pos.x), int(pos.y)))
        surface.blit(shadow, (rect.x + 1, rect.y + 1))
        surface.blit(text, rect)

    def draw_health_ring(self, surface):
        """A thin health arc under the player so the user never loses track of it."""
        ratio = self.health_ratio
        if ratio >= 1.0:
            return
        width, height = 40, 6
        x = int(self.pos.x - width / 2)
        y = int(self.pos.y + self.radius + 10)
        pygame.draw.rect(surface, (18, 24, 20), (x - 1, y - 1, width + 2, height + 2),
                         border_radius=3)
        color = (86, 214, 110) if ratio > 0.5 else (240, 190, 70) if ratio > 0.25 else (226, 74, 68)
        pygame.draw.rect(surface, color, (x, y, int(width * ratio), height), border_radius=3)
