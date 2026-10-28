#!/usr/bin/env python3
"""Band Wagon take factory: renders many slightly different takes of each song, unattended.

  take_factory.py init            build songs.json from the lyric pages
  take_factory.py run             render forever (stop: touch STOP file); one heavy job at a time, low priority
  take_factory.py status          print the catalog size and per-song counts

Each take gets a new seed and a small change (tempo a few BPM, instrument mix, key, mood words). A take is kept only
if it has no mid-song dropout; it is sized to about -16.1 LUFS, tagged "music made with AI", and written to the
catalog. Votes steer which song is rendered next; the live stream's speed log makes the factory back off.
Long rave jams are rendered in sections and joined with beat-aligned crossfades, then checked whole.
"""
import glob, hashlib, json, math, os, random, re, subprocess, sys, time

AUD = os.environ.get("BW_AUDIO", "/home/TurtleWolfe/repos/hub/internship/showcase/audio/band-wagon")
STORY = os.environ.get("BW_STORY", "/home/TurtleWolfe/repos/hub/internship/showcase/band-wagon-story")
LIVE_LOGS = os.environ.get("BW_LIVE_LOGS", "/home/TurtleWolfe/repos/.worktrees/OBS_MCP_bot--band-wagon-vote/playout/vote/state")
RENDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "kits", "render2.py")
TAKES = AUD + "/takes"
CATALOG = TAKES + "/catalog.json"
SONGS = TAKES + "/songs.json"
STOP = TAKES + "/STOP"
YIELD_DIR = os.environ.get("GPU_YIELD_DIR", os.path.expanduser("~/.cache/gpu-yield"))
TAG = "music made with AI (ACE-Step 1.5)"
LUFS_TARGET = -16.1

KEYS = ["A minor", "D minor", "E minor", "G minor", "C minor", "F minor", "B minor"]
MOODS = ["moody", "tender", "bright", "spooky but gentle", "dreamy", "driving", "warm", "eerie", "hopeful", "playful"]
MIXES = ["with extra music box", "with a warmer bass", "with more brass", "with a crunchier guitar", "with soft strings",
         "with a celesta and bells", "with a rolling piano", "with a tapping rim click", "with a breathy sax", "with a wheezing organ"]

# ---------- pure helpers (tested) ----------

def variant(song, n):
    """Deterministic small change for take number n of a song: (style, bpm, seed, key)."""
    h = int(hashlib.sha256(f"{song['id']}:{n}".encode()).hexdigest(), 16)
    r = random.Random(h)
    bpm = max(60, song["bpm"] + (r.randint(-4, 4) if n else 0))
    key = song.get("key") if song.get("key_locked") else (r.choice(KEYS) if n else song.get("key", "A minor"))
    extra = f"{r.choice(MOODS)}, {r.choice(MIXES)}" if n else ""
    style = song["style"]
    style = re.sub(r"about \d+ BPM", f"about {bpm} BPM", style)
    if n:
        style = style.replace("minor key", f"{key} feel") if "minor key" in style else style + f", {key}"
        style = style + ", " + extra
    seed = 10000 + (h % 80000)
    return style, bpm, seed, key


def mid_gaps(silence_log, total, head=1.0, tail=6.0):
    """Dropouts: quiet runs of at least 0.4 s that are not the start (< head s) or the end fade (last tail s)."""
    out = []
    for m in re.finditer(r"silence_start: ([\d.]+)\s*\n?.*?silence_end: ([\d.]+) \| silence_duration: ([\d.]+)", silence_log, re.S):
        a, b, d = float(m.group(1)), float(m.group(2)), float(m.group(3))
        if a < head or a > total - tail:
            continue
        out.append((round(a, 1), round(d, 1)))
    return out


def song_weight(votes, priority=1.0):
    """More net up votes -> more takes; down-voted songs get fewer (never zero)."""
    net = votes.get("up", 0) - votes.get("down", 0)
    return priority * min(5.0, max(0.25, 1 + 0.5 * net))


def pick_song(songs, counts, votes):
    """The song furthest behind its vote-weighted share of takes."""
    best, score = None, -1
    for s in songs:
        w = song_weight(votes.get(s["id"], {}), s.get("priority", 1.0))
        sc = w / (1 + counts.get(s["id"], 0))
        if sc > score:
            best, score = s, sc
    return best


def _clock(stamp):
    """Seconds since midnight for a '10:38:34 PM' stamp."""
    t = time.strptime(stamp, "%I:%M:%S %p")
    return t.tm_hour * 3600 + t.tm_min * 60 + t.tm_sec


def stream_speed(log_text, window=10):
    """Real encoder speed over the last `window` readings, from ffmpeg's since-start figures.

    The log's 'over the last minute' figure can repeat the since-start average, so it is never used. Media
    seconds made by a reading = speed x seconds since the 'ffmpeg started' line; the real speed is the change in
    media seconds over the change in wall-clock time. None until there are two readings and a start line.
    """
    start = re.search(r"^(\d+:\d+:\d+ [AP]M) ffmpeg started", log_text, re.M)
    if not start:
        return None
    t0, pts, day = _clock(start.group(1)), [], 0
    prev = t0
    for stamp, sp in re.findall(r"^(\d+:\d+:\d+ [AP]M) ffmpeg speed=([\d.]+)x since start", log_text, re.M):
        t = _clock(stamp) + day
        if t < prev:
            day += 86400
            t += 86400
        prev = t
        pts.append((t - t0, float(sp) * (t - t0)))
    pts = pts[-window:]
    if len(pts) < 2 or pts[-1][0] <= pts[0][0]:
        return None
    return (pts[-1][1] - pts[0][1]) / (pts[-1][0] - pts[0][0])


MAX_RENDER_SECONDS = 270  # 240 s peaks at 7.5-7.7 GB on the 8 GB card; longer is not proven to fit


def render_seconds(wanted):
    return min(MAX_RENDER_SECONDS, wanted)


def first_bpm(heading, style, default=80):
    """The first 'NN BPM' in the heading, else in the style line, else the default."""
    for text in (heading, style):
        m = re.search(r"(\d+) BPM", text)
        if m:
            return int(m.group(1))
    return default


def crossfade_seconds(bpm, bars=8):
    return round(bars * 4 * 60.0 / bpm, 2)


def section_trim(bpm, seconds, fade_tail=6.0):
    """Length to keep from a non-final section: a whole number of bars, so the next section lands on the beat grid."""
    bar = 4 * 60.0 / bpm
    return math.floor((seconds - fade_tail) / bar) * bar

# ---------- audio plumbing ----------

def sh(*a, **k):
    return subprocess.run(list(a), capture_output=True, text=True, **k)


def duration(p):
    return float(sh("ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", p).stdout)


def lufs(p):
    e = sh("nice", "-n", "19", "ffmpeg", "-nostats", "-i", p, "-af", "ebur128", "-f", "null", "-").stderr
    return float(e.split("Integrated loudness")[-1].split("I:")[1].split("LUFS")[0])


def silence_log(p):
    return sh("nice", "-n", "19", "ffmpeg", "-nostats", "-i", p, "-af", "silencedetect=noise=-50dB:d=0.4", "-f", "null", "-").stderr


def size_and_tag(src, dst, title):
    g = round(LUFS_TARGET - lufs(src), 2)
    sh("nice", "-n", "19", "ffmpeg", "-y", "-v", "error", "-i", src, "-af", f"volume={g}dB,alimiter=limit=0.85:level=disabled",
       "-metadata", f"title={title}", "-metadata", f"comment={TAG}", "-b:a", "192k", dst)
    return round(LUFS_TARGET, 1)


def render(lyrics_text, style, name, seed, seconds, bpm, outdir, beats=4):
    lf = f"{outdir}/{name}.lyrics.txt"
    open(lf, "w").write(lyrics_text)
    r = sh("nice", "-n", "19", "python3", RENDER, lf, style, name, str(seed), str(seconds), str(bpm), outdir + "/", str(beats))
    os.remove(lf)
    files = [f"{outdir}/{name}.mp3", f"{outdir}/{name}b.mp3"]
    return [f for f in files if os.path.exists(f)], r.stdout[-200:] + r.stderr[-200:]


def join_sections(files, bpm, dst):
    """Join rave sections left to right: trim each non-final section to whole bars, 8-bar crossfade between neighbours."""
    xf = crossfade_seconds(bpm)
    trimmed = []
    for i, f in enumerate(files):
        if i == len(files) - 1:
            trimmed.append(f)
            continue
        t = f"{dst}.t{i}.wav"
        sh("ffmpeg", "-y", "-v", "error", "-i", f, "-t", str(section_trim(bpm, duration(f))), t)
        trimmed.append(t)
    cur = trimmed[0]
    for i, nxt in enumerate(trimmed[1:], 1):
        out = f"{dst}.x{i}.wav"
        sh("ffmpeg", "-y", "-v", "error", "-i", cur, "-i", nxt, "-filter_complex", f"acrossfade=d={xf}:c1=qsin:c2=qsin", out)
        cur = out
    return cur


def seam_report(path, seam_times, win=3.0):
    """Loudness just after each seam against the 10 s before it; a jump over 3 LU is flagged."""
    bad = []
    for t in seam_times:
        a = sh("ffmpeg", "-nostats", "-ss", str(max(0, t - 10)), "-t", "10", "-i", path, "-af", "ebur128", "-f", "null", "-").stderr
        b = sh("ffmpeg", "-nostats", "-ss", str(t), "-t", str(win), "-i", path, "-af", "ebur128", "-f", "null", "-").stderr
        try:
            la = float(a.split("Integrated loudness")[-1].split("I:")[1].split("LUFS")[0])
            lb = float(b.split("Integrated loudness")[-1].split("I:")[1].split("LUFS")[0])
        except Exception:
            continue
        if abs(la - lb) > 3.0:
            bad.append((round(t, 1), round(lb - la, 1)))
    return bad

# ---------- registry, votes, catalog ----------

def load_json(p, default):
    try:
        return json.load(open(p))
    except Exception:
        return default


def save_json(p, obj):
    os.makedirs(os.path.dirname(p), exist_ok=True)
    tmp = p + ".tmp"
    json.dump(obj, open(tmp, "w"), indent=1)
    os.replace(tmp, p)


def read_votes():
    v = {}
    for fn in ("votes-twitch.json", "votes-youtube.json"):
        for k, d in load_json(f"{AUD}/{fn}", {}).get("songs", {}).items():
            sid = os.path.basename(k).rsplit(".", 1)[0]
            e = v.setdefault(sid, {"up": 0, "down": 0})
            e["up"] += d.get("up", 0)
            e["down"] += d.get("down", 0)
    for k, val in load_json(f"{AUD}/../votes.json", {}).items():
        if isinstance(val, str):
            sid = os.path.basename(k).rsplit(".", 1)[0]
            e = v.setdefault(sid, {"up": 0, "down": 0})
            e["up" if val == "like" else "down"] += 1
    return v


def stream_busy():
    logs = sorted(glob.glob(LIVE_LOGS + "/live-*.log"), key=os.path.getmtime)
    if not logs or time.time() - os.path.getmtime(logs[-1]) > 180:
        return None
    return stream_speed(open(logs[-1]).read())


def build_registry():
    songs = []
    def sections(path, head):
        t = open(path).read()
        for part in re.split(rf"\n## {head} ", t)[1:]:
            title = part.split("\n", 1)[0]
            m = re.search(r"```\n(.*?)```", part, re.S)
            s = re.search(r'\nStyle: "(.*?)"', part)
            if m and s:
                yield title, m.group(1), s.group(1)
    def add(sid, title, lyr, style, bpm, secs, kind, pr):
        songs.append({"id": sid, "title": title, "lyrics": lyr, "style": style, "bpm": bpm, "seconds": secs, "kind": kind, "priority": pr})
    secs_by = {1: 215, 7: 195, 13: 245, 2: 75, 3: 165, 4: 95, 5: 165, 6: 165, 8: 165, 9: 165, 10: 165, 12: 165}
    for fn in ("lyrics-pass-1.md", "lyrics-pass-3.md"):
        for title, lyr, style in sections(f"{STORY}/{fn}", "Track"):
            n = int(title.split(":")[0])
            bpm = first_bpm(title, style)
            add(f"story-{n}", title.split(":", 1)[1].split(", story")[0].strip(), lyr, style, bpm, secs_by.get(n, 165), "story", 3.0)
    p2 = open(f"{STORY}/lyrics-pass-2.md").read().split("## Part 2")[1]
    m = re.search(r"```\n(.*?)```", p2, re.S); s = re.search(r'\nStyle: "(.*?)"', p2)
    add("story-11", "The Riders", m.group(1), s.group(1), 76, 245, "story", 3.0)
    for fn, kind in (("lyrics-pass-4.md", "bike"), ("lyrics-pass-5.md", "lore"), ("lyrics-pass-6.md", "lore")):
        if not os.path.exists(f"{STORY}/{fn}"):
            continue
        for title, lyr, style in sections(f"{STORY}/{fn}", "Song"):
            letter = title[0]
            bpm = first_bpm(title, style)
            mins = re.search(r"about (\d+):(\d+)", title)
            secs = int(mins[1]) * 60 + int(mins[2]) + 5
            add(f"{kind}-{letter.lower()}", title.split(":", 1)[1].split("(")[0].strip(), lyr, style, bpm, render_seconds(secs), kind, 3.0)
            if "3/4" in title or "in three" in title:
                songs[-1]["beats"] = 3
    songs += rave_songs()
    save_json(SONGS, songs)
    return songs


ARC = ["slow build, filtered kick, music box melody and a bicycle wheel tick",
       "first drop, full four-on-the-floor kick and a rolling bass, brass stabs and bells",
       "breakdown, music box melody alone with rising risers, then the kick returns",
       "second drop, the biggest section, brass lead over a steady pedal-beat pulse, bright synth arpeggios",
       "long outro, the kick thins out, music box and wheel tick, the pulse fades"]
RAVES = [("rave-1", "Pedal Beat Rave (A minor)", "A minor", 128), ("rave-2", "Brass Wheel Rave (D minor)", "D minor", 132),
         ("rave-3", "Music Box Rave (E minor)", "E minor", 140), ("rave-4", "Steam Rave (G minor)", "G minor", 136)]


def rave_songs():
    out = []
    for sid, title, key, bpm in RAVES:
        style = (f"long instrumental uplifting electronic dance, {key}, about {bpm} BPM, steady four-on-the-floor kick, a bicycle wheel tick, "
                 f"the band's brass and music box woven through, builds and drops, no vocals, clean and joyful")
        out.append({"id": sid, "title": title, "lyrics": "[Instrumental]", "style": style, "bpm": bpm, "seconds": 270, "kind": "rave",
                    "priority": 3.0, "key": key, "key_locked": True, "sections": 5, "arc": ARC})
    return out

# ---------- rendering one take ----------

def next_index(catalog, sid):
    return 1 + max([t["take_n"] for t in catalog if t["song"] == sid] or [-1])


def clean_section(song, style, bpm, seed, n, i, work):
    """One rave section with no mid-section dropout, sized to the target loudness; up to 3 seeds, both renders of each."""
    arc = song["arc"][min(i, len(song["arc"]) - 1)]
    for attempt in range(3):
        files, _ = render("[Instrumental]", style + ", " + arc, f"{song['id']}-t{n}-s{i}-{attempt}", seed + attempt * 1000,
                          song["seconds"], bpm, work)
        for f in files:
            if not mid_gaps(silence_log(f), duration(f)):
                out = f.replace(".mp3", ".norm.wav")
                g = round(LUFS_TARGET - lufs(f), 2)
                sh("nice", "-n", "19", "ffmpeg", "-y", "-v", "error", "-i", f, "-af", f"volume={g}dB,alimiter=limit=0.85:level=disabled", out)
                return out
    return None


def make_takes(song, catalog):
    n = next_index(catalog, song["id"])
    style, bpm, seed, key = variant(song, n)
    outdir = f"{TAKES}/{song['id']}"; os.makedirs(outdir, exist_ok=True)
    work = f"{TAKES}/work"; os.makedirs(work, exist_ok=True)
    made = []
    if song["kind"] == "rave":
        secs = []
        for i in range(song["sections"]):
            sec = clean_section(song, style, bpm, seed + i * 7, n, i, work)
            if not sec:
                print("rave section", i, "had no clean take in 3 tries", flush=True)
                return made
            secs.append(sec)
        joined = join_sections(secs, bpm, f"{work}/{song['id']}-t{n}")
        cands = [(joined, f"{song['id']}-t{n}")]
        seams = []
        t = 0.0
        for f in secs[:-1]:
            t += section_trim(bpm, duration(f)) - crossfade_seconds(bpm)
            seams.append(t)
    else:
        files, _ = render(song["lyrics"], style, f"{song['id']}-t{n}", seed, song["seconds"], bpm, work, song.get("beats", 4))
        cands = [(f, f"{song['id']}-t{n}" + ("b" if f.endswith("b.mp3") else "")) for f in files]
        seams = []
    for k, (src, tid) in enumerate(cands):
        dst = f"{outdir}/{tid}.mp3"
        size_and_tag(src, dst, tid)
        total = duration(dst)
        gaps = mid_gaps(silence_log(dst), total)
        bad_seams = seam_report(dst, seams) if seams else []
        ok = not gaps and not bad_seams and (song["kind"] != "rave" or total >= 900)
        if not ok:
            print("rejected", tid, "gaps", gaps, "bad seams", bad_seams, "seconds", round(total, 1), flush=True)
            os.remove(dst)
            continue
        made.append({"song": song["id"], "take": tid, "take_n": n, "style": style, "seed": seed + k, "bpm": bpm, "key": key,
                     "seconds": round(total, 1), "path": dst, "lufs": LUFS_TARGET, "tag": TAG, "kind": song["kind"],
                     "made": time.strftime("%Y-%m-%d %H:%M:%S")})
    for f in glob.glob(f"{work}/{song['id']}-t{n}*"):
        os.remove(f)
    return made


def stack_up():
    if sh("curl", "-s", "-m", "3", "http://127.0.0.1:8001/health").stdout.find('"ok"') < 0:
        sh("timeout", "400", os.path.expanduser("~/.claude/scripts/docker-heavy.sh"), "--timeout", "350", "--", "docker", "compose", "-p", "jingle-audio",
           "-f", os.path.expanduser("~/repos/_vendor/ACE-Step-1.5/docker-compose.jingle.yml"), "up", "-d")
        for _ in range(60):
            if sh("curl", "-s", "-m", "3", "http://127.0.0.1:8001/health").stdout.find('"ok"') >= 0:
                break
            time.sleep(5)


def gpu_free_mb():
    try:
        return int(sh("nvidia-smi", "--query-gpu=memory.free", "--format=csv,noheader,nounits").stdout.split()[0])
    except Exception:
        return 0


def stack_down():
    sh("timeout", "200", os.path.expanduser("~/.claude/scripts/docker-heavy.sh"), "--timeout", "150", "--", "docker", "compose", "-p",
       "jingle-audio", "-f", os.path.expanduser("~/repos/_vendor/ACE-Step-1.5/docker-compose.jingle.yml"), "down")


def yield_gpu(yield_dir=None, free_mb=None, down=None, up=None, sleep=time.sleep, clock=time.time, wait=600, need_mb=6144):
    """Share the card with the comic: music first, then one comic page per music batch.

    If yield_dir/request exists: stop the music stack, wait until the card has need_mb free, write yield_dir/granted,
    wait until both files are gone (at most `wait` seconds), delete any leftovers, and start the stack again.
    Returns True when it yielded.
    """
    yield_dir = yield_dir or YIELD_DIR
    free_mb, down, up = free_mb or gpu_free_mb, down or stack_down, up or stack_up
    request, granted = os.path.join(yield_dir, "request"), os.path.join(yield_dir, "granted")
    if not os.path.exists(request):
        return False
    down()
    start = clock()
    while free_mb() < need_mb and clock() - start < 120:
        sleep(2)
    if free_mb() >= need_mb:
        open(granted, "w").write(time.strftime("%Y-%m-%d %H:%M:%S") + "\n")
        start = clock()
        while (os.path.exists(request) or os.path.exists(granted)) and clock() - start < wait:
            sleep(5)
    for f in (request, granted):
        if os.path.exists(f):
            os.remove(f)
    up()
    return True


def run():
    os.makedirs(TAKES, exist_ok=True)
    songs = load_json(SONGS, None) or build_registry()
    catalog = load_json(CATALOG, [])
    stack_up()
    while not os.path.exists(STOP):
        sp = stream_busy()
        if sp is not None and sp < 0.985:
            print("stream speed", round(sp, 3), "- backing off 180 s", flush=True)
            time.sleep(180)
            continue
        counts = {}
        for t in catalog:
            counts[t["song"]] = counts.get(t["song"], 0) + 1
        s = pick_song(songs, counts, read_votes())
        made = make_takes(s, catalog)
        catalog += made
        save_json(CATALOG, catalog)
        print(time.strftime("%I:%M %p"), s["id"], "kept", len(made), "total", len(catalog), flush=True)
        if yield_gpu():
            print(time.strftime("%I:%M %p"), "gave the card to the comic, stack restarted", flush=True)
        songs = load_json(SONGS, songs)
        time.sleep(2 if sp is None or sp >= 1.0 else 20)


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "status"
    if cmd == "init":
        print(len(build_registry()), "songs")
    elif cmd == "run":
        run()
    else:
        c = load_json(CATALOG, [])
        print(len(c), "takes")
        for sid in sorted({t["song"] for t in c}):
            print(sid, sum(1 for t in c if t["song"] == sid))
