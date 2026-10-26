#!/usr/bin/env python3
"""Render a Band Wagon song kit layer by layer with ACE-Step's Lego task.

The bed (Ivory, keys) is rendered first as a normal text-to-music task. Then each robot is asked,
one at a time, to add its part on top of everything rendered so far. Every step logs the peak
video-memory use and the wall-clock time, so the 8 GB question gets a number.

  kit_render.py bed   --out DIR --bpm 112 --bars 16 --seed 2601 --key "A minor"
  kit_render.py layer --out DIR --src bed.wav --robot crash --seed 3101 [--model-note base]
  kit_render.py kit   --out DIR --bpm 112 --bars 16 --seed 2601 --robots crash,chops,reed,brass,verse,form

The ACE-Step server runs in Docker (compose project jingle-audio, started through
~/.claude/scripts/docker-heavy.sh); this script only talks to http://127.0.0.1:8001.
Stems are written as 48 kHz stereo WAV so tools/kits/measure.mjs can check them exactly.
"""
import argparse, json, os, subprocess, sys, threading, time, urllib.parse, urllib.request

API = os.environ.get("ACESTEP_API", "http://127.0.0.1:8001")
AI_MARK = "music made with AI"

# One casting table for the kit tools; it mirrors src/band.js trackCasting and the plan's mapping of
# ACE-Step track names to the seven robots.
ROBOTS = {
    "ivory": {"track": "keyboard", "caption": "warm piano and music box chords, eerie steam calliope, minor key, dark carnival, spooky and playful"},
    "crash": {"track": "drums", "caption": "driving rock drum kit, kick and snare backbeat, closed hi-hats, tom fills, tight and punchy"},
    "chops": {"track": "guitar", "caption": "crunchy distorted electric guitar riff, palm-muted, minor key, dark carnival alternative rock"},
    "reed": {"track": "woodwinds", "caption": "breathy alto saxophone melody, smoky and mischievous, minor key"},
    "brass": {"track": "brass", "caption": "muted trumpet stabs and short melodic phrases, playful marching-band swagger, minor key"},
    "verse": {"track": "vocals", "caption": "robotic vocoder voice singing wordless melodic phrases, no lyrics, synthetic and eerie"},
    "form": {"track": "synth", "caption": "analog synthesizer pad and arpeggio, pulsing, glassy, eerie"},
}

BED_CAPTION = (
    "eerie steam calliope and music box intro building into a crunchy alternative rock chorus, "
    "minor key, dark carnival, mischievous, slick and spooky, instrumental, about {bpm} BPM"
)


def bar_seconds(bars, bpm):
    return bars * 4 * 60.0 / bpm


class VramPeak:
    """Samples whole-card memory once a second; the desktop's share is part of the number."""

    def __init__(self):
        self.peak = 0
        self.base = None
        self._stop = False
        self._t = threading.Thread(target=self._run, daemon=True)

    def _run(self):
        while not self._stop:
            try:
                v = int(subprocess.check_output(
                    ["nvidia-smi", "--query-gpu=memory.used", "--format=csv,noheader,nounits"]).split()[0])
                if self.base is None:
                    self.base = v
                self.peak = max(self.peak, v)
            except Exception:
                pass
            time.sleep(1)

    def __enter__(self):
        self._t.start()
        return self

    def __exit__(self, *a):
        self._stop = True
        self._t.join(timeout=3)


def _json(req, timeout=120):
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.load(r)


def submit(fields, src_audio=None):
    """Send one task. With a source clip it goes up as multipart (curl), otherwise as JSON."""
    if src_audio:
        cmd = ["curl", "-sS", "-X", "POST", API + "/release_task"]
        for k, v in fields.items():
            cmd += ["-F", f"{k}={v if not isinstance(v, bool) else str(v).lower()}"]
        cmd += ["-F", f"src_audio=@{src_audio}"]
        out = json.loads(subprocess.check_output(cmd, timeout=300))
    else:
        req = urllib.request.Request(API + "/release_task", json.dumps(fields).encode(),
                                     {"Content-Type": "application/json"})
        out = _json(req)
    return out["data"]["task_id"]


def wait(task_id, poll=3, limit=3600):
    t0 = time.time()
    while time.time() - t0 < limit:
        req = urllib.request.Request(API + "/query_result", json.dumps({"task_id_list": [task_id]}).encode(),
                                     {"Content-Type": "application/json"})
        q = _json(req)["data"][0]
        if q["status"] != 0:
            return q
        time.sleep(poll)
    raise TimeoutError(task_id)


def run_task(fields, dest, src_audio=None):
    """Run one task and write the first result to dest. Returns the metrics row."""
    with VramPeak() as vram:
        t0 = time.time()
        tid = submit(fields, src_audio)
        q = wait(tid)
        elapsed = time.time() - t0
    row = {"task": fields.get("task_type", "text2music"), "track": fields.get("track_name"),
           "status": q["status"], "seconds": round(elapsed, 1), "vram_peak_mib": vram.peak,
           "vram_idle_mib": vram.base, "seed": fields.get("seed")}
    if q["status"] != 1:
        row["error"] = q
        return row
    res = json.loads(q["result"])
    url = API + res[0]["file"]
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    urllib.request.urlretrieve(url, dest)
    row["file"] = dest
    row["metas"] = res[0].get("metas")
    return row


def to_wav48(src, dst):
    subprocess.check_call(["ffmpeg", "-y", "-loglevel", "error", "-i", src, "-ar", "48000", "-ac", "2",
                           "-c:a", "pcm_f32le", dst])


def trim_exact(src, dst, samples):
    """Cut to an exact sample count (pad with silence if the model came up short)."""
    subprocess.check_call(["ffmpeg", "-y", "-loglevel", "error", "-i", src, "-af",
                           f"apad=whole_len={samples},atrim=end_sample={samples}", "-c:a", "pcm_f32le", dst])


def mix(paths, dst):
    """Sum stems into one context clip (no normalisation, so relative levels survive)."""
    if len(paths) == 1:
        subprocess.check_call(["cp", paths[0], dst])
        return
    cmd = ["ffmpeg", "-y", "-loglevel", "error"]
    for p in paths:
        cmd += ["-i", p]
    cmd += ["-filter_complex", f"amix=inputs={len(paths)}:normalize=0", "-c:a", "pcm_f32le", dst]
    subprocess.check_call(cmd)


def to_mp3(src, dst):
    """The vote-player copy. Carries the machine-readable AI mark in its ID3 comment and title."""
    subprocess.check_call(["ffmpeg", "-y", "-loglevel", "error", "-i", src, "-c:a", "libmp3lame", "-q:a", "2",
                           "-metadata", f"comment={AI_MARK}", "-metadata", f"copyright={AI_MARK}",
                           "-metadata", "title=" + os.path.splitext(os.path.basename(dst))[0] + f" ({AI_MARK})", dst])


def base_fields(a, duration):
    return {"audio_duration": round(duration, 4), "bpm": a.bpm, "key_scale": a.key, "time_signature": "4",
            "vocal_language": "unknown", "audio_format": "wav", "batch_size": 1, "use_random_seed": False,
            "inference_steps": a.steps, "thinking": False, "use_cot_caption": False, "use_cot_language": False}


def do_bed(a):
    dur = bar_seconds(a.bars, a.bpm)
    f = base_fields(a, dur)
    f.update({"prompt": BED_CAPTION.format(bpm=a.bpm) + ", " + ROBOTS["ivory"]["caption"].split(",")[0] + " only",
              "lyrics": "[Instrumental]", "seed": a.seed})
    raw = os.path.join(a.out, "raw", "ivory.wav")
    row = run_task(f, raw)
    if row["status"] == 1:
        samples = round(a.bars * 4 * 60 * 48000 / a.bpm)
        os.makedirs(os.path.join(a.out, "stems"), exist_ok=True)
        wav = os.path.join(a.out, "raw", "ivory48.wav")
        to_wav48(raw, wav)
        trim_exact(wav, os.path.join(a.out, "stems", "ivory.wav"), samples)
    row["robot"] = "ivory"
    log(a, row)
    return row


def do_layer(a, src=None, robot=None):
    robot = robot or a.robot
    src = src or a.src
    spec = ROBOTS[robot]
    # Same length as the context clip: ask for its duration, then trim to its exact sample count.
    dur = bar_seconds(a.bars, a.bpm)
    f = base_fields(a, dur)
    f.update({"prompt": spec["caption"], "lyrics": "[Instrumental]", "task_type": "lego",
              "track_name": spec["track"], "seed": a.seed, "repainting_start": 0.0, "repainting_end": -1})
    raw = os.path.join(a.out, "raw", f"{robot}.wav")
    row = run_task(f, raw, src_audio=src)
    row["robot"] = robot
    if row["status"] == 1:
        samples = round(a.bars * 4 * 60 * 48000 / a.bpm)
        wav = os.path.join(a.out, "raw", f"{robot}48.wav")
        to_wav48(raw, wav)
        trim_exact(wav, os.path.join(a.out, "stems", f"{robot}.wav"), samples)
    log(a, row)
    return row


def do_kit(a):
    """Resumable: a stem already on disk is kept, so a stopped run picks up where it left off."""
    stems = [os.path.join(a.out, "stems", "ivory.wav")]
    if not os.path.exists(stems[0]):
        bed = do_bed(a)
        if bed["status"] != 1:
            return 1
    for i, robot in enumerate(a.robots.split(",")):
        done = os.path.join(a.out, "stems", f"{robot}.wav")
        if os.path.exists(done):
            stems.append(done)
            continue
        ctx = os.path.join(a.out, "raw", f"context{i}.wav")
        mix(stems, ctx)
        a.seed_robot = a.seed + 100 * (i + 1)
        saved = a.seed
        a.seed = a.seed_robot
        row = do_layer(a, src=ctx, robot=robot)
        a.seed = saved
        if row["status"] == 1:
            stems.append(os.path.join(a.out, "stems", f"{robot}.wav"))
    return 0


def log(a, row):
    print(json.dumps(row), flush=True)
    os.makedirs(a.out, exist_ok=True)
    with open(os.path.join(a.out, "metrics.jsonl"), "a") as fh:
        fh.write(json.dumps(row) + "\n")


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("cmd", choices=["bed", "layer", "kit"])
    p.add_argument("--out", required=True)
    p.add_argument("--bpm", type=int, default=112)
    p.add_argument("--bars", type=int, default=16)
    p.add_argument("--key", default="A minor")
    p.add_argument("--seed", type=int, default=2601)
    p.add_argument("--steps", type=int, default=50)
    p.add_argument("--src")
    p.add_argument("--robot", choices=sorted(ROBOTS))
    p.add_argument("--robots", default="crash,chops,reed,brass,verse,form")
    a = p.parse_args(argv)
    if a.cmd == "bed":
        return 0 if do_bed(a)["status"] == 1 else 1
    if a.cmd == "layer":
        return 0 if do_layer(a)["status"] == 1 else 1
    return do_kit(a)


if __name__ == "__main__":
    sys.exit(main())
