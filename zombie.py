"""
zombie.py
=========
The Zombie class.

Life cycle
----------
1. FALLING  - spawns high above a random spot in the sky and drops with
              gravity; a shadow on the ground grows as it gets closer.
2. LANDING  - a short squash-and-stretch while dust flies everywhere.
3. CHASING  - walks toward the player and bites when it gets close.
4. DEAD     - removed by the game, which awards the points.

Every zombie permanently shows its point value above its head, and the three
special types (gold / red / purple) also show a glowing star, crown or
diamond mark.
"""

import math
import random

import pygame

from settings import (ZOMBIE_TYPES, ZOMBIE_ATTACK_COOLDOWN, ZOMBIE_FALL_GRAVITY,
                      ZOMBIE_FALL_START_HEIGHT, PLAY_RECT, get_font)

# Point labels are rendered once and reused - rendering text every frame for
# 40 zombies would be wasteful.
_LABEL_CACHE = {}


def _point_label(points, color):
    """Cached '10' / '300' label surface with a dark outline for readability."""
    key = (points, color)
    cached = _LABEL_CACHE.get(key)
    if cached is not None:
        return cached
    font = get_font(19, bold=True)
    text = str(points)
    body = font.render(text, True, color)
    outline = font.render(text, True, (8, 14, 10))
    w, h = body.get_width() + 4, body.get_height() + 4
    surf = pygame.Surface((w, h), pygame.SRCALPHA)
    for dx, dy in ((0, 1), (1, 0), (2, 1), (1, 2), (0, 0), (2, 2), (0, 2), (2, 0)):
        surf.blit(outline, (dx, dy))
    surf.blit(body, (1, 1))
    _LABEL_CACHE[key] = surf
    return surf


class Zombie:
    """One zombie, from the sky to the ground to (hopefully) its demise."""

    _next_id = 1

    FALLING = "falling"
    LANDING = "landing"
    CHASING = "chasing"

    def __init__(self, kind, x, ground_y, wave=1, rng=random):
        data = ZOMBIE_TYPES.get(kind, ZOMBIE_TYPES["regular"])
        self.id = Zombie._next_id
        Zombie._next_id += 1

        self.kind = kind
        self.data = data
        self.label = data["label"]
        self.points = int(data["points"])
        self.special = bool(data["special"])
        self.mark = data["mark"]
        self.glow_color = data["glow"]
        self.body_color = data["body"]
        self.limb_color = data["limb"]
        self.shirt_color = data["shirt"]
        self.radius = int(data["radius"])
        self.damage = float(data["damage"])

        # Difficulty scaling: later waves are faster and tougher.
        from settings import SPEED_BONUS_PER_WAVE, HEALTH_BONUS_PER_WAVE
        speed_mult = 1.0 + SPEED_BONUS_PER_WAVE * (wave - 1)
        health_mult = 1.0 + HEALTH_BONUS_PER_WAVE * (wave - 1)
        self.speed = float(data["speed"]) * speed_mult * rng.uniform(0.92, 1.10)
        self.max_health = float(data["health"]) * health_mult
        self.health = self.max_health

        # Position: (x, y) is where the feet touch the ground.
        self.pos = pygame.math.Vector2(x, ground_y)
        self.height = rng.uniform(*ZOMBIE_FALL_START_HEIGHT)   # px above the ground
        self.fall_speed = rng.uniform(60, 180)
        self.spin = rng.uniform(-260, 260)                     # tumbling while falling
        self.tilt = rng.uniform(-40, 40)

        self.state = Zombie.FALLING
        self.facing = pygame.math.Vector2(0, 1)   # direction the arms reach toward
        self.land_timer = 0.0
        self.attack_timer = 0.0
        self.walk_phase = rng.uniform(0, math.tau)
        self.hit_flash = 0.0
        self.knockback = pygame.math.Vector2(0, 0)
        self.wobble = rng.uniform(0.6, 1.5)
        self.alive = True
        self.time_alive = 0.0

    # ------------------------------------------------------------------
    @property
    def draw_y(self):
        """Screen Y of the zombie's centre (feet position minus fall height)."""
        return self.pos.y - self.height - self.radius

    @property
    def center(self):
        return pygame.math.Vector2(self.pos.x, self.draw_y)

    @property
    def landed(self):
        return self.state == Zombie.CHASING

    @property
    def can_be_hit(self):
        """Falling zombies are still in the air; you can only shoot the landed ones."""
        return self.state != Zombie.FALLING and self.alive

    @property
    def health_ratio(self):
        return max(0.0, min(1.0, self.health / self.max_health)) if self.max_health else 0.0

    # ------------------------------------------------------------------
    # Update
    # ------------------------------------------------------------------
    def update(self, dt, player, effects, audio):
        """Advance this zombie one frame.  Returns True if it attacked the player."""
        self.time_alive += dt
        self.hit_flash = max(0.0, self.hit_flash - dt * 3.5)
        attacked = False

        if self.state == Zombie.FALLING:
            self.fall_speed += ZOMBIE_FALL_GRAVITY * dt
            self.height -= self.fall_speed * dt
            self.tilt += self.spin * dt
            if self.height <= 0:
                self.height = 0
                self.state = Zombie.LANDING
                self.land_timer = 0.22
                self.tilt = 0
                # Landing dust + thump.
                effects.dust_burst(self.pos.x, self.pos.y,
                                   amount=14 + self.radius, power=120 + self.radius * 5)
                if self.special and self.glow_color:
                    effects.rings.append(_special_landing_ring(self.pos, self.glow_color))
                audio.play("land", volume=0.5)
                if random.random() < 0.5:
                    audio.play("groan", volume=0.35)

        elif self.state == Zombie.LANDING:
            self.land_timer -= dt
            if self.land_timer <= 0:
                self.state = Zombie.CHASING

        elif self.state == Zombie.CHASING:
            self.walk_phase += dt * (4.0 + self.speed * 0.03)
            self.attack_timer = max(0.0, self.attack_timer - dt)

            to_player = player.pos - self.pos
            distance = to_player.length()
            if distance > 0.001:
                direction = to_player / distance
                self.facing = direction
                # A gentle side-to-side shamble so they do not move like robots.
                sway = math.sin(self.walk_phase * 0.8) * 0.28 * self.wobble
                direction = direction.rotate(math.degrees(sway) * 0.35)
                self.pos += direction * self.speed * dt

            # Apply and decay knock-back from bullets.
            if self.knockback.length_squared() > 1:
                self.pos += self.knockback * dt
                self.knockback *= max(0.0, 1.0 - 6.0 * dt)

            # Keep zombies inside the arena.
            self.pos.x = max(PLAY_RECT.left + self.radius,
                             min(PLAY_RECT.right - self.radius, self.pos.x))
            self.pos.y = max(PLAY_RECT.top + self.radius,
                             min(PLAY_RECT.bottom - self.radius, self.pos.y))

            # Attack when touching the player.
            if distance <= self.radius + player.radius + 2 and self.attack_timer <= 0:
                if player.take_damage(self.damage, self.pos):
                    attacked = True
                    self.attack_timer = ZOMBIE_ATTACK_COOLDOWN
                    effects.player_hurt(player.pos.x, player.pos.y)
                    audio.play("bite", volume=0.55)
                else:
                    self.attack_timer = 0.25    # retry soon while player is invulnerable

        return attacked

    def separate_from(self, other, dt):
        """Push overlapping zombies apart so they do not stack into one blob."""
        if not (self.landed and other.landed):
            return
        delta = self.pos - other.pos
        dist_sq = delta.length_squared()
        min_dist = (self.radius + other.radius) * 0.85
        if 0 < dist_sq < min_dist * min_dist:
            dist = math.sqrt(dist_sq)
            push = delta / dist * (min_dist - dist) * 2.4 * dt
            self.pos += push
            other.pos -= push

    # ------------------------------------------------------------------
    # Damage
    # ------------------------------------------------------------------
    def take_damage(self, amount, effects, direction=None, knock=140):
        """
        Apply damage.  Returns True when this hit killed the zombie.
        Sparks are pale green — arcade style, no gore.
        """
        if not self.alive:
            return False
        self.health -= amount
        self.hit_flash = 1.0
        if direction is not None and self.landed:
            self.knockback += pygame.math.Vector2(direction) * knock

        effects.hit_spark(self.pos.x, self.draw_y, amount=5)

        if self.health <= 0:
            self.health = 0
            self.alive = False
            return True
        return False

    # ------------------------------------------------------------------
    # Drawing
    # ------------------------------------------------------------------
    def draw(self, surface):
        cx = self.pos.x
        cy = self.draw_y

        # --- ground shadow (shrinks while high in the air) --------------
        shadow_scale = max(0.25, 1.0 - self.height / 500.0)
        sw = int(self.radius * 2.2 * shadow_scale)
        sh = int(self.radius * 1.1 * shadow_scale)
        if sw > 1 and sh > 1:
            shadow = pygame.Surface((sw, sh), pygame.SRCALPHA)
            alpha = int(120 * shadow_scale)
            pygame.draw.ellipse(shadow, (0, 0, 0, alpha), shadow.get_rect())
            surface.blit(shadow, (cx - sw / 2, self.pos.y - sh / 2 + 4))

        # --- special glow behind the body -------------------------------
        if self.special and self.glow_color:
            from effects import radial_glow
            pulse = (math.sin(self.time_alive * 5.0) + 1) * 0.5
            gr = int(self.radius * 2.0 + pulse * 6)
            glow = radial_glow(gr, self.glow_color, 95 + int(35 * pulse))
            surface.blit(glow, (cx - gr, cy - gr))

        # Squash while landing, tilt while falling.
        squash = 1.0
        if self.state == Zombie.LANDING:
            t = max(0.0, self.land_timer / 0.22)
            squash = 1.0 - 0.35 * t

        body_r = self.radius
        limb_swing = math.sin(self.walk_phase) * (self.radius * 0.35)
        if self.state == Zombie.FALLING:
            limb_swing = math.sin(self.time_alive * 16) * self.radius * 0.5

        # --- arms reaching out toward the player -------------------------
        arm_len = self.radius * 1.35
        face = self.facing
        if face.length_squared() == 0:
            face = pygame.math.Vector2(0, 1)
        perp = pygame.math.Vector2(-face.y, face.x)
        thickness = max(3, self.radius // 4)
        for side in (-1, 1):
            shoulder = pygame.math.Vector2(cx, cy - self.radius * 0.1) + perp * (self.radius * 0.7 * side)
            hand = shoulder + face * arm_len + perp * (limb_swing * 0.25 * side)
            pygame.draw.line(surface, self.limb_color, shoulder, hand, thickness)
            pygame.draw.circle(surface, self.limb_color, (int(hand.x), int(hand.y)),
                               max(2, thickness - 1))

        # --- legs --------------------------------------------------------
        for side in (-1, 1):
            lx = cx + side * self.radius * 0.45
            ly = cy + self.radius * 0.7 * squash
            pygame.draw.line(surface, self.limb_color, (lx, ly),
                             (lx + limb_swing * side * 0.6, ly + self.radius * 0.55),
                             max(3, self.radius // 4))

        # --- torso -------------------------------------------------------
        torso = pygame.Rect(0, 0, int(body_r * 1.5), int(body_r * 1.5 * squash))
        torso.center = (int(cx), int(cy + body_r * 0.25))
        pygame.draw.ellipse(surface, self.shirt_color, torso)
        pygame.draw.ellipse(surface, (18, 26, 20), torso, 2)

        # --- head --------------------------------------------------------
        head_r = max(6, int(body_r * 0.72))
        head_y = int(cy - body_r * 0.45 * squash)
        pygame.draw.circle(surface, self.body_color, (int(cx), head_y), head_r)
        pygame.draw.circle(surface, (16, 26, 18), (int(cx), head_y), head_r, 2)

        # Eyes (angry glowing dots) + a simple stitched mouth.
        eye_dx = max(2, head_r // 3)
        eye_color = (255, 244, 180) if not self.special else (255, 255, 255)
        pygame.draw.circle(surface, eye_color, (int(cx - eye_dx), head_y - 2), max(1, head_r // 5))
        pygame.draw.circle(surface, eye_color, (int(cx + eye_dx), head_y - 2), max(1, head_r // 5))
        pygame.draw.circle(surface, (30, 40, 30), (int(cx - eye_dx), head_y - 2), max(1, head_r // 9))
        pygame.draw.circle(surface, (30, 40, 30), (int(cx + eye_dx), head_y - 2), max(1, head_r // 9))
        mouth_y = head_y + head_r // 2
        pygame.draw.line(surface, (28, 40, 30), (cx - eye_dx, mouth_y), (cx + eye_dx, mouth_y), 2)

        # --- white hit flash (traces the zombie, not a big blob) -----------
        if self.hit_flash > 0:
            alpha = int(130 * min(1.0, self.hit_flash))
            pad = int(body_r * 1.6)
            flash = pygame.Surface((pad * 2, pad * 2), pygame.SRCALPHA)
            fc = (255, 255, 255, alpha)
            local_torso = torso.copy()
            local_torso.center = (pad, pad + int(body_r * 0.25))
            pygame.draw.ellipse(flash, fc, local_torso)
            pygame.draw.circle(flash, fc, (pad, pad - int(body_r * 0.45 * squash)), head_r)
            surface.blit(flash, (cx - pad, cy - pad))

        # --- health bar (only once damaged) --------------------------------
        if self.health_ratio < 1.0 and self.landed:
            bw = int(self.radius * 2.2)
            bx = int(cx - bw / 2)
            by = int(cy - body_r - 16)
            pygame.draw.rect(surface, (16, 22, 18), (bx - 1, by - 1, bw + 2, 6))
            pygame.draw.rect(surface, (200, 70, 60), (bx, by, bw, 4))
            pygame.draw.rect(surface, (110, 220, 120),
                             (bx, by, int(bw * self.health_ratio), 4))

        # --- floating point number (always visible) -------------------------
        label_color = self.glow_color if self.special else (255, 240, 170)
        label = _point_label(self.points, label_color)
        bob = math.sin(self.time_alive * 3.0) * 2.0
        label_y = cy - body_r - 34 + bob
        surface.blit(label, (cx - label.get_width() / 2, label_y))

        # --- special mark above the number ----------------------------------
        if self.mark:
            self._draw_mark(surface, cx, label_y - 14 + bob * 0.5)

    # ------------------------------------------------------------------
    def _draw_mark(self, surface, cx, cy):
        """Glowing star / crown / diamond above the special zombies."""
        from effects import radial_glow
        color = self.glow_color or (255, 255, 255)
        pulse = (math.sin(self.time_alive * 6.0) + 1) * 0.5

        halo = radial_glow(20, color, 90 + int(60 * pulse))
        surface.blit(halo, (cx - 20, cy - 20))

        if self.mark == "star":
            points = []
            for i in range(10):
                angle = -math.pi / 2 + i * math.pi / 5
                r = 10 if i % 2 == 0 else 4.5
                points.append((cx + math.cos(angle) * r, cy + math.sin(angle) * r))
            pygame.draw.polygon(surface, color, points)
            pygame.draw.polygon(surface, (255, 255, 255), points, 1)

        elif self.mark == "crown":
            pts = [(cx - 10, cy + 7), (cx - 10, cy - 6), (cx - 5, cy + 1),
                   (cx, cy - 9), (cx + 5, cy + 1), (cx + 10, cy - 6), (cx + 10, cy + 7)]
            pygame.draw.polygon(surface, color, pts)
            pygame.draw.polygon(surface, (255, 255, 255), pts, 1)

        else:   # diamond
            pts = [(cx, cy - 10), (cx + 8, cy), (cx, cy + 10), (cx - 8, cy)]
            pygame.draw.polygon(surface, color, pts)
            pygame.draw.polygon(surface, (255, 255, 255), pts, 1)


# ---------------------------------------------------------------------------
def _special_landing_ring(pos, color):
    """Extra coloured shockwave when a special zombie hits the dirt."""
    from effects import ShockRing
    return ShockRing(pos.x, pos.y, color, max_radius=90, life=0.55, width=3, squash=0.4)


# ---------------------------------------------------------------------------
def spawn_zombie(wave, rng=random):
    """
    Build one random zombie for the given wave, dropping from a random spot in
    the sky onto a random patch of ground.
    """
    from settings import pick_zombie_type
    kind = pick_zombie_type(wave, rng)
    radius = ZOMBIE_TYPES[kind]["radius"]
    x = rng.randint(PLAY_RECT.left + radius + 10, PLAY_RECT.right - radius - 10)
    # Land anywhere in the lower 80% of the arena so they are always visible.
    y = rng.randint(int(PLAY_RECT.top + PLAY_RECT.height * 0.18), PLAY_RECT.bottom - radius)
    return Zombie(kind, x, y, wave=wave, rng=rng)
