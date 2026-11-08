#!/usr/bin/env python3
"""Split a Standard MIDI File into one single-channel file per channel, keeping the tempo.

Why: an SFZ renderer plays one instrument per run, so each MIDI channel of a tune is rendered on its own
with its own library, then the tracks are mixed. Notes keep their exact lengths and velocities.
Standard library only (no mido), so it runs on the host and in the container alike.

    python3 tools/sampler/midisplit.py tune.mid OUTDIR      writes OUTDIR/ch00.mid, ch01.mid ... for channels that have notes
"""
import struct
import sys


def read_vlq(b, p):
    v = 0
    while True:
        c = b[p]
        p += 1
        v = (v << 7) | (c & 0x7F)
        if not c & 0x80:
            return v, p


def vlq(v):
    out = [v & 0x7F]
    v >>= 7
    while v:
        out.append((v & 0x7F) | 0x80)
        v >>= 7
    return bytes(reversed(out))


def parse(data):
    """Return (ppq, events) with events = [(abs_tick, order, bytes_without_delta)] for every track merged."""
    if data[:4] != b"MThd":
        raise ValueError("not a MIDI file")
    ntrk, ppq = struct.unpack(">HH", data[10:14])
    if ppq & 0x8000:
        raise ValueError("SMPTE time division is not supported")
    p = 8 + struct.unpack(">I", data[4:8])[0]
    events = []
    order = 0
    for _ in range(ntrk):
        if data[p:p + 4] != b"MTrk":
            raise ValueError("bad track header")
        size = struct.unpack(">I", data[p + 4:p + 8])[0]
        q, end, tick, status = p + 8, p + 8 + size, 0, None
        while q < end:
            delta, q = read_vlq(data, q)
            tick += delta
            b = data[q]
            if b == 0xFF:  # meta
                kind = data[q + 1]
                length, r = read_vlq(data, q + 2)
                ev = data[q:r + length]
                q = r + length
                if kind != 0x2F:  # drop end-of-track, we write our own
                    events.append((tick, order, ev))
            elif b in (0xF0, 0xF7):  # sysex: skip
                length, r = read_vlq(data, q + 1)
                q = r + length
            else:
                if b & 0x80:
                    status = b
                    q += 1
                n = 1 if (status & 0xF0) in (0xC0, 0xD0) else 2
                ev = bytes([status]) + data[q:q + n]
                q += n
                events.append((tick, order, ev))
            order += 1
        p = end
    events.sort(key=lambda e: (e[0], e[1]))
    return ppq, events


def channels_with_notes(events):
    return sorted({e[2][0] & 0x0F for e in events if e[2][0] != 0xFF and (e[2][0] & 0xF0) == 0x90 and e[2][2] > 0})


def write_channel(ppq, events, channel, tail_ticks=0):
    """Format-0 file: every meta event (tempo, time signature) plus the channel's own events.

    `tail_ticks` moves the end-of-track marker that far past the last event, so a renderer run with --use-eot
    lets the last notes ring out instead of stopping the moment they end.
    """
    body = bytearray()
    last = 0
    for tick, _, ev in events:
        if ev[0] != 0xFF and (ev[0] & 0x0F) != channel:
            continue
        body += vlq(tick - last) + ev
        last = tick
    body += vlq(tail_ticks) + b"\xff\x2f\x00"
    return b"MThd" + struct.pack(">IHHH", 6, 0, 1, ppq) + b"MTrk" + struct.pack(">I", len(body)) + bytes(body)


def make_midi(note_list, bpm=120, ppq=480, channel=0, end_s=None):
    """Format-0 file from [(start_s, length_s, key, velocity)], used to play one test note through a sampler.

    `end_s` puts the end-of-track marker that many seconds in, so a renderer run with --use-eot keeps rendering
    through the note's whole natural tail.
    """
    tempo = int(round(60_000_000 / bpm))
    ticks_per_s = ppq * bpm / 60.0
    evs = []
    for start, length, key, vel in note_list:
        on = int(round(start * ticks_per_s))
        off = on + max(1, int(round(length * ticks_per_s)))
        evs.append((on, 1, bytes([0x90 | channel, key, vel])))
        evs.append((off, 0, bytes([0x80 | channel, key, 0])))
    evs.sort(key=lambda e: (e[0], e[1]))
    body = bytearray(vlq(0) + b"\xff\x51\x03" + tempo.to_bytes(3, "big"))
    last = 0
    for tick, _, ev in evs:
        body += vlq(tick - last) + ev
        last = tick
    end_tick = max(last, int(round(end_s * ticks_per_s))) if end_s is not None else last
    body += vlq(end_tick - last) + b"\xff\x2f\x00"
    return b"MThd" + struct.pack(">IHHH", 6, 0, 1, ppq) + b"MTrk" + struct.pack(">I", len(body)) + bytes(body)


def notes(events, channel):
    """[(start_tick, end_tick, key, velocity)] for one channel, pairing each note-on with the next note-off of that key."""
    open_, out = {}, []
    for tick, _, ev in events:
        if ev[0] == 0xFF or (ev[0] & 0x0F) != channel:
            continue
        kind = ev[0] & 0xF0
        if kind == 0x90 and ev[2] > 0:
            open_.setdefault(ev[1], []).append((tick, ev[2]))
        elif kind == 0x80 or (kind == 0x90 and ev[2] == 0):
            if open_.get(ev[1]):
                s, v = open_[ev[1]].pop(0)
                out.append((s, tick, ev[1], v))
    return sorted(out)


def main(argv):
    if len(argv) != 2:
        print(__doc__)
        return 2
    import os
    ppq, events = parse(open(argv[0], "rb").read())
    os.makedirs(argv[1], exist_ok=True)
    for ch in channels_with_notes(events):
        path = os.path.join(argv[1], f"ch{ch:02d}.mid")
        open(path, "wb").write(write_channel(ppq, events, ch))
        print(path, len(notes(events, ch)), "notes")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
