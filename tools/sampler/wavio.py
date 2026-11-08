"""Small WAV helpers on the standard library: read and write 16-bit stereo or mono PCM, plus ffmpeg conversion.

sfizz_render writes whatever format it likes, so every file is first converted with ffmpeg to 16-bit 48 kHz stereo,
which the standard `wave` module can read. Samples are floats in -1..1, one list per channel.
"""
import array
import subprocess
import wave


def run(*cmd):
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode:
        raise RuntimeError(f"{cmd[0]} failed: {r.stderr[-400:]}")
    return r


def to_pcm16(src, dst, rate=48000, channels=2):
    run("ffmpeg", "-y", "-v", "error", "-i", src, "-ar", str(rate), "-ac", str(channels), "-c:a", "pcm_s16le", dst)


def read(path):
    """-> (rate, [channel lists of floats])"""
    with wave.open(path, "rb") as w:
        if w.getsampwidth() != 2:
            raise ValueError("expected 16-bit PCM (convert with to_pcm16)")
        rate, n = w.getframerate(), w.getnchannels()
        raw = array.array("h")
        raw.frombytes(w.readframes(w.getnframes()))
    return rate, [[v / 32768.0 for v in raw[c::n]] for c in range(n)]


def write(path, rate, chans):
    n = len(chans)
    inter = array.array("h", [0]) * (len(chans[0]) * n)
    for c, ch in enumerate(chans):
        inter[c::n] = array.array("h", [max(-32768, min(32767, int(round(v * 32767)))) for v in ch])
    with wave.open(path, "wb") as w:
        w.setnchannels(n)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(inter.tobytes())


def peak(chans):
    return max((abs(v) for ch in chans for v in ch), default=0.0)
