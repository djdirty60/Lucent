# -*- coding: utf-8 -*-
"""Lucent: the calendar of the series and films you follow (data, follow list, pop-up notifications).

The screen itself is scripts/agenda.py; this file holds everything that has no screen:

  follow list     special://profile/addon_data/skin.lucent/agenda_follow.json  (what the calendar shows + the bells)
  episode cache   special://profile/addon_data/skin.lucent/agenda_cache.json   (6 hours)
  new episode     a pop-up "Watch now / Later", from the background helper (run_service)

What the calendar shows: the series (still running) of your Trakt collection and the films of your collection /
watchlist that are about to come out; the Trakt login of your video add-on. The bell of a title is OFF
until you switch it on; with the bell on you get a pop-up for a new episode / the digital release of a film.
Episodes, artwork and plots come from TMDB (the key of your video add-on, like the info page). The air time
comes from TVmaze (free, no key) when it knows the show; otherwise only the date is known.
"""
import datetime
import json
import time
import re
import urllib.error
import urllib.parse

import xbmc
import xbmcgui
import xbmcvfs

import info  # http() and tmdb() helpers of the info page (same folder)

DATA = "special://profile/addon_data/skin.lucent/"
FOLLOW_PATH = DATA + "agenda_follow.json"
CACHE_PATH = DATA + "agenda_cache.json"
CACHE_VERSION = 3
SYNC_TTL = 12 * 3600        # the Trakt collection is read again after this many seconds
TTL = 6 * 3600              # episode data is refreshed after this many seconds
PAST_DAYS = 45              # how far back the calendar looks
FUTURE_DAYS = 200
IMG = "https://image.tmdb.org/t/p/"
TVMAZE = "https://api.tvmaze.com/"
HOME = xbmcgui.Window(10000)
HEADING = "Lucent"

_NL = xbmc.getLanguage(xbmc.ISO_639_1) == "nl"
T = {
    "new_ep": ("New episode", "Nieuwe aflevering"),
    "new_movie": ("Film digitally out", "Film digitaal uit"),
    "ep_out": ("A new episode is out. Do you want to watch it now?", "Er is een nieuwe aflevering. Wil je hem nu kijken?"),
    "movie_out": ("This film has a digital release now. Do you want to watch it?", "Deze film is nu digitaal uit. Wil je hem kijken?"),
    "digital": ("Digital release", "Digitale release"),
    "watch_now": ("Watch now", "Nu kijken"),
    "open_show": ("Open series", "Serie openen"),
    "open_movie": ("Open film", "Film openen"),
    "new_season": ("New season", "Nieuw seizoen"),
    "season_line": ("Season {0} · {1} episodes", "Seizoen {0} · {1} afleveringen"),
    "season_out": ("All out today at once", "Vandaag in één keer verschenen"),
    "from_ep": ("From episode {0}", "Vanaf aflevering {0}"),
    "aired_today": ("Aired today at {0}", "Vandaag om {0} uitgezonden"),
    "aired_today_notime": ("Out today", "Vandaag verschenen"),
    "aired_on": ("Out since {0}", "Verschenen op {0}"),
    "later": ("Later", "Later"),
    "following": ("Notification on for {0}. You get a pop-up for a new episode / the digital release.",
                  "Melding aan voor {0}. Je krijgt een pop-up bij een nieuwe aflevering / digitale release."),
    "unfollowed": ("Notification off for {0}", "Melding uit voor {0}"),
    "no_id": ("This title has no TMDB number, so it cannot be followed.", "Deze titel heeft geen TMDB-nummer en kan niet gevolgd worden."),
    "failed": ("Could not load the calendar data. Try again later.", "Kalendergegevens laden is niet gelukt. Probeer het later opnieuw."),
    "no_addon": ("No video add-on to open it with.", "Geen video-add-on om het mee te openen."),
    "cinema": ("In cinemas", "In de bioscoop"),
    "cinema_soon": ("Coming to cinemas", "Binnenkort in de bioscoop"),
    "film": ("Film", "Film"),
    "time_unknown": ("Time not known yet", "Tijd nog niet bekend"),
    "ep_mid": ("Midseason finale", "Midseason-finale"),
    "ep_finale": ("Season finale", "Seizoensfinale"),
    "ep_premiere": ("Season premiere", "Seizoenspremière"),
    "ep_series_premiere": ("Series premiere", "Seriepremière"),
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
    suffix = "E" if not _NL else "A"
    return f"S{ev['season']} {suffix}{ev['episode']}"


def number(value):
    text = f"{float(value):.1f}"
    return text.replace(".", ",") if _NL else text


# ----------------------------------------------------------------------------- storage
def _read_one(path, default):
    if not xbmcvfs.exists(path):
        return None
    with xbmcvfs.File(path) as fh:
        data = json.loads(fh.read())
    return data if isinstance(data, type(default)) else None


def read_json(path, default):
    for candidate in (path, path + ".tmp"):        # .tmp: a write that was cut off (power loss) left the old file broken
        try:
            data = _read_one(candidate, default)
            if data is not None:
                return data
        except Exception as error:  # noqa: BLE001 - a broken file must never break the skin
            log(f"cannot read {candidate}: {error}")
    return default


def write_json(path, data):
    """Write to a temporary file first and only then put it in place, so a cut-off write never empties a list."""
    xbmcvfs.mkdirs(DATA)
    tmp = path + ".tmp"
    with xbmcvfs.File(tmp, "w") as fh:
        ok = fh.write(json.dumps(data, ensure_ascii=False))
    if ok is False:
        raise OSError(f"cannot write {tmp}")
    if xbmcvfs.exists(path):
        xbmcvfs.delete(path)                        # rename does not overwrite on every system
    if not xbmcvfs.rename(tmp, path):
        xbmcvfs.copy(tmp, path)
        xbmcvfs.delete(tmp)


def load_follow():
    data = read_json(FOLLOW_PATH, {})
    data.setdefault("shows", {})
    data.setdefault("notified", {})
    data.setdefault("snooze", {})
    data.setdefault("hidden", [])
    return data


def load_cache():
    data = read_json(CACHE_PATH, {})
    if data.get("v") != CACHE_VERSION:           # older entries lack logos (v2) or episode types (v3): fetch everything again
        data = {"v": CACHE_VERSION}
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
        # for add-on episodes and seasons the tmdb id on the item is the one of the show
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


def pick_logo(data):
    """Best clear logo (Dutch, then English, then any) from a TMDB 'images' block; '' when there is none."""
    logos = [x for x in ((data or {}).get("images") or {}).get("logos") or [] if x.get("file_path")
             and not x["file_path"].lower().endswith(".svg")]
    for lang in ("nl", "en", None):
        for logo in logos:
            if logo.get("iso_639_1") == lang:
                return img(logo["file_path"], "w500")
    return img(logos[0]["file_path"], "w500") if logos else ""


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


_PLACEHOLDER = re.compile(r"^(aflevering|episode)\s*\d+$", re.I)


def placeholder(name):
    """TMDB gives 'Aflevering 6' when an episode has no Dutch title yet."""
    return not name or bool(_PLACEHOLDER.match(name.strip()))


def english(path):
    """2.1.5: the same TMDB page in English, for titles and summaries that have no Dutch text yet (only when needed)."""
    if LANG == "en":
        return {}
    try:
        return info.tmdb(path, language="en-US")
    except Exception as error:  # noqa: BLE001 - the Dutch text (or nothing) stays
        log(f"english {path}: {error}")
        return {}


def tv_events(rec):
    """Events of one followed series (aired recently or still to come) and its TVmaze id."""
    tmdb_id = rec["tmdb"]
    show = info.tmdb(f"tv/{tmdb_id}", append_to_response="images", include_image_language="nl,en,null")
    networks = show.get("networks") or []
    if not show.get("overview"):
        show["overview"] = english(f"tv/{tmdb_id}").get("overview") or ""
    base = {
        "kind": "tv", "show": show_key("tv", tmdb_id), "tmdb": tmdb_id, "name": show.get("name") or rec["name"],
        "poster": img(show.get("poster_path"), "w342"), "backdrop": img(show.get("backdrop_path"), "w1280"),
        "logo": pick_logo(show), "network": networks[0]["name"] if networks else "", "rating": show.get("vote_average") or 0,
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
        eps = data.get("episodes") or []
        if any(placeholder(ep.get("name")) or not ep.get("overview") for ep in eps if lo <= (ep.get("air_date") or "") <= hi):
            en = {ep["episode_number"]: ep for ep in english(f"tv/{tmdb_id}/season/{season}").get("episodes") or []}
            for ep in eps:
                other = en.get(ep["episode_number"]) or {}
                if placeholder(ep.get("name")) and other.get("name") and not placeholder(other["name"]):
                    ep["name"] = other["name"]
                if not ep.get("overview"):
                    ep["overview"] = other.get("overview") or ""
        for ep in eps:
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
                               runtime=ep.get("runtime") or 0, ep_type=ep.get("episode_type") or ""))
    return events, maze_id


def digital_date(tmdb_id):
    """Date of the digital release (TMDB type 4) of a film: the Netherlands first, then the US, then the earliest."""
    data = info.tmdb(f"movie/{tmdb_id}/release_dates")
    found = {}
    for country in data.get("results") or []:
        dates = [r["release_date"][:10] for r in country.get("release_dates") or [] if r.get("type") == 4 and r.get("release_date")]
        if dates:
            found[country["iso_3166_1"]] = min(dates)
    for code in ("NL", "US", "GB"):
        if code in found:
            return found[code]
    return min(found.values()) if found else ""


def movie_events(rec):
    movie = info.tmdb(f"movie/{rec['tmdb']}", append_to_response="images", include_image_language="nl,en,null")
    if not movie.get("overview"):
        movie["overview"] = english(f"movie/{rec['tmdb']}").get("overview") or ""
    theatrical = movie.get("release_date") or ""
    digital = ""
    try:
        digital = digital_date(rec["tmdb"])
    except Exception as error:  # noqa: BLE001 - the cinema date is a fallback
        log(f"release dates {rec['tmdb']}: {error}")
    date = digital or theatrical
    if not date:
        return [], 0
    return [{
        "kind": "movie", "show": show_key("movie", rec["tmdb"]), "key": f"mv:{rec['tmdb']}", "tmdb": rec["tmdb"],
        "name": movie.get("title") or rec["name"], "title": "", "season": 0, "episode": 0, "date": date, "time": "",
        "digital": bool(digital), "theatrical": theatrical, "logo": pick_logo(movie),
        "plot": movie.get("overview") or "", "poster": img(movie.get("poster_path"), "w342"),
        "backdrop": img(movie.get("backdrop_path"), "w1280"), "still": img(movie.get("backdrop_path"), "w500"),
        "network": "", "rating": movie.get("vote_average") or 0,
        "genre": ", ".join(g["name"] for g in (movie.get("genres") or [])[:2]), "runtime": movie.get("runtime") or 0,
    }], 0


def fetch(rec):
    return (tv_events if rec["kind"] == "tv" else movie_events)(rec)


# ----------------------------------------------------------------------------- your Trakt collection
RUNNING_STATUS_SKIP = ("ended", "canceled", "cancelled")
FILM_LOOKBACK = 120         # films released in the cinema this many days ago can still get a digital release


def wanted_from_trakt():
    """{key: {kind, tmdb, name}} of what the calendar should show, read from Trakt. None when Trakt cannot be used."""
    if not info.trakt_available():
        return None
    trakt = info.Trakt()
    if not trakt.token:
        return None
    wanted = {}
    for entry in trakt.get("sync/collection/shows?extended=full,noseasons") or []:
        show = entry.get("show") or {}
        tmdb = (show.get("ids") or {}).get("tmdb")
        if tmdb and (show.get("status") or "").lower() not in RUNNING_STATUS_SKIP:
            wanted[show_key("tv", tmdb)] = {"kind": "tv", "tmdb": int(tmdb), "name": show.get("title") or "",
                                            "trakt": (show.get("ids") or {}).get("trakt") or 0}
    lo = (today() - datetime.timedelta(days=FILM_LOOKBACK)).isoformat()
    for path in ("sync/collection/movies", "sync/watchlist/movies"):
        for entry in trakt.get(path + "?extended=full") or []:
            movie = entry.get("movie") or {}
            tmdb = (movie.get("ids") or {}).get("tmdb")
            released = movie.get("released") or ""
            if tmdb and released >= lo:
                wanted[show_key("movie", tmdb)] = {"kind": "movie", "tmdb": int(tmdb), "name": movie.get("title") or ""}
    return wanted


def sync_trakt(force=False):
    """Make the calendar follow your Trakt collection. New titles start with the bell OFF. Returns True when it changed."""
    store = load_follow()
    if not force and time.time() - store.get("synced", 0) < SYNC_TTL:
        return False
    try:
        wanted = wanted_from_trakt()
    except Exception as error:  # noqa: BLE001 - no network / token expired: keep what we have
        log(f"trakt sync: {error}")
        store["synced"] = time.time() - SYNC_TTL + 900          # try again in 15 minutes
        write_json(FOLLOW_PATH, store)
        return False
    if wanted is None:
        return False
    changed = False
    for key, rec in wanted.items():
        if key in store["shows"] or key in store["hidden"]:
            continue
        store["shows"][key] = dict(rec, notify=False, source="trakt", added=today().isoformat(), maze=0)
        changed = True
    for key in [k for k, r in store["shows"].items() if r.get("source") == "trakt" and k not in wanted]:
        del store["shows"][key]
        changed = True
    store["synced"] = time.time()
    write_json(FOLLOW_PATH, store)
    return changed


# ----------------------------------------------------------------------------- the cache
def refresh(force=False, only=None, limit=None):
    """Bring the episode cache up to date for the shows in the calendar. Returns True when something changed.

    limit: ask the internet for at most this many shows (the oldest first); the background helper uses a few per
    round so it never sits for minutes on a long list."""
    if not only:
        try:
            sync_trakt(force)
        except Exception as error:  # noqa: BLE001
            log(f"sync: {error}")
    store, cache = load_follow(), load_cache()
    changed = False
    for key in [k for k in cache["shows"] if k not in store["shows"]]:
        del cache["shows"][key]
        changed = True
    asked = 0
    for key in sorted(store["shows"], key=lambda k: cache["shows"].get(k, {}).get("fetched", 0)):
        rec = store["shows"][key]
        entry = cache["shows"].get(key)
        if only and key != only:
            continue
        if not (force or not entry or time.time() - entry.get("fetched", 0) > TTL):
            continue
        if limit and asked >= limit:
            break
        asked += 1
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
    if time.time() - store.get("synced", 0) > SYNC_TTL:
        return True
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
            out.append(dict(ev, notify=bool(rec.get("notify", False))))
    out.sort(key=lambda e: (e["date"], e["time"] or "99:99", e["name"], e.get("season", 0), e.get("episode", 0)))
    return out


# ----------------------------------------------------------------------------- follow / bell
def is_following(key):
    """Is the bell (notification) on for this title?"""
    rec = load_follow()["shows"].get(key)
    return bool(rec and rec.get("notify"))


def mark_past_done(key):
    """What is already out must not pop up as 'new' when the bell is switched on."""
    now = datetime.datetime.now()
    store = load_follow()
    for ev in load_cache()["shows"].get(key, {}).get("events", []):
        out = ev["date"] < today().isoformat() or (ev["date"] == today().isoformat() and (not ev["time"] or ev["time"] <= now.strftime("%H:%M")))
        if out:
            store["notified"][ev["key"]] = "done"
    write_json(FOLLOW_PATH, store)


def toggle_follow(ref):
    """Switch the bell of a title on or off (adding the title to the calendar when it is not there yet).
    Returns True when the bell is now on."""
    key = show_key(ref["kind"], ref["tmdb"])
    store = load_follow()
    rec = store["shows"].get(key)
    if rec:
        now_on = not rec.get("notify")
        set_notify(key, now_on)
        return now_on
    if key in store["hidden"]:
        store["hidden"].remove(key)
    store["shows"][key] = {"kind": ref["kind"], "tmdb": ref["tmdb"], "name": ref["name"], "notify": True,
                           "source": "manual", "added": today().isoformat(), "maze": 0}
    write_json(FOLLOW_PATH, store)
    refresh(only=key)
    mark_past_done(key)
    return True


def set_notify(key, on):
    store = load_follow()
    if key in store["shows"]:
        store["shows"][key]["notify"] = bool(on)
        write_json(FOLLOW_PATH, store)
        if on:
            mark_past_done(key)


def notifications_enabled():
    return not xbmc.getCondVisibility("Skin.HasSetting(nuvio.agenda.nonotify)")


def unfollow(key):
    """Take a title out of the calendar (a Trakt title stays away until you switch its bell on from the info page)."""
    store = load_follow()
    rec = store["shows"].pop(key, None)
    if rec:
        if rec.get("source") == "trakt" and key not in store["hidden"]:
            store["hidden"].append(key)
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


def season_page_ref():
    """The series of Lucent's season page (view 56): from the Kodi library (its ids) or from the add-on item itself."""
    dbid = next((v for v in (xbmc.getInfoLabel(f"Container(56).{n}.TvShowDBID") for n in ("ListItem", "ListItemAbsolute(1)", "ListItemAbsolute(0)"))
                 if v.isdigit()), "")                  # the cursor may be on '..' (no series of its own)
    if dbid.isdigit():
        res = json.loads(xbmc.executeJSONRPC(json.dumps({"jsonrpc": "2.0", "id": 1, "method": "VideoLibrary.GetTVShowDetails",
                                                         "params": {"tvshowid": int(dbid), "properties": ["uniqueid", "title"]}})))
        show = (res.get("result") or {}).get("tvshowdetails") or {}
        ids = show.get("uniqueid") or {}
        tmdb = str(ids.get("tmdb") or "")
        if not tmdb.isdigit():
            tmdb = tmdb_from_imdb(str(ids.get("imdb") or ""), "tv")
        if tmdb:
            return {"kind": "tv", "tmdb": int(tmdb), "name": show.get("title") or xbmc.getInfoLabel("Container.ShowTitle")}
        return None
    return current_ref()


def season_state():
    """Window(home) lucent.s56.bell = 1 when the bell of this series is on (the button on the season page reads it;
    the season page sets it again whenever it gets the focus, so another series never shows an old state)."""
    ref = season_page_ref()
    if ref and is_following(show_key(ref["kind"], ref["tmdb"])):
        HOME.setProperty("lucent.s56.bell", "1")
    else:
        HOME.clearProperty("lucent.s56.bell")
    season_status(ref)


SHOW_STATUS = {"ended": "Ended", "returning series": "Continuing", "canceled": "Cancelled", "cancelled": "Cancelled",
               "in production": "In production", "planned": "In production", "pilot": "In production"}


def season_status(ref):
    """Window(home) lucent.s56.status = Ended / Continuing / Cancelled / In production for the series on the season page.
    Many season lists (add-ons, the Kodi library) do not pass the status of the series; TMDB does. Remembered per series."""
    if not ref or ref.get("kind") != "tv":
        HOME.clearProperty("lucent.s56.status")
        return
    key = "lucent.s56.status.%s" % ref["tmdb"]
    status = HOME.getProperty(key)
    if not status:
        try:
            status = SHOW_STATUS.get(str((info.tmdb(f"tv/{ref['tmdb']}") or {}).get("status") or "").strip().lower(), "-")
        except Exception as error:  # noqa: BLE001 - no key or no network: just no label
            log(f"status: {error}")
            status = ""
        if status:
            HOME.setProperty(key, status)
    HOME.setProperty("lucent.s56.status", "" if status == "-" else status)


def season_follow():
    ref = season_page_ref()
    if not ref:
        xbmcgui.Dialog().notification(HEADING, tr("no_id"), xbmcgui.NOTIFICATION_WARNING, 3000)
        return
    now_following = toggle_follow(ref)
    season_state()
    xbmcgui.Dialog().notification(HEADING, tr("following" if now_following else "unfollowed", ref["name"]),
                                  xbmcgui.NOTIFICATION_INFO, 4000)
    xbmc.sleep(150)
    if xbmc.getCondVisibility("Control.IsVisible(5614) + !Control.HasFocus(5614)"):
        xbmc.executebuiltin("SetFocus(5614)")      # keep the cursor on the button (only while the season page is there)


def follow_button():
    ref = current_ref()
    if not ref:
        xbmcgui.Dialog().notification(HEADING, tr("no_id"), xbmcgui.NOTIFICATION_WARNING, 3000)
        return
    now_following = toggle_follow(ref)
    state()
    xbmcgui.Dialog().notification(HEADING, tr("following" if now_following else "unfollowed", ref["name"]),
                                  xbmcgui.NOTIFICATION_INFO, 4000)


# ----------------------------------------------------------------------------- opening a title
def open_title(name, kind, tmdb=None):
    """Opens the title in your video add-on: the seasons of a series, or the film."""
    if tmdb and info.lv_open_with():
        url = info.lv_play_url(kind, tmdb)
        xbmc.executebuiltin(f"PlayMedia({url})" if kind == "movie" else f'ActivateWindow(Videos,"{url}",return)')
        return
    xbmcgui.Dialog().notification(HEADING, tr("no_addon"), xbmcgui.NOTIFICATION_WARNING, 3000)


# ----------------------------------------------------------------------------- the pop-up for new episodes
def due_events(now, store, events):
    """Events of followed shows (bell on) that are out now and have not been announced yet."""
    out = []
    for ev in events:
        rec = store["shows"].get(ev["show"])
        if not rec or ev["key"] in store["notified"]:
            continue
        films_auto = ev["kind"] == "movie" and rec.get("source") == "trakt" \
            and not xbmc.getCondVisibility("Skin.HasSetting(lucent.films.notify.off)")
        if not rec.get("notify", False) and not films_auto:
            continue
        if ev["kind"] == "movie" and not ev.get("digital"):
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


def providers_line(tmdb_id):
    """'Watch on Netflix, Videoland' for a film (TMDB / JustWatch), '' when unknown."""
    if not tmdb_id:
        return ""
    try:
        result = (info.tmdb(f"movie/{tmdb_id}/watch/providers").get("results") or {}).get(info._region()) or {}
    except Exception as error:  # noqa: BLE001
        log(f"providers: {error}")
        return ""
    names = []
    for group in ("flatrate", "free", "ads", "rent"):
        for p in sorted(result.get(group) or [], key=lambda p: p.get("display_priority", 99)):
            if p.get("provider_name") and p["provider_name"] not in names:
                names.append(p["provider_name"])
    if not names:
        return ""
    return ("Te zien op " if _NL else "Watch on ") + ", ".join(names[:3])


class Announce(xbmcgui.WindowXMLDialog):
    """2.1.8: the pop-up with the poster (xml/Lucent_NewEpisode.xml). choice: 'watch', 'open' or '' (later)."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args)
        self.props, self.choice, self.closed = kwargs["props"], "", False

    def onInit(self):
        for key, value in self.props.items():
            self.setProperty(f"ne.{key}", value)
        self.setFocusId(10)
        import threading
        threading.Thread(target=self._timeout, daemon=True).start()

    def _timeout(self):
        if not xbmc.Monitor().waitForAbort(60) and not self.closed:     # no answer within a minute: later
            self.close()

    def onClick(self, control_id):
        self.choice = {10: "watch", 11: "open"}.get(control_id, "")
        self.closed = True
        self.close()

    def onAction(self, action):
        if action.getId() in (9, 10, 92, 216, 247, 257, 275, 61467, 61448):
            self.closed = True
            self.close()


def when_text(ev):
    day = parse_date(ev["date"])
    if day == today():
        return tr("aired_today", ev["time"]) if ev["time"] else tr("aired_today_notime")
    return tr("aired_on", day_long(day))


def announce(ev, group=None):
    """Ask 'Watch now / Open / Later' for one episode or film, or for a whole season out at once (group = its episodes).
    Returns 'watch', 'open' or '' (later)."""
    movie = ev["kind"] == "movie"
    if group:
        first = min(group, key=lambda e: e["episode"])
        props = {"head": tr("new_season"), "line": tr("season_line", first["season"], len(group)), "when": tr("season_out"),
                 "watch": tr("from_ep", first["episode"]), "open": tr("open_show")}
    elif movie:
        props = {"head": tr("new_movie"), "line": providers_line(ev.get("tmdb")) or tr("digital"), "when": when_text(ev),
                 "watch": tr("watch_now"), "open": tr("open_movie")}
    else:
        props = {"head": tr("new_ep"), "line": f"{ep_code(ev)} · {ev['title']}" if ev["title"] else ep_code(ev),
                 "when": when_text(ev), "watch": tr("watch_now"), "open": tr("open_show")}
    props.update(title=ev["name"], poster=ev.get("poster") or "", later=tr("later"))
    try:
        import xbmcaddon
        path = xbmcaddon.Addon("skin.lucent").getAddonInfo("path")
        window = Announce("Lucent_NewEpisode.xml", path, "Default", "1080i", props=props)
        window.doModal()
        choice = window.choice
        del window
        return choice
    except Exception as error:  # noqa: BLE001 - fall back to Kodi's own question
        log(f"announce window: {error}")
        text = f"[B]{ev['name']}[/B] · {props['line']}\n\n{props['when']}"
        return "watch" if xbmcgui.Dialog().yesno(props["head"], text, nolabel=tr("later"), yeslabel=props["watch"],
                                                 autoclose=60000) else ""


def watch(ev, group=None):
    """Play the episode (the first of a new season), the film, or open it when nothing can play an episode."""
    if ev["kind"] == "tv" and ev.get("tmdb") and info.lv_open_with():
        first = min(group, key=lambda e: e["episode"]) if group else ev
        xbmc.executebuiltin(f"PlayMedia({info.episode_play_url(ev['tmdb'], first['season'], first['episode'])})")
        return
    open_title(ev["name"], ev["kind"], ev["tmdb"])


def already_watched(ev):
    """True when you already saw this episode / film in the Kodi library. Then there is no pop-up for it (you may
    have watched it elsewhere, or right after it came out)."""
    tmdb, season, number = ev.get("tmdb"), ev.get("season") or 0, ev.get("episode") or 0
    if not tmdb:
        return False
    movie = ev["kind"] == "movie"
    try:
        def rpc(method, params):
            res = json.loads(xbmc.executeJSONRPC(json.dumps({"jsonrpc": "2.0", "id": 1, "method": method, "params": params})))
            return res.get("result") or {}
        if movie:
            for m in rpc("VideoLibrary.GetMovies", {"properties": ["uniqueid", "playcount"]}).get("movies") or []:
                if str((m.get("uniqueid") or {}).get("tmdb")) == str(tmdb) and (m.get("playcount") or 0) > 0:
                    return True
            return False
        for show in rpc("VideoLibrary.GetTVShows", {"properties": ["uniqueid"]}).get("tvshows") or []:
            if str((show.get("uniqueid") or {}).get("tmdb")) == str(tmdb):
                eps = rpc("VideoLibrary.GetEpisodes", {"tvshowid": show["tvshowid"], "season": int(season),
                                                       "properties": ["episode", "playcount"]}).get("episodes") or []
                if any(e.get("episode") == int(number) and (e.get("playcount") or 0) > 0 for e in eps):
                    return True
    except Exception as error:  # noqa: BLE001
        log(f"watched (library): {error}")
    return False


def check_notifications():
    """One round of the background helper. Returns the number of pop-ups shown."""
    if not notifications_enabled():
        return 0
    try:
        sync_trakt()                                # has its own wait time; also works before anything is followed
    except Exception as error:  # noqa: BLE001
        log(f"sync: {error}")
    store = load_follow()
    if not store["shows"]:
        return 0
    if stale():
        refresh(limit=5)
    store = load_follow()
    shown = 0
    due = []
    for ev in due_events(datetime.datetime.now(), store, all_events()):
        if already_watched(ev):                     # seen already: no pop-up, now or later
            store["notified"][ev["key"]] = "done"
            write_json(FOLLOW_PATH, store)
            continue
        due.append(ev)
    # 2.1.8: several episodes of one season out on the same day (a whole season at once): one pop-up for that season
    groups, order = {}, []
    for ev in due:
        key = (ev["show"], ev.get("season"), ev["date"]) if ev["kind"] == "tv" else (ev["key"],)
        if key not in groups:
            groups[key] = []
            order.append(key)
        groups[key].append(ev)
    for key in order[:3]:
        if busy_now():
            break
        group = groups[key]
        season = group if len(group) >= 3 else None
        evs = group if season else group[:1]
        ev = min(evs, key=lambda e: e.get("episode") or 0)
        shown += 1
        choice = announce(ev, season)
        if choice:
            for one in evs:
                store["notified"][one["key"]] = "done"
            write_json(FOLLOW_PATH, store)
            if choice == "watch":
                watch(ev, season)
            else:
                open_title(ev["name"], ev["kind"], ev["tmdb"])
            break
        for one in evs:
            count = (store["snooze"].get(one["key"]) or [0, 0])[1] + 1
            if count >= 3:
                store["notified"][one["key"]] = "done"
            else:
                store["snooze"][one["key"]] = [time.time() + 6 * 3600, count]
        write_json(FOLLOW_PATH, store)
    return shown
