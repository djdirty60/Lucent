# -*- coding: utf-8 -*-
"""Two Home rows from Kodi's own library that need more than Kodi's own lists can do (taken over from Lucent Library):

  action=list&name=lib_newseasons&widget=1   series in your library whose new season starts within 45 days or started
                                             in the last 21 (TMDB, kept 12 hours)
  action=list&name=lib_newepisodes&widget=1  series you watch that got episodes in the last two weeks you have not seen,
                                             the newest first

Every item is the library's own (with its DBID), so Info, watched marks and Play work as in Kodi's own lists."""
from concurrent.futures import ThreadPoolExecutor
import datetime
import json

import xbmc
import xbmcgui
import xbmcplugin

import tmdb
import util

T = util.T
LIMIT = 25
S_PROPS = ["title", "ratings", "art", "plot", "year", "genre", "rating", "playcount", "file", "premiered", "mpaa", "uniqueid",
           "dateadded", "lastplayed", "episode", "watchedepisodes", "season", "status", "studio"]


def rpc(method, params):
    answer = json.loads(xbmc.executeJSONRPC(json.dumps({"jsonrpc": "2.0", "id": 1, "method": method, "params": params})))
    if "error" in answer and "status" in (params.get("properties") or []):     # Kodi 20 has no series status yet
        return rpc(method, dict(params, properties=[p for p in params["properties"] if p != "status"]))
    return answer.get("result") or {}


def new_episodes():
    rules = [{"field": "playcount", "operator": "is", "value": "0"}, {"field": "dateadded", "operator": "inthelast", "value": "14 days"}]
    recent = rpc("VideoLibrary.GetEpisodes", {"properties": ["tvshowid", "dateadded"], "filter": {"and": rules},
                                              "sort": {"method": "dateadded", "order": "descending"}}).get("episodes", [])
    order, count = [], {}
    for episode in recent:
        show_id = episode.get("tvshowid")
        if show_id not in count:
            order.append(show_id)
            count[show_id] = 0
        count[show_id] += 1
    out = []
    for show_id in order[:LIMIT]:
        show = rpc("VideoLibrary.GetTVShowDetails", {"tvshowid": show_id, "properties": S_PROPS}).get("tvshowdetails") or {}
        if show and show.get("watchedepisodes"):
            show["newcount"] = count[show_id]
            out.append(show)
    return out


def new_seasons():
    today = datetime.date.today()
    out = []
    shows = []
    for show in rpc("VideoLibrary.GetTVShows", {"properties": S_PROPS}).get("tvshows", []):
        status = str(show.get("status") or "").lower()
        tmdb_id = str((show.get("uniqueid") or {}).get("tmdb") or "")
        if "ended" not in status and "cancel" not in status and tmdb_id.isdigit():
            shows.append((show, tmdb_id))

    def load(pair):
        try:
            return pair[0], tmdb.get("tv/%s" % pair[1], ttl=12 * 3600)
        except util.HttpError:
            return pair[0], None
    with ThreadPoolExecutor(max_workers=8) as pool:
        answers = list(pool.map(load, shows))
    for show, raw in answers:
        if not raw:
            continue
        if "ended" in str(raw.get("status") or "").lower():
            continue
        for key, low, high, nl_word, en_word in (("next_episode_to_air", 0, 45, "vanaf", "from"), ("last_episode_to_air", -21, 0, "sinds", "since")):
            episode = raw.get(key) or {}
            try:
                day = datetime.date.fromisoformat(episode.get("air_date") or "")
            except ValueError:
                continue
            delta = (day - today).days
            if episode.get("episode_number") == 1 and (episode.get("season_number") or 0) > 1 and low <= delta <= high:
                note = (T("Seizoen %d %s %d-%d", "Season %d %s %d-%d")
                        % (episode["season_number"], T(nl_word, en_word), day.day, day.month))
                show = dict(show, seasonnote=note, seasonday=abs(delta))
                show["plot"] = note + (" - " + show["plot"] if show.get("plot") else "")
                out.append(show)
                break
    out.sort(key=lambda s: s["seasonday"])
    return out[:LIMIT]


def listitem(show):
    label = show.get("title") or show.get("label") or ""
    item = xbmcgui.ListItem(label, offscreen=True)
    item.setArt({k: v for k, v in (show.get("art") or {}).items() if v})
    tag = item.getVideoInfoTag()
    tag.setMediaType("tvshow")
    tag.setDbId(int(show["tvshowid"]))
    tag.setTitle(label)
    tag.setPlot(show.get("plot") or "")
    if show.get("year"):
        tag.setYear(int(show["year"]))
    tag.setGenres(list(show.get("genre") or []))
    tag.setStudios(list(show.get("studio") or []))
    scores = {k: (float(v.get("rating") or 0), int(v.get("votes") or 0)) for k, v in (show.get("ratings") or {}).items()
              if isinstance(v, dict) and v.get("rating")}
    if scores:
        default = next((k for k, v in show["ratings"].items() if isinstance(v, dict) and v.get("default")), next(iter(scores)))
        tag.setRatings(scores, default)
    if show.get("mpaa"):
        tag.setMpaa(show["mpaa"])
    if show.get("premiered"):
        tag.setPremiered(show["premiered"])
    if show.get("uniqueid"):
        tag.setUniqueIDs({k: str(v) for k, v in show["uniqueid"].items() if v})
    if show.get("status"):
        tag.setTvShowStatus(show["status"])
    tag.setPlaycount(int(show.get("playcount") or 0))
    total, seen = int(show.get("episode") or 0), int(show.get("watchedepisodes") or 0)
    item.setProperty("TotalEpisodes", str(total))
    item.setProperty("WatchedEpisodes", str(seen))
    item.setProperty("UnWatchedEpisodes", str(max(0, total - seen)))
    if show.get("newcount"):
        item.setProperty("NewEpisodes", str(show["newcount"]))
    if show.get("seasonnote"):
        item.setLabel2(show["seasonnote"])
        item.setProperty("seasonnote", show["seasonnote"])
    return "videodb://tvshows/titles/%s/" % show["tvshowid"], item, True


def send_row(handle, name):
    try:
        shows = new_seasons() if name == "lib_newseasons" else new_episodes()
    except Exception as error:      # noqa: BLE001 - an empty row, never an error on Home
        util.log("library row %s: %s" % (name, type(error).__name__))
        shows = []
    rows = [listitem(s) for s in shows]
    xbmcplugin.setContent(handle, "tvshows")
    xbmcplugin.addSortMethod(handle, xbmcplugin.SORT_METHOD_NONE)
    xbmcplugin.addDirectoryItems(handle, rows, len(rows))
    xbmcplugin.endOfDirectory(handle, cacheToDisc=False)
