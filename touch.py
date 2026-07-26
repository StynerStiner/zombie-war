"""
touch.py
========
Touch-screen controls for phones and tablets.

On a desktop the game is driven by WASD + mouse.  On a touch device neither
exists, so this module turns finger input into the same two actions:

* LEFT half of the screen  -> drag to walk (a virtual thumb-stick that appears
  wherever your thumb lands, so you never have to hunt for a fixed control)
* RIGHT half of the screen -> touch and hold to aim and shoot at that spot

Both halves work at the same time (twin-stick style), and menus can simply be
tapped.  Pygame reports touches as FINGERDOWN / FINGERMOTION / FINGERUP events
with coordinates normalised to 0..1, which also means the controls keep working
no matter how the browser scales the canvas.
"""

import math

import pygame

from settings import SCREEN_WIDTH, SCREEN_HEIGHT, get_font

# How far the thumb-stick knob can travel from its origin, in pixels.
STICK_RADIUS = 78
# Below this distance the stick is treated as centred (prevents jitter).
STICK_DEADZONE = 10

# The dedicated FIRE button: a fixed circle in the bottom-right corner.
FIRE_RADIUS = 72
FIRE_CENTER = (SCREEN_WIDTH - 118, SCREEN_HEIGHT - 118)


class TouchControls:
    """Tracks fingers and converts them into movement + firing."""

    def __init__(self):
        self.enabled = False        # flips to True the first time a finger lands
        self.move_finger = None
        self.move_origin = pygame.math.Vector2(0, 0)
        self.move_point = pygame.math.Vector2(0, 0)
        self.fire_finger = None
        self.fire_point = pygame.math.Vector2(0, 0)
        self.button_finger = None   # finger holding the dedicated FIRE button
        self.last_tap = None        # screen position of the most recent tap

    # ------------------------------------------------------------------
    # Event handling
    # ------------------------------------------------------------------
    @staticmethod
    def _to_screen(event):
        """FINGER events use 0..1 coordinates; convert them to pixels."""
        return pygame.math.Vector2(float(event.x) * SCREEN_WIDTH,
                                   float(event.y) * SCREEN_HEIGHT)

    def handle_event(self, event):
        """
        Feed a pygame event in.  Returns True when the event was a touch event
        (so the caller knows a touch device is being used).
        """
        if event.type == pygame.FINGERDOWN:
            pos = self._to_screen(event)
            self.enabled = True
            self.last_tap = (int(pos.x), int(pos.y))
            finger = getattr(event, "finger_id", 0)
            # The FIRE button wins over everything else it overlaps.
            if self.over_fire_button(pos):
                self.button_finger = finger
            elif pos.x < SCREEN_WIDTH * 0.45 and self.move_finger is None:
                self.move_finger = finger
                self.move_origin = pygame.math.Vector2(pos)
                self.move_point = pygame.math.Vector2(pos)
            else:
                # Touching open ground on the right aims there and shoots.
                self.fire_finger = finger
                self.fire_point = pos
            return True

        if event.type == pygame.FINGERMOTION:
            pos = self._to_screen(event)
            finger = getattr(event, "finger_id", 0)
            if finger == self.move_finger:
                self.move_point = pos
            elif finger == self.fire_finger:
                self.fire_point = pos
            return True

        if event.type == pygame.FINGERUP:
            finger = getattr(event, "finger_id", 0)
            if finger == self.move_finger:
                self.move_finger = None
            elif finger == self.fire_finger:
                self.fire_finger = None
            elif finger == self.button_finger:
                self.button_finger = None
            return True

        return False

    @staticmethod
    def over_fire_button(pos):
        """True when a point is inside the dedicated FIRE button."""
        dx = pos[0] - FIRE_CENTER[0]
        dy = pos[1] - FIRE_CENTER[1]
        return (dx * dx + dy * dy) <= FIRE_RADIUS * FIRE_RADIUS

    def reset(self):
        """Drop every finger (used when changing screen or pausing)."""
        self.move_finger = None
        self.fire_finger = None
        self.button_finger = None

    def take_tap(self):
        """Return the last tap position once, then forget it (for menus)."""
        tap, self.last_tap = self.last_tap, None
        return tap

    # ------------------------------------------------------------------
    # Read the controls
    # ------------------------------------------------------------------
    def move_vector(self):
        """Walk direction as a vector no longer than 1.0 (zero when idle)."""
        if self.move_finger is None:
            return pygame.math.Vector2(0, 0)
        delta = self.move_point - self.move_origin
        length = delta.length()
        if length < STICK_DEADZONE:
            return pygame.math.Vector2(0, 0)
        # Full speed once the thumb is STICK_RADIUS away from the origin.
        scale = min(1.0, length / STICK_RADIUS)
        return (delta / length) * scale

    @property
    def firing(self):
        """True while either the FIRE button or the right half is held."""
        return self.fire_finger is not None or self.button_finger is not None

    @property
    def button_held(self):
        """True only for the dedicated FIRE button (which uses auto-aim)."""
        return self.button_finger is not None

    def aim_point(self):
        """
        Where the player should shoot, or None.

        Only a free touch on the open right-hand side aims explicitly; the FIRE
        button returns None so the game can aim at the nearest zombie for you.
        """
        return self.fire_point if self.fire_finger is not None else None

    # ------------------------------------------------------------------
    # Drawing
    # ------------------------------------------------------------------
    def draw(self, surface):
        """Show the stick and the fire crosshair (only on touch devices)."""
        if not self.enabled:
            return

        # ---- idle hint for the movement side ----------------------------
        font = get_font(15, bold=True)
        if self.move_finger is None:
            self._ghost(surface, (150, SCREEN_HEIGHT - 140), "DRAG TO MOVE", font)

        # ---- the dedicated FIRE button ----------------------------------
        self._draw_fire_button(surface)

        # ---- live thumb-stick -------------------------------------------
        if self.move_finger is not None:
            ox, oy = int(self.move_origin.x), int(self.move_origin.y)
            base = pygame.Surface((STICK_RADIUS * 2 + 8, STICK_RADIUS * 2 + 8),
                                  pygame.SRCALPHA)
            c = STICK_RADIUS + 4
            pygame.draw.circle(base, (12, 26, 20, 110), (c, c), STICK_RADIUS)
            pygame.draw.circle(base, (150, 225, 255, 170), (c, c), STICK_RADIUS, 3)
            surface.blit(base, (ox - c, oy - c))

            delta = self.move_point - self.move_origin
            if delta.length() > STICK_RADIUS:
                delta = delta.normalize() * STICK_RADIUS
            knob = self.move_origin + delta
            pygame.draw.circle(surface, (150, 225, 255), (int(knob.x), int(knob.y)), 30)
            pygame.draw.circle(surface, (20, 46, 62), (int(knob.x), int(knob.y)), 30, 3)

        # ---- fire crosshair ----------------------------------------------
        if self.fire_finger is not None:
            fx, fy = int(self.fire_point.x), int(self.fire_point.y)
            pygame.draw.circle(surface, (255, 170, 90), (fx, fy), 26, 3)
            pygame.draw.circle(surface, (255, 220, 150), (fx, fy), 6)
            for angle in range(0, 360, 90):
                rad = math.radians(angle)
                pygame.draw.line(
                    surface, (255, 170, 90),
                    (fx + math.cos(rad) * 14, fy + math.sin(rad) * 14),
                    (fx + math.cos(rad) * 34, fy + math.sin(rad) * 34), 3)

    def _draw_fire_button(self, surface):
        """Big round FIRE button: hold it and the player shoots automatically."""
        cx, cy = FIRE_CENTER
        held = self.button_finger is not None

        # Soft glow so it reads as the important control on screen.
        from effects import radial_glow
        glow_r = FIRE_RADIUS + (26 if held else 14)
        surface.blit(radial_glow(glow_r, (255, 140, 80), 120 if held else 70),
                     (cx - glow_r, cy - glow_r))

        # Drawn translucent onto its own surface: the button sits in a corner
        # of the arena, so the player must stay visible when walking under it.
        alpha = 225 if held else 165
        radius = FIRE_RADIUS - (4 if held else 0)
        size = FIRE_RADIUS * 2 + 16
        pad = size // 2
        btn = pygame.Surface((size, size), pygame.SRCALPHA)

        body = (255, 156, 74) if held else (196, 92, 52)
        edge = (255, 226, 170) if held else (120, 54, 28)
        pygame.draw.circle(btn, (18, 12, 10, alpha // 2), (pad, pad + 4), radius)
        pygame.draw.circle(btn, body + (alpha,), (pad, pad), radius)
        pygame.draw.circle(btn, edge + (min(255, alpha + 40),), (pad, pad), radius, 4)

        # A simple bullet/crosshair glyph in the middle.
        glyph = (255, 240, 210, min(255, alpha + 50))
        pygame.draw.circle(btn, glyph, (pad, pad), 13)
        for angle in (0, 90, 180, 270):
            rad = math.radians(angle)
            pygame.draw.line(btn, glyph,
                             (pad + math.cos(rad) * 22, pad + math.sin(rad) * 22),
                             (pad + math.cos(rad) * 38, pad + math.sin(rad) * 38), 5)

        font = get_font(18, bold=True)
        label = font.render("FIRE", True, (28, 16, 10) if held else (255, 226, 190))
        label.set_alpha(min(255, alpha + 60))
        btn.blit(label, label.get_rect(center=(pad, pad + FIRE_RADIUS - 20)))

        surface.blit(btn, (cx - pad, cy - pad))

    @staticmethod
    def _ghost(surface, center, label, font):
        """Faint circle + caption showing where a control lives."""
        cx, cy = center
        ghost = pygame.Surface((STICK_RADIUS * 2, STICK_RADIUS * 2), pygame.SRCALPHA)
        pygame.draw.circle(ghost, (200, 230, 240, 40),
                           (STICK_RADIUS, STICK_RADIUS), STICK_RADIUS - 6)
        pygame.draw.circle(ghost, (200, 230, 240, 70),
                           (STICK_RADIUS, STICK_RADIUS), STICK_RADIUS - 6, 2)
        surface.blit(ghost, (cx - STICK_RADIUS, cy - STICK_RADIUS))
        text = font.render(label, True, (206, 226, 232))
        shadow = font.render(label, True, (8, 16, 12))
        rect = text.get_rect(center=(cx, cy))
        surface.blit(shadow, (rect.x + 1, rect.y + 1))
        surface.blit(text, rect)


def touch_hint_banner():
    """Short instruction shown once when a touch device is detected."""
    return "Touch controls: drag on the LEFT to walk, hold on the RIGHT to shoot"
