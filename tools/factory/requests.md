# Take factory requests

What Jonathan has asked for, in his own words, and what was queued. The factory itself steers by votes (`read_votes`); this list
is for asks that are not votes. Newest first. A take made for a request is still checked by `content_problems` before it renders.

## Fri 30 Oct 2026: kid screen (standing content rule)

His words, verbatim: "when marketing to kids we need to watch things that could be converted to dirty jokes, rename finding the bottom to building our bass"

The audience includes kids. Titles and lyrics are screened for double meanings: `DOUBLE_MEANING` in `take_factory.py` (review class in `content_problems`; a song marked
`kid_safe` is refused if it matches; `title_problems` screens cards, YouTube titles and posts). "Finding the Bottom" is now "Building Our Bass" (id unchanged).
About 7:55 AM he also approved kid-safe words for the Night Set songs (`KID_FIXES`: shake the pipes -> rattle the pipes; brass blows low, here we come -> brass plays low,
here we go; going to come -> going to arrive; the ones who come -> the ones who join in; the chain or the screw -> the chain or the bolt; here I come -> here I am;
Crash, pounding -> Crash, drumming). New takes `night-n01`, `night-n08`, `night-n09` are rendered from those words, one after each rave take.

## Fri 30 Oct 2026, about 7:30 AM: keep making rave takes (direction)

His words, verbatim: "more rave takes, keep them coming. I mean, when's the last time a jazz band went viral and for rave style music, let's party dude"

Direction: the Band Wagon leans rave over jazz to reach new listeners.

- A loop (lane bandwagon-takes, `run_rave_loop.py`) keeps making rave takes until Sat 31 Oct 5:30 PM Eastern or until he says stop:
  `rave-1` to `rave-4` first, then the new pedal-beat songs `rave-5` to `rave-10` (keys C, F, B, A, E and D minor; 124 to 140 BPM; a punchy kit and a
  synth lead, a breakdown and a drop; `RAVES2` and `ARC2`). Each take passes the content phrases before render and every check after; each kept take is
  appended to `ready.txt` for the stream.
- The back-off reads the newest "over the last minute" figure of the stream's encoder, and treats "no last-minute figure yet" as wait.
- A refused take is moved to `<song>/_rejected/` with the loudness curve around each bad seam, never deleted.

## Fri 30 Oct 2026, about 7:20 AM: more pedal-beat rave

His words, verbatim: "voting pedal beat rave up, more of that style is banin'" and, right after, "it's banging in a good way".

- Vote: one up on `band-wagon/takes/rave-1-t0` ("Pedal Beat Rave (A minor), take 0"), tagged as his, in the tower vote ledger.
- Style family: the `rave-*` recipe in `RAVES` and `ARC`: long instrumental uplifting electronic dance, about 128 BPM (the family runs 128 to 140),
  steady four-on-the-floor kick, a bicycle wheel tick, the band's brass and music box over builds and drops, no vocals, five sections, about 21 minutes.
- Queued, in this order: `rave-1` take 1 (A minor, closest to what he voted for), `rave-2` take 0 (D minor, 132), `rave-1` take 2,
  `rave-3` take 0 (E minor, 140), `rave-4` take 0 (G minor, 136), `rave-1` take 3.
- Runs through the factory's own checks (content phrases, dropout, seams, 900 s minimum, loudness) and yields the card whenever
  `~/.cache/gpu-yield/request` appears. Finished takes are listed in the lane report; the live catalog is not touched.
