# -*- coding: utf-8 -*-
"""Lucent's own widget rows, straight from TMDb (no other add-on involved).

    plugin://script.lucent.library/?action=tmdb&list=trending_movie

The row is answered at once from a saved copy (the plugin part only reads). The Lucent Library service keeps the copies
fresh: one request to TMDb per list, every 6 hours, never while a video plays; a failed request keeps the old copy
and is tried again later. A click on a title opens its own page in Lucent (Play there goes to Seren), the same way as the
"Tonight for you" row. Needs the TMDb key Lucent already uses (Seren's setting, or the key in Skin settings).
"""
import json
import os
import time
import urllib.parse
import urllib.request

import xbmc
import xbmcaddon
import xbmcgui
import xbmcvfs

ADDON_ID = "script.lucent.library"
DIR = xbmcvfs.translatePath(f"special://profile/addon_data/{ADDON_ID}/tmdb/")
REG = os.path.join(DIR, "registry.json")
HOME = xbmcgui.Window(10000)
TTL = 6 * 3600
BACKOFF = (120, 600, 1800)
TMDB = "https://api.themoviedb.org/3/"
IMG = "https://image.tmdb.org/t/p/"
NL = xbmc.getLanguage(xbmc.ISO_639_1) == "nl"

# list name -> (TMDb endpoint, kind, label en, label nl)
LISTS = {
    "trending_movie": ("trending/movie/week", "movie", "Trending movies", "Trending films"),
    "trending_tv": ("trending/tv/week", "tvshow", "Trending shows", "Trending series"),
    "popular_movie": ("movie/popular", "movie", "Popular movies", "Populaire films"),
    "popular_tv": ("tv/popular", "tvshow", "Popular shows", "Populaire series"),
    "toprated_movie": ("movie/top_rated", "movie", "Top rated movies", "Best beoordeelde films"),
    "toprated_tv": ("tv/top_rated", "tvshow", "Top rated shows", "Best beoordeelde series"),
    "nowplaying_movie": ("movie/now_playing", "movie", "In cinemas now", "Nu in de bioscoop"),
    "upcoming_movie": ("movie/upcoming", "movie", "Coming soon (movies)", "Binnenkort (films)"),
    "airing_tv": ("tv/on_the_air", "tvshow", "Series on air", "Series die nu lopen"),
}
# Trakt lists (your Seren login): name -> (Trakt endpoint, kind)
TRAKT_LISTS = {
    "trakt_watchlist_movie": ("sync/watchlist/movies", "movie"),
    "trakt_watchlist_tv": ("sync/watchlist/shows", "tvshow"),
    "trakt_recommended_movie": ("recommendations/movies", "movie"),
    "trakt_recommended_tv": ("recommendations/shows", "tvshow"),
    "trakt_trending_movie": ("movies/trending", "movie"),
    "trakt_trending_tv": ("shows/trending", "tvshow"),
    "trakt_anticipated_movie": ("movies/anticipated", "movie"),
    "trakt_anticipated_tv": ("shows/anticipated", "tvshow"),
}
META = os.path.join(DIR, "meta.json")        # TMDb details per title (poster, backdrop, score): Trakt gives no pictures
META_KEEP = 4000


def log(text):
    xbmc.log(f"[script.lucent.library] tmdb: {text}", xbmc.LOGINFO)


def read_json(path, default=None):
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except Exception:  # noqa: BLE001
        return default


def write_json(path, data):
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        tmp = f"{path}.{os.getpid()}.tmp"
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(data, fh)
        os.replace(tmp, path)
    except Exception as error:  # noqa: BLE001
        log(f"write {os.path.basename(path)}: {error}")


def cache_file(name):
    return os.path.join(DIR, f"{name}.json")


def tmdb_key():
    try:
        key = (xbmcaddon.Addon("plugin.video.seren").getSetting("tmdb.apikey") or "").strip()
    except Exception:  # noqa: BLE001 - Seren not installed
        key = ""
    for path in ("special://profile/addon_data/skin.lucent/tmdb_key.txt", "special://profile/addon_data/script.lucent.library/tmdb_key.txt"):
        if key:
            break
        try:
            with xbmcvfs.File(path) as fh:
                key = (fh.read() or "").strip()
        except Exception:  # noqa: BLE001
            key = ""
    return key


# ----------------------------------------------------------------------------- TMDb -> row entries
def entry_of(result, kind):
    tmdb_id = result.get("id")
    title = result.get("title") or result.get("name") or ""
    date = result.get("release_date") or result.get("first_air_date") or ""
    year = int(date[:4]) if date[:4].isdigit() else 0
    poster = f"{IMG}w500{result['poster_path']}" if result.get("poster_path") else ""
    fanart = f"{IMG}w1280{result['backdrop_path']}" if result.get("backdrop_path") else ""
    query = urllib.parse.urlencode({"action": "tmdbopen", "type": "movie" if kind == "movie" else "tv", "tmdb": tmdb_id, "year": year or ""})
    return {"type": kind, "label": title, "title": title, "plot": result.get("overview") or "", "year": year,
            "rating": float(result.get("vote_average") or 0), "premiered": date,
            "ratings": {"tmdb": {"rating": float(result.get("vote_average") or 0), "votes": int(result.get("vote_count") or 0), "default": True}},
            "art": {"poster": poster, "thumb": poster, "fanart": fanart},
            "file": f"plugin://{ADDON_ID}/?{query}", "filetype": "file", "action": True,
            "props": {"tmdb_id": str(tmdb_id or ""), "lucent_open": "1"}}


def tmdb_get(path, **params):
    key = tmdb_key()
    if not key:
        return None
    params.update(api_key=key, language="nl-NL" if NL else "en-US")
    try:
        req = urllib.request.Request(f"{TMDB}{path}?{urllib.parse.urlencode(params)}", headers={"User-Agent": "Lucent/1.0", "Accept": "application/json"})
        with urllib.request.urlopen(req, timeout=20) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except Exception as error:  # noqa: BLE001
        log(f"{path}: {type(error).__name__}")
        return None


def enrich(rows):
    """Logo, genres, runtime and vote count from TMDb's detail page, kept in meta.json (a few new titles per run)."""
    meta = read_json(META, {}) or {}
    asked, now = 0, time.time()
    for row in rows:
        tid = (row.get("props") or {}).get("tmdb_id")
        if not tid:
            continue
        kind = "movie" if row.get("type") == "movie" else "tv"
        key = f"d{kind[0]}{tid}"
        info = meta.get(key)
        if info is None and asked < 25:
            asked += 1
            d = tmdb_get(f"{kind}/{tid}", append_to_response="images", include_image_language=("nl,en,null" if NL else "en,null"))
            if d:
                logos = ((d.get("images") or {}).get("logos")) or []
                logos.sort(key=lambda x: (x.get("iso_639_1") not in ("nl" if NL else "en",), -(x.get("vote_average") or 0)))
                run = d.get("runtime") or ((d.get("episode_run_time") or [0])[0])
                info = {"logo": (logos[0].get("file_path") if logos else "") or "", "genre": [g.get("name") for g in d.get("genres") or [] if g.get("name")],
                        "runtime": int(run or 0) * 60, "votes": int(d.get("vote_count") or 0),
                        "studio": [c.get("name") for c in (d.get("production_companies") or [])[:2] if c.get("name")], "t": now}
                meta[key] = info
        if info:
            if info.get("logo"):
                row["art"]["clearlogo"] = f"{IMG}w500{info['logo']}"
            if info.get("genre"):
                row["genre"] = info["genre"]
            if info.get("runtime"):
                row["runtime"] = info["runtime"]
            if info.get("votes"):
                row["votes"] = info["votes"]
            if info.get("studio"):
                row["studio"] = info["studio"]
    if asked:
        if len(meta) > META_KEEP:
            for k in sorted(meta, key=lambda k: meta[k].get("t", 0))[:len(meta) - META_KEEP]:
                del meta[k]
        write_json(META, meta)
    return rows


def fetch_tmdb(name):
    endpoint, kind = LISTS[name][0], LISTS[name][1]
    params = {"page": 1}
    if name in ("nowplaying_movie", "upcoming_movie"):
        params["region"] = "NL" if NL else "US"
    data = tmdb_get(endpoint, **params)
    if data is None:
        return None
    rows = [entry_of(r, kind) for r in (data.get("results") or []) if r.get("poster_path")]
    rows = enrich(rows[:20])
    for row in rows:                                   # the vote count of the detail page is the better one
        if row.get("votes") and "tmdb" in (row.get("ratings") or {}):
            row["ratings"]["tmdb"]["votes"] = row["votes"]
    return rows or None


def trakt_endpoint(name, path):
    """(endpoint, kind) of a Trakt list name; your own lists carry user and list id in the row path."""
    if name in TRAKT_LISTS:
        return TRAKT_LISTS[name]
    q = urllib.parse.parse_qs(urllib.parse.urlsplit(path).query)
    user, lid = (q.get("user") or [""])[0], (q.get("id") or [""])[0]
    if user and lid:
        return f"users/{urllib.parse.quote(user)}/lists/{urllib.parse.quote(lid)}/items", "mixed"
    return None


WHY = {"text": ""}      # why the last fetch gave nothing (shown in the empty row)


def fetch_trakt(name, path):
    """Entries of a Trakt list: the titles from Trakt, the pictures and scores from TMDb (kept in meta.json)."""
    WHY["text"] = ""
    spec = trakt_endpoint(name, path)
    if not spec:
        WHY["text"] = "list not recognised"
        return None
    if not tmdb_key():
        WHY["text"] = "no TMDb key (add it in Skin settings)"
        return None
    try:
        import quick
        trakt = quick.Trakt()
        if not trakt.token and name.startswith(("trakt_watchlist", "trakt_recommended", "tl_")):
            WHY["text"] = "not logged in to Trakt in Seren"
            return None
        data = trakt.call(f"{spec[0]}{'&' if '?' in spec[0] else '?'}extended=full&limit=40")
    except Exception as error:  # noqa: BLE001
        log(f"{name}: {type(error).__name__} {error}"[:200])
        WHY["text"] = f"Trakt error: {type(error).__name__}"
        return None
    meta = read_json(META, {}) or {}
    seen = set((read_json(os.path.join(os.path.dirname(DIR.rstrip("/\\")), "trakt_watched.json"), {}) or {}).get("movies") or [])
    rows, asked = [], 0
    for item in data if isinstance(data, list) else []:
        obj, kind = None, spec[1]
        for key, k in (("movie", "movie"), ("show", "tvshow")):
            if item.get(key):
                obj, kind = item[key], k
        if obj is None and item.get("ids"):
            obj = item
        if not obj or kind == "mixed":
            continue
        tmdb_id = (obj.get("ids") or {}).get("tmdb")
        if not tmdb_id:
            continue
        mk = f"{'m' if kind == 'movie' else 't'}{tmdb_id}"
        info = meta.get(mk)
        if info is None and asked < 25:
            asked += 1
            d = tmdb_get(f"{'movie' if kind == 'movie' else 'tv'}/{tmdb_id}")
            if d:
                info = {"poster": d.get("poster_path") or "", "fanart": d.get("backdrop_path") or "", "plot": d.get("overview") or "",
                        "rating": float(d.get("vote_average") or 0), "t": time.time()}
                meta[mk] = info
        if not info or not info.get("poster"):
            continue
        date = (obj.get("released") or obj.get("first_aired") or "")[:10]
        year = obj.get("year") or (int(date[:4]) if date[:4].isdigit() else 0)
        title = obj.get("title") or ""
        query = urllib.parse.urlencode({"action": "tmdbopen", "type": "movie" if kind == "movie" else "tv", "tmdb": tmdb_id, "year": year or ""})
        rows.append({"type": kind, "label": title, "title": title, "plot": obj.get("overview") or info.get("plot") or "", "year": int(year or 0),
                     "rating": float(obj.get("rating") or info.get("rating") or 0), "premiered": date,
                     "trakt_rating": float(obj.get("rating") or 0), "trakt_votes": int(obj.get("votes") or 0), "tmdb_rating": float(info.get("rating") or 0),
                     "art": {"poster": f"{IMG}w500{info['poster']}", "thumb": f"{IMG}w500{info['poster']}",
                             "fanart": f"{IMG}w1280{info['fanart']}" if info.get("fanart") else ""},
                     "file": f"plugin://{ADDON_ID}/?{query}", "filetype": "file", "action": True, "props": {"tmdb_id": str(tmdb_id), "lucent_open": "1"}})
        if kind == "movie" and (obj.get("ids") or {}).get("trakt") in seen:
            rows[-1]["playcount"] = 1                      # Trakt says you saw it (list kept by the library export)
        if len(rows) >= 20:
            break
    if asked:
        if len(meta) > META_KEEP:
            for k in sorted(meta, key=lambda k: meta[k].get("t", 0))[:len(meta) - META_KEEP]:
                del meta[k]
        write_json(META, meta)
    if not rows:
        WHY["text"] = "list is empty or has no titles with pictures" if data else "Trakt returned nothing"
    rows = enrich(rows)
    for row in rows:                                   # both scores on the card; Trakt's is the main one
        ratings, tr_r, tr_v, tm_r = {}, row.pop("trakt_rating", 0), row.pop("trakt_votes", 0), row.pop("tmdb_rating", 0)
        if tr_r:
            ratings["trakt"] = {"rating": tr_r, "votes": tr_v, "default": True}
        if tm_r:
            ratings["tmdb"] = {"rating": tm_r, "votes": row.get("votes", 0), "default": not ratings}
        if ratings:
            row["ratings"] = ratings
    return rows or None


# ----------------------------------------------------------------------------- streaming services (TMDb watch providers)
REGION = "NL" if NL else "US"
PROV_FILE = os.path.join(DIR, "providers.json")
PROV_TTL = 7 * 86400
PROV_MAX = 16
PROV_KINDS = {  # kind -> (TMDb type, row type, extra discover params, English, Dutch)
    "newmovie": ("movie", "movie", {"sort_by": "primary_release_date.desc", "vote_count.gte": 10}, "New movies", "Nieuwe films"),
    "newtv": ("tv", "tvshow", {"sort_by": "first_air_date.desc", "vote_count.gte": 5}, "New series", "Nieuwe series"),
    "popmovie": ("movie", "movie", {"sort_by": "popularity.desc"}, "Popular movies", "Populaire films"),
    "poptv": ("tv", "tvshow", {"sort_by": "popularity.desc"}, "Popular series", "Populaire series"),
    "topmovie": ("movie", "movie", {"sort_by": "vote_average.desc", "vote_count.gte": 500}, "Top rated movies", "Best beoordeelde films"),
    "toptv": ("tv", "tvshow", {"sort_by": "vote_average.desc", "vote_count.gte": 200}, "Top rated series", "Best beoordeelde series"),
}


def providers(force=False):
    """[{id, name, logo}] of the streaming services in your country, the biggest first (kept for a week)."""
    saved = read_json(PROV_FILE, {}) or {}
    if saved.get("items") and saved.get("region") == REGION and not force and time.time() - saved.get("time", 0) < PROV_TTL:
        return saved["items"]
    found = {}
    for kind in ("movie", "tv"):
        data = tmdb_get(f"watch/providers/{kind}", watch_region=REGION) or {}
        for r in data.get("results") or []:
            pid = r.get("provider_id")
            prio = (r.get("display_priorities") or {}).get(REGION, r.get("display_priority", 999))
            if pid and r.get("logo_path") and (pid not in found or prio < found[pid]["prio"]):
                found[pid] = {"id": pid, "name": r.get("provider_name") or str(pid), "logo": r["logo_path"], "prio": prio}
    items = sorted(found.values(), key=lambda x: x["prio"])[:PROV_MAX]
    old = {p.get("id"): p for p in saved.get("items") or []}
    for p in items:                                   # the transparent logo: looked up once per service
        p["wide"] = old.get(p["id"], {}).get("wide") if "wide" in old.get(p["id"], {}) else wide_logo(p["name"])
    if items:
        write_json(PROV_FILE, {"time": time.time(), "region": REGION, "items": items})
        return items
    return saved.get("items") or []


PACK = "resource://resource.images.studios.white/"


def name_variants(name):
    """'Disney Plus' -> Disney Plus, Disney+, Disney ...: the names a logo pack or TMDb may use for a service."""
    out = [name]
    for a, b in ((" Plus", "+"), ("Plus", "+"), (" Amazon Channel", ""), (" Standard with Ads", ""), (" with Ads", ""),
                 ("Amazon Prime Video", "Prime Video"), ("Amazon Prime Video", "Amazon"), ("HBO Max", "Max"), ("HBO Max", "HBO")):
        if a in name:
            out.append(name.replace(a, b).strip())
    first = name.split(" ")[0]
    if len(first) > 2:
        out.append(first)
    seen, res = set(), []
    for n in out:
        if n and n.lower() not in seen:
            seen.add(n.lower())
            res.append(n)
    return res


def wide_logo(name):
    """A transparent logo of the service: the white logo pack first, else the company logo on TMDb. '' when none."""
    for n in name_variants(name):
        try:
            if xbmcvfs.exists(f"{PACK}{n}.png"):
                return f"{PACK}{n}.png"
        except Exception:  # noqa: BLE001 - pack not installed
            break
    for n in name_variants(name)[:3]:
        data = tmdb_get("search/company", query=n) or {}
        hits = [r for r in data.get("results") or [] if r.get("logo_path")]
        exact = [r for r in hits if (r.get("name") or "").strip().lower() == n.lower()]
        if exact or hits:
            return f"{IMG}w500{(exact or hits)[0]['logo_path']}"
    return ""


def fetch_provider(name):
    """prov_<id>_<kind>: what this service has (new, popular, top rated), from TMDb."""
    try:
        _p, pid, kind = name.split("_", 2)
        ttype, rtype, extra, _en, _nl = PROV_KINDS[kind]
    except (ValueError, KeyError):
        return None
    today = time.strftime("%Y-%m-%d")
    params = {"with_watch_providers": pid, "watch_region": REGION, "with_watch_monetization_types": "flatrate", "page": 1}
    params.update(extra)
    if kind == "newmovie":
        params["primary_release_date.lte"] = today
    elif kind == "newtv":
        params["first_air_date.lte"] = today
    data = tmdb_get(f"discover/{ttype}", **params)
    if data is None:
        return None
    rows = [entry_of(r, rtype) for r in (data.get("results") or []) if r.get("poster_path")]
    rows = enrich(rows[:20])
    for row in rows:
        if row.get("votes") and "tmdb" in (row.get("ratings") or {}):
            row["ratings"]["tmdb"]["votes"] = row["votes"]
    return rows or None


def fetch(name, path=""):
    """The entries of one list, or None when it cannot be had."""
    if name in LISTS:
        return fetch_tmdb(name)
    if name.startswith("prov_"):
        return fetch_provider(name)
    return fetch_trakt(name, path)


def kind_label(kind):
    k = PROV_KINDS.get(kind)
    return (k[4] if NL else k[3]) if k else kind


def provider_rows(handle):
    """A row of streaming services: a click opens the service with its lists."""
    import widget
    items = []
    for p in providers():
        logo = f"{IMG}w500{p['logo']}"
        saved = read_json(cache_file(f"prov_{p['id']}_poptv"), {}) or read_json(cache_file(f"prov_{p['id']}_popmovie"), {}) or {}
        first = (saved.get("items") or [{}])[0]
        fanart = (first.get("art") or {}).get("fanart") or ""
        wide = p.get("wide") or logo
        query = urllib.parse.urlencode({"action": "provideropen", "id": p["id"], "name": p["name"], "logo": p.get("wide") or ""})
        items.append({"type": "video", "label": p["name"], "title": p["name"], "action": True,
                      "plot": (f"Nieuw, populair en best beoordeeld op {p['name']}" if NL else f"New, popular and top rated on {p['name']}"),
                      "art": {"poster": logo, "thumb": logo, "icon": logo, "landscape": logo, "clearlogo": wide, "fanart": fanart},
                      "file": f"plugin://{ADDON_ID}/?{query}", "filetype": "file", "props": {"lucent_open": "1"}})
        register(f"prov_{p['id']}_poptv", "")            # its picture for the row comes along in the background
    widget.answer(handle, items)


def provider_open(query):
    """A click on a service in the row: its pop-up with the six lists (the skin's service.py)."""
    q = urllib.parse.parse_qs(query.lstrip("?"))
    get = lambda k: urllib.parse.quote((q.get(k) or [""])[0], safe="")  # noqa: E731
    xbmc.executebuiltin(f"RunScript(special://skin/scripts/service.py,{get('id')},{get('name')},{get('logo')})")


def provider_page(handle, query):
    """The lists of one service (a folder per list)."""
    import widget
    q = urllib.parse.parse_qs(query.lstrip("?"))
    pid, pname = (q.get("id") or [""])[0], (q.get("name") or [""])[0]
    items = []
    for kind in PROV_KINDS:
        name = f"prov_{pid}_{kind}"
        saved = read_json(cache_file(name), {}) or {}
        first = (saved.get("items") or [{}])[0]
        art = dict(first.get("art") or {})
        label = kind_label(kind)
        items.append({"type": "video", "label": label, "title": f"{pname} · {label}", "art": art,
                      "file": f"plugin://{ADDON_ID}/?action=tmdbbrowse&list={name}", "filetype": "directory"})
    widget.answer(handle, items)


def browse(handle, query):
    """Open one list as a folder: from the saved copy, fetched first when there is none yet."""
    import widget
    name = list_name("plugin://x/?" + query.lstrip("?").replace("action=tmdbbrowse", "action=tmdb"))
    if not known(name):
        widget.answer(handle, [])
        return
    saved = read_json(cache_file(name), {}) or {}
    items = saved.get("items")
    if not items or time.time() - saved.get("time", 0) > TTL:
        fresh = fetch(name)
        if fresh:
            items = fresh
            write_json(cache_file(name), {"time": time.time(), "v": 3, "items": items})
    register(name, "")
    widget.answer(handle, items or [])


# ----------------------------------------------------------------------------- the plugin part (reads only)
def list_name(path):
    """'trending_movie', 'trakt_watchlist_tv', or for one of your own Trakt lists 'tl_<user>_<id>'."""
    q = urllib.parse.parse_qs(urllib.parse.urlsplit(path).query)
    name = (q.get("list") or [""])[0]
    if name == "tl":
        user, lid = (q.get("user") or [""])[0], (q.get("id") or [""])[0]
        return f"tl_{user}_{lid}" if user and lid else ""
    return name


def known(name):
    return name in LISTS or name in TRAKT_LISTS or name.startswith(("tl_", "prov_"))


def register(name, row, path=""):
    reg = read_json(REG, {}) or {}
    item = reg.setdefault(name, {"rows": []})
    if (not row or row in item["rows"]) and time.time() - item.get("seen", 0) < 600 and item.get("seen") and item.get("path") == path:
        return                                              # known and seen lately: nothing to write
    item["path"] = path
    if row and row not in item["rows"]:
        item["rows"] = (item["rows"] + [row])[-4:]
    item["seen"] = time.time()
    write_json(REG, reg)


def show(handle, path, row):
    """Answer a row at once from its saved copy; an unknown list name gives an empty row."""
    import widget
    name = list_name(path)
    if not known(name):
        widget.answer(handle, [])
        return
    register(name, row, path)
    saved = read_json(cache_file(name), {}) or {}
    items = saved.get("items") or []
    why = (read_json(REG, {}) or {}).get(name, {}).get("why")
    if not items and why:                              # tell what is wrong instead of an empty row
        items = [{"type": "video", "label": f"Trakt: {why}", "title": f"Trakt: {why}", "art": {}, "file": "", "filetype": "file", "action": True}]
    widget.answer(handle, items)


def trakt_lists_dir(handle):
    """Folder for the menu: your own and liked Trakt lists, each pointing at its fast row."""
    import quick
    items = []
    try:
        trakt = quick.Trakt()
        if trakt.token:
            for source, mine in (("users/me/lists", True), ("users/likes/lists", False)):
                for entry in trakt.call(source) or []:
                    lst = entry.get("list") or entry
                    ids = lst.get("ids") or {}
                    user = ((lst.get("user") or {}).get("ids") or {}).get("slug") or "me"
                    lid = ids.get("trakt") or ids.get("slug")
                    if not lid or not lst.get("name"):
                        continue
                    query = urllib.parse.urlencode({"action": "tmdb", "list": "tl", "user": user, "id": lid})
                    items.append({"type": "video", "label": lst["name"], "title": lst["name"], "art": {},
                                  "file": f"plugin://{ADDON_ID}/?{query}", "filetype": "directory",
                                  "props": {"count": str(lst.get("item_count") or "")}})
    except Exception as error:  # noqa: BLE001
        log(f"trakt lists: {type(error).__name__}")
    import widget
    widget.answer(handle, items)


def open_title(query):
    """A click on a title: its own page in Lucent (Play there goes to Seren)."""
    q = urllib.parse.parse_qs(query.lstrip("?"))
    get = lambda k: (q.get(k) or [""])[0]  # noqa: E731
    HOME.setProperty("nuvio.open.tmdb", get("tmdb"))
    HOME.setProperty("nuvio.open.type", get("type") or "movie")
    HOME.setProperty("nuvio.open.year", get("year"))
    HOME.setProperty("nuvio.open.path", "")
    HOME.clearProperty("nuvio.open.trakt")
    xbmc.executebuiltin("RunScript(special://skin/scripts/info.py,open,path)")


# ----------------------------------------------------------------------------- the fetching (runs in the service)
def tick(player_busy=False):
    """One step: fetch one list that is missing or old. True when a request was made."""
    if player_busy or not os.path.exists(REG):
        return False
    reg = read_json(REG, {}) or {}
    now = time.time()
    for name in sorted(reg, key=lambda n: os.path.getmtime(cache_file(n)) if os.path.exists(cache_file(n)) else 0):
        if not known(name):
            continue
        item = reg[name]
        saved = read_json(cache_file(name), {}) or {}
        if saved.get("items") and saved.get("v") == 3 and now - saved.get("time", 0) < TTL:
            continue
        if now < item.get("retry", 0):
            continue
        items = fetch(name, item.get("path") or "")
        if items:
            changed = items != saved.get("items")
            write_json(cache_file(name), {"time": now, "v": 3, "items": items})
            item.update(fail=0, retry=0)
            if changed:
                for row in item.get("rows") or []:
                    HOME.setProperty(f"lucent.wr.{row}", str(now))
            log(f"{name}: {len(items)} titles")
        else:
            fail = int(item.get("fail", 0))
            item.update(fail=fail + 1, retry=now + BACKOFF[min(fail, len(BACKOFF) - 1)], why=WHY["text"])
            if WHY["text"]:
                log(f"{name}: {WHY['text']}")
                for row in item.get("rows") or []:
                    HOME.setProperty(f"lucent.wr.{row}", str(now))
        write_json(REG, reg)
        return True
    return False
