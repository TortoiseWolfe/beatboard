#!/usr/bin/env python3
"""Play a MIDI tune through the sound packs: one WAV track per band member, rendered by sfizz in the container.

    python3 tools/sampler/render.py TUNE.mid --lib LIBDIR --packs PACKS --out TRACKS

Each member plays its own channel through the same SFZ program build_pack.py used, so the preview sounds like
the pack. Each track's level is the member's pack gain (the median gain_db in its pack.json), so the render and the
pack are balanced the same way. The end-of-track marker is moved past the last note by the member's tail time
(members.json), so the last notes ring out.
"""
import argparse
import json
import math
import os
import statistics
import sys

sys.path.insert(0, os.path.dirname(__file__))
import build_pack
import midisplit
import sfizz
import wavio


def member_gain_db(pack):
    """The level the pack puts its notes at: the median of the per-note gains."""
    gains = [n["gain_db"] for n in pack["notes"].values()]
    return round(statistics.median(gains), 2) if gains else 0.0


def tail_ticks(member, bpm, ppq):
    return int(math.ceil(member["tail_s"] * ppq * bpm / 60.0))


def plan(events, members):
    """[(member, channel)] for every member whose channel has notes in the tune, in members.json order.
    Channels with notes and no member are returned separately so the caller can say so instead of dropping them."""
    have = set(midisplit.channels_with_notes(events))
    mine = [(m, m["channel"]) for m in members if m["channel"] in have]
    orphans = sorted(have - {m["channel"] for m in members})
    return mine, orphans


def render_tune(midi_path, lib_dir, packs_dir, out_dir, cfg, run=sfizz.run, rate=48000):
    with open(midi_path, "rb") as f:
        data = f.read()
    ppq, events = midisplit.parse(data)
    mine, orphans = plan(events, cfg["members"])
    os.makedirs(out_dir, exist_ok=True)
    work = os.path.join(out_dir, "_work")
    os.makedirs(work, exist_ok=True)
    made = {}
    for member, ch in mine:
        slug = member["name"].lower()
        with open(os.path.join(packs_dir, slug, "pack.json")) as f:
            pack = json.load(f)
        mid = os.path.join(work, slug + ".mid")
        with open(mid, "wb") as f:
            f.write(midisplit.write_channel(ppq, events, ch, tail_ticks(member, cfg["bpm"], ppq)))
        sfz = build_pack.sfz_for(member, lib_dir, work)
        inner = sfizz.render_args(sfz, "/work/" + slug + ".mid", "/work/" + slug + "-raw.wav", rate=rate)
        run(sfizz.container_command(inner, [(lib_dir, "/sfzlib", "ro"), (work, "/work", "rw")], tag="render-" + slug))
        pcm = os.path.join(work, slug + "-pcm.wav")
        wavio.to_pcm16(os.path.join(work, slug + "-raw.wav"), pcm, rate=rate, channels=2)
        rate_, chans = wavio.read(pcm)
        chans = build_pack.apply_gain(chans, member_gain_db(pack))
        track = os.path.join(out_dir, slug + ".wav")
        wavio.write(track, rate_, chans)
        made[member["name"]] = track
    return made, orphans


def main(argv):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("midi")
    ap.add_argument("--lib", required=True)
    ap.add_argument("--packs", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--config")
    a = ap.parse_args(argv)
    made, orphans = render_tune(a.midi, os.path.abspath(a.lib), os.path.abspath(a.packs), os.path.abspath(a.out),
                                build_pack.load_members(a.config))
    for name, path in made.items():
        print(name, path)
    if orphans:
        print("channels with notes and no band member (not rendered):", orphans)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
