ZOMBIE WAR - assets folder
==========================
built by William

The game needs NOTHING in this folder. Every graphic is drawn with Pygame
shapes and every sound is generated in code at start-up, so the game runs
perfectly on a computer with no downloads at all.

This folder only exists so you CAN drop in your own media later:

assets/
  music.ogg          <- optional background music (also accepts music.wav / music.mp3)
  sounds/
      pistol.wav          weapon: pistol
      shotgun.wav         weapon: shotgun
      rifle.wav           weapon: assault rifle
      crossbow.wav        weapon: crossbow
      flame.wav           weapon: flamethrower
      blaster.wav         weapon: energy blaster
      groan.wav           zombie groan
      bite.wav            zombie attack
      zdeath.wav          zombie death
      special_death.wav   special (gold/red/purple) zombie death
      land.wav            zombie landing thump
      box.wav             weapon box opening
      expire.wav          weapon expired
      wave.wav            new wave
      hurt.wav            player hurt
      hit.wav             bullet impact
      click.wav           menu click
      gameover.wav        game over jingle

If a file above exists it is used automatically; if not, the built-in
synthesized sound plays instead. .ogg files also work for sound effects.
