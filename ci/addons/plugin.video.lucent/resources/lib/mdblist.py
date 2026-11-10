# -*- coding: utf-8 -*-
"""MDBList: smart lists, and scores from IMDb, Rotten Tomatoes, Metacritic and more. Needs your own free API key."""
from concurrent.futures import ThreadPoolExecutor
import json
import urllib.parse

import util

API = "https://api.mdblist.com/"
WEEK = 7 * 86400
BATCH = 200
SOURCES = {"imdb": "imdb", "metacritic": "metacritic", "metacriticuser": "metacriticuser", "tomatoes": "tomatoes", "popcorn": "popcorn",
           "letterboxd": "letterboxd", "trakt": "trakt", "rogerebert": "rogerebert", "myanimelist": "myanimelist"}


def key():
    return util.setting("mdblist_key")


def available():
    return bool(key())


def _url(path, **params):
    params["apikey"] = key()
    return API + path + "?" + urllib.parse.urlencode(params)


def lists(kind, query=None):
    """kind: mine, liked, top or search. [(id, name)]"""
    path = {"mine": "lists/user", "liked": "lists/liked", "top": "lists/top", "search": "lists/search"}[kind]
    extra = {"query": query} if kind == "search" else {}
    cached_key = "mdblist" + path + (query or "")
    data = util.cache_get(cached_key, 900)
    if data is None:
        data, _ = util.http(_url(path, **extra))
        util.cache_set(cached_key, data)
    rows = data.get("lists") or [] if isinstance(data, dict) else data or []
    return [(row["id"], row.get("name") or "") for row in rows if row.get("id")]


def items(list_id, page, size):
    """Returns ([(kind, tmdb id)], more pages?)."""
    data, head = util.http(_url("lists/%s/items" % list_id, limit=size, offset=(page - 1) * size))
    pairs = [("movie", str(r["id"])) for r in (data or {}).get("movies") or [] if r.get("id")]
    pairs += [("tvshow", str(r["id"])) for r in (data or {}).get("shows") or [] if r.get("id")]
    return pairs, str(head.get("X-Has-More", "")).lower() == "true"


def _parse(entry):
    scores = {}
    for rating in entry.get("ratings") or []:
        source = SOURCES.get(str(rating.get("source") or "").lower())
        value = rating.get("score")
        if value is None:
            value = rating.get("value")
            value = float(value) * 10 if value is not None and source == "imdb" else value
        if source and value:
            scores[source] = (round(float(value) / 10.0, 1), int(rating.get("votes") or 0))
    return {"scores": scores, "average": entry.get("score_average") or 0, "trakt": str((entry.get("ids") or {}).get("trakt") or "")}


def _fetch(kind, ids):
    media = "movie" if kind == "movie" else "show"
    for start in range(0, len(ids), BATCH):
        part = ids[start:start + BATCH]
        try:
            answer, _ = util.http(_url("tmdb/%s" % media), data={"ids": part})
        except util.HttpError as error:
            util.log("MDBList: %s" % error)
            return
        for entry in answer or []:
            tmdb_id = str((entry.get("ids") or {}).get("tmdb") or "")
            if tmdb_id:
                util.cache_set("mdbscore%s%s" % (kind, tmdb_id), _parse(entry))


def enrich(titles):
    """Adds meta['scores'] (source -> (0-10 score, votes)) and meta['mdb_average'] to films and series."""
    if not available():
        return
    targets = [t for t in titles if t["kind"] in ("movie", "tvshow")]
    missing = {"movie": [], "tvshow": []}
    for meta in targets:
        if util.cache_get("mdbscore%s%s" % (meta["kind"], meta["tmdb"]), WEEK) is None:
            missing[meta["kind"]].append(str(meta["tmdb"]))
    jobs = [(k, v) for k, v in missing.items() if v]
    if jobs:
        with ThreadPoolExecutor(max_workers=2) as pool:
            list(pool.map(lambda job: _fetch(*job), jobs))
    for meta in targets:
        found = util.cache_get("mdbscore%s%s" % (meta["kind"], meta["tmdb"]), WEEK)
        if found:
            meta["scores"] = {k: tuple(v) for k, v in found["scores"].items()}
            meta["mdb_average"] = found["average"]
            if found.get("trakt"):
                meta["trakt_id"] = found["trakt"]


def check():
    if not available():
        return False, util.T("Vul eerst je MDBList-sleutel in.", "Enter your MDBList key first.")
    try:
        answer, _ = util.http(_url("user"))
    except util.HttpError as error:
        return False, util.T("Geen verbinding: %s", "No connection: %s") % error
    return True, util.T("Verbonden als %s.", "Connected as %s.") % json.dumps((answer or {}).get("username") or "?").strip('"')
