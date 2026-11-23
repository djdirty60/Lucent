# -*- coding: utf-8 -*-
"""Lucent screensaver: slowly zooming key art with the title logo and genres bottom left.

Pictures come from TMDB (trending films / series) or from the Kodi library. Two slots (a and b) take turns;
the window XML fades one out through black and the other in, and zooms it slowly.

1.2.0: cinema style (plot and score), Continue watching (with a progress bar), new episodes of your shows (today or
tomorrow), a big clock with the weather, night mode (darker from an hour you choose, black after a while), and after
waking up a question whether you want to watch what was on screen (Kodi itself eats the key that wakes the screensaver).
"""
import datetime
import json
import random
import time
import urllib.parse
import urllib.request

import xbmc
import xbmcaddon
import xbmcgui
import xbmcvfs

ADDON = xbmcaddon.Addon()
PATH = ADDON.getAddonInfo("path")
HOME = xbmcgui.Window(10000)
TMDB = "https://api.themoviedb.org/3/"
IMG = "https://image.tmdb.org/t/p/"
KEY = "81d47c322f4bbec199751d9f55e8dda1"       # 1.2.3: Lucent's own TMDB key, when you did not enter your own
LANG = "nl-NL" if xbmc.getLanguage(xbmc.ISO_639_1) == "nl" else "en-US"
NL = LANG == "nl-NL"


def log(text):
    xbmc.log(f"[screensaver.lucent] {text}", xbmc.LOGINFO)


def own_key():
    """Your own TMDB key from Lucent's Skin settings, else the public key."""
    try:
        with xbmcvfs.File("special://profile/addon_data/skin.lucent/tmdb_key.txt") as fh:
            return (fh.read() or "").strip() or KEY
    except Exception:  # noqa: BLE001
        return KEY


def tmdb(path, **params):
    params["api_key"] = own_key()
    params.setdefault("language", LANG)
    request = urllib.request.Request(f"{TMDB}{path}?{urllib.parse.urlencode(params)}", headers={"User-Agent": "screensaver.lucent"})
    with urllib.request.urlopen(request, timeout=15) as response:
        return json.loads(response.read().decode("utf-8"))


def pick_logo(images):
    logos = [x for x in (images or {}).get("logos") or [] if x.get("file_path") and not x["file_path"].lower().endswith(".svg")]
    for lang in ("nl", "en", None):
        for logo in logos:
            if logo.get("iso_639_1") == lang:
                return f"{IMG}w500{logo['file_path']}"
    return f"{IMG}w500{logos[0]['file_path']}" if logos else ""


# ----------------------------------------------------------------------------- where the pictures come from
def trending(kind):
    """[(kind, tmdb id)] of what is popular right now."""
    out = []
    for page in (1, 2):
        try:
            for entry in tmdb(f"trending/{kind}/week", page=page).get("results") or []:
                if entry.get("backdrop_path"):
                    out.append((kind, entry["id"]))
        except Exception as error:  # noqa: BLE001
            log(f"trending {kind}: {error}")
            break
    return out


def tmdb_item(kind, tmdb_id, where=False):
    data = tmdb(f"{kind}/{tmdb_id}", append_to_response="images", include_image_language="nl,en,null")
    if not data.get("backdrop_path"):
        return None
    year = (data.get("release_date") or data.get("first_air_date") or "")[:4]
    genres = [g["name"] for g in (data.get("genres") or [])[:3]]
    runtime = data.get("runtime") or ((data.get("episode_run_time") or [0])[0] if kind == "tv" else 0)
    score = float(data.get("vote_average") or 0)
    return {
        "fanart": f"{IMG}original{data['backdrop_path']}",
        "logo": pick_logo(data.get("images")),
        "title": data.get("title") or data.get("name") or "",
        "genres": "  ·  ".join(([year] if where and year else []) + genres),
        "where": where_to_watch(kind, tmdb_id) if where else "",
        "plot": data.get("overview") or "",
        "score": f"TMDb {score:.1f}" if score else "",
        "year": year,
        "genre": " · ".join(genres[:2]),
        "runtime": duration(runtime),
        "open": ["tmdb", "movie" if kind == "movie" else "tv", str(tmdb_id)],
    }


def duration(minutes):
    minutes = int(minutes or 0)
    if not minutes:
        return ""
    if minutes < 60:
        return f"{minutes} min"
    return f"{minutes // 60} u {minutes % 60:02d} min" if NL else f"{minutes // 60} h {minutes % 60:02d} min"


def text(number, *args):
    value = ADDON.getLocalizedString(number)
    return value.format(*args) if args else value


def rpc(method, params):
    query = {"jsonrpc": "2.0", "id": 1, "method": method, "params": params}
    return json.loads(xbmc.executeJSONRPC(json.dumps(query))).get("result") or {}



REGION = "NL" if LANG == "nl-NL" else "GB"


def watchlist():
    """[(kind, tmdb id)] of your Trakt watchlist (films and series), through the Trakt login in Lucent's Skin settings."""
    try:
        with xbmcvfs.File("special://profile/addon_data/skin.lucent/trakt.json") as fh:
            login = json.loads(fh.read() or "{}")
    except Exception:  # noqa: BLE001 - no Trakt login
        return []
    client, token = login.get("client_id") or "", login.get("access_token") or ""
    if not (client and token):
        return []
    headers = {"Content-Type": "application/json", "trakt-api-version": "2", "trakt-api-key": client,
               "Authorization": f"Bearer {token}", "User-Agent": "screensaver.lucent"}
    out = []
    for path, kind, key in (("sync/watchlist/movies", "movie", "movie"), ("sync/watchlist/shows", "tv", "show")):
        try:
            request = urllib.request.Request(f"https://api.trakt.tv/{path}", headers=headers)
            with urllib.request.urlopen(request, timeout=15) as response:
                for entry in json.loads(response.read().decode("utf-8")) or []:
                    tmdb_id = ((entry.get(key) or {}).get("ids") or {}).get("tmdb")
                    if tmdb_id:
                        out.append((kind, tmdb_id))
        except Exception as error:  # noqa: BLE001
            log(f"watchlist {kind}: {error}")
    return out


def where_to_watch(kind, tmdb_id):
    try:
        result = (tmdb(f"{kind}/{tmdb_id}/watch/providers").get("results") or {}).get(REGION) or {}
    except Exception:  # noqa: BLE001
        return ""
    names = []
    for group in ("flatrate", "free", "ads"):
        for p in sorted(result.get(group) or [], key=lambda p: p.get("display_priority", 99)):
            if p.get("provider_name") and p["provider_name"] not in names:
                names.append(p["provider_name"])
    if not names:
        return ""
    return ("Te zien op " if LANG == "nl-NL" else "Watch on ") + ", ".join(names[:3])


def library_items():
    """Items of the Kodi library that have fanart: [(None, dict)]."""
    out = []
    for method, key, field in (("VideoLibrary.GetMovies", "movies", "movies"), ("VideoLibrary.GetTVShows", "tvshows", "tvshows")):
        props = ["art", "genre", "title", "plot", "rating", "year", "uniqueid"] + (["runtime"] if key == "movies" else [])
        try:
            result = rpc(method, {"properties": props}).get(field) or []
        except Exception as error:  # noqa: BLE001
            log(f"library {key}: {error}")
            continue
        for entry in result:
            art = entry.get("art") or {}
            if art.get("fanart"):
                tmdb_id = str((entry.get("uniqueid") or {}).get("tmdb") or "")
                rating = float(entry.get("rating") or 0)
                if key == "movies":
                    target = ["tmdb", "movie", tmdb_id] if tmdb_id.isdigit() else ["videos", f"videodb://movies/titles/{entry['movieid']}"]
                else:
                    target = ["videos", f"videodb://tvshows/titles/{entry['tvshowid']}/"]
                out.append((None, {"fanart": art["fanart"], "logo": art.get("clearlogo", ""), "title": entry.get("title", ""),
                                   "genres": "  ·  ".join((entry.get("genre") or [])[:3]),
                                   "plot": entry.get("plot") or "", "score": f"{rating:.1f}" if rating else "",
                                   "year": str(entry.get("year") or ""), "genre": " · ".join((entry.get("genre") or [])[:2]),
                                   "runtime": duration((entry.get("runtime") or 0) // 60), "open": target}))
    return out


def in_progress():
    """1.2.0: films and episodes you stopped halfway, from the Kodi library: [(None, dict)]."""
    out = []
    flt = {"field": "inprogress", "operator": "true", "value": ""}
    try:
        for m in rpc("VideoLibrary.GetMovies", {"filter": flt, "properties": ["art", "title", "resume"],
                                                   "limits": {"end": 10}}).get("movies") or []:
            out.append(resume_item(m, m.get("title", ""), "", {"movieid": m["movieid"]}))
        for e in rpc("VideoLibrary.GetEpisodes", {"filter": flt, "properties": ["art", "title", "resume", "showtitle", "season", "episode"],
                                                     "limits": {"end": 10}}).get("episodes") or []:
            out.append(resume_item(e, e.get("showtitle", ""), text(30039, e.get("season"), e.get("episode")),
                                   {"episodeid": e["episodeid"]}))
    except Exception as error:  # noqa: BLE001
        log(f"in progress: {error}")
    return [x for x in out if x]


def resume_item(entry, title, sub, item):
    art = entry.get("art") or {}
    fanart = art.get("fanart") or art.get("tvshow.fanart") or art.get("thumb")
    resume = entry.get("resume") or {}
    total, position = float(resume.get("total") or 0), float(resume.get("position") or 0)
    if not fanart or not total:
        return None
    left = max(1, int((total - position) / 60))
    return (None, {"fanart": fanart, "logo": art.get("clearlogo") or art.get("tvshow.clearlogo") or "", "title": title,
                   "tag": text(30030), "tagcolor": "FFFFFFFF", "tagtext": "FF000000",
                   "sub": "  ·  ".join(x for x in (sub, text(30033, left)) if x),
                   "pct": str(int(100 * position / total)), "open": ["play", json.dumps(item)]})


def new_episodes():
    """1.2.0: episodes of your shows that come out today or tomorrow: the shows in the Kodi library (TMDb) and your
    Trakt calendar. [(None, dict)]"""
    today = datetime.date.today()
    wanted = {today.isoformat(): text(30040), (today + datetime.timedelta(days=1)).isoformat(): text(30032)}
    out, seen = [], set()

    def add(tmdb_id, show_title, season, episode, name, air, fanart, logo, target):
        key = (str(tmdb_id), season, episode)
        if key in seen or air not in wanted:
            return
        seen.add(key)
        tag = wanted[air]
        sub = text(30039, season, episode) + (f"  ·  “{name}”" if name else "")
        out.append((None, {"fanart": fanart, "logo": logo, "title": show_title, "tag": tag, "tagcolor": "FFE5534B",
                           "tagtext": "FFFFFFFF", "sub": sub, "open": target}))

    try:
        shows = rpc("VideoLibrary.GetTVShows", {"properties": ["art", "title", "uniqueid", "status"]}).get("tvshows") or []
    except Exception as error:  # noqa: BLE001
        log(f"new episodes: {error}")
        shows = []
    for show in [s for s in shows if (s.get("uniqueid") or {}).get("tmdb") and s.get("status") != "Ended"][:40]:
        try:
            data = tmdb(f"tv/{show['uniqueid']['tmdb']}")
        except Exception:  # noqa: BLE001
            continue
        art = show.get("art") or {}
        for ep in (data.get("next_episode_to_air"), data.get("last_episode_to_air")):
            if ep and art.get("fanart"):
                add(show["uniqueid"]["tmdb"], show.get("title", ""), ep.get("season_number"), ep.get("episode_number"),
                    ep.get("name") or "", ep.get("air_date") or "", art["fanart"], art.get("clearlogo", ""),
                    ["videos", f"videodb://tvshows/titles/{show['tvshowid']}/"])
    for entry in trakt_calendar(today):
        show, ep = entry.get("show") or {}, entry.get("episode") or {}
        tmdb_id = (show.get("ids") or {}).get("tmdb")
        if not tmdb_id:
            continue
        air = local_date(entry.get("first_aired") or "")
        if air not in wanted or (str(tmdb_id), ep.get("season"), ep.get("number")) in seen:
            continue
        try:
            item = tmdb_item("tv", tmdb_id)
        except Exception:  # noqa: BLE001
            item = None
        if item:
            add(tmdb_id, item["title"], ep.get("season"), ep.get("number"), ep.get("title") or "", air, item["fanart"],
                item["logo"], ["tmdb", "tv", str(tmdb_id)])
    return out


def local_date(stamp):
    try:
        moment = datetime.datetime.strptime(stamp[:19], "%Y-%m-%dT%H:%M:%S").replace(tzinfo=datetime.timezone.utc)
        return moment.astimezone().date().isoformat()
    except ValueError:
        return ""


def trakt_login():
    try:
        with xbmcvfs.File("special://profile/addon_data/skin.lucent/trakt.json") as fh:
            login = json.loads(fh.read() or "{}")
    except Exception:  # noqa: BLE001 - no Trakt login
        return None
    client, token = login.get("client_id") or "", login.get("access_token") or ""
    if not (client and token):
        return None
    return {"Content-Type": "application/json", "trakt-api-version": "2", "trakt-api-key": client,
            "Authorization": f"Bearer {token}", "User-Agent": "screensaver.lucent"}


def trakt_calendar(today):
    headers = trakt_login()
    if not headers:
        return []
    try:
        request = urllib.request.Request(f"https://api.trakt.tv/calendars/my/shows/{today.isoformat()}/2", headers=headers)
        with urllib.request.urlopen(request, timeout=15) as response:
            return json.loads(response.read().decode("utf-8")) or []
    except Exception as error:  # noqa: BLE001
        log(f"trakt calendar: {error}")
        return []


def build_queue(source):
    if source == 3:
        return library_items()
    if source == 4:
        return watchlist() or trending("movie") + trending("tv")
    queue = []
    if source in (0, 1):
        queue += trending("movie")
    if source in (0, 2):
        queue += trending("tv")
    if not queue:                          # offline: use the library instead
        return library_items()
    return queue


# ----------------------------------------------------------------------------- the window
class Screensaver(xbmcgui.WindowXMLDialog):
    class ExitMonitor(xbmc.Monitor):
        def __init__(self, callback):
            super().__init__()
            self.callback = callback

        def onScreensaverDeactivated(self):  # noqa: N802 - Kodi callback name
            self.callback(kodi=True)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.stop = False
        self.monitor = None
        self.current = None                 # what is on screen: its "open" target, for the question after waking up
        self.started = 0.0
        self.own = False                    # 1.2.6: Kodi's screensaver state is off and this window takes the keys itself
        self.choice = ""                    # 'ok' (OK woke it), 'back' or 'other'; '' when Kodi woke it

    def onInit(self):  # noqa: N802
        self.monitor = self.ExitMonitor(self.exit)
        self.setProperty("showgenres", "1" if ADDON.getSettingBool("genres") else "")
        self.setProperty("showclock", "1" if ADDON.getSettingBool("clock") else "")
        self.setProperty("cinema", "1" if setting_bool("cinema", True) else "")
        self.setProperty("bigclock", "1" if setting_bool("bigclock", False) else "")
        self.setProperty("askopen", "1" if setting_bool("askopen", True) and can_open() else "")
        self.started = time.time()
        self.run()

    def onAction(self, action):  # noqa: N802
        aid = action.getId()
        if self.own:
            if aid in (7, 100, 12):         # OK / Enter / click
                self.choice = "ok"
            elif aid in (9, 10, 92, 216, 247, 257, 275, 61448, 61467):
                self.choice = "back"
            elif aid in (106, 107):         # a mouse that moves a little is not a key
                return
            else:
                self.choice = "other"
        self.exit()

    def release_kodi(self):
        """1.2.6: Kodi throws away the key that wakes a screensaver, so it cannot tell OK from Back. As soon as this
        window is on screen it switches Kodi's own screensaver state off (a JSON-RPC action does that without a key);
        the picture stays and the next key comes to this window like to any other. Only when that worked."""
        HOME.setProperty("lucent.saver.own", str(time.time()))
        self.own = True
        xbmc.executeJSONRPC(json.dumps({"jsonrpc": "2.0", "id": 1, "method": "Input.ExecuteAction", "params": {"action": "noop"}}))
        xbmc.Monitor().waitForAbort(0.6)
        if xbmc.getCondVisibility("System.ScreenSaverActive"):
            self.own = False                # did not work: Kodi wakes it as before
            HOME.clearProperty("lucent.saver.own")
        log(f"own keys: {self.own}")

    def exit(self, kodi=False):
        if kodi and self.own:               # Kodi switching its screensaver off is what release_kodi asked for
            return
        self.stop = True
        HOME.clearProperty("lucent.saver.own")
        self.close()

    def show(self, slot, item):
        # restart the slow zoom and drift of this slot: switch it off while it is hidden, then on again
        self.clearProperty(f"{slot}.go")
        xbmc.Monitor().waitForAbort(0.2)
        for key in ("fanart", "logo", "title", "genres", "where", "plot", "score", "year", "genre", "runtime", "tag", "tagcolor", "tagtext", "sub", "pct"):
            self.setProperty(f"{slot}.{key}", item.get(key, ""))
        self.setProperty(f"{slot}.open", "1" if item.get("open") else "")
        self.current = item if item.get("open") else None
        self.setProperty("slot", slot)
        self.setProperty(f"{slot}.go", "1")

    def tick(self):
        """Every half second: the weather line, night mode (darker from the hour you chose, black after a while)."""
        if self.own:
            HOME.setProperty("lucent.saver.own", str(time.time()))   # still on screen (see __main__)
        if self.getProperty("bigclock"):
            self.setProperty("weather", weather_line())
        night_from = setting_int("nightfrom", 23)
        hour = time.localtime().tm_hour
        night = bool(night_from) and (hour >= night_from or hour < 6)
        self.setProperty("night", "1" if night else "")
        black_after = setting_int("nightblack", 30)
        self.setProperty("black", "1" if night and black_after and time.time() - self.started > black_after * 60 else "")

    def run(self):
        self.release_kodi()
        seconds = max(8, ADDON.getSettingInt("seconds") or 18)
        source = ADDON.getSettingInt("source")
        queue = build_queue(source)
        if not queue:
            log("nothing to show")
            self.wait_for_wake()
            return
        random.shuffle(queue)
        extras = (in_progress() if setting_bool("resume", True) else []) + \
            (new_episodes() if setting_bool("newep", True) else [])
        if extras:                          # one of yours after every three others, yours first
            random.shuffle(extras)
            mixed = []
            for n, entry in enumerate(queue):
                if n % 3 == 0 and extras:
                    mixed.append(extras.pop(0))
                mixed.append(entry)
            queue = mixed + extras
        self.tick()
        monitor = xbmc.Monitor()
        slot, index, shown = "a", 0, 0
        while not self.stop and not monitor.abortRequested():
            kind, ref = queue[index % len(queue)]
            index += 1
            try:
                item = ref if kind is None else tmdb_item(kind, ref, where=source == 4)
            except Exception as error:  # noqa: BLE001 - skip this one
                log(f"{kind} {ref}: {error}")
                item = None
                if monitor.waitForAbort(1):
                    break
                if index > len(queue) * 2 and not shown:
                    break
                continue
            if not item:
                continue
            self.show(slot, item)
            shown += 1
            slot = "b" if slot == "a" else "a"
            waited = 0.0
            while waited < seconds and not self.stop and not monitor.abortRequested():
                if monitor.waitForAbort(0.5):
                    break
                waited += 0.5
                self.tick()
        self.wait_for_wake()

    def wait_for_wake(self):
        """1.1.5: never close on our own while Kodi still has the screensaver on. Closing early left Kodi thinking the
        screensaver was on without one on screen: the first button press then did nothing ('Home stuck after the
        screensaver'). Stay (dark) until Kodi switches it off; then onScreensaverDeactivated closes the window."""
        monitor = xbmc.Monitor()
        while not self.stop and not monitor.abortRequested() and (self.own or xbmc.getCondVisibility("System.ScreenSaverActive")):
            if monitor.waitForAbort(0.5):
                break
            self.tick()
        self.exit()


def setting_bool(name, default):
    try:
        return ADDON.getSettingBool(name)
    except Exception:  # noqa: BLE001 - a setting that is not there yet
        return default


def setting_int(name, default):
    try:
        return ADDON.getSettingInt(name)
    except Exception:  # noqa: BLE001
        return default


def can_open():
    """Opening a title's page needs the Lucent skin (its info page); playing and the library work everywhere."""
    return True


def weather_line():
    """'Cloudy · 6°C  ·  tomorrow 9°C / 3°C' from Kodi's own weather (needs a weather add-on), else empty."""
    if not xbmc.getCondVisibility("Weather.IsFetched"):
        return ""
    now = "  ·  ".join(x for x in (xbmc.getInfoLabel("Weather.Conditions"), xbmc.getInfoLabel("Weather.Temperature")) if x)
    high = xbmc.getInfoLabel("Window(weather).Property(Daily.2.HighTemperature)")
    low = xbmc.getInfoLabel("Window(weather).Property(Daily.2.LowTemperature)")
    if high and low:
        now += f"  ·  {text(30041)} {high} / {low}".replace("  ·   ", "  ·  ")
    return now


def open_target(target):
    """What 'Watch' does for the title that was on screen."""
    kind = target[0]
    if kind == "play":
        rpc("Player.Open", {"item": json.loads(target[1]), "options": {"resume": True}})
    elif kind == "videos":
        xbmc.executebuiltin(f'ActivateWindow(Videos,"{target[1]}",return)')
    elif kind == "tmdb" and xbmc.getSkinDir() == "skin.lucent":
        home = xbmcgui.Window(10000)
        home.setProperty("nuvio.open.tmdb", target[2])
        home.setProperty("nuvio.open.type", target[1])
        home.clearProperty("nuvio.open.trakt")
        xbmc.executebuiltin("RunScript(special://skin/scripts/info.py,open,path)")
    elif kind == "tmdb":
        log("open: a title page needs the Lucent skin")


def ask_open(item):
    """1.2.0: Kodi eats the key that wakes the screensaver, so OK on the picture cannot open it. Right after waking up
    a small question asks whether you want to watch what was on screen (closes by itself after 8 seconds)."""
    target = item.get("open") or []
    if not target or (target[0] == "tmdb" and xbmc.getSkinDir() != "skin.lucent"):
        return
    xbmc.Monitor().waitForAbort(0.4)                   # let Kodi put the previous window back first
    label = text(30038) if target[0] == "play" else text(30036)
    try:
        yes = xbmcgui.Dialog().yesno(item.get("title", ""), text(30035), nolabel=text(30037), yeslabel=label,
                                     autoclose=8000, defaultbutton=xbmcgui.DLG_YESNO_YES_BTN)
    except (TypeError, AttributeError):                 # Kodi 19: no defaultbutton yet
        yes = xbmcgui.Dialog().yesno(item.get("title", ""), text(30035), nolabel=text(30037), yeslabel=label, autoclose=8000)
    if yes:
        open_target(target)


# 1.2.5: no key trick any more. 1.2.2-1.2.4 mapped a key to "Mute" while the screensaver ran, to see which key woke
# it (Kodi throws that key away, except mute, volume and power). On a Fire TV with HDMI-CEC the mute went to the
# soundbar, and stayed there. So the question after waking up comes again after every key, as in 1.2.1; "Continue
# watching" is focused, Back or Close takes it away. A keymap left behind by those versions is removed here.
KEYMAP = "special://profile/keymaps/lucent_saver_ok.xml"


def keymap_off():
    if xbmcvfs.exists(KEYMAP):
        xbmcvfs.delete(KEYMAP)
        xbmc.executebuiltin("Action(reloadkeymaps)")


if __name__ == "__main__":
    keymap_off()
    beat = HOME.getProperty("lucent.saver.own")
    if beat and time.time() - float(beat or 0) < 15:
        # 1.2.6: the screensaver is already on screen in its own window; Kodi only started it again because its idle
        # time ran out. Switch Kodi's state off again and leave the picture as it is.
        xbmc.executeJSONRPC(json.dumps({"jsonrpc": "2.0", "id": 1, "method": "Input.ExecuteAction", "params": {"action": "noop"}}))
    else:
        window = Screensaver("screensaver-lucent.xml", PATH, "default", "")
        window.doModal()
        shown, own, choice = window.current, window.own, window.choice
        del window
        log(f"woken up: own={own} choice={choice or 'kodi'}")
        # OK asks whether to watch it; Back and other keys just close. Should the own-keys trick not have worked,
        # Kodi woke it and the question comes after every key, as before.
        if shown and setting_bool("askopen", True) and (choice == "ok" or not own):
            ask_open(shown)
