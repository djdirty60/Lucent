# -*- coding: utf-8 -*-
"""Lucent 2.1.17: rows the skin makes itself from the Kodi library, in an order a library path cannot give.

    plugin://skin.lucent/?list=lib_continue_new

'Episodes - new and continue': first the new episodes of your library (not watched, out in the last 30 days, newest
first), then the episodes you stopped halfway (last watched first). Works for every add-on that fills the Kodi library
(NLZiet, Videoland, Lucent Video ...). Each tile is the library episode itself, so playing it resumes and marks it as
watched in the library like any library item."""
import json
import sys
import urllib.parse

import xbmc
import xbmcgui
import xbmcplugin

NEW_DAYS = 30
LIMIT = 40
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


def lib_continue_new():
    new = episodes({"and": [{"field": "playcount", "operator": "is", "value": "0"},
                            {"field": "airdate", "operator": "inthelast", "value": f"{NEW_DAYS} days"},
                            {"field": "inprogress", "operator": "false", "value": ""}]},
                   {"method": "date", "order": "descending"})
    going = episodes({"field": "inprogress", "operator": "true", "value": ""}, {"method": "lastplayed", "order": "descending"})
    seen, rows = set(), []
    for ep in new + going:
        if ep["episodeid"] in seen:
            continue
        seen.add(ep["episodeid"])
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
