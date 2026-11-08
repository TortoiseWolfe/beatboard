import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(__file__))
import sfz_render as sr
import test_midisplit as tm


class CommandTests(unittest.TestCase):
    def test_runs_through_docker_heavy_light_slot_with_a_time_limit(self):
        cmd = sr.render_command(9, "/libs", "/out", "kit/kit.sfz")
        self.assertEqual(cmd[0], sr.HEAVY)
        self.assertIn("--light", cmd)
        self.assertIn("--timeout", cmd)
        self.assertEqual(cmd[cmd.index("--") + 1:cmd.index("--") + 4], ["docker", "run", "--rm"])

    def test_libraries_are_mounted_read_only(self):
        cmd = sr.render_command(0, "/libs", "/out", "a/b.sfz")
        self.assertIn("/libs:/libs:ro", cmd)

    def test_channel_names_files(self):
        cmd = sr.render_command(9, "/libs", "/out", "kit.sfz")
        self.assertIn("/out/ch09.mid", cmd)
        self.assertIn("/out/ch09.wav", cmd)
        self.assertIn("/libs/kit.sfz", cmd)

    def test_split_writes_one_file_per_channel_with_notes(self):
        with tempfile.TemporaryDirectory() as d:
            mid = os.path.join(d, "t.mid")
            open(mid, "wb").write(tm.sample())
            self.assertEqual(sr.split(mid, os.path.join(d, "o")), [0, 9])
            self.assertEqual(sorted(os.listdir(os.path.join(d, "o"))), ["ch00.mid", "ch09.mid"])


if __name__ == "__main__":
    unittest.main()
