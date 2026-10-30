"""Seren (Trakt collection) -> .strm + .nfo files for the Kodi video library.

Safe by design (1.6.0):
  - a title Seren has not shown yet (no details in its database) is still added, named from Seren's raw Trakt data;
  - a title is only removed after it has been missing in two runs at least SAFE_HOURS apart, and never when Seren
    suddenly reports far fewer titles (Seren in the middle of a sync, a rebuilt database, a failed Trakt page);
  - every folder keeps the name it got the first time (no delete + add again when Seren's title changes);
  - one bad title is skipped and logged, it never stops the run;
  - Kodi scans only when no other scan runs (UpdateLibrary stops a running scan instead of starting one),
    on the path exactly as the source was added, and cleans only our own folders.
"""
import json
import os
import pickle
import re
import shutil
import sqlite3
import time
from urllib.parse import parse_qsl, unquote, urlencode
from xml.sax.saxutils import escape

import xbmc
import xbmcaddon
import xbmcgui
import xbmcvfs

ADDON = xbmcaddon.Addon()
ADDON_ID = ADDON.getAddonInfo("id")
NL = xbmc.getLanguage(xbmc.ISO_639_1).lower().startswith("nl")
SEREN_DB = xbmcvfs.translatePath("special://profile/addon_data/plugin.video.seren/traktSync.db")
OUT_SPECIAL = f"special://profile/addon_data/{ADDON_ID}/movies/"
OUT = xbmcvfs.translatePath(OUT_SPECIAL)
TV_SPECIAL = f"special://profile/addon_data/{ADDON_ID}/tvshows/"
TV_OUT = xbmcvfs.translatePath(TV_SPECIAL)
USE_SCRAPER = False     # own data from Seren in the .nfo: Kodi's TMDb scraper failed on ids TMDb answers "Not Found" for (error pop-up)
MARK = ".lucent-library"
ENABLED = xbmcvfs.translatePath(f"special://profile/addon_data/{ADDON_ID}/enabled")


def log(text):
    xbmc.log(f"[{ADDON_ID}] {text}", xbmc.LOGINFO)


def say(text, time_ms=6000):
    xbmcgui.Dialog().notification("Lucent Bibliotheek" if NL else "Lucent Library", text, xbmcgui.NOTIFICATION_INFO, time_ms)


def _load(value):
    if isinstance(value, (bytes, bytearray, memoryview)):
        try:
            return pickle.loads(bytes(value))
        except Exception:  # noqa: BLE001
            return None
    return value


DATA = xbmcvfs.translatePath(f"special://profile/addon_data/{ADDON_ID}/")
FOLDERS = os.path.join(DATA, "folders.json")      # {"movie:<trakt>": "<folder>"} - a folder keeps its name
MISSING = os.path.join(DATA, "missing.json")      # {"movies/<folder>": first time seen missing}
LOCK = os.path.join(DATA, "busy.lock")
EPISODE_WAIT_HOURS = 24   # an episode comes in a day after it was on TV: before that there is often no link yet
NEW_EPISODE_HOURS = 1     # a NEW episode of a series in your library (from your Trakt calendar): this long after airing
SAFE_HOURS = 3            # a title must be gone this long (two runs) before its folder is removed
SHRINK = 0.2              # never remove more than this share of the library in one go ...
SHRINK_MIN = 25           # ... unless it is fewer titles than this
NAME_BYTES = 150          # folder names are cut to this many bytes (file systems allow 255 per name)


def safe_name(text):
    name = re.sub(r"\s+", " ", re.sub(r'[<>:"/\\|?*\x00-\x1f]', "", str(text))).strip(" .")
    name = name.encode("utf-8")[:NAME_BYTES].decode("utf-8", "ignore").strip(" .")   # bytes, not characters
    return name or "film"


def tag(name, value):
    if value in (None, "", [], {}):
        return ""
    return f"  <{name}>{escape(str(value))}</{name}>\n"


def rating_of(info):
    value = info.get("rating")
    votes = info.get("votes")
    if isinstance(value, dict):
        value, votes = value.get("rating"), value.get("votes")
    if value in (None, "", 0):
        for key, entry in info.items():
            if str(key).startswith("rating.") and isinstance(entry, dict) and entry.get("rating"):
                value, votes = entry.get("rating"), entry.get("votes")
                break
    try:
        return float(value), int(votes or 0)
    except (TypeError, ValueError):
        return None, 0


def seren_ratings(info):
    """{'imdb': (8.1, 12000), 'trakt': (...), 'tmdb': (...)} from Seren's info (keys 'rating.<name>')."""
    out = {}
    for key, entry in (info or {}).items():
        if str(key).startswith("rating.") and isinstance(entry, dict):
            try:
                value, votes = float(entry.get("rating") or 0), int(entry.get("votes") or 0)
            except (TypeError, ValueError):
                continue
            if value > 0:
                out[str(key)[7:]] = (round(value, 1), votes)
    return out


def strm_url(args):
    try:
        action_args = json.dumps(json.loads(args) if isinstance(args, str) else args, sort_keys=True)
    except Exception:  # noqa: BLE001
        action_args = args if isinstance(args, str) else json.dumps(args)
    return "plugin://plugin.video.seren/?" + urlencode(sorted({"action": "getSources", "action_args": action_args}.items()))


def ids_nfo(root, tmdb_id, imdb_id, trakt_id, extra=""):
    """Only the TMDB address: the format every Kodi scraper reads ('movie' or 'tv')."""
    kind = "movie" if root == "movie" else "tv"
    return f"https://www.themoviedb.org/{kind}/{tmdb_id}\n"


def nfo_of(trakt_id, tmdb_id, imdb_id, info, art, cast, watched, collected_at):
    if USE_SCRAPER and tmdb_id:
        return ids_nfo("movie", tmdb_id, imdb_id, trakt_id)
    title = info.get("title")
    x = ['<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n<movie>\n']
    x.append(tag("title", title))
    x.append(tag("originaltitle", info.get("originaltitle")))
    x.append(tag("year", info.get("year")))
    x.append(tag("plot", info.get("plot") or info.get("overview")))
    x.append(tag("outline", info.get("plotoutline")))
    x.append(tag("tagline", info.get("tagline")))
    duration = info.get("duration")
    if isinstance(duration, (int, float)) and duration > 0:
        x.append(tag("runtime", int(duration // 60)))
    x.append(tag("mpaa", info.get("mpaa")))
    x.append(tag("premiered", (info.get("premiered") or "")[:10]))
    for g in info.get("genre") or []:
        x.append(tag("genre", g))
    for s in info.get("studio") or []:
        x.append(tag("studio", s))
    for d in info.get("director") or []:
        x.append(tag("director", d))
    for w in info.get("writer") or []:
        x.append(tag("credits", w))
    value, votes = rating_of(info)
    if value:
        x.append(f'  <ratings><rating name="default" max="10" default="true"><value>{value}</value><votes>{votes}</votes></rating></ratings>\n')
    if tmdb_id:
        x.append(f'  <uniqueid type="tmdb" default="true">{tmdb_id}</uniqueid>\n')
    if imdb_id and str(imdb_id).startswith("tt"):
        x.append(f'  <uniqueid type="imdb">{escape(str(imdb_id))}</uniqueid>\n')
    x.append(f'  <uniqueid type="trakt">{trakt_id}</uniqueid>\n')
    if info.get("set"):
        x.append(f"  <set><name>{escape(str(info['set']))}</name></set>\n")
    x.append(tag("trailer", info.get("trailer")))
    if collected_at:
        x.append(tag("dateadded", str(collected_at).replace("T", " ")[:19]))
    x.append(tag("playcount", 1 if watched else 0))
    x.append(art_block(art))
    for i, person in enumerate(cast[:25]):
        if isinstance(person, dict) and person.get("name"):
            x.append("  <actor>\n" + tag("name", person.get("name")) + tag("role", person.get("role")) + tag("thumb", person.get("thumbnail"))
                     + f"    <order>{i}</order>\n  </actor>\n")
    x.append("</movie>\n")
    return "".join(x)


def write_if_changed(path, text):
    try:
        with open(path, "r", encoding="utf-8") as handle:
            if handle.read() == text:
                return False
    except OSError:
        pass
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(text)
    return True


ART_KINDS = ("poster", "banner", "clearlogo", "clearart", "landscape", "discart", "keyart")


def art_block(art, episode=False):
    """Kodi reads artwork from <thumb aspect="..."> and <fanart><thumb> (not from an <art> tag)."""
    def good(v):
        return isinstance(v, str) and v.startswith(("http", "special:", "/"))
    out = ""
    for kind in ART_KINDS:
        if good(art.get(kind)):
            out += f'  <thumb aspect="{kind}">{escape(art[kind])}</thumb>\n'
    if episode and good(art.get("thumb")):
        out += f"  <thumb>{escape(art['thumb'])}</thumb>\n"
    elif episode and good(art.get("fanart")):
        out += f"  <thumb>{escape(art['fanart'])}</thumb>\n"
    if good(art.get("fanart")):
        out += f"  <fanart><thumb>{escape(art['fanart'])}</thumb></fanart>\n"
    return out


def actors_block(cast):
    out = ""
    for i, person in enumerate(cast[:25]):
        if isinstance(person, dict) and person.get("name"):
            out += "  <actor>\n" + tag("name", person.get("name")) + tag("role", person.get("role")) + tag("thumb", person.get("thumbnail")) + f"    <order>{i}</order>\n  </actor>\n"
    return out


def tvshow_nfo(show):
    info = show["info"]
    if USE_SCRAPER and show.get("tmdb_id"):
        extra = f'  <uniqueid type="tvdb">{show["tvdb_id"]}</uniqueid>\n' if show.get("tvdb_id") else ""
        return ids_nfo("tvshow", show.get("tmdb_id"), show.get("imdb_id"), show["trakt_id"], extra)
    x = ['<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n<tvshow>\n']
    x.append(tag("title", info.get("title")))
    x.append(tag("originaltitle", info.get("originaltitle")))
    x.append(tag("year", info.get("year")))
    x.append(tag("plot", info.get("plot") or info.get("overview")))
    x.append(tag("mpaa", info.get("mpaa")))
    x.append(tag("premiered", (info.get("premiered") or "")[:10]))
    x.append(tag("status", info.get("status")))
    for g in info.get("genre") or []:
        x.append(tag("genre", g))
    for s in info.get("studio") or []:
        x.append(tag("studio", s))
    value, votes = rating_of(info)
    if value:
        x.append(f'  <ratings><rating name="default" max="10" default="true"><value>{value}</value><votes>{votes}</votes></rating></ratings>\n')
    if show.get("tvdb_id"):
        x.append(f'  <uniqueid type="tvdb" default="true">{show["tvdb_id"]}</uniqueid>\n')
    if show.get("tmdb_id"):
        x.append(f'  <uniqueid type="tmdb">{show["tmdb_id"]}</uniqueid>\n')
    if show.get("imdb_id") and str(show["imdb_id"]).startswith("tt"):
        x.append(f'  <uniqueid type="imdb">{escape(str(show["imdb_id"]))}</uniqueid>\n')
    x.append(f'  <uniqueid type="trakt">{show["trakt_id"]}</uniqueid>\n')
    x.append(art_block(show["art"]))
    for number, sart in sorted(show.get("season_art", {}).items()):
        poster = sart.get("poster") or sart.get("season.poster")
        if isinstance(poster, str) and poster.startswith(("http", "special:", "/")):
            x.append(f'  <thumb type="season" season="{int(number)}" aspect="poster">{escape(poster)}</thumb>\n')
    for number, name in sorted(show.get("season_names", {}).items()):
        if name and not str(name).lower().startswith(("season", "seizoen")):
            x.append(f'  <namedseason number="{int(number)}">{escape(str(name))}</namedseason>\n')
    x.append(actors_block(show["cast"]))
    x.append("</tvshow>\n")
    return "".join(x)


def episode_nfo(show, trakt_id, season, number, info, art, watched, collected_at):
    x = ['<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n<episodedetails>\n']
    x.append(tag("title", info.get("title") or f"Episode {number}"))
    x.append(tag("showtitle", show["info"].get("title")))
    x.append(tag("season", season))
    x.append(tag("episode", number))
    x.append(tag("plot", info.get("plot") or info.get("overview")))
    duration = info.get("duration")
    if isinstance(duration, (int, float)) and duration > 0:
        x.append(tag("runtime", int(duration // 60)))
    x.append(tag("aired", (info.get("aired") or info.get("premiered") or "")[:10]))
    value, votes = rating_of(info)
    if value:
        x.append(f'  <ratings><rating name="default" max="10" default="true"><value>{value}</value><votes>{votes}</votes></rating></ratings>\n')
    x.append(f'  <uniqueid type="trakt" default="true">{trakt_id}</uniqueid>\n')
    if collected_at:
        x.append(tag("dateadded", str(collected_at).replace("T", " ")[:19]))
    x.append(tag("playcount", 1 if watched else 0))
    x.append(art_block(art, episode=True))
    x.append("</episodedetails>\n")
    return "".join(x)




# ----------------------------------------------------------------------------- small state files
def read_json(path, default):
    try:
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
        return data if isinstance(data, type(default)) else default
    except Exception:  # noqa: BLE001
        return default


def write_json(path, data):
    """Write to a temporary file first, then swap: a crash never leaves half a file."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = f"{path}.{os.getpid()}.tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(data, fh)
    os.replace(tmp, path)


class Busy:
    """One writer at a time (a full run, a quick add / remove from the skin) - also across Kodi's Python processes."""

    def __init__(self, wait=0):
        self.wait, self.held = wait, False

    def __enter__(self):
        os.makedirs(DATA, exist_ok=True)
        mon = xbmc.Monitor()
        end = time.time() + self.wait
        while True:
            try:
                fd = os.open(LOCK, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
                os.write(fd, str(time.time()).encode())
                os.close(fd)
                self.held = True
                return self
            except FileExistsError:
                try:
                    if time.time() - os.path.getmtime(LOCK) > 2 * 3600:      # left behind by a crash
                        os.remove(LOCK)
                        continue
                except OSError:
                    continue
            if time.time() >= end or mon.waitForAbort(1):
                return self

    def __exit__(self, *exc):
        if self.held:
            try:
                os.remove(LOCK)
            except OSError:
                pass
        return False


# ----------------------------------------------------------------------------- Trakt's own watched list (paged)
WATCHED_FILE = os.path.join(DATA, "trakt_watched.json")
WATCHED_TTL = 3600
PAGE_CAP = 120                 # pages per kind; a page is 250 films / 100 series


def trakt_watched(force=False):
    """(film trakt ids, {(show trakt id, season, episode)}) that Trakt itself says are watched, or None when Trakt cannot be
    reached. Trakt gives only 100 items without page / limit since 2026, so ask page by page until an empty page: Seren's own
    copy can be cut off at 100, and then everything after that looked unwatched."""
    try:
        with open(WATCHED_FILE, encoding="utf-8") as fh:
            saved = json.load(fh)
        if not force and time.time() - saved.get("time", 0) < WATCHED_TTL:
            return set(saved["movies"]), {tuple(x) for x in saved["episodes"]}
    except (OSError, ValueError, KeyError):
        saved = None
    try:
        import quick
        trakt = quick.Trakt()
        if not trakt.token:
            return None
        mon = xbmc.Monitor()
        movies, episodes = set(), set()
        for page in range(1, PAGE_CAP + 1):
            data = trakt.call(f"sync/watched/movies?page={page}&limit=250")
            if not isinstance(data, list) or not data:
                break
            for item in data:
                tid = ((item.get("movie") or {}).get("ids") or {}).get("trakt")
                if tid:
                    movies.add(int(tid))
            if mon.waitForAbort(0.3):
                return None
        for page in range(1, PAGE_CAP + 1):
            data = trakt.call(f"sync/watched/shows?page={page}&limit=100")
            if not isinstance(data, list) or not data:
                break
            for item in data:
                sid = ((item.get("show") or {}).get("ids") or {}).get("trakt")
                for season in item.get("seasons") or []:
                    for ep in season.get("episodes") or []:
                        if sid and season.get("number") is not None and ep.get("number") is not None:
                            episodes.add((int(sid), int(season["number"]), int(ep["number"])))
            if mon.waitForAbort(0.3):
                return None
        log(f"trakt watched: {len(movies)} films, {len(episodes)} episodes")
        write_json(WATCHED_FILE, {"time": time.time(), "movies": sorted(movies), "episodes": sorted(episodes)})
        return movies, episodes
    except Exception as error:  # noqa: BLE001 - offline / not logged in: Seren's own marks are used as before
        log(f"trakt watched: {type(error).__name__}")
        return None


# ----------------------------------------------------------------------------- new episodes from your Trakt calendar
NEW_EP_FILE = os.path.join(DATA, "new_episodes.json")
def new_episodes(show_ids):
    """Episodes of series in your library that were on TV in the last two weeks (your Trakt calendar), also when they
    are not in your Trakt collection yet: Seren only knows collected episodes, so new ones never came in.
    [(show trakt id, season, number, episode trakt id, info)]. Switch off: Skin.SetBool(lucent.lib.newep.off)."""
    if xbmc.getCondVisibility("Skin.HasSetting(lucent.lib.newep.off)") or not show_ids:
        return []
    try:
        import quick
        trakt = quick.Trakt()
        if not trakt.token:
            return []
        start = time.strftime("%Y-%m-%d", time.gmtime(time.time() - 13 * 86400))
        data = trakt.call(f"calendars/my/shows/{start}/14?extended=full")
    except Exception as error:  # noqa: BLE001 - offline: only what Seren has, as before
        log(f"new episodes: {type(error).__name__}")
        return []
    cutoff = time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime(time.time() - NEW_EPISODE_HOURS * 3600))
    out = []
    for item in data if isinstance(data, list) else []:
        aired = (item.get("first_aired") or "")[:19]
        sid = ((item.get("show") or {}).get("ids") or {}).get("trakt")
        ep = item.get("episode") or {}
        tid = (ep.get("ids") or {}).get("trakt")
        if not aired or aired > cutoff or sid not in show_ids or not tid or not ep.get("season") or ep.get("number") is None:
            continue
        info = {"title": ep.get("title"), "plot": ep.get("overview"), "aired": aired[:10],
                "duration": (ep.get("runtime") or 0) * 60, "rating": ep.get("rating"), "votes": ep.get("votes")}
        out.append((int(sid), int(ep["season"]), int(ep["number"]), int(tid), info))
    return out


def season_ids(trakt_show_id):
    """{season number: season trakt id} - Seren's play link carries the season's id."""
    try:
        import quick
        return {s.get("number"): (s.get("ids") or {}).get("trakt") for s in quick.Trakt().call(f"shows/{trakt_show_id}/seasons") or []}
    except Exception:  # noqa: BLE001
        return {}


def new_episodes_missing():
    """For the service: is there a new episode on your calendar whose file is not there yet? Then a run is due."""
    fmap = read_json(FOLDERS, {}) or {}
    shows = {}
    for key, folder in fmap.items():
        if str(key).startswith("show:"):
            try:
                shows[int(str(key).split(":", 1)[1])] = folder
            except ValueError:
                pass
    for sid, season, number, _tid, _info in new_episodes(set(shows)):
        folder = shows.get(sid)
        name = f"{folder} - S{season:02d}E{number:02d}.strm"
        if folder and not os.path.exists(os.path.join(TV_OUT, folder, f"Season {season:02d}", name)):
            log(f"new episode on the calendar: {folder} S{season:02d}E{number:02d}")
            return True
    return False


# ----------------------------------------------------------------------------- Seren's database
def _connect():
    if not os.path.exists(SEREN_DB):
        raise RuntimeError("seren-db")
    con = sqlite3.connect(f"file:{SEREN_DB}?mode=ro", uri=True, timeout=30)
    con.execute("BEGIN")                 # one snapshot: Seren may write while we read
    return con


def _details(info, meta, trakt_id):
    """Seren's own details, else the raw Trakt data it saved when the title came in (always there)."""
    info = _load(info)
    if not (isinstance(info, dict) and info.get("title")):
        raw = _load(meta)
        raw = raw.get("info") if isinstance(raw, dict) else None
        info = dict(raw) if isinstance(raw, dict) else {}
        info["_raw"] = True
    if not info.get("title"):
        info["title"] = info.get("originaltitle") or info.get("tvshowtitle") or f"Trakt {trakt_id}"
    return info


def read_collection(con):
    """[{trakt, tmdb, imdb, info, args, watched, collected_at, raw}] of the collected films."""
    out = []
    for trakt_id, tmdb_id, imdb_id, info, args, watched, collected_at, meta in con.execute(
            "SELECT m.trakt_id, m.tmdb_id, m.imdb_id, m.info, m.args, m.watched, m.collected_at, t.value "
            "FROM movies m LEFT JOIN movies_meta t ON t.id = m.trakt_id AND t.type = 'trakt' "
            "WHERE m.collected = 1 ORDER BY m.trakt_id"):
        if not args:
            continue
        details = _details(info, meta, trakt_id)
        out.append({"trakt": trakt_id, "tmdb": tmdb_id, "imdb": imdb_id, "info": details, "args": args,
                    "watched": watched, "collected_at": collected_at, "raw": details.pop("_raw", False)})
    return out


def movie_art_cast(con, trakt_id):
    """Only for a film without a TMDB id (its .nfo carries everything itself)."""
    row = con.execute('SELECT art, "cast" FROM movies WHERE trakt_id = ?', (trakt_id,)).fetchone()
    art, cast = (_load(row[0]), _load(row[1])) if row else ({}, [])
    return (art if isinstance(art, dict) else {}), (cast if isinstance(cast, list) else [])


def read_shows(con):
    """{show trakt id: {...show..., episodes: [(trakt, season, number, args, watched, collected_at)], fresh: {(season, number)}}}.
    Episodes come in EPISODE_WAIT_HOURS after they were on TV (before that a source often has no link yet)."""
    eps = {}
    base = ("SELECT trakt_id, trakt_show_id, season, number, args, watched, collected_at FROM episodes "
            "WHERE collected = 1 AND season > 0{} ORDER BY trakt_show_id, season, number")
    wait = (f" AND (air_date IS NULL OR air_date = '' OR "
            f"Datetime(air_date) <= Datetime('now', '-{EPISODE_WAIT_HOURS} hours'))")   # Seren keeps air_date in UTC, like 'now'
    fresh = {}
    try:
        rows = con.execute(base.format(wait)).fetchall()
        for show_id, season, number in con.execute(     # on TV less than a day ago: not added yet ...
                "SELECT trakt_show_id, season, number FROM episodes WHERE collected = 1 AND season > 0 AND air_date > '' "
                f"AND Datetime(air_date) > Datetime('now', '-{EPISODE_WAIT_HOURS} hours')"):
            fresh.setdefault(show_id, set()).add((season, number))   # ... but kept when it is already there
    except sqlite3.OperationalError:                # an old Seren without air_date: everything, like before
        rows = con.execute(base.format("")).fetchall()
    for trakt_id, show_id, season, number, args, watched, collected_at in rows:
        if args:
            eps.setdefault(show_id, []).append((trakt_id, season, number, args, watched, collected_at))
    shows, ids = {}, sorted(eps)
    for i in range(0, len(ids), 500):
        chunk = ids[i:i + 500]
        for sid, tmdb_id, tvdb_id, imdb_id, info, meta in con.execute(
                "SELECT s.trakt_id, s.tmdb_id, s.tvdb_id, s.imdb_id, s.info, t.value FROM shows s "
                f"LEFT JOIN shows_meta t ON t.id = s.trakt_id AND t.type = 'trakt' WHERE s.trakt_id IN ({','.join('?' * len(chunk))})",
                chunk):
            details = _details(info, meta, sid)
            shows[sid] = {"trakt_id": sid, "tmdb_id": tmdb_id, "tvdb_id": tvdb_id, "imdb_id": imdb_id, "info": details,
                          "raw": details.pop("_raw", False), "episodes": eps[sid], "art": {}, "cast": [], "season_art": {},
                          "fresh": fresh.get(sid, set())}
    missing = len(ids) - len(shows)
    if missing:
        log(f"read shows: {missing} series with collected episodes but no series record in Seren")
    return shows


def show_extras(con, show):
    """Only for a series without a TMDB id: artwork, cast, season posters and episode details for its own .nfo files."""
    row = con.execute('SELECT art, "cast" FROM shows WHERE trakt_id = ?', (show["trakt_id"],)).fetchone()
    if row:
        art, cast = _load(row[0]), _load(row[1])
        show["art"] = art if isinstance(art, dict) else {}
        show["cast"] = cast if isinstance(cast, list) else []
    for season, sart in con.execute("SELECT season, art FROM seasons WHERE trakt_show_id = ?", (show["trakt_id"],)):
        loaded = _load(sart)
        if isinstance(loaded, dict):
            show["season_art"][season] = loaded
    details = {}
    for trakt_id, info, art in con.execute("SELECT trakt_id, info, art FROM episodes WHERE trakt_show_id = ? AND collected = 1",
                                           (show["trakt_id"],)):
        einfo, eart = _load(info), _load(art)
        details[trakt_id] = (einfo if isinstance(einfo, dict) else {}, eart if isinstance(eart, dict) else {})
    return details


# ----------------------------------------------------------------------------- folder names that stay
def plan_folders(kind, items):
    """{key: folder}. A title keeps the folder it got before; new ones get 'Title (year)' (with [id] when taken).
    Names are compared without case: Android storage does not tell 'Up' from 'UP'."""
    fmap = read_json(FOLDERS, {})
    taken, out = {}, {}
    for key, title, year, trakt in items:                       # first the ones that already have a folder
        old = fmap.get(key)
        if old and old.casefold() not in taken:
            taken[old.casefold()] = key
            out[key] = old
    for key, title, year, trakt in items:
        if key in out:
            continue
        base = safe_name(f"{title} ({year})" if year else title)
        folder = base if base.casefold() not in taken else safe_name(f"{base} [{trakt}]")
        taken[folder.casefold()] = key
        out[key] = folder
    fmap.update(out)                                             # entries of quick adds not in Seren yet stay
    return out, fmap


def keep_pending(state, prefix, have, wanted, value):
    """Titles added at once (quick.py) stay until Seren has them; marks Seren has caught up with are dropped."""
    import quick
    fresh = quick.load_state()                                   # merge: a quick add may have happened meanwhile
    for part in ("pending", "removed"):
        for k, v in fresh[part].items():
            state[part].setdefault(k, v)
    for k in list(state["pending"]):
        if k.startswith(prefix):
            if k in have:
                state["pending"].pop(k)
            else:
                wanted.setdefault(state["pending"][k]["folder"], value)
    for k in list(state["removed"]):
        if k.startswith(prefix) and k not in have:
            state["removed"].pop(k)
    quick.save_state(state)


# ----------------------------------------------------------------------------- removing, carefully
def remove_gone(kind, base_dir, wanted, seren_count, started, manual):
    """Remove folders of titles that left the collection - only when it is safe. Returns (removed, held)."""
    existing = [d for d in os.listdir(base_dir) if os.path.isdir(os.path.join(base_dir, d))]
    gone = [d for d in existing if d not in wanted]
    missing = read_json(MISSING, {})
    now = time.time()
    for k in [k for k in missing if k.startswith(f"{kind}/") and k.split("/", 1)[1] not in gone]:
        missing.pop(k)                                           # came back
    removed, held = 0, 0
    if not gone:
        write_json(MISSING, missing)
        return 0, 0
    too_many = seren_count == 0 or len(gone) > max(SHRINK_MIN, SHRINK * len(existing))
    if too_many:
        word = ("films" if kind == "movies" else "series")
        log(f"{kind}: Seren reports {seren_count}, {len(gone)} of {len(existing)} would go - nothing removed")
        sure = manual and seren_count and xbmcgui.Dialog().yesno(
            "Lucent Bibliotheek" if NL else "Lucent Library",
            (f"Volgens Seren staan {len(gone)} {word} niet meer in je collectie. Uit de Kodi-bibliotheek halen?\n"
             "Kies Nee als Seren nog bezig is met laden." if NL else
             f"Seren says {len(gone)} {word} are no longer in your collection. Remove them from the Kodi library?\n"
             "Choose No if Seren is still loading."))
        if not sure:
            write_json(MISSING, missing)
            return 0, len(gone)
    for d in gone:
        path = os.path.join(base_dir, d)
        try:
            if os.path.getmtime(path) > started:
                continue                                         # made by a quick add during this run
        except OSError:
            continue
        key = f"{kind}/{d}"
        first = missing.setdefault(key, now)
        if too_many or now - first >= SAFE_HOURS * 3600:        # too_many here = the user said yes
            shutil.rmtree(path, ignore_errors=True)
            missing.pop(key, None)
            removed += 1
        else:
            held += 1
    write_json(MISSING, missing)
    return removed, held


# ----------------------------------------------------------------------------- films
def export(con, started, manual):
    import quick
    rows = read_collection(con)
    tw = trakt_watched()
    if tw:                                           # Seren's mark OR Trakt's own full list
        for r in rows:
            r["watched"] = 1 if (r["watched"] or int(r["trakt"]) in tw[0]) else 0
    os.makedirs(OUT, exist_ok=True)
    write_if_changed(os.path.join(OUT, MARK), "Lucent Bibliotheek - map wordt door de add-on beheerd\n")
    state = quick.load_state()
    have = {quick.key("movie", r["trakt"]) for r in rows}
    rows = [r for r in rows if quick.key("movie", r["trakt"]) not in state["removed"]]
    folders, fmap = plan_folders("movie", [(quick.key("movie", r["trakt"]), r["info"].get("title"), r["info"].get("year"), r["trakt"])
                                           for r in rows])
    wanted, marks, scores, written, failed = {}, {}, {}, 0, 0
    for r in rows:
        folder = folders[quick.key("movie", r["trakt"])]
        wanted[folder] = True
        marks[folder] = bool(r["watched"])
        scores[folder] = seren_ratings(r["info"])
        try:
            directory = os.path.join(OUT, folder)
            os.makedirs(directory, exist_ok=True)
            changed = write_if_changed(os.path.join(directory, f"{folder}.strm"), strm_url(r["args"]) + "\n")
            art, cast = ({}, []) if (USE_SCRAPER and r["tmdb"]) else movie_art_cast(con, r["trakt"])
            nfo = nfo_of(r["trakt"], r["tmdb"], r["imdb"], r["info"], art, cast, r["watched"], r["collected_at"])
            changed = write_if_changed(os.path.join(directory, f"{folder}.nfo"), nfo) or changed
            written += 1 if changed else 0
        except Exception as error:  # noqa: BLE001 - one title never stops the run
            failed += 1
            log(f"film {r['trakt']} '{folder}': {error}")
    keep_pending(state, "movie:", have, wanted, True)
    write_json(FOLDERS, fmap)
    removed, held = remove_gone("movies", OUT, wanted, len(rows), started, manual)
    raw = sum(1 for r in rows if r["raw"])
    log(f"export: {len(rows)} films ({raw} not yet shown in Seren, named from Trakt), {written} changed, "
        f"{failed} failed, {removed} removed, {held} waiting before removal")
    return {"total": len(rows), "written": written, "removed": removed, "marks": marks, "scores": scores}


# ----------------------------------------------------------------------------- series
def export_shows(con, started, manual):
    import quick
    shows = read_shows(con)
    added, seasons = 0, {}
    kept = read_json(NEW_EP_FILE, []) or []           # earlier new episodes stay (the calendar only looks back 2 weeks)
    fresh = new_episodes(set(shows))
    seen = {(e[0], e[1], e[2]) for e in fresh}
    merged = fresh + [tuple(e) for e in kept if isinstance(e, list) and len(e) == 5 and (e[0], e[1], e[2]) not in seen and e[0] in shows]
    if fresh or kept:
        write_json(NEW_EP_FILE, [list(e) for e in merged][-2000:])
    for sid, season, number, tid, info in merged:
        show = shows[sid]
        if any(int(se) == season and int(nu) == number for _t, se, nu, _a, _w, _c in show["episodes"]):
            continue                                   # Seren has it already (collected)
        if sid not in seasons:
            seasons[sid] = season_ids(sid)
        import quick
        args = quick.seren_args({"mediatype": "episode", "trakt_id": tid, "trakt_show_id": sid,
                                 "trakt_season_id": seasons[sid].get(season)})
        show["episodes"].append((tid, season, number, args, 0, None))
        show.setdefault("new_info", {})[tid] = info
        added += 1
    if added:
        log(f"new episodes from the calendar: {added}")
    tw = trakt_watched()
    if tw:
        for sid, show in shows.items():
            show["episodes"] = [(t, se, nu, a, 1 if (w or (int(sid), int(se), int(nu)) in tw[1]) else 0, c)
                                for t, se, nu, a, w, c in show["episodes"]]
    os.makedirs(TV_OUT, exist_ok=True)
    write_if_changed(os.path.join(TV_OUT, MARK), "Lucent Bibliotheek - map wordt door de add-on beheerd\n")
    state = quick.load_state()
    have = {quick.key("show", sid) for sid in shows}
    shows = {sid: sh for sid, sh in shows.items() if quick.key("show", sid) not in state["removed"]}
    folders, fmap = plan_folders("show", [(quick.key("show", sid), sh["info"].get("title"), sh["info"].get("year"), sid)
                                          for sid, sh in shows.items()])
    wanted, marks, scores, changed, episodes, failed = {}, {}, {}, 0, 0, 0
    for sid, show in shows.items():
        folder = folders[quick.key("show", sid)]
        wanted[folder] = set()
        scores[folder] = seren_ratings(show["info"])
        try:
            root = os.path.join(TV_OUT, folder)
            os.makedirs(root, exist_ok=True)
            own_nfo = not (USE_SCRAPER and show.get("tmdb_id"))
            details = show_extras(con, show) if own_nfo else {}
            changed += 1 if write_if_changed(os.path.join(root, "tvshow.nfo"), tvshow_nfo(show)) else 0
            skipped = quick.skip_codes(state, sid)                       # taken out by you (Options > Remove)
            for trakt_id, season, number, args, watched, collected_at in show["episodes"]:
                if skipped and (f"S{int(season):02d}" in skipped or f"S{int(season):02d}E{int(number):02d}" in skipped):
                    continue
                sdir = f"Season {int(season):02d}"
                os.makedirs(os.path.join(root, sdir), exist_ok=True)
                name = f"{folder} - S{int(season):02d}E{int(number):02d}"
                wanted[folder].add(os.path.join(sdir, name))
                marks[f"{folder}/{name}"] = bool(watched)
                a = write_if_changed(os.path.join(root, sdir, f"{name}.strm"), strm_url(args) + "\n")
                nfo_path = os.path.join(root, sdir, f"{name}.nfo")
                b = False
                if own_nfo:
                    info, art = details.get(trakt_id) or ((show.get("new_info") or {}).get(trakt_id, {}), {})
                    b = write_if_changed(nfo_path, episode_nfo(show, trakt_id, season, number, info, art, watched, collected_at))
                elif os.path.exists(nfo_path):
                    os.remove(nfo_path)
                changed += 1 if (a or b) else 0
                episodes += 1
            for season, number in show["fresh"]:      # less than a day on TV: leave it if it is already there
                if skipped and (f"S{int(season):02d}" in skipped or f"S{int(season):02d}E{int(number):02d}" in skipped):
                    continue
                name = os.path.join(f"Season {int(season):02d}", f"{folder} - S{int(season):02d}E{int(number):02d}")
                if os.path.exists(os.path.join(root, name + ".strm")):
                    wanted[folder].add(name)
        except Exception as error:  # noqa: BLE001
            failed += 1
            log(f"series {sid} '{folder}': {error}")
    keep_pending(state, "show:", have, wanted, None)
    write_json(FOLDERS, fmap)
    removed, held = remove_gone("tvshows", TV_OUT, wanted, len(shows), started, manual)
    for folder, names in wanted.items():                         # episodes that left a series we keep
        if names is None:
            continue
        path = os.path.join(TV_OUT, folder)
        for sdir in (os.listdir(path) if os.path.isdir(path) else []):
            sp = os.path.join(path, sdir)
            if not os.path.isdir(sp):
                continue
            for n in os.listdir(sp):
                if os.path.join(sdir, os.path.splitext(n)[0]) not in names and os.path.getmtime(os.path.join(sp, n)) < started:
                    try:
                        os.remove(os.path.join(sp, n))
                    except OSError:
                        pass
            if not os.listdir(sp):
                shutil.rmtree(sp, ignore_errors=True)
    raw = sum(1 for s in shows.values() if s["raw"])
    log(f"export shows: {len(shows)} series ({raw} named from Trakt), {episodes} episodes, {changed} changed, "
        f"{failed} failed, {removed} removed, {held} waiting before removal")
    return {"total": len(shows), "episodes": episodes, "written": changed, "removed": removed, "marks": marks, "scores": scores}


# ----------------------------------------------------------------------------- Kodi
def rpc(method, params=None):
    request = {"jsonrpc": "2.0", "id": 1, "method": method, "params": params or {}}
    answer = json.loads(xbmc.executeJSONRPC(json.dumps(request)))
    if "error" in answer:
        log(f"rpc {method}: {answer['error']}")
    return answer.get("result", {})


BATCH = 50          # Kodi handles a list of JSON-RPC calls in one go: much faster than one call per title
SHOW_FROM = 10      # show the progress bar at the top from this many changes


def rpc_batch(calls, what):
    """Run [(method, params)] in batches, with Kodi's small progress bar at the top: '<what>: 150 of 1240'.
    Returns the number of calls that went through."""
    if not calls:
        return 0
    total, done, failed = len(calls), 0, 0
    bar = None
    if total >= SHOW_FROM:
        bar = xbmcgui.DialogProgressBG()
        bar.create("Lucent Bibliotheek" if NL else "Lucent Library", f"{what}: 0 {'van' if NL else 'of'} {total}")
    monitor = xbmc.Monitor()
    home = xbmcgui.Window(10000)
    try:
        for start in range(0, total, BATCH):
            if monitor.abortRequested():
                break
            chunk = calls[start:start + BATCH]
            request = [{"jsonrpc": "2.0", "id": n, "method": m, "params": p} for n, (m, p) in enumerate(chunk)]
            try:
                answers = json.loads(xbmc.executeJSONRPC(json.dumps(request)))
                answers = answers if isinstance(answers, list) else [answers]
                failed += sum(1 for a in answers if isinstance(a, dict) and "error" in a)
            except Exception as error:  # noqa: BLE001
                log(f"batch {what}: {error}")
                failed += len(chunk)
            done += len(chunk)
            home.setProperty("lucent.lib.syncing", str(time.time()))   # service.py: these changes come from Trakt, do not send back
            if bar:
                bar.update(int(done * 100 / total), message=f"{what}: {done} {'van' if NL else 'of'} {total}")
    finally:
        if bar:
            bar.close()
    if failed:
        log(f"batch {what}: {failed} of {total} failed")
    return done - failed


def source_path(special):
    """The video source exactly as Kodi has it (special:// or the real path) - scanning another spelling does nothing."""
    real = xbmcvfs.translatePath(special).rstrip("/\\")
    for s in rpc("Files.GetSources", {"media": "video"}).get("sources", []):
        f = s.get("file", "")
        if f.rstrip("/") == special.rstrip("/") or xbmcvfs.translatePath(f).rstrip("/\\") == real:
            return f if f.endswith(("/", "\\")) else f + "/"
    return ""


def source_added(special=OUT_SPECIAL):
    return bool(source_path(special))


def _scanning():
    return xbmc.getCondVisibility("Library.IsScanningVideo")


def wait_idle(limit=1800):
    mon = xbmc.Monitor()
    end = time.time() + limit
    while _scanning() and time.time() < end:
        if mon.waitForAbort(2):
            return False
    return not _scanning()


def scan(path):
    """UpdateLibrary stops a scan that is already running instead of starting one: wait until Kodi is idle first."""
    if not path or not wait_idle():
        log(f"scan skipped (Kodi busy): {path}")
        return False
    xbmc.executebuiltin(f'UpdateLibrary(video,"{path}",false)')
    mon = xbmc.Monitor()
    for _ in range(30):                                          # wait until it really started
        if _scanning() or mon.waitForAbort(1):
            break
    return wait_idle(3600)


def clean(path):
    """Clean only our own folder (never the user's other sources)."""
    if path and wait_idle():
        xbmc.executebuiltin(f'CleanLibrary(video,false,"{path}")')
        xbmc.Monitor().waitForAbort(2)
        wait_idle(600)


def sync_watched(movie_marks, episode_marks):
    """Trakt -> Kodi: what Seren knows as watched gets the mark in the Kodi library too (with a progress bar at the
    top when there are many - the first run can be thousands of episodes)."""
    calls = []
    try:
        for movie in rpc("VideoLibrary.GetMovies", {"properties": ["file", "playcount"]}).get("movies", []):
            f = movie.get("file", "")
            if ADDON_ID in f and f.endswith(".strm") and not movie.get("playcount"):
                folder = os.path.basename(os.path.dirname(f.replace("\\", "/")))
                if movie_marks.get(folder):
                    calls.append(("VideoLibrary.SetMovieDetails", {"movieid": movie["movieid"], "playcount": 1}))
        for ep in rpc("VideoLibrary.GetEpisodes", {"properties": ["file", "playcount"]}).get("episodes", []):
            f = ep.get("file", "").replace("\\", "/")
            if ADDON_ID in f and f.endswith(".strm") and not ep.get("playcount"):
                parts = f.split("/")
                if len(parts) >= 3 and episode_marks.get(f"{parts[-3]}/{parts[-1][:-5]}"):
                    calls.append(("VideoLibrary.SetEpisodeDetails", {"episodeid": ep["episodeid"], "playcount": 1}))
    except Exception as error:  # noqa: BLE001
        log(f"watched sync: {error}")
    done = rpc_batch(calls, "Gezien-vinkjes" if NL else "Watched marks")
    if done:
        log(f"watched sync: {done} marks set")
    return done


def _rating_changes(current, wanted):
    """Only the scores that are new or different; Kodi keeps the others (and which one is the default)."""
    out = {}
    for name, (value, votes) in wanted.items():
        have = current.get(name) or {}
        if round(float(have.get("rating") or 0), 1) != value or int(have.get("votes") or 0) != votes:
            out[name] = {"rating": value, "votes": votes, "default": False}
    return out


def sync_ratings(movie_scores, show_scores):
    """Seren -> Kodi: the IMDb, Trakt and TMDB scores Seren shows, also on the films and series in the Kodi library
    (Kodi's TMDB scrapers only keep their own score unless you switch the others on). Returns the number updated."""
    calls = []
    try:
        for movie in rpc("VideoLibrary.GetMovies", {"properties": ["file", "ratings"]}).get("movies", []):
            f = movie.get("file", "").replace("\\", "/")
            if ADDON_ID in f and f.endswith(".strm"):
                changes = _rating_changes(movie.get("ratings") or {}, movie_scores.get(os.path.basename(os.path.dirname(f)), {}))
                if changes:
                    calls.append(("VideoLibrary.SetMovieDetails", {"movieid": movie["movieid"], "ratings": changes}))
        for show in rpc("VideoLibrary.GetTVShows", {"properties": ["file", "ratings"]}).get("tvshows", []):
            f = show.get("file", "").replace("\\", "/").rstrip("/")
            if ADDON_ID in f:
                changes = _rating_changes(show.get("ratings") or {}, show_scores.get(os.path.basename(f), {}))
                if changes:
                    calls.append(("VideoLibrary.SetTVShowDetails", {"tvshowid": show["tvshowid"], "ratings": changes}))
    except Exception as error:  # noqa: BLE001
        log(f"scores: {error}")
    done = rpc_batch(calls, "Scores")
    if done:
        log(f"scores: {done} titles got Seren's IMDb / Trakt / TMDB scores")
    return done


# ----------------------------------------------------------------------------- the run
def run(manual=True):
    with Busy(wait=60 if manual else 0) as lock:
        if not lock.held:
            log("run skipped: another run or a quick add is busy")
            if manual:
                say("Even geduld, Lucent Bibliotheek is al bezig" if NL else "Please wait, Lucent Library is already busy")
            return
        _run(manual)


def _run(manual):
    title = "Lucent Bibliotheek" if NL else "Lucent Library"
    started = time.time()
    try:
        con = _connect()
    except RuntimeError:
        if manual:
            xbmcgui.Dialog().ok(title, "Seren heeft nog geen gegevens. Open eerst in Seren je Trakt-collectie en probeer het dan opnieuw."
                                if NL else "Seren has no data yet. First open your Trakt collection in Seren, then try again.")
        return
    films = shows = None
    try:
        try:
            films = export(con, started, manual)
        except Exception as error:  # noqa: BLE001
            log(f"export films failed: {error}")
        try:
            shows = export_shows(con, started, manual)
        except Exception as error:  # noqa: BLE001
            log(f"export series failed: {error}")
    finally:
        con.close()
    if films is None and shows is None:
        if manual:
            say(("Mislukt, zie de Kodi-log" if NL else "Failed, see the Kodi log"))
        return
    films = films or {"total": 0, "written": 0, "removed": 0, "marks": {}, "scores": {}}
    shows = shows or {"total": 0, "episodes": 0, "written": 0, "removed": 0, "marks": {}, "scores": {}}
    os.makedirs(os.path.dirname(ENABLED), exist_ok=True)
    open(ENABLED, "w").close()
    paths = {"movies": source_path(OUT_SPECIAL), "tv": source_path(TV_SPECIAL)}
    missing = [sp for sp, key in ((OUT_SPECIAL, "movies"), (TV_SPECIAL, "tv")) if not paths[key]]
    if missing and manual:
        lines = "\n".join(missing)
        xbmcgui.Dialog().ok(title, (f"Klaar: {films['total']} films en {shows['total']} series ({shows['episodes']} afleveringen) klaargezet.\n"
                                    f"Voeg eenmalig deze map(pen) als bron toe in Kodi:\n{lines}" if NL else
                                    f"Done: {films['total']} movies and {shows['total']} series ({shows['episodes']} episodes) prepared.\n"
                                    f"Add this folder(s) as a source in Kodi (once):\n{lines}"))
    scanned = False
    for key in ("movies", "tv"):
        if paths[key]:
            scanned = scan(paths[key]) or scanned
    if scanned:
        home = xbmcgui.Window(10000)
        home.setProperty("lucent.lib.syncing", str(time.time()))   # service.py: these marks come from Trakt, do not send back
        sync_watched(films["marks"], shows["marks"])
        home.setProperty("lucent.lib.syncing", str(time.time()))
        if films["removed"]:
            clean(paths["movies"])
        if shows["removed"]:
            clean(paths["tv"])
    if paths["movies"] or paths["tv"]:
        sync_ratings(films["scores"], shows["scores"])          # also for titles that were already in the library
    changed = films["written"] or films["removed"] or shows["written"] or shows["removed"]
    if manual or changed:
        say(f"{films['total']} films, {shows['total']} series" if NL else f"{films['total']} movies, {shows['total']} series")
    try:
        import tools
        tools.mark_run()
    except Exception as error:  # noqa: BLE001
        log(f"last run: {error}")
