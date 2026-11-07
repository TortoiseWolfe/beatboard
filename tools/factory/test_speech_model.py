#!/usr/bin/env python3
"""Quick test that the speech model is available and working."""
import os
import sys
sys.path.insert(0, os.path.dirname(__file__))
import take_factory as tf

# Test that heard_words doesn't return None (meaning the model is available)
# We can't easily test with a real audio file, but we can verify the venv exists
# and the module can be imported.

asr_py = os.environ.get("BW_ASR_PY", os.path.expanduser("~/.cache/bandwagon-asr/venv/bin/python"))
if not os.path.exists(asr_py):
    print(f"FAIL: ASR_PY not found at {asr_py}")
    sys.exit(1)

# Try importing faster_whisper in the venv
import subprocess
result = subprocess.run([asr_py, "-c", "from faster_whisper import WhisperModel; print('OK')"], capture_output=True, text=True)
if result.returncode != 0:
    print(f"FAIL: faster_whisper not importable: {result.stderr}")
    sys.exit(1)

print("PASS: Speech model environment is set up correctly")
