# -*- coding: utf-8 -*-
"""Lucent widget cache.

The Lucent skin asks for its Home rows through this add-on:
    plugin://script.lucent.library/?action=widget&row=3&r=<reload token>&path=<the real path, e.g. a Seren list>

The plugin part only READS: it answers at once with the saved copy of that row (or an empty row the very first time)
and never calls the other add-on itself. Kodi asks all rows of a tab at the same time; when every one of them started
Seren, rows stayed empty, loaded slowly or Kodi hung. Fetching is done by the Lucent Library service (worker() below):
  - one row at a time, rows of the same add-on after each other, a short pause in between;
  - first the rows that have no copy yet (a few seconds after Kodi starts), refreshes only after half a minute, so
    Seren can first sync with Trakt; refreshes wait while a video plays;
  - 'Continue watching' / 'Next up' kind of rows are refreshed every 15 minutes and right after you watched
    something, other rows (trending, popular, lists) every 6 hours;
  - a fetch that hangs is given up after 45 seconds; a failed or empty answer never replaces a good copy and is
    tried again later (1, 5, 15 minutes);
  - when a row has new items, Window(home).Property(lucent.wr.<row>) changes, so Kodi reloads just that row.

Seren's own properties (trakt_id, trakt_show_id, ...) are not given by JSON-RPC, so they are read back from the
action_args in the Seren path of every item.
"""
import hashlib
import json
import os
import sys
import threading
import time
import urllib.parse

import xbmc
import xbmcaddon
import xbmcgui
import xbmcplugin
import xbmcvfs

ADDON_ID = "script.lucent.library"
DIR = xbmcvfs.translatePath(f"special://profile/addon_data/{ADDON_ID}/widgets/")
HOME = xbmcgui.Window(10000)
PROPS = ["title", "art", "plot", "plotoutline", "year", "genre", "rating", "votes", "playcount", "resume",
         "runtime", "season", "episode", "showtitle", "firstaired", "premiered", "mpaa", "uniqueid", "tagline",
         "studio", "country", "director", "writer", "originaltitle", "trailer", "dateadded", "lastplayed"]
BASIC = ["title", "art", "plot", "year", "genre", "rating", "playcount", "resume", "runtime", "season", "episode",
         "showtitle", "premiered", "uniqueid"]


def log(text):
    xbmc.log(f"[{ADDON_ID}] widgets: {text}", xbmc.LOGINFO)


def key_of(path):
    return hashlib.md5(path.encode("utf-8")).hexdigest()


def cache_file(key):
    return os.path.join(DIR, key + ".json")


def load(key):
    try:
        with open(cache_file(key), encoding="utf-8") as fh:
            return json.load(fh)
    except Exception:  # noqa: BLE001
        return None


def save(key, path, items):
    try:
        os.makedirs(DIR, exist_ok=True)
        tmp = f"{cache_file(key)}.{os.getpid()}.{threading.get_ident()}.tmp"   # never two writers on one file
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump({"v": 2, "path": path, "time": time.time(), "items": items}, fh)
        os.replace(tmp, cache_file(key))
    except Exception as error:  # noqa: BLE001
        log(f"save: {error}")


def rpc(method, params):
    answer = json.loads(xbmc.executeJSONRPC(json.dumps({"jsonrpc": "2.0", "id": 1, "method": method, "params": params})))
    if "error" in answer:
        raise RuntimeError(answer["error"].get("message", "error"))
    return answer.get("result") or {}


def fetch(path):
    """Items of the real path (a list of dicts as JSON-RPC gives them)."""
    for props in (PROPS, BASIC):
        try:
            result = rpc("Files.GetDirectory", {"directory": path, "media": "video", "properties": props})
            return result.get("files") or []
        except Exception as error:  # noqa: BLE001
            log(f"{path[:90]}: {error}")
    return []


def fetch_retry(path):
    items = fetch(path)
    if not items:
        xbmc.Monitor().waitForAbort(3)
        items = fetch(path)
    return enrich(items)


# ----------------------------------------------------------------------------- what JSON-RPC leaves out, from Seren's own database
SEREN_DB = xbmcvfs.translatePath("special://profile/addon_data/plugin.video.seren/traktSync.db")
TABLES = {"movie": "movies", "tvshow": "shows", "season": "seasons", "episode": "episodes"}
EXTRA_PROPS = {"rottentomatoes_rating": "RottenTomatoes_Rating", "metacritic_rating": "Metacritic_Rating",
               "rottentomatoes_image": "RottenTomatoes_Image"}


def action_args(url):
    try:
        query = urllib.parse.parse_qs(urllib.parse.urlsplit(url).query)
        raw = (query.get("action_args") or [""])[0]
        for _ in range(2):
            if raw[:3].lower() == "%7b":
                raw = urllib.parse.unquote(raw)
        return json.loads(raw) if raw.startswith("{") else {}
    except Exception:  # noqa: BLE001
        return {}


def enrich(items):
    """Ratings per site (IMDb, Trakt, TMDB), the show status and a few Seren properties, read from Seren's database
    (Seren keeps the details of every title it showed). Items Seren does not know stay as they are."""
    if not items or not os.path.exists(SEREN_DB):
        return items
    import pickle
    import sqlite3
    try:
        con = sqlite3.connect(f"file:{SEREN_DB}?mode=ro", uri=True, timeout=10)
    except Exception as error:  # noqa: BLE001
        log(f"seren db: {error}")
        return items
    try:
        for entry in items:
            args = action_args(entry.get("file") or "")
            table = TABLES.get(args.get("mediatype") or entry.get("type"))
            trakt_id = args.get("trakt_id")
            if not table or not trakt_id:
                continue
            try:
                row = con.execute(f"SELECT info FROM {table} WHERE trakt_id = ?", (int(trakt_id),)).fetchone()
            except Exception:  # noqa: BLE001 - another Seren version
                continue
            if not row or row[0] is None:
                continue
            info = row[0]
            if isinstance(info, (bytes, bytearray, memoryview)):
                try:
                    info = pickle.loads(bytes(info))
                except Exception:  # noqa: BLE001
                    continue
            if not isinstance(info, dict):
                continue
            ratings = {}
            for key, value in info.items():
                if key.startswith("rating.") and isinstance(value, dict) and value.get("rating"):
                    ratings[key.split(".", 1)[1]] = {"rating": value.get("rating"), "votes": value.get("votes") or 0}
            if ratings:
                entry["ratings"] = ratings
            status = info.get("status") or info.get("tvshow.status")
            if status:
                entry["status"] = status
            props = {name: str(info[key]) for key, name in EXTRA_PROPS.items() if info.get(key) not in (None, "")}
            if props:
                entry["props"] = props
    finally:
        con.close()
    return items


# ----------------------------------------------------------------------------- items back into list items
def seren_ids(url):
    """{'trakt_id': '123', ...} from the action_args of a Seren path."""
    try:
        query = urllib.parse.parse_qs(urllib.parse.urlsplit(url).query)
        raw = (query.get("action_args") or [""])[0]
        for _ in range(2):
            if raw.startswith("%7B") or raw.startswith("%7b"):
                raw = urllib.parse.unquote(raw)
        data = json.loads(raw) if raw.startswith("{") else {}
        return {k: str(v) for k, v in data.items() if k.endswith("_id") and v not in (None, "")}
    except Exception:  # noqa: BLE001
        return {}


def listitem(entry):
    li = xbmcgui.ListItem(entry.get("label") or entry.get("title") or "", offscreen=True)
    art = {k: v for k, v in (entry.get("art") or {}).items() if v}
    if art:
        li.setArt(art)
    tag = li.getVideoInfoTag()
    kind = entry.get("type") if entry.get("type") in ("movie", "tvshow", "season", "episode") else "video"
    tag.setMediaType(kind)
    dbid = entry.get("id")                         # a title from the Kodi library: without its id the info page
    if kind != "video" and isinstance(dbid, int) and dbid > 0:     # cannot find it (OK > info did nothing)
        try:
            tag.setDbId(dbid)
        except Exception:  # noqa: BLE001
            pass
    simple = (("title", tag.setTitle), ("plot", tag.setPlot), ("showtitle", tag.setTvShowTitle),
              ("mpaa", tag.setMpaa), ("tagline", tag.setTagLine), ("originaltitle", tag.setOriginalTitle),
              ("trailer", tag.setTrailer), ("premiered", tag.setPremiered), ("firstaired", tag.setFirstAired))
    for name, setter in simple:
        if entry.get(name):
            try:
                setter(str(entry[name]))
            except Exception:  # noqa: BLE001
                pass
    for name, setter in (("year", tag.setYear), ("season", tag.setSeason), ("episode", tag.setEpisode),
                         ("playcount", tag.setPlaycount), ("runtime", tag.setDuration)):
        value = entry.get(name)
        if isinstance(value, int) and value >= 0 and not (name in ("season", "episode") and value < 0):
            try:
                setter(value)
            except Exception:  # noqa: BLE001
                pass
    for name, setter in (("genre", tag.setGenres), ("studio", tag.setStudios), ("country", tag.setCountries),
                         ("director", tag.setDirectors), ("writer", tag.setWriters)):
        if entry.get(name):
            try:
                setter(list(entry[name]))
            except Exception:  # noqa: BLE001
                pass
    ratings = entry.get("ratings") or {}
    if ratings:
        try:
            default = next((k for k, v in ratings.items() if v.get("default")), "")
            tag.setRatings({k: (float(v.get("rating") or 0), int(v.get("votes") or 0)) for k, v in ratings.items()}, default)
        except Exception:  # noqa: BLE001
            pass
    elif entry.get("rating"):
        try:
            tag.setRating(float(entry["rating"]), int(entry.get("votes") or 0))
        except Exception:  # noqa: BLE001
            pass
    if entry.get("status"):
        try:
            tag.setTvShowStatus(str(entry["status"]))
        except Exception:  # noqa: BLE001
            pass
    for k, v in (entry.get("props") or {}).items():
        li.setProperty(k, v)
    if entry.get("uniqueid"):
        try:
            tag.setUniqueIDs({k: str(v) for k, v in entry["uniqueid"].items() if v})
        except Exception:  # noqa: BLE001
            pass
    resume = entry.get("resume") or {}
    if resume.get("position"):
        try:
            tag.setResumePoint(float(resume["position"]), float(resume.get("total") or 0))
        except Exception:  # noqa: BLE001
            pass
    for k, v in seren_ids(entry.get("file") or "").items():
        li.setProperty(k, v)
    folder = entry.get("filetype") == "directory"
    li.setProperty("IsPlayable", "false" if folder or entry.get("action") else "true")     # an action item opens a page, it does not play
    return entry.get("file") or "", li, folder


def answer(handle, items):
    kinds = [e.get("type") for e in items]
    content = "movies" if kinds.count("movie") > len(kinds) / 2 else "episodes" if kinds.count("episode") > len(kinds) / 2 \
        else "tvshows" if kinds.count("tvshow") > len(kinds) / 2 else "videos"
    xbmcplugin.setContent(handle, content)
    xbmcplugin.addDirectoryItems(handle, [listitem(e) for e in items], len(items))
    xbmcplugin.addSortMethod(handle, xbmcplugin.SORT_METHOD_NONE)
    xbmcplugin.endOfDirectory(handle, succeeded=True, cacheToDisc=False)


# ----------------------------------------------------------------------------- what the service should fetch
REG = os.path.join(DIR, "reg")                # one small file per row path: its path, rows and fetch state
WANT = os.path.join(DIR, "want")              # an empty file per row the skin asked for that needs fetching
TTL_FAST = 15 * 60                            # 'continue watching' kind of rows
TTL_SLOW = 6 * 3600                           # trending, popular, lists
FAST_WORDS = ("next", "progress", "ondeck", "on_deck", "deck", "continue", "resume", "recent", "watching", "unfinished")
FETCH_TIMEOUT = 45
MISS_DELAY = 5                                # after Kodi starts: rows without a copy
REFRESH_DELAY = 30                            # after Kodi starts: refreshes of saved rows
GAP = 1.5                                     # pause between two fetches
BACKOFF = (60, 300, 900)


def ttl_of(path):
    low = path.lower()
    return TTL_FAST if any(word in low for word in FAST_WORDS) else TTL_SLOW


def read_json(path, default=None):
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except Exception:  # noqa: BLE001
        return default


def write_json(path, data):
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        tmp = f"{path}.{os.getpid()}.{threading.get_ident()}.tmp"
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(data, fh)
        os.replace(tmp, path)
    except Exception as error:  # noqa: BLE001
        log(f"write {os.path.basename(path)}: {error}")


def register(key, path, row):
    """Remember this row path (and on which row number it shows), at most once every 10 minutes per path."""
    file = os.path.join(REG, key + ".json")
    reg = read_json(file, {}) or {}
    rows = reg.get("rows") or []
    if reg.get("path") == path and row in rows and time.time() - reg.get("seen", 0) < 600:
        return
    if row not in rows:
        rows = (rows + [row])[-4:]
    reg.update({"path": path, "rows": rows, "seen": time.time()})
    write_json(file, reg)


def want(key):
    try:
        os.makedirs(WANT, exist_ok=True)
        with open(os.path.join(WANT, key), "w") as fh:
            fh.write(str(time.time()))
    except OSError:
        pass


def start_refresh(key, row):                  # older callers: just ask the service
    want(key)


def refresh(key, row):                        # RunScript(script.lucent.library,widget_refresh,...) from older skins
    want(key)


def mark_all_stale():
    """A video stopped: the 'continue watching' kind of rows are fetched again (by the service, one at a time)."""
    for name in list_dir(REG):
        reg = read_json(os.path.join(REG, name), {}) or {}
        if reg.get("path") and ttl_of(reg["path"]) == TTL_FAST:
            want(name[:-5])


def list_dir(folder):
    try:
        return [n for n in os.listdir(folder) if not n.endswith(".tmp")]
    except OSError:
        return []


def show(handle, query):
    if query.lstrip("?").startswith("action=tmdbopen"):          # a click on one of Lucent's own TMDb rows
        import tmdbwidgets
        tmdbwidgets.open_title(query)
        return
    if query.lstrip("?").startswith("action=providers"):          # a row of streaming services
        import tmdbwidgets
        tmdbwidgets.provider_rows(handle)
        return
    if query.lstrip("?").startswith("action=provideropen"):       # a click on a service: its pop-up
        import tmdbwidgets
        tmdbwidgets.provider_open(query)
        return
    if query.lstrip("?").startswith("action=tmdbbrowse"):         # one list opened as a folder
        import tmdbwidgets
        tmdbwidgets.browse(handle, query)
        return
    if query.lstrip("?").startswith("action=traktlists"):        # the menu asks: which Trakt lists does this person have?
        import tmdbwidgets
        tmdbwidgets.trakt_lists_dir(handle)
        return
    if query.lstrip("?").startswith("action=tmdb"):
        import tmdbwidgets
        tmdbwidgets.show(handle, "plugin://script.lucent.library/" + query.lstrip("/"), "")
        return
    if query.lstrip("?").startswith("action=lib"):  # rows straight from Kodi's own library
        import libwidgets
        libwidgets.show(handle, query)
        return
    row = "0"
    path = ""
    q = query[1:] if query.startswith("?") else query
    if "path=" in q:
        head, path = q.split("path=", 1)
        for part in head.split("&"):
            if part.startswith("row="):
                row = part[4:]
    if path.lower().startswith(("plugin%3a", "special%3a", "videodb%3a")):
        path = urllib.parse.unquote(path)
    if not path:
        xbmcplugin.endOfDirectory(handle, succeeded=False, cacheToDisc=False)
        return
    if path.startswith(f"plugin://{ADDON_ID}/?action=tmdb"):
        import tmdbwidgets                           # Lucent's own TMDb rows: instant, from their own saved copy
        tmdbwidgets.show(handle, path, row)
        return
    if path.startswith(f"plugin://{ADDON_ID}/?action=providers"):
        import tmdbwidgets                           # the streaming services row (also when the skin wraps it)
        tmdbwidgets.provider_rows(handle)
        return
    if path.startswith(f"plugin://{ADDON_ID}/?action=lib"):
        import libwidgets                            # a library row: instant, no need to keep a copy
        libwidgets.show(handle, path.split("?", 1)[1])
        return
    key = key_of(path)
    register(key, path, row)
    cache = load(key)
    if cache and cache.get("items"):
        answer(handle, cache["items"])
        if cache.get("v") != 2 or time.time() - cache.get("time", 0) > ttl_of(path):
            want(key)
        return
    want(key)                                        # the service fetches it and then reloads this row
    answer(handle, [])


# ----------------------------------------------------------------------------- the fetching (runs in the service)
class Worker:
    def __init__(self, monitor, player):
        self.monitor = monitor
        self.player = player
        self.started = time.time()
        self.hung = None                             # a fetch that did not come back in time
        self.last_pre = 0.0

    def candidates(self):
        """[(priority, plugin id, path, key, reg)] of what may be fetched now, best first."""
        now = time.time()
        wanted = set(n for n in list_dir(WANT))
        out = []
        for name in list_dir(REG):
            key = name[:-5]
            reg = read_json(os.path.join(REG, name), {}) or {}
            path = reg.get("path")
            if not path or reg.get("retry", 0) > now:
                continue
            cache = load(key)
            have = bool(cache and cache.get("items"))
            age = now - (cache or {}).get("time", 0) if have else 1e12
            recent = now - reg.get("seen", 0) < 3 * 86400        # rows not shown for days are left alone
            if not have and (key in wanted or recent):
                prio = 0
            elif key in wanted and age > 60:
                prio = 1
            elif recent and age > ttl_of(path):
                prio = 2
            else:
                if key in wanted:
                    self.drop(key)
                continue
            if prio and now - self.started < REFRESH_DELAY:
                continue
            if prio and self.player.isPlayingVideo():
                continue                             # no fetching while you watch (except rows that are empty)
            addon = path.split("/")[2] if path.startswith("plugin://") else ""
            out.append((prio, addon, path, key, reg))
        out.sort(key=lambda c: (c[0], c[1], c[2]))
        return out

    def drop(self, key):
        try:
            os.remove(os.path.join(WANT, key))
        except OSError:
            pass

    def fetch_timed(self, path):
        box = {}

        def work():
            try:
                box["items"] = fetch_retry(path)
            except Exception as error:  # noqa: BLE001
                log(f"fetch: {error}")
                box["items"] = []
        thread = threading.Thread(target=work, daemon=True)
        thread.start()
        thread.join(FETCH_TIMEOUT)
        if thread.is_alive():
            self.hung = thread
            return None
        return box.get("items") or []

    def one(self):
        if self.hung is not None:
            if self.hung.is_alive():
                return False                         # never two fetches at the same time
            self.hung = None
        if time.time() - self.started < MISS_DELAY:
            return False
        todo = self.candidates()
        if not todo:
            return False
        _prio, _addon, path, key, reg = todo[0]
        self.drop(key)
        before = load(key) or {}
        started = time.time()
        items = self.fetch_timed(path)
        file = os.path.join(REG, key + ".json")
        reg = read_json(file, reg) or reg
        if items:
            save(key, path, items)
            reg.update({"fail": 0, "retry": 0})
            write_json(file, reg)
            if items != before.get("items"):
                for row in reg.get("rows") or []:
                    HOME.setProperty(f"lucent.wr.{row}", str(time.time()))
            log(f"{len(items)} items in {time.time() - started:.1f}s: {path[:80]}")
        else:
            fail = int(reg.get("fail", 0))
            reg.update({"fail": fail + 1, "retry": time.time() + BACKOFF[min(fail, len(BACKOFF) - 1)]})
            write_json(file, reg)
            if before.get("items"):
                save(key, path, before["items"])     # keep the good copy (and do not ask again at once)
            log(f"{'no answer in time' if items is None else 'nothing'} for {path[:80]}; kept the saved row, again later")
        return True

    def prefetch(self):
        """Every row of every tab (not only the tab on screen) is put on the list, so a tab you open later is already
        filled instead of being fetched row by row while you wait."""
        if time.time() - self.last_pre < 1200 or time.time() - self.started < 15:
            return
        self.last_pre = time.time()
        seen, added = set(), 0
        for tab in range(0, 13):                              # 0 = the start tab's own copy (nuvio.home.*)
            for w in range(1, 11):
                base = f"nuvio.home.w{w}" if tab == 0 else f"nuvio.tab{tab}.w{w}"
                path = xbmc.getInfoLabel(f"Skin.String({base}.path)")
                if not path.startswith("plugin://") or path in seen:
                    continue
                seen.add(path)
                if path.startswith(f"plugin://{ADDON_ID}/?action=tmdb"):
                    import tmdbwidgets
                    name = tmdbwidgets.list_name(path)
                    if tmdbwidgets.known(name):
                        tmdbwidgets.register(name, "", path)
                    continue
                if path.startswith(f"plugin://{ADDON_ID}/?action=lib"):
                    continue
                key = key_of(path)
                if not read_json(os.path.join(REG, key + ".json"), None):
                    register(key, path, str(w))
                    added += 1
        if added:
            log(f"prefetch: {added} rows of other tabs put on the list")

    def run(self):
        while not self.monitor.abortRequested():
            try:
                self.prefetch()
                worked = self.one()
                if not worked and time.time() - self.started >= MISS_DELAY:
                    import tmdbwidgets                   # Lucent's own TMDb rows, when nothing else is waiting
                    worked = tmdbwidgets.tick(self.player.isPlayingVideo())
            except Exception as error:  # noqa: BLE001 - never stop
                log(f"worker: {error}")
                worked = False
            if self.monitor.waitForAbort(GAP if worked else 1.0):
                break


if __name__ == "__main__":
    show(int(sys.argv[1]), sys.argv[2] if len(sys.argv) > 2 else "")
