# -*- coding: utf-8 -*-
"""Lucent 2.1.17: rows the skin makes itself from the Kodi library, in an order a library path cannot give.

    plugin://skin.lucent/?list=lib_continue_new

'Episodes - new and continue': one tile per series you are watching - first its newest new episode (not watched, out
in the last 30 days, newest first), then the episode you stopped halfway (last watched first). Works for every add-on that fills the Kodi library
(NLZiet, Videoland, Lucent Video ...). Each tile is the library episode itself, so playing it resumes and marks it as
watched in the library like any library item."""
import json
import sys
import urllib.parse

import xbmc
import xbmcgui
import xbmcplugin

NEW_DAYS = 30
LIMIT = 200
FIELDS = ["title", "showtitle", "season", "episode", "firstaired", "plot", "rating", "runtime", "playcount", "lastplayed",
          "resume", "art", "file", "tvshowid", "dateadded", "streamdetails", "uniqueid"]


def rpc(method, **params):
    res = json.loads(xbmc.executeJSONRPC(json.dumps({"jsonrpc": "2.0", "id": 1, "method": method, "params": params})))
    return res.get("result") or {}


def episodes(rule, sort):
    return rpc("VideoLibrary.GetEpisodes", properties=FIELDS, filter=rule, sort=sort,
               limits={"start": 0, "end": LIMIT}).get("episodes") or []


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
    if ids:
        tag.setUniqueIDs(ids, "tmdb" if "tmdb" in ids else next(iter(ids)))
    art = {k: urllib.parse.unquote(v[8:-1]) if v.startswith("image://") else v for k, v in (ep.get("art") or {}).items()}
    li.setArt(art)
    li.setProperty("TvShowDBID", str(ep.get("tvshowid") or ""))
    li.setProperty("lucent.library", "1")
    return ep.get("file") or "", li


def next_up(show_id):
    """2.1.22: the episode after the last one you watched of this series (season and episode order), not the newest:
    if you are behind, the new episodes wait until you get there."""
    eps = rpc("VideoLibrary.GetEpisodes", tvshowid=int(show_id), properties=FIELDS,
              sort={"method": "episode", "order": "ascending"}).get("episodes") or []
    eps = [e for e in eps if int(e.get("season") or 0) > 0] or eps          # specials (season 0) only as a last resort
    last = max((i for i, e in enumerate(eps) if int(e.get("playcount") or 0) > 0), default=-1)
    return next((e for e in eps[last + 1:] if not int(e.get("playcount") or 0)), None)


def lib_continue_new():
    """One tile per series, only for series you are watching (you saw an episode of it): first the series with a new
    episode (unwatched, out in the last 30 days) that you are not halfway an episode of, newest first - the tile is the
    episode after the last one you watched (2.1.22), so you are never sent past episodes you have not seen; then the
    episodes you stopped halfway, last watched first."""
    shows = rpc("VideoLibrary.GetTVShows", properties=["watchedepisodes"]).get("tvshows") or []
    going = episodes({"field": "inprogress", "operator": "true", "value": ""}, {"method": "lastplayed", "order": "descending"})
    watching = {s["tvshowid"] for s in shows if int(s.get("watchedepisodes") or 0) > 0} | {e.get("tvshowid") for e in going}
    new = episodes({"and": [{"field": "playcount", "operator": "is", "value": "0"},
                            {"field": "airdate", "operator": "inthelast", "value": f"{NEW_DAYS} days"},
                            {"field": "inprogress", "operator": "false", "value": ""}]},
                   {"method": "date", "order": "descending"})
    done, rows = set(), []
    halfway = {e.get("tvshowid") for e in going}       # halfway an episode: you meet the new one by yourself
    for ep in [e for e in new if e.get("tvshowid") in watching and e.get("tvshowid") not in halfway] + going:
        if ep.get("tvshowid") in done:
            continue                                    # one tile per series
        done.add(ep.get("tvshowid"))
        if ep not in going:                             # a new episode: show the next one after where you are
            try:
                ep = next_up(ep.get("tvshowid")) or ep
            except Exception:  # noqa: BLE001 - a library hiccup: keep the new episode
                pass
        url, li = item(ep)
        if url:
            rows.append((url, li, False))
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
