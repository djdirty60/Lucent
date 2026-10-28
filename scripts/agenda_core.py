# -*- coding: utf-8 -*-
"""Lucent: the calendar of the series and films you follow (data, follow list, pop-up notifications).

The screen itself is scripts/agenda.py; this file holds everything that has no screen:

  follow list     special://profile/addon_data/skin.lucent/agenda_follow.json  (the bell)
  episode cache   special://profile/addon_data/skin.lucent/agenda_cache.json   (6 hours)
  new episode     a pop-up "Watch now / Later", from the background helper (run_service)

Episodes, artwork and plots come from TMDB (the key of Seren, like the info page). The air time
comes from TVmaze (free, no key) when it knows the show; otherwise only the date is known.
"""
import datetime
import json
import time
import urllib.error
import urllib.parse

import xbmc
import xbmcgui
import xbmcvfs

import info  # http() and tmdb() helpers of the info page (same folder)

DATA = "special://profile/addon_data/skin.lucent/"
FOLLOW_PATH = DATA + "agenda_follow.json"
CACHE_PATH = DATA + "agenda_cache.json"
TTL = 6 * 3600              # episode data is refreshed after this many seconds
PAST_DAYS = 45              # how far back the calendar looks
FUTURE_DAYS = 200
IMG = "https://image.tmdb.org/t/p/"
TVMAZE = "https://api.tvmaze.com/"
SEREN = "plugin://plugin.video.seren/"
HOME = xbmcgui.Window(10000)
RUNNING = "nuvio.agenda.service"      # heartbeat of the background helper
HEADING = "Lucent"

_NL = xbmc.getLanguage(xbmc.ISO_639_1) == "nl"
T = {
    "new_ep": ("New episode", "Nieuwe aflevering"),
    "new_movie": ("New film", "Nieuwe film"),
    "ep_out": ("A new episode is out. Do you want to watch it now?", "Er is een nieuwe aflevering. Wil je hem nu kijken?"),
    "movie_out": ("This film is out now. Do you want to watch it?", "Deze film is nu uit. Wil je hem kijken?"),
    "watch_now": ("Watch now", "Nu kijken"),
    "later": ("Later", "Later"),
    "following": ("You now follow {0}. New episodes show up in the calendar.",
                  "Je volgt nu {0}. Nieuwe afleveringen staan in de kalender."),
    "unfollowed": ("You no longer follow {0}", "Je volgt {0} niet meer"),
    "no_id": ("This title has no TMDB number, so it cannot be followed.", "Deze titel heeft geen TMDB-nummer en kan niet gevolgd worden."),
    "failed": ("Could not load the calendar data. Try again later.", "Kalendergegevens laden is niet gelukt. Probeer het later opnieuw."),
    "no_seren": ("Seren is not installed.", "Seren is niet geïnstalleerd."),
    "cinema": ("In cinemas", "In de bioscoop"),
    "cinema_soon": ("Coming to cinemas", "Binnenkort in de bioscoop"),
    "film": ("Film", "Film"),
    "time_unknown": ("Time not known yet", "Tijd nog niet bekend"),
}
WEEKDAYS = {"nl": ["maandag", "dinsdag", "woensdag", "donderdag", "vrijdag", "zaterdag", "zondag"],
            "en": ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]}
WEEKDAYS_SHORT = {"nl": ["ma", "di", "wo", "do", "vr", "za", "zo"], "en": ["Mo", "Tu", "We", "Th", "Fr", "Sa", "Su"]}
MONTHS = {"nl": ["januari", "februari", "maart", "april", "mei", "juni", "juli", "augustus", "september", "oktober",
                 "november", "december"],
          "en": ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October",
                 "November", "December"]}
MONTHS_SHORT = {"nl": ["jan", "feb", "mrt", "apr", "mei", "jun", "jul", "aug", "sep", "okt", "nov", "dec"],
                "en": ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]}
LANG = "nl" if _NL else "en"


def tr(key, *args):
    text = T[key][1 if _NL else 0]
    return text.format(*args) if args else text


def log(text):
    xbmc.log(f"[skin.lucent] agenda: {text}", xbmc.LOGINFO)


# ----------------------------------------------------------------------------- dates
def today():
    return datetime.date.today()


def parse_date(value):
    return datetime.date.fromisoformat(value)


def day_long(d):
    return f"{WEEKDAYS[LANG][d.weekday()]} {d.day} {MONTHS[LANG][d.month - 1]}"


def day_short(d):
    return f"{WEEKDAYS_SHORT[LANG][d.weekday()]} {d.day} {MONTHS_SHORT[LANG][d.month - 1]}"


def month_title(d):
    return f"{MONTHS[LANG][d.month - 1].capitalize()} {d.year}"


def ep_code(ev):
    if ev.get("kind") != "tv":
        return ""
    prefix = "S" if not _NL else "S"
    suffix = "E" if not _NL else "A"
    return f"{prefix}{ev['season']} {suffix}{ev['episode']}"


def number(value):
    text = f"{float(value):.1f}"
    return text.replace(".", ",") if _NL else text


# ----------------------------------------------------------------------------- storage
def read_json(path, default):
    try:
        if not xbmcvfs.exists(path):
            return default
        with xbmcvfs.File(path) as fh:
            raw = fh.read()
        data = json.loads(raw)
        return data if isinstance(data, type(default)) else default
    except Exception as error:  # noqa: BLE001 - a broken file must never break the skin
        log(f"cannot read {path}: {error}")
        return default


def write_json(path, data):
    xbmcvfs.mkdirs(DATA)
    with xbmcvfs.File(path, "w") as fh:
        fh.write(json.dumps(data, ensure_ascii=False))


def load_follow():
    data = read_json(FOLLOW_PATH, {})
    data.setdefault("shows", {})
    data.setdefault("notified", {})
    data.setdefault("snooze", {})
    return data


def load_cache():
    data = read_json(CACHE_PATH, {})
    data.setdefault("shows", {})
    return data


def show_key(kind, tmdb_id):
    return f"{'tv' if kind == 'tv' else 'mv'}:{tmdb_id}"


# ----------------------------------------------------------------------------- what is on screen now
def li(name):
    return xbmc.getInfoLabel(f"ListItem.{name}")


def current_ref():
    """The series / film of the item on the info page, as {kind, tmdb, name}, or None."""
    dbtype = li("DBType")
    if dbtype == "movie":
        kind, tmdb, name = "movie", li("UniqueID(tmdb)") or li("Property(tmdb_id)"), li("Title") or li("Label")
    elif dbtype in ("tvshow", "season", "episode"):
        # for Seren episodes and seasons the tmdb id on the item is the one of the show
        kind = "tv"
        tmdb = li("Property(tvshow.tmdb_id)") or li("UniqueID(tmdb)") or li("Property(tmdb_id)")
        name = li("TVShowTitle") or li("Title") or li("Label")
    else:
        return None
    if not tmdb.isdigit():
        imdb = li("UniqueID(imdb)") or li("IMDBNumber") or li("Property(imdb_id)")
        tmdb = tmdb_from_imdb(imdb, kind)
    if not tmdb:
        return None
    return {"kind": kind, "tmdb": int(tmdb), "name": name}


def tmdb_from_imdb(imdb, kind):
    if not (imdb or "").startswith("tt"):
        return ""
    try:
        found = info.tmdb(f"find/{imdb}", external_source="imdb_id")
    except Exception as error:  # noqa: BLE001
        log(f"find {imdb}: {error}")
        return ""
    results = found.get("movie_results" if kind == "movie" else "tv_results") or []
    return str(results[0]["id"]) if results else ""


# ----------------------------------------------------------------------------- TMDB / TVmaze
def img(path, size):
    return f"{IMG}{size}{path}" if path else ""


def local_stamp(stamp):
    """('2026-10-28', '02:00') in the time zone of this device, from a TVmaze airstamp."""
    when = datetime.datetime.fromisoformat(stamp.replace("Z", "+00:00")).astimezone()
    return when.strftime("%Y-%m-%d"), when.strftime("%H:%M")


def maze_times(tmdb_id, maze_id):
    """({(season, episode): (date, time)}, maze id) - times in local time. Empty when TVmaze does not know the show."""
    if maze_id == -1:
        return {}, -1
    if not maze_id:
        ext = info.tmdb(f"tv/{tmdb_id}/external_ids")
        found = None
        for query in (("imdb", ext.get("imdb_id")), ("thetvdb", ext.get("tvdb_id"))):
            if not query[1]:
                continue
            try:
                found = info.http(f"{TVMAZE}lookup/shows?{query[0]}={query[1]}")
                break
            except urllib.error.HTTPError:
                continue
        if not found:
            return {}, -1
        maze_id = found["id"]
    times = {}
    for ep in info.http(f"{TVMAZE}shows/{maze_id}/episodes") or []:
        if not (ep.get("airtime") and ep.get("airstamp") and ep.get("season") and ep.get("number")):
            continue
        try:
            times[(ep["season"], ep["number"])] = local_stamp(ep["airstamp"])
        except ValueError:
            continue
    return times, maze_id


def tv_events(rec):
    """Events of one followed series (aired recently or still to come) and its TVmaze id."""
    tmdb_id = rec["tmdb"]
    show = info.tmdb(f"tv/{tmdb_id}")
    networks = show.get("networks") or []
    base = {
        "kind": "tv", "show": show_key("tv", tmdb_id), "tmdb": tmdb_id, "name": show.get("name") or rec["name"],
        "poster": img(show.get("poster_path"), "w342"), "backdrop": img(show.get("backdrop_path"), "w1280"),
        "network": networks[0]["name"] if networks else "", "rating": show.get("vote_average") or 0,
        "genre": ", ".join(g["name"] for g in (show.get("genres") or [])[:2]), "show_plot": show.get("overview") or "",
    }
    seasons = {ep["season_number"] for ep in (show.get("last_episode_to_air"), show.get("next_episode_to_air")) if ep}
    if not seasons and show.get("number_of_seasons"):
        seasons.add(show["number_of_seasons"])
    maze, maze_id = {}, rec.get("maze", 0)
    try:
        maze, maze_id = maze_times(tmdb_id, maze_id)
    except Exception as error:  # noqa: BLE001 - times are a bonus
        log(f"tvmaze {tmdb_id}: {error}")
    lo = (today() - datetime.timedelta(days=PAST_DAYS)).isoformat()
    hi = (today() + datetime.timedelta(days=FUTURE_DAYS)).isoformat()
    events = []
    for season in sorted(seasons):
        data = info.tmdb(f"tv/{tmdb_id}/season/{season}")
        for ep in data.get("episodes") or []:
            date, at = ep.get("air_date") or "", ""
            if not date:
                continue
            if (season, ep["episode_number"]) in maze:
                date, at = maze[(season, ep["episode_number"])]
            if not lo <= date <= hi:
                continue
            events.append(dict(base, key=f"tv:{tmdb_id}:S{season}E{ep['episode_number']}", season=season,
                               episode=ep["episode_number"], title=ep.get("name") or "", date=date, time=at,
                               plot=ep.get("overview") or base["show_plot"],
                               still=img(ep.get("still_path"), "w500") or img(show.get("backdrop_path"), "w500"),
                               runtime=ep.get("runtime") or 0))
    return events, maze_id


def movie_events(rec):
    movie = info.tmdb(f"movie/{rec['tmdb']}")
    date = movie.get("release_date") or ""
    if not date:
        return [], 0
    return [{
        "kind": "movie", "show": show_key("movie", rec["tmdb"]), "key": f"mv:{rec['tmdb']}", "tmdb": rec["tmdb"],
        "name": movie.get("title") or rec["name"], "title": "", "season": 0, "episode": 0, "date": date, "time": "",
        "plot": movie.get("overview") or "", "poster": img(movie.get("poster_path"), "w342"),
        "backdrop": img(movie.get("backdrop_path"), "w1280"), "still": img(movie.get("backdrop_path"), "w500"),
        "network": "", "rating": movie.get("vote_average") or 0,
        "genre": ", ".join(g["name"] for g in (movie.get("genres") or [])[:2]), "runtime": movie.get("runtime") or 0,
    }], 0


def fetch(rec):
    return (tv_events if rec["kind"] == "tv" else movie_events)(rec)


# ----------------------------------------------------------------------------- the cache
def refresh(force=False, only=None):
    """Bring the episode cache up to date for the shows you follow. Returns True when something changed."""
    store, cache = load_follow(), load_cache()
    changed = False
    for key in [k for k in cache["shows"] if k not in store["shows"]]:
        del cache["shows"][key]
        changed = True
    for key, rec in store["shows"].items():
        entry = cache["shows"].get(key)
        if only and key != only:
            continue
        if not (force or not entry or time.time() - entry.get("fetched", 0) > TTL):
            continue
        try:
            events, maze = fetch(rec)
        except Exception as error:  # noqa: BLE001 - keep the old data, try again in a while
            log(f"{key}: {error}")
            if not entry:
                cache["shows"][key] = {"fetched": time.time() - TTL + 300, "events": []}
                changed = True
            continue
        cache["shows"][key] = {"fetched": time.time(), "events": events}
        changed = True
        if rec.get("maze") != maze:
            rec["maze"] = maze
            write_json(FOLLOW_PATH, store)
    if changed:
        write_json(CACHE_PATH, cache)
    return changed


def stale():
    store, cache = load_follow(), load_cache()
    return any(time.time() - cache["shows"].get(k, {}).get("fetched", 0) > TTL for k in store["shows"])


def all_events():
    """Every cached event of the followed shows, oldest first, each with a 'notify' flag."""
    store, cache = load_follow(), load_cache()
    out = []
    for key, entry in cache["shows"].items():
        rec = store["shows"].get(key)
        if not rec:
            continue
        for ev in entry.get("events", []):
            out.append(dict(ev, notify=bool(rec.get("notify", True))))
    out.sort(key=lambda e: (e["date"], e["time"] or "99:99", e["name"], e.get("season", 0), e.get("episode", 0)))
    return out


# ----------------------------------------------------------------------------- follow / bell
def is_following(key):
    return key in load_follow()["shows"]


def toggle_follow(ref):
    """Follow the show, or stop following it. Returns True when it is now followed."""
    key = show_key(ref["kind"], ref["tmdb"])
    store = load_follow()
    if key in store["shows"]:
        del store["shows"][key]
        write_json(FOLLOW_PATH, store)
        refresh()
        return False
    store["shows"][key] = {"kind": ref["kind"], "tmdb": ref["tmdb"], "name": ref["name"], "notify": True,
                           "added": today().isoformat(), "maze": 0}
    write_json(FOLLOW_PATH, store)
    refresh(only=key)
    # what has already aired should not pop up as "new"
    store = load_follow()
    for ev in load_cache()["shows"].get(key, {}).get("events", []):
        if ev["date"] <= today().isoformat():
            store["notified"][ev["key"]] = "done"
    write_json(FOLLOW_PATH, store)
    return True


def set_notify(key, on):
    store = load_follow()
    if key in store["shows"]:
        store["shows"][key]["notify"] = bool(on)
        write_json(FOLLOW_PATH, store)


def notifications_enabled():
    return not xbmc.getCondVisibility("Skin.HasSetting(nuvio.agenda.nonotify)")


def unfollow(key):
    store = load_follow()
    if key in store["shows"]:
        del store["shows"][key]
        write_json(FOLLOW_PATH, store)
        refresh()


def state():
    """Set Window(home) nuvio.agenda.followed for the item on the info page (the bell button reads it)."""
    ref = current_ref()
    followed = bool(ref) and is_following(show_key(ref["kind"], ref["tmdb"]))
    if followed:
        HOME.setProperty("nuvio.agenda.followed", "1")
    else:
        HOME.clearProperty("nuvio.agenda.followed")


def follow_button():
    ref = current_ref()
    if not ref:
        xbmcgui.Dialog().notification(HEADING, tr("no_id"), xbmcgui.NOTIFICATION_WARNING, 3000)
        return
    now_following = toggle_follow(ref)
    state()
    xbmcgui.Dialog().notification(HEADING, tr("following" if now_following else "unfollowed", ref["name"]),
                                  xbmcgui.NOTIFICATION_INFO, 4000)


# ----------------------------------------------------------------------------- opening a show in Seren
def open_in_seren(name, kind):
    if not xbmc.getCondVisibility("System.HasAddon(plugin.video.seren)"):
        xbmcgui.Dialog().notification(HEADING, tr("no_seren"), xbmcgui.NOTIFICATION_WARNING, 3000)
        return
    action = "moviesSearchResults" if kind == "movie" else "showsSearchResults"
    xbmc.executebuiltin(f'ActivateWindow(Videos,"{SEREN}?action={action}&action_args={urllib.parse.quote(name)}",return)')


# ----------------------------------------------------------------------------- the pop-up for new episodes
def due_events(now, store, events):
    """Events of followed shows (bell on) that are out now and have not been announced yet."""
    out = []
    for ev in events:
        rec = store["shows"].get(ev["show"])
        if not rec or not rec.get("notify", True) or ev["key"] in store["notified"]:
            continue
        snooze = store["snooze"].get(ev["key"])
        if snooze and snooze[0] > time.time():
            continue
        day = parse_date(ev["date"])
        if day > now.date() or day < now.date() - datetime.timedelta(days=2):
            continue
        if ev["time"]:
            hour, minute = ev["time"].split(":")
            if datetime.datetime.combine(day, datetime.time(int(hour), int(minute))) > now:
                continue
        out.append(ev)
    return out


def busy_now():
    """Do not interrupt a film, the screensaver or another dialog."""
    return xbmc.getCondVisibility("Player.HasMedia | System.ScreenSaverActive | System.HasModalDialog"
                                  " | Window.IsActive(fullscreenvideo)")


def announce(ev):
    """Ask 'Watch now / Later'. Returns True when the user wants to watch."""
    movie = ev["kind"] == "movie"
    code = "" if movie else f" · {ep_code(ev)}" + (f" · {ev['title']}" if ev["title"] else "")
    text = f"[B]{ev['name']}[/B]{code}\n\n{tr('movie_out' if movie else 'ep_out')}"
    return xbmcgui.Dialog().yesno(tr("new_movie" if movie else "new_ep"), text, nolabel=tr("later"), yeslabel=tr("watch_now"))


def check_notifications():
    """One round of the background helper. Returns the number of pop-ups shown."""
    if not notifications_enabled():
        return 0
    store = load_follow()
    if not store["shows"]:
        return 0
    if stale():
        refresh()
    store = load_follow()
    shown = 0
    for ev in due_events(datetime.datetime.now(), store, all_events())[:3]:
        if busy_now():
            break
        shown += 1
        if announce(ev):
            store["notified"][ev["key"]] = "done"
            write_json(FOLLOW_PATH, store)
            open_in_seren(ev["name"], ev["kind"])
            break
        count = (store["snooze"].get(ev["key"]) or [0, 0])[1] + 1
        if count >= 3:
            store["notified"][ev["key"]] = "done"
        else:
            store["snooze"][ev["key"]] = [time.time() + 6 * 3600, count]
        write_json(FOLLOW_PATH, store)
    return shown


def running():
    try:
        return time.time() - float(HOME.getProperty(RUNNING) or 0) < 900
    except ValueError:
        return False


def run_service():
    """Background helper, started from the Home screen (like the trailer helper)."""
    if running():
        return
    monitor = xbmc.Monitor()
    log("service started")
    HOME.setProperty(RUNNING, f"{time.time():.1f}")
    if monitor.waitForAbort(60):      # let Kodi finish starting up first
        return
    while not monitor.abortRequested():
        HOME.setProperty(RUNNING, f"{time.time():.1f}")
        try:
            check_notifications()
        except Exception as error:  # noqa: BLE001 - never die silently in a loop
            log(f"service error: {error}")
        if monitor.waitForAbort(120):
            break
    HOME.clearProperty(RUNNING)
