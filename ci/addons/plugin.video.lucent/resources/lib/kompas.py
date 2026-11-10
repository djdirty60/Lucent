# -*- coding: utf-8 -*-
"""Kompas: picks that know your taste, each with a real reason, made on this device.

Kompas learns from what you watched (Trakt, Simkl or this device), from your ratings (Great, Nice, Not for me) and,
for a new profile, from 'Do you like this?'. It looks at genres, themes, directors, writers, actors, languages,
countries, decades and how well known the titles are that you choose. Everything stays on this device, per profile.

Rows for the skin (each with &widget=1; built once a day per profile, shown at once):
  action=list&name=kompas_foryou      Picked for you (about one pick in five is a stretch, something a little different)
  action=list&name=kompas_because     Because you watched ...  (Home property lucent.video.kompas.because has the title)
  action=list&name=kompas_gems        Hidden gems in your taste
  action=list&name=kompas_new         New for you (empty when not enough suits you)
  action=list&name=kompas_trending    Trending for you
  action=list&name=kompas_saved&id=N  a row saved on the Kompas page
Every title carries ListItem.Property(kompas_reason) (and the reason as its tagline).
Picks shown for two weeks that you never opened take a rest of three months."""
from concurrent.futures import ThreadPoolExecutor
import datetime
import math
import random
import threading
import time

import xbmc

import tmdb
import tracker
import users
import util

T = util.T
FEATURES = "kompas_features.json"      # shared by all profiles: a short summary of a title
PROFILE = "kompas_profile.json"
RATINGS = "kompas_ratings.json"        # {"movie:123": 2 great / 1 nice / -1 not for me}
ROWS = "kompas_rows.json"
SHOWN = "kompas_shown.json"
SAVED = "kompas_saved.json"
DAY = 86400
REST_AFTER, REST_FOR = 14 * DAY, 90 * DAY
ROW_NAMES = ("kompas_foryou", "kompas_because", "kompas_gems", "kompas_new", "kompas_trending")
_lock = threading.Lock()

MOODS = [  # key, Dutch, English, movie (with, without), tv (with, without)
    ("feelgood", "Feelgood", "Feel-good", ("35|10751|10749", "27,53,80,10752"), ("35|10751", "80,9648,10768")),
    ("tense", "Spannend", "Tense", ("53|9648|28", "10751,16"), ("9648|80|10759", "10751,16")),
    ("dark", "Donker", "Dark", ("27|80|53", "10751,35,16"), ("80|9648", "10751,35")),
    ("laugh", "Om te lachen", "To laugh", ("35", "18,27"), ("35", "18")),
    ("epic", "Groots", "Epic", ("12|14|878|10752", "35"), ("10765|10759", "35")),
    ("calm", "Rustig", "Calm", ("18|99|36", "28,27,53"), ("18", "10759,80")),
    ("cry", "Om bij te huilen", "To cry", ("18|10749", "35,28,27"), ("18", "35,10759")),
]
KINDS = [("movie", "Film", "Film"), ("tvshow", "Serie", "Series"), ("anime", "Anime", "Anime"), ("doc", "Documentaire", "Documentary")]
TIMES = [(0, "Elke duur", "Any length"), (90, "Tot 90 min", "Up to 90 min"), (120, "Tot 2 uur", "Up to 2 hours")]
REGIONS = [("nlbe", "Nederland en België", "Netherlands and Belgium", "NL|BE"), ("ukie", "VK en Ierland", "UK and Ireland", "GB|IE"),
           ("usca", "VS en Canada", "US and Canada", "US|CA"), ("nordic", "Scandinavië", "Nordic countries", "SE|DK|NO|FI|IS"),
           ("fr", "Frankrijk", "France", "FR"), ("de", "Duitsland en Oostenrijk", "Germany and Austria", "DE|AT|CH"),
           ("it", "Italië", "Italy", "IT"), ("eslatam", "Spanje en Latijns-Amerika", "Spain and Latin America", "ES|MX|AR|CO|CL|BR"),
           ("asia", "Oost-Azië", "East Asia", "JP|KR|CN|HK|TW"), ("in", "India", "India", "IN")]


def on():
    return util.setting("kompas_on").lower() != "false"


def _key(kind, tmdb_id):
    return "%s:%s" % ("movie" if kind == "movie" else "tvshow", tmdb_id)


# ------------------------------------------------------------------ what a title is about
def _summary(kind, raw):
    movie = kind == "movie"
    crew = (raw.get("credits") or {}).get("crew") or []
    words = (raw.get("keywords") or {}).get("keywords" if movie else "results") or []
    date = raw.get("release_date" if movie else "first_air_date") or ""
    makers = [c for c in crew if c.get("job") == "Director"] if movie else (raw.get("created_by") or [])
    return {"kind": kind, "id": str(raw.get("id")), "t": raw.get("title" if movie else "name") or "",
            "y": int(date[:4]) if date[:4].isdigit() else 0,
            "g": [[g["id"], g["name"]] for g in raw.get("genres") or []],
            "k": [[w["id"], w["name"]] for w in words[:12]],
            "d": [[c["id"], c["name"]] for c in makers[:2]],
            "w": [[c["id"], c["name"]] for c in crew if c.get("department") == "Writing"][:3],
            "c": [[c["id"], c["name"]] for c in ((raw.get("credits") or {}).get("cast") or [])[:5]],
            "l": raw.get("original_language") or "",
            "o": ([c["iso_3166_1"] for c in raw.get("production_countries") or []] if movie else raw.get("origin_country") or [])[:3],
            "v": raw.get("vote_count") or 0, "r": raw.get("vote_average") or 0, "rt": (raw.get("runtime") if movie else (raw.get("episode_run_time") or [0] or [0])[0]) or 0,
            "col": str((raw.get("belongs_to_collection") or {}).get("id") or ""), "st": raw.get("status") or "",
            "pp": raw.get("poster_path") or "", "bp": raw.get("backdrop_path") or ""}


def features(pairs):
    """{key: summary} for [(kind, id)], from the saved summaries or TMDB (30 days)."""
    store = util.load_json(FEATURES, {})
    wanted = [(("movie" if k == "movie" else "tvshow"), str(i)) for k, i in pairs]
    missing = [p for p in dict.fromkeys(wanted) if _key(*p) not in store]

    def load(pair):
        kind, tmdb_id = pair
        try:
            raw = tmdb.get("%s/%s" % ("movie" if kind == "movie" else "tv", tmdb_id), ttl=30 * DAY, append_to_response="keywords,credits")
            return _key(kind, tmdb_id), _summary(kind, raw)
        except (util.HttpError, KeyError, TypeError, ValueError):
            return _key(kind, tmdb_id), None
    if missing:
        with ThreadPoolExecutor(max_workers=8) as pool:
            for key, found in pool.map(load, missing):
                if found:
                    store[key] = found
        with _lock:
            if len(store) > 6000:                     # keep the newest
                store = dict(list(store.items())[-5000:])
            util.save_json(FEATURES, store)
    return {_key(*p): store[_key(*p)] for p in wanted if _key(*p) in store}


# ------------------------------------------------------------------ your taste
def ratings():
    return util.load_json(RATINGS, {})


def rate(kind, tmdb_id, value, send=True):
    data = ratings()
    data[_key(kind, tmdb_id)] = value
    util.save_json(RATINGS, data)
    profile = util.load_json(PROFILE, {})
    profile["at"] = 0                            # learn it at the next look
    util.save_json(PROFILE, profile)
    rows = util.load_json(ROWS, {})
    rows["at"] = 0
    util.save_json(ROWS, rows)
    if send and value is not None and util.setting("kompas_trakt").lower() != "false" and tracker.active() is not None and tracker.name() == "Trakt":
        import trakt
        bucket = "movies" if kind == "movie" else "shows"
        try:
            trakt.call("sync/ratings", data={bucket: [{"rating": {2: 9, 1: 7, -1: 3}[value], "ids": {"tmdb": int(tmdb_id)}}]})
        except util.HttpError as error:
            util.log("rating to Trakt: %s" % error)


def history():
    """[(kind, id, weight)] of what you watched and rated, the most recent and best liked weighing most."""
    try:
        films, shows = tracker.watched_movies(), tracker.watched_episodes()
    except util.HttpError:
        films, shows = {}, {}
    recent_films = sorted(films, key=lambda i: films[i] or "", reverse=True)[:80]
    recent_shows = sorted(shows, key=lambda i: max(shows[i].values()) if shows[i] else "", reverse=True)[:50]
    out = {}
    for rank, tmdb_id in enumerate(recent_films):
        out[_key("movie", tmdb_id)] = 1.0 - 0.5 * rank / max(1, len(recent_films))
    for rank, tmdb_id in enumerate(recent_shows):
        out[_key("tvshow", tmdb_id)] = (0.6 + min(0.8, len(shows[tmdb_id]) / 10.0)) * (1.0 - 0.5 * rank / max(1, len(recent_shows)))
    for key, value in ratings().items():
        if value is None:
            continue
        out[key] = {2: 3.0, 1: 1.6, -1: -3.0}.get(value, 0) + max(0, out.get(key, 0)) * 0.3
    return [(k.split(":")[0], k.split(":")[1], w) for k, w in out.items()]


def build_profile():
    rows = history()
    found = features([(k, i) for k, i, _w in rows])
    facets = {name: {} for name in ("g", "k", "d", "w", "c", "l", "o", "dec")}
    names = {}
    pop_sum = pop_weight = 0.0
    top = None
    for kind, tmdb_id, weight in rows:
        info = found.get(_key(kind, tmdb_id))
        if not info:
            continue
        for facet in ("g", "k", "d", "w", "c"):
            for entry_id, name in info.get(facet) or []:
                key = str(entry_id)
                facets[facet][key] = facets[facet].get(key, 0) + weight
                names["%s:%s" % (facet, key)] = name
        if info.get("l"):
            facets["l"][info["l"]] = facets["l"].get(info["l"], 0) + weight
        for country in info.get("o") or []:
            facets["o"][country] = facets["o"].get(country, 0) + weight
        if info.get("y"):
            decade = str(info["y"] // 10 * 10)
            facets["dec"][decade] = facets["dec"].get(decade, 0) + weight
        if weight > 0:
            pop_sum += math.log10((info.get("v") or 0) + 1) * weight
            pop_weight += weight
            if top is None or weight > top[0]:
                top = (weight, info)
    for facet, values in facets.items():
        high = max([v for v in values.values() if v > 0] or [1])
        facets[facet] = {k: round(v / high, 3) for k, v in values.items() if abs(v / high) >= 0.05}
    profile = {"at": time.time(), "count": len([r for r in rows if r[2] > 0]), "facets": facets, "names": names,
               "pop": round(pop_sum / pop_weight, 2) if pop_weight else 3.0,
               "top": {"kind": top[1]["kind"], "id": top[1]["id"], "t": top[1]["t"], "pp": top[1].get("pp")} if top else None,
               "weights": {_key(k, i): round(w, 2) for k, i, w in rows}}
    util.save_json(PROFILE, profile)
    return profile


def profile(fresh=False):
    saved = util.load_json(PROFILE, {})
    if not fresh and saved.get("facets") and time.time() - saved.get("at", 0) < 12 * 3600:
        return saved
    return build_profile()


def needs_start():
    return profile().get("count", 0) < 3


# ------------------------------------------------------------------ how well a title suits you
def score(info, taste, seeds=0):
    """(score, [(weight, reason)])."""
    facets = taste.get("facets") or {}
    parts = []
    total = 0.0
    genres = [(facets.get("g", {}).get(str(i), 0), n) for i, n in info.get("g") or []]
    if genres:
        value = sum(v for v, _n in genres) / math.sqrt(len(genres))
        total += value
        liked = [n for v, n in sorted(genres, key=lambda x: -x[0]) if v > 0.3][:2]
        if liked:
            parts.append((value * 0.8, T("Jouw soort: %s", "Your kind: %s") % T(" en ", " and ").join(n.lower() if util.NL else n for n in liked)))
    themes = sorted(((facets.get("k", {}).get(str(i), 0), n) for i, n in info.get("k") or []), key=lambda x: -x[0])
    total += min(3.0, sum(v for v, _n in themes)) * 0.6
    if themes and themes[0][0] > 0.4 and not util.NL:
        parts.append((themes[0][0] * 1.2, "Because you love %s" % themes[0][1]))
    for facet, weight, nl, en in (("d", 2.5, "Van %s, die je vaak kiest", "From %s, whom you often choose"),
                                   ("w", 1.2, "Geschreven door %s, die je vaak kiest", "Written by %s, whom you often choose"),
                                   ("c", 0.8, "Met %s, die je vaak ziet", "With %s, whom you often watch")):
        best = max(((facets.get(facet, {}).get(str(i), 0), n) for i, n in info.get(facet) or []), default=(0, ""))
        total += best[0] * weight
        if best[0] > 0.35:
            parts.append((best[0] * weight, T(nl, en) % best[1]))
    total += facets.get("l", {}).get(info.get("l") or "", 0) * 0.6
    total += max([facets.get("o", {}).get(c, 0) for c in info.get("o") or []] or [0]) * 0.4
    if info.get("y"):
        total += facets.get("dec", {}).get(str(info["y"] // 10 * 10), 0) * 0.3
    total += min(seeds, 4) * 0.6
    total -= abs(math.log10((info.get("v") or 0) + 1) - (taste.get("pop") or 3.0)) * 0.25
    total += 0.15 * ((info.get("r") or 6.5) - 6.5)
    return total, parts


def reason_for(info, taste, seed=None):
    _value, parts = score(info, taste)
    if seed:
        rated = ratings().get(_key(*seed[:2]))
        line = (T("Omdat je %s geweldig vond", "Because you loved %s") if rated == 2 else
                T("Omdat je %s mooi vond", "Because you liked %s") if rated == 1 else T("Omdat je %s keek", "Because you watched %s")) % seed[2]
        return line
    if parts:
        return max(parts)[1]
    return T("Past bij wat je kijkt", "Suits what you watch")


# ------------------------------------------------------------------ resting picks
def _shown():
    return util.load_json(SHOWN, {})


def resting(data=None):
    data = _shown() if data is None else data
    now = time.time()
    return {k for k, v in data.items() if not v.get("o") and REST_AFTER < now - v.get("f", now) < REST_AFTER + REST_FOR}


def _mark_shown(keys):
    data = _shown()
    now = time.time()
    for key in [k for k, v in data.items() if now - v.get("f", now) > REST_AFTER + REST_FOR]:
        data.pop(key)                                   # rested long enough: may come back
    for key in keys:
        data.setdefault(key, {"f": now})
    util.save_json(SHOWN, data)


def opened(kind, tmdb_id):
    """A pick you opened or played never takes a rest."""
    try:
        data = _shown()
        key = _key(kind, tmdb_id)
        if key in data and not data[key].get("o"):
            data[key]["o"] = 1
            util.save_json(SHOWN, data)
    except Exception:          # noqa: BLE001 - never in the way of playing
        pass


# ------------------------------------------------------------------ candidates
def _results(path, kind, **params):
    try:
        return [(kind, str(r["id"])) for r in tmdb.get(path, ttl=DAY, **params).get("results") or [] if r.get("id")]
    except util.HttpError:
        return []


def _seen():
    try:
        return {_key("movie", i) for i in tracker.watched_movies()} | {_key("tvshow", i) for i in tracker.watched_episodes()}
    except util.HttpError:
        return set()


def _ranked(pool, taste, skip, limit=120):
    """pool: {key: number of seeds}. Returns [(score, info, parts, seeds)] best first."""
    keys = [k for k in pool if k not in skip][:limit * 2]
    found = features([tuple(k.split(":")) for k in keys][:limit])
    out = []
    import hide
    hidden = hide.languages()
    for key, info in found.items():
        if info.get("v", 0) < 20 or info.get("l") in hidden:
            continue
        value, parts = score(info, taste, pool.get(key, 0))
        out.append((value, info, parts, pool.get(key, 0)))
    out.sort(key=lambda r: -r[0])
    return out


def _latest():
    """The title you watched last (film or series)."""
    try:
        films, shows = tracker.watched_movies(), tracker.watched_episodes()
    except util.HttpError:
        return None
    best = None
    for tmdb_id, when in films.items():
        if ratings().get(_key("movie", tmdb_id)) != -1 and (best is None or (when or "") > best[0]):
            best = (when or "", _key("movie", tmdb_id))
    for tmdb_id, episodes in shows.items():
        when = max(episodes.values()) if episodes else ""
        if ratings().get(_key("tvshow", tmdb_id)) != -1 and (best is None or (when or "") > best[0]):
            best = (when or "", _key("tvshow", tmdb_id))
    return best[1] if best else None


def _seeds(taste, count=12):
    weights = taste.get("weights") or {}
    return [k for k, w in sorted(weights.items(), key=lambda kv: -kv[1]) if w > 0][:count]


def _recs(key):
    kind, tmdb_id = key.split(":")
    api = "movie" if kind == "movie" else "tv"
    return _results("%s/%s/recommendations" % (api, tmdb_id), kind)


def _row(entries):
    return [[r[1]["kind"], r[1]["id"], r[2]] for r in entries]


def build_rows(taste=None):
    taste = taste or profile(fresh=True)
    skip = _seen() | {k for k, v in ratings().items() if v is not None} | resting()
    seeds = _seeds(taste)
    pool, origin = {}, {}
    with ThreadPoolExecutor(max_workers=6) as executor:
        answers = list(executor.map(_recs, seeds))
    for seed, found in zip(seeds, answers):
        for kind, tmdb_id in found:
            key = _key(kind, tmdb_id)
            pool[key] = pool.get(key, 0) + 1
            origin.setdefault(key, seed)
    facets = taste.get("facets") or {}
    top_genres = [g for g, v in sorted((facets.get("g") or {}).items(), key=lambda kv: -kv[1]) if v > 0][:3]
    for api, kind in (("movie", "movie"), ("tv", "tvshow")):
        for kind_, tmdb_id in _results("discover/" + api, kind, sort_by="popularity.desc", include_adult="false",
                                       with_genres="|".join(top_genres), **{"vote_count.gte": 300}):
            pool.setdefault(_key(kind_, tmdb_id), 0)
    seed_info = features([tuple(s.split(":")) for s in seeds])
    ranked = _ranked(pool, taste, skip)
    rows = {}
    # picked for you: no more than three from the same seed, one per film series, one in five a stretch
    used, per_seed, collections, picks = set(), {}, set(), []
    stretch = [r for r in ranked[25:] if (r[1].get("r") or 0) >= 7 and not set(str(g) for g, _n in r[1].get("g") or []) & set(top_genres[:2])]
    random.shuffle(stretch)
    for entry in ranked:
        if len(picks) >= 30:
            break
        if len(picks) % 5 == 4 and stretch:
            other = stretch.pop()
            if _key(other[1]["kind"], other[1]["id"]) not in used:
                picks.append((other[0], other[1], T("Iets anders: een gok die je kan verrassen", "Something different: a stretch that may surprise you")))
                used.add(_key(other[1]["kind"], other[1]["id"]))
        key = _key(entry[1]["kind"], entry[1]["id"])
        seed = origin.get(key)
        if key in used or per_seed.get(seed, 0) >= 3 or (entry[1].get("col") and entry[1]["col"] in collections):
            continue
        per_seed[seed] = per_seed.get(seed, 0) + 1
        if entry[1].get("col"):
            collections.add(entry[1]["col"])
        used.add(key)
        seed_title = (seed_info.get(seed) or {}).get("t") if seed else ""
        line = reason_for(entry[1], taste, (seed.split(":")[0], seed.split(":")[1], seed_title) if seed_title and entry[3] >= 2 else None)
        picks.append((entry[0], entry[1], line))
    rows["kompas_foryou"] = [[p[1]["kind"], p[1]["id"], p[2]] for p in picks]
    # because you watched: the most recent title you liked
    recent = _latest()
    because = ""
    if recent:
        info = features([tuple(recent.split(":"))]).get(recent) or {}
        because = info.get("t") or ""
        near = {_key(k, i): 1 for k, i in _recs(recent)}
        line = T("Lijkt op %s", "Like %s") % because
        rows["kompas_because"] = [[r[1]["kind"], r[1]["id"], line] for r in _ranked(near, taste, skip, 40)][:20]
    # hidden gems
    gems = {}
    for api, kind in (("movie", "movie"), ("tv", "tvshow")):
        for page in (1, 2):
            for found in _results("discover/" + api, kind, sort_by="vote_average.desc", include_adult="false", page=page,
                                  with_genres="|".join(top_genres), **{"vote_count.gte": 60, "vote_count.lte": 1500, "vote_average.gte": 7.0}):
                gems.setdefault(_key(*found), 0)
    rows["kompas_gems"] = [[r[1]["kind"], r[1]["id"], T("Verborgen parel: weinig bekend, hoog gewaardeerd", "Hidden gem: little known, highly rated")]
                           for r in _ranked(gems, taste, skip, 60)][:20]
    # new for you: films only once they are out to stream or rent
    today = datetime.date.today()
    before = (today - datetime.timedelta(days=90)).isoformat()
    fresh = {}
    for found in _results("discover/movie", "movie", sort_by="popularity.desc", include_adult="false", region=tmdb.region(),
                          with_release_type="4|5", **{"release_date.gte": before, "release_date.lte": today.isoformat()}):
        fresh.setdefault(_key(*found), 0)
    for found in _results("discover/tv", "tvshow", sort_by="popularity.desc", include_adult="false",
                          **{"first_air_date.gte": before, "first_air_date.lte": today.isoformat()}):
        fresh.setdefault(_key(*found), 0)
    suits = [r for r in _ranked(fresh, taste, skip, 40) if r[0] > 0.8]
    rows["kompas_new"] = [[r[1]["kind"], r[1]["id"], T("Net uit · ", "Just out · ") + reason_for(r[1], taste)] for r in suits][:20] if len(suits) >= 5 else []
    trend = {}
    for found in _results("trending/movie/week", "movie") + _results("trending/tv/week", "tvshow"):
        trend.setdefault(_key(*found), 0)
    rows["kompas_trending"] = [[r[1]["kind"], r[1]["id"], T("Populair deze week · ", "Big this week · ") + reason_for(r[1], taste)]
                               for r in _ranked(trend, taste, skip, 40) if r[0] > 0][:20]
    _mark_shown([_key(k, i) for name in ROW_NAMES for k, i, _r in (rows.get(name) or [])[:15]])
    data = {"at": time.time(), "day": today.isoformat(), "rows": rows, "because": because}
    util.save_json(ROWS, data)
    publish(data)
    return data


def publish(data=None):
    data = data or util.load_json(ROWS, {})
    util.HOME.setProperty("lucent.video.kompas", "1" if on() else "")
    because = data.get("because") or ""
    util.HOME.setProperty("lucent.video.kompas.because", (T("Omdat je %s keek", "Because you watched %s") % because) if because else "")


def due():
    if not on() or not tmdb.key():
        return False
    data = util.load_json(ROWS, {})
    return data.get("day") != datetime.date.today().isoformat() or time.time() - data.get("at", 0) > DAY


def run():
    try:
        build_rows()
        import widgets
        widgets.bump()
    except Exception as error:      # noqa: BLE001 - the service must go on
        util.log("kompas: %s" % type(error).__name__, xbmc.LOGERROR)


def _with_reasons(entries):
    metas = tmdb.many([(k, i) for k, i, _r in entries])
    reasons = {_key(k, i): r for k, i, r in entries}
    for meta in metas:
        meta["reason"] = reasons.get(_key(meta["kind"], meta["tmdb"]), "")
    return metas


def row_titles(name, params):
    if not on():
        return []
    if name == "kompas_saved":
        return saved_titles(params.get("id"))
    data = util.load_json(ROWS, {})
    if not data.get("rows"):
        data = build_rows()
    entries = (data.get("rows") or {}).get(name) or []
    rest = resting()
    import kids
    return kids.keep(_with_reasons([e for e in entries if _key(e[0], e[1]) not in rest]))


# ------------------------------------------------------------------ the Kompas page
def discover(filters, page=1):
    """TMDB discover parameters for the page's choices: [(api, kind, params)]."""
    kind = filters.get("kind", "movie")
    mood = next((m for m in MOODS if m[0] == filters.get("mood")), None)
    today = datetime.date.today()
    out = []
    for api, lucent in (("movie", "movie"), ("tv", "tvshow")):
        if kind in ("movie", "tvshow") and lucent != kind:
            continue
        if kind == "anime" and lucent == "movie" and filters.get("anime_series_only"):
            continue
        params = {"include_adult": "false", "sort_by": "popularity.desc", "page": page,
                  "vote_count.gte": 60 if filters.get("gems") else (150 if lucent == "movie" else 80)}
        with_, without = [], []
        if kind == "anime":
            with_.append("16")
            params["with_original_language"] = "ja"
        elif kind == "doc":
            with_.append("99")
            without.append("35")
        elif mood:
            genres, avoid = mood[3] if lucent == "movie" else mood[4]
            with_.append(genres)
            without.append(avoid)
        tone = filters.get("tone", 0)
        if tone < 0:
            without.append("27,53,80")
            if not mood and kind in ("movie", "tvshow"):
                with_.append("35|10751|12|16" if lucent == "movie" else "35|10751|16")
        elif tone > 0:
            without.append("10751,16,35")
            if not mood and kind in ("movie", "tvshow"):
                with_.append("27|80|53|9648" if lucent == "movie" else "80|9648")
        if with_:
            params["with_genres"] = ",".join(with_)
        if without:
            keep_out = set(",".join(without).split(",")) - set(",".join(with_).replace("|", ",").split(","))
            if keep_out - {""}:
                params["without_genres"] = ",".join(sorted(keep_out - {""}))
        if filters.get("minutes"):
            params["with_runtime.lte"] = filters["minutes"]
        field = "primary_release_date" if lucent == "movie" else "first_air_date"
        if filters.get("newer"):
            params[field + ".gte"] = (today - datetime.timedelta(days=5 * 365)).isoformat()
        if filters.get("decade"):
            start = int(filters["decade"])
            params[field + ".gte"] = "%d-01-01" % start
            params[field + ".lte"] = "%d-12-31" % min(start + 9, today.year)
        params[field + ".lte"] = params.get(field + ".lte") or today.isoformat()
        if filters.get("gems"):
            params.update({"vote_count.lte": 1500, "vote_average.gte": 7.0, "sort_by": "vote_average.desc"})
        region = next((r for r in REGIONS if r[0] == filters.get("region")), None)
        if region:
            params["with_origin_country"] = region[3]
        if filters.get("family"):
            if lucent == "movie":
                params.update(certification_country="NL", **{"certification.lte": "12"})
            params["without_genres"] = ",".join(filter(None, [params.get("without_genres"), "27"]))
        if filters.get("complete") and lucent == "tvshow":
            params["with_status"] = "3|4"
        out.append(("discover/" + api, lucent, params))
    return out


def page_picks(filters, people, exclude, count=3):
    """Three titles for everyone on the couch, none of you saw, with a reason. Returns [meta]."""
    import pick
    films, shows = pick.seen_by(people)
    seen = {_key("movie", i) for i in films} | {_key("tvshow", i) for i in shows}
    tastes = []
    for person in people:
        util.OVERRIDE_USER = person
        try:
            tastes.append(profile())
            seen |= {k for k, v in ratings().items() if v == -1}
        finally:
            util.OVERRIDE_USER = None
    pool = {}
    if filters.get("award"):
        import browse
        name, kind, winners = browse.AWARDS[filters["award"]]
        for page in (1, 2, 3):
            for meta in browse.award_titles(filters["award"], page)[0]:
                pool.setdefault(_key(meta["kind"], meta["tmdb"]), 0)
    else:
        for path, kind, params in discover(filters):
            try:
                first = tmdb.get(path, ttl=12 * 3600, **params)
            except util.HttpError:
                continue
            pages = min(int(first.get("total_pages") or 1), 8)
            rows = list(first.get("results") or [])
            for page in random.sample(range(2, pages + 1), min(2, max(0, pages - 1))):
                params = dict(params, page=page)
                try:
                    rows += tmdb.get(path, ttl=12 * 3600, **params).get("results") or []
                except util.HttpError:
                    pass
            for row in rows:
                pool.setdefault(_key(kind, row["id"]), 0)
    keys = [k for k in pool if k not in seen and k not in exclude]
    random.shuffle(keys)
    found = features([tuple(k.split(":")) for k in keys[:45]])
    scored = []
    for key, info in found.items():
        if filters.get("complete") and info["kind"] == "tvshow" and info.get("st") not in ("Ended", "Canceled"):
            continue
        values = [score(info, taste) for taste in tastes] or [(0, [])]
        value = sum(v[0] for v in values) / len(values)
        parts = [p for v in values for p in v[1]]
        scored.append((value, info, parts))
    scored.sort(key=lambda r: -r[0])
    top = scored[:9]
    chosen = []
    while top and len(chosen) < count + 3:                  # a few extra: some may be hidden below            # the best ones are the most likely, but not always the same three
        weights = [max(0.05, r[0] - (top[-1][0] - 0.5)) for r in top]
        entry = random.choices(top, weights=weights)[0]
        top.remove(entry)
        chosen.append(entry)
    out = []
    for value, info, parts in chosen:
        meta = tmdb.details(info["kind"], info["id"])
        if not meta:
            continue
        if len(people) > 1:
            meta["reason"] = T("Past bij jullie allemaal", "Suits all of you") if value > 0.5 else T("Niemand van jullie zag dit al", "None of you saw this yet")
        elif filters.get("gems"):
            meta["reason"] = T("Verborgen parel: weinig bekend, hoog gewaardeerd", "Hidden gem: little known, highly rated")
        else:
            meta["reason"] = max(parts)[1] if parts else T("Past bij wat je kiest", "Suits what you chose")
        out.append(meta)
    import hide
    import kids
    return kids.keep(hide.keep(out, "kompas_foryou"))[:count]


def save_row(filters, label):
    data = util.load_json(SAVED, {"rows": []})
    number = max([r["id"] for r in data["rows"]] or [0]) + 1
    data["rows"].append({"id": number, "label": label, "filters": filters})
    util.save_json(SAVED, data)
    return number


def saved_rows():
    return util.load_json(SAVED, {"rows": []})["rows"]


def saved_titles(number):
    entry = next((r for r in saved_rows() if str(r["id"]) == str(number)), None)
    if not entry:
        return []
    store = util.load_json(ROWS, {})
    key = "saved:%s" % number
    cached = (store.get("saved") or {}).get(key)
    if cached and time.time() - cached.get("at", 0) < DAY:
        return _with_reasons(cached["items"])
    metas = []
    seen_keys = set()
    for _round in range(4):
        for meta in page_picks(entry["filters"], [users.current_id()], seen_keys, 6):
            seen_keys.add(_key(meta["kind"], meta["tmdb"]))
            metas.append(meta)
        if len(metas) >= 20:
            break
    items = [[m["kind"], m["tmdb"], m.get("reason") or ""] for m in metas]
    store.setdefault("saved", {})[key] = {"at": time.time(), "items": items}
    util.save_json(ROWS, store)
    return metas


# ------------------------------------------------------------------ after a film
def after_film(meta):
    if not on() or util.setting("kompas_rate").lower() == "false":
        return
    if ratings().get(_key("movie", meta["tmdb"])) is not None:
        return

    def ask():
        if xbmc.Monitor().waitForAbort(4) or xbmc.Player().isPlayingVideo():
            return
        import kompasui
        kompasui.rate_after(meta)
    threading.Thread(target=ask, daemon=True).start()


# ------------------------------------------------------------------ actions
def action(name, params):
    import kompasui
    if name == "kompas_page":
        return kompasui.open_page()
    if name == "kompas_taste":
        return kompasui.open_taste()
    if name == "kompas_start":
        return kompasui.open_start()
    if name == "kompas_rate":
        return kompasui.rate_one(params.get("type", "movie"), params["tmdb"])
    if name == "kompas_build":
        build_rows()
        return util.notify(T("Kompas is bijgewerkt", "Kompas is updated"))
    if name == "kompas_unsave":
        data = util.load_json(SAVED, {"rows": []})
        data["rows"] = [r for r in data["rows"] if str(r["id"]) != str(params.get("id"))]
        util.save_json(SAVED, data)
        return xbmc.executebuiltin("Container.Refresh")
    if name == "kompas_forget":
        return kompasui.forget()
    return None
