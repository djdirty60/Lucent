# -*- coding: utf-8 -*-
"""Lucent 2.1.33: the numbers of its series on every episode of the Kodi library, for episode pictures with badges.

Kodi gives an episode of the library no TMDB / IMDb / TVDB number of its series (only the episode's own), and a skin
cannot look one up by the series. So this writes them to each library episode as three extra ids next to the ones it
already has: lshowtmdb, lshowimdb, lshowtvdb (ListItem.UniqueID(lshowtmdb) in the skin). Nothing else of the episode
changes. Only while Lucent Video gives an episode picture pattern (Window(home).Property(lucent.video.episodes)), so a
library is never touched for people who do not use it. Wilfried agreed to this on 16-11-2026.

Run from the helper (worker thread): once after the start, after every library change and every six hours. Only
episodes that miss a number are written; a series refreshed by its scraper gets them again the next time."""
import json

import xbmc
import xbmcgui

HOME = xbmcgui.Window(10000)
KINDS = (("tmdb", "lshowtmdb"), ("imdb", "lshowimdb"), ("tvdb", "lshowtvdb"))


def log(text):
    xbmc.log(f"[skin.lucent] episode ids: {text}", xbmc.LOGINFO)


def rpc(method, params):
    res = json.loads(xbmc.executeJSONRPC(json.dumps({"jsonrpc": "2.0", "id": 1, "method": method, "params": params})))
    return res.get("result") or {}


def wanted():
    return bool(HOME.getProperty("lucent.video.episodes"))


def sync(stop=None):
    """Write the series' numbers to the library episodes that miss them. Returns how many episodes were written."""
    if not wanted():
        return 0
    written = 0
    shows = rpc("VideoLibrary.GetTVShows", {"properties": ["uniqueid"]}).get("tvshows") or []
    for show in shows:
        if stop is not None and stop.is_set():
            break
        ids = show.get("uniqueid") or {}
        extra = {mine: str(ids[kind]) for kind, mine in KINDS if ids.get(kind)}
        if not extra:
            continue
        episodes = rpc("VideoLibrary.GetEpisodes", {"tvshowid": show["tvshowid"], "properties": ["uniqueid"]}).get("episodes") or []
        for ep in episodes:
            have = ep.get("uniqueid") or {}
            if all(have.get(k) == v for k, v in extra.items()):
                continue
            rpc("VideoLibrary.SetEpisodeDetails", {"episodeid": ep["episodeid"], "uniqueid": dict(have, **extra)})
            written += 1
    if written:
        log(f"{written} episodes got the numbers of their series")
    return written
