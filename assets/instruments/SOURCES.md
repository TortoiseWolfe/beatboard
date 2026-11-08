# Instrument sound sources (Count Me In game music)

One professionally recorded library per band member. Every library is played through a standard SFZ sampler
(SFZ is a text map of recorded notes that samplers read), never a General MIDI sound font. Chosen Sat 7 Nov 2026
for the plan in `hub/internship/showcase/kids-game-music-plan.md`. Licences were read from each library's own
LICENSE file or readme on that day.

| Band member | Instrument | Library (SFZ program) | Licence | Range the game needs | Range the library records | Natural fade-out |
|---|---|---|---|---|---|---|
| Crash | Drums | Virtuosity Drums, Versilian Studios and Karoryfer Samples (`Programs/01-basic-kit.sfz`) | CC0 (free for any use) | kick, snare, closed hat, open hat (MIDI keys 36 to 46) | full jazz kit, up to 5 velocity layers | yes, whole hits ring out |
| Timber | Bass | Meatbass, a 1958 double bass played pizzicato, Karoryfer Samples (`Programs/pizz_three.sfz`) | CC0 | G1 to D3 (MIDI 31 to 50) | A0 to A3 (MIDI 21 to 57) | yes, plucked notes decay on their own |
| Switch | Pad | Cowsynth, a sample-based synth, Karoryfer Samples (`cowsynth_lonely_pad.sfz`) | CC0 | C3 to E4 (MIDI 48 to 64) | G2 to E4 (MIDI 43 to 64) | yes, pad release recordings |
| Chops | Rhythm guitar | Emilyguitar, an Epiphone guitar, Karoryfer Samples (`emily_clean.sfz`) | CC0 (readme: royalty-free, all uses) | G3 to C5 (MIDI 55 to 72) | C#2 to C7 (MIDI 37 to 96) | yes, plus string-release samples |
| Ivory | Piano | Scarypiano, Karoryfer Samples, built on University of Iowa piano recordings (`Programs/Scarypiano.sfz`) | CC0 | C4 to F5 (MIDI 60 to 77) | MIDI 22 to 101 | yes |
| Reed | Alto sax | Weresax, a real alto saxophone, Karoryfer Samples (`Programs/Sax.sfz`, forte and piano layers) | CC0 | G3 to D5 (MIDI 55 to 74) | MIDI 49 to 80 | yes |
| Brass | Trumpet | VSCO 2 Community Edition trumpet recordings, Versilian Studios (`Brass/Trumpet/sus`, 20 sustained notes) | CC0 | C4 to G5 (MIDI 60 to 79) | F2 to C5 (MIDI 41 to 72) | yes, recordings include the release |
| Chorus | Voices | epic-choir, a vowel choir of real singers from the VocalSet dataset (`S_ah.sfz`, soprano ah) | CC BY 4.0 (credit line below) | D4 to G5 (MIDI 62 to 79) | C4 to G#5 (MIDI 60 to 80) | yes, each singer keeps their own release |

## Things to know

- Trumpet: the library does not record above C5, so the five notes from C#5 to G5 are repitched up by at most 7 semitones. The gate and the ear decide whether that stays.
- VSCO ships recordings with no SFZ file, so the trumpet pack is built from its file names (note, velocity, round robin) by a tested helper in `tools/sampler/`.
- Chorus sings wordless vowels (ah), not the words of the hook. It is a section of 3 to 10 real singers per note.
- The Chorus credit line must travel with every pack and the preview page: "Choir samples derived from VocalSet (Wilkins, Seetharaman, Wahl, Pardo 2018), CC BY 4.0, https://doi.org/10.5281/zenodo.1442513".
- Tried and rejected: Caveman Cosmonaut "clarinet" and "trumpet" stops (organ sounds, not real instruments); SanicBoom/vsco-trumpet (no licence file); MTG Trumpet (samples sit on Freesound behind a login, licence unread); General MIDI sound fonts (the cheap Muzak sound).
- Sources on disk (not committed): `~/.claude/state/lanes/2026-11-05-bw-masters/sfz/lib/`.
