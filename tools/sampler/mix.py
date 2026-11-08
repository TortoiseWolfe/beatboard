#!/usr/bin/env python3
"""Mix the per-member tracks into one band mix with ffmpeg: tone shaping per instrument, one shared room reverb,
gentle compression on the whole mix, then loudness to -16 LUFS with peaks held at least 1 dB under clipping.

    python3 tools/sampler/mix.py TRACKS_DIR OUT.wav [--lufs -16]

The reverb is a short room impulse (decaying noise, fixed seed so a mix is repeatable) applied with ffmpeg's `afir`.
Loudness comes from take_factory.lufs (the same EBU R128 reading the album takes use).
"""
import argparse
import os
import random
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "..", "factory"))
import take_factory  # noqa: E402  (lufs)
import wavio  # noqa: E402

TARGET_LUFS = -16.0
CEILING = 10 ** (-1.0 / 20)  # peaks at least 1 dB under clipping

# Per-member shaping: a high-pass to clear low mud, a low-pass for the darker junkyard sound, and a level trim in dB.
TONE = {
    "timber": ("highpass=f=35,lowpass=f=4000", 0.0),
    "switch": ("highpass=f=120,lowpass=f=6000", -3.0),
    "chops": ("highpass=f=110,lowpass=f=7000", -1.0),
    "ivory": ("highpass=f=90,lowpass=f=8000", -1.0),
    "reed": ("highpass=f=150,lowpass=f=7000", 0.0),
    "brass": ("highpass=f=180,lowpass=f=7500", 0.0),
    "chorus": ("highpass=f=200,lowpass=f=8000", -2.0),
    "crash": ("highpass=f=50,lowpass=f=12000", 0.0),
}
DEFAULT_TONE = ("highpass=f=60,lowpass=f=8000", 0.0)
REVERB_SEND_DB = -14.0


def room_impulse(path, rate=48000, seconds=0.7, seed=7):
    """A stereo room impulse: noise that dies away smoothly. Different noise per ear so the room is wide."""
    rng = random.Random(seed)
    n = int(rate * seconds)
    chans = [[rng.uniform(-1, 1) * (1 - i / n) ** 4 * (0.25 if i == 0 else 1.0) for i in range(n)] for _ in range(2)]
    scale = 0.9 / max(abs(v) for ch in chans for v in ch)
    wavio.write(path, rate, [[v * scale for v in ch] for ch in chans])


def filtergraph(names, ir_index):
    """The ffmpeg -filter_complex string for tracks named `names` (inputs 0..n-1) and the impulse at input ir_index."""
    parts = []
    for i, name in enumerate(names):
        eq, trim = TONE.get(name.lower(), DEFAULT_TONE)
        parts.append(f"[{i}:a]{eq},volume={trim}dB[t{i}]")
    ins = "".join(f"[t{i}]" for i in range(len(names)))
    parts.append(f"{ins}amix=inputs={len(names)}:normalize=0:duration=longest[dry]")
    parts.append("[dry]asplit[a][b]")
    parts.append(f"[b][{ir_index}:a]afir=dry=0:wet=1[w0]")
    parts.append(f"[w0]volume={REVERB_SEND_DB}dB[wet]")
    parts.append("[a][wet]amix=inputs=2:normalize=0:duration=first,"
                 "acompressor=threshold=-20dB:ratio=2:attack=30:release=250:makeup=1[out]")
    return ";".join(parts)


def mix_tracks(tracks, out_path, work_dir, target=TARGET_LUFS):
    """tracks: {member name: wav path}. Writes the 48 kHz 16-bit stereo mix and returns its loudness and peak."""
    os.makedirs(work_dir, exist_ok=True)
    names = sorted(tracks, key=str.lower)
    ir = os.path.join(work_dir, "room.wav")
    room_impulse(ir)
    raw = os.path.join(work_dir, "mix-raw.wav")
    cmd = ["ffmpeg", "-y", "-v", "error"]
    for n in names:
        cmd += ["-i", tracks[n]]
    cmd += ["-i", ir, "-filter_complex", filtergraph(names, len(names)), "-map", "[out]", "-ar", "48000", "-c:a", "pcm_f32le", raw]
    wavio.run(*cmd)
    gain = round(target - take_factory.lufs(raw), 2)
    wavio.run("ffmpeg", "-y", "-v", "error", "-i", raw, "-af",
              f"volume={gain}dB,alimiter=limit={CEILING:.4f}:level=disabled:attack=5:release=50",
              "-ar", "48000", "-c:a", "pcm_s16le", out_path)
    _, chans = wavio.read(out_path)
    return {"lufs": take_factory.lufs(out_path), "peak": wavio.peak(chans), "gain_db": gain}


def main(argv):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("tracks_dir")
    ap.add_argument("out")
    ap.add_argument("--lufs", type=float, default=TARGET_LUFS)
    a = ap.parse_args(argv)
    tracks = {os.path.splitext(f)[0]: os.path.join(a.tracks_dir, f) for f in sorted(os.listdir(a.tracks_dir)) if f.endswith(".wav")}
    if not tracks:
        print("no .wav tracks in", a.tracks_dir)
        return 2
    print(mix_tracks(tracks, a.out, os.path.join(os.path.dirname(os.path.abspath(a.out)), "_mixwork"), a.lufs))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
