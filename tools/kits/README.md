# Band Wagon song kits

Tools for rendering one tune as seven stems (one per robot) that line up, so the beat box can mute
and unmute each robot without the song drifting apart. All audio these tools write is
"music made with AI" (ACE-Step 1.5, MIT licence). The ID3 comment, copyright and title tags on every
MP3 say so, and `CREDITS.md` lists it.

## Files

| File | What it does |
|---|---|
| `kit_render.py` | Renders a kit through a local ACE-Step server (`http://127.0.0.1:8001`). `bed` makes the keys bed with text-to-music; `layer` adds one robot's part on top with Lego (output is that part alone); `kit` does the bed and all six layers and can be resumed. Logs video-memory peak and seconds per stem to `metrics.jsonl`. |
| `measure.mjs` | Checks a set of stems: equal length in samples, pairwise onset offset under 5 ms, loudness within 1 LU (BS.1770 integrated), no click at the loop seam. Can also normalise loudness and shift the whole kit onto the tempo grid. Exit code 0 only if all four pass. |
| `render2.py` | The first one-off renderer, kept for reference. |

```
node tools/kits/measure.mjs --bpm 112 --bars 16 a.wav b.wav ...
node tools/kits/measure.mjs --bpm 112 --bars 16 --grid-lock --normalise out/ --target -20 stems/*.wav
```

Tests: `npm test` (`test/kit-measure.test.mjs`).

## Findings (theme kit: 112 BPM, A minor, 16 bars, 48 kHz stereo)

- Lego fits an 8 GB card (RTX 3070 Ti) on both the base and the sft model; each layer is the new part alone.
- Video-memory peak, whole card with the desktop on it: bed 7660 MiB (base) / 6815 (sft); Lego layers up to 7889 MiB.
- Time: the bed about 90 s (first run includes model load); each Lego layer 12 to 21 s. A seven-stem kit takes about 3.5 minutes.
- Length: every stem is exactly 1645714 samples on both models.
- Loudness: raw spread 9.1 LU; after gain-only normalising to -20 LUFS it is 0.00 LU (brass would clip at -18).
- Seam: raw stems have no click; the grid-lock shift needs an 8 ms fade at both ends.
- Offset: on the sft model the stems that have a clear beat all agree at 0 ms, and the whole kit sits about 35 ms late against the tempo grid, so one kit-wide shift fixes it. On the base model the bed and drums sit about 28 ms apart and the offset check fails, so sft is the model to use.
- Pads and sustained parts have no beat to judge; the tool reports them as unjudged, never as passed.
