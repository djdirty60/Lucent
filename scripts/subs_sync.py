# -*- coding: utf-8 -*-
"""Lucent: put a subtitle in sync with the video by comparing it with a subtitle that is already in sync.

No sound is needed (a stream cannot be listened to from a skin): subtitles in any language follow the same speech, so
the start times of their lines line up. This finds the shift (seconds earlier / later) and the drift (a subtitle made
for another frame rate, e.g. 25 instead of 23.976 frames a second) that make the most lines start together, like the
tool alass does, and writes a corrected copy.

Works for a fixed shift and a wrong frame rate - not for a version with scenes cut or added (no single shift fits).
"""
import bisect
import os
import time

import xbmc

import subs_ai

# frame rate pairs a subtitle can be made for vs the video
RATES = [23.976, 24.0, 25.0, 29.97, 30.0]
SCALES = sorted({round(a / b, 6) for a in RATES for b in RATES})
WINDOW = 180.0          # largest shift looked at (seconds)
BIN = 0.1
HIT = 0.6               # a line counts as matching when it starts within this many seconds of a reference line


def log(text):
    xbmc.log(f"[skin.lucent] subs_sync: {text}", xbmc.LOGINFO)


def score(starts, ref, scale, offset):
    hits = 0
    for t in starts:
        x = t * scale + offset
        i = bisect.bisect_left(ref, x - HIT)
        if i < len(ref) and ref[i] <= x + HIT:
            hits += 1
    return hits


def best_offset(starts, ref, scale):
    """The shift that lines up most start times for this scale (a histogram of all nearby differences)."""
    counts = {}
    for t in starts:
        x = t * scale
        lo = bisect.bisect_left(ref, x - WINDOW)
        hi = bisect.bisect_right(ref, x + WINDOW)
        for r in ref[lo:hi]:
            b = round((r - x) / BIN)
            counts[b] = counts.get(b, 0) + 1
    if not counts:
        return 0.0
    top = sorted(counts.items(), key=lambda kv: -(kv[1] + counts.get(kv[0] - 1, 0) + counts.get(kv[0] + 1, 0)))[:5]
    best, best_score = 0.0, -1
    for b, _n in top:                                  # refine the best bins in small steps
        for step in range(-5, 6):
            off = (b + step / 5) * BIN
            s = score(starts, ref, scale, off)
            if s > best_score:
                best, best_score = off, s
    return best


def align(cues, ref_cues):
    """(scale, offset, matched share before, matched share after)."""
    starts = [c["start"] for c in cues]
    ref = sorted(c["start"] for c in ref_cues)
    if len(starts) < 20 or len(ref) < 20:
        return 1.0, 0.0, 0.0, 0.0
    before = score(starts, ref, 1.0, 0.0) / len(starts)
    best = (1.0, 0.0, before)
    for scale in SCALES:
        off = best_offset(starts, ref, scale)
        share = score(starts, ref, scale, off) / len(starts)
        if share > best[2] + (0.02 if scale != 1.0 else 0):   # only take a frame-rate change when it is clearly better
            best = (scale, off, share)
    return best[0], best[1], before, best[2]


def stamp(sec):
    sec = max(0.0, sec)
    ms = int(round(sec * 1000))
    h, ms = divmod(ms, 3600000)
    m, ms = divmod(ms, 60000)
    s, ms = divmod(ms, 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def write_shifted(path, cues, scale, offset):
    out = []
    for n, c in enumerate(cues, start=1):
        out.append(f"{n}\n{stamp(c['start'] * scale + offset)} --> {stamp(c['end'] * scale + offset)}\n{c['text']}\n")
    with open(path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(out))


def sync_text(target_text, reference_text, name="sub"):
    """Returns (path of the corrected file or '', message for the user)."""
    nl = xbmc.getLanguage(xbmc.ISO_639_1) == "nl"
    cues, ref = subs_ai.parse_srt(target_text), subs_ai.parse_srt(reference_text)
    if not cues or not ref:
        return "", ("Kan niet gelijkzetten: geen SRT-ondertitel" if nl else "Cannot sync: not an SRT subtitle")
    scale, offset, before, after = align(cues, ref)
    log(f"scale {scale} offset {offset:+.2f}s, lines matching {before:.0%} -> {after:.0%}")
    if after < 0.25:
        return "", ("Gelijkzetten lukte niet (andere versie van de film?)" if nl else "Could not sync (another version of the film?)")
    if abs(offset) < 0.15 and scale == 1.0:
        return "", ("Liep al gelijk" if nl else "Already in sync")
    os.makedirs(subs_ai.DIR, exist_ok=True)
    path = os.path.join(subs_ai.DIR, f"sync.{name}.{int(time.time())}.srt")
    write_shifted(path, cues, scale, offset)
    if scale != 1.0:
        msg = (f"Ondertitel gelijkgezet: {offset:+.1f} s en beeldsnelheid aangepast".replace(".", ",") if nl
               else f"Subtitle synced: {offset:+.1f} s and frame rate fixed")
    else:
        msg = (f"Ondertitel {abs(offset):.1f} s {'later' if offset > 0 else 'eerder'} gezet".replace(".", ",") if nl
               else f"Subtitle moved {abs(offset):.1f} s {'later' if offset > 0 else 'earlier'}")
    return path, msg
