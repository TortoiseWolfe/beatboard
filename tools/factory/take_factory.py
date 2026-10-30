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
import glob, hashlib, json, math, os, random, re, shutil, subprocess, sys, time

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

# Content gate (hub CONTENT-RULE.md, 28 Oct): nothing may read as a figure near a child or as an invitation aimed at children.
# Same nine phrases as the track-sheet builder. The first eight block a render; the last (send/tell/post/told) is review only.
BAD_PHRASES = [r"taps three times, and waits", r"ROOM FOR EVERY KID", r"FOLLOW THE LIGHTS", r"room on the wagon for you and me",
               r"a girl at a window", r"couldn't speak.*watched|watched a girl", r"so the little one", r"come sit with me"]
REVIEW_PHRASES = [r"\b(send|tell|post|told)\b"]

# Kid screen (Jonathan, Fri 30 Oct 2026): the audience includes kids, so titles and lyrics are screened for words a kid could turn into a
# dirty joke. content_problems lists a match as review; a song marked kid_safe must have none (make_takes refuses it); title_problems
# screens cards, YouTube titles and posts.
DOUBLE_MEANING = [r"\bbottom\b", r"\bbooty\b", r"\bballs?\b", r"\bwood\b", r"\bscrews?\b", r"\bpounding\b", r"\bshake the pipes\b",
                  r"\bblows? (low|me|it)\b", r"\b(going to|here we|here I|ones who|I'm gonna|gonna) come\b", r"\bcomes? (in|on) (me|you)\b",
                  # 30 Oct, Jonathan's "fix all 27" (double-meanings.md): chants and phrases a kid could twist
                  r"\bpull it\b", r"\bhammering\b", r"\bwho's coming\b", r"\bcomes? first\b", r"\bthey came\b", r"\bput inside\b",
                  r"\bputting the service\b", r"\bride, ride, ride\b", r"\booh, ah\b", r"\bone push on\b", r"\bprovides the push\b",
                  r"\brolling full\b", r"\blength of the road\b", r"\bnot a straight line\b", r"\bbend it\b", r"\bplays it bent\b",
                  r"\bpush along\b", r"\bhead comes up\b", r"\beveryone comes\b", r"\bhorn can make it bigger\b", r"\bhorn has made\b"]
# Night Set songs re-worded for kids (Jonathan, 30 Oct about 7:55 AM): (old words, new words).
KID_FIXES = [("shake the pipes!", "rattle the pipes!"), ("Brass blows low, here we come.", "Brass plays low, here we go."),
             ("is going to come.", "is going to arrive."), ("to the ones who come.", "to the ones who join in."),
             ("it's the chain or the screw,", "it's the chain or the bolt,"), ("it says here I come!", "it says here I am!"),
             ("Crash, pounding]", "Crash, drumming]"),
             # 30 Oct about 11:45 AM, Jonathan: the same "here we come" joke in three more songs (double-meanings.md, kit section; the screen's wording)
             ("Brass is on the horn, here we come!", "Brass is on the trumpet, hear it hum!"),
             ("The Band Wagon's rolling, here we come!", "The Band Wagon's rolling, hear the drum!"),
             ("One, two, three, four, boom, here we come!", "One, two, three, four, boom, hear us drum!"),
             # 30 Oct, Jonathan's own wording for the n09 bridge
             ("Down low, down low, down low...", "Down we go, down we go, down we go..."), ("Up high, up high, hey!", "Up we go, up we go, hey!"),
             # 30 Oct, Jonathan's own wording for the n08 chorus (all three times) and the line after the verse
             ("Tighten it, tap it, and give it a turn!", "Fix it, tap it, and see what you learn!"),
             ("Put it in the beat and take it home.", "Play it in the beat and take it home."),
             # 30 Oct, Jonathan's own wording for the n04 chorus (both times) and the verse 2 line
             ("Twist it, turn it, tick and tock,\nWe both wind it, we both rock!", "Spin it, wind it, tick and tock,\nWe both turn the key and rock!"),
             ("Crank it till it rattles and the spring goes what the heck!", "Spin it till it rattles and the spring goes what the heck!"),
             # 30 Oct, Jonathan's own wording for the n05 line
             ("If there's a ghost around the corner, I'll toot it out of fright!", "If there's a ghost around the corner, I'll play it out of fright!")]
# Sung songs re-worded for kids (Jonathan, Fri 30 Oct about 8:18 AM: fix the 27 rows of double-meanings.md that are not marked low).
# Applied to the title, ribbon, lyrics and style of every song that carries the words, so the ns-* and saas-* copies follow their parent.
KID_SONG_FIXES = [
    ("The horn has made the sound bigger.", "The speaker has made the sound louder."),
    ("The horn can make it bigger,", "The speaker can make it louder,"),
    ("But it can only make more of whatever's put inside.", "But it can only play whatever's sent inside the sound."),
    ("We put in sameness, and the sameness gets to be", "We feed it sameness, and the sameness gets to be"),
    ("Chops plays it bent, and sideways, and human.", "Chops plays it wobbly, and sideways, and human."),
    ("bend it round the bend,", "wiggle it round the bend,"),
    ("BEND IT ROUND THE BEND", "WIGGLE IT ROUND THE BEND"),
    ("it's not a straight line, friend.", "it's not a ruler line, friend."),
    ("So we play it crooked and we play it true", "So we play it wiggly and we play it true"),
    ("a bent guitar solo", "a wobbly guitar solo"),
    ("they push along beside,", "they walk along beside,"),
    ("is a rhythm you can ride.", "is a rhythm we can trust."),
    ("who's coming to the show?", "who's joining the show?"),
    ("nineteen hundred miles they came,", "nineteen hundred miles they rode,"),
    ("Ivory's piano hammering", "Ivory's piano ringing out"),
    ("Ivory hammering piano", "Ivory playing piano bright and fast"),
    ("Crash on a pounding kick", "Crash on a driving kick"),
    ("a pounding kick", "a driving kick"),
    ("a pounding four-on-the-floor kick", "a driving four-on-the-floor kick"),
    ("Band: Pull it!", "Band: Link it!"),
    ("Chain! Pull it!", "Chain! Link it!"),
    ("CHAIN! PULL IT!", "CHAIN! LINK IT!"),
    ("The rider provides the push.", "The rider provides the power."),
    ("One push on the pedal and the chain starts to pull,", "One step on the pedal and the chain starts to move,"),
    ("the big wheel's rolling full.", "the big wheel's in the groove."),
    ("Ride, ride, ride, we are riding side by side,", "Roll, roll, roll, we are rolling side by side,"),
    ("Ride, ride, ride, it's a big wide world", "Roll, roll, roll, it's a big wide world"),
    ("Feel the wheels go over the ground!", "Hear the wheels go over the ground!"),
    ("was the length of the road,", "was the way they rode,"),
    ("and they carried the load.", "and they never let go."),
    ("high as a flag up there.", "bright as a flag up there."),
    ("every head comes up,", "every head looks up,"),
    ("and I never think to stop.", "but I know when to stop."),
    ("so everyone comes near.", "so everyone stays near."),
    ("bring them near.", "bring them here."),
    ("Putting the Service in SaaS (software as a service)", "Software as a Service, Hooray"),
    ("PUTTING THE SERVICE IN SAAS", "SOFTWARE AS A SERVICE, HOORAY"),
    ("Putting the service in SaaS!", "Software as a service, hooray!"),
    ("The people come first,", "The people go first,"),
    ("Log entry: the band has a bottom now.", "Log entry: the band has its groove now."),
    ("Ooh, ah, ooh, ah", "Hey, oh, hey, oh"),
]
# Songs that get a new kid-safe take, in the order they render (after the three Night Set songs, one after each rave take).
KID_REDO = ["story-8", "story-9", "story-12", "story-11", "story-13", "bike-a", "bike-b", "bike-c", "bike-d", "lore-h", "lore-j",
            "finding-the-bottom", "ukraine-warriorz-cry", "saas-a", "saas-b", "saas-c", "ns-story-9-puppet", "ns-bike-b-jazzrave",
            "ns-story-12-polka", "ns-story-8-monsterlite"]
NIGHT_SET = [("n01", "Seven Ghosts in the Wiring"), ("n08", "Wrench in the Works"), ("n09", "Boiler Room Boogie")]
# Kit songs whose held take is replaced under the same id (n02 Lantern Parade: its chorus carried the "here we come" joke; n04 Who Winds the Music Box?: Jonathan's new chorus and verse 2 line).
KIT_REDO = [("n02", "Lantern Parade"), ("n04", "Who Winds the Music Box?"), ("n05", "The Night Watch")]
JINGLE = os.environ.get("BW_JINGLE", os.path.join(os.path.dirname(STORY.rstrip("/")), "band-wagon-jingle.md"))

# ---------- pure helpers (tested) ----------

def content_problems(*texts):
    """(blocking, review): the BAD_PHRASES and REVIEW_PHRASES matches over the lyrics, style and title, before anything renders."""
    text = "\n".join(t for t in texts if t)
    return ([p for p in BAD_PHRASES if re.search(p, text, re.I)],
            [p for p in REVIEW_PHRASES + DOUBLE_MEANING if re.search(p, text, re.I)])


def title_problems(*titles):
    """The DOUBLE_MEANING patterns a card, YouTube title or post text matches; empty means it passes the kid screen."""
    text = "\n".join(t for t in titles if t)
    return [p for p in DOUBLE_MEANING if re.search(p, text, re.I)]


def kid_reword(text):
    """text with every KID_FIXES pair that occurs in it applied; words the pairs miss are caught by the kid screen in make_takes."""
    for old, new in KID_FIXES:
        text = text.replace(old, new)
    return text


def kid_song_fix(song):
    """A copy of a song entry with every KID_SONG_FIXES pair applied to its title, ribbon, lyrics and style."""
    out = dict(song)
    for key in ("title", "ribbon", "lyrics", "style"):
        if out.get(key):
            for old, new in KID_SONG_FIXES:
                out[key] = out[key].replace(old, new)
    return out


def variant(song, n):
    """Deterministic small change for take number n of a song: (style, bpm, seed, key)."""
    h = int(hashlib.sha256(f"{song['id']}:{n}".encode()).hexdigest(), 16)
    r = random.Random(h)
    bpm = max(60, song["bpm"] + (r.randint(-4, 4) if n else 0))
    key = song.get("key") if song.get("key_locked") else (r.choice(KEYS) if n else song.get("key", "A minor"))
    rave = song.get("kind") == "rave"
    extra = f"{r.choice(RAVE_MOODS if rave else MOODS)}, {r.choice(RAVE_MIXES if rave else MIXES)}" if n else ""
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


def stream_speed(log_text):
    """Encoder speed for the factory's back-off: the newest 'over the last minute' figure of the current ffmpeg run.

    The since-start average carries the slow start-up for a long time, so it is not used. A run with no last-minute
    figure yet ('no last-minute figure yet', or no reading at all since 'ffmpeg started') returns 0.0, which the
    callers treat as 'wait'. None only when the log has no 'ffmpeg started' line (no stream to protect).
    """
    starts = [m.end() for m in re.finditer(r"^\d+:\d+:\d+ [AP]M ffmpeg started", log_text, re.M)]
    if not starts:
        return None
    readings = re.findall(r"^\d+:\d+:\d+ [AP]M ffmpeg speed=[\d.]+x since start; (?:([\d.]+)x over the last minute|no last-minute figure yet)",
                          log_text[starts[-1]:], re.M)
    return float(readings[-1]) if readings and readings[-1] else 0.0


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


def silence_log(p, noise=-50, d=0.4):
    return sh("nice", "-n", "19", "ffmpeg", "-nostats", "-i", p, "-af", f"silencedetect=noise={noise}dB:d={d}", "-f", "null", "-").stderr


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

def loudness_curve(path, start, dur):
    """Momentary loudness (M, 400 ms) every 0.1 s from start for dur seconds: [(t, M)]. Used as evidence when a seam is refused."""
    err = sh("ffmpeg", "-nostats", "-ss", str(max(0, start)), "-t", str(dur), "-i", path, "-af", "ebur128", "-f", "null", "-").stderr
    out = []
    for m in re.finditer(r"t:\s*([\d.]+)\s.*?M:\s*(-?[\d.]+|-inf)", err):
        try:
            out.append((round(max(0, start) + float(m.group(1)), 1), float(m.group(2))))
        except ValueError:
            pass
    return out


def lufs_window(path, start, dur):
    """Integrated loudness of dur seconds from start, or None when the window is empty."""
    e = sh("ffmpeg", "-nostats", "-ss", str(max(0, start)), "-t", str(dur), "-i", path, "-af", "ebur128", "-f", "null", "-").stderr
    try:
        return float(e.split("Integrated loudness")[-1].split("I:")[1].split("LUFS")[0])
    except Exception:
        return None


def arc_kind(text):
    """What an ARC entry plans: a drop (arrives louder), a dip (breakdown or outro), or a build."""
    head = text.split(",")[0].lower()
    return "drop" if "drop" in head else "dip" if ("breakdown" in head or "outro" in head) else "build"


def rave_plan(secs, bpm, arc, tol_db=3.0, tol_s=0.5):
    """The plan for a joined rave take, from the recipe's section map and the sections themselves.

    One event per seam: the crossfade window [start, end] on the joined timeline, the planned kind (from ARC) and the planned
    level step, measured on the audio that will sit either side of the crossfade (10 s of the outgoing section before it, 10 s of the
    incoming section after it). A planned stop is {"time", "max_len"}; the recipe plans none yet.
    """
    xf = crossfade_seconds(bpm)
    events, t = [], 0.0
    for i in range(len(secs) - 1):
        keep = section_trim(bpm, duration(secs[i]))
        start = t + keep - xf
        pre, post = lufs_window(secs[i], keep - xf - 10, 10), lufs_window(secs[i + 1], xf, 10)
        event = {"kind": arc_kind(arc[min(i + 1, len(arc) - 1)]), "start": round(start, 2), "end": round(start + xf, 2)}
        event["planned_db"] = round(post - pre, 1) if pre is not None and post is not None else None
        events.append(event)
        t = start
    return {"events": events, "stops": [], "tol_db": tol_db, "tol_s": tol_s}


def judge_gaps(gaps, plan):
    """Gaps [(start, length)] that the plan does not explain. A planned stop is a gap starting within tol_s of its time and no longer than its max_len."""
    return [g for g in gaps if not any(abs(g[0] - st["time"]) <= plan["tol_s"] and g[1] <= st["max_len"] for st in plan["stops"])]


def judge_seam(event, pre, post, tol_db=3.0):
    """None when the joined take shows the planned step within tol_db; else (start, measured_db, planned_db, why)."""
    if pre is None or post is None or event["planned_db"] is None:
        return (event["start"], None, event["planned_db"], "seam not measurable")
    measured, planned = round(post - pre, 1), event["planned_db"]
    if abs(measured - planned) > tol_db:
        return (event["start"], measured, planned, "step differs from the plan")
    if (event["kind"] == "drop" and planned < -tol_db) or (event["kind"] == "dip" and planned > tol_db):
        return (event["start"], measured, planned, f"a {event['kind']} that goes the wrong way")
    return None


def check_rave(path, plan):
    """Plan-aware seam check on the joined file: [(start, measured_db, planned_db, why)]; empty means every planned step is there."""
    bad = []
    for ev in plan["events"]:
        pre, post = lufs_window(path, ev["start"] - 10, 10), lufs_window(path, ev["end"], 10)
        f = judge_seam(ev, pre, post, plan["tol_db"])
        if f:
            bad.append(f)
    return bad


def keep_rejected(src, tid, outdir, work, song_id, n, bad_seams, gaps, secs):
    """Never delete a take: move a refused one into <song>/_rejected/ with the loudness curve around each bad seam and its sections."""
    rej = f"{outdir}/_rejected"; os.makedirs(rej, exist_ok=True)
    dst = f"{rej}/{tid}.mp3"
    shutil.move(src, dst)
    curves = {str(t): loudness_curve(dst, t - 20, 60) for t, *_ in bad_seams}
    json.dump({"take": tid, "gaps": gaps, "bad_seams": bad_seams, "curves_M_dB": curves}, open(f"{rej}/{tid}.seams.json", "w"))
    for f in glob.glob(f"{work}/{song_id}-t{n}-s*.mp3"):
        shutil.move(f, f"{rej}/{os.path.basename(f)}")

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


def night_songs(path=None, songs=None, prefix="night-"):
    """The three Night Set songs re-worded for kids, as kid_safe song entries (ids night-n01, night-n08, night-n09)."""
    t = open(path or JINGLE).read()
    out = []
    for nid, title in (songs or NIGHT_SET):
        part = re.split(rf"(?:^|\n)### {nid}: ", t)[1].split("\n### ")[0]
        m = re.search(r"```\n(.*?)```", part, re.S)
        s = re.search(r'\nStyle: "(.*?)"', part)
        bpm = int(re.search(r"\((\d+) BPM", part)[1])
        out.append({"id": f"{prefix}{nid}", "title": title, "lyrics": kid_reword(m.group(1)), "style": s.group(1), "bpm": bpm,
                    "seconds": render_seconds(150), "kind": "kid", "priority": 3.0, "kid_safe": True})
    return out


def kit_redo_songs(path=None):
    """KIT_REDO songs re-worded for kids, as kid_safe entries that keep the kit id (the new take replaces the held one)."""
    return night_songs(path, KIT_REDO, "")


def redo_songs(path=None):
    """The KID_REDO songs from songs.json with the kid fixes applied, as kid_safe entries (id unchanged: the new take replaces the held one)."""
    by = {s["id"]: s for s in load_json(path or SONGS, [])}
    return [dict(kid_song_fix(by[i]), kid_safe=True) for i in KID_REDO if i in by]


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
    songs = [kid_song_fix(s) for s in songs] + night_songs() + rave_songs()
    save_json(SONGS, songs)
    return songs


# Grunge drum and bass (Jonathan, 30 Oct about 9:55 AM, hearing rave-7 take 1: "we're loosing the grungier side of our kids rock band, they still
# play outside in the mud on their bikes with some drum and bass wild child rave"). Every rave take from now on uses this style; kid-safe, no vocals.
ARC = ["slow build, a dirty filtered breakbeat, scratchy guitar feedback and a bicycle wheel tick in the mud",
       "first drop, fast chopped breakbeats on a live drum kit, a growling distorted bass, crunchy overdriven guitar riffs",
       "breakdown, the breakbeat keeps rolling under a growling bass with raw guitar stabs and a snare roll, a bicycle bell, then the full drop crashes back in",
       "second drop, the biggest section, wild breakbeats, distorted bass wobbles and loud garage guitar, kids shouting along off-mic",
       "long outro, the drums loosen to a muddy shuffle, guitar feedback and wheel tick, ending on one final big hit"]
RAVES = [("rave-1", "Pedal Beat Rave (A minor)", "A minor", 170), ("rave-2", "Brass Wheel Rave (D minor)", "D minor", 172),
         ("rave-3", "Music Box Rave (E minor)", "E minor", 174), ("rave-4", "Steam Rave (G minor)", "G minor", 168)]
RAVES2 = [("rave-5", "Kit and Synth Rave (C minor)", "C minor", 170), ("rave-6", "Hollow Wheel Rave (F minor)", "F minor", 172),
          ("rave-7", "Lantern Drop Rave (B minor)", "B minor", 174), ("rave-8", "Copper Pulse Rave (A minor)", "A minor", 168),
          ("rave-9", "Chain Lightning Rave (E minor)", "E minor", 170), ("rave-10", "Wagon Wheel Drop (D minor)", "D minor", 172)]
RAVE_MOODS = ["muddy", "raw", "gritty", "wild", "rough", "scrappy", "feral", "roaring"]
RAVE_MIXES = ["with a crunchier guitar", "with a heavier distorted bass", "with a tighter breakbeat", "with fuzzy garage guitar",
              "with a noisier lo-fi mix", "with a rattling snare", "with a bicycle bell cutting through", "with a gritty amen-style break"]


def rave_style(key, bpm):
    return (f"long instrumental gritty drum and bass rave, {key}, about {bpm} BPM, fast chopped breakbeats on a live drum kit, a growling distorted bass, "
            f"crunchy overdriven guitar from a kids' garage rock band, raw and rough, outdoor mud-and-bikes energy, a bicycle bell and wheel tick buried "
            f"in the mix, a breakdown and a drop, wild child rave, no vocals, dirty")


def rave_songs():
    out = []
    for sid, title, key, bpm in RAVES + RAVES2:
        out.append({"id": sid, "title": title, "lyrics": "[Instrumental]", "style": rave_style(key, bpm), "bpm": bpm, "seconds": 270, "kind": "rave",
                    "priority": 3.0, "key": key, "key_locked": True, "sections": 5, "arc": ARC})
    return out

# ---------- rendering one take ----------

def next_index(catalog, sid):
    return 1 + max([t["take_n"] for t in catalog if t["song"] == sid] or [-1])


def clean_section(song, style, bpm, seed, n, i, work):
    """One rave section with no mid-section dropout, sized to the target loudness; up to 3 seeds, both renders of each.

    The dropout check runs on the sized (normalized) audio with a margin (-46 dB, 0.25 s): the whole take is sized again after
    the join, and a dip that only just clears the check here (rave-2 take 0, 283.8 s) is a dropout there.
    """
    arc = song["arc"][min(i, len(song["arc"]) - 1)]
    for attempt in range(3):
        files, _ = render("[Instrumental]", style + ", " + arc, f"{song['id']}-t{n}-s{i}-{attempt}", seed + attempt * 1000,
                          song["seconds"], bpm, work)
        for f in files:
            out = f.replace(".mp3", ".norm.wav")
            g = round(LUFS_TARGET - lufs(f), 2)
            sh("nice", "-n", "19", "ffmpeg", "-y", "-v", "error", "-i", f, "-af", f"volume={g}dB,alimiter=limit=0.85:level=disabled", out)
            if not mid_gaps(silence_log(out, -46, 0.25), duration(out)):
                return out
    return None


def make_takes(song, catalog):
    blocking, review = content_problems(song.get("lyrics"), song.get("style"), song.get("title"), song.get("ribbon"))
    if review:
        print("content review (not blocking)", song["id"], review, flush=True)
    if blocking:
        print("content gate: not rendering", song["id"], "matches", blocking, flush=True)
        return []
    if song.get("kid_safe"):
        kid = title_problems(song.get("lyrics"), song.get("title"))
        if kid:
            print("kid screen: not rendering", song["id"], "matches", kid, flush=True)
            return []
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
        plan = rave_plan(secs, bpm, song["arc"])
        seams = []
    else:
        plan = None
        files, _ = render(song["lyrics"], style, f"{song['id']}-t{n}", seed, song["seconds"], bpm, work, song.get("beats", 4))
        cands = [(f, f"{song['id']}-t{n}" + ("b" if f.endswith("b.mp3") else "")) for f in files]
        seams = []
    for k, (src, tid) in enumerate(cands):
        dst = f"{outdir}/{tid}.mp3"
        size_and_tag(src, dst, tid)
        total = duration(dst)
        gaps = mid_gaps(silence_log(dst), total)
        bad_seams = []
        if plan:
            gaps = judge_gaps(gaps, plan)
            bad_seams = check_rave(dst, plan)
        elif seams:
            bad_seams = seam_report(dst, seams)
        ok = not gaps and not bad_seams and (song["kind"] != "rave" or total >= 900)
        if not ok:
            print("rejected", tid, "gaps", gaps, "bad seams", bad_seams, "seconds", round(total, 1), flush=True)
            keep_rejected(dst, tid, outdir, work, song["id"], n, bad_seams, gaps, song["kind"])
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
