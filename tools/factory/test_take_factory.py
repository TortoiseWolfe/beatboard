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

    def line(self, t, since, last):
        tail = "no last-minute figure yet" if last is None else f"{last}x over the last minute"
        return f"{t} ffmpeg speed={since}x since start; {tail}\n"

    def test_reads_the_last_minute_figure_not_the_average(self):
        # since-start average is dragged down by the start-up (0.977); the last minute is 1.000
        log = self.START + self.line("10:39:34 PM", 0.959, None) + self.line("10:40:34 PM", 0.977, 1.0)
        self.assertEqual(tf.stream_speed(log), 1.0)

    def test_slow_last_minute_is_seen_even_when_average_is_fine(self):
        log = self.START + self.line("10:39:34 PM", 0.999, 1.0) + self.line("10:40:34 PM", 0.998, 0.93)
        self.assertEqual(tf.stream_speed(log), 0.93)

    def test_no_last_minute_figure_yet_means_wait(self):
        self.assertEqual(tf.stream_speed(self.START + self.line("10:39:34 PM", 0.959, None)), 0.0)
        self.assertEqual(tf.stream_speed(self.START), 0.0)

    def test_only_the_current_run_counts(self):
        old = self.START + self.line("10:39:34 PM", 0.9, 0.5)
        log = old + "10:50:00 PM ffmpeg started: restart\n" + self.line("10:51:00 PM", 0.97, 1.0)
        self.assertEqual(tf.stream_speed(log), 1.0)

    def test_none_without_a_start_line(self):
        self.assertIsNone(tf.stream_speed(self.line("11:00:34 PM", 1.0, 1.0)))


class RavePlanTests(unittest.TestCase):
    PLAN = {"events": [{"kind": "drop", "start": 747.3, "end": 761.8, "planned_db": 14.0}], "stops": [], "tol_db": 3.0, "tol_s": 0.5}

    def test_planned_drop_passes(self):
        # breakdown at -30, drop at -16: the plan says +14 and the take shows +13.4
        self.assertIsNone(tf.judge_seam(self.PLAN["events"][0], -30.0, -16.6))

    def test_drop_that_misses_its_depth_fails(self):
        self.assertIsNotNone(tf.judge_seam(self.PLAN["events"][0], -30.0, -24.0))

    def test_drop_that_goes_the_wrong_way_fails(self):
        ev = {"kind": "drop", "start": 247.6, "end": 262.6, "planned_db": -15.0}
        self.assertEqual(tf.judge_seam(ev, -16.0, -31.0)[3], "a drop that goes the wrong way")

    def test_unplanned_gap_fails(self):
        self.assertEqual(tf.judge_gaps([(283.8, 0.4)], self.PLAN), [(283.8, 0.4)])

    def test_planned_stop_on_time_passes(self):
        plan = dict(self.PLAN, stops=[{"time": 740.0, "max_len": 0.6}])
        self.assertEqual(tf.judge_gaps([(740.3, 0.5)], plan), [])

    def test_planned_stop_at_the_wrong_time_fails(self):
        plan = dict(self.PLAN, stops=[{"time": 740.0, "max_len": 0.6}])
        self.assertEqual(tf.judge_gaps([(741.2, 0.5)], plan), [(741.2, 0.5)])

    def test_planned_stop_that_runs_long_fails(self):
        plan = dict(self.PLAN, stops=[{"time": 740.0, "max_len": 0.6}])
        self.assertEqual(tf.judge_gaps([(740.0, 1.4)], plan), [(740.0, 1.4)])

    def test_arc_kinds(self):
        self.assertEqual([tf.arc_kind(a) for a in tf.ARC], ["build", "drop", "dip", "drop", "dip"])
        self.assertEqual([tf.arc_kind(a) for a in tf.ARC2], ["build", "drop", "dip", "drop", "dip"])

    def test_gentle_take_like_rave_1_t0_passes(self):
        # rave-1-t0's four seams step by less than 3 dB (10 s before against 3 s after, measured 30 Oct); each matches a plan of the same size
        for start, d in ((247.5, -0.4), (495.0, 0.6), (742.5, -0.8), (990.0, -0.5)):
            self.assertIsNone(tf.judge_seam({"kind": "dip", "start": start, "end": start + 15, "planned_db": d}, -15.0, -15.0 + d))


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


class ContentGateTests(unittest.TestCase):
    def test_clean_instrumental_passes(self):
        self.assertEqual(tf.content_problems("[Instrumental]", "long instrumental uplifting electronic dance, A minor", "Pedal Beat Rave"), ([], []))

    def test_each_blocking_phrase_is_caught(self):
        for line in ["She taps three times, and waits", "ROOM FOR EVERY KID", "follow the lights", "a girl at a window", "so the little one", "Come sit with me"]:
            self.assertTrue(tf.content_problems(line)[0], line)

    def test_send_tell_post_is_review_only(self):
        self.assertEqual(tf.content_problems("do what they're told"), ([], [r"\b(send|tell|post|told)\b"]))

    def test_make_takes_skips_a_blocked_song(self):
        song = {"id": "x", "title": "x", "lyrics": "[Verse]\na girl at a window", "style": "pop", "bpm": 100, "seconds": 60, "kind": "story"}
        self.assertEqual(tf.make_takes(song, []), [])


if __name__ == "__main__":
    unittest.main()
