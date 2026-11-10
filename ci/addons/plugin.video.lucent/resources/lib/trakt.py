# -*- coding: utf-8 -*-
"""Your Trakt account: login, lists, progress and scrobbling. Tokens are never logged."""
import os
import time
import urllib.parse

import xbmc
import xbmcgui

import apikeys
import keys
import util

API = "https://api.trakt.tv/"
OAUTH = "https://auth.trakt.tv/"     # Trakt wants every oauth request on this host
FILE = "trakt.json"
HAS_LISTS = True
COLLECTIONS = {"watchlist_movie": ("sync/watchlist/movies", "movie"), "watchlist_tv": ("sync/watchlist/shows", "tvshow"),
               "collection_movie": ("sync/collection/movies", "movie"), "collection_tv": ("sync/collection/shows", "tvshow")}


def client():
    return apikeys.trakt_id(), util.setting("trakt_secret") or keys.TRAKT_CLIENT_SECRET


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


def _with_secret(body, secret):
    """New Trakt apps have no secret at all; older ones still send theirs."""
    if secret:
        body["client_secret"] = secret
    return body


def _refresh():
    cid, secret = client()
    saved = account()
    try:
        token, _ = util.http(OAUTH + "oauth/token", data=_with_secret({
            "refresh_token": saved["refresh_token"], "client_id": cid,
            "redirect_uri": "urn:ietf:wg:oauth:2.0:oob", "grant_type": "refresh_token"}, secret))
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


PAGED = ("sync/watched/movies", "sync/watched/shows", "sync/playback")


def cached(path, ttl=300):
    """A Trakt answer kept for a few minutes. Watched lists and playback are read page by page: Trakt gives at
    most 100 items per request, so with only the first page most of your history was missing."""
    value = util.cache_get("trakt" + path, ttl)
    if value is None:
        value = all_pages(path, limit=1000) if path in PAGED else call(path)[0]
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


def all_pages(path, limit=250):
    """Every page of a paged Trakt answer, so there is no limit of 100. A failure reaches the caller."""
    join = "&" if "?" in path else "?"
    out, page = [], 1
    while True:
        data, head = call("%s%spage=%d&limit=%d" % (path, join, page, limit))
        out += data or []
        head = {k.lower(): v for k, v in (head or {}).items()}
        try:
            pages = int(head.get("x-pagination-page-count") or 1)
        except ValueError:
            pages = 1
        if page >= pages or not data or page >= 400:
            return out
        page += 1


LIBRARY = "library_sources.json"


def library_sources():
    """What the Kodi library follows: the collection, the watchlist and/or chosen lists."""
    saved = util.load_json(LIBRARY, {})
    return {"collection": saved.get("collection", True), "watchlist": bool(saved.get("watchlist")),
            "lists": [entry for entry in saved.get("lists") or [] if len(entry) == 3]}


def library_rows(kind):
    """Everything the library follows, without any limit. A failure reaches the caller: then nothing gets removed."""
    key = "movie" if kind == "movies" else "show"
    chosen = library_sources()
    paths = []
    if chosen["collection"]:
        paths.append("sync/collection/%s" % kind)
    if chosen["watchlist"]:
        paths.append("sync/watchlist/%s" % kind)
    paths += ["users/%s/lists/%s/items/%s" % (owner, list_id, key) for owner, list_id, _name in chosen["lists"]]
    out, seen = [], set()
    for path in paths:
        for row in all_pages(path):
            item = row.get(key) or {}
            tmdb_id = (item.get("ids") or {}).get("tmdb")
            if not tmdb_id or tmdb_id in seen:
                continue
            seen.add(tmdb_id)
            row.setdefault("collected_at", row.get("listed_at"))
            out.append(row)
    return out


def library_list(meta, add):
    key = "movies" if meta["kind"] == "movie" else "shows"
    body = {key: [{"ids": {"tmdb": int(meta["tmdb"])}}]}
    chosen = library_sources()
    end = "" if add else "/remove"
    done = False
    if chosen["collection"]:
        call("sync/collection" + end, data=body)
        done = True
    if chosen["watchlist"] and not (add and done):
        call("sync/watchlist" + end, data=body)
        done = True
    for owner, list_id, _name in chosen["lists"]:
        if add and done:
            break
        if str(owner) in ("me", account().get("user", "")):
            call("users/me/lists/%s/items%s" % (list_id, end), data=body)
            done = True
    if add and not done:                 # the library follows nothing you can add to: use the collection
        call("sync/collection", data=body)
    forget_lists()


def choose_library():
    """A simple tick list: which Trakt parts the Kodi library follows."""
    chosen = library_sources()
    try:
        lists = [(o, i, n) for o, i, n in custom_lists("mine")] + [(o, i, n) for o, i, n in custom_lists("liked")]
    except util.HttpError:
        lists = []
    names = [util.T("Collectie", "Collection"), "Watchlist"] + [n if o == "me" else "%s (%s)" % (n, o) for o, i, n in lists]
    picked = [i for i, on in enumerate((chosen["collection"], chosen["watchlist"])) if on]
    keep = {(str(o), str(i)) for o, i, _n in chosen["lists"]}
    picked += [2 + number for number, (o, i, _n) in enumerate(lists) if (str(o), str(i)) in keep]
    answer = xbmcgui.Dialog().multiselect(util.T("Wat komt in de bibliotheek?", "What goes in the library?"), names, preselect=picked)
    if answer is None:
        return False
    util.save_json(LIBRARY, {"collection": 0 in answer, "watchlist": 1 in answer,
                             "lists": [list(lists[n - 2]) for n in answer if n >= 2]})
    return True


def login():
    import dialogs
    import threading
    cid, secret = client()
    if not cid:
        xbmcgui.Dialog().ok("Lucent", util.T("Vul eerst de Trakt Client ID in bij de instellingen.",
                                             "Enter the Trakt Client ID in the settings first."))
        return False
    try:
        code, _ = util.http(OAUTH + "oauth/device/code", data={"client_id": cid})
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
                token, _ = util.http(OAUTH + "oauth/device/token", data=_with_secret({"code": code["device_code"], "client_id": cid}, secret))
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
