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


def _tmdb_count(tmdb_id, season):
    key = f"tmdb:{tmdb_id}:{season}"
    if key not in COUNTS:
        try:
            import info
            data = info.tmdb(f"tv/{tmdb_id}/season/{season}") if info.tmdb_key() else {}
            eps = [e["episode_number"] for e in data.get("episodes") or [] if e.get("episode_number")]
            COUNTS[key] = max(eps, default=0)      # an episode without an air date yet still counts (the finale is known early)
        except Exception as error:  # noqa: BLE001
            log(f"tmdb {tmdb_id} S{season}: {error}")
            return 0
    return COUNTS[key]


def _fill(ident, season, episode, own_count, show_dbid, tmdb_id):
    try:
        count = own_count or (_library_count(show_dbid, season) if show_dbid else 0) or \
            (_tmdb_count(tmdb_id, season) if tmdb_id else 0)
        if STATE["id"] != ident:
            return
        left = count - episode if count >= episode else -1
        if left > 1:
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
    ident = f"{show_dbid or tmdb_id or label(pre + 'TVShowTitle')}:{season}:{episode}"
    now = time.time()
    if ident != STATE["id"]:
        STATE["id"], STATE["since"], STATE["done"] = ident, now, ""
        clear()
        return
    if STATE["done"] == ident or STATE["busy"] or now - STATE["since"] < 0.4:
        return
    STATE["busy"] = True
    threading.Thread(target=_fill, args=(ident, season, episode, own_count, show_dbid, tmdb_id), daemon=True).start()
