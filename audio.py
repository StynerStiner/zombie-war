"""
audio.py
========
All sound in Zombie War is SYNTHESIZED at start-up with plain Python maths —
no .wav or .mp3 downloads are required, so the game sounds identical on every
machine.

If you drop real files into `assets/sounds/<name>.wav` they are loaded instead
of the generated version, and `assets/music.ogg` / `assets/music.wav`
overrides the generated soundtrack.

Everything is wrapped in try/except: on a computer with no working audio
device the game simply runs silently instead of crashing.
"""

import array
import math
import os
import random

import pygame

from settings import ASSETS_DIR, SOUNDS_DIR

SAMPLE_RATE = 44100


# ---------------------------------------------------------------------------
# Tiny waveform helpers (all return lists of floats between -1.0 and 1.0)
# ---------------------------------------------------------------------------
def _envelope(i, total, attack=0.01, release=0.35):
    """Simple attack / sustain / release volume shape."""
    t = i / float(total)
    a = max(1e-6, attack)
    r = max(1e-6, release)
    if t < a:
        return t / a
    if t > 1.0 - r:
        return max(0.0, (1.0 - t) / r)
    return 1.0


def _tone(freq, duration, wave="sine", volume=0.5, attack=0.01, release=0.35,
          freq_end=None, vibrato=0.0, rate=SAMPLE_RATE):
    """Generate one note.  `freq_end` sweeps the pitch over the note."""
    total = max(1, int(duration * rate))
    out = [0.0] * total
    phase = 0.0
    for i in range(total):
        t = i / float(total)
        f = freq if freq_end is None else freq + (freq_end - freq) * t
        if vibrato:
            f *= 1.0 + math.sin(i * 0.0009 * vibrato) * 0.05
        phase += 2.0 * math.pi * f / rate
        if wave == "sine":
            s = math.sin(phase)
        elif wave == "square":
            s = 1.0 if math.sin(phase) >= 0 else -1.0
        elif wave == "saw":
            s = ((phase / math.pi) % 2.0) - 1.0
        elif wave == "tri":
            s = abs(((phase / math.pi) % 2.0) - 1.0) * 2.0 - 1.0
        else:                                     # noise
            s = random.uniform(-1.0, 1.0)
        out[i] = s * volume * _envelope(i, total, attack, release)
    return out


def _noise(duration, volume=0.5, attack=0.005, release=0.5, lowpass=0.0,
           rate=SAMPLE_RATE):
    """White noise with an optional cheap one-pole low-pass filter."""
    total = max(1, int(duration * rate))
    out = [0.0] * total
    prev = 0.0
    for i in range(total):
        s = random.uniform(-1.0, 1.0)
        if lowpass > 0.0:
            prev = prev + (s - prev) * lowpass
            s = prev
        out[i] = s * volume * _envelope(i, total, attack, release)
    return out


def _mix(*layers):
    """Overlay several sample lists (longest one wins) with soft clipping."""
    length = max((len(layer) for layer in layers), default=0)
    out = [0.0] * length
    for layer in layers:
        for i, value in enumerate(layer):
            out[i] += value
    for i, value in enumerate(out):
        out[i] = max(-1.0, min(1.0, value))
    return out


def _sequence(*chunks):
    """Play sample lists one after another."""
    out = []
    for chunk in chunks:
        out.extend(chunk)
    return out


# ---------------------------------------------------------------------------
class Audio:
    """Owns the mixer, the generated sound bank and the background music."""

    def __init__(self, enabled=True):
        self.enabled = False
        self.sounds = {}
        self.music_sound = None
        self.music_channel = None
        self.music_file = None
        self.muted = False
        # Deliberately quiet defaults - the game is played for long stretches.
        # Adjust live in-game with the - and = keys, or mute with M.
        self.sfx_volume = 0.34
        self.music_volume = 0.13
        self.error = None
        self._music_built = False
        self._last_played = {}
        self._min_gap = {          # stop rapid-fire weapons machine-gunning the mixer
            "rifle": 0.055, "flame": 0.075, "blaster": 0.09,
            "groan": 0.35, "bite": 0.12, "hit": 0.04,
        }

        if not enabled:
            return

        try:
            # pre_init must happen before pygame.mixer.init() for a clean buffer.
            if pygame.mixer.get_init() is None:
                pygame.mixer.pre_init(SAMPLE_RATE, -16, 2, 512)
                pygame.mixer.init()
            pygame.mixer.set_num_channels(24)
            pygame.mixer.set_reserved(1)      # channel 0 belongs to the music
            self.enabled = True
        except pygame.error as exc:
            self.error = "Audio disabled ({}).".format(exc)
            self.enabled = False
            return

        try:
            # Only the short effects are built now.  The music loop is long and
            # is generated on first play instead, so the title screen appears
            # without waiting for it (this matters a lot in the browser).
            self._build_bank()
            self._music_built = False
        except Exception as exc:                    # never let audio kill the game
            self.error = "Sound generation failed ({}).".format(type(exc).__name__)
            self.enabled = False

    # ------------------------------------------------------------------
    # Buffer -> pygame.mixer.Sound
    # ------------------------------------------------------------------
    def _make_sound(self, samples):
        """Convert a float sample list into a pygame Sound (16-bit, mixer-aware)."""
        init = pygame.mixer.get_init()
        if not init:
            return None
        _freq, fmt, channels = init
        if abs(fmt) != 16:
            return None                              # unusual mixer format: skip synth

        signed = fmt < 0
        peak = 32767 if signed else 32767
        buf = array.array("h" if signed else "H")
        mono = array.array("h" if signed else "H")
        for value in samples:
            v = int(max(-1.0, min(1.0, value)) * peak * 0.9)
            mono.append(v if signed else v + 32768)

        if channels <= 1:
            buf = mono
        else:
            buf = array.array(mono.typecode, bytes(len(mono) * 2 * channels))
            for ch in range(channels):
                buf[ch::channels] = mono
        try:
            return pygame.mixer.Sound(buffer=buf.tobytes())
        except pygame.error:
            return None

    def _register(self, name, samples):
        """Load assets/sounds/<name>.wav if it exists, otherwise use the synth."""
        for ext in (".wav", ".ogg"):
            path = os.path.join(SOUNDS_DIR, name + ext)
            if os.path.isfile(path):
                try:
                    self.sounds[name] = pygame.mixer.Sound(path)
                    return
                except pygame.error:
                    pass                              # fall through to the synth
        sound = self._make_sound(samples)
        if sound is not None:
            self.sounds[name] = sound

    # ------------------------------------------------------------------
    # The sound bank
    # ------------------------------------------------------------------
    def _build_bank(self):
        # HAUNTING, not harsh.  Two rules here:
        #  1. No white noise anywhere - the old hiss/static was the worst part.
        #  2. Pure sine/triangle tones, minor intervals, slow swells and a
        #     little vibrato, which reads as "eerie" rather than "aggressive".

        # ---- weapons -------------------------------------------------
        # Hollow, breathy tones. A weapon can fire ten times a second, so
        # these stay the quietest sounds in the game.
        self._register("pistol", _mix(
            _tone(392, 0.13, "sine", 0.15, attack=0.006, release=0.85, freq_end=196),
            _tone(196, 0.16, "sine", 0.07, attack=0.010, release=0.9, freq_end=98)))

        self._register("shotgun", _mix(
            _tone(175, 0.24, "sine", 0.18, attack=0.008, release=0.9, freq_end=62),
            _tone(87, 0.30, "tri", 0.09, attack=0.012, release=0.9, freq_end=44)))

        self._register("rifle", _tone(330, 0.075, "sine", 0.085,
                                      attack=0.005, release=0.85, freq_end=220))

        self._register("crossbow", _tone(740, 0.15, "tri", 0.12,
                                         attack=0.006, release=0.88, freq_end=330))

        # A soft airy whoosh built from a low tone, not from static.
        self._register("flame", _mix(
            _tone(150, 0.18, "sine", 0.06, attack=0.05, release=0.8, freq_end=110,
                  vibrato=22),
            _tone(75, 0.18, "sine", 0.04, attack=0.05, release=0.8)))

        self._register("blaster", _mix(
            _tone(330, 0.18, "sine", 0.12, attack=0.006, release=0.8, freq_end=660),
            _tone(660, 0.18, "tri", 0.05, attack=0.008, release=0.8, freq_end=1320)))

        # ---- zombies -------------------------------------------------
        # The centrepiece of the "haunted" feel: a wavering minor-second moan
        # that slides downward. Two detuned voices beat against each other.
        self._register("groan", _mix(
            _tone(138, 0.85, "sine", 0.12, attack=0.22, release=0.55,
                  freq_end=104, vibrato=13),
            _tone(146, 0.85, "sine", 0.09, attack=0.26, release=0.55,
                  freq_end=98, vibrato=9),
            _tone(69, 0.85, "sine", 0.07, attack=0.30, release=0.6)))

        self._register("bite", _mix(
            _tone(196, 0.15, "sine", 0.14, attack=0.006, release=0.85, freq_end=98),
            _tone(104, 0.18, "tri", 0.07, attack=0.010, release=0.9, freq_end=58)))

        # A ghostly sigh as a zombie dissolves.
        self._register("zdeath", _mix(
            _tone(440, 0.34, "sine", 0.12, attack=0.010, release=0.8,
                  freq_end=147, vibrato=7),
            _tone(220, 0.34, "sine", 0.06, attack=0.014, release=0.85, freq_end=73)))

        # Special zombies: a bright but still eerie bell figure (minor triad).
        self._register("special_death", _sequence(
            _tone(587, 0.11, "sine", 0.13, attack=0.006, release=0.7),
            _tone(698, 0.11, "sine", 0.13, attack=0.006, release=0.7),
            _tone(880, 0.30, "sine", 0.14, attack=0.006, release=0.85)))

        # Landing: a deep tolling thud, felt more than heard.
        self._register("land", _mix(
            _tone(98, 0.30, "sine", 0.17, attack=0.006, release=0.9, freq_end=44),
            _tone(49, 0.34, "sine", 0.08, attack=0.010, release=0.9)))

        # ---- pickups / UI --------------------------------------------
        # Distant music-box chime for opening a weapon box.
        self._register("box", _sequence(
            _tone(587, 0.11, "sine", 0.14, attack=0.008, release=0.65),
            _tone(880, 0.11, "sine", 0.14, attack=0.008, release=0.65),
            _tone(1175, 0.30, "sine", 0.12, attack=0.008, release=0.88)))

        self._register("expire", _sequence(
            _tone(466, 0.14, "tri", 0.12, attack=0.010, release=0.65),
            _tone(311, 0.28, "sine", 0.12, attack=0.010, release=0.88)))

        # New wave: a low warning bell, rising minor third.
        self._register("wave", _sequence(
            _tone(220, 0.18, "sine", 0.13, attack=0.014, release=0.6),
            _tone(262, 0.18, "sine", 0.13, attack=0.014, release=0.6),
            _tone(330, 0.36, "sine", 0.13, attack=0.014, release=0.85)))

        self._register("hurt", _mix(
            _tone(233, 0.26, "sine", 0.15, attack=0.006, release=0.85, freq_end=110),
            _tone(117, 0.26, "sine", 0.07, attack=0.010, release=0.9)))

        self._register("click", _tone(587, 0.07, "sine", 0.09,
                                      attack=0.006, release=0.8))

        # Game over: a slow, hollow descent with a long tail.
        self._register("gameover", _sequence(
            _tone(392, 0.38, "sine", 0.15, attack=0.04, release=0.5),
            _tone(311, 0.38, "sine", 0.15, attack=0.04, release=0.5),
            _tone(262, 0.42, "sine", 0.15, attack=0.04, release=0.5),
            _tone(196, 1.10, "sine", 0.16, attack=0.06, release=0.8, vibrato=5)))

        self._register("hit", _tone(523, 0.05, "sine", 0.05,
                                    attack=0.005, release=0.85, freq_end=392))

    # ------------------------------------------------------------------
    # Background music (a looping jungle-survival groove)
    # ------------------------------------------------------------------
    def _build_music(self):
        # Real music file wins if the player supplies one.
        for name in ("music.ogg", "music.wav", "music.mp3"):
            path = os.path.join(ASSETS_DIR, name)
            if os.path.isfile(path):
                self.music_file = path
                return

        # Otherwise synthesize a slow, haunting loop.
        #
        # The mood comes from three things, none of which involve noise:
        #   * a low drone of two sine waves a few cents apart, so they beat
        #     slowly against each other (that unsettled "wavering" sound),
        #   * a sparse minor-key bell melody with long decays, and
        #   * an occasional deep toll, like something distant in the jungle.
        beat = 60.0 / 58.0                     # slow, funeral-ish tempo

        # A natural minor progression: Am - F - Dm - E.
        roots = [55.00, 43.65, 36.71, 41.20]   # very low drone roots
        # Bell notes (A natural minor). None repeats the same shape twice, so
        # the loop does not feel mechanical.
        bells = [
            [880.00, None, 659.26, None],
            [698.46, None, None, 587.33],
            [587.33, None, 440.00, None],
            [659.26, None, None, 493.88],
        ]

        drone_track, bell_track, toll_track = [], [], []
        bar = beat * 4
        for index, root in enumerate(roots):
            # Two detuned drones per bar -> slow beating, very long swell.
            drone_track.extend(_mix(
                _tone(root, bar, "sine", 0.15, attack=0.35, release=0.45),
                _tone(root * 1.008, bar, "sine", 0.12, attack=0.40, release=0.45),
                _tone(root * 2.0, bar, "sine", 0.05, attack=0.45, release=0.5)))

            # Bells on the quarter notes that have a note defined.
            for note in bells[index]:
                if note is None:
                    bell_track.extend([0.0] * int(beat * SAMPLE_RATE))
                else:
                    hit = _mix(
                        _tone(note, beat * 0.95, "sine", 0.085,
                              attack=0.006, release=0.92),
                        _tone(note * 2.002, beat * 0.95, "sine", 0.025,
                              attack=0.010, release=0.92))
                    bell_track.extend(hit)
                    pad = int(beat * SAMPLE_RATE) - len(hit)
                    if pad > 0:
                        bell_track.extend([0.0] * pad)

            # One deep toll at the start of bars 1 and 3.
            if index % 2 == 0:
                toll = _tone(73.42, beat * 1.6, "sine", 0.10,
                             attack=0.02, release=0.9, freq_end=69.30)
                toll_track.extend(toll)
                toll_track.extend([0.0] * max(0, int(bar * SAMPLE_RATE) - len(toll)))
            else:
                toll_track.extend([0.0] * int(bar * SAMPLE_RATE))

        loop = _mix(drone_track, bell_track, toll_track)
        self.music_sound = self._make_sound(loop)

    # ------------------------------------------------------------------
    # Playback API
    # ------------------------------------------------------------------
    def play(self, name, volume=1.0):
        """Play a one-shot sound effect (safe to call even with audio off)."""
        if not self.enabled or self.muted:
            return
        sound = self.sounds.get(name)
        if sound is None:
            return
        gap = self._min_gap.get(name)
        now = pygame.time.get_ticks() / 1000.0
        if gap:
            if now - self._last_played.get(name, -99.0) < gap:
                return
        self._last_played[name] = now
        try:
            sound.set_volume(max(0.0, min(1.0, volume * self.sfx_volume)))
            sound.play()
        except pygame.error:
            pass

    def play_weapon(self, weapon_name):
        """Map a weapon to its sound effect."""
        from settings import WEAPONS
        key = WEAPONS.get(weapon_name, {}).get("sound", "pistol")
        self.play(key, volume=0.6)

    def start_music(self):
        if not self.enabled or self.muted:
            return
        if not self._music_built:
            self._music_built = True
            try:
                self._build_music()
            except Exception as exc:
                self.error = "Music generation failed ({}).".format(type(exc).__name__)
                return
        try:
            if self.music_file:
                pygame.mixer.music.load(self.music_file)
                pygame.mixer.music.set_volume(self.music_volume)
                pygame.mixer.music.play(-1)
            elif self.music_sound is not None and self.music_channel is None:
                self.music_channel = pygame.mixer.Channel(0)
                self.music_channel.set_volume(self.music_volume)
                self.music_channel.play(self.music_sound, loops=-1)
        except pygame.error as exc:
            self.error = "Music failed ({}).".format(exc)

    def stop_music(self):
        if not self.enabled:
            return
        try:
            if self.music_file:
                pygame.mixer.music.stop()
            elif self.music_channel is not None:
                self.music_channel.stop()
                self.music_channel = None
        except pygame.error:
            pass

    def set_music_volume(self, volume):
        self.music_volume = max(0.0, min(1.0, volume))
        try:
            if self.music_file:
                pygame.mixer.music.set_volume(self.music_volume)
            elif self.music_channel is not None:
                self.music_channel.set_volume(self.music_volume)
        except pygame.error:
            pass

    def change_volume(self, delta):
        """
        Nudge the overall loudness up or down (bound to - and = in game).
        Returns the new effect volume as a 0-100 percentage for the on-screen
        message.
        """
        self.sfx_volume = max(0.0, min(1.0, self.sfx_volume + delta))
        self.music_volume = max(0.0, min(0.6, self.music_volume + delta * 0.5))
        self.set_music_volume(self.music_volume)
        return int(round(self.sfx_volume * 100))

    def toggle_mute(self):
        """M key: silence everything (or bring it back)."""
        self.muted = not self.muted
        if self.muted:
            self.stop_music()
        else:
            self.start_music()
        return self.muted

    def quit(self):
        try:
            self.stop_music()
            pygame.mixer.quit()
        except pygame.error:
            pass
