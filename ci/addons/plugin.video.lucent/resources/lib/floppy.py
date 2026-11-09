# -*- coding: utf-8 -*-
"""Floppy: receives what you watch, next to your Trakt or Simkl account. The address and token are never logged."""
import util


def _base():
    return util.setting("floppy_url").rstrip("/")


def _token():
    return util.setting("floppy_token")


def available():
    return bool(_base() and _token())


def _head():
    return {"X-API-Key": _token()}


def scrobble(state, meta, position, total):
    if not available() or not total:
        return
    body = {"action": state, "media_type": "movie" if meta.get("kind") == "movie" else "episode", "ids": {"tmdb": str(meta["tmdb"])},
            "title": meta.get("title") or "", "position_seconds": int(position), "duration_seconds": int(total)}
    if meta.get("imdb"):
        body["ids"]["imdb"] = meta["imdb"]
    if body["media_type"] == "episode":
        body.update(season_number=int(meta["season"]), episode_number=int(meta["episode"]))
    try:
        util.http(_base() + "/api/v1/scrobble", data=body, headers=_head())
    except util.HttpError as error:
        util.log("Floppy %s: %s" % (state, error))


def lists():
    """Your Floppy lists: [(id, name)]."""
    answer, _ = util.http(_base() + "/api/v1/lists?limit=200", headers=_head())
    return [(row["id"], row.get("name") or "") for row in (answer or {}).get("results") or [] if row.get("id")]


def items(list_id, page, size):
    """Returns ([(kind, tmdb id)], more pages?). Films and series from TMDB only: other things cannot be played."""
    start = (page - 1) * size
    answer, _ = util.http("%s/api/v1/lists/%s/items?limit=%d&offset=%d" % (_base(), list_id, size, start), headers=_head())
    answer = answer or {}
    kinds = {"movie": "movie", "tv": "tvshow"}
    pairs = []
    for row in answer.get("results") or []:
        item = row.get("item") or {}
        if item.get("source") == "tmdb" and item.get("media_type") in kinds and item.get("media_id"):
            pairs.append((kinds[item["media_type"]], str(item["media_id"])))
    total = (answer.get("pagination") or {}).get("total") or 0
    return pairs, start + size < total


def check():
    if not available():
        return False, util.T("Vul eerst het adres en de token in.", "Enter the address and token first.")
    try:
        util.http(_base() + "/api/v1/media?limit=1", headers=_head())
    except util.HttpError as error:
        return False, util.T("Geen verbinding: %s", "No connection: %s") % error
    return True, util.T("Verbonden met Floppy.", "Connected to Floppy.")
