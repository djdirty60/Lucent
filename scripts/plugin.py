# -*- coding: utf-8 -*-
"""Lucent 2.1.17: rows the skin makes itself from the Kodi library, in an order a library path cannot give.

    plugin://skin.lucent/?list=lib_continue_new

'Episodes - new and continue': one tile per series you are watching - first its newest new episode (not watched, out
in the last 30 days, newest first), then the episode you stopped halfway (last watched first). Works for every add-on that fills the Kodi library
(NLZiet, Videoland, Lucent Video ...). Each tile is the library episode itself, so playing it resumes and marks it as
watched in the library like any library item."""
import json
import sys
import time
import urllib.parse

import xbmc
import xbmcgui
import xbmcplugin

NEW_DAYS = 30
LIMIT = 200
FIELDS = ["title", "showtitle", "season", "episode", "firstaired", "plot", "rating", "runtime", "playcount", "lastplayed",
          "resume", "art", "file", "tvshowid", "dateadded", "streamdetails", "uniqueid"]


def log(text):
    xbmc.log(f"[skin.lucent] plugin: {text}", xbmc.LOGINFO)


def rpc(method, **params):
    res = json.loads(xbmc.executeJSONRPC(json.dumps({"jsonrpc": "2.0", "id": 1, "method": method, "params": params})))
    return res.get("result") or {}


def episodes(rule, sort):
    return rpc("VideoLibrary.GetEpisodes", properties=FIELDS, filter=rule, sort=sort,
               limits={"start": 0, "end": LIMIT}).get("episodes") or []


_SHOWS = {}


def show_ids(show_id):
    """TMDB / IMDb / TVDB number of a library series (once per series per row)."""
    if not show_id:
        return {}
    if show_id not in _SHOWS:
        ids = (rpc("VideoLibrary.GetTVShowDetails", tvshowid=int(show_id), properties=["uniqueid"]).get("tvshowdetails") or {}).get("uniqueid") or {}
        _SHOWS[show_id] = {k: str(ids[k]) for k in ("tmdb", "imdb", "tvdb") if ids.get(k)}
    return _SHOWS[show_id]


def item(ep):
    li = xbmcgui.ListItem(ep.get("title") or "", offscreen=True)
    tag = li.getVideoInfoTag()
    tag.setMediaType("episode")
    tag.setDbId(int(ep["episodeid"]))
    tag.setTitle(ep.get("title") or "")
    tag.setTvShowTitle(ep.get("showtitle") or "")
    tag.setSeason(int(ep.get("season") or 0))
    tag.setEpisode(int(ep.get("episode") or 0))
    tag.setFirstAired(ep.get("firstaired") or "")
    tag.setPremiered(ep.get("firstaired") or "")
    tag.setPlot(ep.get("plot") or "")
    tag.setRating(float(ep.get("rating") or 0))
    tag.setDuration(int(ep.get("runtime") or 0))
    tag.setPlaycount(int(ep.get("playcount") or 0))
    tag.setLastPlayed(ep.get("lastplayed") or "")
    tag.setDateAdded(ep.get("dateadded") or "")
    resume = ep.get("resume") or {}
    if resume.get("position") and resume.get("total"):
        tag.setResumePoint(float(resume["position"]), float(resume["total"]))
    ids = {k: str(v) for k, v in (ep.get("uniqueid") or {}).items() if v}
    default = "tmdb" if "tmdb" in ids else (next(iter(ids)) if ids else "")
    # 2.1.33: the numbers of the series too (lshowtmdb / lshowimdb / lshowtvdb), only on this tile, not in the library:
    # Kodi gives an episode no number of its series, and episode pictures with badges need it (Variables.xml LucentEpBadge)
    for kind, value in show_ids(ep.get("tvshowid")).items():
        ids[f"lshow{kind}"] = value
    if ids:
        tag.setUniqueIDs(ids, default or next(iter(ids)))
    art = {k: urllib.parse.unquote(v[8:-1]) if v.startswith("image://") else v for k, v in (ep.get("art") or {}).items()}
    li.setArt(art)
    li.setProperty("TvShowDBID", str(ep.get("tvshowid") or ""))
    li.setProperty("lucent.library", "1")
    return ep.get("file") or "", li


def aired(ep):
    first = str(ep.get("firstaired") or "")[:10]
    return not first or first <= time.strftime("%Y-%m-%d")


def next_up(show_id):
    """2.1.22: the episode after the last one you watched of this series (season and episode order), not the newest:
    if you are behind, the new episodes wait until you get there. Only an episode that is out."""
    eps = rpc("VideoLibrary.GetEpisodes", tvshowid=int(show_id), properties=FIELDS).get("episodes") or []
    # 2.1.26: our own order (season, then episode) - not Kodi's sort, which can mix up seasons
    eps.sort(key=lambda e: (int(e.get("season") or 0), int(e.get("episode") or 0)))
    eps = [e for e in eps if int(e.get("season") or 0) > 0] or eps          # specials (season 0) only as a last resort
    last = max((i for i, e in enumerate(eps) if int(e.get("playcount") or 0) > 0), default=-1)
    nxt = next((e for e in eps[last + 1:] if not int(e.get("playcount") or 0) and aired(e)), None)
    seen = eps[last] if last >= 0 else {}
    log(f"next up {seen.get('showtitle') or show_id}: last watched "
        f"{'S%sE%s' % (seen.get('season'), seen.get('episode')) if seen else '-'} -> "
        f"{'S%sE%s' % (nxt.get('season'), nxt.get('episode')) if nxt else 'none'} ({len(eps)} episodes)")
    return nxt


def lib_continue_new():
    """One tile per series you are watching:
    1. series with a new episode (unwatched, out in the last 30 days), newest first;
    2. then, last watched first: the episode you stopped halfway, or - 2.1.25 - for a series you watched in the last
       30 days and finished an episode of, the next episode that is out.
    A tile is always the episode after the last one you watched (2.1.22), so you never skip episodes."""
    shows = rpc("VideoLibrary.GetTVShows", properties=["watchedepisodes", "lastplayed"]).get("tvshows") or []
    going = episodes({"field": "inprogress", "operator": "true", "value": ""}, {"method": "lastplayed", "order": "descending"})
    watching = {s["tvshowid"] for s in shows if int(s.get("watchedepisodes") or 0) > 0} | {e.get("tvshowid") for e in going}
    new = episodes({"and": [{"field": "playcount", "operator": "is", "value": "0"},
                            {"field": "airdate", "operator": "inthelast", "value": f"{NEW_DAYS} days"},
                            {"field": "inprogress", "operator": "false", "value": ""}]},
                   {"method": "date", "order": "descending"})
    halfway = {e.get("tvshowid") for e in going}       # halfway an episode: you meet the new one by yourself
    done, rows = set(), []

    def add(ep):
        url, li = item(ep)
        if url:
            rows.append((url, li, False))

    for ep in new:                                      # 1. new episodes
        sid = ep.get("tvshowid")
        if sid not in watching or sid in halfway or sid in done:
            continue
        done.add(sid)
        try:
            ep = next_up(sid) or ep
        except Exception:  # noqa: BLE001 - a library hiccup: keep the new episode
            pass
        add(ep)
    since = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(time.time() - NEW_DAYS * 86400))
    later = [(str(e.get("lastplayed") or ""), "half", e) for e in going]
    for s in shows:                                     # 2. finished an episode lately: the next one
        sid = s["tvshowid"]
        if sid in done or sid in halfway or not int(s.get("watchedepisodes") or 0) or str(s.get("lastplayed") or "") < since:
            continue
        later.append((str(s.get("lastplayed") or ""), "next", sid))
    for _when, kind, what in sorted(later, key=lambda r: r[0], reverse=True):
        sid = what.get("tvshowid") if kind == "half" else what
        if sid in done:
            continue
        if kind == "next":
            try:
                what = next_up(sid)
            except Exception:  # noqa: BLE001
                what = None
            if not what:
                continue                                # all caught up (or the next one is not out yet)
        done.add(sid)
        add(what)
    return rows


def main():
    handle = int(sys.argv[1])
    params = dict(urllib.parse.parse_qsl(sys.argv[2].lstrip("?")))
    rows = lib_continue_new() if params.get("list") == "lib_continue_new" else []
    xbmcplugin.setContent(handle, "episodes")
    xbmcplugin.addDirectoryItems(handle, rows, len(rows))
    xbmcplugin.endOfDirectory(handle, succeeded=True, cacheToDisc=False)


if __name__ == "__main__":
    main()
