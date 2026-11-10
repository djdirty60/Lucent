# -*- coding: utf-8 -*-
"""Trakt collection -> .strm and .nfo files for the Kodi video library, without Seren.

Careful by design (the same rules as Lucent Library):
  - a failed Trakt or TMDB request never removes anything;
  - a title is only removed after it was missing in two runs at least SAFE_HOURS apart;
  - when far fewer titles come back than before, nothing is removed without asking;
  - a title keeps the folder it got the first time; only files in our own folder are touched.
"""
from concurrent.futures import ThreadPoolExecutor
import json
import os
import re
import shutil
import time
from xml.sax.saxutils import escape

import xbmc
import xbmcgui
import xbmcvfs

import tmdb
import tracker
import users
import util

T = util.T
MOVIES_SPECIAL = "special://profile/addon_data/%s/library/movies/" % util.ADDON_ID
SHOWS_SPECIAL = "special://profile/addon_data/%s/library/tvshows/" % util.ADDON_ID
MOVIES = xbmcvfs.translatePath(MOVIES_SPECIAL)
SHOWS = xbmcvfs.translatePath(SHOWS_SPECIAL)
FOLDERS = "library_folders.json"
MISSING = "library_missing.json"
LAST = "library_last.json"
LOCK = os.path.join(util.PROFILE, "library.lock")
SAFE_HOURS = 3
SHRINK = 0.2
SHRINK_MIN = 25
NAME_BYTES = 150
BATCH = 50


def safe_name(text):
    name = re.sub(r"\s+", " ", re.sub(r'[<>:"/\\|?*\x00-\x1f]', "", str(text))).strip(" .")
    return name.encode("utf-8")[:NAME_BYTES].decode("utf-8", "ignore").strip(" .") or "titel"


def tag(name, value):
    return "  <%s>%s</%s>\n" % (name, escape(str(value)), name) if value not in (None, "", 0, [], {}) else ""


def write_if_changed(path, text):
    try:
        with open(path, encoding="utf-8") as handle:
            if handle.read() == text:
                return False
    except OSError:
        pass
    with open(path + ".tmp", "w", encoding="utf-8") as handle:
        handle.write(text)
    os.replace(path + ".tmp", path)
    return True


def rating_block(meta):
    if not meta.get("rating"):
        return ""
    return ('  <ratings><rating name="tmdb" max="10" default="true"><value>%s</value><votes>%s</votes></rating></ratings>\n'
            % (meta["rating"], meta.get("votes") or 0))


def _preview(url):
    return url.replace("/w1280/", "/w300/").replace("/w500/", "/w185/")


def art_block(meta):
    """Every picture TMDB has, so Kodi's 'Choose art' offers them all. The first of each kind is the one used."""
    gallery = meta.get("gallery") or {}
    out = ""
    for kind, key in (("poster", "poster"), ("clearlogo", "logo"), ("landscape", None)):
        urls = list(dict.fromkeys(([meta[key]] if key and meta.get(key) else []) + (gallery.get(kind) or [])))
        out += "".join('  <thumb aspect="%s" preview="%s">%s</thumb>\n' % (kind, escape(_preview(u)), escape(u)) for u in urls)
    for season in meta.get("seasons") or []:
        if season.get("poster_path"):
            url = tmdb.image(season["poster_path"], "w500")
            out += '  <thumb aspect="poster" type="season" season="%d" preview="%s">%s</thumb>\n' % (season["season_number"], escape(_preview(url)), escape(url))
    fanart = list(dict.fromkeys(([meta["fanart"]] if meta.get("fanart") else []) + (gallery.get("fanart") or [])))
    if fanart:
        out += "  <fanart>\n%s  </fanart>\n" % "".join('    <thumb preview="%s">%s</thumb>\n' % (escape(_preview(u)), escape(u)) for u in fanart)
    return out


def people_block(meta):
    out = "".join(tag("genre", g) + "" for g in meta.get("genres") or [])
    out += "".join(tag("studio", s) for s in meta.get("studios") or [])
    out += "".join(tag("director", d) for d in meta.get("directors") or [])
    out += "".join(tag("credits", w) for w in meta.get("writers") or [])
    for order, person in enumerate(meta.get("cast") or []):
        out += ("  <actor>\n  " + tag("name", person["name"]) + "  " + tag("role", person.get("role")) + "  "
                + tag("thumb", person.get("thumb")) + "    <order>%d</order>\n  </actor>\n" % order)
    return out


def ids_block(meta):
    out = '  <uniqueid type="tmdb" default="true">%s</uniqueid>\n' % meta["tmdb"]
    if str(meta.get("imdb") or "").startswith("tt"):
        out += '  <uniqueid type="imdb">%s</uniqueid>\n' % escape(meta["imdb"])
    return out


def base_block(meta):
    return (tag("title", meta["title"]) + tag("originaltitle", meta.get("original_title")) + tag("year", meta.get("year"))
            + tag("plot", meta.get("plot")) + tag("tagline", meta.get("tagline")) + tag("runtime", meta.get("runtime"))
            + tag("premiered", meta.get("premiered")) + tag("trailer", meta.get("trailer")) + tag("mpaa", meta.get("mpaa")) + rating_block(meta) + ids_block(meta) + people_block(meta) + art_block(meta))


HEAD = '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'


def movie_nfo(meta, added):
    extra = "  <set><name>%s</name></set>\n" % escape(meta["set"]) if meta.get("set") else ""
    return HEAD + "<movie>\n" + base_block(meta) + extra + tag("dateadded", added) + "</movie>\n"


def show_nfo(show):
    return HEAD + "<tvshow>\n" + base_block(show) + "</tvshow>\n"


def episode_nfo(show, raw, added):
    return (HEAD + "<episodedetails>\n" + tag("title", raw.get("name")) + tag("showtitle", show["title"])
            + '  <season>%d</season>\n  <episode>%d</episode>\n' % (raw["season_number"], raw["episode_number"])
            + tag("plot", raw.get("overview")) + tag("aired", raw.get("air_date")) + tag("premiered", raw.get("air_date"))
            + tag("runtime", raw.get("runtime") or show.get("runtime"))
            + ('  <thumb>%s</thumb>\n' % escape(tmdb.image(raw["still_path"], "w780")) if raw.get("still_path") else "")
            + tag("dateadded", added) + "</episodedetails>\n")


def stamp(text):
    return str(text or "").replace("T", " ")[:19]


def plan(prefix, rows, folders):
    """rows: [(tmdb id, title, year)]. Gives every title a folder that stays the same; names are compared without case."""
    taken, out = {}, {}
    for tmdb_id, _title, _year in rows:
        old = folders.get("%s:%s" % (prefix, tmdb_id))
        if old:
            taken[old.casefold()] = tmdb_id
            out[tmdb_id] = old
    for tmdb_id, title, year in rows:
        if tmdb_id in out:
            continue
        base = safe_name("%s (%s)" % (title, year) if year else title)
        name = base if base.casefold() not in taken else safe_name("%s [%s]" % (base, tmdb_id))
        taken[name.casefold()] = tmdb_id
        out[tmdb_id] = name
        folders["%s:%s" % (prefix, tmdb_id)] = name
    return out


def remove_gone(kind, base, wanted, total, manual):
    """Returns (removed, held back)."""
    existing = [d for d in os.listdir(base) if os.path.isdir(os.path.join(base, d))]
    gone = [d for d in existing if d not in wanted]
    missing = util.load_json(MISSING, {})
    for key in [k for k in missing if k.startswith(kind + "/") and k.split("/", 1)[1] not in gone]:
        missing.pop(key)
    removed, held = 0, 0
    if gone:
        too_many = total == 0 or len(gone) > max(SHRINK_MIN, SHRINK * len(existing))
        allowed = False
        if too_many:
            word = T("films", "films") if kind == "movies" else T("series", "shows")
            util.log("%s: %d of %d would go, nothing removed without asking" % (kind, len(gone), len(existing)))
            allowed = bool(manual and total) and xbmcgui.Dialog().yesno("Lucent", T(
                "Volgens Trakt staan %d %s niet meer in je collectie. Uit de bibliotheek halen?",
                "Trakt says %d %s are no longer in your collection. Remove them from the library?") % (len(gone), word))
            if not allowed:
                util.save_json(MISSING, missing)
                return 0, len(gone)
        now = time.time()
        for folder in gone:
            key = "%s/%s" % (kind, folder)
            first = missing.setdefault(key, now)
            if allowed or now - first >= SAFE_HOURS * 3600:
                shutil.rmtree(os.path.join(base, folder), ignore_errors=True)
                missing.pop(key, None)
                removed += 1
            else:
                held += 1
    util.save_json(MISSING, missing)
    return removed, held


def export_movies(manual, folders):
    collection = tracker.library_rows("movies")
    metas = {}
    def load(row):
        tmdb_id = str(row["movie"]["ids"]["tmdb"])
        return tmdb_id, tmdb.details("movie", tmdb_id)
    with ThreadPoolExecutor(max_workers=8) as pool:
        metas = dict(pool.map(load, collection))
    rows = [(str(r["movie"]["ids"]["tmdb"]), r["movie"].get("title") or "film", r["movie"].get("year")) for r in collection]
    names = plan("movie", rows, folders)
    wanted, changed = set(names.values()), 0
    for row in collection:
        tmdb_id = str(row["movie"]["ids"]["tmdb"])
        meta = metas.get(tmdb_id)
        if not meta:                     # TMDB failed: leave what is there and try again next time
            continue
        folder = names[tmdb_id]
        path = os.path.join(MOVIES, folder)
        os.makedirs(path, exist_ok=True)
        strm = util.url_for(action="play", type="movie", tmdb=tmdb_id, lib=1) + "\n"
        changed += write_if_changed(os.path.join(path, folder + ".strm"), strm)
        nfo = os.path.join(path, folder + ".nfo")
        existed = os.path.exists(nfo)
        if write_if_changed(nfo, movie_nfo(meta, stamp(row.get("collected_at")))):
            changed += 1
            if existed:
                REFRESH.add(path)
    removed, held = remove_gone("movies", MOVIES, wanted, len(collection), manual)
    return len(collection), changed, removed, held


def _load_show(row):
    tmdb_id = str(row["show"]["ids"]["tmdb"])
    show = tmdb.details("tvshow", tmdb_id)
    if not show:
        return tmdb_id, None, []
    seasons, complete = [], True
    for entry in show["seasons"]:
        try:
            seasons += [e for e in tmdb.season(tmdb_id, entry["season_number"]).get("episodes") or [] if tmdb.aired(e.get("air_date"))]
        except util.HttpError:
            complete = False
    show["complete"] = complete
    return tmdb_id, show, seasons


def export_shows(manual, folders):
    collection = tracker.library_rows("shows")
    with ThreadPoolExecutor(max_workers=6) as pool:
        loaded = {i: (s, e) for i, s, e in pool.map(_load_show, collection)}
    rows = [(str(r["show"]["ids"]["tmdb"]), r["show"].get("title") or "serie", r["show"].get("year")) for r in collection]
    names = plan("show", rows, folders)
    wanted, changed = set(names.values()), 0
    for row in collection:
        tmdb_id = str(row["show"]["ids"]["tmdb"])
        show, episodes = loaded.get(tmdb_id, (None, []))
        if not show:
            continue
        folder = names[tmdb_id]
        root = os.path.join(SHOWS, folder)
        os.makedirs(root, exist_ok=True)
        existed = os.path.exists(os.path.join(root, "tvshow.nfo"))
        if write_if_changed(os.path.join(root, "tvshow.nfo"), show_nfo(show)):
            changed += 1
            if existed:
                REFRESH.add(root)
        keep = {"tvshow.nfo"}
        added = stamp(row.get("last_collected_at"))
        for raw in episodes:
            season_dir = "Season %02d" % raw["season_number"]
            name = "%s - S%02dE%02d" % (folder, raw["season_number"], raw["episode_number"])
            os.makedirs(os.path.join(root, season_dir), exist_ok=True)
            strm = util.url_for(action="play", type="episode", tmdb=tmdb_id, season=raw["season_number"],
                                episode=raw["episode_number"], lib=1) + "\n"
            changed += write_if_changed(os.path.join(root, season_dir, name + ".strm"), strm)
            changed += write_if_changed(os.path.join(root, season_dir, name + ".nfo"), episode_nfo(show, raw, added))
            keep |= {os.path.join(season_dir, name + ".strm"), os.path.join(season_dir, name + ".nfo")}
        if show.get("complete"):         # only tidy up when every season came back
            for directory, _subdirs, files in os.walk(root):
                for file_name in files:
                    full = os.path.join(directory, file_name)
                    if os.path.relpath(full, root) not in keep and file_name.endswith((".strm", ".nfo")):
                        os.remove(full)
                        changed += 1
    removed, held = remove_gone("shows", SHOWS, wanted, len(collection), manual)
    return len(collection), changed, removed, held


def rpc(method, params=None):
    answer = json.loads(xbmc.executeJSONRPC(json.dumps({"jsonrpc": "2.0", "id": 1, "method": method, "params": params or {}})))
    return answer.get("result") or {}


def rpc_batch(calls):
    for start in range(0, len(calls), BATCH):
        xbmc.executeJSONRPC(json.dumps([{"jsonrpc": "2.0", "id": i, "method": m, "params": p}
                                        for i, (m, p) in enumerate(calls[start:start + BATCH])]))


def source_path(special):
    real = xbmcvfs.translatePath(special).rstrip("/\\")
    for source in rpc("Files.GetSources", {"media": "video"}).get("sources", []):
        path = source.get("file", "")
        if path.rstrip("/") == special.rstrip("/") or xbmcvfs.translatePath(path).rstrip("/\\") == real:
            return path if path.endswith(("/", "\\")) else path + "/"
    return ""


def scanning():
    return xbmc.getCondVisibility("Library.IsScanningVideo")


def wait_idle(limit=1800):
    monitor = xbmc.Monitor()
    end = time.time() + limit
    while scanning() and time.time() < end:
        if monitor.waitForAbort(2):
            return False
    return not scanning()


def scan(path):
    """UpdateLibrary stops a running scan instead of starting one, so wait until Kodi is free."""
    if not path or not wait_idle():
        return False
    xbmc.executebuiltin('UpdateLibrary(video,"%s",false)' % path)
    monitor = xbmc.Monitor()
    for _ in range(30):
        if scanning() or monitor.waitForAbort(1):
            break
    return wait_idle(3600)


REFRESH = set()


def refresh_changed():
    """Kodi only reads a changed .nfo when a title is refreshed: do that for titles whose information or pictures changed."""
    if not REFRESH or not wait_idle():
        return
    folders = {os.path.normcase(os.path.normpath(p)) for p in REFRESH}
    calls = []
    for method, key, id_name, refresh in (("VideoLibrary.GetMovies", "movies", "movieid", "VideoLibrary.RefreshMovie"),
                                          ("VideoLibrary.GetTVShows", "tvshows", "tvshowid", "VideoLibrary.RefreshTVShow")):
        for item in rpc(method, {"properties": ["file"]}).get(key, []):
            path = xbmcvfs.translatePath(item.get("file", ""))
            folder = path if key == "tvshows" else os.path.dirname(path)
            if util.ADDON_ID in path and os.path.normcase(os.path.normpath(folder)) in folders:
                params = {id_name: item[id_name], "ignorenfo": False}
                if key == "tvshows":
                    params["refreshepisodes"] = False
                calls.append((refresh, params))
    REFRESH.clear()
    for method, params in calls:                # one by one: Kodi runs each refresh as its own job
        rpc(method, params)
        wait_idle(600)
    util.log("library: %d titles refreshed" % len(calls))


def prune():
    """Take titles whose files are gone out of Kodi's library, one by one. Only ever touches our own folder."""
    if not wait_idle():
        return
    calls = []
    for movie in rpc("VideoLibrary.GetMovies", {"properties": ["file"]}).get("movies", []):
        if _ours(movie) and not xbmcvfs.exists(movie["file"]):
            calls.append(("VideoLibrary.RemoveMovie", {"movieid": movie["movieid"]}))
    for episode in rpc("VideoLibrary.GetEpisodes", {"properties": ["file"]}).get("episodes", []):
        if _ours(episode) and not xbmcvfs.exists(episode["file"]):
            calls.append(("VideoLibrary.RemoveEpisode", {"episodeid": episode["episodeid"]}))
    for show in rpc("VideoLibrary.GetTVShows", {"properties": ["file"]}).get("tvshows", []):
        if util.ADDON_ID in show.get("file", "") and not xbmcvfs.exists(show["file"]):
            calls.append(("VideoLibrary.RemoveTVShow", {"tvshowid": show["tvshowid"]}))
    rpc_batch(calls)
    util.log("library: %d entries pruned" % len(calls))


def _ours(item):
    return util.ADDON_ID in item.get("file", "") and item.get("file", "").endswith(".strm")


def _resume_call(method, id_name, item, percent):
    total = item.get("runtime") or 0
    if not percent or not total:
        return None
    position = int(total * percent / 100.0)
    if abs((item.get("resume") or {}).get("position", 0) - position) < 30:
        return None
    return method, {id_name: item[id_name], "resume": {"position": position, "total": total}}


def sync_state():
    """The account is the truth for what you have seen and where you stopped."""
    if not tracker.refresh():     # never reset 'seen' on a failed answer
        return
    films, shows, paused = tracker.watched_movies(), tracker.watched_episodes(), tracker.paused()
    film_percent = {str(p["movie"]["ids"].get("tmdb")): p.get("progress") for p in paused if p.get("type") == "movie"}
    episode_percent = {(str(p["show"]["ids"].get("tmdb")), p["episode"]["season"], p["episode"]["number"]): p.get("progress")
                       for p in paused if p.get("type") == "episode"}
    calls = []
    props = ["file", "playcount", "uniqueid", "runtime", "resume"]
    for movie in rpc("VideoLibrary.GetMovies", {"properties": props}).get("movies", []):
        if not _ours(movie):
            continue
        tmdb_id = str((movie.get("uniqueid") or {}).get("tmdb"))
        seen = tmdb_id in films
        if seen != bool(movie.get("playcount")):
            calls.append(("VideoLibrary.SetMovieDetails", {"movieid": movie["movieid"], "playcount": 1 if seen else 0}))
        resume = _resume_call("VideoLibrary.SetMovieDetails", "movieid", movie, film_percent.get(tmdb_id))
        if resume:
            calls.append(resume)
    show_ids = {s["tvshowid"]: str((s.get("uniqueid") or {}).get("tmdb"))
                for s in rpc("VideoLibrary.GetTVShows", {"properties": ["uniqueid"]}).get("tvshows", [])}
    props = ["file", "playcount", "season", "episode", "tvshowid", "runtime", "resume"]
    for episode in rpc("VideoLibrary.GetEpisodes", {"properties": props}).get("episodes", []):
        if not _ours(episode):
            continue
        tmdb_id = show_ids.get(episode.get("tvshowid"), "")
        pair = (episode["season"], episode["episode"])
        seen = pair in shows.get(tmdb_id, set())
        if seen != bool(episode.get("playcount")):
            calls.append(("VideoLibrary.SetEpisodeDetails", {"episodeid": episode["episodeid"], "playcount": 1 if seen else 0}))
        resume = _resume_call("VideoLibrary.SetEpisodeDetails", "episodeid", episode, episode_percent.get((tmdb_id,) + pair))
        if resume:
            calls.append(resume)
    rpc_batch(calls)
    util.log("library: %d seen/resume changes" % len(calls))


class Busy:
    def __enter__(self):
        os.makedirs(util.PROFILE, exist_ok=True)
        try:
            if time.time() - os.path.getmtime(LOCK) < 7200:
                return False
        except OSError:
            pass
        with open(LOCK, "w", encoding="utf-8") as handle:
            handle.write("1")
        return True

    def __exit__(self, *_):
        try:
            os.remove(LOCK)
        except OSError:
            pass


HOW_TO = T("Voeg deze map eenmalig toe in Kodi, via Video's > Bestanden > Video's toevoegen:\n%s\nKies bij 'Deze map bevat' %s en als informatiebron The Movie Database.",
           "Add this folder once in Kodi, via Videos > Files > Add videos:\n%s\nSet 'This directory contains' to %s and the information provider to The Movie Database.")


def run(manual=False):
    if users.current_id() != users.MAIN:      # one Kodi library: it follows the first profile
        if manual:
            util.notify(T("De bibliotheek volgt het eerste profiel", "The library follows the first profile"))
        return
    if not tmdb.key():
        if manual:
            xbmcgui.Dialog().ok("Lucent", T("Vul eerst je TMDB-sleutel in.", "Enter your TMDB key first."))
        return
    with Busy() as free:
        if not free:
            if manual:
                util.notify(T("De bibliotheek wordt al bijgewerkt", "The library is already updating"))
            return
        progress = xbmcgui.DialogProgressBG() if manual else None
        if progress:
            progress.create("Lucent", T("Bibliotheek bijwerken...", "Updating the library..."))
        try:
            os.makedirs(MOVIES, exist_ok=True)
            os.makedirs(SHOWS, exist_ok=True)
            folders = util.load_json(FOLDERS, {})
            try:
                films = export_movies(manual, folders)
                if progress:
                    progress.update(50, message=T("Series...", "Shows..."))
                series = export_shows(manual, folders)
            except util.HttpError as error:
                util.log("library stopped, nothing removed: %s" % error, xbmc.LOGERROR)
                if manual:
                    util.notify(T("Je account is niet bereikbaar, er is niets gewijzigd", "Your account cannot be reached, nothing was changed"))
                return
            finally:
                util.save_json(FOLDERS, folders)
            util.log("library: films %s, shows %s (total, changed files, removed, held)" % (films, series))
            util.save_json(LAST, {"at": time.time()})
            missing_sources = []
            restart = False
            for special, result, word, content in ((MOVIES_SPECIAL, films, T("Films", "Movies"), "movies"),
                                                   (SHOWS_SPECIAL, series, T("Series", "TV shows"), "tvshows")):
                path = source_path(special)
                fresh = False
                if not path and result[0] and util.flag("library_auto_sources"):
                    import libsources
                    scannable, changed = libsources.ensure(special, "Lucent Video %s" % word, content)
                    restart = restart or changed
                    if scannable:
                        path, fresh = special, True
                if not path:
                    if result[0]:
                        missing_sources.append(HOW_TO % (special, word))
                    continue
                if progress:
                    progress.update(80, message=word)
                if result[1] or fresh or util.flag("library_force_scan"):
                    scan(path)
            refresh_changed()
            prune()
            sync_state()
        finally:
            if progress:
                progress.close()
    xbmc.executebuiltin("Container.Refresh")
    if manual:
        if missing_sources:
            xbmcgui.Dialog().textviewer("Lucent", "\n\n".join(missing_sources))
        elif restart:
            xbmcgui.Dialog().ok("Lucent", T("De mappen van Lucent Video staan nu in je bibliotheek. Na de volgende herstart van Kodi zie je ze ook bij Video's > Bestanden.",
                                            "Lucent Video's folders are now in your library. After the next restart of Kodi you also see them under Videos > Files."))
        else:
            util.notify(T("Bibliotheek bijgewerkt: %d films, %d series", "Library updated: %d films, %d shows") % (films[0], series[0]))


def publish_status():
    """Home window properties for the skin."""
    linked = tracker.logged_in()
    util.HOME.setProperty("lucent.video.account", tracker.name())
    util.HOME.setProperty("lucent.video.account.user", tracker.user())
    util.HOME.setProperty("lucent.video.trakt", "1" if tracker.name() == "Trakt" else "")
    util.HOME.setProperty("lucent.video.trakt.user", tracker.user() if tracker.name() == "Trakt" else "")
    return linked


def due():
    hours = util.number("library_hours", 12)
    return util.flag("library_on") and time.time() - util.load_json(LAST, {}).get("at", 0) >= hours * 3600
