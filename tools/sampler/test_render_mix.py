import json
import math
import os
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(__file__))
import build_pack
import midisplit
import mix
import render
import wavio

RATE = 48000


def sine(seconds, hz, amp=0.3):
    ch = [amp * math.sin(2 * math.pi * hz * i / RATE) for i in range(int(seconds * RATE))]
    return [ch, list(ch)]


def tune():
    t = lambda ev: b"MTrk" + len(ev).to_bytes(4, "big") + ev
    cond = t(b"\x00\xff\x51\x03" + (638297).to_bytes(3, "big") + b"\x00\xff\x2f\x00")
    notes = t(b"\x00\x90\x1f\x64\x81\x70\x80\x1f\x00\x00\xff\x2f\x00")      # ch0: one note, 240 ticks
    drum = t(b"\x00\x99\x24\x7f\x78\x89\x24\x00\x00\xff\x2f\x00")           # ch9
    stray = t(b"\x00\x95\x40\x64\x78\x85\x40\x00\x00\xff\x2f\x00")          # ch5 has notes
    body = cond + notes + drum + stray
    return b"MThd" + (6).to_bytes(4, "big") + (1).to_bytes(2, "big") + (4).to_bytes(2, "big") + (480).to_bytes(2, "big") + body


class RenderPlanTests(unittest.TestCase):
    def test_plan_pairs_channels_with_members_and_reports_strays(self):
        _, ev = midisplit.parse(tune())
        cfg = build_pack.load_members()
        mine, orphans = render.plan(ev, [m for m in cfg["members"] if m["name"] in ("Timber", "Crash")])
        self.assertEqual([m["name"] for m, _ in mine], ["Timber", "Crash"])
        self.assertEqual(orphans, [5])

    def test_member_gain_is_the_median_note_gain(self):
        pack = {"notes": {"1": {"gain_db": 2.0}, "2": {"gain_db": 4.0}, "3": {"gain_db": 10.0}}}
        self.assertEqual(render.member_gain_db(pack), 4.0)

    def test_end_marker_waits_for_the_member_tail(self):
        # 94 BPM, 480 ppq: 752 ticks a second; 3 s of tail is 2256 ticks
        self.assertEqual(render.tail_ticks({"tail_s": 3.0}, 94, 480), 2256)
        ppq, ev = midisplit.parse(tune())
        short = midisplit.write_channel(ppq, ev, 0)
        long_ = midisplit.write_channel(ppq, ev, 0, tail_ticks=2256)
        self.assertEqual(len(long_) - len(short), len(midisplit.vlq(2256)) - 1)
        self.assertTrue(long_.endswith(midisplit.vlq(2256) + b"\xff\x2f\x00"))

    def test_render_tune_with_a_stand_in_renderer(self):
        cfg = build_pack.load_members()
        cfg = {"bpm": cfg["bpm"], "members": [m for m in cfg["members"] if m["name"] in ("Timber", "Crash")]}
        with tempfile.TemporaryDirectory() as d:
            midi, packs, out, lib = (os.path.join(d, x) for x in ("t.mid", "packs", "out", "lib"))
            os.makedirs(lib)
            open(midi, "wb").write(tune())
            for m in cfg["members"]:
                os.makedirs(os.path.join(packs, m["name"].lower()))
                json.dump({"notes": {"1": {"gain_db": 6.0}}}, open(os.path.join(packs, m["name"].lower(), "pack.json"), "w"))
            seen = []

            def fake_run(cmd):
                seen.append(cmd)
                work = [c for c in cmd if c.endswith(":/work:rw")][0].split(":")[0]
                wav = cmd[cmd.index("--wav") + 1].replace("/work/", work + "/")
                wavio.write(wav, RATE, sine(0.5, 220, amp=0.1))

            made, orphans = render.render_tune(midi, lib, packs, out, cfg, run=fake_run)
            self.assertEqual(sorted(made), ["Crash", "Timber"])
            self.assertEqual(orphans, [5])
            self.assertEqual(len(seen), 2)
            _, chans = wavio.read(made["Timber"])
            self.assertAlmostEqual(wavio.peak(chans), 0.1 * 10 ** (6 / 20), places=2)  # +6 dB pack gain applied
            self.assertTrue(all("--oversampling" not in c for c in seen))


class MixTests(unittest.TestCase):
    def test_filtergraph_has_every_track_one_reverb_and_a_compressor(self):
        g = mix.filtergraph(["Timber", "Crash", "Mystery"], 3)
        for i in range(3):
            self.assertIn(f"[{i}:a]", g)
        self.assertEqual(g.count("afir"), 1)
        self.assertIn("acompressor", g)
        self.assertIn("[3:a]afir", g)

    def test_room_impulse_is_repeatable_and_decays(self):
        with tempfile.TemporaryDirectory() as d:
            a, b = os.path.join(d, "a.wav"), os.path.join(d, "b.wav")
            mix.room_impulse(a)
            mix.room_impulse(b)
            self.assertEqual(open(a, "rb").read(), open(b, "rb").read())
            _, ch = wavio.read(a)
            n = len(ch[0])
            early = max(abs(v) for v in ch[0][: n // 4])
            late = max(abs(v) for v in ch[0][3 * n // 4:])
            self.assertGreater(early, late * 5)

    def test_mix_lands_on_loudness_and_under_clipping(self):
        self.assertTrue(shutil.which("ffmpeg"), "ffmpeg is required for this test (CI installs it)")
        with tempfile.TemporaryDirectory() as d:
            tracks = {}
            for name, hz in (("Timber", 110), ("Reed", 440), ("Crash", 3000)):
                p = os.path.join(d, name.lower() + ".wav")
                wavio.write(p, RATE, sine(3.0, hz, amp=0.4))
                tracks[name] = p
            out = os.path.join(d, "mix.wav")
            r = mix.mix_tracks(tracks, out, os.path.join(d, "work"))
            self.assertAlmostEqual(r["lufs"], -16.0, delta=0.7)
            self.assertLessEqual(r["peak"], 10 ** (-1.0 / 20) + 0.002)


if __name__ == "__main__":
    unittest.main()
