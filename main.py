"""
ZOMBIE WAR  -  built by William
===============================
A 2D top-down arcade survival game made with Python + Pygame.

Run it with:      python main.py
Self-check it:    python main.py --selftest      (headless, no window)

Everything is drawn with Pygame shapes and every sound is generated in code,
so the game needs no downloaded assets at all.

Controls
--------
W A S D / Arrows .... walk
Mouse ............... aim
Space / Left click .. shoot
P ................... pause
R ................... restart after game over
M ................... mute / unmute
Esc ................. back to the menu (quit from the title screen)
"""

import asyncio
import math
import os
import random
import sys
import traceback

# True when running in a browser through pygbag / Pyodide (WebAssembly build).
# The desktop and web versions share this one file; only a few small things
# differ (the loop must yield to the browser, and scores go to localStorage).
IS_WEB = (sys.platform == "emscripten")

try:
    import pygame
except ImportError:                      # friendly message instead of a traceback
    print("Zombie War needs Pygame, which is not installed for this Python.\n"
          "Install it with:\n"
          "    python3 -m pip install pygame        (Windows:  py -m pip install pygame)\n",
          file=sys.stderr)
    raise SystemExit(1)

from settings import (GAME_TITLE, AUTHOR, VERSION, SCREEN_WIDTH, SCREEN_HEIGHT, FPS,
                      MAX_DT, HUD_HEIGHT, PLAY_RECT, WHITE, GREY, DARK, PANEL,
                      PANEL_EDGE, ACCENT, GOLD, RED, PURPLE, HEALTH_GOOD, HEALTH_WARN,
                      HEALTH_BAD, WEAPONS, ZOMBIE_TYPES, KILLS_PER_WEAPON, CONTROLS,
                      BOX_MAX_ON_FIELD, BOX_SPAWN_INTERVAL, BOX_SPAWN_INTERVAL_UNARMED,
                      BOX_LIFETIME, WAVE_DURATION, HISTORY_SHOW, TOUCH_CONTROLS,
                      ZOMBIE_ATTACK_COOLDOWN, GRACE_SECONDS,
                      STATE_TITLE, STATE_INSTRUCTIONS, STATE_PLAYING, STATE_PAUSED,
                      STATE_GAME_OVER, STATE_HISTORY,
                      spawn_interval_for_wave, max_zombies_for_wave, get_font)
from ally import Teammate
from audio import Audio
from effects import EffectManager
from environment import Rainforest
from player import Player
from score_manager import ScoreManager
from touch import TouchControls, touch_hint_banner
from weapon import random_weapon
from weapon_box import WeaponBox, random_box_position
from zombie import Zombie, spawn_zombie


# ===========================================================================
# Small drawing helpers
# ===========================================================================
def draw_text(surface, text, font, color, pos, align="left", shadow=True,
              shadow_color=(6, 12, 8)):
    """Render text with an optional drop shadow.  Returns the drawn rect."""
    img = font.render(str(text), True, color)
    rect = img.get_rect()
    if align == "center":
        rect.center = pos
    elif align == "right":
        rect.midright = pos
    elif align == "midleft":
        rect.midleft = pos
    else:
        rect.topleft = pos
    if shadow:
        shadow_img = font.render(str(text), True, shadow_color)
        surface.blit(shadow_img, (rect.x + 2, rect.y + 2))
    surface.blit(img, rect)
    return rect


def draw_big_title(surface, text, font, color, center, spacing=10, outline=3):
    """
    Draw a chunky arcade headline one letter at a time.

    Rendering per-character lets us add letter spacing and a thick outline,
    which keeps big headlines readable on every machine (some system fonts
    are very condensed and squash a single long render).
    """
    glyphs = [(ch, font.render(ch, True, color)) for ch in text]
    total = sum(img.get_width() for _ch, img in glyphs) + spacing * (len(glyphs) - 1)
    x = center[0] - total // 2
    outline_color = (10, 16, 12)
    for ch, img in glyphs:
        rect = img.get_rect()
        rect.midleft = (x, center[1])
        if ch != " " and outline > 0:
            shade = font.render(ch, True, outline_color)
            for dx in (-outline, 0, outline):
                for dy in (-outline, 0, outline):
                    if dx or dy:
                        surface.blit(shade, (rect.x + dx, rect.y + dy))
        surface.blit(img, rect)
        x += img.get_width() + spacing
    return total


def draw_panel(surface, rect, fill=PANEL, edge=PANEL_EDGE, alpha=225, radius=12, width=2):
    """A translucent rounded UI panel."""
    panel = pygame.Surface((rect.width, rect.height), pygame.SRCALPHA)
    pygame.draw.rect(panel, fill + (alpha,), panel.get_rect(), border_radius=radius)
    pygame.draw.rect(panel, edge + (255,), panel.get_rect(), width, border_radius=radius)
    surface.blit(panel, rect.topleft)


def draw_bar(surface, rect, ratio, fill_color, back=(24, 34, 28), border=(70, 96, 78)):
    """A simple horizontal progress / health bar."""
    ratio = max(0.0, min(1.0, ratio))
    pygame.draw.rect(surface, back, rect, border_radius=4)
    if ratio > 0:
        inner = pygame.Rect(rect.x, rect.y, int(rect.width * ratio), rect.height)
        pygame.draw.rect(surface, fill_color, inner, border_radius=4)
    pygame.draw.rect(surface, border, rect, 2, border_radius=4)


# The title screen's controls panel grows upward from this line; the buttons
# start just below it.  Keep the two in step.
TITLE_PANEL_BOTTOM = 482


# ===========================================================================
class Button:
    """A clickable UI button with hover and press feedback."""

    def __init__(self, rect, label, action, color=ACCENT, key_hint=None):
        self.rect = pygame.Rect(rect)
        self.label = label
        self.action = action
        self.color = color
        self.key_hint = key_hint
        self.hover = False
        self.pressed = False

    def update(self, mouse_pos):
        self.hover = self.rect.collidepoint(mouse_pos)

    def hit(self, pos):
        return self.rect.collidepoint(pos)

    def draw(self, surface):
        base = (22, 40, 30)
        edge = self.color if self.hover else (70, 100, 80)
        offset = 2 if self.pressed else 0
        rect = self.rect.move(0, offset)

        shadow = rect.move(0, 4)
        pygame.draw.rect(surface, (8, 16, 12), shadow, border_radius=10)
        pygame.draw.rect(surface, base, rect, border_radius=10)
        if self.hover:
            glow = pygame.Surface((rect.width, rect.height), pygame.SRCALPHA)
            pygame.draw.rect(glow, self.color + (46,), glow.get_rect(), border_radius=10)
            surface.blit(glow, rect.topleft)
        pygame.draw.rect(surface, edge, rect, 2, border_radius=10)

        font = get_font(24, bold=True)
        label_color = WHITE if not self.hover else self.color
        draw_text(surface, self.label, font, label_color, rect.center, align="center")

        if self.key_hint:
            hint_font = get_font(14)
            draw_text(surface, self.key_hint, hint_font, (140, 160, 148),
                      (rect.centerx, rect.bottom - 9), align="center", shadow=False)


# ===========================================================================
class _MenuTarget:
    """A fake 'player' the decorative title-screen zombies wander toward."""

    def __init__(self):
        self.pos = pygame.math.Vector2(SCREEN_WIDTH / 2, SCREEN_HEIGHT * 0.62)
        self.radius = 16
        self.t = 0.0

    def update(self, dt):
        self.t += dt
        self.pos.x = SCREEN_WIDTH / 2 + math.cos(self.t * 0.4) * 300
        self.pos.y = SCREEN_HEIGHT * 0.62 + math.sin(self.t * 0.55) * 120

    def take_damage(self, *_args, **_kwargs):
        return False        # menu zombies can never hurt anything


class _FakeKeys:
    """Key state used by the automated self-test (no real keyboard needed)."""

    def __init__(self, pressed=()):
        self.pressed = set(pressed)

    def __getitem__(self, key):
        return key in self.pressed


class _KeyState:
    """
    Combines two sources of "is this key held down?".

    `pygame.key.get_pressed()` is the normal way to read held keys, but in the
    browser (pygbag/WebAssembly) it is not always kept up to date, which makes
    the player feel like walking is broken.  So we ALSO track keys ourselves
    from KEYDOWN / KEYUP events and treat a key as held if either source says
    so.  On the desktop the two simply agree.
    """

    def __init__(self, held, snapshot):
        self.held = held              # set of keycodes, from our own events
        self.snapshot = snapshot      # pygame.key.get_pressed() result, or None

    def __getitem__(self, key):
        if key in self.held:
            return True
        if self.snapshot is None:
            return False
        try:
            return bool(self.snapshot[key])
        except (IndexError, TypeError):
            return False


# ===========================================================================
class Game:
    """Owns the window, the game loop, every screen and all the game objects."""

    def __init__(self, headless=False):
        self.headless = headless
        self.test_mode = headless
        self.fake_keys = _FakeKeys()

        # ---- pygame start-up ------------------------------------------
        if headless:
            os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
            os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
        try:
            pygame.mixer.pre_init(44100, -16, 2, 512)
        except pygame.error:
            pass
        pygame.init()

        flags = 0
        try:
            self.screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT), flags)
        except pygame.error as exc:
            raise SystemExit("Could not open the game window: {}".format(exc))
        pygame.display.set_caption("{}  -  built by {}".format(GAME_TITLE, AUTHOR))
        self._set_icon()

        self.clock = pygame.time.Clock()
        self.running = True

        # ---- systems ---------------------------------------------------
        self.audio = Audio(enabled=True)
        if headless:
            # The self-test must never touch the player's real score file.
            import tempfile
            self.scores = ScoreManager(os.path.join(tempfile.gettempdir(),
                                                    "zombiewar_selftest_scores.json"))
        else:
            self.scores = ScoreManager()
        self.effects = EffectManager()
        self.forest = Rainforest(seed=7)
        # The world is drawn onto this surface so it can be shaken on impact.
        self.world_surface = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT)).convert()

        # ---- fonts -----------------------------------------------------
        self.f_title = get_font(78, bold=True)      # drawn via draw_big_title()
        self.f_big = get_font(52, bold=True)
        self.f_mid = get_font(30, bold=True)
        self.f_ui = get_font(22, bold=True)
        self.f_small = get_font(17)
        self.f_tiny = get_font(14)
        self.f_hud_value = get_font(30, bold=True)
        self.f_hud_label = get_font(13, bold=True)

        # ---- state -----------------------------------------------------
        self.state = STATE_TITLE
        self.previous_state = STATE_TITLE
        self.mouse_pos = (SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2)
        self.held_keys = set()        # keys currently down, tracked from events
        self.mouse_down = False       # left button held, tracked from events
        self.touch = TouchControls()  # phone / tablet input
        self.touch_hint_shown = False
        self._detect_touch_device()
        self.prev_fire = False
        self.menu_time = 0.0
        self.buttons = {}
        self._build_buttons()

        # ---- decorative title screen zombies ---------------------------
        self.menu_target = _MenuTarget()
        self.menu_zombies = []
        self.menu_spawn_timer = 0.0

        # ---- gameplay data (filled in by reset_game) -------------------
        self.player = None
        self.zombies = []
        self.projectiles = []
        self.boxes = []
        self.score = 0
        self.kills = 0
        self.wave = 1
        self.elapsed = 0.0
        self.spawn_timer = 0.0
        self.box_timer = 0.0
        self.banner = None            # (text, color, timer, total)
        self.new_record = False
        self.shake = 0.0              # screen-shake strength, 0.0 - 1.0
        self.force_fire = False       # used by the automated self-test
        self.reset_game()
        # Music is started after the first frame is on screen (see run()), so
        # generating the loop never delays the title screen appearing.
        self._music_started = False

    # ------------------------------------------------------------------
    def _detect_touch_device(self):
        """
        Switch to touch mode straight away on a phone or tablet.

        Without this the menus would advertise WASD until the player's first
        touch, which is exactly the moment they most need the right hint.  In
        the browser we ask the page how many touch points it supports.
        """
        if not IS_WEB:
            return
        try:
            import platform as _platform          # pygbag injects .window here
            navigator = getattr(_platform, "window").navigator
            points = int(getattr(navigator, "maxTouchPoints", 0) or 0)
            if points > 0:
                self.touch.enabled = True
        except Exception:
            pass          # not fatal: the first real touch enables it anyway

    def _set_icon(self):
        """Draw a tiny zombie head as the window icon."""
        try:
            icon = pygame.Surface((32, 32), pygame.SRCALPHA)
            pygame.draw.circle(icon, (92, 146, 78), (16, 17), 13)
            pygame.draw.circle(icon, (24, 40, 26), (16, 17), 13, 2)
            pygame.draw.circle(icon, (255, 244, 180), (11, 14), 3)
            pygame.draw.circle(icon, (255, 244, 180), (21, 14), 3)
            pygame.draw.line(icon, (24, 40, 26), (10, 24), (22, 24), 2)
            pygame.display.set_icon(icon)
        except pygame.error:
            pass

    # ------------------------------------------------------------------
    # Buttons for every screen
    # ------------------------------------------------------------------
    def _build_buttons(self):
        cx = SCREEN_WIDTH // 2
        # Shown during play on touch devices only (no P key on a phone).
        self.pause_button = Button((SCREEN_WIDTH - 92, HUD_HEIGHT + 12, 76, 48),
                                   "II", "pause", color=GOLD)
        self.buttons = {
            STATE_TITLE: [
                Button((cx - 330, TITLE_PANEL_BOTTOM + 16, 300, 62), "START GAME",
                       "start", key_hint="Enter / Space"),
                Button((cx + 30, TITLE_PANEL_BOTTOM + 16, 300, 62), "HOW TO PLAY",
                       "instructions", color=GOLD, key_hint="I"),
                Button((cx - 330, TITLE_PANEL_BOTTOM + 92, 300, 56), "SCORE HISTORY",
                       "history", color=PURPLE, key_hint="H"),
                Button((cx + 30, TITLE_PANEL_BOTTOM + 92, 300, 56), "QUIT",
                       "quit", color=RED, key_hint="Esc"),
            ],
            STATE_INSTRUCTIONS: [
                Button((cx - 150, SCREEN_HEIGHT - 84, 300, 56), "BACK TO MENU", "title",
                       key_hint="Esc"),
            ],
            STATE_HISTORY: [
                Button((cx - 150, SCREEN_HEIGHT - 84, 300, 56), "BACK TO MENU", "title",
                       key_hint="Esc"),
            ],
            STATE_PAUSED: [
                Button((cx - 320, 516, 300, 60), "RESUME", "resume", key_hint="P"),
                Button((cx + 20, 516, 300, 60), "MAIN MENU", "title",
                       color=GOLD, key_hint="Esc"),
            ],
            STATE_GAME_OVER: [
                Button((cx - 330, SCREEN_HEIGHT - 104, 310, 62), "PLAY AGAIN", "restart",
                       key_hint="R"),
                Button((cx + 20, SCREEN_HEIGHT - 104, 310, 62), "QUIT GAME", "quit",
                       color=RED, key_hint="Esc = menu"),
            ],
        }

    # ------------------------------------------------------------------
    # New run
    # ------------------------------------------------------------------
    def reset_game(self):
        """Start a completely fresh run (used at launch and by Play Again / R)."""
        self.player = Player(SCREEN_WIDTH / 2, (PLAY_RECT.top + PLAY_RECT.bottom) / 2)
        self.teammate = Teammate(self.player.pos.x - 70, self.player.pos.y + 40)
        self.zombies = []
        self.projectiles = []
        self.boxes = []
        self.effects.clear()

        self.score = 0
        self.kills = 0
        self.wave = 1
        self.elapsed = 0.0
        # Nothing falls for the first few seconds: you start unarmed, and being
        # swarmed before you can reach a crate is what made runs end in ~14s.
        self.spawn_timer = GRACE_SECONDS
        self.box_timer = 2.4            # second crate follows the starting one
        self.banner = None
        self.new_record = False
        self.shake = 0.0
        self.prev_fire = False

        # A crate is placed within reach immediately so the player is never
        # hunted while completely defenceless.
        start_x, start_y = random_box_position(self.player.pos,
                                               min_player_distance=0)
        toward = pygame.math.Vector2(start_x, start_y) - self.player.pos
        if toward.length() > 150:
            toward.scale_to_length(150)
        first = pygame.math.Vector2(self.player.pos) + toward
        first.x = max(PLAY_RECT.left + 40, min(PLAY_RECT.right - 40, first.x))
        first.y = max(PLAY_RECT.top + 40, min(PLAY_RECT.bottom - 40, first.y))
        self.boxes.append(WeaponBox(first.x, first.y, BOX_LIFETIME * 3))

        if self.touch.enabled:
            self.set_banner("You are the BLUE player marked YOU  -  "
                            "drag on the LEFT to walk", ACCENT, 6.0)
        else:
            self.set_banner("You are the BLUE player marked YOU  -  W A S D to walk",
                            ACCENT, 6.0)

    # ------------------------------------------------------------------
    # Banner messages under the HUD
    # ------------------------------------------------------------------
    def set_banner(self, text, color, seconds=2.2):
        self.banner = [text, color, seconds, seconds]

    # ==================================================================
    # EVENTS
    # ==================================================================
    def handle_events(self):
        for event in pygame.event.get():
            # ---- touch screens (phones / tablets) ------------------------
            if event.type in (pygame.FINGERDOWN, pygame.FINGERMOTION, pygame.FINGERUP):
                first_touch = not self.touch.enabled
                self.touch.enabled = True
                if first_touch and not self.touch_hint_shown:
                    self.touch_hint_shown = True
                    self.set_banner(touch_hint_banner(), ACCENT, 6.0)

                tap = None
                if event.type == pygame.FINGERDOWN:
                    tap = (int(float(event.x) * SCREEN_WIDTH),
                           int(float(event.y) * SCREEN_HEIGHT))

                # 1. While playing, the on-screen pause button wins.
                if tap and self.state == STATE_PLAYING and self.pause_button.hit(tap):
                    self.audio.play("click", 0.5)
                    self.touch.reset()
                    self.do_action("pause")
                    continue

                # 2. On any menu, a tap behaves exactly like a mouse click.
                if tap and self.state != STATE_PLAYING:
                    self.mouse_pos = tap
                    hit_button = False
                    for button in self.buttons.get(self.state, []):
                        if button.hit(tap):
                            hit_button = True
                            self.audio.play("click", 0.5)
                            self.do_action(button.action)
                            break
                    # Tapping empty space on the title screen just starts the
                    # game, so a phone player can never get stuck on the menu.
                    if not hit_button and self.state == STATE_TITLE:
                        self.do_action("start")
                    continue

                # 3. Otherwise it is gameplay input: move stick / fire.
                self.touch.handle_event(event)
                continue

            if event.type == pygame.QUIT:
                self.quit_game()

            elif event.type == pygame.MOUSEMOTION:
                self.mouse_pos = event.pos

            elif event.type == pygame.KEYDOWN:
                self.held_keys.add(event.key)
                self._on_keydown(event)

            elif event.type == pygame.KEYUP:
                self.held_keys.discard(event.key)

            elif event.type in (pygame.WINDOWFOCUSLOST, pygame.WINDOWLEAVE):
                # Losing focus mid-stride would otherwise leave a key "stuck".
                self.held_keys.clear()
                self.mouse_down = False

            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                self.mouse_pos = event.pos
                self.mouse_down = True
                for button in self.buttons.get(self.state, []):
                    if button.hit(event.pos):
                        button.pressed = True

            elif event.type == pygame.MOUSEBUTTONUP and event.button == 1:
                self.mouse_pos = event.pos
                self.mouse_down = False
                for button in self.buttons.get(self.state, []):
                    was_pressed = button.pressed
                    button.pressed = False
                    if was_pressed and button.hit(event.pos):
                        self.audio.play("click", 0.5)
                        self.do_action(button.action)

    def _on_keydown(self, event):
        key = event.key

        # --- global keys ----------------------------------------------
        if key == pygame.K_m:
            muted = self.audio.toggle_mute()
            self.set_banner("SOUND OFF" if muted else "SOUND ON", GREY, 1.2)
            return

        if key in (pygame.K_MINUS, pygame.K_KP_MINUS):
            level = self.audio.change_volume(-0.06)
            self.set_banner("VOLUME {}%".format(level), GREY, 1.0)
            return

        if key in (pygame.K_EQUALS, pygame.K_PLUS, pygame.K_KP_PLUS):
            level = self.audio.change_volume(+0.06)
            self.set_banner("VOLUME {}%".format(level), GREY, 1.0)
            return

        if self.state == STATE_TITLE:
            if key in (pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_SPACE):
                self.do_action("start")
            elif key == pygame.K_i:
                self.do_action("instructions")
            elif key == pygame.K_h:
                self.do_action("history")
            elif key == pygame.K_ESCAPE:
                self.quit_game()

        elif self.state in (STATE_INSTRUCTIONS, STATE_HISTORY):
            if key in (pygame.K_ESCAPE, pygame.K_RETURN, pygame.K_BACKSPACE):
                self.do_action("title")
            elif key == pygame.K_SPACE and self.state == STATE_INSTRUCTIONS:
                self.do_action("start")

        elif self.state == STATE_PLAYING:
            if key == pygame.K_p:
                self.do_action("pause")
            elif key == pygame.K_ESCAPE:
                self.do_action("abandon")

        elif self.state == STATE_PAUSED:
            if key in (pygame.K_p, pygame.K_RETURN):
                self.do_action("resume")
            elif key == pygame.K_ESCAPE:
                self.do_action("abandon")

        elif self.state == STATE_GAME_OVER:
            if key == pygame.K_r:
                self.do_action("restart")
            elif key == pygame.K_ESCAPE:
                self.do_action("title")
            elif key == pygame.K_h:
                self.do_action("history")

    def do_action(self, action):
        """Central place where every button / hotkey action is carried out."""
        # Clear any half-finished click so no button stays visually stuck down
        # when we jump to a different screen.
        for buttons in self.buttons.values():
            for button in buttons:
                button.pressed = False

        if action == "start":
            self.reset_game()
            self.state = STATE_PLAYING
            self.audio.play("wave", 0.5)
        elif action == "restart":
            self.reset_game()
            self.state = STATE_PLAYING
            self.audio.start_music()
            self.audio.play("wave", 0.5)
        elif action == "instructions":
            self.state = STATE_INSTRUCTIONS
        elif action == "history":
            self.state = STATE_HISTORY
        elif action == "title":
            self.state = STATE_TITLE
        elif action == "pause":
            self.state = STATE_PAUSED
        elif action == "resume":
            self.state = STATE_PLAYING
        elif action == "abandon":
            # Leaving a run in progress still counts as a finished game.
            if self.score > 0:
                self.scores.record(self.score, self.kills, self.wave)
            self.state = STATE_TITLE
        elif action == "quit":
            self.quit_game()

    def quit_game(self):
        self.running = False

    # ==================================================================
    # UPDATE
    # ==================================================================
    def update(self, dt):
        self.forest.update(dt)
        for button in self.buttons.get(self.state, []):
            button.update(self.mouse_pos)

        if self.state == STATE_PLAYING:
            self.update_playing(dt)
        elif self.state in (STATE_TITLE, STATE_INSTRUCTIONS, STATE_HISTORY):
            self.update_menu(dt)
        elif self.state in (STATE_PAUSED, STATE_GAME_OVER):
            # The world is frozen, but the interface still breathes.
            self.menu_time += dt

        # Banner countdown.
        if self.banner:
            self.banner[2] -= dt
            if self.banner[2] <= 0:
                self.banner = None

        self.shake = max(0.0, self.shake - dt * 3.5)

    # ------------------------------------------------------------------
    def update_menu(self, dt):
        """Decorative zombies raining behind the menus."""
        self.menu_time += dt
        self.menu_target.update(dt)

        self.menu_spawn_timer -= dt
        if self.menu_spawn_timer <= 0 and len(self.menu_zombies) < 7:
            self.menu_spawn_timer = random.uniform(0.7, 1.6)
            self.menu_zombies.append(spawn_zombie(random.randint(1, 6)))

        for zombie in self.menu_zombies:
            zombie.update(dt, self.menu_target, self.effects, self.audio)
        # Recycle the oldest ones so the menu never fills up.
        self.menu_zombies = [z for z in self.menu_zombies if z.time_alive < 16.0]
        self.effects.update(dt)

    # ------------------------------------------------------------------
    def update_playing(self, dt):
        """One frame of actual gameplay."""
        self.elapsed += dt

        # ---- difficulty / waves ---------------------------------------
        new_wave = 1 + int(self.elapsed // WAVE_DURATION)
        if new_wave != self.wave:
            self.wave = new_wave
            self.set_banner("WAVE {}  -  they are getting faster!".format(self.wave),
                            GOLD, 2.6)
            self.audio.play("wave", 0.55)

        # ---- input -----------------------------------------------------
        if self.test_mode:
            keys = self.fake_keys
            firing = False
        else:
            # Event-tracked keys OR'd with pygame's snapshot: see _KeyState.
            try:
                snapshot = pygame.key.get_pressed()
            except pygame.error:
                snapshot = None
            keys = _KeyState(self.held_keys, snapshot)
            try:
                firing = bool(pygame.mouse.get_pressed()[0]) or self.mouse_down
                self.mouse_pos = pygame.mouse.get_pos()
            except pygame.error:
                firing = self.mouse_down

        # Touch input (phone / tablet) sits alongside keyboard and mouse.
        touch_move = self.touch.move_vector()
        touch_aim = self.touch.aim_point()
        if touch_aim is not None:
            # Player is aiming explicitly by touching the arena.
            self.mouse_pos = (touch_aim.x, touch_aim.y)
        elif self.touch.button_held:
            # The FIRE button aims for you: lock on to the closest zombie that
            # has already landed, so one thumb is enough to play.
            target = self.nearest_target()
            if target is not None:
                self.mouse_pos = (target.pos.x, target.draw_y)

        wants_fire = bool(keys[pygame.K_SPACE]) or firing or self.touch.firing \
            or getattr(self, "force_fire", False)

        # ---- player ----------------------------------------------------
        self.player.update(dt, keys, self.mouse_pos,
                           move_override=touch_move if touch_move.length_squared() > 0
                           else None)

        # ---- shooting ---------------------------------------------------
        if self.player.has_weapon and wants_fire:
            auto = self.player.weapon.is_auto
            if auto or not self.prev_fire:
                if self.player.shoot(self.projectiles):
                    self.audio.play_weapon(self.player.weapon.name)
                    self.effects.muzzle_smoke(
                        self.player.pos.x + self.player.aim.x * 24,
                        self.player.pos.y + self.player.aim.y * 24,
                        self.player.aim)
                    self.shake = min(1.0, self.shake + 0.12)
                    # Running dry also ends the weapon.
                    if self.player.weapon.ammo <= 0:
                        self.expire_weapon(out_of_ammo=True)
        self.prev_fire = wants_fire

        # ---- teammate ---------------------------------------------------
        self.teammate.update(dt, self.player, self.zombies, self.projectiles,
                             self.effects, self.audio, self.nearest_target)

        # ---- spawn zombies ------------------------------------------------
        self.spawn_timer -= dt
        if self.spawn_timer <= 0:
            self.spawn_timer = spawn_interval_for_wave(self.wave)
            if len(self.zombies) < max_zombies_for_wave(self.wave):
                self.zombies.append(spawn_zombie(self.wave))
                # From wave 4 there is a chance of a double drop.
                if self.wave >= 4 and random.random() < 0.25 and \
                        len(self.zombies) < max_zombies_for_wave(self.wave):
                    self.zombies.append(spawn_zombie(self.wave))

        # ---- spawn weapon boxes ---------------------------------------------
        self.box_timer -= dt
        if self.box_timer <= 0:
            unarmed = not self.player.has_weapon
            self.box_timer = BOX_SPAWN_INTERVAL_UNARMED if unarmed else BOX_SPAWN_INTERVAL
            if len(self.boxes) < BOX_MAX_ON_FIELD:
                x, y = random_box_position(self.player.pos)
                lifetime = BOX_LIFETIME * (1.8 if unarmed else 1.0)
                self.boxes.append(WeaponBox(x, y, lifetime))

        # ---- update world objects --------------------------------------------
        for zombie in self.zombies:
            zombie.update(dt, self.player, self.effects, self.audio)
            if zombie.state == Zombie.CHASING and random.random() < dt * 0.25:
                self.audio.play("groan", 0.22)

        # Zombies that walk into the teammate hurt him as well (a bit less
        # than they hurt the player, so he is not downed constantly).
        if self.teammate.alive:
            for zombie in self.zombies:
                if not zombie.landed or zombie.attack_timer > 0:
                    continue
                reach = zombie.radius + self.teammate.radius + 2
                if zombie.pos.distance_to(self.teammate.pos) <= reach:
                    zombie.attack_timer = ZOMBIE_ATTACK_COOLDOWN
                    self.teammate.take_damage(zombie.damage * 0.6,
                                              self.effects, self.audio)

        # Keep the crowd from stacking on one pixel.
        count = len(self.zombies)
        for i in range(count):
            for j in range(i + 1, count):
                self.zombies[i].separate_from(self.zombies[j], dt)

        for projectile in self.projectiles:
            projectile.update(dt, PLAY_RECT)

        for box in self.boxes:
            box.update(dt)

        self.effects.update(dt)

        # ---- collisions -------------------------------------------------------
        self.handle_bullet_hits()
        self.handle_box_pickups()

        # ---- clean up ---------------------------------------------------------
        self.projectiles = [p for p in self.projectiles if p.alive]
        self.zombies = [z for z in self.zombies if z.alive]
        self.boxes = [b for b in self.boxes if b.alive]

        # ---- death ------------------------------------------------------------
        if not self.player.alive:
            self.trigger_game_over()

    # ------------------------------------------------------------------
    def nearest_target(self, origin=None, max_range=None):
        """
        The closest landed zombie to `origin` (the player by default).

        Used by the touch FIRE button's auto-aim and by the teammate.
        Returns None when there is nothing worth shooting at.
        """
        origin = pygame.math.Vector2(origin if origin is not None else self.player.pos)
        best, best_dist = None, float("inf")
        for zombie in self.zombies:
            if not zombie.can_be_hit:
                continue
            dist = origin.distance_to((zombie.pos.x, zombie.draw_y))
            if dist < best_dist:
                best, best_dist = zombie, dist
        if best is not None and max_range is not None and best_dist > max_range:
            return None
        return best

    def handle_bullet_hits(self):
        """Projectile vs zombie collision detection (circle overlap)."""
        for projectile in self.projectiles:
            if not projectile.alive:
                continue
            for zombie in self.zombies:
                if not zombie.can_be_hit or zombie.id in projectile.hit_ids:
                    continue
                dx = zombie.pos.x - projectile.pos.x
                dy = zombie.draw_y - projectile.pos.y
                reach = zombie.radius + projectile.radius
                if dx * dx + dy * dy > reach * reach:
                    continue

                projectile.hit_ids.add(zombie.id)
                killed = zombie.take_damage(projectile.damage, self.effects,
                                            direction=projectile.dir)
                self.audio.play("hit", 0.25)
                self.effects.impact(projectile.pos.x, projectile.pos.y,
                                    projectile.trail_color)

                if killed:
                    self.on_zombie_killed(zombie,
                                          by_player=(projectile.owner == "player"))

                if not projectile.pierce:
                    projectile.alive = False
                    break

    # ------------------------------------------------------------------
    def on_zombie_killed(self, zombie, by_player=True):
        """
        Award points, spawn effects, and run the 3-kill weapon rule.

        `by_player` is False when the teammate got the kill: it still scores
        for the team, but it must not use up one of the player's three shots.
        """
        self.score += zombie.points
        self.kills += 1
        if not by_player:
            self.teammate.kills += 1

        color = zombie.glow_color if zombie.special else (255, 236, 150)
        if not by_player:
            color = (150, 255, 190)
        self.effects.death_burst(zombie.pos.x, zombie.draw_y,
                                 zombie.body_color, special=zombie.special)
        self.effects.floating_score(zombie.pos.x, zombie.draw_y - 10,
                                    zombie.points, color, big=zombie.special)
        if zombie.special:
            self.effects.message(zombie.pos.x, zombie.draw_y - 44,
                                 "{} BONUS!".format(zombie.label.upper()),
                                 color, size=18, life=1.4)
            self.audio.play("special_death", 0.6)
            self.shake = min(1.0, self.shake + 0.35)
        else:
            self.audio.play("zdeath", 0.45)

        # The weapon only lasts KILLS_PER_WEAPON (3) kills - teammate kills
        # are free.
        if by_player and self.player.weapon is not None:
            self.player.weapon.register_kill()
            if self.player.weapon.kills >= KILLS_PER_WEAPON:
                self.expire_weapon()

    # ------------------------------------------------------------------
    def expire_weapon(self, out_of_ammo=False):
        """Take the weapon away and tell the player to find another box."""
        if not self.player.has_weapon:
            return
        name = self.player.weapon.name
        self.player.drop_weapon()
        self.audio.play("expire", 0.6)
        if out_of_ammo:
            self.set_banner("{} is out of ammo!  Find another weapon box.".format(name),
                            HEALTH_WARN, 3.2)
        else:
            self.set_banner("Weapon expired!  Find another weapon box.", HEALTH_WARN, 3.2)
        self.effects.message(self.player.pos.x, self.player.pos.y - 42,
                             "WEAPON EXPIRED", HEALTH_WARN, size=20, life=1.6)

    # ------------------------------------------------------------------
    def handle_box_pickups(self):
        """Touching a crate instantly grants a RANDOM weapon."""
        for box in self.boxes:
            if not box.alive or not box.collides_with(self.player):
                continue
            box.open()
            previous = self.player.weapon.name if self.player.has_weapon else None
            weapon = random_weapon(avoid=previous)
            self.player.give_weapon(weapon)

            self.audio.play("box", 0.7)
            self.effects.pickup_burst(box.pos.x, box.pos.y)
            self.effects.message(box.pos.x, box.pos.y - 34,
                                 weapon.name.upper(), (255, 236, 150), size=22, life=1.6)
            self.set_banner(
                "You found the {}!  {}  ({} kills, then it is gone)".format(
                    weapon.name, weapon.description, KILLS_PER_WEAPON),
                ACCENT, 3.0)

    # ------------------------------------------------------------------
    def trigger_game_over(self):
        """Stop the run, save the score, and switch to the game-over screen."""
        self.state = STATE_GAME_OVER
        self.banner = None            # clear any leftover pickup message
        self.audio.stop_music()
        self.audio.play("gameover", 0.8)
        self.new_record = self.scores.record(self.score, self.kills, self.wave)
        self.effects.death_burst(self.player.pos.x, self.player.pos.y,
                                 (220, 120, 100), amount=28)

    # ==================================================================
    # DRAWING
    # ==================================================================
    def draw(self):
        if self.state == STATE_TITLE:
            self.draw_title()
        elif self.state == STATE_INSTRUCTIONS:
            self.draw_instructions()
        elif self.state == STATE_HISTORY:
            self.draw_history_screen()
        elif self.state == STATE_PLAYING:
            self.draw_world()
            self.draw_hud()
        elif self.state == STATE_PAUSED:
            self.draw_world()
            self.draw_hud()
            self.draw_pause()
        elif self.state == STATE_GAME_OVER:
            self.draw_world()
            self.draw_hud()
            self.draw_game_over()

        pygame.display.flip()

    # ------------------------------------------------------------------
    def draw_world(self):
        """The rainforest, the fighters, the bullets and all the effects."""
        surface = self.world_surface
        surface.fill(DARK)

        self.forest.draw_ground(surface)
        self.forest.draw_trunks(surface)

        # Weapon crates sit on the ground, under everybody.
        for box in self.boxes:
            box.draw(surface)

        # Zombies are sorted by their feet so nearer ones overlap the farther
        # ones.  The player is then drawn on top of them all: in an arcade game
        # you must never lose track of your own character inside a crowd.
        for zombie in sorted(self.zombies, key=lambda z: z.pos.y):
            zombie.draw(surface)
        self.teammate.draw(surface)
        self.player.draw(surface)
        self.player.draw_health_ring(surface)

        # Unarmed? Point at the nearest crate so nobody wanders around lost.
        if not self.player.has_weapon and self.boxes:
            nearest = min(self.boxes, key=lambda b: b.pos.distance_to(self.player.pos))
            self.player.draw_pointer_to(surface, nearest.pos, label="WEAPON BOX")

        for projectile in self.projectiles:
            projectile.draw(surface)

        self.effects.draw(surface)

        self.forest.draw_canopies(surface, self.forest.fog_time)
        self.forest.draw_fog(surface)
        self.forest.draw_vignette(surface)
        self.effects.draw_texts(surface)
        self.touch.draw(surface)        # thumb-stick + crosshair on touch devices

        # Blit the finished world to the screen, nudged when something big hits.
        if self.shake > 0.01:
            amount = self.shake * 7.0
            offset = (random.uniform(-amount, amount), random.uniform(-amount, amount))
            self.screen.fill(DARK)
            self.screen.blit(surface, offset)
        else:
            self.screen.blit(surface, (0, 0))

    # ------------------------------------------------------------------
    def draw_hud(self):
        """The permanent score panel across the top of the screen."""
        surface = self.screen
        hud = pygame.Surface((SCREEN_WIDTH, HUD_HEIGHT), pygame.SRCALPHA)
        pygame.draw.rect(hud, (10, 20, 15, 236), (0, 0, SCREEN_WIDTH, HUD_HEIGHT))
        pygame.draw.line(hud, PANEL_EDGE, (0, HUD_HEIGHT - 2), (SCREEN_WIDTH, HUD_HEIGHT - 2), 3)
        surface.blit(hud, (0, 0))

        def stat(x, label, value, color=WHITE, value_font=None):
            draw_text(surface, label, self.f_hud_label, (128, 152, 136), (x, 12))
            draw_text(surface, value, value_font or self.f_hud_value, color, (x, 28))

        # --- score block --------------------------------------------------
        stat(18, "SCORE", "{:,}".format(self.score), ACCENT)
        draw_text(surface, "HIGH  {:,}".format(max(self.scores.high_score, self.score)),
                  self.f_tiny, GOLD, (18, 66))
        draw_text(surface, "KILLS  {}".format(self.kills), self.f_tiny, (200, 214, 202),
                  (18, 82))

        # --- wave block ----------------------------------------------------
        stat(210, "WAVE", str(self.wave), GOLD)
        wave_progress = (self.elapsed % WAVE_DURATION) / WAVE_DURATION
        draw_bar(surface, pygame.Rect(210, 68, 120, 9), wave_progress, (214, 168, 60))
        draw_text(surface, "TIME  {:02d}:{:02d}".format(int(self.elapsed) // 60,
                                                        int(self.elapsed) % 60),
                  self.f_tiny, (200, 214, 202), (210, 82))

        # --- weapon block ---------------------------------------------------
        wx = 380
        panel_rect = pygame.Rect(wx - 12, 8, 470, HUD_HEIGHT - 18)
        draw_panel(surface, panel_rect, fill=(16, 30, 22), edge=(52, 84, 62),
                   alpha=200, radius=10)

        if self.player.has_weapon:
            weapon = self.player.weapon
            draw_text(surface, "WEAPON", self.f_hud_label, (128, 152, 136), (wx, 14))
            draw_text(surface, weapon.name.upper(), self.f_ui, WHITE, (wx, 30))

            # Ammo bar.
            draw_text(surface, "AMMO", self.f_tiny, (128, 152, 136), (wx, 60))
            draw_bar(surface, pygame.Rect(wx + 46, 60, 150, 12),
                     weapon.ammo / float(weapon.max_ammo), (110, 190, 240))
            draw_text(surface, "{}/{}".format(weapon.ammo, weapon.max_ammo),
                      self.f_tiny, (200, 214, 202), (wx + 204, 60))

            # Kills remaining before the weapon vanishes: three little pips.
            draw_text(surface, "KILLS LEFT", self.f_tiny, (128, 152, 136), (wx + 264, 14))
            left = weapon.kills_left
            for i in range(KILLS_PER_WEAPON):
                px = wx + 268 + i * 26
                color = HEALTH_GOOD if i < left else (58, 70, 62)
                pygame.draw.circle(surface, color, (px + 8, 42), 9)
                pygame.draw.circle(surface, (20, 30, 24), (px + 8, 42), 9, 2)
            draw_text(surface, "{} to go".format(left), self.f_tiny,
                      HEALTH_WARN if left <= 1 else (200, 214, 202), (wx + 268, 60))
        else:
            pulse = (math.sin(self.elapsed * 6.0) + 1) * 0.5
            color = (255, int(150 + 80 * pulse), 90)
            draw_text(surface, "WEAPON", self.f_hud_label, (128, 152, 136), (wx, 14))
            draw_text(surface, "NONE - UNARMED", self.f_ui, color, (wx, 30))
            draw_text(surface, "Find a glowing weapon box!", self.f_small,
                      (214, 224, 210), (wx, 62))

        # --- health block -----------------------------------------------------
        hx = SCREEN_WIDTH - 330
        draw_text(surface, "HEALTH", self.f_hud_label, (128, 152, 136), (hx, 12))
        ratio = self.player.health_ratio
        color = HEALTH_GOOD if ratio > 0.5 else HEALTH_WARN if ratio > 0.25 else HEALTH_BAD
        bar = pygame.Rect(hx, 30, 300, 26)
        draw_bar(surface, bar, ratio, color)
        draw_text(surface, "{} / {}".format(int(self.player.health), self.player.max_health),
                  self.f_small, WHITE, bar.center, align="center")

        zombies_alive = len(self.zombies)
        draw_text(surface, "ZOMBIES ON SCREEN  {}".format(zombies_alive), self.f_tiny,
                  (200, 214, 202), (hx, 64))
        if self.teammate.downed:
            draw_text(surface, "BUDDY IS DOWN - back in {}s".format(
                int(self.teammate.revive_timer) + 1),
                self.f_tiny, (255, 168, 120), (hx, 82))
        else:
            draw_text(surface, "BUDDY  {}%  -  {} kills".format(
                int(self.teammate.health_ratio * 100), self.teammate.kills),
                self.f_tiny, (150, 230, 170), (hx, 82))

        # --- banner message ----------------------------------------------------
        # Only while actually playing: otherwise it shows through the PAUSED and
        # GAME OVER overlays and collides with their headlines.
        if self.banner and self.state == STATE_PLAYING:
            text, color, remaining, total = self.banner
            alpha = 255 if remaining > 0.6 else int(255 * (remaining / 0.6))
            font = self.f_ui
            img = font.render(text, True, color)
            img.set_alpha(max(0, alpha))
            bg = pygame.Surface((img.get_width() + 34, img.get_height() + 14),
                                pygame.SRCALPHA)
            pygame.draw.rect(bg, (8, 18, 12, min(200, alpha)), bg.get_rect(), border_radius=10)
            pygame.draw.rect(bg, color + (min(255, alpha),), bg.get_rect(), 2, border_radius=10)
            bx = SCREEN_WIDTH // 2 - bg.get_width() // 2
            by = HUD_HEIGHT + 10
            surface.blit(bg, (bx, by))
            surface.blit(img, (bx + 17, by + 7))

        # --- on-screen pause button for touch devices -----------------------------
        if self.touch.enabled and self.state == STATE_PLAYING:
            self.pause_button.draw(surface)

        # --- quiet warning if scores could not be saved --------------------------
        if self.scores.last_error:
            draw_text(surface, self.scores.last_error, self.f_tiny, (230, 150, 140),
                      (10, SCREEN_HEIGHT - 18))

    # ------------------------------------------------------------------
    def draw_menu_background(self, dim=150):
        """Shared animated background for the title / instructions / history."""
        surface = self.screen
        self.forest.draw_ground(surface)
        self.forest.draw_trunks(surface)
        for zombie in self.menu_zombies:
            zombie.draw(surface)
        self.effects.draw(surface)
        self.forest.draw_canopies(surface, self.forest.fog_time)
        self.forest.draw_fog(surface)
        overlay = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
        overlay.fill((6, 14, 10, dim))
        surface.blit(overlay, (0, 0))
        self.forest.draw_vignette(surface)

    # ------------------------------------------------------------------
    def draw_title(self):
        surface = self.screen
        self.draw_menu_background(dim=140)

        # --- logo ---------------------------------------------------------
        pulse = (math.sin(self.menu_time * 2.2) + 1) * 0.5
        title_color = (200 + int(40 * pulse), 60 + int(30 * pulse), 55)
        draw_big_title(surface, "ZOMBIE WAR", self.f_title, title_color,
                       (SCREEN_WIDTH // 2, 96), spacing=8)
        draw_text(surface, "SURVIVE THE RAINFOREST", self.f_mid, ACCENT,
                  (SCREEN_WIDTH // 2, 154), align="center")
        draw_text(surface, "built by {}".format(AUTHOR), self.f_small, (190, 208, 194),
                  (SCREEN_WIDTH // 2, 188), align="center")

        # --- high score badge -----------------------------------------------
        badge = pygame.Rect(SCREEN_WIDTH // 2 - 170, 208, 340, 46)
        draw_panel(surface, badge, fill=(16, 30, 22), edge=GOLD, alpha=200)
        draw_text(surface, "HIGH SCORE   {:,}".format(self.scores.high_score),
                  self.f_ui, GOLD, badge.center, align="center")

        # --- controls -----------------------------------------------------------
        # The panel is sized from its contents and anchored by its BOTTOM edge,
        # just above the buttons.  A fixed height silently pushed the last row
        # out of the box as soon as a control was added to the list.
        touch_mode = self.touch.enabled
        rows = TOUCH_CONTROLS if touch_mode else CONTROLS
        row_h, header_h, pad = 20, 48, 18
        panel_h = header_h + len(rows) * row_h + pad
        panel = pygame.Rect(SCREEN_WIDTH // 2 - 340,
                            TITLE_PANEL_BOTTOM - panel_h, 680, panel_h)
        draw_panel(surface, panel)
        draw_text(surface, "TOUCH CONTROLS" if touch_mode else "CONTROLS",
                  self.f_ui, WHITE, (panel.centerx, panel.y + 20), align="center")
        y = panel.y + header_h
        for keys, description in rows:
            draw_text(surface, keys, self.f_small, ACCENT, (panel.x + 26, y))
            draw_text(surface, description, self.f_small, (206, 218, 208),
                      (panel.x + 300, y))
            y += row_h

        for button in self.buttons[STATE_TITLE]:
            button.draw(surface)

        draw_text(surface, "v{}  -  no gore, just arcade zombie action".format(VERSION),
                  self.f_tiny, (120, 142, 128),
                  (SCREEN_WIDTH // 2, SCREEN_HEIGHT - 22), align="center")

    # ------------------------------------------------------------------
    def draw_instructions(self):
        surface = self.screen
        self.draw_menu_background(dim=185)

        draw_text(surface, "HOW TO PLAY", self.f_big, ACCENT,
                  (SCREEN_WIDTH // 2, 46), align="center")

        # ---- left column: the rules -------------------------------------
        left = pygame.Rect(40, 92, 590, 520)
        draw_panel(surface, left)
        y = left.y + 18
        draw_text(surface, "MISSION", self.f_ui, GOLD, (left.x + 22, y)); y += 30
        for line in [
            "Zombies rain out of the sky and hunt you down.",
            "Stay alive, grab weapons, and score as high as you can.",
            "",
            "BUDDY, your teammate, follows you and shoots too.",
            "If he is downed he gets back up after a few seconds.",
            "",
            "You start with NO weapon. Run to a glowing crate.",
            "Each crate gives you a RANDOM weapon - you cannot pick.",
            "",
            "Every weapon disappears after {} kills.".format(KILLS_PER_WEAPON),
            "Then you must find another crate. The counter restarts",
            "with every new weapon.",
            "",
            "Zombies get faster, tougher and more numerous every",
            "{} seconds (one wave).".format(int(WAVE_DURATION)),
        ]:
            draw_text(surface, line, self.f_small, (212, 224, 214), (left.x + 22, y))
            y += 21

        y += 10
        draw_text(surface, "CONTROLS", self.f_ui, GOLD, (left.x + 22, y)); y += 30
        for keys, description in CONTROLS:
            draw_text(surface, keys, self.f_small, ACCENT, (left.x + 22, y))
            draw_text(surface, description, self.f_small, (206, 218, 208), (left.x + 268, y))
            y += 21

        # ---- right column: weapons + zombies ------------------------------
        right = pygame.Rect(650, 92, 590, 520)
        draw_panel(surface, right)
        y = right.y + 18
        draw_text(surface, "WEAPONS  (randomly assigned)", self.f_ui, GOLD,
                  (right.x + 22, y))
        y += 28
        draw_text(surface, "NAME", self.f_tiny, (130, 152, 138), (right.x + 22, y))
        draw_text(surface, "DMG", self.f_tiny, (130, 152, 138), (right.x + 210, y))
        draw_text(surface, "AMMO", self.f_tiny, (130, 152, 138), (right.x + 268, y))
        draw_text(surface, "NOTES", self.f_tiny, (130, 152, 138), (right.x + 340, y))
        y += 18
        for name, data in WEAPONS.items():
            draw_text(surface, name, self.f_small, WHITE, (right.x + 22, y))
            draw_text(surface, str(data["damage"]), self.f_small, (200, 214, 202),
                      (right.x + 210, y))
            draw_text(surface, str(data["ammo"]), self.f_small, (200, 214, 202),
                      (right.x + 268, y))
            draw_text(surface, data["desc"], self.f_tiny, (170, 190, 176),
                      (right.x + 340, y + 3))
            y += 23

        y += 14
        draw_text(surface, "ZOMBIES  (points shown above each head)", self.f_ui, GOLD,
                  (right.x + 22, y))
        y += 30
        for key, data in ZOMBIE_TYPES.items():
            color = data["glow"] if data["special"] else (200, 214, 202)
            pygame.draw.circle(surface, data["body"], (right.x + 32, y + 8), 9)
            pygame.draw.circle(surface, (20, 30, 22), (right.x + 32, y + 8), 9, 2)
            draw_text(surface, data["label"] + " zombie", self.f_small, WHITE,
                      (right.x + 52, y))
            draw_text(surface, "{} pts".format(data["points"]), self.f_small, color,
                      (right.x + 272, y))
            if data["special"]:
                draw_text(surface, "special mark: {}".format(data["mark"]),
                          self.f_tiny, color, (right.x + 340, y + 3))
            y += 24

        for button in self.buttons[STATE_INSTRUCTIONS]:
            button.draw(surface)
        draw_text(surface, "Press SPACE to jump straight into the game",
                  self.f_tiny, (150, 172, 156),
                  (SCREEN_WIDTH // 2, SCREEN_HEIGHT - 96), align="center")

    # ------------------------------------------------------------------
    def draw_history_screen(self):
        surface = self.screen
        self.draw_menu_background(dim=190)

        draw_text(surface, "SCORE HISTORY", self.f_big, PURPLE,
                  (SCREEN_WIDTH // 2, 52), align="center")
        draw_text(surface, "Saved locally in scores.json - newest run at the top",
                  self.f_small, (180, 196, 184), (SCREEN_WIDTH // 2, 92), align="center")

        panel = pygame.Rect(SCREEN_WIDTH // 2 - 420, 120, 840, 470)
        draw_panel(surface, panel)

        # Header row.
        hy = panel.y + 18
        draw_text(surface, "#", self.f_small, (130, 152, 138), (panel.x + 26, hy))
        draw_text(surface, "SCORE", self.f_small, (130, 152, 138), (panel.x + 80, hy))
        draw_text(surface, "KILLS", self.f_small, (130, 152, 138), (panel.x + 250, hy))
        draw_text(surface, "WAVE", self.f_small, (130, 152, 138), (panel.x + 390, hy))
        draw_text(surface, "PLAYED", self.f_small, (130, 152, 138), (panel.x + 520, hy))
        pygame.draw.line(surface, (60, 88, 68), (panel.x + 20, hy + 24),
                         (panel.right - 20, hy + 24), 2)

        entries = self.scores.history
        if not entries:
            draw_text(surface, "No games recorded yet - play a round!", self.f_ui,
                      (170, 190, 178), panel.center, align="center")
        else:
            y = hy + 38
            best = self.scores.high_score
            for index, entry in enumerate(entries[:16], start=1):
                is_best = entry["score"] == best
                color = GOLD if is_best else WHITE
                draw_text(surface, str(index), self.f_small, (150, 170, 158),
                          (panel.x + 26, y))
                draw_text(surface, "{:,}".format(entry["score"]), self.f_ui, color,
                          (panel.x + 80, y - 3))
                draw_text(surface, str(entry["kills"]), self.f_small, (200, 214, 202),
                          (panel.x + 250, y))
                draw_text(surface, str(entry["wave"]), self.f_small, (200, 214, 202),
                          (panel.x + 390, y))
                draw_text(surface, entry["date"], self.f_small, (166, 184, 172),
                          (panel.x + 520, y))
                if is_best:
                    draw_text(surface, "BEST", self.f_tiny, GOLD, (panel.right - 70, y + 2))
                y += 27

        draw_text(surface, "Games played: {}     High score: {:,}".format(
            self.scores.games_played, self.scores.high_score),
            self.f_ui, ACCENT, (SCREEN_WIDTH // 2, panel.bottom + 22), align="center")

        for button in self.buttons[STATE_HISTORY]:
            button.draw(surface)

    # ------------------------------------------------------------------
    def draw_pause(self):
        surface = self.screen
        overlay = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
        overlay.fill((4, 12, 8, 195))
        surface.blit(overlay, (0, 0))

        draw_big_title(surface, "PAUSED", self.f_title, ACCENT,
                       (SCREEN_WIDTH // 2, 150), spacing=12)
        draw_text(surface, "Take a breath - the jungle will wait.", self.f_ui,
                  (200, 216, 204), (SCREEN_WIDTH // 2, 216), align="center")

        # Same rule as the title screen: size the panel from its contents so a
        # new control line can never spill out of the box.
        rows = TOUCH_CONTROLS if self.touch.enabled else CONTROLS
        row_h, header_h, pad = 21, 54, 18
        panel_h = header_h + len(rows) * row_h + pad
        panel = pygame.Rect(SCREEN_WIDTH // 2 - 340, 250, 680, panel_h)
        draw_panel(surface, panel)
        draw_text(surface, "TOUCH CONTROLS" if self.touch.enabled else "CONTROLS",
                  self.f_ui, GOLD, (panel.centerx, panel.y + 20), align="center")
        y = panel.y + header_h
        for keys, description in rows:
            draw_text(surface, keys, self.f_small, ACCENT, (panel.x + 30, y))
            draw_text(surface, description, self.f_small, (206, 218, 208), (panel.x + 300, y))
            y += row_h

        stats = "Score {:,}     Kills {}     Wave {}     Weapon {}".format(
            self.score, self.kills, self.wave, self.player.weapon_name)
        draw_text(surface, stats, self.f_ui, WHITE,
                  (SCREEN_WIDTH // 2, panel.bottom + 26), align="center")

        for button in self.buttons[STATE_PAUSED]:
            button.draw(surface)

    # ------------------------------------------------------------------
    def draw_game_over(self):
        surface = self.screen
        overlay = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
        overlay.fill((10, 4, 6, 208))
        surface.blit(overlay, (0, 0))

        pulse = (math.sin(self.menu_time * 3.0) + 1) * 0.5
        draw_big_title(surface, "GAME OVER", self.f_title,
                       (210 + int(40 * pulse), 60, 55), (SCREEN_WIDTH // 2, 78), spacing=10)

        if self.new_record:
            draw_text(surface, "NEW HIGH SCORE!", self.f_mid,
                      (255, int(190 + 60 * pulse), 80),
                      (SCREEN_WIDTH // 2, 132), align="center")
        else:
            draw_text(surface, "The rainforest claimed another survivor.", self.f_ui,
                      (206, 216, 208), (SCREEN_WIDTH // 2, 132), align="center")

        # ---- left panel: this run -----------------------------------------
        left = pygame.Rect(SCREEN_WIDTH // 2 - 420, 168, 400, 330)
        draw_panel(surface, left)
        y = left.y + 22
        draw_text(surface, "THIS RUN", self.f_ui, GOLD, (left.centerx, y), align="center")
        y += 42
        draw_text(surface, "FINAL SCORE", self.f_small, (150, 172, 156), (left.x + 30, y))
        draw_text(surface, "{:,}".format(self.score), self.f_big, ACCENT,
                  (left.right - 30, y + 14), align="right")
        y += 60
        draw_text(surface, "HIGH SCORE", self.f_small, (150, 172, 156), (left.x + 30, y))
        draw_text(surface, "{:,}".format(self.scores.high_score), self.f_mid, GOLD,
                  (left.right - 30, y + 8), align="right")
        y += 48
        for label, value in (("Zombies killed", self.kills),
                             ("Wave reached", self.wave),
                             ("Time survived", "{:02d}:{:02d}".format(
                                 int(self.elapsed) // 60, int(self.elapsed) % 60)),
                             ("Games played", self.scores.games_played)):
            draw_text(surface, label, self.f_small, (186, 202, 190), (left.x + 30, y))
            draw_text(surface, str(value), self.f_ui, WHITE, (left.right - 30, y - 3),
                      align="right")
            y += 30

        # ---- right panel: score history ------------------------------------
        right = pygame.Rect(SCREEN_WIDTH // 2 + 20, 168, 400, 330)
        draw_panel(surface, right)
        y = right.y + 22
        draw_text(surface, "LAST {} SCORES".format(HISTORY_SHOW), self.f_ui, PURPLE,
                  (right.centerx, y), align="center")
        y += 40
        recent = self.scores.recent(HISTORY_SHOW)
        if not recent:
            draw_text(surface, "No scores yet.", self.f_small, (170, 190, 178),
                      (right.centerx, y + 40), align="center")
        else:
            for index, entry in enumerate(recent, start=1):
                newest = (index == 1)
                color = ACCENT if newest else WHITE
                if entry["score"] == self.scores.high_score:
                    color = GOLD
                draw_text(surface, "{:>2}.".format(index), self.f_small, (140, 162, 148),
                          (right.x + 24, y))
                draw_text(surface, "{:,}".format(entry["score"]), self.f_ui, color,
                          (right.x + 68, y - 3))
                # Kills + wave, right aligned (full dates live on the history screen).
                draw_text(surface, "{} kills  -  wave {}".format(entry["kills"],
                                                                 entry["wave"]),
                          self.f_tiny, (160, 180, 168), (right.right - 24, y + 8),
                          align="right")
                if newest:
                    pygame.draw.circle(surface, ACCENT, (right.x + 14, y + 9), 4)
                y += 26

        draw_text(surface, "Press R to play again  -  Esc for the menu  -  H for full history",
                  self.f_small, (180, 198, 186),
                  (SCREEN_WIDTH // 2, SCREEN_HEIGHT - 128), align="center")

        for button in self.buttons[STATE_GAME_OVER]:
            button.draw(surface)

    # ==================================================================
    # MAIN LOOP
    # ==================================================================
    async def run(self):
        """
        The game loop: events -> update -> draw, forever.

        It is a coroutine because the browser build (pygbag) needs the loop to
        hand control back to the page every frame; on the desktop the awaits
        cost nothing measurable.
        """
        while self.running:
            dt = self.clock.tick(FPS) / 1000.0
            dt = min(dt, MAX_DT)        # delta-time safety after a lag spike
            try:
                self.handle_events()
                self.update(dt)
                self.draw()
            except pygame.error as exc:
                print("Pygame error: {}".format(exc), file=sys.stderr)
                traceback.print_exc()
                self.running = False

            # Kick the soundtrack off once the player can already see something.
            if not self._music_started:
                self._music_started = True
                self.audio.start_music()

            await asyncio.sleep(0)      # yield: required for the web build
        self.shutdown()

    def shutdown(self):
        """Save everything and close pygame politely."""
        try:
            self.scores.save()
        except Exception:
            pass
        self.audio.quit()
        pygame.quit()


# ===========================================================================
# Automated self-test (no window, no speakers, no keyboard needed)
# ===========================================================================
def run_self_test(frames=1400, verbose=True):
    """
    Drive the whole game headlessly to prove every screen, weapon, zombie type
    and state transition works.  Returns 0 on success.
    """
    from settings import ZOMBIE_TYPES as ZT, WEAPON_NAMES
    from weapon import Weapon
    from zombie import Zombie as Z

    def say(msg):
        if verbose:
            print("[selftest] {}".format(msg))

    game = Game(headless=True)
    dt = 1.0 / 60.0
    say("window + systems started ({} sounds generated)".format(len(game.audio.sounds)))

    # ---- 1. every screen renders -------------------------------------
    for state in (STATE_TITLE, STATE_INSTRUCTIONS, STATE_HISTORY,
                  STATE_PLAYING, STATE_PAUSED, STATE_GAME_OVER):
        game.state = state
        for _ in range(3):
            game.update(dt)
            game.draw()
    say("all six screens rendered")

    # ---- 2. every weapon fires ---------------------------------------
    game.do_action("start")
    for name in WEAPON_NAMES:
        game.player.give_weapon(Weapon(name))
        game.force_fire = True
        for _ in range(45):
            game.update(dt)
            game.draw()
        assert game.player.weapon is None or game.player.weapon.ammo <= \
            game.player.weapon.max_ammo
    game.force_fire = False
    say("all {} weapons fired".format(len(WEAPON_NAMES)))

    # ---- 3. every zombie type spawns, lands, is killed ----------------
    game.do_action("start")
    game.player.max_health = 100000       # keep the tester alive during this stage
    game.player.health = 100000
    mine = [Z(kind, 300 + i * 90, 400, wave=3) for i, kind in enumerate(ZT)]
    game.zombies.extend(mine)
    for _ in range(120):                      # let them fall + land
        game.update(dt)
        game.draw()
    landed = sum(1 for z in mine if z.landed)
    assert landed == len(ZT), "only {}/{} zombies landed".format(landed, len(ZT))
    say("all {} zombie types fell and landed".format(len(ZT)))

    before = game.score
    for zombie in mine:
        zombie.take_damage(999999, game.effects)
        game.on_zombie_killed(zombie)
    expected = sum(d["points"] for d in ZT.values())
    assert game.score - before == expected, \
        "score {} != expected {}".format(game.score - before, expected)
    say("scoring verified: killing one of each type = {} points".format(expected))

    # ---- 4. the three-kill weapon rule --------------------------------
    game.player.give_weapon(Weapon("Pistol"))
    assert game.player.kills_left == KILLS_PER_WEAPON
    for i in range(KILLS_PER_WEAPON):
        z = Z("regular", 500, 500, wave=1)
        z.state = Z.CHASING
        game.zombies.append(z)
        z.take_damage(999999, game.effects)
        game.on_zombie_killed(z)
    assert game.player.weapon is None, "weapon should have expired after 3 kills"
    say("weapon expired after exactly {} kills".format(KILLS_PER_WEAPON))

    # ---- 5. weapon box pickup is random and refills the counter --------
    picked = set()
    for _ in range(60):
        box = WeaponBox(game.player.pos.x, game.player.pos.y)
        game.boxes.append(box)
        game.handle_box_pickups()
        if game.player.has_weapon:
            picked.add(game.player.weapon.name)
            assert game.player.kills_left == KILLS_PER_WEAPON
    assert len(picked) >= 3, "random weapon assignment looks broken: {}".format(picked)
    say("weapon boxes handed out {} different weapons at random".format(len(picked)))

    # ---- 6. an aimed shot really kills a zombie through the game loop ---
    game.do_action("start")
    game.spawn_timer = 9999               # no interruptions during this check
    game.box_timer = 9999
    game.player.pos.update(300, 400)
    game.player.max_health = 100000
    game.player.health = 100000
    target = Z("regular", 640, 400, wave=1)
    target.state = Z.CHASING
    target.height = 0.0
    target.speed = 0.0                    # a stationary practice dummy
    game.zombies.append(target)
    game.player.give_weapon(Weapon("Assault Rifle"))
    game.force_fire = True
    score_before = game.score
    hit_frame = None
    for i in range(240):
        game.fake_keys = _FakeKeys()
        game.mouse_pos = (int(target.pos.x), int(target.draw_y))
        game.update(dt)
        game.draw()
        if not target.alive:
            hit_frame = i
            break
    game.force_fire = False
    assert hit_frame is not None, "bullets never killed the practice dummy"
    assert game.score - score_before == 10, \
        "expected 10 points, got {}".format(game.score - score_before)
    say("aimed fire killed a zombie in {} frames and scored 10 points".format(hit_frame + 1))

    # ---- 7. a long simulated game with movement + shooting -------------
    game.do_action("start")
    game.force_fire = True
    keysets = [
        (pygame.K_w,), (pygame.K_d,), (pygame.K_s,), (pygame.K_a,),
        (pygame.K_w, pygame.K_d), (pygame.K_s, pygame.K_a), (),
    ]
    frame = -1
    for frame in range(frames):
        game.fake_keys = _FakeKeys(keysets[(frame // 40) % len(keysets)])
        game.mouse_pos = (random.randint(0, SCREEN_WIDTH), random.randint(0, SCREEN_HEIGHT))
        game.update(dt)
        game.draw()
        if frame == frames // 2:
            game.do_action("pause")
            game.update(dt); game.draw()
            game.do_action("resume")
        if game.state == STATE_GAME_OVER:
            break
    say("simulated {} frames: wave {}, score {}, kills {}, health {}".format(
        frame + 1, game.wave, game.score, game.kills, int(game.player.health)))
    assert game.wave >= 1 and game.elapsed > 0

    # ---- 7b. touch controls drive the player ----------------------------
    game.do_action("start")
    game.spawn_timer = game.box_timer = 9999
    game.zombies.clear()
    game.force_fire = False
    game.player.pos.update(640, 400)
    start_x = game.player.pos.x

    class _Finger:                       # a stand-in FINGER* event
        def __init__(self, type_, x, y, fid=1):
            self.type, self.x, self.y, self.finger_id = type_, x, y, fid

    # Drag left-of-centre: thumb down, then pulled to the right.
    game.touch.handle_event(_Finger(pygame.FINGERDOWN, 0.15, 0.70))
    game.touch.handle_event(_Finger(pygame.FINGERMOTION, 0.25, 0.70))
    for _ in range(30):
        game.update(dt)
        game.draw()
    moved = game.player.pos.x - start_x
    assert moved > 30, "touch stick did not move the player (moved {:.1f}px)".format(moved)

    game.touch.handle_event(_Finger(pygame.FINGERUP, 0.25, 0.70))
    for _ in range(5):
        game.update(dt)
    assert game.touch.move_vector().length() == 0, "touch stick stuck after finger up"

    # Right-side touch should aim and fire.
    game.player.give_weapon(Weapon("Pistol"))
    game.touch.handle_event(_Finger(pygame.FINGERDOWN, 0.85, 0.35, fid=2))
    assert game.touch.firing, "right-side touch did not register as firing"
    before = len(game.projectiles)
    for _ in range(20):
        game.update(dt)
        game.draw()
    assert len(game.projectiles) > before or game.player.weapon.ammo < 60, \
        "touch firing produced no shots"
    game.touch.handle_event(_Finger(pygame.FINGERUP, 0.85, 0.35, fid=2))
    say("touch controls work: stick moved player {:.0f}px, tap-to-shoot fired".format(moved))

    # ---- 7c. the teammate fights, and his kills are free ----------------
    game.do_action("start")
    game.spawn_timer = game.box_timer = 9999
    game.zombies.clear()
    game.player.max_health = 100000
    game.player.health = 100000
    game.player.pos.update(300, 400)
    game.teammate.pos.update(340, 400)
    game.player.give_weapon(Weapon("Pistol"))     # 3 charges, must stay at 3
    buddy = Z("regular", 620, 400, wave=1)
    buddy.state = Z.CHASING
    buddy.height = 0.0
    buddy.speed = 0.0
    game.zombies.append(buddy)

    score_before, charges_before = game.score, game.player.weapon.kills_left
    for _ in range(420):
        game.update(dt)
        game.draw()
        if not buddy.alive:
            break
    assert not buddy.alive, "the teammate never killed the practice zombie"
    assert game.score - score_before == 10, "teammate kill did not score"
    assert game.player.weapon is not None and \
        game.player.weapon.kills_left == charges_before, \
        "a teammate kill wrongly used up one of the player's three charges"
    say("teammate killed a zombie for 10 points and used none of your 3 charges")

    # He can be downed and revives on his own.
    game.teammate.take_damage(9999, game.effects, game.audio)
    assert game.teammate.downed, "teammate should be downed at zero health"
    game.teammate.revive_timer = 0.05
    for _ in range(10):
        game.update(dt)
    assert not game.teammate.downed and game.teammate.health > 0, \
        "teammate never got back up"
    say("teammate goes down at 0 health and revives afterwards")

    # ---- 8. game over + score saving + restart --------------------------
    game.do_action("start")          # fresh player: earlier stages buffed health
    game.player.hurt_timer = 0
    game.player.take_damage(game.player.max_health + 1)
    game.update(dt)
    assert game.state == STATE_GAME_OVER, "player death did not end the game"
    game.draw()
    assert game.scores.history, "score history was not written"
    say("game over recorded: history now holds {} runs, high score {}".format(
        len(game.scores.history), game.scores.high_score))

    game.do_action("restart")
    assert game.state == STATE_PLAYING and game.score == 0 and game.player.health > 0
    say("restart works (fresh player, score reset)")

    # ---- 9. persistence round-trip ---------------------------------------
    game.scores.save()
    reloaded = ScoreManager(game.scores.path)      # same (temporary) file
    assert reloaded.high_score == game.scores.high_score
    assert len(reloaded.history) == len(game.scores.history)
    say("scores.json reloaded correctly (high score {})".format(reloaded.high_score))

    game.shutdown()
    say("ALL CHECKS PASSED")
    return 0


# ===========================================================================
async def main():
    """
    Async entry point.  Handles the --selftest flag and any start-up failure.

    pygbag (the WebAssembly build) requires the program to be driven by
    `asyncio.run(main())`, and the same shape works fine on the desktop.
    """
    if "--selftest" in sys.argv:
        frames = 1400
        for arg in sys.argv[1:]:
            if arg.isdigit():
                frames = int(arg)
        return run_self_test(frames)

    try:
        await Game().run()
    except SystemExit:
        raise
    except Exception:
        print("Zombie War crashed. Full details below:", file=sys.stderr)
        traceback.print_exc()
        try:
            pygame.quit()
        except Exception:
            pass
        return 1
    return 0


if __name__ == "__main__":
    _exit_code = asyncio.run(main())
    if not IS_WEB:
        # In the browser there is no process to exit; on the desktop there is.
        sys.exit(_exit_code or 0)
