"""Lucent Bibliotheek: small jobs for the Lucent skin.

    status        counts and last update -> Window(home).Property(lucent.lib.*) (Skin settings > Library)
    update        a full run now (same as starting the add-on)
    surprise      pick something from your library you have not seen yet (asks film / series and genre)
    pushwatched   (from service.py) a watched mark you set in Kodi goes to Trakt too
"""
import json
import os
import random
import time

import xbmc
import xbmcgui
import xbmcvfs

import lib

HOME = xbmcgui.Window(10000)
NL = lib.NL
LAST = os.path.join(os.path.dirname(lib.ENABLED), "last_run")
OURS = lib.ADDON_ID     # every file of ours sits under addon_data/script.lucent.library/


def t(nl, en):
    return nl if NL else en


def log(text):
    lib.log(f"tools: {text}")


def total(method, field, params=None):
    params = dict(params or {})
    params["limits"] = {"start": 0, "end": 1}
    result = lib.rpc(method, params)
    return int((result.get("limits") or {}).get("total") or len(result.get(field, [])))


# ----------------------------------------------------------------------------- status
def status():
    unwatched = {"field": "playcount", "operator": "is", "value": "0"}
    HOME.setProperty("lucent.lib.movies", str(total("VideoLibrary.GetMovies", "movies")))
    HOME.setProperty("lucent.lib.shows", str(total("VideoLibrary.GetTVShows", "tvshows")))
    HOME.setProperty("lucent.lib.episodes", str(total("VideoLibrary.GetEpisodes", "episodes")))
    HOME.setProperty("lucent.lib.unwatched", str(total("VideoLibrary.GetMovies", "movies", {"filter": unwatched})))
    try:
        stamp = os.path.getmtime(LAST)
        HOME.setProperty("lucent.lib.last", time.strftime("%d-%m-%Y %H:%M", time.localtime(stamp)))
    except OSError:
        HOME.setProperty("lucent.lib.last", t("nog nooit", "never"))
    HOME.setProperty("lucent.lib.on", "1" if os.path.exists(lib.ENABLED) else "")


def mark_run():
    os.makedirs(os.path.dirname(LAST), exist_ok=True)
    with open(LAST, "w") as fh:
        fh.write(str(time.time()))


# ----------------------------------------------------------------------------- surprise me
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
        for g in lib.rpc("VideoLibrary.GetGenres", {"type": kind}).get("genres", []):
            genres.add(g.get("label", ""))
    genres = sorted(g for g in genres if g)
    choice = xbmcgui.Dialog().select(t("Welk genre?", "Which genre?"), [t("Alle genres", "All genres")] + genres)
    if choice < 0:
        return
    genre = genres[choice - 1] if choice > 0 else ""
    found = []
    for kind, method, field, idname in pools:
        rules = [{"field": "playcount", "operator": "is", "value": "0"}]
        if genre:
            rules.append({"field": "genre", "operator": "is", "value": genre})
        flt = {"and": rules} if len(rules) > 1 else rules[0]
        props = ["title", "year", "art", "plot", "genre", "rating", "file"] + (["runtime"] if kind == "movie" else [])
        if kind == "tvshow":   # a series counts when not every episode is watched
            flt = {"field": "genre", "operator": "is", "value": genre} if genre else None
            props.append("watchedepisodes")
            props.append("episode")
        params = {"properties": props}
        if flt:
            params["filter"] = flt
        for item in lib.rpc(method, params).get(field, []):
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


# ----------------------------------------------------------------------------- watched -> Trakt
def push_watched(marks):
    """Watched / unwatched marks set by hand in Kodi: the same on Trakt, in one request each way (Seren's login).
    marks = [(kind, kodi id, playcount)]. The Trakt ids come from our own .strm files."""
    import quick
    add, remove = {"movies": [], "episodes": []}, {"movies": [], "episodes": []}
    for kind, item_id, playcount in marks:
        if kind == "movie":
            d = lib.rpc("VideoLibrary.GetMovieDetails", {"movieid": item_id, "properties": ["file"]}).get("moviedetails", {})
        elif kind == "episode":
            d = lib.rpc("VideoLibrary.GetEpisodeDetails", {"episodeid": item_id, "properties": ["file"]}).get("episodedetails", {})
        else:
            continue
        f = d.get("file", "")
        if OURS not in f or not f.endswith(".strm"):
            continue
        trakt = quick.strm_ids(xbmcvfs.translatePath(f)).get("trakt_id")
        if not str(trakt).isdigit():
            continue
        (add if playcount else remove)["movies" if kind == "movie" else "episodes"].append({"ids": {"trakt": int(trakt)}})
    if not any(add.values()) and not any(remove.values()):
        return
    trakt = quick.Trakt()
    for path, body in (("sync/history", add), ("sync/history/remove", remove)):
        body = {k: v for k, v in body.items() if v}
        if body:
            try:
                trakt.call(path, body)
                log(f"push watched: {path} {sum(len(v) for v in body.values())} items")
            except Exception as error:  # noqa: BLE001
                log(f"push watched {path}: {error}")


def ids_of(unique):
    ids = {}
    for k, v in (unique or {}).items():
        if k in ("trakt", "tmdb", "tvdb") and str(v).isdigit():
            ids[k] = int(v)
        elif k == "imdb" and str(v).startswith("tt"):
            ids[k] = str(v)
    return ids


# ----------------------------------------------------------------------------- film collections
def next_in_set(args):
    """Kijk de volgende: the first film of this collection (by year) you have not seen yet - resume if started."""
    import re
    path = ",".join(args)
    match = re.search(r"videodb://movies/sets/(\d+)", path)
    if not match:
        return
    detail = lib.rpc("VideoLibrary.GetMovieSetDetails", {
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
    xbmc.executebuiltin(f'PlayMedia("{film["file"]}")' if not (film.get("resume") or {}).get("position")
                        else f'PlayMedia("{film["file"]}",resume)')


def run(action, args):
    if action == "status":
        status()
    elif action == "update":
        lib.run(manual=True)
        status()
    elif action == "surprise":
        surprise(args)
    elif action == "nextinset":
        next_in_set(args)
    elif action == "pushwatched" and len(args) >= 3:
        push_watched([(args[0], int(args[1]), int(args[2]))])
