# -*- coding: utf-8 -*-
"""Nuvio Arc: helpers for the info page (DialogVideoInfo).

RunScript(special://skin/scripts/info.py,load)      fill the collection row and the studios
RunScript(special://skin/scripts/info.py,lists)     choose: Seren library (Trakt collection), watchlist, own Trakt lists
RunScript(special://skin/scripts/info.py,watched)   mark as watched / unwatched on Trakt

Trakt calls use the Trakt login of Seren (the same account, nothing new to set up).
Everything shown on the page goes through Window(home) properties named nuvio.info.*.
"""
import json
import sys
import urllib.error
import urllib.parse
import urllib.request

import xbmc
import xbmcaddon
import xbmcgui

HEADING = "Nuvio Arc"
SEREN_ID = "plugin.video.seren"
SEREN = "plugin://plugin.video.seren/"
TRAKT = "https://api.trakt.tv/"
TMDB = "https://api.themoviedb.org/3/"
TMDB_IMG = "https://image.tmdb.org/t/p/"
MAX_COLLECTION = 12
MAX_STUDIOS = 4
HOME = xbmcgui.Window(10000)

_NL = xbmc.getLanguage(xbmc.ISO_639_1) == "nl"
T = {
    "library": ("Seren library (Trakt collection)", "Seren-bibliotheek (Trakt-collectie)"),
    "watchlist": ("Trakt · Watchlist", "Trakt · Kijklijst"),
    "list": ("Trakt · {0}", "Trakt · {0}"),
    "pick": ("{0} – choose the lists for this title", "{0} – kies in welke lijsten deze titel staat"),
    "loading": ("Loading your Trakt lists…", "Je Trakt-lijsten laden…"),
    "saved": ("Saved", "Opgeslagen"),
    "nothing": ("Nothing changed", "Niets veranderd"),
    "no_seren": ("Seren is not installed.", "Seren is niet geïnstalleerd."),
    "no_login": ("You are not logged in to Trakt in Seren. Log in via Seren → Settings → Trakt.",
                 "Je bent in Seren niet ingelogd bij Trakt. Log in via Seren → Instellingen → Trakt."),
    "expired": ("Your Trakt login has expired. Open Seren once so it can renew it, then try again.",
                "Je Trakt-login is verlopen. Open Seren één keer zodat hij hem vernieuwt en probeer het dan opnieuw."),
    "failed": ("Trakt did not respond. Try again later.", "Trakt reageert niet. Probeer het later opnieuw."),
    "no_ids": ("This title has no Trakt or TMDB id.", "Deze titel heeft geen Trakt- of TMDB-nummer."),
    "watched": ("Marked as watched", "Gemarkeerd als bekeken"),
    "unwatched": ("Marked as not watched", "Gemarkeerd als niet bekeken"),
}


def tr(key, *args):
    text = T[key][1 if _NL else 0]
    return text.format(*args) if args else text


def info(label):
    return xbmc.getInfoLabel(f"ListItem.{label}")


def notify(text, icon=xbmcgui.NOTIFICATION_INFO):
    xbmcgui.Dialog().notification(HEADING, text, icon, 3000)


def log(text):
    xbmc.log(f"[skin.nuvioarc] info.py: {text}", xbmc.LOGINFO)


def http(url, data=None, headers=None, method=None):
    body = json.dumps(data).encode("utf-8") if data is not None else None
    headers = dict(headers or {})
    headers.setdefault("User-Agent", "skin.nuvioarc (Kodi)")
    request = urllib.request.Request(url, data=body, headers=headers, method=method)
    with urllib.request.urlopen(request, timeout=20) as response:
        raw = response.read()
        return json.loads(raw.decode("utf-8")) if raw else {}


# ----------------------------------------------------------------------------- the current item
class Item:
    def __init__(self):
        self.dbtype = info("DBType") or "movie"
        self.title = info("Title") or info("Label")
        self.trakt = info("Property(trakt_id)")
        self.tmdb = info("UniqueID(tmdb)") or info("Property(tmdb_id)")
        self.imdb = info("UniqueID(imdb)") or info("IMDBNumber") or info("Property(imdb_id)")
        self.watched = int(info("PlayCount") or 0) > 0
        if self.dbtype in ("season", "episode"):
            show_trakt = info("Property(trakt_show_id)")
            self.show_ids = {"trakt": int(show_trakt)} if show_trakt.isdigit() else {}
        self.key = self.trakt or self.tmdb or self.imdb or self.title

    def ids(self):
        ids = {}
        if self.trakt.isdigit():
            ids["trakt"] = int(self.trakt)
        if self.tmdb.isdigit():
            ids["tmdb"] = int(self.tmdb)
        if self.imdb.startswith("tt"):
            ids["imdb"] = self.imdb
        return ids

    @property
    def kind(self):
        """Trakt's word for this item: movie, show or episode."""
        return {"movie": "movie", "tvshow": "show", "episode": "episode", "season": "season"}.get(self.dbtype, "movie")

    def payload(self):
        return {f"{self.kind}s": [{"ids": self.ids()}]}

    def matches(self, entry):
        """Does a Trakt list entry ({'movie': {'ids': …}}) point to this item?"""
        ids = (entry.get(self.kind) or {}).get("ids", {})
        mine = self.ids()
        return any(ids.get(k) == v for k, v in mine.items())


# ----------------------------------------------------------------------------- Trakt (Seren's login)
class Trakt:
    def __init__(self):
        seren = xbmcaddon.Addon(SEREN_ID)
        self.client_id = seren.getSetting("trakt.clientid") or \
            "0c9a30819e4af6ffaf3b954cbeae9b54499088513863c03c02911de00ac2de79"
        self.token = seren.getSetting("trakt.auth")

    def headers(self):
        return {"Content-Type": "application/json", "trakt-api-version": "2",
                "trakt-api-key": self.client_id, "Authorization": f"Bearer {self.token}"}

    def get(self, path):
        return http(TRAKT + path, headers=self.headers())

    def post(self, path, data):
        return http(TRAKT + path, data=data, headers=self.headers(), method="POST")


def trakt_or_explain():
    if not xbmc.getCondVisibility(f"System.HasAddon({SEREN_ID})"):
        xbmcgui.Dialog().ok(HEADING, tr("no_seren"))
        return None
    trakt = Trakt()
    if not trakt.token:
        xbmcgui.Dialog().ok(HEADING, tr("no_login"))
        return None
    return trakt


def explain_error(error):
    log(f"Trakt error: {error}")
    if isinstance(error, urllib.error.HTTPError) and error.code in (401, 403):
        xbmcgui.Dialog().ok(HEADING, tr("expired"))
    else:
        notify(tr("failed"), xbmcgui.NOTIFICATION_WARNING)


def after_trakt_change():
    """Let Seren pick up the change and refresh what is on screen."""
    xbmc.executebuiltin(f"RunPlugin({SEREN}?action=syncTraktActivities)")
    xbmc.executebuiltin("Container.Refresh")


# ----------------------------------------------------------------------------- lists dialog
def choose_lists():
    item = Item()
    if not item.ids():
        xbmcgui.Dialog().ok(HEADING, tr("no_ids"))
        return
    if item.kind not in ("movie", "show"):
        return
    trakt = trakt_or_explain()
    if not trakt:
        return
    kind = item.kind + "s"
    progress = xbmcgui.DialogProgress()
    progress.create(HEADING, tr("loading"))
    try:
        rows = []  # (label, in_list, add_path, remove_path)
        collection = trakt.get(f"sync/collection/{kind}")
        rows.append((tr("library"), any(item.matches(e) for e in collection),
                     "sync/collection", "sync/collection/remove"))
        progress.update(30)
        watchlist = trakt.get(f"sync/watchlist/{kind}")
        rows.append((tr("watchlist"), any(item.matches(e) for e in watchlist),
                     "sync/watchlist", "sync/watchlist/remove"))
        progress.update(50)
        lists = trakt.get("users/me/lists") or []
        for n, lst in enumerate(lists[:25]):
            if progress.iscanceled():
                return
            slug = lst.get("ids", {}).get("trakt")
            entries = trakt.get(f"users/me/lists/{slug}/items/{item.kind}")
            rows.append((tr("list", lst.get("name", "")), any(item.matches(e) for e in entries),
                         f"users/me/lists/{slug}/items", f"users/me/lists/{slug}/items/remove"))
            progress.update(50 + int(50 * (n + 1) / max(1, len(lists[:25]))))
    except Exception as error:  # noqa: BLE001 - show a friendly message instead of a traceback
        progress.close()
        explain_error(error)
        return
    progress.close()

    items = []
    for label, _in_list, _a, _r in rows:
        li = xbmcgui.ListItem(label)
        li.setArt({"icon": "icons/trakt.png" if "Trakt" in label else "icons/library.png"})
        items.append(li)
    preselect = [n for n, row in enumerate(rows) if row[1]]
    chosen = xbmcgui.Dialog().multiselect(tr("pick", item.title), items, preselect=preselect)
    if chosen is None:
        return
    changes = 0
    try:
        for n, (_label, in_list, add_path, remove_path) in enumerate(rows):
            wanted = n in chosen
            if wanted != in_list:
                trakt.post(add_path if wanted else remove_path, item.payload())
                changes += 1
    except Exception as error:  # noqa: BLE001
        explain_error(error)
        return
    if changes:
        notify(tr("saved"))
        after_trakt_change()
    else:
        notify(tr("nothing"))


# ----------------------------------------------------------------------------- watched
def toggle_watched():
    item = Item()
    if not item.ids():
        xbmcgui.Dialog().ok(HEADING, tr("no_ids"))
        return
    trakt = trakt_or_explain()
    if not trakt:
        return
    state = HOME.getProperty("nuvio.info.watched")
    watched = (state == "1") if state in ("0", "1") else item.watched
    try:
        trakt.post("sync/history/remove" if watched else "sync/history", item.payload())
    except Exception as error:  # noqa: BLE001
        explain_error(error)
        return
    HOME.setProperty("nuvio.info.watched", "0" if watched else "1")
    notify(tr("unwatched") if watched else tr("watched"))
    after_trakt_change()


# ----------------------------------------------------------------------------- collection + studios
def tmdb_key():
    try:
        return xbmcaddon.Addon(SEREN_ID).getSetting("tmdb.apikey") or "9f3ca569aa46b6fb13931ec96ab8ae7e"
    except Exception:  # noqa: BLE001 - Seren not installed
        return "9f3ca569aa46b6fb13931ec96ab8ae7e"


def tmdb(path, **params):
    params["api_key"] = tmdb_key()
    params.setdefault("language", "nl-NL" if _NL else "en-US")
    return http(f"{TMDB}{path}?{urllib.parse.urlencode(params)}")


def clear_collection():
    for n in range(1, MAX_COLLECTION + 1):
        for p in ("title", "year", "art", "path", "watched"):
            HOME.clearProperty(f"nuvio.info.coll.{n}.{p}")
    HOME.setProperty("nuvio.info.coll.count", "0")


def load_collection(item):
    """Fill nuvio.info.coll.* with the films of the TMDB collection this film belongs to."""
    clear_collection()
    if item.dbtype != "movie":
        return
    collection_id = None
    try:
        if item.tmdb.isdigit():
            movie = tmdb(f"movie/{item.tmdb}")
            collection_id = (movie.get("belongs_to_collection") or {}).get("id")
        name = info("Set")
        if not collection_id and name:
            found = tmdb("search/collection", query=name).get("results") or []
            collection_id = found[0]["id"] if found else None
        if not collection_id:
            return
        collection = tmdb(f"collection/{collection_id}")
    except Exception as error:  # noqa: BLE001 - a missing row is fine
        log(f"collection: {error}")
        return
    if HOME.getProperty("nuvio.info.key") != item.key:
        return  # the user already opened another title
    parts = sorted(collection.get("parts") or [], key=lambda p: p.get("release_date") or "9999")
    parts = [p for p in parts if p.get("release_date")][:MAX_COLLECTION]
    if len(parts) < 2:
        return
    HOME.setProperty("nuvio.info.coll.name", collection.get("name", ""))
    for n, part in enumerate(parts, start=1):
        title = part.get("title", "")
        art = part.get("backdrop_path") or part.get("poster_path")
        HOME.setProperty(f"nuvio.info.coll.{n}.title", title)
        HOME.setProperty(f"nuvio.info.coll.{n}.year", (part.get("release_date") or "")[:4])
        HOME.setProperty(f"nuvio.info.coll.{n}.art", f"{TMDB_IMG}w780{art}" if art else "")
        query = urllib.parse.quote(title)
        HOME.setProperty(f"nuvio.info.coll.{n}.path", f"{SEREN}?action=moviesSearchResults&action_args={query}")
        HOME.setProperty(f"nuvio.info.coll.{n}.current", "1" if str(part.get("id")) == item.tmdb else "")
    HOME.setProperty("nuvio.info.coll.count", str(len(parts)))


VIDEO_TYPES = ["Trailer", "Teaser", "Clip", "Featurette", "Behind the Scenes"]
MAX_VIDEOS = 12


def load_videos(item):
    """Fill nuvio.info.vid.* with the YouTube trailers TMDB knows for this title."""
    for n in range(1, MAX_VIDEOS + 1):
        for p in ("title", "sub", "thumb", "path"):
            HOME.clearProperty(f"nuvio.info.vid.{n}.{p}")
    HOME.setProperty("nuvio.info.vid.count", "0")
    kind = {"movie": "movie", "tvshow": "tv"}.get(item.dbtype)
    if not kind or not item.tmdb.isdigit():
        return
    try:
        lang = "nl" if _NL else "en"
        videos = tmdb(f"{kind}/{item.tmdb}/videos", include_video_language=f"{lang},en,null").get("results") or []
    except Exception as error:  # noqa: BLE001
        log(f"videos: {error}")
        return
    if HOME.getProperty("nuvio.info.key") != item.key:
        return
    videos = [v for v in videos if v.get("site") == "YouTube" and v.get("key")]
    videos.sort(key=lambda v: (VIDEO_TYPES.index(v.get("type")) if v.get("type") in VIDEO_TYPES else 99,
                               not v.get("official"), v.get("published_at") or ""))
    videos = videos[:MAX_VIDEOS]
    for n, video in enumerate(videos, start=1):
        key = video["key"]
        HOME.setProperty(f"nuvio.info.vid.{n}.title", video.get("name", ""))
        HOME.setProperty(f"nuvio.info.vid.{n}.sub", f"{video.get('type', '')} · {(video.get('iso_639_1') or '').upper()}".strip(" ·"))
        HOME.setProperty(f"nuvio.info.vid.{n}.thumb", f"https://img.youtube.com/vi/{key}/hqdefault.jpg")
        HOME.setProperty(f"nuvio.info.vid.{n}.path", f"plugin://plugin.video.youtube/play/?video_id={key}")
    HOME.setProperty("nuvio.info.vid.count", str(len(videos)))


def load_studios():
    studios = [s.strip() for s in info("Studio").split("/") if s.strip()][:MAX_STUDIOS]
    for n in range(1, MAX_STUDIOS + 1):
        HOME.setProperty(f"nuvio.info.studio.{n}", studios[n - 1] if n <= len(studios) else "")


def load():
    item = Item()
    HOME.setProperty("nuvio.info.key", item.key)
    HOME.clearProperty("nuvio.info.watched")
    load_studios()
    load_videos(item)
    load_collection(item)


if __name__ == "__main__":
    action = sys.argv[1] if len(sys.argv) > 1 else "load"
    if action == "lists":
        choose_lists()
    elif action == "watched":
        toggle_watched()
    else:
        load()
