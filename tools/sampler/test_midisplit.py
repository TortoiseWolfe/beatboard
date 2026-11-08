import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(__file__))
import midisplit as ms


def track(events):
    """events = [(delta, bytes)] -> MTrk chunk."""
    import struct
    body = b"".join(ms.vlq(d) + e for d, e in events) + ms.vlq(0) + b"\xff\x2f\x00"
    return b"MTrk" + struct.pack(">I", len(body)) + body


def smf(tracks, ppq=480):
    import struct
    return b"MThd" + struct.pack(">IHHH", 6, 1, len(tracks), ppq) + b"".join(tracks)


TEMPO = b"\xff\x51\x03" + (638297).to_bytes(3, "big")  # 94 BPM


def sample():
    cond = track([(0, TEMPO)])
    bass = track([(0, b"\x90\x1f\x64"), (480, b"\x80\x1f\x00"), (0, b"\x90\x20\x50"), (240, b"\x90\x20\x00")])  # ch0: note off as velocity 0
    drums = track([(0, b"\x99\x24\x7f"), (120, b"\x89\x24\x00")])  # ch9
    return smf([cond, bass, drums])


class SplitTests(unittest.TestCase):
    def test_channels_found(self):
        ppq, ev = ms.parse(sample())
        self.assertEqual(ppq, 480)
        self.assertEqual(ms.channels_with_notes(ev), [0, 9])

    def test_note_lengths_and_velocities_kept(self):
        _, ev = ms.parse(sample())
        self.assertEqual(ms.notes(ev, 0), [(0, 480, 0x1F, 100), (480, 720, 0x20, 80)])
        self.assertEqual(ms.notes(ev, 9), [(0, 120, 0x24, 127)])

    def test_split_file_keeps_tempo_and_only_its_channel(self):
        ppq, ev = ms.parse(sample())
        one = ms.write_channel(ppq, ev, 9)
        ppq2, ev2 = ms.parse(one)
        self.assertEqual(ppq2, 480)
        self.assertTrue(any(e[2] == TEMPO for e in ev2))
        self.assertEqual(ms.channels_with_notes(ev2), [9])
        self.assertEqual(ms.notes(ev2, 9), [(0, 120, 0x24, 127)])

    def test_running_status(self):
        # second note-on has no status byte (running status)
        t = track([(0, b"\x90\x3c\x64"), (100, b"\x3e\x64"), (100, b"\x80\x3c\x00"), (0, b"\x80\x3e\x00")])
        _, ev = ms.parse(smf([t]))
        self.assertEqual(ms.notes(ev, 0), [(0, 200, 60, 100), (100, 200, 62, 100)])

    def test_make_midi_round_trip(self):
        data = ms.make_midi([(0.0, 1.0, 60, 100), (1.0, 0.5, 64, 90)], bpm=120, ppq=480, channel=3)
        ppq, ev = ms.parse(data)
        self.assertEqual(ppq, 480)
        self.assertEqual(ms.channels_with_notes(ev), [3])
        self.assertEqual(ms.notes(ev, 3), [(0, 960, 60, 100), (960, 1440, 64, 90)])  # 960 ticks per second at 120 BPM

    def test_not_midi_is_refused(self):
        with self.assertRaises(ValueError):
            ms.parse(b"RIFFxxxx")


if __name__ == "__main__":
    unittest.main()
