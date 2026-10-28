import unittest
import take_factory as tf

SONG = {"id": "story-3", "bpm": 120, "style": "warm pop, minor key, about 120 BPM, gentle", "key": "A minor"}


class VariantTests(unittest.TestCase):
    def test_deterministic(self):
        self.assertEqual(tf.variant(SONG, 4), tf.variant(SONG, 4))

    def test_take_zero_is_the_original(self):
        style, bpm, seed, key = tf.variant(SONG, 0)
        self.assertEqual((style, bpm, key), (SONG["style"], 120, "A minor"))

    def test_later_takes_change_a_little(self):
        seeds = {tf.variant(SONG, n)[2] for n in range(1, 30)}
        self.assertGreater(len(seeds), 25)
        for n in range(1, 30):
            self.assertLessEqual(abs(tf.variant(SONG, n)[1] - 120), 4)

    def test_locked_key_stays(self):
        s = dict(SONG, key="D minor", key_locked=True)
        self.assertTrue(all(tf.variant(s, n)[3] == "D minor" for n in range(1, 10)))


class GapTests(unittest.TestCase):
    LOG = ("[silencedetect @ 0x1] silence_start: 0.0\n[silencedetect @ 0x1] silence_end: 0.6 | silence_duration: 0.6\n"
           "[silencedetect @ 0x1] silence_start: 50.2\n[silencedetect @ 0x1] silence_end: 51.0 | silence_duration: 0.8\n"
           "[silencedetect @ 0x1] silence_start: 162.5\n[silencedetect @ 0x1] silence_end: 165.0 | silence_duration: 2.5\n")

    def test_ignores_head_and_tail(self):
        self.assertEqual(tf.mid_gaps(self.LOG, 165.0), [(50.2, 0.8)])

    def test_clean_take_has_none(self):
        self.assertEqual(tf.mid_gaps("", 165.0), [])


class VoteTests(unittest.TestCase):
    SONGS = [{"id": "a"}, {"id": "b"}]

    def test_weight_floor_and_cap(self):
        self.assertEqual(tf.song_weight({"down": 99}), 0.25)
        self.assertEqual(tf.song_weight({"up": 99}), 5.0)

    def test_up_votes_get_picked_first(self):
        self.assertEqual(tf.pick_song(self.SONGS, {}, {"b": {"up": 4}})["id"], "b")

    def test_down_votes_get_fewer_takes(self):
        votes = {"a": {"down": 5}}
        counts = {"b": 2}
        self.assertEqual(tf.pick_song(self.SONGS, counts, votes)["id"], "b")
        counts = {"b": 8}
        self.assertEqual(tf.pick_song(self.SONGS, counts, votes)["id"], "a")

    def test_priority_counts(self):
        songs = [{"id": "a", "priority": 3.0}, {"id": "b"}]
        self.assertEqual(tf.pick_song(songs, {}, {})["id"], "a")


class StreamTests(unittest.TestCase):
    START = "10:38:34 PM ffmpeg started: 37 full songs\n"

    def log(self, readings):
        return self.START + "".join(f"{t} ffmpeg speed={s}x since start; {s}x over the last minute\n" for t, s in readings)

    def test_real_time_when_average_is_flat(self):
        # since-start average holds at 0.994 while real speed is 1.0: the per-minute figure would mislead
        r = [("11:00:34 PM", 0.994), ("11:02:34 PM", 0.9945), ("11:04:34 PM", 0.995), ("11:06:34 PM", 0.9954)]
        self.assertAlmostEqual(tf.stream_speed(self.log(r)), 1.0, delta=0.01)

    def test_slow_encoder_is_seen(self):
        # average falls from 1.000 to 0.980 between 11:00 and 11:10: real speed in the window is well under 1
        r = [("11:00:34 PM", 1.0), ("11:05:34 PM", 0.99), ("11:10:34 PM", 0.98)]
        self.assertLess(tf.stream_speed(self.log(r)), 0.95)

    def test_none_without_two_readings_or_start(self):
        self.assertIsNone(tf.stream_speed(self.log([("11:00:34 PM", 1.0)])))
        self.assertIsNone(tf.stream_speed("11:00:34 PM ffmpeg speed=1.0x since start; 1.0x over the last minute\n"))

    def test_crossing_midnight(self):
        r = [("11:58:34 PM", 1.0), ("12:00:34 AM", 1.0), ("12:02:34 AM", 1.0)]
        self.assertAlmostEqual(tf.stream_speed(self.log(r)), 1.0, delta=0.01)


class TimingTests(unittest.TestCase):
    def test_trim_is_whole_bars(self):
        bar = 4 * 60.0 / 128
        keep = tf.section_trim(128, 270)
        self.assertAlmostEqual(keep / bar, round(keep / bar), places=6)
        self.assertLessEqual(keep, 270 - 6)
        self.assertGreater(keep, 270 - 6 - bar)

    def test_crossfade_is_eight_bars(self):
        self.assertEqual(tf.crossfade_seconds(120), 16.0)

    def test_long_songs_are_capped_to_what_fits_the_card(self):
        self.assertEqual(tf.render_seconds(365), 270)
        self.assertEqual(tf.render_seconds(185), 185)

    def test_first_bpm(self):
        self.assertEqual(tf.first_bpm("3: Song, 100 BPM", "x, about 90 BPM"), 100)
        self.assertEqual(tf.first_bpm("3: Song", "x, about 90 BPM"), 90)
        self.assertEqual(tf.first_bpm("3: Song", "x"), 80)


class YieldTests(unittest.TestCase):
    def setUp(self):
        import tempfile, os
        self.d = tempfile.mkdtemp()
        self.req, self.grant = os.path.join(self.d, "request"), os.path.join(self.d, "granted")
        self.events = []
        self.now = [0.0]

    def clock(self):
        return self.now[0]

    def sleep(self, s):
        self.now[0] += s

    def run_yield(self, free, comic=None, wait=600):
        def sleeper(s):
            self.sleep(s)
            if comic:
                comic()
        return tf.yield_gpu(self.d, free_mb=free, down=lambda: self.events.append("down"),
                            up=lambda: self.events.append("up"), sleep=sleeper, clock=self.clock, wait=wait)

    def test_no_request_does_nothing(self):
        self.assertFalse(self.run_yield(lambda: 8000))
        self.assertEqual(self.events, [])

    def test_request_stops_stack_grants_and_restarts(self):
        import os
        open(self.req, "w").close()
        seen = []

        def comic():
            seen.append(os.path.exists(self.grant))
            if os.path.exists(self.grant):
                os.remove(self.grant)
                os.remove(self.req)

        self.assertTrue(self.run_yield(lambda: 7000, comic))
        self.assertEqual(self.events, ["down", "up"])
        self.assertIn(True, seen)
        self.assertFalse(os.path.exists(self.req) or os.path.exists(self.grant))

    def test_gives_up_waiting_after_ten_minutes_and_clears_files(self):
        import os
        open(self.req, "w").close()
        self.assertTrue(self.run_yield(lambda: 7000))
        self.assertGreaterEqual(self.now[0], 600)
        self.assertFalse(os.path.exists(self.req) or os.path.exists(self.grant))
        self.assertEqual(self.events, ["down", "up"])

    def test_no_grant_when_card_stays_full(self):
        import os
        open(self.req, "w").close()
        self.assertTrue(self.run_yield(lambda: 2000))
        self.assertFalse(os.path.exists(self.grant))
        self.assertEqual(self.events, ["down", "up"])


if __name__ == "__main__":
    unittest.main()
