# -*- coding: utf-8 -*-
"""Titles, pictures and episode data from TMDB, in one simple shape."""
from concurrent.futures import ThreadPoolExecutor
import datetime
import urllib.parse

import apikeys
import util

API = "https://api.themoviedb.org/3/"
IMG = "https://image.tmdb.org/t/p/"
DAY = 86400


def key():
    return apikeys.tmdb()


def lang():
    return "nl-NL" if util.NL else "en-US"


def get(path, ttl=DAY, language=None, **params):
    params.update(api_key=key(), language=language or lang())
    url = API + path + "?" + urllib.parse.urlencode(sorted(params.items()))
    cached = util.cache_get("tmdb" + url, ttl)
    if cached is not None:
        return cached
    data, _ = util.http(url)
    util.cache_set("tmdb" + url, data)
    return data


def image(path, size):
    return IMG + size + path if path else ""


def _gallery(images, key, size, limit=20):
    """All choices of one kind of picture, own language first, then English, then without text, then the rest."""
    wanted = "nl" if util.NL else "en"
    rank = {wanted: 0, "en": 1, None: 2}
    rows = [i for i in (images or {}).get(key) or [] if i.get("file_path") and not i["file_path"].endswith(".svg")]
    rows.sort(key=lambda i: (rank.get(i.get("iso_639_1"), 3), -(i.get("vote_average") or 0)))
    return [image(i["file_path"], size) for i in rows[:limit]]


def _logo(images):
    logos = (images or {}).get("logos") or []
    wanted = "nl" if util.NL else "en"
    for code in (wanted, "en", None):
        for logo in logos:
            if logo.get("iso_639_1") == code and not (logo.get("file_path") or "").endswith(".svg"):
                return image(logo["file_path"], "w500")
    return ""


def _year(text):
    return int(text[:4]) if text and text[:4].isdigit() else 0


def aired(date):
    return bool(date) and date <= datetime.date.today().isoformat()


def _mpaa(raw, movie):
    wanted = ("NL", "US")
    if movie:
        table = {r.get("iso_3166_1"): [d.get("certification") for d in r.get("release_dates") or [] if d.get("certification")]
                 for r in (raw.get("release_dates") or {}).get("results") or []}
    else:
        table = {r.get("iso_3166_1"): [r.get("rating")] for r in (raw.get("content_ratings") or {}).get("results") or [] if r.get("rating")}
    for country in wanted:
        if table.get(country):
            return table[country][0]
    return ""


def _digital(raw):
    """The first day a film could be streamed, rented or bought (digital, disc or TV release), as YYYY-MM-DD.
    Without such a date: the cinema date plus 120 days, because older films often have no digital date on TMDB."""
    found, cinema = [], []
    for country in (raw.get("release_dates") or {}).get("results") or []:
        for entry in country.get("release_dates") or []:
            day = (entry.get("release_date") or "")[:10]
            if not day:
                continue
            if entry.get("type") in (4, 5, 6):
                found.append(day)
            elif entry.get("type") in (2, 3):
                cinema.append(day)
    if found:
        return min(found)
    first = min(cinema) if cinema else (raw.get("release_date") or "")
    if not first:
        return ""
    try:
        return (datetime.date.fromisoformat(first) + datetime.timedelta(days=120)).isoformat()
    except ValueError:
        return ""


def _trailer(raw):
    videos = [v for v in (raw.get("videos") or {}).get("results") or [] if v.get("site") == "YouTube" and v.get("key")]
    videos.sort(key=lambda v: v.get("type") != "Trailer")
    return "plugin://plugin.video.youtube/play/?video_id=%s" % videos[0]["key"] if videos else ""


def _english(raw, field):
    for row in (raw.get("translations") or {}).get("translations") or []:
        if row.get("iso_639_1") == "en" and (row.get("data") or {}).get(field):
            return row["data"][field]
    return ""


def details(kind, tmdb_id):
    """kind: movie or tvshow. Returns the normalised title, or None."""
    api_kind = "movie" if kind == "movie" else "tv"
    extra = {"append_to_response": "external_ids,images,credits,release_dates,content_ratings,videos,translations",
             "include_image_language": "nl,en,null,de,fr,es,it"}
    try:
        raw = get("%s/%s" % (api_kind, tmdb_id), ttl=7 * DAY, **extra)
    except util.HttpError as error:
        util.log("details failed: %s" % error)
        return None
    movie = kind == "movie"
    if not raw.get("overview"):
        raw["overview"] = _english(raw, "overview")       # in the same answer: no second request
    if not raw.get("tagline"):
        raw["tagline"] = _english(raw, "tagline")
    crew = raw.get("credits") or {}
    date = raw.get("release_date" if movie else "first_air_date") or ""
    runtimes = raw.get("episode_run_time") or [0]
    return {
        "kind": kind,
        "tmdb": str(raw["id"]),
        "imdb": raw.get("imdb_id") or (raw.get("external_ids") or {}).get("imdb_id") or "",
        "title": raw.get("title" if movie else "name") or "",
        "original_title": raw.get("original_title" if movie else "original_name") or "",
        "year": _year(date),
        "premiered": date,
        "plot": raw.get("overview") or "",
        "tagline": raw.get("tagline") or "",
        "poster": image(raw.get("poster_path"), "w500"),
        "fanart": image(raw.get("backdrop_path"), "w1280"),
        "logo": _logo(raw.get("images")),
        "gallery": {"poster": _gallery(raw.get("images"), "posters", "w500"), "clearlogo": _gallery(raw.get("images"), "logos", "w500"),
                    "fanart": _gallery(raw.get("images"), "backdrops", "w1280"),
                    "landscape": [image(i["file_path"], "w1280") for i in (raw.get("images") or {}).get("backdrops") or []
                                  if i.get("iso_639_1") and i.get("file_path")][:10]},
        "rating": raw.get("vote_average") or 0,
        "votes": raw.get("vote_count") or 0,
        "genres": [g["name"] for g in raw.get("genres") or []],
        "studios": [s["name"] for s in (raw.get("production_companies") or raw.get("networks") or [])[:3]],
        "runtime": (raw.get("runtime") if movie else runtimes[0]) or 0,
        "seasons": [s for s in raw.get("seasons") or [] if s.get("season_number", 0) > 0],
        "episodes": raw.get("number_of_episodes") or 0,
        "tvdb": str((raw.get("external_ids") or {}).get("tvdb_id") or ""),
        "mpaa": _mpaa(raw, movie),
        "trailer": _trailer(raw),
        "set": (raw.get("belongs_to_collection") or {}).get("name") or "",
        "lang": raw.get("original_language") or "",
        "digital": _digital(raw) if movie else date,
        "cast": [{"id": c.get("id"), "name": c["name"], "role": c.get("character") or "", "thumb": image(c.get("profile_path"), "w185")}
                 for c in crew.get("cast") or []][:25],
        "directors": [c["name"] for c in crew.get("crew") or [] if c.get("job") == "Director"],
        "writers": [c["name"] for c in crew.get("crew") or [] if c.get("department") == "Writing"][:6],
    }


def many(pairs):
    """Details of many (kind, id) pairs at once, in the same order, skipping failures."""
    with ThreadPoolExecutor(max_workers=8) as pool:
        return [m for m in pool.map(lambda p: details(p[0], p[1]), pairs) if m]


def listing(path, kind, page=1, **params):
    """A TMDB list page: (titles, more pages?)."""
    data = get(path, ttl=6 * 3600, page=page, **params)
    titles = many([(kind, r["id"]) for r in data.get("results") or []])
    return titles, page < min(data.get("total_pages") or 1, 500)


def find(kind, imdb=None, tvdb=None):
    """The TMDB id for an IMDb or TVDB id, or None."""
    key_name = "movie_results" if kind == "movie" else "tv_results"
    for source, value in (("imdb_id", imdb), ("tvdb_id", tvdb)):
        if not value:
            continue
        try:
            rows = get("find/%s" % value, ttl=30 * DAY, external_source=source).get(key_name) or []
        except util.HttpError:
            continue
        if rows:
            return rows[0]["id"]
    return None


def on_air(tmdb_id):
    """(last aired, next to air) episodes of a series, as dicts or None."""
    raw = get("tv/%s" % tmdb_id, ttl=6 * 3600)
    return raw.get("last_episode_to_air"), raw.get("next_episode_to_air")


def person_titles(person, page_size=40):
    """Best-known films and series of one person: [(kind, id)]."""
    credits_ = get("person/%s/combined_credits" % person, ttl=7 * DAY).get("cast") or []
    credits_.sort(key=lambda c: c.get("popularity") or 0, reverse=True)
    pairs, seen = [], set()
    for row in credits_:
        kind = {"movie": "movie", "tv": "tvshow"}.get(row.get("media_type"))
        if kind and row.get("id") not in seen:
            seen.add(row["id"])
            pairs.append((kind, row["id"]))
    return pairs[:page_size]


def region():
    """The country the streaming services are read for."""
    chosen = util.setting("watch_region").upper()
    return chosen or ("NL" if util.NL else "US")


def upcoming(kind, page=1, size=20):
    """Films or series that are still to come: nothing already out, the first release date first. (titles, more?)"""
    today = datetime.date.today()
    later = (today + datetime.timedelta(days=365)).isoformat()
    api, field = ("movie", "primary_release_date") if kind == "movie" else ("tv", "first_air_date")
    params = {field + ".gte": (today + datetime.timedelta(days=1)).isoformat(), field + ".lte": later,
              "sort_by": "popularity.desc", "include_adult": "false"}
    if kind == "movie":
        params.update(region=region(), with_release_type="2|3|4")
    rows = []
    for number in range(1, 6):              # the 100 most awaited, then sorted by date
        data = get("discover/" + api, ttl=12 * 3600, page=number, **params)
        rows += data.get("results") or []
        if number >= (data.get("total_pages") or 1):
            break
    date_key = "release_date" if kind == "movie" else "first_air_date"
    rows = [r for r in rows if (r.get(date_key) or "") > today.isoformat()]
    rows.sort(key=lambda r: r.get(date_key) or "9999")
    part = rows[(page - 1) * size:page * size]
    return [m for m in many([(kind, r["id"]) for r in part])], len(rows) > page * size


def new_series(page=1, size=20, days=120):
    """Series that started in the last months, the newest start first. (titles, more?)"""
    today = datetime.date.today()
    params = {"first_air_date.gte": (today - datetime.timedelta(days=days)).isoformat(), "first_air_date.lte": today.isoformat(),
              "sort_by": "popularity.desc", "include_adult": "false", "include_null_first_air_dates": "false",
              "without_genres": "10763,10767"}            # no news or talk shows
    rows = []
    for number in range(1, 6):              # the 100 most watched new series, then sorted by date
        data = get("discover/tv", ttl=6 * 3600, page=number, **params)
        rows += data.get("results") or []
        if number >= (data.get("total_pages") or 1):
            break
    rows = [r for r in rows if r.get("first_air_date") and r["first_air_date"] <= today.isoformat()]
    rows.sort(key=lambda r: r["first_air_date"], reverse=True)
    part = rows[(page - 1) * size:page * size]
    return many([("tvshow", r["id"]) for r in part]), len(rows) > page * size


def providers():
    """Streaming services of your country, most popular first: [(id, name, logo)]."""
    found = {}
    for api in ("movie", "tv"):
        for row in get("watch/providers/%s" % api, ttl=7 * DAY, watch_region=region()).get("results") or []:
            entry = found.setdefault(row["provider_id"], (row.get("display_priorities", {}).get(region(), row.get("display_priority", 999)), row["provider_name"], row.get("logo_path")))
            if row.get("display_priority", 999) < entry[0]:
                found[row["provider_id"]] = (row.get("display_priority", 999), entry[1], entry[2])
    return [(pid, name, image(logo, "w500")) for pid, (_, name, logo) in sorted(found.items(), key=lambda item: item[1][0])]


def newest_on(provider, kind, page=1):
    """What a service offers, newest release first and nothing that is yet to come. kind: movie, tvshow or all."""
    today = datetime.date.today().isoformat()
    base = {"with_watch_providers": provider, "watch_region": region(), "with_watch_monetization_types": "flatrate", "include_adult": "false"}
    if kind == "all":
        films, more_films = newest_on(provider, "movie", page)
        shows, more_shows = newest_on(provider, "tvshow", page)
        return sorted(films + shows, key=lambda m: m.get("premiered") or "", reverse=True), more_films or more_shows
    if kind == "movie":
        titles, more = listing("discover/movie", "movie", page, sort_by="primary_release_date.desc", **dict(base, **{"primary_release_date.lte": today}))
    else:
        titles, more = listing("discover/tv", "tvshow", page, sort_by="first_air_date.desc", **dict(base, **{"first_air_date.lte": today}))
    return sorted(titles, key=lambda m: m.get("premiered") or "", reverse=True), more


def season(tmdb_id, number):
    return get("tv/%s/season/%s" % (tmdb_id, number), ttl=6 * 3600)


def episode_meta(show, raw):
    return {
        "kind": "episode",
        "tmdb": show["tmdb"],
        "imdb": show["imdb"],
        "tvdb": show.get("tvdb", ""),
        "tmdb_episode": str(raw.get("id") or ""),
        "tvshow_fanart": show["fanart"],
        "mpaa": show.get("mpaa", ""),
        "cast": show.get("cast") or [],
        "show": show["title"],
        "title": raw.get("name") or "",
        "season": raw["season_number"],
        "episode": raw["episode_number"],
        "premiered": raw.get("air_date") or "",
        "year": _year(raw.get("air_date")),
        "plot": raw.get("overview") or "",
        "poster": show["poster"],
        "fanart": show["fanart"],
        "logo": show["logo"],
        "thumb": image(raw.get("still_path"), "w780") or show["fanart"],
        "rating": raw.get("vote_average") or 0,
        "votes": raw.get("vote_count") or 0,
        "genres": show["genres"],
        "studios": show["studios"],
        "runtime": raw.get("runtime") or show["runtime"],
    }


def next_episode(tmdb_id, season_number, episode_number):
    """The aired episode after this one as {season, episode}, or None."""
    this = season(tmdb_id, season_number)
    for raw in this.get("episodes") or []:
        if raw["episode_number"] == episode_number + 1:
            return {"season": season_number, "episode": raw["episode_number"]} if aired(raw.get("air_date")) else None
    show = details("tvshow", tmdb_id)
    if show and any(s["season_number"] == season_number + 1 for s in show["seasons"]):
        first = (season(tmdb_id, season_number + 1).get("episodes") or [{}])[0]
        if first and aired(first.get("air_date")):
            return {"season": season_number + 1, "episode": first["episode_number"]}
    return None
