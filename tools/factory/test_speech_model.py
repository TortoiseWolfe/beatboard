#!/usr/bin/env python3
"""Fail unless the speech model venv exists, imports faster-whisper, and transcribes the spoken fixture."""
import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(__file__))
import take_factory as tf

asr_py = os.environ.get("BW_ASR_PY", os.path.expanduser("~/.cache/bandwagon-asr/venv/bin/python"))
if not os.path.exists(asr_py):
    print(f"FAIL: ASR_PY not found at {asr_py}")
    sys.exit(1)


def run(cmd, **kw):
    r = subprocess.run(cmd, **kw)
    if r.returncode != 0 or not (r.stdout or "").strip():
        print("FAIL: speech model command failed", cmd,
              "\nrc", r.returncode, "\nstdout", r.stdout, "\nstderr", r.stderr, flush=True)
    return r


result = subprocess.run([asr_py, "-c", "from faster_whisper import WhisperModel; print('OK')"], capture_output=True, text=True)
if result.returncode != 0:
    print(f"FAIL: faster_whisper not importable: {result.stderr}")
    sys.exit(1)

fixture = os.path.join(os.path.dirname(__file__), "fixtures", "speech.wav")
words = tf.heard_words(fixture, run=run, model="small")
if words is None:
    print("FAIL: the speech model did not transcribe the fixture")
    sys.exit(1)

print(f"PASS: speech model heard {len(words)} words in the fixture")
