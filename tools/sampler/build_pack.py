#!/usr/bin/env python3
"""Build a sound pack per band member from a recorded SFZ library.

For each member, one note is rendered through sfizz (the library's own program, its own release recordings) at every
few semitones across the member's range. Each file keeps the note's full natural tail: only silence at the very end is
trimmed. Files are exported as OGG and MP3, and pack.json records, per note, its key, files, hold time, length, release
time and gain, plus the member's licence and credit line.

    python3 tools/sampler/build_pack.py --lib ~/.../sfz/lib --out PACKS [--members Timber,Brass]

Needs the beatboard-sfizz container image (tools/sampler/Dockerfile) and ffmpeg on the host.
"""
import argparse
import json
import math
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
import midisplit
import sfizz
import vsco
import wavio

HERE = os.path.dirname(os.path.abspath(__file__))
RATE = 48000
SILENCE_DB = -66.0       # a tail is "silent" below this; only what is below it, at the very end, is trimmed
TARGET_PEAK_DB = -3.0    # every note is brought to the same peak so no note is a surprise in level
MAX_FILE_BYTES = 50 * 1024 * 1024  # Base44's live upload limit


def load_members(path=None):
    with open(path or os.path.join(HERE, "members.json")) as f:
        return json.load(f)


def pitch_grid(lo, hi, step):
    """Keys lo, lo+step, ... always ending on hi, so the top of the range is a recorded note."""
    keys = list(range(lo, hi + 1, step))
    if keys[-1] != hi:
        keys.append(hi)
    return keys


def member_keys(member):
    return list(member["keys"]) if member.get("keys") else pitch_grid(member["range"][0], member["range"][1], member["step"])


def to_db(x):
    return 20 * math.log10(x) if x > 0 else -999.0


def trim_tail(chans, rate=RATE, floor_db=SILENCE_DB, pad_ms=30):
    """Cut trailing silence only: the file ends pad_ms after the last sample louder than floor_db."""
    floor = 10 ** (floor_db / 20)
    n = len(chans[0])
    last = 0
    for ch in chans:
        i = n - 1
        while i > last and abs(ch[i]) < floor:
            i -= 1
        last = max(last, i)
    end = min(n, last + 1 + int(rate * pad_ms / 1000))
    return [ch[:end] for ch in chans]


def gain_to_peak(chans, target_db=TARGET_PEAK_DB):
    """Gain in dB that puts the loudest sample at target_db (0 for silence)."""
    p = wavio.peak(chans)
    return round(target_db - to_db(p), 2) if p > 0 else 0.0


def apply_gain(chans, gain_db):
    g = 10 ** (gain_db / 20)
    return [[v * g for v in ch] for ch in chans]


def note_entry(member, key, chans, rate, gain_db, files):
    length = len(chans[0]) / rate
    oneshot = member["kind"] == "oneshot"
    hold = min(member["hold_s"], length)
    return {"key": key, "files": files, "hold_s": round(hold, 3), "length_s": round(length, 3),
            "release_s": 0.0 if oneshot else round(max(0.0, length - hold), 3), "gain_db": gain_db}


def pack_json(member, notes):
    return {"member": member["name"], "instrument": member["instrument"], "channel": member["channel"],
            "oneshot": member["kind"] == "oneshot", "sample_rate": RATE,
            "licence": member["licence"], "credit": member["credit"], "program": member["program"],
            "notes": {str(n["key"]): {k: v for k, v in n.items() if k != "key"} for n in notes}}


def sfz_for(member, lib_dir, work_dir):
    """Path (inside the container, with lib_dir mounted at /lib and work_dir at /work) of the SFZ to play."""
    prog = member["program"]
    if prog.endswith(".sfz"):
        return "/lib/" + prog
    names = sorted(n for n in os.listdir(os.path.join(lib_dir, prog, "sus")) if n.endswith(".wav"))
    text = vsco.sfz_text(names, sample_dir_in_sfz="/lib/%s/sus" % prog, top=member["range"][1])
    path = os.path.join(work_dir, member["name"].lower() + "-generated.sfz")
    with open(path, "w") as f:
        f.write(text)
    return "/work/" + os.path.basename(path)


def container_render(lib_dir, work_dir, tag):
    """The real renderer: sfizz_render in the container. Returns render(sfz_in_container, midi_bytes, wav_path)."""
    def render(sfz, midi, wav_path):
        base = os.path.splitext(os.path.basename(wav_path))[0]
        mid_path = os.path.join(work_dir, base + ".mid")
        with open(mid_path, "wb") as f:
            f.write(midi)
        inner = sfizz.render_args(sfz, "/work/" + base + ".mid", "/work/" + base + "-raw.wav", rate=RATE)
        sfizz.run(sfizz.container_command(inner, [(lib_dir, "/lib", "ro"), (work_dir, "/work", "rw")], tag=tag))
        wavio.to_pcm16(os.path.join(work_dir, base + "-raw.wav"), wav_path, rate=RATE, channels=2)
    return render


def ffmpeg_export(wav, ogg, mp3):
    wavio.run("ffmpeg", "-y", "-v", "error", "-i", wav, "-c:a", "libvorbis", "-q:a", "6", ogg)
    wavio.run("ffmpeg", "-y", "-v", "error", "-i", wav, "-c:a", "libmp3lame", "-b:a", "192k", mp3)


def build_member(member, sfz, out_dir, work_dir, render, export=ffmpeg_export, keys=None):
    """Render, trim, level and export every note of one member. Returns the pack.json dict."""
    os.makedirs(out_dir, exist_ok=True)
    slug = member["name"].lower()
    notes = []
    for key in keys or member_keys(member):
        wav = os.path.join(work_dir, f"{slug}-{key}.wav")
        end_s = member["hold_s"] + member["tail_s"]
        midi = midisplit.make_midi([(0.0, member["hold_s"], key, member["velocity"])], end_s=end_s)
        render(sfz, midi, wav)
        rate, chans = wavio.read(wav)
        chans = trim_tail(chans, rate)
        if wavio.peak(chans) == 0:
            raise RuntimeError(f"{member['name']} key {key}: the sampler wrote silence (wrong program or key outside its range?)")
        gain = gain_to_peak(chans)
        chans = apply_gain(chans, gain)
        fixed = os.path.join(work_dir, f"{slug}-{key}-final.wav")
        wavio.write(fixed, rate, chans)
        files = {"ogg": f"{slug}-{key}.ogg", "mp3": f"{slug}-{key}.mp3"}
        export(fixed, os.path.join(out_dir, files["ogg"]), os.path.join(out_dir, files["mp3"]))
        for name in files.values():
            size = os.path.getsize(os.path.join(out_dir, name))
            if size >= MAX_FILE_BYTES:
                raise RuntimeError(f"{name} is {size} bytes, over the 50 MB limit")
        notes.append(note_entry(member, key, chans, rate, gain, files))
    pack = pack_json(member, notes)
    with open(os.path.join(out_dir, "pack.json"), "w") as f:
        json.dump(pack, f, indent=1)
    return pack


def main(argv):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--lib", required=True, help="folder holding the SFZ libraries")
    ap.add_argument("--out", required=True, help="folder to write packs into (one subfolder per member)")
    ap.add_argument("--members", help="comma-separated member names (default: all)")
    ap.add_argument("--config", help="members.json (default: next to this file)")
    a = ap.parse_args(argv)
    cfg = load_members(a.config)
    want = {m.strip().lower() for m in a.members.split(",")} if a.members else None
    lib, out = os.path.abspath(a.lib), os.path.abspath(a.out)
    for member in cfg["members"]:
        if want and member["name"].lower() not in want:
            continue
        work = os.path.join(out, "_work", member["name"].lower())
        os.makedirs(work, exist_ok=True)
        render = container_render(lib, work, tag="pack-" + member["name"].lower())
        pack = build_member(member, sfz_for(member, lib, work), os.path.join(out, member["name"].lower()), work, render)
        print(member["name"], len(pack["notes"]), "notes")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
