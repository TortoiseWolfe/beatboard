import math
import os
import random
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(__file__))
import gate
import wavio

RATE = 48000
GOOD = {"lufs": -16.2, "peak_db": -2.0, "cutoffs": [{"file": "mix.wav", "cuts": 0, "first": []}],
        "grid": {"ms": 1.5, "sharpness": 2.4}}


def with_(**kw):
    m = dict(GOOD)
    m.update(kw)
    return m


class JudgeTests(unittest.TestCase):
    def test_good_render_passes(self):
        self.assertTrue(gate.judge(GOOD, (3.0, 3.0))["pass"])

    def test_cut_note_fails_and_names_the_track(self):
        v = gate.judge(with_(cutoffs=[{"file": "mix.wav", "cuts": 0}, {"file": "reed.wav", "cuts": 2}]), (3, 3))
        self.assertFalse(v["pass"])
        self.assertEqual(v["checks"]["cutoffs"]["where"], ["reed.wav"])

    def test_clipping_fails(self):
        self.assertFalse(gate.judge(with_(peak_db=-0.4), (3, 3))["pass"])
        self.assertTrue(gate.judge(with_(peak_db=-1.0), (3, 3))["pass"])

    def test_loudness_window(self):
        self.assertFalse(gate.judge(with_(lufs=-14.5), (3, 3))["pass"])
        self.assertFalse(gate.judge(with_(lufs=-17.2), (3, 3))["pass"])
        self.assertTrue(gate.judge(with_(lufs=-15.1), (3, 3))["pass"])

    def test_timing_off_the_grid_fails(self):
        self.assertFalse(gate.judge(with_(grid={"ms": -6.0, "sharpness": 2.0}), (3, 3))["pass"])

    def test_a_beat_too_weak_to_read_is_unjudged_not_passed(self):
        v = gate.judge(with_(grid={"ms": 0.0, "sharpness": 1.1}), (3, 3))
        self.assertFalse(v["pass"])
        self.assertEqual(v["checks"]["timing"]["status"], "unjudged")
        self.assertTrue(gate.judge(with_(grid={"ms": 0.0, "sharpness": 1.1}), (3, 3), allow_unjudged=True)["pass"])

    def test_songeval_below_the_album_by_more_than_the_margin_fails(self):
        self.assertFalse(gate.judge(GOOD, (2.7, 3.0), margin=0.2)["pass"])
        self.assertTrue(gate.judge(GOOD, (2.85, 3.0), margin=0.2)["pass"])

    def test_songeval_not_run_does_not_pass(self):
        v = gate.judge(GOOD, None)
        self.assertFalse(v["pass"])
        self.assertEqual(v["checks"]["songeval"]["status"], "not run")
        self.assertTrue(gate.judge(GOOD, None, allow_no_songeval=True)["pass"])

    def test_songeval_mean(self):
        self.assertAlmostEqual(gate.songeval_mean({"a": {"x": 2.0, "y": 4.0}}, "a"), 3.0)


def burst_train(cut):
    """A 2-second 220 Hz tone. With cut=True it stops dead at 1.0 s while loud; otherwise it dies away smoothly."""
    n = 2 * RATE
    out = []
    for i in range(n):
        t = i / RATE
        env = 1.0 if t < 1.0 else (0.0 if cut else math.exp(-12 * (t - 1.0)))
        out.append(0.5 * env * math.sin(2 * math.pi * 220 * t))
    return [out, list(out)]


class NodeCheckTests(unittest.TestCase):
    """These call the real cutoff.mjs and measure.mjs with node (the CI workflow has node 22)."""

    def test_hard_stop_is_found_and_smooth_decay_is_not(self):
        with tempfile.TemporaryDirectory() as d:
            cut, smooth = os.path.join(d, "cut.wav"), os.path.join(d, "smooth.wav")
            wavio.write(cut, RATE, burst_train(True))
            wavio.write(smooth, RATE, burst_train(False))
            self.assertEqual(gate.cutoff(cut)["cuts"], 1)
            self.assertEqual(gate.cutoff(smooth)["cuts"], 0)

    def test_grid_phase_reads_a_click_track(self):
        bpm = 120.0
        period = int(RATE * 60 / bpm)
        rng = random.Random(1)
        ch = [0.0] * (RATE * 8)
        for beat in range(15):
            at = beat * period + int(0.003 * RATE)  # clicks 3 ms late
            for k in range(200):
                ch[at + k] = (1 if k % 2 else -1) * 0.8 * math.exp(-k / 40) + rng.uniform(-0.001, 0.001)
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "clicks.wav")
            wavio.write(p, RATE, [ch, list(ch)])
            g = gate.grid(p, bpm)
            self.assertAlmostEqual(abs(g["ms"]), 3.0, delta=1.5)
            self.assertGreater(g["sharpness"], 1.7)


if __name__ == "__main__":
    unittest.main()
