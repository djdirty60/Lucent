# -*- coding: utf-8 -*-
"""Lucent: helpers for the info page (DialogVideoInfo).

RunScript(special://skin/scripts/info.py,load)      fill the collection row and the studios
RunScript(special://skin/scripts/info.py,lists)     choose: Seren library (Trakt collection), watchlist, own Trakt lists
RunScript(special://skin/scripts/info.py,watched)   mark as watched / unwatched on Trakt

Trakt calls use the Trakt login of Seren (the same account, nothing new to set up).
Everything shown on the page goes through Window(home) properties named nuvio.info.*.
"""
import json
import sys
import threading
import urllib.error
import urllib.parse
import urllib.request

import xbmc
import xbmcaddon
import xbmcgui
import xbmcvfs

HEADING = "Lucent"
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
    "director": ("Director", "Regisseur"),
    "creator": ("Creator", "Bedenker"),
    "born": ("Born: {0}", "Geboren: {0}"),
    "died": ("Died: {0}", "Overleden: {0}"),
    "years": ("{0} years", "{0} jaar"),
    "no_tmdb": ("No TMDB key yet. Enter your own free key in Skin settings > Integrations (or in Seren).",
                "Nog geen TMDB-sleutel. Vul je eigen gratis sleutel in bij Skin-instellingen > Integraties (of in Seren)."),
    "failed_tmdb": ("TMDB did not respond. Try again later.", "TMDB reageert niet. Probeer het later opnieuw."),
}


def tr(key, *args):
    text = T[key][1 if _NL else 0]
    return text.format(*args) if args else text


def info(label):
    return xbmc.getInfoLabel(f"ListItem.{label}")


def notify(text, icon=xbmcgui.NOTIFICATION_INFO):
    xbmcgui.Dialog().notification(HEADING, text, icon, 3000)


def log(text):
    xbmc.log(f"[skin.lucent] info.py: {text}", xbmc.LOGINFO)


def http(url, data=None, headers=None, method=None):
    body = json.dumps(data).encode("utf-8") if data is not None else None
    headers = dict(headers or {})
    headers.setdefault("User-Agent", "skin.lucent (Kodi)")
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
        # Seren gives episodes and seasons the ids of their show (tmdb/imdb) plus trakt_show_id
        self.show_trakt = info("Property(trakt_show_id)") if self.dbtype in ("season", "episode") else ""
        self.key = self.trakt or self.tmdb or self.imdb or self.title

    @property
    def is_seren_episode(self):
        return self.dbtype in ("season", "episode") and self.show_trakt.isdigit()

    def as_show(self):
        """The show an episode or season belongs to (for lists, credits, similar titles and trailers)."""
        show = Item.__new__(Item)
        show.__dict__.update(self.__dict__)
        show.dbtype, show.trakt, show.show_trakt = "tvshow", self.show_trakt, ""
        show.title = info("TVShowTitle") or self.title
        return show

    def ids(self):
        ids = {}
        if self.dbtype in ("season", "episode"):
            # the tmdb/imdb ids here belong to the show, so only the episode's own trakt id is safe
            return {"trakt": int(self.trakt)} if self.trakt.isdigit() else {}
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
    if item.is_seren_episode:
        item = item.as_show()
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
TMDB_KEYFILES = (
    "special://profile/addon_data/skin.lucent/tmdb_key.txt",
    "special://profile/addon_data/script.lucent.library/tmdb_key.txt",
)


def _read_key(path):
    try:
        with xbmcvfs.File(path) as fh:
            return (fh.read() or "").strip()
    except Exception:  # noqa: BLE001
        return ""


def tmdb_key():
    """Your own free TMDB key: from Seren's setting, else the key you entered in Skin settings (or in the Lucent library add-on)."""
    try:
        key = (xbmcaddon.Addon(SEREN_ID).getSetting("tmdb.apikey") or "").strip()
    except Exception:  # noqa: BLE001 - Seren not installed
        key = ""
    for path in TMDB_KEYFILES:
        if key:
            break
        key = _read_key(path)
    return key


def set_tmdb_key():
    """Skin settings > Integrations: type your own TMDB key (empty = remove it)."""
    text = ("TMDB API-sleutel (gratis op themoviedb.org > Instellingen > API)" if _NL
            else "TMDB API key (free at themoviedb.org > Settings > API)")
    key = xbmcgui.Dialog().input(text, defaultt=_read_key(TMDB_KEYFILES[0]))
    if key is None or (not key.strip() and not _read_key(TMDB_KEYFILES[0])):
        return
    xbmcvfs.mkdirs("special://profile/addon_data/skin.lucent/")
    with xbmcvfs.File(TMDB_KEYFILES[0], "w") as fh:
        fh.write(key.strip())
    notify(tr("saved"))


def tmdb(path, **params):
    key = tmdb_key()
    if not key:
        raise RuntimeError("no TMDB key")
    params["api_key"] = key
    params.setdefault("language", "nl-NL" if _NL else "en-US")
    return http(f"{TMDB}{path}?{urllib.parse.urlencode(params)}")


def clear_collection():
    for n in range(1, MAX_COLLECTION + 1):
        for p in ("title", "year", "art", "path", "watched", "id"):
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
        HOME.setProperty(f"nuvio.info.coll.{n}.id", str(part.get("id", "")))
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
    if item.is_seren_episode:
        item = item.as_show()
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


STUDIO_PACK = "resource://resource.images.studios.white/"
STUDIO_CACHE = "special://profile/addon_data/skin.lucent/studio_logos.json"


def _studio_cache():
    try:
        with xbmcvfs.File(STUDIO_CACHE) as fh:
            return json.loads(fh.read() or "{}")
    except Exception:  # noqa: BLE001 - no file yet / damaged: start again
        return {}


def _save_studio_cache(cache):
    try:
        xbmcvfs.mkdirs("special://profile/addon_data/skin.lucent/")
        with xbmcvfs.File(STUDIO_CACHE, "w") as fh:
            fh.write(json.dumps(cache))
    except Exception:  # noqa: BLE001 - only a cache
        pass


def tmdb_company_logo(name, cache):
    """Logo of a production company from TMDB (remembered, also when there is none)."""
    if name in cache:
        return cache[name]
    logo = ""
    try:
        results = tmdb("search/company", query=name).get("results") or []
        with_logo = [r for r in results if r.get("logo_path")]
        exact = [r for r in with_logo if (r.get("name") or "").strip().lower() == name.lower()]
        pick = (exact or with_logo[:1] or [None])[0]
        logo = f"{TMDB_IMG}w300{pick['logo_path']}" if pick else ""
    except Exception:  # noqa: BLE001 - offline: try again next time (not remembered)
        return ""
    cache[name] = logo
    return logo


def load_studios():
    studios = [s.strip() for s in info("Studio").split("/") if s.strip()][:MAX_STUDIOS]
    for n in range(1, MAX_STUDIOS + 1):
        HOME.setProperty(f"nuvio.info.studio.{n}", studios[n - 1] if n <= len(studios) else "")
        HOME.clearProperty(f"nuvio.info.studio.{n}.logo")
    # a studio the logo pack does not have: take its logo from TMDB (shown on a light plate)
    cache = _studio_cache()
    before = len(cache)
    for n, name in enumerate(studios, 1):
        try:
            if xbmcvfs.exists(f"{STUDIO_PACK}{name}.png"):
                continue
        except Exception:  # noqa: BLE001
            pass
        logo = tmdb_company_logo(name, cache)
        if logo:
            HOME.setProperty(f"nuvio.info.studio.{n}.logo", logo)
    if len(cache) != before:
        _save_studio_cache(cache)


MAX_CAST = 24
PROFILE = TMDB_IMG + "w342"
MONTHS = {
    "nl": ["jan", "feb", "mrt", "apr", "mei", "jun", "jul", "aug", "sep", "okt", "nov", "dec"],
    "en": ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"],
}


def load_credits(item):
    """Fill nuvio.info.cast.* (directors first, then the cast) from TMDB, with person ids for the person page."""
    for n in range(1, MAX_CAST + 1):
        for p in ("name", "role", "thumb", "id"):
            HOME.clearProperty(f"nuvio.info.cast.{n}.{p}")
    HOME.setProperty("nuvio.info.cast.count", "0")
    if item.is_seren_episode:
        item = item.as_show()
    if not item.tmdb.isdigit() or item.dbtype not in ("movie", "tvshow"):
        return
    try:
        if item.dbtype == "movie":
            credits = tmdb(f"movie/{item.tmdb}/credits")
            people = [(p, tr("director")) for p in credits.get("crew") or [] if p.get("job") == "Director"][:2]
            people += [(p, p.get("character") or "") for p in (credits.get("cast") or [])]
        else:
            show = tmdb(f"tv/{item.tmdb}")
            credits = tmdb(f"tv/{item.tmdb}/aggregate_credits")
            people = [(p, tr("creator")) for p in show.get("created_by") or []][:2]
            people += [(p, ((p.get("roles") or [{}])[0].get("character") or "")) for p in (credits.get("cast") or [])]
    except Exception as error:  # noqa: BLE001 - Kodi's own cast list is shown instead
        log(f"credits: {error}")
        return
    if HOME.getProperty("nuvio.info.key") != item.key:
        return
    seen, n = set(), 0
    for person, role in people:
        if person.get("id") in seen or n >= MAX_CAST:
            continue
        seen.add(person.get("id"))
        n += 1
        HOME.setProperty(f"nuvio.info.cast.{n}.name", person.get("name", ""))
        HOME.setProperty(f"nuvio.info.cast.{n}.role", role)
        path = person.get("profile_path")
        HOME.setProperty(f"nuvio.info.cast.{n}.thumb", f"{PROFILE}{path}" if path else "DefaultActor.png")
        HOME.setProperty(f"nuvio.info.cast.{n}.id", str(person.get("id", "")))
    HOME.setProperty("nuvio.info.cast.count", str(n))


def nice_date(value):
    try:
        year, month, day = (int(x) for x in value.split("-"))
        return f"{day} {MONTHS['nl' if _NL else 'en'][month - 1]} {year}"
    except Exception:  # noqa: BLE001
        return value


def age(born, died=None):
    import datetime
    try:
        b = datetime.date.fromisoformat(born)
        d = datetime.date.fromisoformat(died) if died else datetime.date.today()
        return d.year - b.year - ((d.month, d.day) < (b.month, b.day))
    except Exception:  # noqa: BLE001
        return None


def set_works(works):
    """Fill the film cards of the person / studio page (the 40 most popular)."""
    works.sort(key=lambda e: e.get("popularity") or 0, reverse=True)
    for n, work in enumerate(works[:40], start=1):
        title = work.get("title") or work.get("name") or ""
        date = work.get("release_date") or work.get("first_air_date") or ""
        rating = work.get("vote_average") or 0
        sub = "  ·  ".join(x for x in (f"★ {rating:.1f}" if rating else "", date[:4]) if x)
        poster = work.get("poster_path")
        action = "moviesSearchResults" if work.get("media_type") == "movie" else "showsSearchResults"
        HOME.setProperty(f"nuvio.person.film.{n}.title", title)
        HOME.setProperty(f"nuvio.person.film.{n}.sub", sub)
        HOME.setProperty(f"nuvio.person.film.{n}.poster", f"{TMDB_IMG}w342{poster}" if poster else "")
        HOME.setProperty(f"nuvio.person.film.{n}.path", f"{SEREN}?action={action}&action_args={urllib.parse.quote(title)}")
        HOME.setProperty(f"nuvio.person.film.{n}.date", date[:4])
        HOME.setProperty(f"nuvio.person.film.{n}.id", str(work.get("id", "")))
        HOME.setProperty(f"nuvio.person.film.{n}.type", "movie" if work.get("media_type") == "movie" else "tv")


def show_person(person_id):
    """Open the person page (Custom_1180_Person.xml) and fill it from TMDB."""
    if not str(person_id).isdigit():
        return
    for key in ("name", "born", "place", "bio", "photo", "count", "studio"):
        HOME.clearProperty(f"nuvio.person.{key}")
    for n in range(1, 41):
        for p in ("title", "sub", "poster", "path", "date", "id", "type"):
            HOME.clearProperty(f"nuvio.person.film.{n}.{p}")
    HOME.setProperty("nuvio.open.overlay", json.dumps(["person", str(person_id)]))
    xbmc.executebuiltin("ActivateWindow(1180)")
    try:
        person = tmdb(f"person/{person_id}", append_to_response="combined_credits")
        if not person.get("biography") and _NL:
            person["biography"] = tmdb(f"person/{person_id}", language="en-US").get("biography", "")
    except Exception as error:  # noqa: BLE001
        log(f"person: {error}")
        if not tmdb_key():
            xbmcgui.Dialog().ok(HEADING, tr("no_tmdb"))
        else:
            notify(tr("failed_tmdb"), xbmcgui.NOTIFICATION_WARNING)
        return
    born, died = person.get("birthday"), person.get("deathday")
    if born:
        years = age(born, died)
        text = tr("born", nice_date(born)) + (f" ({tr('years', years)})" if years is not None and not died else "")
        if died:
            text += f"  ·  {tr('died', nice_date(died))} ({tr('years', years)})"
        HOME.setProperty("nuvio.person.born", text)
    HOME.setProperty("nuvio.person.place", person.get("place_of_birth") or "")
    HOME.setProperty("nuvio.person.bio", person.get("biography") or "")
    path = person.get("profile_path")
    HOME.setProperty("nuvio.person.photo", f"{TMDB_IMG}h632{path}" if path else "DefaultActor.png")

    credits = person.get("combined_credits") or {}
    works, seen = [], set()
    for entry in (credits.get("cast") or []) + [c for c in credits.get("crew") or [] if c.get("job") == "Director"]:
        key = (entry.get("media_type"), entry.get("id"))
        if key in seen or entry.get("media_type") not in ("movie", "tv"):
            continue
        if entry.get("media_type") == "tv" and entry.get("character", "").lower() in ("himself", "herself", "self"):
            continue
        seen.add(key)
        works.append(entry)
    HOME.setProperty("nuvio.person.count", str(len(works)))
    set_works(works)
    # set the name last: the page shows a spinner until it is there
    HOME.setProperty("nuvio.person.name", person.get("name", ""))


def show_studio(name):
    """Open the person page for a production company: its logo, where it is from and its most popular films / series."""
    if not name:
        return
    for key in ("name", "born", "place", "bio", "photo", "count"):
        HOME.clearProperty(f"nuvio.person.{key}")
    for n in range(1, 41):
        for p in ("title", "sub", "poster", "path", "date", "id", "type"):
            HOME.clearProperty(f"nuvio.person.film.{n}.{p}")
    HOME.setProperty("nuvio.person.studio", "1")
    HOME.setProperty("nuvio.open.overlay", json.dumps(["studio", name]))
    xbmc.executebuiltin("ActivateWindow(1180)")
    try:
        results = tmdb("search/company", query=name).get("results") or []
        exact = [r for r in results if (r.get("name") or "").strip().lower() == name.lower()]
        company = (exact or results[:1] or [None])[0]
        if not company:
            raise RuntimeError("company not found")
        cid = company["id"]
        details = tmdb(f"company/{cid}")
        movies = tmdb("discover/movie", with_companies=cid, sort_by="popularity.desc").get("results") or []
        shows = tmdb("discover/tv", with_companies=cid, sort_by="popularity.desc").get("results") or []
    except Exception as error:  # noqa: BLE001
        log(f"studio: {error}")
        xbmc.executebuiltin("Dialog.Close(1180,true)")
        if not tmdb_key():
            xbmcgui.Dialog().ok(HEADING, tr("no_tmdb"))
        else:
            notify(tr("failed_tmdb"), xbmcgui.NOTIFICATION_WARNING)
        return
    works = [dict(m, media_type="movie") for m in movies[:30]] + [dict(t, media_type="tv") for t in shows[:30]]
    logo = details.get("logo_path") or company.get("logo_path")
    HOME.setProperty("nuvio.person.photo", f"{TMDB_IMG}w500{logo}" if logo else "")
    place = ", ".join(x for x in (details.get("headquarters"), details.get("origin_country")) if x)
    HOME.setProperty("nuvio.person.place", place)
    HOME.setProperty("nuvio.person.bio", details.get("description") or "")
    HOME.setProperty("nuvio.person.count", str(len(works)))
    set_works(works)
    HOME.setProperty("nuvio.person.name", details.get("name") or name)


# ----------------------------------------------------------------------------- open a title's page from TMDB data
def trakt_id_for(kind, tmdb_id):
    """Trakt id of a TMDB title (needed to play it through Seren); None when it cannot be found."""
    try:
        found = Trakt().get(f"search/tmdb/{tmdb_id}?type={'movie' if kind == 'movie' else 'show'}")
        for entry in found or []:
            ids = ((entry.get("movie") if kind == "movie" else entry.get("show")) or {}).get("ids") or {}
            if ids.get("trakt"):
                return int(ids["trakt"])
    except Exception as error:  # noqa: BLE001
        log(f"trakt lookup: {error}")
    return None


def seren_play_url(kind, trakt_id):
    """The address Seren itself gives a film (play: sources) or a series (play: next episode)."""
    args = urllib.parse.quote(json.dumps({"mediatype": "movie" if kind == "movie" else "tvshow", "trakt_id": trakt_id},
                                         sort_keys=True))
    action = "getSources" if kind == "movie" else "forceResumeShow"
    return f"{SEREN}?" + urllib.parse.urlencode(sorted({"action": action, "action_args": args}.items()))


def build_listitem(kind, tmdb_id, trakt_id):
    """A film / series item with TMDB data that the info page can show; Play goes to Seren."""
    lang = "nl" if _NL else "en"
    extra = "credits,external_ids,images,release_dates" if kind == "movie" else "credits,external_ids,images,content_ratings"
    data = tmdb(f"{kind}/{tmdb_id}", append_to_response=extra, include_image_language=f"{lang},en,null")
    if not data.get("overview"):
        try:
            data["overview"] = tmdb(f"{kind}/{tmdb_id}", language="en-US").get("overview", "")
        except Exception:  # noqa: BLE001
            pass
    title = data.get("title") or data.get("name") or ""
    date = data.get("release_date") or data.get("first_air_date") or ""
    li = xbmcgui.ListItem(title, offscreen=True)
    if trakt_id:
        li.setPath(seren_play_url(kind, trakt_id))
        li.setProperty("trakt_id", str(trakt_id))
    tag = li.getVideoInfoTag()
    tag.setMediaType("movie" if kind == "movie" else "tvshow")
    tag.setTitle(title)
    tag.setOriginalTitle(data.get("original_title") or data.get("original_name") or title)
    if date[:4].isdigit():
        tag.setYear(int(date[:4]))
        tag.setPremiered(date)
    tag.setPlot(data.get("overview") or "")
    tag.setTagLine(data.get("tagline") or "")
    tag.setGenres([g.get("name", "") for g in data.get("genres") or []])
    runtime = data.get("runtime") or ((data.get("episode_run_time") or [0])[0])
    if runtime:
        tag.setDuration(int(runtime) * 60)
    if data.get("vote_average"):
        tag.setRating(float(data["vote_average"]), int(data.get("vote_count") or 0), "tmdb", True)
    tag.setStudios([c.get("name", "") for c in data.get("production_companies") or []])
    tag.setCountries([c.get("name", "") for c in data.get("production_countries") or []])
    ids = {"tmdb": str(tmdb_id)}
    imdb = (data.get("external_ids") or {}).get("imdb_id") or data.get("imdb_id")
    if imdb:
        ids["imdb"] = imdb
        tag.setIMDBNumber(imdb)
    if trakt_id:
        ids["trakt"] = str(trakt_id)
    tag.setUniqueIDs(ids, "tmdb")
    # age rating
    mpaa = ""
    country = "NL" if _NL else "US"
    if kind == "movie":
        for block in (data.get("release_dates") or {}).get("results") or []:
            if block.get("iso_3166_1") in (country, "US"):
                certs = [r.get("certification") for r in block.get("release_dates") or [] if r.get("certification")]
                if certs and (not mpaa or block.get("iso_3166_1") == country):
                    mpaa = certs[0]
    else:
        for block in (data.get("content_ratings") or {}).get("results") or []:
            if block.get("iso_3166_1") in (country, "US") and block.get("rating"):
                if not mpaa or block.get("iso_3166_1") == country:
                    mpaa = block["rating"]
    if mpaa:
        tag.setMpaa(mpaa)
    credits = data.get("credits") or {}
    tag.setDirectors([p.get("name", "") for p in credits.get("crew") or [] if p.get("job") == "Director"][:3])
    tag.setCast([xbmc.Actor(p.get("name", ""), p.get("character", ""), n,
                            f"{PROFILE}{p['profile_path']}" if p.get("profile_path") else "")
                 for n, p in enumerate((credits.get("cast") or [])[:MAX_CAST])])
    art = {}
    if data.get("poster_path"):
        art["poster"] = art["thumb"] = f"{TMDB_IMG}w780{data['poster_path']}"
    if data.get("backdrop_path"):
        art["fanart"] = art["landscape"] = f"{TMDB_IMG}w1280{data['backdrop_path']}"
    logos = (data.get("images") or {}).get("logos") or []
    best = next((x for pref in (lang, "en") for x in logos if x.get("iso_639_1") == pref), None) or (logos[0] if logos else None)
    if best:
        art["clearlogo"] = f"{TMDB_IMG}w500{best['file_path']}"
    li.setArt(art)
    return li


def page_identity():
    """Which title the open info page is about, so Back can bring you to it again: [kind, tmdb, trakt] or None.
    (Saved when the page loaded; asking the screen later is not reliable while a list on the page has focus.)"""
    try:
        return json.loads(HOME.getProperty("nuvio.info.identity") or "null")
    except ValueError:
        return None


def remember_identity(item):
    """Called when an info page loads."""
    if item.is_seren_episode:
        item = item.as_show()
    kind = {"movie": "movie", "tvshow": "tv"}.get(item.dbtype)
    ident = [kind, item.tmdb, item.trakt] if kind and item.tmdb.isdigit() else None
    HOME.setProperty("nuvio.info.identity", json.dumps(ident) if ident else "")


def _stack():
    try:
        return json.loads(HOME.getProperty("nuvio.open.stack") or "[]")
    except ValueError:
        return []


def _save_stack(stack):
    HOME.setProperty("nuvio.open.stack", json.dumps(stack[-12:]))


def _overlay_open():
    """Which person / studio page is on top of the info page right now: ["person", id] / ["studio", name] or None."""
    if not xbmc.getCondVisibility("Window.IsActive(1180)"):
        return None
    try:
        return json.loads(HOME.getProperty("nuvio.open.overlay") or "null")
    except ValueError:
        return None


def _show_title(kind, tmdb_id, trakt_id):
    """Open the page of a title from TMDB data. Raises when that does not work."""
    trakt = int(trakt_id) if str(trakt_id).isdigit() else trakt_id_for(kind, tmdb_id)
    if not trakt:
        raise RuntimeError("no Trakt id")
    li = build_listitem(kind, tmdb_id, trakt)
    HOME.setProperty("nuvio.open.current", json.dumps([kind, str(tmdb_id)]))
    xbmc.executebuiltin("Dialog.Close(1180,true)")
    xbmc.executebuiltin("Dialog.Close(movieinformation,true)")
    xbmc.Monitor().waitForAbort(0.4)
    # Kodi can hold this call until the page is closed again, so it runs in its own thread and the script goes on
    threading.Thread(target=_show_info, args=(li,)).start()


def _show_info(li):
    try:
        xbmcgui.Dialog().info(li)
    except Exception as error:  # noqa: BLE001
        log(f"info dialog: {error}")


def _wait_page_loaded(tmdb_id):
    """Wait until the info page that was just opened has registered itself (see remember_identity)."""
    monitor = xbmc.Monitor()
    waited = 0.0
    while waited < 5:
        ident = page_identity()
        if ident and str(ident[1]) == str(tmdb_id):
            return
        if monitor.waitForAbort(0.2):
            return
        waited += 0.2


def _new_generation():
    gen = int(HOME.getProperty("nuvio.open.gen") or "0") + 1
    HOME.setProperty("nuvio.open.gen", str(gen))
    return gen


def _restore(entry, stack):
    """Bring one page of the chain back. A person / studio page sits on top of the film page it was opened from,
    so that film page (the entry below it) is opened first."""
    kind = entry[0]
    if kind == "title":
        _show_title(entry[1], entry[2], entry[3])
        return
    title = stack.pop() if stack and stack[-1][0] == "title" else None
    if title:
        _show_title(title[1], title[2], title[3])
        _wait_page_loaded(title[2])
        _save_stack(stack)
    if kind == "person":
        show_person(entry[1])
    elif kind == "studio":
        show_studio(entry[1])


def watch_back(gen):
    """While a page we opened is on screen: when it is closed with Back, show the page you came from
    (film page, or the actor / studio page on top of it), and so on down the chain."""
    monitor = xbmc.Monitor()
    while True:
        waited = 0.0
        while not xbmc.getCondVisibility("Window.IsActive(movieinformation)"):
            if monitor.waitForAbort(0.2):
                return
            if waited > 15:
                log("back: page did not appear, stop watching")
                HOME.clearProperty("nuvio.open.current")
                return
            waited += 0.2
        while xbmc.getCondVisibility("Window.IsActive(movieinformation) | Window.IsActive(1180)"):
            if monitor.waitForAbort(0.3):
                return
        if HOME.getProperty("nuvio.open.gen") != str(gen):
            log("back: another page took over")
            return                      # another page took over
        stack = _stack()
        if HOME.getProperty("nuvio.open.leave") or not stack:
            log(f"back: nothing to do (leave={HOME.getProperty('nuvio.open.leave')!r}, stack={stack})")
            HOME.clearProperty("nuvio.open.stack")
            HOME.clearProperty("nuvio.open.current")
            return                      # Play / trailer, or nothing to go back to
        if monitor.waitForAbort(0.5):
            return
        if xbmc.Player().isPlaying() or xbmc.getCondVisibility("Window.IsActive(fullscreenvideo)"):
            log("back: a video started, no going back")
            HOME.clearProperty("nuvio.open.stack")
            HOME.clearProperty("nuvio.open.current")
            return
        entry = stack.pop()
        _save_stack(stack)
        log(f"back: reopening {entry}")
        gen = _new_generation()
        try:
            _restore(entry, stack)
            _save_stack(stack)
        except Exception as error:  # noqa: BLE001
            log(f"back: {error}")
            return


def open_title():
    """Click on a title (collection, actor / studio films, similar titles): open ITS PAGE straight from TMDB data
    (Play then goes to Seren). Back brings you to the page you came from: the film page, or the actor / studio page
    on top of it, and so on all the way down. When this is not possible fall back to opening Seren's list and
    pressing Info."""
    kind = HOME.getProperty("nuvio.open.type") or "movie"
    tmdb_id = HOME.getProperty("nuvio.open.tmdb")
    trakt_id = HOME.getProperty("nuvio.open.trakt")
    mode = sys.argv[2] if len(sys.argv) > 2 else "path"
    fallback = f"RunScript(special://skin/scripts/openpage.py,{mode})"
    if not tmdb_id.isdigit() or not tmdb_key():
        xbmc.executebuiltin(fallback)
        return
    # the pages we leave: the film page and, when we come from it, the person / studio page on top
    leaving = []
    ident = page_identity()
    if ident:
        leaving.append(["title"] + ident)
    overlay = _overlay_open()
    if overlay:
        leaving.append(overlay)
    gen = _new_generation()
    HOME.clearProperty("nuvio.open.leave")
    stack = _stack()
    # the page you leave was not opened by Lucent (you came from a list or Home): a new chain starts
    try:
        current = json.loads(HOME.getProperty("nuvio.open.current") or "null")
    except ValueError:
        current = None
    if not ident or current != [ident[0], str(ident[1])]:
        stack = []
    # the page you leave is already in the chain (you went back to it): continue from there
    for i in range(len(stack) - 1, -1, -1):
        if leaving and stack[i] == leaving[0]:
            stack = stack[:i]
            break
    for entry in leaving:
        if not stack or stack[-1] != entry:
            stack.append(entry)
    _save_stack(stack)
    log(f"open {kind} {tmdb_id}; leaving {leaving}; stack {stack[-12:]}")
    try:
        _show_title(kind, tmdb_id, trakt_id)
    except Exception as error:  # noqa: BLE001
        log(f"open title: {error}")
        xbmc.executebuiltin(fallback)
        return
    watch_back(gen)


LOGO_DIR = "special://profile/addon_data/skin.lucent/logos/"
LOGO_SOURCES = ("imdb", "tmdb", "trakt")


def load_logos():
    """Your own rating logos: put imdb.png, tmdb.png and trakt.png in LOGO_DIR and the info page uses them."""
    if not xbmcvfs.exists(LOGO_DIR):
        xbmcvfs.mkdirs(LOGO_DIR)
    for name in LOGO_SOURCES:
        path = f"{LOGO_DIR}{name}.png"
        HOME.setProperty(f"nuvio.logo.{name}", path if xbmcvfs.exists(path) else "")


def load():
    item = Item()
    load_logos()
    remember_identity(item)
    if not tmdb_key() and not HOME.getProperty("nuvio.tmdb.warned"):
        HOME.setProperty("nuvio.tmdb.warned", "1")   # once per Kodi session
        xbmcgui.Dialog().notification(HEADING, tr("no_tmdb"), xbmcgui.NOTIFICATION_WARNING, 8000)
    HOME.setProperty("nuvio.info.key", item.key)
    HOME.clearProperty("nuvio.info.watched")
    load_studios()
    load_credits(item)
    load_videos(item)
    load_collection(item)


if __name__ == "__main__":
    action = sys.argv[1] if len(sys.argv) > 1 else "load"
    if action == "lists":
        choose_lists()
    elif action == "watched":
        toggle_watched()
    elif action == "studio":
        show_studio(HOME.getProperty("nuvio.open.studio"))
    elif action == "open":
        open_title()
    elif action == "tmdbkey":
        set_tmdb_key()
    elif action == "person":
        show_person(sys.argv[2] if len(sys.argv) > 2 else "")
    else:
        load()
