# CREDITS

## Code
- `src/dsp.js`, `src/rng.js`: Vendored from Claude-of-Duty (MIT) by Matt Shumer, via TortoiseWolfe/ScriptHammer.
- Original pianoMACHINE (2018): by TurtleWolfe. Dark tiles, yellow labels, keyboard-first play.
- wp-dev (2025): devscripts/metronome-app track pattern models by TortoiseWolfe.

## Audio

| Asset | Source / Details | License | Verified |
|---|---|---|---|
| `assets/piano/*.mp3` (13 notes: a1.mp3, a1s.mp3, b1.mp3, c1.mp3, c1s.mp3, c2.mp3, d1.mp3, d1s.mp3, e1.mp3, f1.mp3, f1s.mp3, g1.mp3, g1s.mp3) | ctc87/mp3-piano-sound via TurtleWolfe/pianoMACHINE | Unlicense | 2026-10-25 |
| `assets/fx/quarter-flip.mp3` | coin-3.wav by l_q, freesound.org/s/440957, CC BY 3.0 | CC BY 3.0 | 2026-10-25 |
| `assets/beds/404840_dark-hop-beet-f2.mp3` | freesound 404840 Dark hop beet f2 (.Andre_Onate), freesound.org/s/404840 | CC0 | 2026-10-25 |
| `assets/beds/409940_webandbotmadeloop.mp3` | freesound 409940 WebAndBotMadeLoop (gis_sweden), freesound.org/s/409940 | CC0 | 2026-10-25 |
| `assets/beds/435147_ambient-drone.mp3` | freesound 435147 Ambient Drone (kickhat), freesound.org/s/435147 | CC0 | 2026-10-25 |
| `assets/beds/441375_organ.mp3` | freesound 441375 Organ (Malinby), freesound.org/s/441375 | CC0 | 2026-10-25 |
| `assets/beds/214775_acid-bass.mp3` | freesound 214775 acid bass (SpankMyFilth), freesound.org/s/214775 | CC0 | 2026-10-25 |
| `assets/beds/214958_acid-mod-bass.mp3` | freesound 214958 acid bass (SpankMyFilth), freesound.org/s/214958 | CC0 | 2026-10-25 |
| `assets/jingle/manifest.json` | Public jingle manifest. AI-generated takes (ACE-Step 1.5, 110 BPM) | Public Domain / CC0 | 2026-10-26 |
| `tools/kits/` (kit tooling) | Renders per-robot stems with ACE-Step 1.5 (MIT). Output is "music made with AI", and the ID3 tag says so. | MIT (tool); output Public Domain / CC0 | 2026-10-26 |

All drums (kick, snare, closed hat, open hat, ride, clap, tom, tink, sub boom) are synthesized in real-time (`src/kit.js`) from DSP noise and resonator primitives; no drum samples are shipped.

## Visuals
- Band characters and portraits: the ScriptHammer band, TortoiseWolfe/wp-dev (2025), by Jonathan Pohlner. The tool that made the portraits is not recorded.
  - `assets/band/crash.webp`
  - `assets/band/ivory.webp`
  - `assets/band/chops.webp`
  - `assets/band/reed.webp`
  - `assets/band/brass.webp`
  - `assets/band/verse.webp`
  - `assets/band/form.webp`
  - `assets/band/logo.webp`
