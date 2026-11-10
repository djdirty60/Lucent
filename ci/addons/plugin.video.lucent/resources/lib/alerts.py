# -*- coding: utf-8 -*-
"""'Ready in top quality': a message when a film on your watchlist, or a new episode of a series you follow, can be
played in the quality you want (for example 4K Dolby Vision, ready to play at once) - not at the first cam copy.

Runs in the background every few hours, never while a video plays, and checks a few titles per round.
For the skin: Home window properties lucent.video.alerts (number of new ones), lucent.video.alert.title and
.label, and the row plugin://plugin.video.lucent/?action=list&name=alerts&widget=1.
"""
import datetime
import time

import player
import ranking
import scrapers
import tmdb
import tracker
import util

T = util.T
FILE = "alerts.json"
EVERY = 6 * 3600
PER_ROUND = 6
QUALITY = [  # setting alert_quality -> (label, test)
    (T("4K Dolby Vision", "4K Dolby Vision"), lambda tags, s: s.get("resolution") == "4K" and "dv" in tags),
    ("4K", lambda tags, s: s.get("resolution") == "4K"),
    ("1080p", lambda tags, s: s.get("resolution") in ("4K", "1080p")),
]


def _state():
    data = util.load_json(FILE, {})
    data.setdefault("done", {})
    data.setdefault("found", [])
    return data


def due():
    return util.flag("alert_on") and time.time() - _state().get("at", 0) > EVERY


def _candidates(done):
    today = datetime.date.today()
    out = []
    for kind, tmdb_id in tracker.pairs("watchlist_movie"):
        key = "movie:%s" % tmdb_id
        if key not in done:
            out.append(("movie", str(tmdb_id), None, None, key))
    for show, season, episode in tracker.next_up()[:20]:
        key = "episode:%s:%s:%s" % (show, season, episode)
        if key not in done:
            out.append(("episode", str(show), int(season), int(episode), key))
    return out, (today - datetime.timedelta(days=60)).isoformat()


def _publish(data):
    fresh = [f for f in data["found"] if not f.get("seen")]
    util.HOME.setProperty("lucent.video.alerts", str(len(fresh)) if fresh else "")
    util.HOME.setProperty("lucent.video.alert.title", fresh[0]["title"] if fresh else "")
    util.HOME.setProperty("lucent.video.alert.label", fresh[0]["label"] if fresh else "")


def run():
    data = _state()
    data["at"] = time.time()
    util.save_json(FILE, data)
    label, test = QUALITY[min(util.number("alert_quality", 0), len(QUALITY) - 1)]
    try:
        todo, _oldest = _candidates(data["done"])
    except util.HttpError:
        return
    checked = 0
    for kind, tmdb_id, season, episode, key in todo:
        if checked >= PER_ROUND:
            break
        meta = player.title_meta(kind, tmdb_id, season, episode)
        if not meta or not tmdb.aired(meta.get("premiered")):
            continue
        checked += 1
        try:
            sources, _problem = scrapers.search(dict(meta, no_subcheck=True))
        except Exception as error:         # a failing scraper must never stop the service
            util.log("alerts: %s" % type(error).__name__)
            continue
        good = [s for s in sources or [] if s.get("cached") and test(ranking.tags_of(s), s)]
        if not good:
            continue
        name = meta["title"] if kind == "movie" else "%s S%02dE%02d" % (meta.get("show") or "", season, episode)
        data["done"][key] = time.time()
        data["found"].insert(0, {"key": key, "type": kind, "tmdb": tmdb_id, "season": season, "episode": episode,
                                 "title": name, "label": label, "at": time.time()})
        data["found"] = data["found"][:30]
        util.notify(T("Klaar in %s: %s", "Ready in %s: %s") % (label, name))
    util.save_json(FILE, data)
    _publish(data)


def titles():
    """The found titles, newest first, for the alerts row. Opening the row marks them as seen."""
    data = _state()
    out = []
    for entry in data["found"]:
        meta = player.title_meta(entry["type"], entry["tmdb"], entry.get("season"), entry.get("episode"))
        if meta:
            out.append(meta)
        entry["seen"] = True
    util.save_json(FILE, data)
    _publish(data)
    return out
