"""
settings.py
===========
Central configuration for ZOMBIE WAR (built by William).

Every "magic number" in the game lives here so the whole game can be
re-balanced from a single file.  Nothing in this module draws anything; it
only stores data plus two tiny helpers (font cache + zombie type picker).
"""

import os
import random

import pygame

# ---------------------------------------------------------------------------
# Identity
# ---------------------------------------------------------------------------
GAME_TITLE = "Zombie War"
AUTHOR = "William"
VERSION = "1.0"

# ---------------------------------------------------------------------------
# Window / timing
# ---------------------------------------------------------------------------
SCREEN_WIDTH = 1280
SCREEN_HEIGHT = 720
FPS = 60
MAX_DT = 0.05          # never let one frame simulate more than 50 ms (delta-time safety)

# Heads-up display bar across the top of the screen.
HUD_HEIGHT = 104

# The rectangle the player and zombies are allowed to walk inside.
PLAY_LEFT = 16
PLAY_TOP = HUD_HEIGHT + 12
PLAY_RIGHT = SCREEN_WIDTH - 16
PLAY_BOTTOM = SCREEN_HEIGHT - 16
PLAY_RECT = pygame.Rect(PLAY_LEFT, PLAY_TOP, PLAY_RIGHT - PLAY_LEFT, PLAY_BOTTOM - PLAY_TOP)

# ---------------------------------------------------------------------------
# File paths
# ---------------------------------------------------------------------------
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ASSETS_DIR = os.path.join(BASE_DIR, "assets")
SOUNDS_DIR = os.path.join(ASSETS_DIR, "sounds")
SCORES_FILE = os.path.join(BASE_DIR, "scores.json")

# ---------------------------------------------------------------------------
# Colour palette (arcade jungle look, no gore)
# ---------------------------------------------------------------------------
BLACK = (0, 0, 0)
WHITE = (245, 248, 245)
GREY = (150, 158, 152)
DARK = (14, 22, 18)
PANEL = (18, 30, 24)
PANEL_EDGE = (58, 96, 70)

JUNGLE_DARK = (18, 44, 30)
JUNGLE_MID = (28, 68, 42)
JUNGLE_LIGHT = (44, 96, 58)
DIRT = (72, 60, 40)
ROCK = (96, 102, 96)
FOG = (188, 214, 198)

ACCENT = (120, 230, 140)      # menu / highlight green
GOLD = (255, 206, 74)
RED = (232, 78, 68)
PURPLE = (186, 118, 255)
BLOOD_FREE_HIT = (200, 255, 210)   # pale green spark instead of blood
HEALTH_GOOD = (86, 214, 110)
HEALTH_WARN = (240, 190, 70)
HEALTH_BAD = (226, 74, 68)

# ---------------------------------------------------------------------------
# Fonts
# ---------------------------------------------------------------------------
# Comma separated list -> pygame picks the first one installed on the machine.
FONT_STACK = "consolas,menlo,dejavusansmono,couriernew,monospace"
TITLE_FONT_STACK = "impact,haettenschweiler,arialblack,dejavusans,arial"

_FONT_CACHE = {}


def get_font(size, bold=False, title=False):
    """Return a cached pygame Font.  Falls back to the built-in font safely."""
    key = (size, bold, title)
    cached = _FONT_CACHE.get(key)
    if cached is not None:
        return cached
    if not pygame.font.get_init():          # be safe if called very early
        pygame.font.init()
    try:
        font = pygame.font.SysFont(TITLE_FONT_STACK if title else FONT_STACK, size, bold=bold)
    except Exception:                        # pragma: no cover - very rare
        font = pygame.font.Font(None, size)
    _FONT_CACHE[key] = font
    return font


# ---------------------------------------------------------------------------
# Player
# ---------------------------------------------------------------------------
PLAYER_MAX_HEALTH = 100
PLAYER_SPEED = 265          # pixels per second
PLAYER_RADIUS = 16
PLAYER_HURT_IFRAMES = 0.85  # seconds of invulnerability after being hit
GRACE_SECONDS = 5.0         # calm before the first zombie falls

# ---------------------------------------------------------------------------
# Weapons
# ---------------------------------------------------------------------------
# damage      : damage per projectile
# fire_rate   : seconds between shots
# speed       : projectile speed (px/sec)
# range       : how far a projectile travels before vanishing (px)
# ammo        : rounds supplied by the weapon box
# pellets     : projectiles created per shot (shotgun = 6)
# spread      : random cone in degrees
# auto        : True = hold the fire button to keep shooting
# pierce      : projectile passes through zombies
KILLS_PER_WEAPON = 3        # <-- the "three kills and the weapon disappears" rule

WEAPONS = {
    "Pistol": {
        "damage": 26, "fire_rate": 0.30, "speed": 780, "range": 520, "ammo": 60,
        "pellets": 1, "spread": 2.0, "auto": False, "pierce": False,
        "bullet_radius": 4, "color": (255, 226, 140), "trail": (255, 170, 60),
        "sound": "pistol", "desc": "Reliable. Steady damage.",
    },
    "Shotgun": {
        "damage": 20, "fire_rate": 0.72, "speed": 700, "range": 300, "ammo": 30,
        "pellets": 6, "spread": 15.0, "auto": False, "pierce": False,
        "bullet_radius": 3, "color": (255, 190, 120), "trail": (240, 120, 50),
        "sound": "shotgun", "desc": "Six pellets, close range.",
    },
    "Assault Rifle": {
        "damage": 17, "fire_rate": 0.10, "speed": 940, "range": 640, "ammo": 150,
        "pellets": 1, "spread": 5.0, "auto": True, "pierce": False,
        "bullet_radius": 3, "color": (255, 244, 190), "trail": (255, 150, 70),
        "sound": "rifle", "desc": "Full auto. Hold to spray.",
    },
    "Crossbow": {
        "damage": 85, "fire_rate": 0.80, "speed": 1050, "range": 820, "ammo": 22,
        "pellets": 1, "spread": 0.5, "auto": False, "pierce": True,
        "bullet_radius": 4, "color": (226, 236, 246), "trail": (150, 190, 220),
        "sound": "crossbow", "desc": "Silent bolts that pierce.",
    },
    "Flamethrower": {
        "damage": 8, "fire_rate": 0.045, "speed": 380, "range": 200, "ammo": 260,
        "pellets": 1, "spread": 11.0, "auto": True, "pierce": True,
        "bullet_radius": 7, "color": (255, 168, 54), "trail": (255, 92, 40),
        "sound": "flame", "desc": "Short range fire wall.",
    },
    "Energy Blaster": {
        "damage": 45, "fire_rate": 0.26, "speed": 860, "range": 720, "ammo": 48,
        "pellets": 1, "spread": 0.0, "auto": True, "pierce": True,
        "bullet_radius": 8, "color": (140, 236, 255), "trail": (90, 160, 255),
        "sound": "blaster", "desc": "Piercing plasma bolts.",
    },
}
WEAPON_NAMES = list(WEAPONS.keys())

# ---------------------------------------------------------------------------
# Weapon boxes
# ---------------------------------------------------------------------------
BOX_SIZE = 34
BOX_SPAWN_INTERVAL = 3.2        # seconds between crate drops when the player is armed
BOX_SPAWN_INTERVAL_UNARMED = 1.3  # crates come faster when the player has nothing
BOX_MAX_ON_FIELD = 6            # plenty of crates around: weapons run out fast
BOX_LIFETIME = 34.0             # crates fade away after a while (unarmed players get longer)

# ---------------------------------------------------------------------------
# Zombies
# ---------------------------------------------------------------------------
# mark: None | "star" | "crown" | "diamond"  -> drawn above the special zombies
ZOMBIE_TYPES = {
    "regular": {
        "label": "Regular", "health": 60, "speed": 62, "radius": 18, "points": 10,
        "damage": 6, "body": (92, 146, 78), "limb": (66, 108, 56), "shirt": (72, 92, 120),
        "mark": None, "glow": None, "special": False,
    },
    "fast": {
        "label": "Fast", "health": 42, "speed": 122, "radius": 15, "points": 20,
        "damage": 5, "body": (132, 188, 92), "limb": (96, 146, 66), "shirt": (110, 84, 60),
        "mark": None, "glow": None, "special": False,
    },
    "strong": {
        "label": "Strong", "health": 135, "speed": 54, "radius": 22, "points": 30,
        "damage": 10, "body": (74, 122, 100), "limb": (52, 92, 76), "shirt": (58, 66, 84),
        "mark": None, "glow": None, "special": False,
    },
    "giant": {
        "label": "Giant", "health": 280, "speed": 40, "radius": 31, "points": 50,
        "damage": 15, "body": (104, 132, 76), "limb": (62, 84, 50), "shirt": (110, 84, 52),
        "mark": None, "glow": None, "special": False,
    },
    # ---- the three special marked zombies -------------------------------
    "gold": {
        "label": "Gold Marked", "health": 120, "speed": 98, "radius": 20, "points": 100,
        "damage": 8, "body": (186, 152, 60), "limb": (140, 112, 40), "shirt": (96, 78, 30),
        "mark": "star", "glow": GOLD, "special": True,
    },
    "red": {
        "label": "Red Marked", "health": 190, "speed": 112, "radius": 22, "points": 200,
        "damage": 11, "body": (168, 66, 60), "limb": (124, 46, 44), "shirt": (86, 34, 34),
        "mark": "crown", "glow": RED, "special": True,
    },
    "purple": {
        "label": "Purple Marked", "health": 265, "speed": 126, "radius": 24, "points": 300,
        "damage": 14, "body": (126, 78, 168), "limb": (94, 56, 128), "shirt": (62, 40, 88),
        "mark": "diamond", "glow": PURPLE, "special": True,
    },
}

ZOMBIE_ATTACK_COOLDOWN = 0.85   # seconds between bites
ZOMBIE_FALL_GRAVITY = 1500      # px/sec^2 while dropping out of the sky
ZOMBIE_FALL_START_HEIGHT = (420, 780)   # how high above the ground they appear

# ---------------------------------------------------------------------------
# Difficulty curve
# ---------------------------------------------------------------------------
WAVE_DURATION = 24.0            # seconds per wave / level
SPAWN_INTERVAL_START = 1.95     # seconds between zombie drops on wave 1
SPAWN_INTERVAL_MIN = 0.28
SPAWN_INTERVAL_STEP = 0.11      # subtracted per wave
SPEED_BONUS_PER_WAVE = 0.055    # +5.5% zombie speed per wave
HEALTH_BONUS_PER_WAVE = 0.09    # +9% zombie health per wave
MAX_ZOMBIES_BASE = 5
MAX_ZOMBIES_PER_WAVE = 3
MAX_ZOMBIES_CAP = 42


def spawn_interval_for_wave(wave):
    """Seconds between zombie drops for the given wave (never below the floor)."""
    return max(SPAWN_INTERVAL_MIN, SPAWN_INTERVAL_START - (wave - 1) * SPAWN_INTERVAL_STEP)


def max_zombies_for_wave(wave):
    """How many zombies may be alive at once during this wave."""
    return min(MAX_ZOMBIES_CAP, MAX_ZOMBIES_BASE + (wave - 1) * MAX_ZOMBIES_PER_WAVE)


def pick_zombie_type(wave, rng=random):
    """
    Randomly choose a zombie type for the given wave.

    Ordinary zombies dominate early; the three special marked zombies start
    showing up occasionally from wave 2 and get slightly more common later.
    """
    # The three marked "zombie kings" (gold / red / purple) are the fun part,
    # so they show up from the very first wave and become common quickly.
    weights = {
        "regular": max(10.0, 40.0 - wave * 3.0),
        "fast": 10.0 + wave * 1.8,
        "strong": max(0.0, (wave - 1) * 3.4),
        "giant": max(0.0, (wave - 2) * 2.2),
        "gold": min(20.0, 6.0 + wave * 1.6),
        "red": 0.0 if wave < 2 else min(14.0, 3.0 + wave * 1.2),
        "purple": 0.0 if wave < 3 else min(10.0, 2.0 + wave * 0.9),
    }
    names = [n for n, w in weights.items() if w > 0]
    values = [weights[n] for n in names]
    # random.choices returns a list; take the single element.
    return rng.choices(names, weights=values, k=1)[0]


# ---------------------------------------------------------------------------
# Score storage
# ---------------------------------------------------------------------------
HISTORY_KEEP = 20      # how many runs we store in scores.json
HISTORY_SHOW = 10      # how many we show on the game-over screen

# ---------------------------------------------------------------------------
# Game states
# ---------------------------------------------------------------------------
STATE_TITLE = "title"
STATE_INSTRUCTIONS = "instructions"
STATE_PLAYING = "playing"
STATE_PAUSED = "paused"
STATE_GAME_OVER = "game_over"
STATE_HISTORY = "history"

CONTROLS = [
    ("W A S D  /  Arrow Keys", "Walk around the rainforest"),
    ("SPACEBAR  /  Left Click", "Shoot toward the mouse cursor"),
    ("MOUSE", "Aim your weapon"),
    ("P", "Pause / resume the game"),
    ("R", "Restart after game over"),
    ("M   and   - / =", "Mute, and turn the sound down / up"),
    ("ESC", "Back to menu  (quit from the title screen)"),
]

# Shown instead of the list above once a touch screen is detected.
TOUCH_CONTROLS = [
    ("DRAG - left half", "Walk: a thumb-stick appears under your thumb"),
    ("HOLD - right half", "Aim and shoot at that spot"),
    ("BOTH AT ONCE", "Walk and shoot at the same time"),
    ("II  button (top right)", "Pause the game"),
    ("TAP a button", "Choose it  (tap anywhere here to start)"),
]
