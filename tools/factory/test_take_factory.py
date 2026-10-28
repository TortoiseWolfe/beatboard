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
    def test_parse(self):
        log = "".join(f"10:5{i}:35 PM ffmpeg speed=0.99x since start; {v}x over the last minute\n" for i, v in enumerate([1.2, 1.0, 0.9, 0.8]))
        self.assertAlmostEqual(tf.stream_speed(log), 0.9)

    def test_none_without_figures(self):
        self.assertIsNone(tf.stream_speed("nothing here"))


class TimingTests(unittest.TestCase):
    def test_trim_is_whole_bars(self):
        bar = 4 * 60.0 / 128
        keep = tf.section_trim(128, 270)
        self.assertAlmostEqual(keep / bar, round(keep / bar), places=6)
        self.assertLessEqual(keep, 270 - 6)
        self.assertGreater(keep, 270 - 6 - bar)

    def test_crossfade_is_eight_bars(self):
        self.assertEqual(tf.crossfade_seconds(120), 16.0)

    def test_first_bpm(self):
        self.assertEqual(tf.first_bpm("3: Song, 100 BPM", "x, about 90 BPM"), 100)
        self.assertEqual(tf.first_bpm("3: Song", "x, about 90 BPM"), 90)
        self.assertEqual(tf.first_bpm("3: Song", "x"), 80)


if __name__ == "__main__":
    unittest.main()
