#!/usr/bin/env python3
"""usage: words.py FILE -> JSON list of [start, end, word] on stdout (faster-whisper small, CPU)."""
import sys, json
from faster_whisper import WhisperModel
m = WhisperModel("small", device="cpu", compute_type="int8", cpu_threads=4)
segs, _ = m.transcribe(sys.argv[1], language="en", vad_filter=False, condition_on_previous_text=False, beam_size=1, word_timestamps=True)
print(json.dumps([[round(w.start, 1), round(w.end, 1), w.word.strip()] for s in segs for w in (s.words or [])]))
