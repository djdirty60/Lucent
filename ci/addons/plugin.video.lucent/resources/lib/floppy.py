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


def check():
    if not available():
        return False, util.T("Vul eerst het adres en de token in.", "Enter the address and token first.")
    try:
        util.http(_base() + "/api/v1/media?limit=1", headers=_head())
    except util.HttpError as error:
        return False, util.T("Geen verbinding: %s", "No connection: %s") % error
    return True, util.T("Verbonden met Floppy.", "Connected to Floppy.")
