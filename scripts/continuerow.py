# -*- coding: utf-8 -*-
"""Lucent: "Continue watching" for series from the Kodi library in ONE row - the episodes you stopped in, then the
next episode of every series you are watching (films have a row of their own).

    RunScript(special://skin/scripts/continuerow.py,play)   OK on an item of the row (Container(8092))

The Lucent helper (helper.py) calls update() once a minute (always on); it only asks the
library again when something was played or the library changed (VideoLibrary is quick, but not needed every minute).
The row reads Window(home).Property(lucent.cw.<n>.*) - the same idea as "Tonight for you".
"""
import json
import sys
import time

import xbmc
import xbmcgui

HOME = xbmcgui.Window(10000)
P = "lucent.cw."
MAX = 15
_STATE = {"sig": None, "t": 0.0}


def log(text):
    xbmc.log(f"[skin.lucent] continuerow: {text}", xbmc.LOGINFO)


def rpc(method, params):
    req = {"jsonrpc": "2.0", "id": 1, "method": method, "params": params}
    try:
        return json.loads(xbmc.executeJSONRPC(json.dumps(req))).get("result") or {}
    except Exception as error:  # noqa: BLE001
        log(f"{method}: {error}")
        return {}


def _art(art, *keys):
    for key in keys:
        if art.get(key):
            return art[key]
    return ""


def _percent(resume):
    try:
        total = float(resume.get("total") or 0)
        return int(100 * float(resume.get("position") or 0) / total) if total > 0 else 0
    except (TypeError, ValueError):
        return 0


def collect():
    items = []
    # films are not in this row: they have their own row ("Films die je kijkt" in Menu and widgets)
    eps = rpc("VideoLibrary.GetEpisodes", {
        "filter": {"field": "inprogress", "operator": "true", "value": ""},
        "properties": ["title", "showtitle", "season", "episode", "art", "resume", "lastplayed", "plot", "file", "tvshowid"],
        "sort": {"method": "lastplayed", "order": "descending"}, "limits": {"start": 0, "end": MAX}}).get("episodes") or []
    busy_shows = set()
    for e in eps:
        busy_shows.add(e.get("tvshowid"))
        items.append(_episode(e, e.get("resume") or {}, e.get("lastplayed", "")))
    shows = rpc("VideoLibrary.GetTVShows", {
        "filter": {"field": "inprogress", "operator": "true", "value": ""},
        "properties": ["title", "lastplayed", "art"],
        "sort": {"method": "lastplayed", "order": "descending"}, "limits": {"start": 0, "end": MAX}}).get("tvshows") or []
    for show in shows:
        if show["tvshowid"] in busy_shows:
            continue                                     # already in the row with the episode you stopped in
        nxt = rpc("VideoLibrary.GetEpisodes", {
            "tvshowid": show["tvshowid"],
            "filter": {"and": [{"field": "playcount", "operator": "is", "value": "0"},
                               {"field": "season", "operator": "greaterthan", "value": "0"}]},
            "properties": ["title", "showtitle", "season", "episode", "art", "resume", "plot", "file", "tvshowid"],
            "sort": {"method": "episode", "order": "ascending"}, "limits": {"start": 0, "end": 1}}).get("episodes") or []
        if nxt:
            item = _episode(nxt[0], {}, show.get("lastplayed", ""))
            item["logo"] = item["logo"] or _art(show.get("art") or {}, "clearlogo")
            items.append(item)
    items.sort(key=lambda i: i["last"] or "", reverse=True)
    return items[:MAX]


def _episode(e, resume, last):
    art = e.get("art") or {}
    sub = f"S{int(e.get('season') or 0):02d}E{int(e.get('episode') or 0):02d}  {e.get('title', '')}".strip()
    return {"type": "episode", "id": e["episodeid"], "title": e.get("showtitle") or e.get("title", ""), "sub": sub,
            "thumb": _art(art, "thumb", "tvshow.landscape", "tvshow.fanart", "fanart"),
            "fanart": _art(art, "tvshow.fanart", "fanart"), "logo": _art(art, "tvshow.clearlogo"),
            "plot": e.get("plot", ""), "file": e.get("file", ""), "percent": _percent(resume), "last": last}


def signature():
    """Changes when something was played or the library changed: the newest 'last played' and the counts."""
    m = rpc("VideoLibrary.GetMovies", {"filter": {"field": "inprogress", "operator": "true", "value": ""},
                                       "properties": ["lastplayed"], "sort": {"method": "lastplayed", "order": "descending"},
                                       "limits": {"start": 0, "end": 1}})
    e = rpc("VideoLibrary.GetEpisodes", {"properties": ["lastplayed"], "sort": {"method": "lastplayed", "order": "descending"},
                                         "limits": {"start": 0, "end": 1}})
    return json.dumps([(m.get("limits") or {}).get("total"), [x.get("lastplayed") for x in m.get("movies") or []],
                       (e.get("limits") or {}).get("total"), [x.get("lastplayed") for x in e.get("episodes") or []]])


def update(force=False):
    sig = signature()
    if not force and sig == _STATE["sig"] and time.time() - _STATE["t"] < 3600:
        return
    _STATE["sig"], _STATE["t"] = sig, time.time()
    items = collect()
    for n, item in enumerate(items, 1):
        for key in ("type", "id", "title", "sub", "thumb", "fanart", "logo", "plot", "file", "percent"):
            HOME.setProperty(f"{P}{n}.{key}", str(item[key]))
    for n in range(len(items) + 1, MAX + 1):
        for key in ("type", "id", "title", "sub", "thumb", "fanart", "logo", "plot", "file", "percent"):
            HOME.clearProperty(f"{P}{n}.{key}")
    HOME.setProperty(P + "count", str(len(items)))
    log(f"{len(items)} items")


def clear():
    for n in range(1, MAX + 1):
        for key in ("type", "id", "title", "sub", "thumb", "fanart", "logo", "plot", "file", "percent"):
            HOME.clearProperty(f"{P}{n}.{key}")
    HOME.clearProperty(P + "count")


def play():
    """OK on the row: play the film or episode from the library (Kodi asks to resume where you stopped)."""
    n = xbmc.getInfoLabel("Container(8092).ListItem.Property(n)")
    kind, ident = HOME.getProperty(f"{P}{n}.type"), HOME.getProperty(f"{P}{n}.id")
    if not ident.isdigit():
        return
    key = "movieid" if kind == "movie" else "episodeid"
    rpc("Player.Open", {"item": {key: int(ident)}, "options": {"resume": True}})


if __name__ == "__main__":
    action = sys.argv[1] if len(sys.argv) > 1 else "update"
    if action == "play":
        play()
    else:
        update(force=True)
