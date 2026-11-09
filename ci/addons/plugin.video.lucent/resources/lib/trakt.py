# -*- coding: utf-8 -*-
"""Your Trakt account: login, lists, progress and scrobbling. Tokens are never logged."""
import os
import time
import urllib.parse

import xbmc
import xbmcgui

import keys
import util

API = "https://api.trakt.tv/"
FILE = "trakt.json"
HAS_LISTS = True
COLLECTIONS = {"watchlist_movie": ("sync/watchlist/movies", "movie"), "watchlist_tv": ("sync/watchlist/shows", "tvshow"),
               "collection_movie": ("sync/collection/movies", "movie"), "collection_tv": ("sync/collection/shows", "tvshow")}


def client():
    return util.setting("trakt_id") or keys.TRAKT_CLIENT_ID, util.setting("trakt_secret") or keys.TRAKT_CLIENT_SECRET


def account():
    return util.load_json(FILE, {})


def logged_in():
    return bool(account().get("access_token"))


def _store(token):
    token["expires_at"] = time.time() + int(token.get("expires_in") or 86400)
    previous = account()
    token["user"] = previous.get("user", "")
    util.save_json(FILE, token)
    return token


def _refresh():
    cid, secret = client()
    saved = account()
    try:
        token, _ = util.http(API + "oauth/token", data={
            "refresh_token": saved["refresh_token"], "client_id": cid, "client_secret": secret,
            "redirect_uri": "urn:ietf:wg:oauth:2.0:oob", "grant_type": "refresh_token"})
    except (util.HttpError, KeyError) as error:
        util.log("Trakt renewal failed: %s" % type(error).__name__)
        return None
    return _store(token)


def _access():
    saved = account()
    if saved.get("access_token") and saved.get("expires_at", 0) - time.time() < 3600:
        return (_refresh() or saved).get("access_token")
    return saved.get("access_token")


def call(path, data=None, method=None, auth=True, retry=True):
    """Returns (json, headers). Raises util.HttpError."""
    cid, _ = client()
    head = {"trakt-api-version": "2", "trakt-api-key": cid}
    if auth:
        token = _access()
        if token:
            head["Authorization"] = "Bearer " + token
    try:
        return util.http(API + path, data=data, headers=head, method=method)
    except util.HttpError as error:
        if error.status == 401 and auth and retry and _refresh():
            return call(path, data, method, auth, False)
        if error.status == 429 and retry:
            xbmc.sleep(1500)
            return call(path, data, method, auth, False)
        raise


def cached(path, ttl=300):
    value = util.cache_get("trakt" + path, ttl)
    if value is None:
        value = call(path)[0]
        util.cache_set("trakt" + path, value)
    return value


def refresh():
    forget_lists()
    try:
        cached("sync/watched/movies", 0)
        cached("sync/watched/shows", 0)
        cached("sync/playback", 0)
        return True
    except util.HttpError as error:
        util.log("Trakt refresh: %s" % error)
        return False


def pairs_from(data):
    out = []
    for row in data or []:
        kind = row.get("type") or ("movie" if "movie" in row else "show")
        tmdb_id = (row.get(kind) or {}).get("ids", {}).get("tmdb")
        if tmdb_id and kind in ("movie", "show"):
            out.append(("movie" if kind == "movie" else "tvshow", tmdb_id))
    return out


def pairs(name):
    return pairs_from(cached(COLLECTIONS[name][0]))


def custom_lists(kind, query=None):
    """[(owner, id, name)]. kind: mine, liked, trending, popular or search."""
    if kind == "mine":
        return [("me", i["ids"]["trakt"], i["name"]) for i in cached("users/me/lists", 900)]
    if kind == "liked":
        path = "users/likes/lists?limit=100"
    elif kind == "search":
        path = "search/list?" + urllib.parse.urlencode({"query": query or "", "limit": 50})
    else:
        path = "lists/%s?limit=50" % ("popular" if kind == "popular" else "trending")
    rows = []
    for row in cached(path, 900) or []:
        entry = row.get("list") or {}
        owner = ((entry.get("user") or {}).get("ids") or {}).get("slug")
        if owner and (entry.get("ids") or {}).get("trakt") and entry.get("privacy", "public") == "public" or kind == "liked" and owner:
            rows.append((owner, entry["ids"]["trakt"], entry["name"]))
    return rows


def list_pairs(owner, list_id, page, size):
    return pairs_from(cached("users/%s/lists/%s/items/movie,show?limit=%d&page=%d" % (owner, list_id, size, page), 900))


def next_up():
    from concurrent.futures import ThreadPoolExecutor
    shows = sorted(cached("sync/watched/shows?extended=noseasons"), key=lambda s: s.get("last_watched_at") or "", reverse=True)[:40]

    def load(row):
        ids = row["show"]["ids"]
        if not ids.get("tmdb"):
            return None
        try:
            following = (call("shows/%s/progress/watched?hidden=false&specials=false" % ids["trakt"])[0] or {}).get("next_episode")
        except util.HttpError:
            return None
        return (ids["tmdb"], following["season"], following["number"]) if following else None
    with ThreadPoolExecutor(max_workers=6) as pool:
        return [r for r in pool.map(load, shows) if r]


def library_rows(kind):
    """A failure reaches the caller: then nothing gets removed."""
    key = "movie" if kind == "movies" else "show"
    return [r for r in call("sync/collection/%s" % kind)[0] or [] if r.get(key, {}).get("ids", {}).get("tmdb")]


def login():
    import dialogs
    import threading
    cid, secret = client()
    if not cid or not secret:
        xbmcgui.Dialog().ok("Lucent", util.T("Vul eerst de Trakt Client ID en Secret in bij de instellingen.",
                                             "Enter the Trakt Client ID and Secret in the settings first."))
        return False
    try:
        code, _ = util.http(API + "oauth/device/code", data={"client_id": cid})
    except util.HttpError:
        util.notify(util.T("Trakt is niet bereikbaar", "Trakt cannot be reached"))
        return False
    dialog, picture = dialogs.link_dialog("Trakt", code["verification_url"], code["user_code"])
    state = {"open": True, "linked": False}

    def poll():
        interval, started = int(code["interval"]), time.time()
        monitor = xbmc.Monitor()
        while state["open"] and time.time() - started < int(code["expires_in"]):
            if monitor.waitForAbort(interval):
                break
            try:
                token, _ = util.http(API + "oauth/device/token", data={"code": code["device_code"], "client_id": cid, "client_secret": secret})
            except util.HttpError as error:
                if error.status == 400:      # not entered yet
                    continue
                if error.status == 429:
                    interval += 1
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
            saved["user"] = (call("users/me")[0] or {}).get("username", "")
            util.save_json(FILE, saved)
        except util.HttpError:
            pass
        util.cache_clear()
        util.notify(util.T("Trakt is gekoppeld", "Trakt is linked"))
    return state["linked"]


def logout():
    util.save_json(FILE, {})
    util.cache_clear()
    util.notify(util.T("Trakt is losgekoppeld", "Trakt is unlinked"))


def ids_body(meta):
    """The body naming a film or episode for Trakt."""
    if meta.get("kind") == "movie" or meta.get("type") == "movie":
        return {"movie": {"ids": {"tmdb": int(meta["tmdb"])}}}
    return {"show": {"ids": {"tmdb": int(meta["tmdb"])}},
            "episode": {"season": int(meta["season"]), "number": int(meta["episode"])}}


def scrobble(state, meta, percent):
    if not logged_in():
        return
    body = ids_body(meta)
    body["progress"] = round(float(percent), 2)
    try:
        call("scrobble/" + state, data=body)
    except util.HttpError as error:
        util.log("scrobble %s: %s" % (state, error))


def forget_lists():
    for path in ("sync/watched/movies", "sync/watched/shows", "sync/playback", "sync/watchlist/movies",
                 "sync/watchlist/shows"):
        util.cache_drop("trakt" + path)
    util.cache_drop("nextup")


def _stamp(text):
    return str(text or "").replace("T", " ")[:19]


def watched_movies():
    """{tmdb id: when watched}"""
    if not logged_in():
        return {}
    try:
        return {str(i["movie"]["ids"].get("tmdb")): _stamp(i.get("last_watched_at")) for i in cached("sync/watched/movies")}
    except util.HttpError:
        return {}


def watched_episodes():
    """{show tmdb id: {(season, episode): when watched}}"""
    if not logged_in():
        return {}
    try:
        data = cached("sync/watched/shows")
    except util.HttpError:
        return {}
    return {str(i["show"]["ids"].get("tmdb")): {(s["number"], e["number"]): _stamp(e.get("last_watched_at"))
                                                 for s in i.get("seasons") or [] for e in s.get("episodes") or []} for i in data}


def paused():
    if not logged_in():
        return []
    try:
        return cached("sync/playback", ttl=60) or []
    except util.HttpError:
        return []


def resume_percent(kind, tmdb, season=None, episode=None):
    for item in paused():
        if kind == "movie" and item.get("type") == "movie" and str(item["movie"]["ids"].get("tmdb")) == str(tmdb):
            return item.get("progress") or 0
        if kind == "episode" and item.get("type") == "episode" and str(item["show"]["ids"].get("tmdb")) == str(tmdb) \
                and item["episode"]["season"] == int(season) and item["episode"]["number"] == int(episode):
            return item.get("progress") or 0
    return 0


def set_watched(meta, watched):
    show = {"ids": {"tmdb": int(meta["tmdb"])}}
    if meta["kind"] == "movie":
        body = {"movies": [{"ids": {"tmdb": int(meta["tmdb"])}}]}
    elif meta["kind"] == "tvshow":
        body = {"shows": [show]}
    elif meta["kind"] == "season":
        body = {"shows": [dict(show, seasons=[{"number": int(meta["season"])}])]}
    else:
        body = {"shows": [dict(show, seasons=[{"number": int(meta["season"]), "episodes": [{"number": int(meta["episode"])}]}])]}
    call("sync/history" + ("" if watched else "/remove"), data=body)
    forget_lists()
    return None


def set_watchlist(meta, add):
    key = "movies" if meta["kind"] == "movie" else "shows"
    call("sync/watchlist" + ("" if add else "/remove"), data={key: [{"ids": {"tmdb": int(meta["tmdb"])}}]})
    forget_lists()


def _enrich_one(meta):
    kind = "movie" if meta["kind"] == "movie" else "show"
    path = "search/tmdb/%s?type=%s&extended=full" % (meta["tmdb"], kind)
    try:
        rows = cached(path, 7 * 86400) if client()[0] else []
    except util.HttpError:
        return
    if rows:
        entry = rows[0].get(kind) or {}
        meta["trakt_rating"], meta["trakt_votes"] = entry.get("rating") or 0, entry.get("votes") or 0
        meta["trakt_id"] = str((entry.get("ids") or {}).get("trakt") or "")


def enrich(titles):
    """Adds the Trakt score and id to films and series."""
    from concurrent.futures import ThreadPoolExecutor
    targets = [t for t in titles if t["kind"] in ("movie", "tvshow")]
    if targets:
        with ThreadPoolExecutor(max_workers=6) as pool:
            list(pool.map(_enrich_one, targets))
