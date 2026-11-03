# -*- coding: utf-8 -*-
"""Artwork and cast from TMDb for titles Seren has no pictures of (yet).

A series or film added straight from a page (quick.py) is written before Seren has synced it, so its .nfo had no
poster, backdrop or logo and Kodi showed a folder icon until you refreshed it by hand. These helpers fill the gap;
the answers are kept 14 days in tmdb/art.json.
"""
import os
import time

import tmdbwidgets as tw

CACHE = os.path.join(tw.DIR, "art.json")
TTL = 14 * 86400
_BUDGET = {"left": 40}              # TMDb asks per library run (the rest come next run)


def _img(path, size="original"):
    return f"{tw.IMG}{size}{path}" if path else ""


def _logo(images):
    logos = (images or {}).get("logos") or []
    lang = "nl" if tw.NL else "en"
    for want in (lang, "en", None):
        for item in logos:
            if item.get("iso_639_1") == want and item.get("file_path", "").endswith(".png"):
                return _img(item["file_path"])
    return _img(logos[0]["file_path"]) if logos else ""


def _cached(key):
    data = tw.read_json(CACHE, {}) or {}
    hit = data.get(key)
    if hit and time.time() - hit.get("t", 0) < TTL:
        return hit
    return None


def _store(key, value):
    data = tw.read_json(CACHE, {}) or {}
    value["t"] = time.time()
    data[key] = value
    if len(data) > 3000:                                     # keep the file small: drop the oldest
        for k in sorted(data, key=lambda k: data[k].get("t", 0))[:500]:
            data.pop(k, None)
    try:
        os.makedirs(tw.DIR, exist_ok=True)
        tw.write_json(CACHE, data)
    except Exception:  # noqa: BLE001
        pass
    return value


def _ask():
    if _BUDGET["left"] <= 0:
        return False
    _BUDGET["left"] -= 1
    return True


def reset_budget(n=40):
    _BUDGET["left"] = n


def show(tmdb_id, episodes=True):
    """{'art': {...}, 'season_art': {n: {'poster': url}}, 'cast': [...], 'stills': {'S01E01': url}} or {}."""
    if not tmdb_id:
        return {}
    key = f"tv{tmdb_id}{'e' if episodes else ''}"
    hit = _cached(key)
    if hit:
        return hit
    if not _ask():
        return {}
    d = tw.tmdb_get(f"tv/{tmdb_id}", append_to_response="images,aggregate_credits",
                    include_image_language=f"{'nl,' if tw.NL else ''}en,null")
    if not d:
        return {}
    art = {"poster": _img(d.get("poster_path"), "w780"), "fanart": _img(d.get("backdrop_path")),
           "landscape": _img(d.get("backdrop_path"), "w1280"), "clearlogo": _logo(d.get("images"))}
    art = {k: v for k, v in art.items() if v}
    seasons, stills = {}, {}
    for s in d.get("seasons") or []:
        n = s.get("season_number") or 0
        if n > 0 and s.get("poster_path"):
            seasons[str(n)] = {"poster": _img(s["poster_path"], "w500")}
    if episodes:
        for s in (d.get("seasons") or [])[:20]:
            n = s.get("season_number") or 0
            if n <= 0:
                continue
            sd = tw.tmdb_get(f"tv/{tmdb_id}/season/{n}") or {}
            for ep in sd.get("episodes") or []:
                if ep.get("still_path"):
                    stills[f"S{n:02d}E{int(ep.get('episode_number') or 0):02d}"] = _img(ep["still_path"], "w780")
    cast = [{"name": c.get("name"), "role": ((c.get("roles") or [{}])[0]).get("character", ""),
             "thumbnail": _img(c.get("profile_path"), "w185")} for c in ((d.get("aggregate_credits") or {}).get("cast") or [])[:25]]
    return _store(key, {"art": art, "season_art": seasons, "cast": cast, "stills": stills})


def movie(tmdb_id):
    """{'art': {...}, 'cast': [...]} or {}."""
    if not tmdb_id:
        return {}
    key = f"mv{tmdb_id}"
    hit = _cached(key)
    if hit:
        return hit
    if not _ask():
        return {}
    d = tw.tmdb_get(f"movie/{tmdb_id}", append_to_response="images,credits",
                    include_image_language=f"{'nl,' if tw.NL else ''}en,null")
    if not d:
        return {}
    art = {"poster": _img(d.get("poster_path"), "w780"), "fanart": _img(d.get("backdrop_path")),
           "landscape": _img(d.get("backdrop_path"), "w1280"), "clearlogo": _logo(d.get("images"))}
    cast = [{"name": c.get("name"), "role": c.get("character", ""), "thumbnail": _img(c.get("profile_path"), "w185")}
            for c in ((d.get("credits") or {}).get("cast") or [])[:25]]
    return _store(key, {"art": {k: v for k, v in art.items() if v}, "cast": cast})


def fill_show(show_dict, details=None):
    """Seren gave no poster: take TMDb's. details (trakt id -> (info, art)) gets episode stills where it has none."""
    if (show_dict.get("art") or {}).get("poster") or not show_dict.get("tmdb_id"):
        return False
    extra = show(show_dict["tmdb_id"])
    if not extra:
        return False
    show_dict["art"] = dict(extra.get("art") or {}, **{k: v for k, v in (show_dict.get("art") or {}).items() if v})
    if not show_dict.get("season_art"):
        show_dict["season_art"] = {int(k): v for k, v in (extra.get("season_art") or {}).items()}
    if not show_dict.get("cast"):
        show_dict["cast"] = extra.get("cast") or []
    show_dict["stills"] = extra.get("stills") or {}
    return True
