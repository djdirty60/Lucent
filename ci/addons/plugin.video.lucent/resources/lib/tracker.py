# -*- coding: utf-8 -*-
"""One front for 'the account that remembers what you watched': Trakt, Simkl, or only this device.

Everything else in the add-on talks to this file, so the rest does not care which one is used.
Floppy is separate: it only receives what you watch, next to whichever account is chosen.
"""
from concurrent.futures import ThreadPoolExecutor
import time

import floppy
import mdblist
import simkl
import tmdb
import trakt
import users
import util

T = util.T
SEEN = "watched.json"
LISTED = "watchlist.json"
PROGRESS = "progress.json"


def choice():
    return users.tracker_choice()     # 0 Trakt, 1 Simkl, 2 only this device


def active():
    """The linked account module, or None when working on this device only."""
    mode = choice()
    if mode == 0 and trakt.logged_in():
        return trakt
    if mode == 1 and simkl.logged_in():
        return simkl
    return None


def logged_in():
    return active() is not None


def name():
    return {trakt: "Trakt", simkl: "Simkl"}.get(active(), "")


def user():
    account = active()
    return account.account().get("user", "") if account else ""


def has_lists():
    account = active()
    return bool(account and account.HAS_LISTS)


def forget_lists():
    account = active()
    if account:
        account.forget_lists()
    util.cache_drop("nextup")


# ----------------------------------------------------------------------- this device only
def _local():
    return util.load_json(SEEN, {"movies": {}, "episodes": {}})


def _aired(meta):
    if meta["kind"] == "season":
        numbers = [int(meta["season"])]
    else:
        numbers = [x["season_number"] for x in (tmdb.details("tvshow", meta["tmdb"]) or {}).get("seasons") or []]
    return [(number, e["episode_number"]) for number in numbers
            for e in tmdb.season(meta["tmdb"], number).get("episodes") or [] if tmdb.aired(e.get("air_date"))]


def mark_local(meta, watched):
    data, tmdb_id, now = _local(), str(meta["tmdb"]), time.strftime("%Y-%m-%d %H:%M:%S")
    if meta["kind"] == "movie":
        if watched:
            data["movies"][tmdb_id] = now
        else:
            data["movies"].pop(tmdb_id, None)
    else:
        pairs = [(int(meta["season"]), int(meta["episode"]))] if meta["kind"] == "episode" else _aired(meta)
        episodes = data["episodes"].setdefault(tmdb_id, {})
        for season, episode in pairs:
            key = "%d:%d" % (season, episode)
            if watched:
                episodes[key] = now
            else:
                episodes.pop(key, None)
    util.save_json(SEEN, data)


def _local_paused():
    rows = []
    for key, saved in util.load_json(PROGRESS, {}).items():
        if not saved.get("total"):
            continue
        percent, parts = saved["position"] * 100.0 / saved["total"], key.split(":")
        if parts[0] == "movie":
            rows.append({"type": "movie", "progress": percent, "at": saved.get("at", 0), "movie": {"ids": {"tmdb": int(parts[1])}}})
        else:
            rows.append({"type": "episode", "progress": percent, "at": saved.get("at", 0), "show": {"ids": {"tmdb": int(parts[1])}},
                         "episode": {"season": int(parts[2]), "number": int(parts[3])}})
    return sorted(rows, key=lambda r: r["at"], reverse=True)


def _local_next_up():
    def step(item):
        show, seen = item
        if not seen:
            return None
        season, episode = max(tuple(int(x) for x in key.split(":")) for key in seen)
        try:
            following = tmdb.next_episode(show, season, episode)
        except util.HttpError:
            return None
        return (show, following["season"], following["episode"]) if following else None
    recent = sorted(_local()["episodes"].items(), key=lambda s: max(s[1].values()) if s[1] else "", reverse=True)[:40]
    with ThreadPoolExecutor(max_workers=6) as pool:
        return [r for r in pool.map(step, recent) if r]


# ----------------------------------------------------------------------- the same questions for every account
def refresh():
    """Fetch fresh watched data. False when that failed: then nothing may be reset."""
    account = active()
    return account.refresh() if account else True


def watched_movies():
    account = active()
    return account.watched_movies() if account else _local()["movies"]


def watched_episodes():
    account = active()
    if account:
        return account.watched_episodes()
    return {show: {tuple(int(x) for x in key.split(":")): when for key, when in eps.items()} for show, eps in _local()["episodes"].items()}


def paused():
    account = active()
    return account.paused() if account else _local_paused()


def resume_percent(kind, tmdb_id, season=None, episode=None):
    for item in paused():
        if kind == "movie" and item.get("type") == "movie" and str(item["movie"]["ids"].get("tmdb")) == str(tmdb_id):
            return item.get("progress") or 0
        if kind == "episode" and item.get("type") == "episode" and str(item["show"]["ids"].get("tmdb")) == str(tmdb_id) \
                and item["episode"]["season"] == int(season) and item["episode"]["number"] == int(episode):
            return item.get("progress") or 0
    return 0


def next_up():
    """[(show tmdb id, season, episode)], most recent first."""
    account = active()
    return account.next_up() if account else _local_next_up()


def pairs(name_of_list):
    """[(kind, tmdb id)] for watchlist_movie, watchlist_tv, collection_movie or collection_tv."""
    account = active()
    if account:
        return account.pairs(name_of_list)
    if name_of_list.startswith("watchlist_"):
        wanted = "movie" if name_of_list.endswith("movie") else "tvshow"
        return [(k, i) for k, i in util.load_json(LISTED, []) if k == wanted]
    return []


def custom_lists(kind, query=None):
    account = active()
    return account.custom_lists(kind, query) if account and account.HAS_LISTS else []


def list_pairs(owner, list_id, page, size):
    account = active()
    return account.list_pairs(owner, list_id, page, size) if account and account.HAS_LISTS else []


def set_watched(meta, watched):
    account = active()
    if account:
        account.set_watched(meta, watched)
    else:
        mark_local(meta, watched)
    util.cache_drop("nextup")


def set_watchlist(meta, add):
    account = active()
    if account:
        account.set_watchlist(meta, add)
        return
    entry = [meta["kind"], str(meta["tmdb"])]
    listed = [e for e in util.load_json(LISTED, []) if e != entry]
    util.save_json(LISTED, ([entry] + listed) if add else listed)


def library_list(meta, add):
    """Puts one title in (or takes it out of) what the Kodi library follows: the Trakt collection (or the watchlist or
    a chosen list), the Simkl list, or this device's watchlist."""
    account = active()
    if account:
        account.library_list(meta, add)
    else:
        set_watchlist(meta, add)
    util.cache_drop("nextup")


def library_rows(kind):
    """kind: movies or shows. What belongs in the Kodi library, with title and year."""
    account = active()
    if account:
        return account.library_rows(kind)
    wanted, key = ("movie", "movie") if kind == "movies" else ("tvshow", "show")
    metas = tmdb.many([(k, i) for k, i in util.load_json(LISTED, []) if k == wanted])
    return [{key: {"title": m["title"], "year": m["year"], "ids": {"tmdb": int(m["tmdb"])}}} for m in metas]


def scrobble(state, meta, percent, position=0, total=0):
    account = active()
    if account:
        account.scrobble(state, meta, percent)
    floppy.scrobble(state, meta, position, total)


def enrich(titles):
    """Adds Trakt and MDBList scores where those are available."""
    mdblist.enrich(titles)                  # one request for 50 titles, the Trakt score included
    if active() is trakt:
        trakt.enrich([t for t in titles if "trakt" not in (t.get("scores") or {})])
