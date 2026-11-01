"""Lucent Bibliotheek: add or remove one film / series at once - on Trakt and in the Kodi library together.

    RunScript(script.lucent.library,add,movie|show,<trakt id>[,trakt])
    RunScript(script.lucent.library,remove,movie|show,<trakt id>[,trakt])

With the extra word 'trakt' the title is also put in (or taken out of) your Trakt collection; without it only the
Kodi files are written (the skin already told Trakt).

Before, a title you collected only showed up in Kodi after Seren had synced with Trakt and the next library run.
Now the .strm / .nfo files are written straight away from Trakt's own data, and Kodi scans just that one folder.
The next full run (lib.export) knows these titles ('pending') and keeps them until Seren has them too; a removed
title is kept out until Seren knows it is gone.
"""
import re
import json
import os
import shutil
import time
import urllib.error
import urllib.parse
import urllib.request

import xbmc
import xbmcaddon
import xbmcgui
import xbmcvfs

import lib

SEREN_ID = "plugin.video.seren"
TRAKT = "https://api.trakt.tv/"
STATE = os.path.join(os.path.dirname(lib.ENABLED), "quick.json")
KEEP = 7 * 86400            # a pending / removed mark is forgotten after a week (Seren has long synced by then)
NL = lib.NL


def log(text):
    lib.log(f"quick: {text}")


# ----------------------------------------------------------------------------- state shared with lib.export
def load_state():
    try:
        with open(STATE, encoding="utf-8") as fh:
            state = json.load(fh)
    except Exception:  # noqa: BLE001
        state = {}
    now = time.time()
    for part in ("pending", "removed"):
        state[part] = {k: v for k, v in (state.get(part) or {}).items() if now - v.get("t", 0) < KEEP}
    return state


def save_state(state):
    lib.write_json(STATE, state)


def key(kind, trakt_id):
    try:
        trakt_id = int(trakt_id)
    except (TypeError, ValueError):
        trakt_id = str(trakt_id)                   # never let one odd row stop the whole library run
    return f"{'movie' if kind == 'movie' else 'show'}:{trakt_id}"


# ----------------------------------------------------------------------------- Trakt (Seren's login)
def seren_client_id(seren):
    """The Trakt app key Seren itself uses. Its login only works with that same key, and Seren versions differ:
    taken from Seren's setting, else read from Seren's own code (its built-in default)."""
    key = seren.getSetting("trakt.clientid").strip()
    if key:
        return key
    try:
        path = xbmcvfs.translatePath("special://home/addons/plugin.video.seren/resources/lib/indexers/trakt.py")
        with open(path, encoding="utf-8") as fh:
            found = re.search(r'"trakt\.clientid",\s*"([0-9a-f]{64})"', fh.read())
        if found:
            return found.group(1)
    except Exception:  # noqa: BLE001
        pass
    return "0c9a30819e4af6ffaf3b954cbeae9b54499088513863c03c02911de00ac2de79"


def seren_refresh_login(old_token, wait=20):
    """Trakt logins only last a day now. Seren renews its own login when it talks to Trakt (a sync), so let it do
    that and wait for the new one - renewing it here would leave Seren with a login that no longer works."""
    xbmc.executebuiltin(f"RunPlugin(plugin://{SEREN_ID}/?action=syncTraktActivities)")
    monitor = xbmc.Monitor()
    for _ in range(int(wait * 2)):
        if monitor.waitForAbort(0.5):
            break
        token = xbmcaddon.Addon(SEREN_ID).getSetting("trakt.auth")
        if token and token != old_token:
            log("Trakt login renewed by Seren")
            return token
    return old_token


class Trakt:
    def __init__(self):
        seren = xbmcaddon.Addon(SEREN_ID)
        self.client_id = seren_client_id(seren)
        self.token = seren.getSetting("trakt.auth")
        try:
            expires = float(seren.getSetting("trakt.expires") or 0)
        except ValueError:
            expires = 0
        if self.token and expires and expires < time.time() + 120:
            self.token = seren_refresh_login(self.token)

    def call(self, path, data=None, again=True):
        try:
            return self._call(path, data)
        except urllib.error.HTTPError as error:
            if error.code != 401 or not again or not self.token:
                raise
            new = seren_refresh_login(self.token)
            if new == self.token:
                raise
            self.token = new
            return self._call(path, data)

    def _call(self, path, data=None):
        headers = {"Content-Type": "application/json", "trakt-api-version": "2", "trakt-api-key": self.client_id,
                   "User-Agent": "script.lucent.library (Kodi)"}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        body = json.dumps(data).encode("utf-8") if data is not None else None
        request = urllib.request.Request(TRAKT + path, data=body, headers=headers, method="POST" if body else "GET")
        with urllib.request.urlopen(request, timeout=20) as response:
            raw = response.read()
            return json.loads(raw.decode("utf-8")) if raw else {}


def seren_args(args):
    """Exactly the way Seren stores action_args, so the next full run writes the same .strm (no change)."""
    return urllib.parse.quote(json.dumps(args, sort_keys=True))


# ----------------------------------------------------------------------------- writing the files
def movie_files(trakt, trakt_id):
    m = trakt.call(f"movies/{trakt_id}?extended=full")
    ids = m.get("ids") or {}
    title, year = m.get("title") or "", m.get("year")
    folder = choose_folder("movie", trakt_id, title, year, lib.OUT)
    directory = os.path.join(lib.OUT, folder)
    os.makedirs(directory, exist_ok=True)
    lib.write_if_changed(os.path.join(directory, f"{folder}.strm"),
                         lib.strm_url(seren_args({"mediatype": "movie", "trakt_id": int(trakt_id)})) + "\n")
    info = {"title": title, "year": year, "plot": m.get("overview"), "genre": m.get("genres") or [],
            "mpaa": m.get("certification"), "premiered": m.get("released"), "tagline": m.get("tagline"),
            "trailer": m.get("trailer"), "rating": m.get("rating"), "votes": m.get("votes"),
            "duration": (m.get("runtime") or 0) * 60}
    lib.write_if_changed(os.path.join(directory, f"{folder}.nfo"),
                         lib.nfo_of(int(trakt_id), ids.get("tmdb"), ids.get("imdb"), info, {}, [], False, None))
    return folder, title


def show_files(trakt, trakt_id):
    s = trakt.call(f"shows/{trakt_id}?extended=full")
    ids = s.get("ids") or {}
    title, year = s.get("title") or "", s.get("year")
    folder = choose_folder("show", trakt_id, title, year, lib.TV_OUT)
    root = os.path.join(lib.TV_OUT, folder)
    os.makedirs(root, exist_ok=True)
    show = {"trakt_id": int(trakt_id), "tmdb_id": ids.get("tmdb"), "tvdb_id": ids.get("tvdb"), "imdb_id": ids.get("imdb"),
            "info": {"title": title, "year": year, "plot": s.get("overview"), "genre": s.get("genres") or [],
                     "mpaa": s.get("certification"), "premiered": s.get("first_aired"), "status": s.get("status"),
                     "rating": s.get("rating"), "votes": s.get("votes")},
            "art": {}, "cast": [], "episodes": [], "season_art": {}}
    lib.write_if_changed(os.path.join(root, "tvshow.nfo"), lib.tvshow_nfo(show))
    now = time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime(time.time() - lib.EPISODE_WAIT_HOURS * 3600))
    count = 0
    for season in trakt.call(f"shows/{trakt_id}/seasons?extended=full,episodes") or []:
        number = season.get("number") or 0
        if number <= 0:
            continue
        season_id = (season.get("ids") or {}).get("trakt")
        for ep in season.get("episodes") or []:
            aired = ep.get("first_aired") or ""
            if not aired or aired[:19] > now:          # only what was on TV at least a day ago (then there is a link)
                continue
            sdir = os.path.join(root, f"Season {int(number):02d}")
            os.makedirs(sdir, exist_ok=True)
            name = f"{folder} - S{int(number):02d}E{int(ep.get('number') or 0):02d}"
            args = {"mediatype": "episode", "trakt_id": (ep.get("ids") or {}).get("trakt"),
                    "trakt_show_id": int(trakt_id), "trakt_season_id": season_id}
            lib.write_if_changed(os.path.join(sdir, f"{name}.strm"), lib.strm_url(seren_args(args)) + "\n")
            if not (lib.USE_SCRAPER and show.get("tmdb_id")):
                info = {"title": ep.get("title"), "plot": ep.get("overview"), "aired": aired[:10],
                        "duration": (ep.get("runtime") or 0) * 60, "rating": ep.get("rating"), "votes": ep.get("votes")}
                lib.write_if_changed(os.path.join(sdir, f"{name}.nfo"),
                                     lib.episode_nfo(show, args["trakt_id"], number, ep.get("number"), info, {}, False, None))
            count += 1
    return folder, title, count


def choose_folder(kind, trakt_id, title, year, base):
    """The folder this title had before (shared with the full run), else a new free name - remembered."""
    fmap = lib.read_json(lib.FOLDERS, {})
    k = key(kind, trakt_id)
    if fmap.get(k):
        return fmap[k]
    taken = {v.casefold() for v in fmap.values()}
    try:
        taken |= {d.casefold() for d in os.listdir(base)}
    except OSError:
        pass
    folder = lib.safe_name(f"{title} ({year})" if year else title)
    if folder.casefold() in taken:
        folder = lib.safe_name(f"{folder} [{trakt_id}]")
    fmap[k] = folder
    lib.write_json(lib.FOLDERS, fmap)
    return folder


def strm_ids(path):
    """The ids inside one of our .strm files (Seren's action_args, URL-encoded twice)."""
    try:
        with open(path, encoding="utf-8") as fh:
            query = fh.read().strip().split("?", 1)[-1]
        args = dict(urllib.parse.parse_qsl(query)).get("action_args", "")
        return json.loads(urllib.parse.unquote(args))
    except Exception:  # noqa: BLE001
        return {}


def owns(directory, kind, trakt_id):
    """Is this folder the one of this title? (exact id, so 12 never matches 123)"""
    want = int(trakt_id)
    try:
        for r, _d, files in os.walk(directory):
            for f in files:
                if f.endswith(".strm"):
                    ids = strm_ids(os.path.join(r, f))
                    return int(ids.get("trakt_id" if kind == "movie" else "trakt_show_id") or 0) == want
    except OSError:
        pass
    return False


def scan(kind, folder):
    """Let Kodi read just this one folder, on the path as the source was added - after any running scan."""
    base = lib.source_path(lib.OUT_SPECIAL if kind == "movie" else lib.TV_SPECIAL)
    if base:
        lib.scan(base + folder + "/")
    return bool(base)


# ----------------------------------------------------------------------------- remove
def library_items(kind, trakt_id, folder):
    """Kodi library ids of this title (by its folder)."""
    out = []
    method, field, idname = ("VideoLibrary.GetMovies", "movies", "movieid") if kind == "movie" else \
        ("VideoLibrary.GetTVShows", "tvshows", "tvshowid")
    for item in lib.rpc(method, {"properties": ["file", "uniqueid"]}).get(field, []):
        f = item.get("file", "").replace("\\", "/")
        if lib.ADDON_ID not in f:
            continue                                     # never touch the user's own sources
        if (folder and f"/{folder}/" in f + "/") or str((item.get("uniqueid") or {}).get("trakt", "")) == str(trakt_id):
            out.append(item[idname])
    return out


def find_folder(kind, trakt_id, state):
    entry = state["pending"].get(key(kind, trakt_id))
    if entry:
        return entry["folder"]
    known = lib.read_json(lib.FOLDERS, {}).get(key(kind, trakt_id))
    base_dir = lib.OUT if kind == "movie" else lib.TV_OUT
    if known and os.path.isdir(os.path.join(base_dir, known)):
        return known
    base = lib.OUT if kind == "movie" else lib.TV_OUT
    try:
        for name in os.listdir(base):
            if os.path.isdir(os.path.join(base, name)) and owns(os.path.join(base, name), kind, trakt_id):
                return name
    except OSError:
        pass
    return ""


def remove_files(kind, trakt_id, state):
    folder = find_folder(kind, trakt_id, state)
    base = lib.OUT if kind == "movie" else lib.TV_OUT
    ids = library_items(kind, trakt_id, folder)
    if folder:
        shutil.rmtree(os.path.join(base, folder), ignore_errors=True)
    for item_id in ids:            # straight out of Kodi's library (no full clean-up needed)
        if kind == "movie":
            lib.rpc("VideoLibrary.RemoveMovie", {"movieid": item_id})
        else:
            lib.rpc("VideoLibrary.RemoveTVShow", {"tvshowid": item_id})
    return folder


# ----------------------------------------------------------------------------- entry
def skip_codes(state, show_trakt_id):
    """Episodes ('S01E02') and whole seasons ('S01') you took out of a series yourself: they stay out of the library."""
    return set((state.get("skip") or {}).get(str(show_trakt_id)) or [])


def skip(show_trakt_id, code):
    """Take one episode (S01E02) or a whole season (S01) of a Lucent series out of the Kodi library, for good:
    the files go, Kodi forgets them, and the next runs leave them out. Nothing changes on Trakt.
    Adding the series again (Library and lists) brings everything back."""
    code = code.upper()
    if not str(show_trakt_id).isdigit() or not re.match(r"^S\d{2}(E\d{2,4})?$", code):
        log(f"skip: bad input {show_trakt_id} {code}")
        return False
    with lib.Busy(wait=90) as lock:
        if not lock.held:
            lib.say("Lucent Bibliotheek is bezig, probeer het zo opnieuw" if NL else "Lucent Library is busy, try again in a moment", 4000)
            return False
        state = load_state()
        codes = (state.setdefault("skip", {})).setdefault(str(show_trakt_id), [])
        if code not in codes:
            codes.append(code)
        save_state(state)
        folder = find_folder("show", show_trakt_id, state)
        removed = 0
        if folder:
            root = os.path.join(lib.TV_OUT, folder)
            season_dir = os.path.join(root, f"Season {code[1:3]}")
            if len(code) == 3:
                shutil.rmtree(season_dir, ignore_errors=True)
            elif os.path.isdir(season_dir):
                for name in os.listdir(season_dir):
                    if f" - {code}." in name:
                        try:
                            os.remove(os.path.join(season_dir, name))
                        except OSError:
                            pass
            for show_id in library_items("show", show_trakt_id, folder):          # straight out of Kodi as well
                for ep in lib.rpc("VideoLibrary.GetEpisodes", {"tvshowid": show_id, "properties": ["season", "episode"]}).get("episodes", []):
                    ep_code = f"S{int(ep.get('season') or 0):02d}E{int(ep.get('episode') or 0):02d}"
                    if ep_code == code or (len(code) == 3 and ep_code.startswith(code)):
                        lib.rpc("VideoLibrary.RemoveEpisode", {"episodeid": ep["episodeid"]})
                        removed += 1
        log(f"skip {show_trakt_id} {code}: {removed} episode(s) out of Kodi")
        lib.say("Uit je bibliotheek gehaald" if NL else "Removed from your library", 3000)
        return True


def payload(kind, trakt_id):
    return {("movies" if kind == "movie" else "shows"): [{"ids": {"trakt": int(trakt_id)}}]}


def run(action, kind, trakt_id, tell_trakt=False):
    with lib.Busy(wait=90) as lock:
        if not lock.held:
            log(f"{action}: library busy, gave up")
            lib.say("Lucent Bibliotheek is bezig, probeer het zo opnieuw" if NL else "Lucent Library is busy, try again in a moment", 4000)
            return False
        return _run(action, kind, trakt_id, tell_trakt)


def _run(action, kind, trakt_id, tell_trakt=False):
    kind = "movie" if kind == "movie" else "show"
    if not str(trakt_id).isdigit():
        log(f"{action}: no trakt id")
        return False
    title_word = "Lucent Bibliotheek" if NL else "Lucent Library"
    try:
        trakt = Trakt()
    except Exception:  # noqa: BLE001 - Seren missing
        xbmcgui.Dialog().notification(title_word, "Seren?", xbmcgui.NOTIFICATION_WARNING, 4000)
        return False
    state = load_state()
    k = key(kind, trakt_id)
    try:
        if action == "add":
            if tell_trakt:
                trakt.call("sync/collection", payload(kind, trakt_id))
            if kind == "movie":
                folder, title = movie_files(trakt, trakt_id)
                extra = ""
            else:
                folder, title, count = show_files(trakt, trakt_id)
                extra = f" ({count} {'afleveringen' if NL else 'episodes'})"
            state["removed"].pop(k, None)
            if kind == "show":
                (state.get("skip") or {}).pop(str(trakt_id), None)        # added again: every episode comes back
            state["pending"][k] = {"folder": folder, "t": time.time()}
            save_state(state)
            if lib.source_added(lib.OUT_SPECIAL if kind == "movie" else lib.TV_SPECIAL):
                lib.say((f"{title} komt in je bibliotheek{extra}" if NL else f"{title} is going into your library{extra}"), 4000)
                scan(kind, folder)
            else:
                lib.say(("Klaar - voeg eenmalig de map toe als bron (Lucent Bibliotheek starten)" if NL
                         else "Done - add the folder as a source once (start Lucent Library)"), 6000)
            log(f"added {k} -> {folder}{extra}")
        else:
            if tell_trakt:
                trakt.call("sync/collection/remove", payload(kind, trakt_id))
            folder = remove_files(kind, trakt_id, state)
            state["pending"].pop(k, None)
            state["removed"][k] = {"folder": folder, "t": time.time()}
            save_state(state)
            lib.say("Uit je bibliotheek gehaald" if NL else "Removed from your library", 3000)
            log(f"removed {k} ({folder})")
    except urllib.error.HTTPError as error:
        log(f"{action} {k}: HTTP {error.code}")
        xbmcgui.Dialog().notification(title_word, f"Trakt: HTTP {error.code}", xbmcgui.NOTIFICATION_WARNING, 5000)
        return False
    except Exception as error:  # noqa: BLE001
        log(f"{action} {k}: {error}")
        xbmcgui.Dialog().notification(title_word, ("Mislukt: " if NL else "Failed: ") + str(error)[:60],
                                      xbmcgui.NOTIFICATION_WARNING, 5000)
        return False
    return True

