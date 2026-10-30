import os
import re
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


class RaveGrungeTests(unittest.TestCase):
    def test_every_rave_is_grungy_drum_and_bass_and_kid_safe(self):
        songs = tf.rave_songs()
        self.assertEqual(len(songs), 10)
        for s in songs:
            self.assertIn("drum and bass", s["style"])
            self.assertIn("distorted bass", s["style"])
            self.assertIn("mud", s["style"])
            self.assertNotIn("clean and joyful", s["style"])
            self.assertNotIn("lo-fi", s["style"])
            self.assertTrue(all(w in s["style"] for w in ("dirty", "raw and rough", "growling distorted bass", "crunchy overdriven guitar",
                                                         "fast chopped breakbeats", "wild child rave")))
            self.assertFalse(any("drone" in a or "fades" in a for a in s["arc"]))
            self.assertIn("breakbeat keeps rolling", s["arc"][2])
            self.assertEqual(tf.content_problems(s["lyrics"], s["style"], s["title"], None)[0], [])
            self.assertEqual([tf.arc_kind(a) for a in s["arc"]], ["build", "drop", "dip", "drop", "dip"])

    def test_rave_takes_use_rave_moods_and_other_songs_keep_theirs(self):
        rave = tf.rave_songs()[0]
        style, _, _, _ = tf.variant(rave, 1)
        self.assertTrue(any(m in style for m in tf.RAVE_MOODS) and any(m in style for m in tf.RAVE_MIXES))
        self.assertFalse(any(m in style.split("no vocals")[-1] for m in ("tender", "breathy sax", "dreamy")))


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

    def test_gentle_take_like_rave_1_t0_passes(self):
        # rave-1-t0's four seams step by less than 3 dB (10 s before against 3 s after, measured 30 Oct); each matches a plan of the same size
        for start, d in ((247.5, -0.4), (495.0, 0.6), (742.5, -0.8), (990.0, -0.5)):
            self.assertIsNone(tf.judge_seam({"kind": "dip", "start": start, "end": start + 15, "planned_db": d}, -15.0, -15.0 + d))


class NotMeasurableTests(unittest.TestCase):
    EV = {"kind": "drop", "start": 100.0, "end": 114.0, "planned_db": 3.0}

    def test_unmeasurable_window_is_a_failure(self):
        self.assertEqual(tf.judge_seam(self.EV, None, -20.0)[3], "seam not measurable")
        self.assertEqual(tf.judge_seam(self.EV, -20.0, None)[3], "seam not measurable")
        self.assertEqual(tf.judge_seam(dict(self.EV, planned_db=None), -20.0, -17.0)[3], "seam not measurable")

    def test_measurable_seam_still_judged_by_the_plan(self):
        self.assertIsNone(tf.judge_seam(self.EV, -20.0, -17.0))

    def test_rave_plan_keeps_an_unmeasurable_seam_as_an_event(self):
        orig_win, orig_dur = tf.lufs_window, tf.duration
        try:
            tf.duration = lambda p: 100.0
            tf.lufs_window = lambda p, s, d: None
            plan = tf.rave_plan(["a", "b"], 128, ["slow build", "first drop, big"])
        finally:
            tf.lufs_window, tf.duration = orig_win, orig_dur
        self.assertEqual(len(plan["events"]), 1)
        self.assertIsNone(plan["events"][0]["planned_db"])

    def test_check_rave_reports_an_unmeasurable_seam(self):
        orig = tf.lufs_window
        try:
            tf.lufs_window = lambda p, s, d: None
            bad = tf.check_rave("x.mp3", {"events": [self.EV], "tol_db": 3.0})
        finally:
            tf.lufs_window = orig
        self.assertEqual([b[3] for b in bad], ["seam not measurable"])


class KeepRejectedTests(unittest.TestCase):
    def test_four_part_seam_faults_are_kept_aside(self):
        import tempfile, json as j
        with tempfile.TemporaryDirectory() as d:
            src = f"{d}/rave-x-t0.mp3"; open(src, "wb").write(b"x")
            orig = tf.loudness_curve
            tf.loudness_curve = lambda p, s, n: [-20.0]
            try:
                tf.keep_rejected(src, "rave-x-t0", d, d, "rave-x", 0, [(495.49, 3.9, 3.9, "a dip that goes the wrong way")], [], 5)
            finally:
                tf.loudness_curve = orig
            self.assertTrue(os.path.exists(f"{d}/_rejected/rave-x-t0.mp3"))
            self.assertIn("495.49", j.load(open(f"{d}/_rejected/rave-x-t0.seams.json"))["curves_M_dB"])


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


class KidFixAllTests(unittest.TestCase):
    OLD = {"id": "bike-b", "title": "Chain and Gears", "ribbon": "CHAIN! PULL IT! GEAR! TURN IT!", "style": "a pounding four-on-the-floor kick",
           "lyrics": "Chain! Pull it! Gear! Turn it!\nOne push on the pedal and the chain starts to pull,\nThe rider provides the push.\nThe people come first,"}

    def test_old_words_trip_the_screen(self):
        self.assertTrue(tf.title_problems(self.OLD["lyrics"]))

    def test_fix_changes_title_ribbon_style_and_lyrics(self):
        new = tf.kid_song_fix(self.OLD)
        self.assertEqual(tf.title_problems(new["lyrics"], new["title"]), [])
        self.assertEqual(new["ribbon"], "CHAIN! LINK IT! GEAR! TURN IT!")
        self.assertIn("a driving four-on-the-floor kick", new["style"])
        self.assertIn("The rider provides the power.", new["lyrics"])
        self.assertEqual(tf.kid_song_fix(new), new)

    def test_saas_title_and_chorus(self):
        s = tf.kid_song_fix({"id": "saas-a", "title": "Putting the Service in SaaS (software as a service)", "ribbon": "PUTTING THE SERVICE IN SAAS",
                             "lyrics": "Putting the service in SaaS!"})
        self.assertEqual((s["title"], s["ribbon"], s["lyrics"]), ("Software as a Service, Hooray", "SOFTWARE AS A SERVICE, HOORAY",
                                                                  "Software as a service, hooray!"))

    def test_redo_songs_follow_the_list_and_are_kid_safe(self):
        import tempfile, json
        songs = [dict(self.OLD, id=i) for i in reversed(tf.KID_REDO)] + [dict(self.OLD, id="story-1")]
        with tempfile.NamedTemporaryFile("w", suffix=".json") as f:
            json.dump(songs, f); f.flush()
            out = tf.redo_songs(f.name)
        self.assertEqual([s["id"] for s in out], tf.KID_REDO)
        for s in out:
            self.assertTrue(s["kid_safe"])
            self.assertEqual(tf.title_problems(s["lyrics"], s["title"]), [])

    def test_pairs_do_not_loop(self):
        for old, new in tf.KID_SONG_FIXES:
            self.assertNotIn(old, new)


class KitRepeatTests(unittest.TestCase):
    """Jonathan, 30 Oct about 11:45 AM: the 'here we come' joke is fixed in n02, n06 and the v1 theme too."""
    def test_three_more_lines_are_reworded(self):
        for old, new in [("Brass is on the horn, here we come!", "Brass is on the trumpet, hear it hum!"),
                         ("The Band Wagon's rolling, here we come!", "The Band Wagon's rolling, hear the drum!"),
                         ("One, two, three, four, boom, here we come!", "One, two, three, four, boom, hear us drum!")]:
            self.assertEqual(tf.kid_reword("a\n" + old + "\nb"), "a\n" + new + "\nb")
            self.assertTrue(any(re.search(p, old, re.I) for p in tf.DOUBLE_MEANING))
            self.assertFalse(any(re.search(p, new, re.I) for p in tf.DOUBLE_MEANING))

    def test_n09_bridge_uses_jonathans_words(self):
        out = tf.kid_reword("[Bridge]\nDown low, down low, down low...\nUp high, up high, hey!\n")
        self.assertEqual(out, "[Bridge]\nDown we go, down we go, down we go...\nUp we go, up we go, hey!\n")

    def test_n08_lines_use_jonathans_words(self):
        out = tf.kid_reword("Tighten it, tap it, and give it a turn!\nPut it in the beat and take it home.\nTighten it, tap it, and give it a turn!")
        self.assertEqual(out, "Fix it, tap it, and see what you learn!\nPlay it in the beat and take it home.\nFix it, tap it, and see what you learn!")

    def test_n02_keeps_its_id_and_is_kid_safe(self):
        jingle = os.path.join(os.path.dirname(__file__), "jingle-fixture.md")
        text = "### n02: Lantern Parade (120 BPM, 150 s)\n\n```\n[Chorus]\nLight the glow, beat the drum,\nThe Band Wagon's rolling, here we come!\n```\n\nStyle: \"dark march\"\n"
        with open(jingle, "w") as f:
            f.write(text)
        try:
            out = tf.kit_redo_songs(jingle)
        finally:
            os.remove(jingle)
        self.assertEqual([s["id"] for s in out], ["n02"])
        self.assertIn("hear the drum!", out[0]["lyrics"])
        self.assertEqual(tf.title_problems(out[0]["lyrics"], out[0]["title"]), [])


if __name__ == "__main__":
    unittest.main()


class KidScreenTests(unittest.TestCase):
    OLD = "Brass blows low, here we come.\nSomething wonderful is going to come.\nVerse sings out to the ones who come.\n"

    def test_old_words_are_flagged_and_new_words_pass(self):
        for line in ["Boiler room boogie, shake the pipes!", "Brass blows low, here we come.", "Something wonderful is going to come.",
                     "Verse sings out to the ones who come.", "it's the chain or the screw,", "and it says here I come!", "[Verse 2 - Crash, pounding]", "Finding the Bottom"]:
            self.assertTrue(tf.title_problems(line), line)
        for line in ["Boiler room boogie, rattle the pipes!", "Brass plays low, here we go.", "Something wonderful is going to arrive.",
                     "Verse sings out to the ones who join in.", "it's the chain or the bolt,", "it says here I am!", "[Verse 2 - Crash, drumming]", "Building Our Bass",
                     "Come on, come along, the wagon rolls on"]:
            self.assertEqual(tf.title_problems(line), [], line)

    def test_content_problems_lists_double_meanings_as_review(self):
        blocking, review = tf.content_problems("Brass blows low, here we come.")
        self.assertEqual(blocking, [])
        self.assertTrue(review)

    def test_kid_reword_applies_every_pair_and_keeps_the_rest(self):
        new = tf.kid_reword(self.OLD)
        self.assertEqual(new, "Brass plays low, here we go.\nSomething wonderful is going to arrive.\nVerse sings out to the ones who join in.\n")
        self.assertEqual(tf.title_problems(new), [])
        self.assertEqual(tf.kid_reword(new), new)  # already changed: fine

    def test_words_the_fixes_miss_are_still_caught(self):
        self.assertTrue(tf.title_problems(tf.kid_reword("the wood and the bottom")))

    def test_night_songs_from_the_jingle_page(self):
        import tempfile
        page = "\n".join(f"### {n}: {t} ({b} BPM, 150 s)\n\nx\n\n```\n[Verse]\nline\n```\n\nStyle: \"funk, about {b} BPM\"\n"
                         for n, t, b in [("n01", "A", 112), ("n08", "B", 126), ("n09", "C", 118)])
        page = page.replace("line", "Boiler room boogie, shake the pipes!\nBrass blows low, here we come.\nit's the chain or the screw,\nit says here I come!\nSomething wonderful is going to come.\nVerse sings out to the ones who come.", 3)
        with tempfile.NamedTemporaryFile("w", suffix=".md") as f:
            f.write(page); f.flush()
            songs = tf.night_songs(f.name)
        self.assertEqual([s["id"] for s in songs], ["night-n01", "night-n08", "night-n09"])
        self.assertEqual([s["bpm"] for s in songs], [112, 126, 118])
        for s in songs:
            self.assertTrue(s["kid_safe"])
            self.assertEqual(tf.title_problems(s["lyrics"], s["title"]), [])
