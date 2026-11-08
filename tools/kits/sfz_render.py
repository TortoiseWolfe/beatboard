#!/usr/bin/env python3
"""Render one MIDI file with SFZ instrument libraries, one MIDI channel per library, with sfizz_render in a container.

    python3 tools/kits/sfz_render.py --midi tune.mid --map map.json --out OUTDIR [--build]

map.json maps a MIDI channel to the .sfz file to play it, paths relative to --libs (default: the folder map.json is in):
    {"0": "karoryfer.meatbass/Programs/meatbass-sustain.sfz", "9": "virtuosity_drums/Programs/kit.sfz"}

Each channel is split with midisplit.py (note lengths and velocities kept), rendered to OUTDIR/chNN.wav at 48 kHz,
and every wav is checked with cutoff.mjs. Mixing is a separate step. Heavy work runs through docker-heavy.sh
(one job at a time across sessions, memory and CPU caps, a time limit); nothing is installed on the host.
"""
import argparse
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import midisplit  # noqa: E402

IMAGE = "beatboard-sfizz"
HEAVY = os.path.expanduser("~/.claude/scripts/docker-heavy.sh")


def render_command(channel, libs, out, sfz, sample_rate=48000, tag="sfz-render", timeout=1800):
    """Argument list for one channel: docker-heavy.sh --light ... -- docker run ... sfizz_render. Pure, so it can be tested."""
    cname = f"ch{channel:02d}"
    return [
        HEAVY, "--light", "--tag", f"{tag}-{cname}", "--timeout", str(timeout), "--",
        "docker", "run", "--rm",
        "-v", f"{os.path.abspath(libs)}:/libs:ro",
        "-v", f"{os.path.abspath(out)}:/out",
        IMAGE, "sfizz_render",
        "--sfz", f"/libs/{sfz}", "--midi", f"/out/{cname}.mid", "--wav", f"/out/{cname}.wav",
        "--samplerate", str(sample_rate), "--quality", "3", "--oversampling", "1",
    ]


def split(midi, out):
    ppq, events = midisplit.parse(open(midi, "rb").read())
    os.makedirs(out, exist_ok=True)
    found = midisplit.channels_with_notes(events)
    for ch in found:
        with open(os.path.join(out, f"ch{ch:02d}.mid"), "wb") as f:
            f.write(midisplit.write_channel(ppq, events, ch))
    return found


def main(argv):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--midi", required=True)
    ap.add_argument("--map", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--libs", help="folder the .sfz paths in map.json are relative to (default: folder of map.json)")
    ap.add_argument("--build", action="store_true", help="build the beatboard-sfizz image first (slow, once)")
    a = ap.parse_args(argv)
    mapping = {int(k): v for k, v in json.load(open(a.map)).items()}
    libs = a.libs or os.path.dirname(os.path.abspath(a.map))
    if a.build:
        subprocess.run([HEAVY, "--tag", "sfz-build", "--timeout", "3000", "--", "docker", "build", "-t", IMAGE,
                        os.path.join(HERE, "sfz")], check=True)
    found = split(a.midi, a.out)
    missing = [c for c in found if c not in mapping]
    if missing:
        print(f"no library mapped for channels {missing}: say so, never fake it", file=sys.stderr)
    for ch in found:
        if ch not in mapping:
            continue
        sfz = mapping[ch]
        if not os.path.isfile(os.path.join(libs, sfz)):
            print(f"missing {sfz}", file=sys.stderr)
            return 3
        subprocess.run(render_command(ch, libs, a.out, sfz), check=True)
    wavs = [os.path.join(a.out, f"ch{c:02d}.wav") for c in found if c in mapping]
    return subprocess.run(["node", os.path.join(HERE, "cutoff.mjs"), *wavs]).returncode


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
