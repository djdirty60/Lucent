# -*- coding: utf-8 -*-
"""Lucent: small jobs on Kodi's own library, from the side menu of the lists (no other add-on needed).

    RunScript(special://skin/scripts/libtools.py,surprise,<0 film | 1 series | 2 either>)
        something from your library you have not seen yet (asks for a genre), shown on its info page
    RunScript(special://skin/scripts/libtools.py,nextinset,<videodb://movies/sets/<id>/...>)
        play the next film of a collection: the one you started, else the first unseen one (by year)
"""
import json
import random
import re
import sys

import xbmc
import xbmcgui

NL = xbmc.getLanguage(xbmc.ISO_639_1) == "nl"


def t(nl, en):
    return nl if NL else en


def log(text):
    xbmc.log(f"[skin.lucent] libtools: {text}", xbmc.LOGINFO)


def rpc(method, params):
    answer = json.loads(xbmc.executeJSONRPC(json.dumps({"jsonrpc": "2.0", "id": 1, "method": method, "params": params})))
    return answer.get("result") or {}


def surprise(args):
    kinds = [t("Film", "Film"), t("Serie", "Series"), t("Maakt niet uit", "Either")]
    pick = int(args[0]) if args and args[0].isdigit() else xbmcgui.Dialog().select(t("Verras me", "Surprise me"), kinds)
    if pick < 0:
        return
    pools = []
    if pick in (0, 2):
        pools.append(("movie", "VideoLibrary.GetMovies", "movies", "movieid"))
    if pick in (1, 2):
        pools.append(("tvshow", "VideoLibrary.GetTVShows", "tvshows", "tvshowid"))
    genres = set()
    for kind, *_ in pools:
        for genre in rpc("VideoLibrary.GetGenres", {"type": kind}).get("genres", []):
            genres.add(genre.get("label", ""))
    genres = sorted(g for g in genres if g)
    choice = xbmcgui.Dialog().select(t("Welk genre?", "Which genre?"), [t("Alle genres", "All genres")] + genres)
    if choice < 0:
        return
    genre = genres[choice - 1] if choice > 0 else ""
    found = []
    for kind, method, field, idname in pools:
        props = ["title", "year", "art", "plot", "genre", "rating", "file"]
        if kind == "movie":
            rules = [{"field": "playcount", "operator": "is", "value": "0"}]
            if genre:
                rules.append({"field": "genre", "operator": "is", "value": genre})
            flt = {"and": rules} if len(rules) > 1 else rules[0]
        else:                                     # a series counts while not every episode is watched
            flt = {"field": "genre", "operator": "is", "value": genre} if genre else None
            props += ["watchedepisodes", "episode"]
        params = {"properties": props}
        if flt:
            params["filter"] = flt
        for item in rpc(method, params).get(field, []):
            if kind == "tvshow" and item.get("episode") and item.get("watchedepisodes", 0) >= item.get("episode", 0):
                continue
            found.append((kind, idname, item))
    if not found:
        xbmcgui.Dialog().notification("Lucent", t("Niets gevonden dat je nog niet zag", "Nothing unseen found"),
                                      xbmcgui.NOTIFICATION_INFO, 4000)
        return
    kind, idname, item = random.choice(found)
    log(f"surprise: {item.get('title')} ({kind})")
    li = xbmcgui.ListItem(item.get("title", ""), offscreen=True)
    li.setArt(item.get("art") or {})
    li.setPath(item.get("file", ""))
    tag = li.getVideoInfoTag()
    tag.setMediaType(kind)
    tag.setDbId(int(item[idname]))
    tag.setTitle(item.get("title", ""))
    tag.setYear(int(item.get("year") or 0))
    tag.setPlot(item.get("plot", ""))
    tag.setGenres(item.get("genre") or [])
    xbmcgui.Dialog().info(li)


def next_in_set(args):
    match = re.search(r"videodb://movies/sets/(\d+)", ",".join(args))
    if not match:
        return
    detail = rpc("VideoLibrary.GetMovieSetDetails", {
        "setid": int(match.group(1)),
        "movies": {"properties": ["title", "playcount", "file", "year", "resume"], "sort": {"method": "year"}}}).get("setdetails", {})
    films = detail.get("movies", [])
    todo = [m for m in films if (m.get("resume") or {}).get("position")] or [m for m in films if not m.get("playcount")]
    if not todo:
        xbmcgui.Dialog().notification("Lucent", t("Je hebt deze hele collectie gezien", "You have seen this whole collection"),
                                      xbmcgui.NOTIFICATION_INFO, 4000)
        return
    film = todo[0]
    log(f"next in set: {film.get('title')}")
    resume = ",resume" if (film.get("resume") or {}).get("position") else ""
    xbmc.executebuiltin(f'PlayMedia("{film["file"]}"{resume})')


if __name__ == "__main__":
    action = sys.argv[1] if len(sys.argv) > 1 else ""
    if action == "surprise":
        surprise(sys.argv[2:])
    elif action == "nextinset":
        next_in_set(sys.argv[2:])
