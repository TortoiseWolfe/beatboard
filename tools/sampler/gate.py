#!/usr/bin/env python3
"""The check before anyone listens. Writes a pass/fail JSON for a rendered mix (and its per-member tracks).

    python3 tools/sampler/gate.py MIX.wav --out gate.json [--tracks TRACKS_DIR] [--bpm 94]
        [--songeval-result DIR/songeval-result.json --name MIXNAME --album ALBUMNAME [--margin 0.2]]

It fails the render for any of:
  * a cut-off note: sound still loud, then down more than 26 dB within 12 ms (tools/kits/cutoff.mjs, on the mix and on
    every member track, where a cut note is easiest to see);
  * clipping: a sample peak within 1 dB of full scale;
  * loudness outside -16 +/- 1 LUFS (take_factory.lufs);
  * timing: the beat grid's phase more than 5 ms off the grid (tools/kits/measure.mjs gridPhase). A mix whose beat is too
    weak to read is reported "unjudged" and does not pass silently: `pass` stays false unless --allow-unjudged;
  * SongEval (a music-quality model run by band-wagon-crew/tools/songeval.sh, internal ranking only) lower than the
    album take's mean score minus the margin. Not run = not passed, unless --allow-no-songeval.
"""
import argparse
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
KITS = os.path.abspath(os.path.join(HERE, "..", "kits"))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "..", "factory"))
import take_factory  # noqa: E402
import wavio  # noqa: E402

LUFS_TARGET, LUFS_TOL = -16.0, 1.0
PEAK_LIMIT_DB = -1.0
GRID_MS = 5.0
MIN_SHARP = 1.7
SONGEVAL_MARGIN = 0.2

GRID_JS = """
import { readFileSync } from 'node:fs';
import { decodeWav, gridPhase } from %r;
const { sampleRate, data } = decodeWav(readFileSync(process.argv[1]));
console.log(JSON.stringify(gridPhase(data, sampleRate, Number(process.argv[2]))));
"""


def songeval_mean(result, name):
    """Mean of the five SongEval axes for one file in songeval-result.json ({name: {axis: score}})."""
    axes = result[name]
    return sum(axes.values()) / len(axes)


def cutoff(path):
    r = subprocess.run(["node", os.path.join(KITS, "cutoff.mjs"), path], capture_output=True, text=True)
    if r.returncode not in (0, 1):
        raise RuntimeError("cutoff.mjs failed: " + (r.stderr or r.stdout)[-400:])
    res = json.loads(r.stdout)["results"][0]
    return {"file": os.path.basename(path), "cuts": res["cuts"], "first": res["first"]}


def grid(path, bpm):
    url = "file://" + os.path.join(KITS, "measure.mjs")
    r = subprocess.run(["node", "--input-type=module", "-e", GRID_JS % url, path, str(bpm)], capture_output=True, text=True)
    if r.returncode:
        raise RuntimeError("gridPhase failed: " + r.stderr[-400:])
    return json.loads(r.stdout)


def measure(mix, tracks, bpm):
    _, chans = wavio.read(mix)
    p = wavio.peak(chans)
    return {
        "lufs": take_factory.lufs(mix),
        "peak_db": 20 * __import__("math").log10(p) if p > 0 else -999.0,
        "cutoffs": [cutoff(t) for t in [mix] + list(tracks)],
        "grid": grid(mix, bpm),
    }


def judge(m, songeval=None, margin=SONGEVAL_MARGIN, allow_unjudged=False, allow_no_songeval=False):
    """Pure decision from measured numbers. `songeval` = (render_mean, album_mean) or None."""
    checks = {}
    cuts = sum(c["cuts"] for c in m["cutoffs"])
    checks["cutoffs"] = {"ok": cuts == 0, "count": cuts, "where": [c["file"] for c in m["cutoffs"] if c["cuts"]]}
    checks["clipping"] = {"ok": m["peak_db"] <= PEAK_LIMIT_DB, "peak_db": round(m["peak_db"], 2)}
    checks["loudness"] = {"ok": abs(m["lufs"] - LUFS_TARGET) <= LUFS_TOL, "lufs": round(m["lufs"], 2)}
    g = m["grid"]
    if g["sharpness"] >= MIN_SHARP:
        checks["timing"] = {"ok": abs(g["ms"]) <= GRID_MS, "ms": round(g["ms"], 2), "sharpness": round(g["sharpness"], 2)}
    else:
        checks["timing"] = {"ok": allow_unjudged, "status": "unjudged", "sharpness": round(g["sharpness"], 2)}
    if songeval is None:
        checks["songeval"] = {"ok": allow_no_songeval, "status": "not run"}
    else:
        render, album = songeval
        checks["songeval"] = {"ok": render >= album - margin, "render": round(render, 3), "album": round(album, 3), "margin": margin}
    return {"pass": all(c["ok"] for c in checks.values()), "checks": checks}


def main(argv):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("mix")
    ap.add_argument("--out", required=True)
    ap.add_argument("--tracks", help="folder of per-member .wav tracks to cut-off check as well")
    ap.add_argument("--bpm", type=float, default=94)
    ap.add_argument("--songeval-result")
    ap.add_argument("--name", help="the mix's name in the SongEval result (file name without extension)")
    ap.add_argument("--album", help="the album take's name in the SongEval result")
    ap.add_argument("--margin", type=float, default=SONGEVAL_MARGIN)
    ap.add_argument("--allow-unjudged", action="store_true")
    ap.add_argument("--allow-no-songeval", action="store_true")
    a = ap.parse_args(argv)
    tracks = sorted(os.path.join(a.tracks, f) for f in os.listdir(a.tracks) if f.endswith(".wav")) if a.tracks else []
    se = None
    if a.songeval_result:
        with open(a.songeval_result) as f:
            res = json.load(f)
        se = (songeval_mean(res, a.name), songeval_mean(res, a.album))
    verdict = judge(measure(a.mix, tracks, a.bpm), se, a.margin, a.allow_unjudged, a.allow_no_songeval)
    verdict["file"] = a.mix
    with open(a.out, "w") as f:
        json.dump(verdict, f, indent=1)
    print("PASS" if verdict["pass"] else "FAIL", json.dumps(verdict["checks"]))
    return 0 if verdict["pass"] else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
