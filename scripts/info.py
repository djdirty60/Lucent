# -*- coding: utf-8 -*-
"""Lucent: helpers for the info page (DialogVideoInfo).

RunScript(special://skin/scripts/info.py,load)      fill the collection row and the studios
RunScript(special://skin/scripts/info.py,lists)     choose: Trakt collection, watchlist, own Trakt lists
RunScript(special://skin/scripts/info.py,watched)   mark as watched / unwatched on Trakt

Trakt calls use Lucent's own Trakt login (traktlogin.py); without it, the Trakt login of a video add-on that shares it.
Everything shown on the page goes through Window(home) properties named nuvio.info.*.
"""
import json
import re
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request

import xbmc
import xbmcaddon
import xbmcgui
import xbmcvfs

HEADING = "Lucent"
TRAKT = "https://api.trakt.tv/"
TMDB = "https://api.themoviedb.org/3/"
TMDB_IMG = "https://image.tmdb.org/t/p/"
MAX_COLLECTION = 12
MAX_STUDIOS = 4
HOME = xbmcgui.Window(10000)

_NL = xbmc.getLanguage(xbmc.ISO_639_1) == "nl"
T = {
    "library": ("Trakt collection", "Trakt-collectie"),
    "added_to": ("{0} added to your library ({1})", "{0} toegevoegd aan je bibliotheek ({1})"),
    "watchlist": ("Trakt · Watchlist", "Trakt · Kijklijst"),
    "list": ("Trakt · {0}", "Trakt · {0}"),
    "pick": ("{0} – choose the lists for this title", "{0} – kies in welke lijsten deze titel staat"),
    "loading": ("Loading your Trakt lists…", "Je Trakt-lijsten laden…"),
    "saved": ("Saved", "Opgeslagen"),
    "nothing": ("Nothing changed", "Niets veranderd"),
    "no_video": ("You are not logged in to Trakt. Log in at Skin settings > Follow > Trakt login.",
                 "Je bent niet ingelogd bij Trakt. Log in bij Skin-instellingen > Volgen > Trakt-login."),
    "no_login": ("You are not logged in to Trakt. Log in at Skin settings > Follow > Trakt login.",
                 "Je bent niet ingelogd bij Trakt. Log in bij Skin-instellingen > Volgen > Trakt-login."),
    "expired": ("Trakt does not accept the login any more (Trakt code {0}). Log in again: "
                "you get a code that you enter on trakt.tv/activate.",
                "Trakt accepteert de login niet meer (Trakt-code {0}). Log opnieuw in: "
                "je krijgt een code die je invult op trakt.tv/activate."),
    "relink": ("Log in again now", "Nu opnieuw inloggen"),
    "later": ("Later", "Later"),
    "failed": ("Trakt did not respond. Try again later.", "Trakt reageert niet. Probeer het later opnieuw."),
    "no_ids": ("This title has no Trakt or TMDB id.", "Deze titel heeft geen Trakt- of TMDB-nummer."),
    "watched": ("Marked as watched", "Gemarkeerd als bekeken"),
    "unwatched": ("Marked as not watched", "Gemarkeerd als niet bekeken"),
    "director": ("Director", "Regisseur"),
    "creator": ("Creator", "Bedenker"),
    "born": ("Born: {0}", "Geboren: {0}"),
    "died": ("Died: {0}", "Overleden: {0}"),
    "years": ("{0} years", "{0} jaar"),
    "no_tmdb": ("No TMDB key yet. Enter your own free key in Skin settings > Integrations (or in your video add-on).",
                "Nog geen TMDB-sleutel. Vul je eigen gratis sleutel in bij Skin-instellingen > Integraties (of in je video-add-on)."),
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
    def __init__(self, prefix="ListItem."):
        def info(label):                           # read from the focused item, or from a named list
            return xbmc.getInfoLabel(f"{prefix}{label}")
        self._prefix = prefix
        self.dbtype = info("DBType") or "movie"
        self.title = info("Title") or info("Label")
        self.trakt = info("Property(trakt_id)")
        self.tmdb = info("UniqueID(tmdb)") or info("Property(tmdb_id)")
        self.imdb = info("UniqueID(imdb)") or info("IMDBNumber") or info("Property(imdb_id)")
        self.watched = int(info("PlayCount") or 0) > 0
        # some add-ons give episodes and seasons the ids of their show (tmdb/imdb) plus trakt_show_id
        self.show_trakt = info("Property(trakt_show_id)") if self.dbtype in ("season", "episode") else ""
        self.key = self.trakt or self.tmdb or self.imdb or self.title

    @property
    def has_show_trakt(self):
        return self.dbtype in ("season", "episode") and self.show_trakt.isdigit()

    def as_show(self):
        """The show an episode or season belongs to (for lists, credits, similar titles and trailers)."""
        show = Item.__new__(Item)
        show.__dict__.update(self.__dict__)
        show.dbtype, show.trakt, show.show_trakt = "tvshow", self.show_trakt, ""
        show.title = xbmc.getInfoLabel(f"{self._prefix}TVShowTitle") or self.title
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


# ----------------------------------------------------------------------------- Trakt (the video add-on's login)
LV_DATA = "special://profile/addon_data/plugin.video.lucent/"


def _lv_json(name):
    try:
        with open(xbmcvfs.translatePath(LV_DATA + name), encoding="utf-8") as fh:
            data = json.load(fh)
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def lv_trakt():
    """(client id, login) of the Trakt login of the video add-on, or ("", "") when it is not logged in.
    The add-on renews its own login whenever it talks to Trakt, so an expired one is simply not used."""
    if not xbmc.getCondVisibility("System.HasAddon(plugin.video.lucent)"):
        return "", ""
    account = _lv_json("trakt.json")
    token = account.get("access_token") or ""
    try:
        if token and float(account.get("expires_at") or 0) < time.time() + 120:
            token = ""
    except (TypeError, ValueError):
        pass
    try:
        client = xbmcaddon.Addon("plugin.video.lucent").getSetting("trakt_id").strip()
    except Exception:  # noqa: BLE001
        client = ""
    client = client or (_lv_json("keys.json").get("trakt_client_id") or "")
    return (client, token) if client and token else ("", "")


def trakt_available():
    """Lucent has its own Trakt login, or a video add-on whose login Lucent can share is installed."""
    import traktlogin
    return traktlogin.has_login() or xbmc.getCondVisibility("System.HasAddon(plugin.video.lucent)")


def relink_trakt():
    """Log in to Trakt again (a code you enter on trakt.tv/activate)."""
    import traktlogin
    traktlogin.login()


def lv_supports(action):
    """True when the installed the video add-on knows this action or row name (versions can go back as well as forward,
    so its code is checked instead of its version number)."""
    try:
        path = xbmcvfs.translatePath("special://home/addons/plugin.video.lucent/resources/lib/router.py")
        with open(path, encoding="utf-8") as fh:
            return f'"{action}"' in fh.read()
    except OSError:
        return False


def lv_renew(wait=15):
    """The video add-on renews its Trakt login itself: ask it (0.32.4+: action=trakt_refresh, older: open the watchlist once)
    and wait for the new login."""
    old = _lv_json("trakt.json").get("access_token") or ""
    if not old or not _lv_json("trakt.json").get("refresh_token"):
        return
    if lv_supports("trakt_refresh"):             # its own quiet renewal (no listing, no dialog)
        xbmc.executebuiltin("RunPlugin(plugin://plugin.video.lucent/?action=trakt_refresh)")
    else:
        xbmc.executebuiltin("RunPlugin(plugin://plugin.video.lucent/?action=list&name=watchlist_movie&widget=1)")
    monitor = xbmc.Monitor()
    for _ in range(int(wait * 2)):
        if monitor.waitForAbort(0.5):
            return
        if (_lv_json("trakt.json").get("access_token") or "") != old:
            log("Trakt login renewed by the video add-on")
            return


class Trakt:
    """Trakt with Lucent's own login, else the shared login of a video add-on."""

    def __init__(self):
        import traktlogin
        self.own = traktlogin.has_login()
        if self.own:
            self.client_id, self.token = traktlogin.credentials()
            return
        self.client_id, self.token = lv_trakt()
        if not self.token and _lv_json("trakt.json").get("access_token"):
            lv_renew()
            self.client_id, self.token = lv_trakt()

    def headers(self):
        return {"Content-Type": "application/json", "trakt-api-version": "2",
                "trakt-api-key": self.client_id, "Authorization": f"Bearer {self.token}"}

    def _call(self, path, data=None):
        try:
            if data is None:
                return http(TRAKT + path, headers=self.headers())
            return http(TRAKT + path, data=data, headers=self.headers(), method="POST")
        except urllib.error.HTTPError as error:
            if error.code != 401 or not self.token:
                raise
            if self.own:                                 # rejected: renew it once, then try again
                import traktlogin
                client, token = (traktlogin.load().get("client_id", ""), traktlogin.load().get("access_token", "")) \
                    if traktlogin.renew() else ("", "")
            else:
                lv_renew()                               # let the video add-on renew it once, then try again
                client, token = lv_trakt()
            if not token or token == self.token:
                raise
            self.client_id, self.token = client, token
            if data is None:
                return http(TRAKT + path, headers=self.headers())
            return http(TRAKT + path, data=data, headers=self.headers(), method="POST")

    def get(self, path):
        return self._call(path)

    def get_all(self, path, cap=40):
        """Every page: Trakt gives only 100 items without page / limit."""
        out = []
        for page in range(1, cap + 1):
            data = self.get(f"{path}{'&' if '?' in path else '?'}page={page}&limit=250")
            if not isinstance(data, list) or not data or (out and data[0] == out[0]):
                break                              # empty, or Trakt ignores pages and gave everything again
            out += data
            if len(data) < 100:
                break                              # less than the smallest page Trakt gives: this was the last
        return out

    def post(self, path, data):
        return self._call(path, data)


def trakt_or_explain():
    if not trakt_available():
        xbmcgui.Dialog().ok(HEADING, tr("no_video"))
        return None
    trakt = Trakt()
    if not trakt.token:
        xbmcgui.Dialog().ok(HEADING, tr("no_login"))
        return None
    return trakt


TRAKT_CODES = {
    400: ("Trakt did not understand the request", "Trakt begreep het verzoek niet"),
    404: ("Trakt does not know this title", "Trakt kent deze titel niet"),
    409: ("It was already there", "Het stond er al"),
    420: ("Trakt says this list is full (the most items Trakt allows for your account)",
          "Trakt zegt dat deze lijst vol zit (het maximum dat Trakt voor je account toestaat)"),
    423: ("Your Trakt account is locked - contact Trakt support", "Je Trakt-account is geblokkeerd - neem contact op met Trakt"),
    426: ("Only for Trakt VIP", "Alleen voor Trakt VIP"),
    429: ("Too many requests to Trakt - wait a minute", "Te veel verzoeken naar Trakt - wacht een minuut"),
}


def explain_error(error, where=""):
    body, extra = "", ""
    if isinstance(error, urllib.error.HTTPError):
        try:
            body = error.read().decode("utf-8", "replace")[:300]
        except Exception:  # noqa: BLE001
            pass
        hdr = error.headers or {}
        vip, limit = hdr.get("X-VIP-User", ""), hdr.get("X-Account-Limit", "")
        if vip or limit:
            extra = f"\n[COLOR grey]Trakt: VIP = {vip or '?'}{((', limiet = ' if _NL else ', limit = ') + limit) if limit else ''}[/COLOR]"
    log(f"Trakt error{' at ' + where if where else ''}: {error} {body} {extra.strip()}")
    head = f"[B]{where}[/B]: " if where else ""
    if isinstance(error, urllib.error.HTTPError) and error.code not in (401, 403):
        text = TRAKT_CODES.get(error.code)
        text = text[1 if _NL else 0] if text else ("Trakt is busy or down" if not _NL else "Trakt is druk of ligt eruit") \
            if error.code >= 500 else (f"Trakt answered {error.code}" if not _NL else f"Trakt antwoordde {error.code}")
        xbmcgui.Dialog().ok(HEADING, f"{head}{text}. (Trakt-code {error.code}){extra}")
        return
    if isinstance(error, (urllib.error.URLError, TimeoutError, OSError)) and not isinstance(error, urllib.error.HTTPError):
        xbmcgui.Dialog().ok(HEADING, ("No connection with Trakt: " if not _NL else "Geen verbinding met Trakt: ") + str(error)[:120])
        return
    if not isinstance(error, urllib.error.HTTPError):
        xbmcgui.Dialog().ok(HEADING, ("Something went wrong: " if not _NL else "Er ging iets mis: ") + f"{type(error).__name__}: {str(error)[:120]}")
        return
    if isinstance(error, urllib.error.HTTPError) and error.code in (401, 403):
        if xbmcgui.Dialog().yesno(HEADING, tr("expired", error.code), nolabel=tr("later"), yeslabel=tr("relink")):
            relink_trakt()
    else:
        notify(tr("failed"), xbmcgui.NOTIFICATION_WARNING)


def after_trakt_change():
    """Refresh what is on screen."""
    xbmc.executebuiltin("Container.Refresh")


# ----------------------------------------------------------------------------- the video add-on (1.37.0)
LV_ID = "plugin.video.lucent"
LVP = "plugin://plugin.video.lucent/"


def lv_on():
    return xbmc.getCondVisibility(f"System.AddonIsEnabled({LV_ID})")


def lv_version():
    try:
        return tuple(int(x) for x in xbmc.getInfoLabel(f"System.AddonVersion({LV_ID})").split(".")[:3])
    except ValueError:
        return (0, 0, 0)


def use_lv(prefix="ListItem."):
    """Who does Library and lists / Mark as watched: the video add-on, for its own titles and for titles of other video
    add-ons."""
    return lv_on()


def lv_target(prefix="ListItem."):
    """{type, tmdb[, season, episode]} of the item in the video add-on's words, or None without a TMDB number.
    Episodes and seasons use the number of their series (from the item, or from Kodi's library)."""
    def get(label):
        return xbmc.getInfoLabel(f"{prefix}{label}")
    dbtype = get("DBType") or "movie"
    if dbtype == "movie":
        tmdb_id = get("UniqueID(tmdb)") or get("Property(tmdb_id)")
        return {"type": "movie", "tmdb": tmdb_id} if tmdb_id.isdigit() else None
    if dbtype in ("season", "episode") and get("DBID").isdigit():
        show = str(library_show_ids(prefix).get("tmdb", ""))       # Kodi's library: the episode's own number is not the series'
    elif dbtype in ("season", "episode"):
        show = get("Property(tmdb_id)") or get("UniqueID(tmdb)")
    else:
        show = get("UniqueID(tmdb)") or get("Property(tmdb_id)")
        if not show.isdigit() and get("DBID").isdigit():
            show = str(library_show_ids(prefix).get("tmdb", ""))
    if not show.isdigit():
        return None
    if dbtype == "episode" and get("Season").isdigit() and get("Episode").isdigit():
        return {"type": "episode", "tmdb": show, "season": get("Season"), "episode": get("Episode")}
    if dbtype == "season" and get("Season").isdigit():
        return {"type": "season", "tmdb": show, "season": get("Season")}
    return {"type": "tvshow", "tmdb": show}


def lv_run(action, **params):
    xbmc.executebuiltin(f"RunPlugin({LVP}?{urllib.parse.urlencode(dict(action=action, **params))})")


def lv_watched(prefix="ListItem."):
    target = lv_target(prefix)
    if not target:
        xbmcgui.Dialog().ok(HEADING, tr("no_ids"))
        return
    state = HOME.getProperty("nuvio.info.watched")
    watched = (state == "1") if state in ("0", "1") else int(xbmc.getInfoLabel(f"{prefix}PlayCount") or 0) > 0
    lv_run("watched", value=0 if watched else 1, **target)          # the video add-on tells Trakt / Simkl (or keeps it itself)
    HOME.setProperty("nuvio.info.watched", "0" if watched else "1")
    dbid = xbmc.getInfoLabel(f"{prefix}DBID")
    dbtype = xbmc.getInfoLabel(f"{prefix}DBType")
    if dbid.isdigit() and dbtype in ("movie", "episode"):            # Kodi's own library: the same mark at once
        method = "VideoLibrary.SetMovieDetails" if dbtype == "movie" else "VideoLibrary.SetEpisodeDetails"
        key = "movieid" if dbtype == "movie" else "episodeid"
        xbmc.executeJSONRPC(json.dumps({"jsonrpc": "2.0", "id": 1, "method": method,
                                        "params": {key: int(dbid), "playcount": 0 if watched else 1}}))
    notify(tr("unwatched") if watched else tr("watched"))


def lv_lists(prefix="ListItem."):
    """Library and lists through the video add-on (its own account: Trakt, Simkl or this device)."""
    target = lv_target(prefix)
    if target and target["type"] in ("season", "episode"):
        target = {"type": "tvshow", "tmdb": target["tmdb"]}          # a season or episode: the whole series goes on the list
    if not target:
        xbmcgui.Dialog().ok(HEADING, tr("no_ids"))
        return
    if lv_version() >= LV_LISTS:                                      # the video add-on's own chooser (knows what is on which list)
        lv_run("lists", **target)
        return
    title = xbmc.getInfoLabel(f"{prefix}Title") or xbmc.getInfoLabel(f"{prefix}Label")
    rows = [(G_LV["wl_add"], "watchlist", {"value": 1}), (G_LV["wl_remove"], "watchlist", {"value": 0})]
    if lv_version() >= (0, 26, 0):
        rows += [(G_LV["lib_add"], "library_add", {}), (G_LV["lib_remove"], "library_remove", {})]
    pick = xbmcgui.Dialog().select(tr("pick", title), [r[0][1 if _NL else 0] for r in rows])
    if pick < 0:
        return
    _label, action, extra = rows[pick]
    lv_run(action, **dict(target, **extra))


def lv_menu(prefix="ListItem."):
    """'More' on the info page: all of the video add-on's options for this title in one menu (the video add-on 0.30.0)."""
    target = lv_target(prefix)
    if not target:
        xbmcgui.Dialog().ok(HEADING, tr("no_ids"))
        return
    # the video add-on 0.33.3 leaves out what the page has a button for; ask for everything when one of those is missing
    on_page = xbmc.getCondVisibility(
        "Control.IsVisible(21) + Control.IsVisible(22)"
        " + [Integer.IsGreater(Window(home).Property(nuvio.info.cast.count),0) | Integer.IsGreater(Container(50).NumItems,0)]"
        " + Integer.IsGreater(Window(home).Property(nuvio.info.vid.count),0) + System.HasAddon(plugin.video.youtube)")
    if not on_page:
        target = dict(target, all="1")
    lv_run("title_menu", **target)


LV_LISTS = (0, 30, 0)       # the first the video add-on with action=lists (asked for in the project; not in 0.29.x)
G_LV = {
    "wl_add": ("Watchlist: add", "Kijklijst: toevoegen"),
    "wl_remove": ("Watchlist: remove", "Kijklijst: weghalen"),
    "lib_add": ("Kodi library: add", "Kodi-bibliotheek: toevoegen"),
    "lib_remove": ("Kodi library: remove", "Kodi-bibliotheek: weghalen"),
}


# ----------------------------------------------------------------------------- series from Kodi's own library
def library_show_ids(prefix="ListItem."):
    """{'trakt', 'tmdb', 'imdb', 'tvdb', 'title'} of the series a library season / episode belongs to.

    Seasons in Kodi's library carry no ids of their own; the series (made by the video add-on) does,
    so ask Kodi for the series by its library number."""
    show_id = ""
    for label in (f"{prefix}TvShowDBID", "ListItem.TvShowDBID"):
        show_id = xbmc.getInfoLabel(label)
        if show_id.isdigit():
            break
    if not show_id.isdigit() and xbmc.getInfoLabel(f"{prefix}DBType") == "tvshow":
        show_id = xbmc.getInfoLabel(f"{prefix}DBID")
    if not show_id.isdigit():
        match = re.search(r"videodb://tvshows/[^/]+/(\d+)/", xbmc.getInfoLabel("Container.FolderPath"))
        show_id = match.group(1) if match else ""
    if not show_id.isdigit():
        return {}
    request = {"jsonrpc": "2.0", "id": 1, "method": "VideoLibrary.GetTVShowDetails",
               "params": {"tvshowid": int(show_id), "properties": ["uniqueid", "imdbnumber", "title"]}}
    try:
        details = json.loads(xbmc.executeJSONRPC(json.dumps(request))).get("result", {}).get("tvshowdetails", {})
    except Exception as error:  # noqa: BLE001
        log(f"library show {show_id}: {error}")
        return {}
    ids = {k: str(v) for k, v in (details.get("uniqueid") or {}).items() if v}
    if str(details.get("imdbnumber", "")).startswith("tt"):
        ids.setdefault("imdb", details["imdbnumber"])
    ids["title"] = details.get("title", "")
    log(f"library show {show_id}: {ids}")
    return ids


def trakt_show_from(ids):
    """The Trakt number of a series from its tmdb / imdb / tvdb number (Trakt search)."""
    if str(ids.get("trakt", "")).isdigit():
        return str(ids["trakt"])
    if not trakt_available():
        return ""
    trakt = Trakt()
    for kind in ("tmdb", "imdb", "tvdb"):
        if ids.get(kind):
            try:
                for hit in trakt.get(f"search/{kind}/{ids[kind]}?type=show") or []:
                    found = (hit.get("show") or {}).get("ids", {}).get("trakt")
                    if found:
                        return str(found)
            except Exception as error:  # noqa: BLE001
                log(f"trakt search {kind}: {error}")
    return ""


# ----------------------------------------------------------------------------- lists dialog
def choose_lists(container=""):
    prefix = f"Container({container}).ListItem." if container.isdigit() else "ListItem."
    if use_lv(prefix):
        lv_lists(prefix)
        return
    item = Item(prefix)
    if item.dbtype in ("season", "episode") and (item.has_show_trakt or item.tmdb.isdigit() or item.imdb.startswith("tt")):
        item = item.as_show()                      # a season or episode: put the whole series in the list
    if not item.ids() and item.dbtype in ("season", "episode", "tvshow"):
        lib = library_show_ids(item._prefix)       # Kodi's own library: the ids sit on the series
        if lib:
            item.dbtype, item.show_trakt = "tvshow", ""
            item.trakt, item.tmdb, item.imdb = lib.get("trakt", ""), lib.get("tmdb", ""), lib.get("imdb", "")
            item.title = lib.get("title") or item.title
            if not item.ids() and lib.get("tvdb"):
                item.trakt = trakt_show_from(lib)
    if not item.ids():
        log(f"lists: no ids (container={container!r} type={item.dbtype} trakt={item.trakt!r} show={item.show_trakt!r} "
            f"tmdb={item.tmdb!r} imdb={item.imdb!r})")
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
        rows = []  # (label, in_list, add_path, remove_paths, library row)
        collection = trakt.get_all(f"sync/collection/{kind}")
        in_coll = any(item.matches(e) for e in collection)
        rows.append((tr("library"), in_coll, "sync/collection", ["sync/collection/remove"], True))
        progress.update(30)
        watchlist = trakt.get_all(f"sync/watchlist/{kind}")
        rows.append((tr("watchlist"), any(item.matches(e) for e in watchlist),
                     "sync/watchlist", ["sync/watchlist/remove"], False))
        progress.update(50)
        lists = trakt.get("users/me/lists") or []
        for n, lst in enumerate(lists[:25]):
            if progress.iscanceled():
                progress.close()
                return
            slug = lst.get("ids", {}).get("trakt")
            try:
                entries = trakt.get_all(f"users/me/lists/{slug}/items/{item.kind}")
            except Exception as error:  # noqa: BLE001 - skip this one list, show the rest
                log(f"Trakt list {lst.get('name')}: {error}")
                continue
            rows.append((tr("list", lst.get("name", "")), any(item.matches(e) for e in entries),
                         f"users/me/lists/{slug}/items", [f"users/me/lists/{slug}/items/remove"], False))
            progress.update(50 + int(50 * (n + 1) / max(1, len(lists[:25]))))
    except Exception as error:  # noqa: BLE001 - show a friendly message instead of a traceback
        progress.close()
        explain_error(error)
        return
    progress.close()

    items = []
    for label, _in_list, _a, _r, is_library in rows:
        li = xbmcgui.ListItem(label)
        li.setArt({"icon": "icons/library.png" if is_library or "Trakt" not in label else "icons/trakt.png"})
        items.append(li)
    preselect = [n for n, row in enumerate(rows) if row[1]]
    chosen = xbmcgui.Dialog().multiselect(tr("pick", item.title), items, preselect=preselect)
    if chosen is None:
        return
    changes = 0
    for n, (label, in_list, add_path, remove_paths, is_library) in enumerate(rows):
        wanted = n in chosen
        if wanted == in_list:
            continue
        try:
            for path in ([add_path] if wanted else remove_paths):
                trakt.post(path, item.payload())
        except Exception as error:  # noqa: BLE001 - say which one failed, go on with the others
            explain_error(error, label)
            continue
        changes += 1
    if changes:
        notify(tr("saved"))
        after_trakt_change()
    else:
        notify(tr("nothing"))


def quick_add():
    """Long press > Add to my library: in the video add-on (when it is there), else in the Trakt collection."""
    if use_lv():
        target = lv_target()
        if target and target["type"] in ("season", "episode"):
            target = {"type": "tvshow", "tmdb": target["tmdb"]}
        if target and lv_version() >= (0, 26, 0):
            lv_run("library_add", **target)
            return
        if target:
            lv_run("watchlist", value=1, **target)
            return
    item = Item()
    if not item.ids() or item.kind not in ("movie", "show"):
        xbmcgui.Dialog().ok(HEADING, tr("no_ids"))
        return
    trakt = trakt_or_explain()
    if not trakt:
        return
    try:
        trakt.post("sync/collection", item.payload())
    except Exception as error:  # noqa: BLE001
        explain_error(error)
        return
    notify(tr("added_to", item.title, tr("library")))
    after_trakt_change()


# ----------------------------------------------------------------------------- watched
def fen_light_id():
    """The add-on of this item when it is Fen Light or a clone of it (Red Light, ...), else ''."""
    path = info("FileNameAndPath") or info("Path") or xbmc.getInfoLabel("Container.FolderPath")
    parts = path.split("/")
    if not path.startswith("plugin://") or len(parts) < 3:
        return ""
    try:
        with xbmcvfs.File(f"special://home/addons/{parts[2]}/resources/lib/modules/router.py") as fh:
            return parts[2] if "watched_status.mark_episode" in fh.read() else ""
    except Exception:  # noqa: BLE001
        return ""


def fen_light_mark(addon_id, item, watched):
    """Let Fen Light / Red Light mark it itself: it also tells Trakt, as set in that add-on."""
    season, episode = info("Season"), info("Episode")
    if item.dbtype == "episode" and season.isdigit() and episode.isdigit():
        params = {"mode": "watched_status.mark_episode", "tmdb_id": item.tmdb, "tvdb_id": info("UniqueID(tvdb)") or "0",
                  "season": season, "episode": episode, "title": info("TVShowTitle") or item.title}
    elif item.dbtype == "movie":
        params = {"mode": "watched_status.mark_movie", "tmdb_id": item.tmdb, "title": item.title}
    else:
        return False
    params["action"] = "mark_as_unwatched" if watched else "mark_as_watched"
    params["refresh"] = "false"
    xbmc.executebuiltin(f"RunPlugin(plugin://{addon_id}/?{urllib.parse.urlencode(params)})")
    HOME.setProperty("nuvio.info.watched", "0" if watched else "1")
    return True


def toggle_watched():
    if use_lv() and not fen_light_id():
        lv_watched()
        return
    item = Item()
    fen = fen_light_id()                            # Fen Light / Red Light: the add-on marks it (and tells Trakt) itself
    if fen and item.tmdb.isdigit():
        state = HOME.getProperty("nuvio.info.watched")
        if fen_light_mark(fen, item, (state == "1") if state in ("0", "1") else item.watched):
            return
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
    dbid = info("DBID")
    if dbid.isdigit() and item.dbtype in ("movie", "episode"):     # Kodi's own library: the same mark at once
        method = "VideoLibrary.SetMovieDetails" if item.dbtype == "movie" else "VideoLibrary.SetEpisodeDetails"
        key = "movieid" if item.dbtype == "movie" else "episodeid"
        xbmc.executeJSONRPC(json.dumps({"jsonrpc": "2.0", "id": 1, "method": method,
                                        "params": {key: int(dbid), "playcount": 0 if watched else 1}}))
    notify(tr("unwatched") if watched else tr("watched"))
    after_trakt_change()


# ----------------------------------------------------------------------------- collection + studios
TMDB_KEYFILES = (
    "special://profile/addon_data/skin.lucent/tmdb_key.txt",
)


def _read_key(path):
    try:
        with xbmcvfs.File(path) as fh:
            return (fh.read() or "").strip()
    except Exception:  # noqa: BLE001
        return ""


_KEY = {"value": "", "time": 0.0}


def tmdb_key():
    """Your own free TMDB key: the key you entered in Skin settings, else the video add-on's.
    Remembered for 10 minutes (the background helper asks for it hundreds of times)."""
    if _KEY["value"] and time.time() - _KEY["time"] < 600:
        return _KEY["value"]
    key = ""
    for path in TMDB_KEYFILES:
        if key:
            break
        key = _read_key(path)
    if not key:                                         # the video add-on: its own setting, or the tester code's keys.json
        try:
            key = (xbmcaddon.Addon("plugin.video.lucent").getSetting("tmdb_key") or "").strip() \
                if xbmc.getCondVisibility("System.HasAddon(plugin.video.lucent)") else ""
        except Exception:  # noqa: BLE001 - not installed
            key = ""
        if not key:
            try:
                key = str(json.loads(_read_key("special://profile/addon_data/plugin.video.lucent/keys.json") or "{}").get("tmdb") or "").strip()
            except ValueError:
                key = ""
    _KEY.update(value=key, time=time.time())
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
    _KEY["time"] = 0.0                              # use the new key right away
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
    if item.has_show_trakt:
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


MAX_PROVIDERS = 6


def _region():
    """Country for the streaming services: from Kodi's language (nl -> NL), else NL."""
    try:
        code = xbmc.getLanguage(xbmc.ISO_639_1, True) or ""
        if "-" in code:
            return code.split("-")[1].upper()
        return {"nl": "NL", "en": "GB", "de": "DE", "fr": "FR", "be": "BE"}.get(code.lower(), "NL")
    except Exception:  # noqa: BLE001
        return "NL"


def load_providers(item):
    """Fill nuvio.info.prov.* with the streaming services where this title can be watched (TMDB / JustWatch)."""
    for n in range(1, MAX_PROVIDERS + 1):
        HOME.clearProperty(f"nuvio.info.prov.{n}.logo")
        HOME.clearProperty(f"nuvio.info.prov.{n}.name")
    HOME.setProperty("nuvio.info.prov.count", "0")
    HOME.clearProperty("nuvio.info.prov.names")
    if item.has_show_trakt:
        item = item.as_show()
    kind = {"movie": "movie", "tvshow": "tv"}.get(item.dbtype)
    if not kind or not item.tmdb.isdigit():
        return
    try:
        result = (tmdb(f"{kind}/{item.tmdb}/watch/providers").get("results") or {}).get(_region()) or {}
    except Exception as error:  # noqa: BLE001
        log(f"providers: {error}")
        return
    if HOME.getProperty("nuvio.info.key") != item.key:
        return
    seen, providers = set(), []
    for group in ("flatrate", "free", "ads"):
        for p in sorted(result.get(group) or [], key=lambda p: p.get("display_priority", 99)):
            if p.get("provider_id") in seen:
                continue
            seen.add(p.get("provider_id"))
            providers.append(p)
    providers = providers[:MAX_PROVIDERS]
    for n, p in enumerate(providers, start=1):
        HOME.setProperty(f"nuvio.info.prov.{n}.name", p.get("provider_name", ""))
        logo = p.get("logo_path")
        HOME.setProperty(f"nuvio.info.prov.{n}.logo", f"{TMDB_IMG}w92{logo}" if logo else "")
    HOME.setProperty("nuvio.info.prov.names", ", ".join(p.get("provider_name", "") for p in providers[:3]))
    HOME.setProperty("nuvio.info.prov.count", str(len(providers)))


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
    if item.has_show_trakt:
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
        HOME.setProperty(f"nuvio.person.film.{n}.title", title)
        HOME.setProperty(f"nuvio.person.film.{n}.sub", sub)
        HOME.setProperty(f"nuvio.person.film.{n}.poster", f"{TMDB_IMG}w342{poster}" if poster else "")
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
        if entry.get("media_type") == "tv" and (entry.get("character") or "").lower() in ("himself", "herself", "self"):
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
def build_listitem(kind, tmdb_id, trakt_id):
    """A film / series item with TMDB data that the info page can show."""
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
    if item.has_show_trakt:
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


def lv_open_with():
    """Titles opened by Lucent itself (actor, collection, similar): played with the video add-on."""
    return lv_on()


def lv_play_url(kind, tmdb_id):
    return f"{LVP}?action=play&type=movie&tmdb={tmdb_id}" if kind == "movie" else f"{LVP}?action=seasons&tmdb={tmdb_id}"


def _show_title(kind, tmdb_id, trakt_id):
    """Open the page of a title from TMDB data. Raises when that does not work."""
    if lv_open_with():
        li = build_listitem(kind, tmdb_id, None)
        li.setPath(lv_play_url(kind, tmdb_id))
        li.setProperty("tmdb_id", str(tmdb_id))
        li.setProperty("lucent_video", "1")
        if kind != "movie":
            try:
                li.setIsFolder(True)
            except AttributeError:      # older Kodi
                pass
        folder = lv_play_url(kind, tmdb_id) if kind != "movie" else ""
    else:                                            # no video add-on: the page shows the title, Play has nothing to start
        li = build_listitem(kind, tmdb_id, trakt_id if str(trakt_id).isdigit() else None)
        folder = ""
    HOME.setProperty("nuvio.open.current", json.dumps([kind, str(tmdb_id)]))
    # what Play opens for a series: the streaming pop-up (service.py) opens it itself after closing (see there)
    HOME.setProperty("nuvio.open.folder", folder)
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
        while xbmc.getCondVisibility("Window.IsActive(movieinformation) | Window.IsActive(1180)") \
                and HOME.getProperty("nuvio.open.gen") == str(gen):
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
    (Play then goes to the video add-on). Back brings you to the page you came from: the film page, or the actor /
    studio page on top of it, and so on all the way down."""
    kind = HOME.getProperty("nuvio.open.type") or "movie"
    tmdb_id = HOME.getProperty("nuvio.open.tmdb")
    trakt_id = HOME.getProperty("nuvio.open.trakt")
    if kind == "tv" and len(sys.argv) > 3 and sys.argv[3] == "series" and not Skin_series_page():
        open_seasons()                                   # a series in a TMDb row: straight to its seasons
        return
    if not tmdb_id.isdigit() or not tmdb_key():
        notify(tr("no_ids"), xbmcgui.NOTIFICATION_WARNING)
        return
    # the pages we leave: the film page and, when we come from it, the person / studio page on top
    leaving = []
    ident = page_identity() if xbmc.getCondVisibility("Window.IsActive(movieinformation)") else None
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
        notify(tr("failed"), xbmcgui.NOTIFICATION_WARNING)
        return
    watch_back(gen)


def Skin_series_page():
    """Skin setting: a series in a TMDb row opens its page first (instead of its seasons)."""
    return xbmc.getCondVisibility("Skin.HasSetting(lucent.series.page)")


def open_seasons():
    """A series in a TMDb row (streaming services ...): straight to its seasons and episodes in the video add-on, like a
    series in the library. Without one its page opens instead."""
    tmdb_id = HOME.getProperty("nuvio.open.tmdb")
    if lv_open_with() and tmdb_id.isdigit():                 # the video add-on: its seasons, no Trakt number needed
        folder = lv_play_url("tv", tmdb_id)
        if xbmc.getCondVisibility("Window.IsVisible(Lucent_Service.xml)"):
            HOME.setProperty("lucent.svc.folder", folder)    # the pop-up closes and opens it (it is on top of everything)
        else:
            xbmc.executebuiltin(f'ActivateWindow(Videos,"{folder}",return)')
        return
    if len(sys.argv) > 3:
        sys.argv[3] = ""                                 # no endless loop: open its page
    open_title()


LOGO_DIR = "special://profile/addon_data/skin.lucent/logos/"
LOGO_SOURCES = ("imdb", "tmdb", "trakt", "rt")


def load_logos():
    """Your own rating logos: put imdb.png, tmdb.png and trakt.png in LOGO_DIR and the info page uses them."""
    if not xbmcvfs.exists(LOGO_DIR):
        xbmcvfs.mkdirs(LOGO_DIR)
    for name in LOGO_SOURCES:
        path = f"{LOGO_DIR}{name}.png"
        HOME.setProperty(f"nuvio.logo.{name}", path if xbmcvfs.exists(path) else "")


def resume_show():
    """Series page (seasons as tabs): Continue = the episode after the last one you watched (Trakt), played by the
    video add-on; without a Trakt number its seasons open."""
    tmdb_id = xbmc.getInfoLabel("Container(56).ListItem.Property(tmdb_id)") or xbmc.getInfoLabel("ListItem.Property(tmdb_id)")
    if not tmdb_id.isdigit():
        tmdb_id = str((library_show_ids("Container(56).ListItem.") or {}).get("tmdb") or "")
    if not lv_open_with():
        notify(tr("no_video"))
        return
    if not tmdb_id.isdigit():
        notify(tr("no_ids"))
        return
    trakt = ""
    for name in ("Container(56).ListItem.Property(trakt_show_id)", "Container(56).ListItem.Property(tvshow.trakt_id)",
                 "ListItem.Property(trakt_show_id)"):
        trakt = xbmc.getInfoLabel(name)
        if trakt.isdigit():
            break
    if not trakt.isdigit():
        trakt = trakt_show_from(library_show_ids("Container(56).ListItem.") or {}) or trakt_show_from({"tmdb": tmdb_id})
    episode = next_episode(int(trakt)) if str(trakt).isdigit() else None
    if episode and episode.get("season") is not None:
        log(f"continue {tmdb_id}: season {episode['season']} episode {episode['number']} ({episode['why']})")
        xbmc.executebuiltin(f"PlayMedia({LVP}?action=play&type=episode&tmdb={tmdb_id}"
                            f"&season={episode['season']}&episode={episode['number']})")
    else:
        xbmc.executebuiltin(f'ActivateWindow(Videos,"{lv_play_url("tv", tmdb_id)}",return)')


def next_episode(show):
    """The episode 'Continue' should play, from Trakt itself: the first one after the last one you watched (also a new
    episode that just came out). Only when Trakt has no next one: an episode you stopped halfway. None when Trakt cannot
    be asked."""
    try:
        trakt = Trakt()
        if not trakt.token:
            return None
        seasons = {s.get("number"): (s.get("ids") or {}).get("trakt") for s in trakt.get(f"shows/{show}/seasons") or []}
        progress = trakt.get(f"shows/{show}/progress/watched?hidden=false&specials=false&count_specials=false") or {}
        ep = progress.get("next_episode") or {}
        if (ep.get("ids") or {}).get("trakt"):
            return {"season": ep.get("season"), "number": ep.get("number"), "trakt_id": ep["ids"]["trakt"],
                    "trakt_season_id": seasons.get(ep.get("season")), "why": "next after the last watched"}
        for entry in trakt.get("sync/playback/episodes?limit=50") or []:          # stopped halfway, newest first
            if ((entry.get("show") or {}).get("ids") or {}).get("trakt") == show and 2 < float(entry.get("progress") or 0) < 90:
                ep = entry.get("episode") or {}
                return {"season": ep.get("season"), "number": ep.get("number"), "trakt_id": (ep.get("ids") or {}).get("trakt"),
                        "trakt_season_id": seasons.get(ep.get("season")), "why": "stopped halfway"}
    except Exception as error:  # noqa: BLE001
        log(f"next episode of {show}: {error}")
    return None


def load():
    item = Item()
    load_logos()
    remember_identity(item)
    if not tmdb_key() and not HOME.getProperty("nuvio.tmdb.warned"):
        HOME.setProperty("nuvio.tmdb.warned", "1")   # once per Kodi session
        xbmcgui.Dialog().notification(HEADING, tr("no_tmdb"), xbmcgui.NOTIFICATION_WARNING, 8000)
    HOME.setProperty("nuvio.info.key", item.key)
    HOME.clearProperty("nuvio.info.watched")
    try:
        import omdb                                 # IMDb, Rotten Tomatoes, Metacritic (your own OMDb key)
        omdb.load(item)
    except Exception as error:  # noqa: BLE001
        log(f"omdb: {error}")
    load_studios()
    load_providers(item)
    load_credits(item)
    load_videos(item)
    load_collection(item)


if __name__ == "__main__":
    action = sys.argv[1] if len(sys.argv) > 1 else "load"
    if action == "quickadd":
        quick_add()
    elif action == "lists":
        choose_lists(sys.argv[2] if len(sys.argv) > 2 else "")
    elif action == "watched":
        toggle_watched()
    elif action == "lvmenu":
        lv_menu()
    elif action == "studio":
        show_studio(HOME.getProperty("nuvio.open.studio"))
    elif action == "open":
        open_title()
    elif action == "seasons":
        open_seasons()
    elif action == "resumeshow":
        resume_show()
    elif action == "tmdbkey":
        set_tmdb_key()
    elif action == "person":
        show_person(sys.argv[2] if len(sys.argv) > 2 else "")
    else:
        load()
