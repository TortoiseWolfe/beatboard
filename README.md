# beatboard — keyboard beat machine

A browser-based, keyboard-first beat machine built on the look and keys of the 2018 **pianoMACHINE**, with a fresh Web Audio engine, an 8-track mixer driven from the keyboard, AI-generated jingle on its own track, and the "quarter flip" coin sound as a stinger.

**Play it:** `python3 -m http.server` from the repo root, then open `http://localhost:8000`

---

## What it is

- **8 tracks**: Kick, Snare, Hats (closed/open/ride), Perc (clap/tom/tink), Bass (sub boom + acid), Keys (13 piano notes), Bed (ambience + quarter flip), Jingle (hook + full takes at 110 BPM)
- **Keyboard-first**: every control is a physical key (`event.code`), works on any keyboard layout
- **Two layers**: **PLAY** (default) for performing, **MIX** (hold Space, latch with Tab) for mixer control
- **Sample-accurate timing**: lookahead clock (25 ms timer, 100 ms window) schedules on `AudioContext.currentTime`
- **Synthesized drums**: kick, snare, hats, ride, clap, tom, tink, boom — all built from DSP primitives, zero samples
- **Real samples**: 13 piano notes (Unlicense), 4 beds + 2 acid bass (CC0), quarter flip (CC BY 3.0), jingle (AI-generated, local-only until cleared)
- **Drag & drop**: drop any audio file onto a pad or mixer strip to replace its sample (stored in IndexedDB, never uploaded)
- **Learn mode**: press ` ` (backquote), click a pad/control, press a key to remap — saved to localStorage, export/import as JSON
- **The band**: 7 steampunk robot musicians from **ScriptHammer** (TortoiseWolfe/wp-dev, 2025) cast across the tracks

---

## Keyboard Map

### PLAY layer (default)

| Key | Action | Track |
|-----|--------|-------|
| `A` | Clap | 4 |
| `S` | Closed Hat | 3 |
| `D` | Kick | 1 |
| `F` | Open Hat | 3 |
| `G` | Boom (sub) | 5 |
| `H` | Ride | 3 |
| `J` | Snare | 2 |
| `K` | Tom | 4 |
| `L` | Tink | 4 |
| `Q`–`\` | Piano C–C² (Shift = sharp) | 6 |
| `Z` | Jingle Hook | 8 |
| `X` | Jingle Full Take (press again to stop) | 8 |
| `C` `B` `N` `M` | Reserved | — |
| `V` | Quarter Flip | 7 |
| `1`–`8` | Launch/stop track N on next bar (Shift = immediate) | 1–8 |
| `Enter` | Transport start/stop | — |
| `←` `→` | Tempo −1 / +1 BPM (Shift = ±5) | — |
| `↑` `↓` | Master level ±5% | — |
| `[` `]` | Previous / next preset | — |
| `Backspace` | Reset mixer | — |
| `Esc` | Stop everything | — |
| ` ` (backquote) | Learn mode | — |

### MIX layer (hold **Space**, **Tab** latches)

| Key | Action | Track |
|-----|--------|-------|
| `Q` `W` `E` `R` `T` `Y` `U` `I` | Mute | 1–8 |
| `A` `S` `D` `F` `G` `H` `J` `K` | Solo (Shift clears all) | 1–8 |
| `Z` `X` `C` `V` `B` `N` `M` `,` | Level +5% (Shift = −5%) | 1–8 |

---

## The Band (ScriptHammer)

| Track | Musician | Instrument | Role |
|-------|----------|------------|------|
| 1–4 | **Crash** | Full drum kit | Pulse Engine |
| 5 | **Chops** | Franken-guitar | Harmonic Hacker |
| 6 | **Ivory** | Jazz piano & vintage synths | Melody Master (band leader) |
| 7 | **Reed** | Alto sax | Lyrical Breeze |
| 8 | **Verse** (+ **Brass**) | Vocoder & Mic / Trumpet | Soul Node / Frontline Flame |
| Master | **Form** | Control surface | Architect |

Open **Meet the band** with `Shift+/` or the 👥 button.

---

## Running locally

```bash
cd beatboard
python3 -m http.server
# open http://localhost:8000
```

No build step, no npm, no dependencies. Static files only — works on GitHub Pages.

---

## Project structure

```
index.html          # keycap grid + 8 mixer strips
style.css           # dark keycap look, yellow labels
src/
  engine.js         # AudioContext, tracks, master, clock, quantized launch
  mixer.js          # mute/solo/level logic (pure)
  keymap.js         # layers, learn mode, localStorage
  kit.js            # synthesized drums from dsp primitives
  patterns.js       # 5 presets (Hip Hop first), deep-copied on load
  band.js           # 7 ScriptHammer band members + casting
  dsp.js, rng.js    # from ScriptHammer (MIT, mshumer/Claude-of-Duty)
  main.js           # UI wiring
assets/
  piano/            # 13 MP3 notes (Unlicense)
  beds/             # 4 ambience + 2 bass MP3 (CC0)
  fx/quarter-flip.mp3
  band/*.webp       # 7 portraits + logo (256px, <80KB each)
  jingle/manifest.json   # public (empty takes)
  jingle-local/     # gitignored, AI-generated takes
CREDITS.md          # every shipped asset with source/license/date
NOTICE              # MIT notice for vendored code
LICENSE             # MIT (TortoiseWolfe)
keymap.default.json # factory keymap
.nojekyll           # GitHub Pages
test/*.test.mjs     # node --test
```

---

## Credits

See [CREDITS.md](CREDITS.md) for every asset with source, license, and verification date.

**Key attributions:**
- Piano samples: ctc87/mp3-piano-sound (Unlicense)
- Dark hop beet f2: Andre_Onate, freesound.org/s/404840 (CC0)
- WebAndBotMadeLoop: gis_sweden, freesound.org/s/409940 (CC0)
- Ambient Drone: kickhat, freesound.org/s/435147 (CC0)
- Organ: Malinby, freesound.org/s/441375 (CC0)
- Acid bass: SpankMyFilth, freesound.org/s/214775 & /214958 (CC0)
- Quarter flip (coin-3): l_q, freesound.org/s/440957 (CC BY 3.0)
- DSP/RNG: mshumer/Claude-of-Duty (MIT) via ScriptHammer
- Band characters/portraits: ScriptHammer band, TortoiseWolfe/wp-dev (2025), by Jonathan Pohlner

---

## Why its own repo?

This project has its own public GitHub Pages URL so people can play and share it directly. It merges the best of pianoMACHINE, fccTempLate, wp-dev metronome-app, and ScriptHammer's audio toolkit into one amalgamation.