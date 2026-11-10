# -*- coding: utf-8 -*-
"""Self-learning choice of sources: this device remembers which releases played well and which failed.

A 'release' is its group, resolution and service (for example FLUX · 4K · TORBOX). After a few tries a release that
keeps failing moves down and one that keeps playing well moves up, but only within its own resolution: a 1080p that
plays well never jumps above 4K. Kept per device (not per profile), because it is about what this device can play.
"""
import time

import ranking
import util

FILE = "learned.json"
GOOD_AFTER = 120          # seconds of playing that count as 'played well'
KEEP = 400                # releases remembered at most


def key(source):
    group = (ranking.release_group(source) or "").lower()
    if not group:
        return ""
    return "%s|%s|%s" % (group, source.get("resolution") or "", (source.get("scraper") or source.get("service") or "").lower())


def _save(data):
    if len(data) > KEEP:
        data = dict(sorted(data.items(), key=lambda kv: kv[1].get("at", 0))[-KEEP:])
    util.save_json(FILE, data)


def record(source_key, good):
    if not source_key:
        return
    data = util.load_json(FILE, {})
    entry = data.setdefault(source_key, {"good": 0, "bad": 0})
    entry["good" if good else "bad"] += 1
    entry["at"] = time.time()
    _save(data)


def score(source_key, data):
    entry = data.get(source_key)
    if not entry:
        return 0
    return entry.get("good", 0) - 2 * entry.get("bad", 0)


def adjust(sources):
    """Same order of resolutions as the ranking gave; inside each, good releases first and failing ones last."""
    if not util.flag("learn") or not sources:
        return sources
    data = util.load_json(FILE, {})
    if not data:
        return sources
    groups = {}
    for source in sources:
        groups.setdefault(source.get("resolution"), len(groups))

    def bucket(source):
        value = score(key(source), data)
        return 0 if value >= 2 else (2 if value <= -2 else 1)
    order = {id(s): n for n, s in enumerate(sources)}
    return sorted(sources, key=lambda s: (groups[s.get("resolution")], bucket(s), order[id(s)]))


def forget():
    util.save_json(FILE, {})
    util.notify(util.T("Geleerde bronnen gewist", "Learned sources cleared"))
