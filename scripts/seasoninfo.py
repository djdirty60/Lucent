# -*- coding: utf-8 -*-
"""Lucent 2.1.3: for the episode under the cursor in a Home row, how many episodes of its season are left, and whether
it is the season premiere or the season finale (idea from Reddit, Nov 2026).

Window(home).Property:
  lucent.ep.left   'Nog 6 afleveringen in seizoen 7' / 'Laatste aflevering van seizoen 7' (empty when unknown)
  lucent.ep.badge  'premiere' / 'finale' / ''
How many episodes a season has: the video add-on's own property (lucent.season.count) when it gives one, else the Kodi
library (a library episode), else TMDB (with the series' TMDB id). Remembered per season for this session.
"""
import json
import threading
import time

import xbmc
import xbmcgui

HOME = xbmcgui.Window(10000)
NL = xbmc.getLanguage(xbmc.ISO_639_1) == "nl"
STATE = {"id": "", "since": 0.0, "done": "", "busy": False}
COUNTS = {}                                         # 'db:12:3' / 'tmdb:1399:3' -> episodes in that season


def t(en, nl):
    return nl if NL else en


def log(text):
    xbmc.log(f"[skin.lucent] seasoninfo: {text}", xbmc.LOGINFO)


def clear():
    if HOME.getProperty("lucent.ep.for"):
        for p in ("left", "badge", "for"):
            HOME.clearProperty("lucent.ep." + p)


def _iso(text):
    """Kodi's date label (in the date format of your region) -> 'YYYY-MM-DD' when it can be read, else ''."""
    import re
    text = (text or "").strip()
    m = re.match(r"(\d{4})-(\d{2})-(\d{2})", text)
    if m:
        return m.group(0)
    m = re.match(r"(\d{1,2})[-/.](\d{1,2})[-/.](\d{4})", text)
    if m:
        a, b, y = int(m.group(1)), int(m.group(2)), m.group(3)
        order = xbmc.getRegion("dateshort").lower()
        month, day = (a, b) if order.find("m") < order.find("d") else (b, a)
        return f"{y}-{month:02d}-{day:02d}"
    return ""


def _int(text):
    try:
        return int(str(text).strip())
    except (TypeError, ValueError):
        return 0


def _library_count(show_dbid, season):
    key = f"db:{show_dbid}:{season}"
    if key not in COUNTS:
        req = {"jsonrpc": "2.0", "id": 1, "method": "VideoLibrary.GetEpisodes",
               "params": {"tvshowid": int(show_dbid), "season": int(season), "properties": ["episode"]}}
        res = json.loads(xbmc.executeJSONRPC(json.dumps(req))).get("result") or {}
        eps = [e.get("episode") or 0 for e in res.get("episodes") or []]
        COUNTS[key] = max(eps) if eps else 0
    return COUNTS[key]


SHOWS = {}                                          # series title -> TMDB id (searched once per session)


def show_by_title(title, season=0, episode=0, aired=""):
    """2.1.12 (#19): add-ons like TMDb Movies give an episode without the series' TMDB number. Find it by the series
    title. 2.1.13: several series share a name (Millennium 1996 and 2010), so the one is taken whose season has this
    episode on the same air date; else the series that started closest before that date. '' when not found."""
    title = (title or "").strip()
    if not title:
        return ""
    key = f"{title}|{aired[:4]}"
    if key not in SHOWS:
        try:
            import info
            res = (info.tmdb("search/tv", query=title) if info.tmdb_key() else {}).get("results") or []
            names = [r for r in res if title.lower() in ((r.get("name") or "").lower(), (r.get("original_name") or "").lower())]
            pool = names or res[:5]
            pick = None
            if aired and season and episode:
                for r in pool[:4]:                          # the episode's air date decides
                    try:
                        data = info.tmdb(f"tv/{r['id']}/season/{season}")
                    except Exception:  # noqa: BLE001
                        continue
                    ep = next((e for e in data.get("episodes") or [] if e.get("episode_number") == episode), None)
                    if ep and (ep.get("air_date") or "")[:10] == aired[:10]:
                        pick = r
                        break
            if not pick and aired:                          # else: started closest before the episode
                before = [r for r in pool if r.get("first_air_date") and r["first_air_date"] <= aired[:10]]
                pick = max(before, key=lambda r: r["first_air_date"]) if before else None
            pick = pick or (pool[:1] or [None])[0]
            SHOWS[key] = str(pick["id"]) if pick else ""
        except Exception as error:  # noqa: BLE001 - offline: try again next time
            log(f"search {title}: {error}")
            return ""
    return SHOWS[key]


def _tmdb_count(tmdb_id, season):
    """(episodes in the season, episodes out by today) from TMDB; an announced episode without an air date counts in
    the first number only. 2.1.10: 'Nog 2 afleveringen' was wrong when those two were not out yet."""
    key = f"tmdb:{tmdb_id}:{season}"
    if key not in COUNTS:
        try:
            import datetime
            import info
            data = info.tmdb(f"tv/{tmdb_id}/season/{season}") if info.tmdb_key() else {}
            eps = [e for e in data.get("episodes") or [] if e.get("episode_number")]
            today = datetime.date.today().isoformat()
            out = [e["episode_number"] for e in eps if e.get("air_date") and e["air_date"] <= today]
            COUNTS[key] = (max((e["episode_number"] for e in eps), default=0), max(out, default=0))
        except Exception as error:  # noqa: BLE001
            log(f"tmdb {tmdb_id} S{season}: {error}")
            return 0, 0
    return COUNTS[key]


def _fill(ident, season, episode, own_count, show_dbid, tmdb_id, own_left=0, title="", aired=""):
    try:
        if not (own_count or show_dbid or tmdb_id) and title:
            tmdb_id = show_by_title(title, season, episode, aired)
        # the video add-on gives the season's episodes (also announced ones) and how many after this one are out
        out = episode + own_left if own_count else 0
        count = own_count or (_library_count(show_dbid, season) if show_dbid else 0)
        if not count and tmdb_id:
            count, out = _tmdb_count(tmdb_id, season)
        if STATE["id"] != ident:
            return
        left = count - episode if count >= episode else -1
        aired = out - episode if out >= episode else 0          # of those, already out (TMDB only)
        if (own_count or tmdb_id) and not show_dbid and left > 0 and aired < left:
            if aired > 0:
                text = t(f"{aired} more out now, {left - aired} still to come", f"Nog {aired} te zien, {left - aired} komen nog")
            else:
                text = t(f"Newest episode · {left} still to come", f"Nieuwste aflevering · nog {left} op komst")
        elif left > 1:
            text = t(f"{left} episodes left in season {season}", f"Nog {left} afleveringen in seizoen {season}")
        elif left == 1:
            text = t(f"1 episode left in season {season}", f"Nog 1 aflevering in seizoen {season}")
        elif left == 0:
            text = t(f"Last episode of season {season}", f"Laatste aflevering van seizoen {season}")
        else:
            text = ""
        badge = "finale" if left == 0 and count > 1 else "premiere" if episode == 1 else ""
        for p, v in (("left", text), ("badge", badge)):
            if v:
                HOME.setProperty("lucent.ep." + p, v)
            else:
                HOME.clearProperty("lucent.ep." + p)
        HOME.setProperty("lucent.ep.for", ident)
        STATE["done"] = ident
    except Exception as error:  # noqa: BLE001
        log(f"fill: {error}")
    finally:
        STATE["busy"] = False


def tick():
    if not xbmc.getCondVisibility("Window.IsActive(home)"):
        STATE["id"] = STATE["done"] = ""
        clear()
        return
    row = HOME.getProperty("nuvio.row")
    pre = f"Container({row}).ListItem."
    label = xbmc.getInfoLabel
    if not row.isdigit() or label(pre + "DBType") != "episode":
        STATE["id"] = STATE["done"] = ""
        clear()
        return
    season, episode = _int(label(pre + "Season")), _int(label(pre + "Episode"))
    if season < 1 or episode < 1:
        STATE["id"] = ""
        clear()
        return
    show_dbid = label(pre + "TvShowDBID")
    show_dbid = show_dbid if show_dbid.isdigit() and label(pre + "DBID").isdigit() else ""
    tmdb_id = label(pre + "Property(tvshow.tmdb_id)") or label(pre + "UniqueID(tmdbshow)")
    tmdb_id = tmdb_id if tmdb_id.isdigit() else ""
    own_count = _int(label(pre + "Property(lucent.season.count)"))
    own_left = _int("".join(c for c in label(pre + "Property(lucent.season.left)") if c.isdigit()) or 0)
    title = label(pre + "TVShowTitle")
    aired = _iso(label(pre + "Premiered") or label(pre + "Date"))
    ident = f"{show_dbid or tmdb_id or title}:{season}:{episode}"
    now = time.time()
    if ident != STATE["id"]:
        STATE["id"], STATE["since"], STATE["done"] = ident, now, ""
        clear()
        return
    if STATE["done"] == ident or STATE["busy"] or now - STATE["since"] < 0.4:
        return
    STATE["busy"] = True
    threading.Thread(target=_fill, args=(ident, season, episode, own_count, show_dbid, tmdb_id, own_left, title, aired), daemon=True).start()
