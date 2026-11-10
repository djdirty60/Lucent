# -*- coding: utf-8 -*-
"""Start at once: the sources for what you will most likely watch are looked up beforehand, in the background.
That is the top of 'Continue watching', your next episodes, and what you put ready for tonight. Pressing play then
skips the search screen. Also 'Ready for tonight': a film or episode you put on the list in the afternoon is
searched (with the subtitle check) before the evening, and you get a message when it is ready.

For the skin: the row plugin://plugin.video.lucent/?action=list&name=tonight&widget=1 and the Home property
lucent.video.tonight (number of titles ready for tonight)."""
import datetime
import time

import player
import ranking
import scrapers
import tracker
import util

T = util.T
FILE = "prefetch.json"
TONIGHT = "tonight.json"
KEEP = 90 * 60          # links stay fresh this long
EVERY = 15 * 60
PER_ROUND = 4
_last = {"at": 0.0}


def key_of(kind, tmdb_id, season=None, episode=None):
    return "%s:%s:%s:%s" % (kind, tmdb_id, season or "", episode or "")


def due():
    return util.flag("prefetch") and time.time() - _last["at"] > EVERY


def _candidates():
    out = []
    try:
        paused, following = tracker.paused()[:3], tracker.next_up()[:3]
    except util.HttpError as error:
        util.log("prefetch: account not reachable (%s)" % error)
        paused, following = [], []
    for row in paused:
        try:
            if row.get("type") == "movie":
                out.append(("movie", str(row["movie"]["ids"]["tmdb"]), None, None))
            else:
                out.append(("episode", str(row["show"]["ids"]["tmdb"]), int(row["episode"]["season"]), int(row["episode"]["number"])))
        except (KeyError, TypeError, ValueError):
            continue
    for show, season, episode in following:
        out.append(("episode", str(show), int(season), int(episode)))
    return out


def _fetch(entry, subtitles=False):
    kind, tmdb_id, season, episode = entry
    meta = player.title_meta(kind, tmdb_id, season, episode)
    if not meta:
        return None
    sources, _problem = scrapers.search(meta if subtitles else dict(meta, no_subcheck=True))
    if not sources:
        return None
    return {"at": time.time(), "meta": meta, "sources": sources[:20]}


def run():
    _last["at"] = time.time()
    store = {k: v for k, v in util.load_json(FILE, {}).items() if time.time() - v.get("at", 0) < KEEP}
    wanted = [(e, False) for e in _candidates()] + [((t["type"], t["tmdb"], t.get("season"), t.get("episode")), True) for t in tonight()]
    done = 0
    for entry, subtitles in wanted:
        key = key_of(*entry)
        if key in store or done >= PER_ROUND:
            continue
        try:
            found = _fetch(entry, subtitles)
        except Exception as error:          # noqa: BLE001 - a failing scraper must never stop the service
            util.log("prefetch: %s" % type(error).__name__)
            found = None
        done += 1
        if found:
            store[key] = found
    util.save_json(FILE, store)
    tonight_ready(store)


def take(params):
    """(meta, sources) found beforehand for this title, or (None, None)."""
    if not util.flag("prefetch"):
        return None, None
    key = key_of(params.get("type"), params.get("tmdb"), params.get("season"), params.get("episode"))
    entry = util.load_json(FILE, {}).get(key)
    if not entry or time.time() - entry.get("at", 0) > KEEP:
        return None, None
    util.log("starting at once: sources were found beforehand")
    return entry["meta"], entry["sources"]


# ------------------------------------------------------------------ ready for tonight
def tonight():
    data = util.load_json(TONIGHT, {})
    if data.get("day") != datetime.date.today().isoformat() and datetime.datetime.now().hour >= 6:
        return []                          # yesterday's evening is over
    return data.get("items") or []


def add_tonight(params):
    meta = player.title_meta(params["type"], params["tmdb"], params.get("season") and int(params["season"]), params.get("episode") and int(params["episode"]))
    if not meta:
        return
    entries = [e for e in tonight() if key_of(e["type"], e["tmdb"], e.get("season"), e.get("episode")) != key_of(params["type"], params["tmdb"], params.get("season"), params.get("episode"))]
    title = meta["title"] if meta["kind"] == "movie" else "%s S%02dE%02d" % (meta.get("show") or "", int(meta["season"]), int(meta["episode"]))
    entries.append({"type": params["type"], "tmdb": str(params["tmdb"]), "season": params.get("season"), "episode": params.get("episode"),
                    "title": title, "told": False})
    util.save_json(TONIGHT, {"day": datetime.date.today().isoformat(), "items": entries})
    _last["at"] = 0                         # look it up at the next round
    util.notify(T("Klaargezet voor vanavond: %s", "Ready for tonight: %s") % title)
    publish()


def tonight_ready(store):
    data = util.load_json(TONIGHT, {})
    hour = util.number("tonight_hour", 19)
    changed = False
    for entry in data.get("items") or []:
        found = store.get(key_of(entry["type"], entry["tmdb"], entry.get("season"), entry.get("episode")))
        if found and not entry.get("told") and datetime.datetime.now().hour >= hour - 1:
            best = found["sources"][0]
            tags = ranking.tags_of(best)
            bits = [best.get("resolution") or ""] + (["Dolby Vision"] if "dv" in tags else []) + ([T("NL-ondertitels", "Dutch subtitles")] if "nlsubs" in tags else [])
            util.notify(T("Vanavond staat klaar: %s · %s", "Ready for tonight: %s · %s") % (entry["title"], " · ".join(b for b in bits if b)))
            entry["told"] = True
            changed = True
    if changed:
        util.save_json(TONIGHT, data)
    publish()


def publish():
    util.HOME.setProperty("lucent.video.tonight", str(len(tonight())) if tonight() else "")


def tonight_titles():
    out = []
    for entry in tonight():
        meta = player.title_meta(entry["type"], entry["tmdb"], entry.get("season") and int(entry["season"]), entry.get("episode") and int(entry["episode"]))
        if meta:
            out.append(meta)
    return out
