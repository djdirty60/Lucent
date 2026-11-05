"""Home rows straight from Kodi's own library (fast, no internet, no Seren call).

    plugin://script.lucent.library/?action=lib&kind=continue   films and episodes you stopped halfway
    plugin://script.lucent.library/?action=lib&kind=nextup     the next episode of every series you watch
    plugin://script.lucent.library/?action=lib&kind=newepisodes series you watch that got episodes you have not seen
    plugin://script.lucent.library/?action=lib&kind=newin      new in your collection (films and series together)
    ...&only=movie / &only=tv                                    continue / newin with only films or only series

Every item carries its library number (DBID), so the info page, watched marks and Play work as in Kodi's own lists.
"""
import json
import urllib.parse

import xbmc
import xbmcgui
import xbmcplugin

LIMIT = 25
M_PROPS = ["title", "ratings", "art", "plot", "year", "genre", "rating", "playcount", "resume", "runtime", "file", "premiered",
           "mpaa", "uniqueid", "dateadded", "lastplayed", "tagline", "studio"]
E_PROPS = ["title", "ratings", "art", "plot", "season", "episode", "showtitle", "tvshowid", "rating", "playcount", "resume",
           "runtime", "file", "firstaired", "uniqueid", "dateadded", "lastplayed"]
NL_ROWS = xbmc.getLanguage(xbmc.ISO_639_1) == "nl"
S_PROPS = ["title", "ratings", "art", "plot", "year", "genre", "rating", "playcount", "file", "premiered", "mpaa", "uniqueid",
           "dateadded", "lastplayed", "episode", "watchedepisodes", "season", "status", "studio"]


def rpc(method, params):
    request = {"jsonrpc": "2.0", "id": 1, "method": method, "params": params}
    answer = json.loads(xbmc.executeJSONRPC(json.dumps(request)))
    if "error" in answer and "status" in (params.get("properties") or []):   # Kodi 20 has no series status yet
        params = dict(params, properties=[p for p in params["properties"] if p != "status"])
        return rpc(method, params)
    if "error" in answer:
        xbmc.log(f"[script.lucent.library] lib rows {method}: {answer['error']}", xbmc.LOGINFO)
    return answer.get("result", {})


def episodes(params):
    return rpc("VideoLibrary.GetEpisodes", params).get("episodes", [])


# ----------------------------------------------------------------------------- the rows
def continue_watching(only=""):
    flt = {"field": "inprogress", "operator": "true", "value": ""}
    sort = {"method": "lastplayed", "order": "descending"}
    films = [] if only == "tv" else rpc("VideoLibrary.GetMovies", {"properties": M_PROPS, "filter": flt, "sort": sort,
                                                                   "limits": {"end": LIMIT}}).get("movies", [])
    eps = [] if only == "movie" else episodes({"properties": E_PROPS, "filter": flt, "sort": sort, "limits": {"end": LIMIT}})
    items = [("movie", m) for m in films] + [("episode", e) for e in eps]
    items.sort(key=lambda x: x[1].get("lastplayed") or "", reverse=True)
    return items[:LIMIT]


def next_up(only=""):
    """Per series you have started (newest watched first): the episode after the last one you saw."""
    shows = rpc("VideoLibrary.GetTVShows", {
        "properties": ["title", "lastplayed", "watchedepisodes", "episode", "art"],
        "filter": {"field": "inprogress", "operator": "true", "value": ""},
        "sort": {"method": "lastplayed", "order": "descending"}, "limits": {"end": LIMIT}}).get("tvshows", [])
    out = []
    for show in shows:
        sid = show["tvshowid"]
        resume = episodes({"tvshowid": sid, "properties": E_PROPS, "limits": {"end": 1},
                           "filter": {"field": "inprogress", "operator": "true", "value": ""}})
        if resume:
            out.append(("episode", resume[0]))
            continue
        last = episodes({"tvshowid": sid, "properties": ["season", "episode"], "limits": {"end": 1},
                         "filter": {"field": "playcount", "operator": "greaterthan", "value": "0"},
                         "sort": {"method": "episode", "order": "descending"}})
        unseen = [{"field": "playcount", "operator": "is", "value": "0"},
                  {"field": "season", "operator": "greaterthan", "value": "0"}]
        nxt = []
        if last:                                      # the first unseen one after the last one you saw
            s, e = str(last[0].get("season", 0)), str(last[0].get("episode", 0))
            after = {"or": [{"field": "season", "operator": "greaterthan", "value": s},
                            {"and": [{"field": "season", "operator": "is", "value": s},
                                     {"field": "episode", "operator": "greaterthan", "value": e}]}]}
            nxt = episodes({"tvshowid": sid, "properties": E_PROPS, "filter": {"and": unseen + [after]},
                            "sort": {"method": "episode", "order": "ascending"}, "limits": {"end": 1}})
        if not nxt:
            nxt = episodes({"tvshowid": sid, "properties": E_PROPS, "filter": {"and": unseen},
                            "sort": {"method": "episode", "order": "ascending"}, "limits": {"end": 1}})
        if nxt:
            out.append(("episode", nxt[0]))
    return out


def new_episodes(only=""):
    """Series you watch (at least one episode seen) that got episodes in the last two weeks you have not seen."""
    rules = [{"field": "playcount", "operator": "is", "value": "0"},
             {"field": "dateadded", "operator": "inthelast", "value": "14 days"}]
    recent = episodes({"properties": ["tvshowid", "dateadded"], "filter": {"and": rules},
                       "sort": {"method": "dateadded", "order": "descending"}})
    order, count = [], {}
    for ep in recent:
        sid = ep.get("tvshowid")
        if sid not in count:
            order.append(sid)
            count[sid] = 0
        count[sid] += 1
    out = []
    for sid in order[:LIMIT]:
        show = rpc("VideoLibrary.GetTVShowDetails", {"tvshowid": sid, "properties": S_PROPS}).get("tvshowdetails", {})
        if show and show.get("watchedepisodes"):
            show["newcount"] = count[sid]
            out.append(("tvshow", show))
    return out


def new_in_collection(only=""):
    sort = {"method": "dateadded", "order": "descending"}
    films = [] if only == "tv" else rpc("VideoLibrary.GetMovies", {"properties": M_PROPS, "sort": sort, "limits": {"end": LIMIT}}).get("movies", [])
    shows = [] if only == "movie" else rpc("VideoLibrary.GetTVShows", {"properties": S_PROPS, "sort": sort, "limits": {"end": LIMIT}}).get("tvshows", [])
    items = [("movie", m) for m in films] + [("tvshow", s) for s in shows]
    items.sort(key=lambda x: x[1].get("dateadded") or "", reverse=True)
    return items[:LIMIT]


def _all(kind, flt=None, sort=None, limit=None):
    method, field, props = ("VideoLibrary.GetMovies", "movies", M_PROPS) if kind == "movie" else \
        ("VideoLibrary.GetTVShows", "tvshows", S_PROPS)
    params = {"properties": props, "sort": sort or {"method": "sorttitle", "order": "ascending", "ignorearticle": True}}
    if flt:
        params["filter"] = flt
    if limit:
        params["limits"] = {"end": limit}
    return [(kind, d) for d in rpc(method, params).get(field, [])]


def unwatched(kind):
    """Films you have not seen / series with episodes you have not seen."""
    if kind == "movie":
        return _all("movie", {"field": "playcount", "operator": "is", "value": "0"})
    return _all("tvshow", {"field": "playcount", "operator": "is", "value": "0"})   # a series counts as seen when every episode is


def short(kind):
    """Films shorter than two hours (runtime in seconds)."""
    return [(k, d) for k, d in _all("movie") if 0 < (d.get("runtime") or 0) <= 7200]


def recent(kind):
    """Added to your collection in the last 30 days, newest first."""
    return _all(kind, {"field": "dateadded", "operator": "inthelast", "value": "30 days"},
                {"method": "dateadded", "order": "descending"})



SEASONS_FILE = None


def new_seasons(only=""):
    """Series in your library whose new season starts within 45 days or started in the last 21 (TMDb, kept 12 hours)."""
    import datetime
    import os
    import time
    import tmdbwidgets
    global SEASONS_FILE
    if SEASONS_FILE is None:
        import lib
        SEASONS_FILE = os.path.join(lib.DATA, "seasons.json")
    import lib
    cache = lib.read_json(SEASONS_FILE, {}) or {}
    shows = rpc("VideoLibrary.GetTVShows", {"properties": S_PROPS}).get("tvshows", [])
    today = datetime.date.today()
    asked, now, out = 0, time.time(), []
    for show in shows:
        status = str(show.get("status") or "").lower()
        if "ended" in status or "cancel" in status:
            continue                                   # Kodi 21+: the series is finished
        if "ended" in str((cache.get(str((show.get("uniqueid") or {}).get("tmdb") or "")) or {}).get("status", "")).lower():
            continue
        tmdb = str((show.get("uniqueid") or {}).get("tmdb") or "")
        if not tmdb.isdigit():
            continue
        entry = cache.get(tmdb)
        if (not entry or now - entry.get("t", 0) > 12 * 3600) and asked < 30:
            asked += 1
            d = tmdbwidgets.tmdb_get(f"tv/{tmdb}") or {}
            if d:
                entry = {"t": now, "next": d.get("next_episode_to_air") or {}, "last": d.get("last_episode_to_air") or {},
                         "status": d.get("status") or ""}
                cache[tmdb] = entry
        if not entry:
            continue
        for key, lo, hi, nl_word, en_word in (("next", 0, 45, "vanaf", "from"), ("last", -21, 0, "sinds", "since")):
            ep = entry.get(key) or {}
            try:
                day = datetime.date.fromisoformat(ep.get("air_date") or "")
            except ValueError:
                continue
            delta = (day - today).days
            if ep.get("episode_number") == 1 and (ep.get("season_number") or 0) > 1 and lo <= delta <= hi:
                when = f"{day.day}-{day.month}"
                show = dict(show)
                show["seasonnote"] = (f"Seizoen {ep['season_number']} {nl_word} {when}" if NL_ROWS
                                      else f"Season {ep['season_number']} {en_word} {when}")
                show["seasonday"] = abs(delta)
                show["plot"] = show["seasonnote"] + (" – " + show["plot"] if show.get("plot") else "")
                out.append(("tvshow", show))
                break
    lib.write_json(SEASONS_FILE, cache)
    out.sort(key=lambda x: x[1]["seasonday"])
    return out[:LIMIT]

ROWS = {"continue": continue_watching, "nextup": next_up, "newepisodes": new_episodes, "newin": new_in_collection,
        "newseasons": new_seasons}
FILTERS = {"unwatched": unwatched, "short": short, "recent": recent}


# ----------------------------------------------------------------------------- list items
def listitem(kind, d):
    label = d.get("title") or d.get("label") or ""
    li = xbmcgui.ListItem(label, offscreen=True)
    art = {k: v for k, v in (d.get("art") or {}).items() if v}
    li.setArt(art)                                 # episodes keep tvshow.poster / tvshow.clearlogo like Kodi's own lists
    tag = li.getVideoInfoTag()
    tag.setMediaType(kind)
    idname = {"movie": "movieid", "episode": "episodeid", "tvshow": "tvshowid"}[kind]
    if d.get(idname) is not None:
        tag.setDbId(int(d[idname]))
    tag.setTitle(label)
    tag.setPlot(d.get("plot") or "")
    if d.get("year"):
        tag.setYear(int(d["year"]))
    if d.get("genre"):
        tag.setGenres(list(d["genre"]))
    scores = {k: (float(v.get("rating") or 0), int(v.get("votes") or 0)) for k, v in (d.get("ratings") or {}).items()
              if isinstance(v, dict) and v.get("rating")}
    if scores:                                     # all of them (IMDb, Trakt, TMDB), so Lucent shows the same scores as for Seren
        default = next((k for k, v in d["ratings"].items() if isinstance(v, dict) and v.get("default")), next(iter(scores)))
        tag.setRatings(scores, default)
    elif d.get("rating"):
        tag.setRating(float(d["rating"]))
    if d.get("mpaa"):
        tag.setMpaa(d["mpaa"])
    if d.get("premiered"):
        tag.setPremiered(d["premiered"])
    if d.get("runtime"):
        tag.setDuration(int(d["runtime"]))
    if d.get("uniqueid"):
        tag.setUniqueIDs({k: str(v) for k, v in d["uniqueid"].items() if v})
    tag.setPlaycount(int(d.get("playcount") or 0))
    if kind == "episode":
        tag.setTvShowTitle(d.get("showtitle") or "")
        tag.setSeason(int(d.get("season") or 0))
        tag.setEpisode(int(d.get("episode") or 0))
        if d.get("firstaired"):
            tag.setFirstAired(d["firstaired"])
        li.setProperty("TvShowDBID", str(d.get("tvshowid", "")))
    if kind == "tvshow":
        total, seen = int(d.get("episode") or 0), int(d.get("watchedepisodes") or 0)
        li.setProperty("TotalEpisodes", str(total))
        li.setProperty("WatchedEpisodes", str(seen))
        li.setProperty("UnWatchedEpisodes", str(max(0, total - seen)))
        if d.get("newcount"):
            li.setProperty("NewEpisodes", str(d["newcount"]))
        if d.get("status"):
            tag.setTvShowStatus(d["status"])
        if d.get("seasonnote"):
            li.setLabel2(d["seasonnote"])
            li.setProperty("seasonnote", d["seasonnote"])
    resume = d.get("resume") or {}
    if resume.get("position"):
        tag.setResumePoint(float(resume["position"]), float(resume.get("total") or 0))
    if kind == "tvshow":
        path = f"videodb://tvshows/titles/{d['tvshowid']}/"
        return path, li, True
    li.setProperty("IsPlayable", "true")
    return d.get("file") or "", li, False


def show(handle, query):
    q = dict(urllib.parse.parse_qsl(query.lstrip("?")))
    row = ROWS.get(q.get("kind", ""))
    items = []
    try:
        if q.get("kind") == "showinfo":            # one series, for its scores on Lucent's season page
            sid = int(q.get("dbid") or 0)
            show = rpc("VideoLibrary.GetTVShowDetails", {"tvshowid": sid, "properties": S_PROPS}).get("tvshowdetails") if sid > 0 else None
            items = [("tvshow", show)] if show else []
        elif q.get("kind") in FILTERS:
            items = FILTERS[q["kind"]]("movie" if q.get("type", "movie") == "movie" else "tvshow")
        else:
            only = q.get("only", "")                # only=movie / only=tv: films or series of a mixed row
            items = row(only if only in ("movie", "tv") else "") if row else []
    except Exception as error:  # noqa: BLE001
        xbmc.log(f"[script.lucent.library] lib row {q.get('kind')}: {error}", xbmc.LOGINFO)
    kinds = [k for k, _ in items]
    content = "movies" if kinds and kinds.count("movie") == len(kinds) else \
        "episodes" if kinds and kinds.count("episode") > len(kinds) / 2 else \
        "tvshows" if kinds and kinds.count("tvshow") == len(kinds) else "videos"
    xbmcplugin.setContent(handle, content)
    # keep this order: without a sort method Kodi sorts a row of only films / only episodes on its title itself
    # ("As the source gives it" looked random on a Films or Series tab; a mixed row was not touched)
    xbmcplugin.addSortMethod(handle, xbmcplugin.SORT_METHOD_NONE)
    xbmcplugin.addDirectoryItems(handle, [listitem(k, d) for k, d in items], len(items))
    xbmcplugin.endOfDirectory(handle, succeeded=True, cacheToDisc=False)
