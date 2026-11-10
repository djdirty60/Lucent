# -*- coding: utf-8 -*-
"""Simkl account. Like Trakt, but its lists are watch states and it wants as few big requests as possible."""
from concurrent.futures import ThreadPoolExecutor
import os
import re
import threading
import time
import urllib.parse

import xbmc
import xbmcgui

import apikeys
import tmdb
import util

API = "https://api.simkl.com/"
FILE = "simkl.json"
STATE = "simkl_state.json"
HAS_LISTS = False
AGENT = "lucent-video/0.4"
CHECK_EVERY = 300


def client():
    return apikeys.simkl_id()


def account():
    return util.load_json(FILE, {})


def logged_in():
    return bool(account().get("access_token"))


def _store(token):
    token["expires_at"] = time.time() + int(token.get("expires_in") or 604800)
    saved = account()
    token["user"] = saved.get("user", "")
    token.setdefault("refresh_token", saved.get("refresh_token", ""))
    util.save_json(FILE, token)
    return token


def _refresh():
    saved = account()
    try:
        token, _ = util.http(API + "oauth2/token", form={"grant_type": "refresh_token", "client_id": client(),
                                                         "refresh_token": saved["refresh_token"]}, headers={"User-Agent": AGENT})
    except (util.HttpError, KeyError) as error:
        util.log("Simkl renewal failed: %s" % type(error).__name__)
        return None
    return _store(token)


def _access():
    saved = account()
    if saved.get("refresh_token") and saved.get("expires_at", 0) - time.time() < 3600:
        return (_refresh() or saved).get("access_token")
    return saved.get("access_token")


def call(path, data=None, retry=True):
    join = "&" if "?" in path else "?"
    url = API + path + join + urllib.parse.urlencode({"client_id": client(), "app-name": "lucent-video", "app-version": "0.4"})
    head = {"User-Agent": AGENT, "Authorization": "Bearer %s" % _access()}
    try:
        return util.http(url, data=data, headers=head)[0]
    except util.HttpError as error:
        if error.status == 401 and retry and _refresh():
            return call(path, data, False)
        raise


def login():
    import dialogs
    if not client():
        xbmcgui.Dialog().ok("Lucent", util.T("Vul eerst de Simkl Client ID in bij de instellingen.", "Enter the Simkl Client ID in the settings first."))
        return False
    try:
        code, _ = util.http(API + "oauth2/device", form={"client_id": client(), "scope": "media:read media:write"}, headers={"User-Agent": AGENT})
    except util.HttpError:
        util.notify(util.T("Simkl is niet bereikbaar", "Simkl cannot be reached"))
        return False
    dialog, picture = dialogs.link_dialog("Simkl", code["verification_uri"], code["user_code"], code.get("verification_uri_complete"))
    state = {"open": True, "linked": False}

    def poll():
        interval, started = int(code.get("interval") or 5), time.time()
        monitor = xbmc.Monitor()
        while state["open"] and time.time() - started < int(code.get("expires_in") or 900):
            if monitor.waitForAbort(interval):
                break
            try:
                token, _ = util.http(API + "oauth2/token", form={"grant_type": "urn:ietf:params:oauth:grant-type:device_code",
                                                                 "client_id": client(), "device_code": code["device_code"]},
                                     headers={"User-Agent": AGENT})
            except util.HttpError as error:
                reason = error.detail.get("error")
                if reason == "authorization_pending":
                    continue
                if reason == "slow_down":
                    interval += 5
                    continue
                break
            _store(token)
            state["linked"] = True
            break
        if state["open"]:
            state["open"] = False
            dialog.close()

    worker = threading.Thread(target=poll, daemon=True)
    worker.start()
    dialog.doModal()
    state["open"] = False
    worker.join(timeout=20)
    del dialog
    try:
        os.remove(picture)
    except OSError:
        pass
    if state["linked"]:
        try:
            saved = account()
            saved["user"] = ((call("users/settings", data={}) or {}).get("user") or {}).get("name", "")
            util.save_json(FILE, saved)
        except util.HttpError:
            pass
        util.cache_clear()
        util.notify(util.T("Simkl is gekoppeld", "Simkl is linked"))
    return state["linked"]


def logout():
    util.save_json(FILE, {})
    util.save_json(STATE, {})
    util.cache_clear()
    util.notify(util.T("Simkl is losgekoppeld", "Simkl is unlinked"))


def _library(force=False):
    """Everything in the account. Simkl asks apps to fetch this only after /sync/activities says something changed."""
    saved = util.load_json(STATE, {})
    if not force and saved.get("data") and util.cache_get("simkl_checked", CHECK_EVERY) is not None:
        return saved["data"]
    activities = call("sync/activities") or {}
    util.cache_set("simkl_checked", 1)
    if saved.get("data") is not None and activities.get("all") and activities.get("all") == saved.get("all"):
        return saved["data"]
    data = call("sync/all-items?extended=full&episode_watched_at=yes") or {}
    _attach_tmdb(data)
    util.save_json(STATE, {"all": activities.get("all"), "data": data})
    return data


def _attach_tmdb(data):
    """Not every Simkl title carries a TMDB id: look the others up by IMDb or TVDB id."""
    jobs = []
    for bucket, key, kind in (("movies", "movie", "movie"), ("shows", "show", "tvshow"), ("anime", "show", "tvshow")):
        for row in data.get(bucket) or []:
            entry = row.get(key) or row.get("anime") or {}
            ids = entry.get("ids") or {}
            if not ids.get("tmdb"):
                jobs.append((ids, kind))

    def look(job):
        ids, kind = job
        found = tmdb.find(kind, imdb=ids.get("imdb"), tvdb=ids.get("tvdb"))
        if found:
            ids["tmdb"] = found
    if jobs:
        with ThreadPoolExecutor(max_workers=6) as pool:
            list(pool.map(look, jobs))


def _rows(data, bucket):
    if bucket == "movies":
        return [(r, r.get("movie") or {}) for r in data.get("movies") or []]
    return [(r, r.get("show") or r.get("anime") or {}) for r in (data.get("shows") or []) + (data.get("anime") or [])]


def _id(entry):
    value = (entry.get("ids") or {}).get("tmdb")
    return str(value) if value else ""


def _stamp(text):
    return str(text or "").replace("T", " ")[:19]


def refresh():
    try:
        _library(force=True)
        return True
    except util.HttpError as error:
        util.log("Simkl refresh: %s" % error)
        return False


def forget_lists():
    util.cache_drop("simkl_checked")


def _safe():
    try:
        return _library()
    except util.HttpError as error:
        util.log("Simkl: %s" % error)
        return util.load_json(STATE, {}).get("data") or {}


def watched_movies():
    return {_id(e): _stamp(r.get("last_watched_at")) for r, e in _rows(_safe(), "movies") if _id(e) and r.get("status") == "completed"}


def watched_episodes():
    out = {}
    for row, entry in _rows(_safe(), "shows"):
        if _id(entry):
            out[_id(entry)] = {(s["number"], e["number"]): _stamp(e.get("watched_at"))
                               for s in row.get("seasons") or [] for e in s.get("episodes") or []}
    return out


def paused():
    try:
        rows = call("sync/playback") or []
    except util.HttpError:
        return []
    out = []
    for row in rows:
        row = dict(row)
        if row.get("anime") and not row.get("show"):
            row["show"] = row["anime"]
        title = row.get("movie") or row.get("show") or {}
        ids = title.get("ids") or {}
        if not ids.get("tmdb"):
            found = tmdb.find("movie" if row.get("type") == "movie" else "tvshow", imdb=ids.get("imdb"), tvdb=ids.get("tvdb"))
            if not found:
                continue
            ids["tmdb"] = found
        out.append(row)
    return out


def next_up():
    out = []
    for row, entry in _rows(_safe(), "shows"):
        match = re.match(r"S(\d+)E(\d+)", str(row.get("next_to_watch") or ""), re.I)
        if match and _id(entry) and row.get("status") == "watching":
            out.append((row.get("last_watched_at") or "", _id(entry), int(match.group(1)), int(match.group(2))))
    return [(show, season, episode) for _, show, season, episode in sorted(out, reverse=True)]


def pairs(name):
    bucket, kind = ("movies", "movie") if name.endswith("movie") else ("shows", "tvshow")
    keep = (lambda s: s == "plantowatch") if name.startswith("watchlist_") else (lambda s: s in ("completed", "watching"))
    return [(kind, _id(e)) for r, e in _rows(_safe(), bucket) if _id(e) and keep(r.get("status"))]


def library_rows(kind):
    """Simkl has no 'collection': everything you follow goes in, except what you dropped."""
    key = "movie" if kind == "movies" else "show"
    data = _library()         # a failure must reach the caller: then nothing gets removed
    out = []
    for row, entry in _rows(data, kind):
        if _id(entry) and row.get("status") != "dropped":
            out.append({key: {"title": entry.get("title"), "year": entry.get("year"), "ids": {"tmdb": int(_id(entry))}},
                        "collected_at": row.get("added_to_watchlist_at"), "last_collected_at": row.get("added_to_watchlist_at")})
    return out


def library_list(meta, add):
    """Simkl has no collection: the library follows everything except 'dropped'. In = plan to watch (when it is not in
    your lists yet), out = dropped."""
    bucket = "movies" if meta["kind"] == "movie" else "shows"
    if add:
        known = {_id(e): r.get("status") for r, e in _rows(_library(), bucket)}
        if known.get(str(meta["tmdb"])) not in (None, "dropped"):
            return
        call("sync/add-to-list", data={bucket: [{"to": "plantowatch", "ids": _ids(meta)}]})
    else:
        call("sync/add-to-list", data={bucket: [{"to": "dropped", "ids": _ids(meta)}]})
    forget_lists()


def _ids(meta):
    out = {"tmdb": str(meta["tmdb"])}
    if meta.get("imdb"):
        out["imdb"] = meta["imdb"]
    return out


def scrobble(state, meta, percent):
    if meta.get("kind") == "movie":
        body = {"movie": {"ids": _ids(meta)}}
    else:
        body = {"show": {"ids": _ids(meta)}, "episode": {"season": int(meta["season"]), "number": int(meta["episode"])}}
    body["progress"] = round(float(percent), 2)
    try:
        call("scrobble/" + state, data=body)
    except util.HttpError as error:
        util.log("Simkl scrobble %s: %s" % (state, error))


def set_watched(meta, watched):
    item = {"ids": _ids(meta)}
    if meta["kind"] == "movie":
        body = {"movies": [item]}
    elif meta["kind"] == "tvshow":
        body = {"shows": [dict(item, status="completed") if watched else item]}
    elif meta["kind"] == "season":
        body = {"shows": [dict(item, seasons=[{"number": int(meta["season"])}])]}
    else:
        body = {"shows": [dict(item, seasons=[{"number": int(meta["season"]), "episodes": [{"number": int(meta["episode"])}]}])]}
    call("sync/history" + ("" if watched else "/remove"), data=body)
    forget_lists()


def set_watchlist(meta, add):
    bucket = "movies" if meta["kind"] == "movie" else "shows"
    if add:
        call("sync/add-to-list", data={bucket: [{"to": "plantowatch", "ids": _ids(meta)}]})
    else:
        call("sync/history/remove", data={bucket: [{"ids": _ids(meta)}]})
    forget_lists()
