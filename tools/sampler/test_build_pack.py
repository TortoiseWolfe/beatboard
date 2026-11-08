import json
import math
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(__file__))
import build_pack as bp
import midisplit
import sfizz
import vsco
import wavio

RATE = 48000


def tone(seconds, hz=220.0, decay=3.0, amp=0.5, tail_zero=0.0):
    """A decaying sine as a stereo float pair, with optional digital silence after it."""
    n = int(seconds * RATE)
    ch = [amp * math.exp(-decay * i / RATE) * math.sin(2 * math.pi * hz * i / RATE) for i in range(n)]
    ch += [0.0] * int(tail_zero * RATE)
    return [ch, list(ch)]


MEMBER = {"channel": 0, "name": "Test", "instrument": "Sine", "program": "x/test.sfz", "kind": "sustained",
          "range": [48, 55], "step": 3, "hold_s": 0.2, "tail_s": 0.5, "velocity": 100, "licence": "CC0", "credit": "nobody"}


class SfizzTests(unittest.TestCase):
    def test_only_real_flags(self):
        cmd = sfizz.render_args("/lib/a.sfz", "/work/a.mid", "/work/a.wav")
        flags = {c for c in cmd if c.startswith("--")}
        self.assertEqual(flags, {"--sfz", "--midi", "--wav", "--samplerate", "--quality", "--polyphony", "--use-eot"})
        self.assertNotIn("--oversampling", cmd)

    def test_container_command_goes_through_docker_heavy_with_timeout(self):
        cmd = sfizz.container_command(["sfizz_render"], [("/h", "/lib", "ro")], tag="t", timeout=60, heavy="/x/docker-heavy.sh")
        self.assertEqual(cmd[0], "/x/docker-heavy.sh")
        self.assertIn("--timeout", cmd)
        self.assertEqual(cmd[cmd.index("--timeout") + 1], "60")
        self.assertIn("none", cmd)  # no network
        self.assertIn("/h:/lib:ro", cmd)
        self.assertEqual(cmd[-1], "sfizz_render")


class MidiEndTests(unittest.TestCase):
    def test_end_of_track_marker_waits_for_the_tail(self):
        data = midisplit.make_midi([(0, 0.5, 60, 100)], bpm=120, ppq=480, end_s=2.0)
        self.assertTrue(data.endswith(midisplit.vlq(1920 - 480) + b"\xff\x2f\x00"))


class GridTests(unittest.TestCase):
    def test_grid_ends_on_top_of_range(self):
        self.assertEqual(bp.pitch_grid(31, 50, 3), [31, 34, 37, 40, 43, 46, 49, 50])
        self.assertEqual(bp.pitch_grid(48, 54, 3), [48, 51, 54])

    def test_drum_keys_are_exact(self):
        self.assertEqual(bp.member_keys({"kind": "oneshot", "keys": [36, 38, 42, 46], "range": [36, 46]}), [36, 38, 42, 46])

    def test_members_file_covers_the_eight_band_members(self):
        cfg = bp.load_members()
        self.assertEqual([m["name"] for m in cfg["members"]],
                         ["Timber", "Switch", "Chops", "Ivory", "Reed", "Brass", "Chorus", "Crash"])
        for m in cfg["members"]:
            self.assertIn(m["licence"], ("CC0", "CC BY 4.0"))
            self.assertTrue(m["credit"])
        chorus = [m for m in cfg["members"] if m["name"] == "Chorus"][0]
        self.assertIn("VocalSet", chorus["credit"])


class TrimTests(unittest.TestCase):
    def test_only_trailing_silence_is_cut(self):
        chans = tone(1.0, decay=2.0, tail_zero=2.0)
        out = bp.trim_tail(chans, RATE, pad_ms=30)
        self.assertGreater(len(out[0]), RATE)                 # the whole sound is kept
        self.assertLess(len(out[0]), RATE + RATE * 0.1)       # the zeros are gone
        self.assertEqual(out[0][:RATE], chans[0][:RATE])       # nothing inside was touched

    def test_a_ringing_tail_is_never_chopped(self):
        # decays to -66 dB only after about 2.5 s; every sample louder than that must survive
        chans = tone(4.0, decay=3.0)
        out = bp.trim_tail(chans, RATE, floor_db=-66)
        last_loud = max(i for i, v in enumerate(chans[0]) if abs(v) >= 10 ** (-66 / 20))
        self.assertGreater(len(out[0]), last_loud)

    def test_gain_puts_peak_at_target(self):
        chans = tone(0.5, amp=0.1)
        g = bp.gain_to_peak(chans, -3.0)
        self.assertAlmostEqual(to_db(wavio.peak(bp.apply_gain(chans, g))), -3.0, places=1)


def to_db(x):
    return 20 * math.log10(x)


class VscoTests(unittest.TestCase):
    NAMES = ["Sum_SHTrumpet_sus_C3_v1_rr1.wav", "Sum_SHTrumpet_sus_C3_v3_rr1.wav",
             "Sum_SHTrumpet_sus_A#3_v1_rr1.wav", "Sum_SHTrumpet_sus_A#3_v3_rr1.wav"]

    def test_note_names_use_middle_c_is_60(self):
        self.assertEqual(vsco.parse_name("x_C4_v1_rr1.wav")["key"], 60)
        self.assertEqual(vsco.parse_name("x_A#3_v1_rr1.wav")["key"], 58)
        self.assertIsNone(vsco.parse_name("readme.txt"))

    def test_regions_cover_every_key_and_velocity_once(self):
        rs = vsco.regions(self.NAMES, bottom=0, top=79)
        for key in range(0, 80):
            for vel in (1, 64, 127):
                hit = [r for r in rs if r["lokey"] <= key <= r["hikey"] and r["lovel"] <= vel <= r["hivel"]]
                self.assertEqual(len(hit), 1, (key, vel))

    def test_top_recording_is_repitched_up_to_the_range_top(self):
        rs = vsco.regions(self.NAMES, top=79)
        top = [r for r in rs if r["key"] == 58][0]
        self.assertEqual(top["hikey"], 79)

    def test_sfz_text_names_each_file(self):
        text = vsco.sfz_text(self.NAMES, sample_dir_in_sfz="/lib/V/sus")
        for n in self.NAMES:
            self.assertIn("sample=/lib/V/sus/" + n, text)
        self.assertIn("ampeg_release", text)


class BuildMemberTests(unittest.TestCase):
    def fake_render(self, sfz, midi, wav_path):
        _, ev = midisplit.parse(midi)
        n = midisplit.notes(ev, 0)[0]
        hz = 440 * 2 ** ((n[2] - 69) / 12)
        wavio.write(wav_path, RATE, tone(0.7, hz=hz, decay=4.0, tail_zero=1.5))

    def fake_export(self, wav, ogg, mp3):
        for p in (ogg, mp3):
            with open(p, "wb") as f:
                f.write(b"x" * 100)

    def test_pack_json_per_note(self):
        with tempfile.TemporaryDirectory() as d:
            out, work = os.path.join(d, "out"), os.path.join(d, "work")
            os.makedirs(work)
            pack = bp.build_member(MEMBER, "/lib/x/test.sfz", out, work, self.fake_render, self.fake_export)
            self.assertEqual(sorted(pack["notes"]), ["48", "51", "54", "55"])
            n = pack["notes"]["48"]
            self.assertEqual(n["hold_s"], 0.2)
            self.assertGreater(n["length_s"], 0.7)            # the full tail is in the file
            self.assertAlmostEqual(n["release_s"], n["length_s"] - 0.2, places=2)
            self.assertIn("gain_db", n)
            self.assertEqual(pack["licence"], "CC0")
            on_disk = json.load(open(os.path.join(out, "pack.json")))
            self.assertEqual(on_disk["notes"]["55"]["files"]["ogg"], "test-55.ogg")

    def test_oneshot_has_no_release(self):
        shot = dict(MEMBER, name="Drum", kind="oneshot", keys=[36, 38], range=[36, 38])
        with tempfile.TemporaryDirectory() as d:
            work = os.path.join(d, "w")
            os.makedirs(work)
            pack = bp.build_member(shot, "/lib/x/d.sfz", os.path.join(d, "o"), work, self.fake_render, self.fake_export)
            self.assertTrue(pack["oneshot"])
            self.assertEqual(pack["notes"]["36"]["release_s"], 0.0)

    def test_silence_from_the_sampler_is_an_error(self):
        def silent(sfz, midi, wav_path):
            wavio.write(wav_path, RATE, [[0.0] * RATE, [0.0] * RATE])
        with tempfile.TemporaryDirectory() as d:
            work = os.path.join(d, "w")
            os.makedirs(work)
            with self.assertRaises(RuntimeError):
                bp.build_member(MEMBER, "/lib/x/test.sfz", os.path.join(d, "o"), work, silent, self.fake_export)


if __name__ == "__main__":
    unittest.main()
