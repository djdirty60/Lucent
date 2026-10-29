# -*- coding: utf-8 -*-
"""Lucent: "Tonight for you" - a row on Home that fits the moment of the day.

Run by the Lucent helper (helper.py) once a minute. Every few hours, and whenever the part of
the day changes, it looks at what you watched last on Trakt (through Seren's login), asks TMDB for titles like
those, leaves out what you have seen and fills Window(home).Property(lucent.fy.*):

  morning   series            afternoon  series and films      evening / night  films
  weekend daytime: series to binge

Without Trakt it falls back to what is trending this week on TMDB. A click opens the title's own page
(info.py open), Play there goes to Seren.
"""
import datetime
import json
import random
import time
import urllib.parse

import xbmc
import xbmcgui
import xbmcvfs

import info

HOME = xbmcgui.Window(10000)
P = "lucent.fy."
MAX = 12
REFRESH = 3 * 3600
_LAST_TRY = [0.0]
CACHE = "special://profile/addon_data/skin.lucent/foryou.json"
_NL = xbmc.getLanguage(xbmc.ISO_639_1) == "nl"
TX = {
    "morning": ("This morning for you", "Vanochtend voor jou"),
    "afternoon": ("This afternoon for you", "Vanmiddag voor jou"),
    "evening": ("Tonight for you", "Vanavond voor jou"),
    "night": ("Tonight for you", "Vannacht voor jou"),
    "weekend": ("This weekend for you", "Dit weekend voor jou"),
    "because": ("Because you watched {0}", "Omdat je {0} keek"),
    "trending": ("Popular this week", "Populair deze week"),
}


def t(key, *args):
    text = TX[key][1 if _NL else 0]
    return text.format(*args) if args else text


def log(text):
    xbmc.log(f"[skin.lucent] foryou: {text}", xbmc.LOGINFO)


def daypart(now=None):
    now = now or datetime.datetime.now()
    h = now.hour
    if now.weekday() >= 5 and 9 <= h < 18:
        return "weekend"
    if 6 <= h < 12:
        return "morning"
    if 12 <= h < 18:
        return "afternoon"
    if 18 <= h < 24:
        return "evening"
    return "night"


KINDS = {"morning": ["tv"], "afternoon": ["tv", "movie"], "evening": ["movie"], "night": ["movie"], "weekend": ["tv"]}


def history(trakt, kind):
    """[(tmdb id, title)] of what you watched last (newest first, unique)."""
    path = "sync/history/movies?limit=40" if kind == "movie" else "sync/history/episodes?limit=60"
    seen, out = set(), []
    for entry in trakt.get(path) or []:
        media = entry.get("movie") if kind == "movie" else entry.get("show")
        if not media:
            continue
        tmdb = (media.get("ids") or {}).get("tmdb")
        if tmdb and tmdb not in seen:
            seen.add(tmdb)
            out.append((tmdb, media.get("title") or ""))
    return out


def recommend(kinds):
    """List of TMDB results (dicts with media_type), each with a 'because' title."""
    lang = "nl-NL" if _NL else "en-US"
    trakt = None
    try:
        if xbmc.getCondVisibility("System.HasAddon(plugin.video.seren)"):
            trakt = info.Trakt()
            if not trakt.token:
                trakt = None
    except Exception:  # noqa: BLE001
        trakt = None
    picks, watched = [], set()
    if trakt:
        for kind in kinds:
            try:
                hist = history(trakt, kind)
            except Exception as error:  # noqa: BLE001
                log(f"history {kind}: {error}")
                hist = []
            watched.update((kind, h[0]) for h in hist)
            for tmdb_id, title in hist[:4]:
                try:
                    results = info.tmdb(f"{kind}/{tmdb_id}/recommendations", language=lang).get("results") or []
                except Exception as error:  # noqa: BLE001
                    log(f"recommendations {kind} {tmdb_id}: {error}")
                    continue
                for r in results[:10]:
                    r["media_type"] = kind
                    r["because"] = title
                    picks.append(r)
    if len(picks) < MAX:
        for kind in kinds:
            try:
                for r in info.tmdb(f"trending/{kind}/week", language=lang).get("results") or []:
                    r["media_type"] = kind
                    r["because"] = ""
                    picks.append(r)
            except Exception as error:  # noqa: BLE001
                log(f"trending {kind}: {error}")
    out, seen = [], set()
    # mix the seeds: take round robin so one film does not fill the whole row
    random.shuffle(picks)
    picks.sort(key=lambda r: (not r.get("because"), -(r.get("vote_average") or 0) * min(r.get("vote_count") or 0, 500) / 500))
    for r in picks:
        key = (r["media_type"], r.get("id"))
        if key in seen or key in watched or not r.get("poster_path"):
            continue
        if (r.get("vote_count") or 0) < 50:
            continue
        seen.add(key)
        out.append(r)
        if len(out) >= MAX:
            break
    return out


def logo_of(kind, tmdb_id):
    """Clear logo (title art) from TMDB: Dutch, then English, then without text language."""
    try:
        data = info.tmdb(f"{kind}/{tmdb_id}/images", include_image_language="nl,en,null", language="")
    except Exception as error:  # noqa: BLE001
        log(f"logo {kind} {tmdb_id}: {error}")
        return ""
    logos = [x for x in data.get("logos") or [] if x.get("file_path") and not x["file_path"].lower().endswith(".svg")]
    for lang in ("nl" if _NL else "en", "en", None):
        for logo in logos:
            if logo.get("iso_639_1") == lang:
                return f"{info.TMDB_IMG}w500{logo['file_path']}"
    return f"{info.TMDB_IMG}w500{logos[0]['file_path']}" if logos else ""


def add_logos(items):
    for r in items:
        if "logo" not in r:
            r["logo"] = logo_of(r["media_type"], r.get("id"))
    return items


def publish(part, items):
    img = info.TMDB_IMG
    for n in range(1, MAX + 1):
        for k in ("title", "poster", "fanart", "year", "plot", "tmdb", "type", "rating", "because", "path", "logo"):
            HOME.clearProperty(f"{P}{n}.{k}")
    for n, r in enumerate(items, start=1):
        movie = r["media_type"] == "movie"
        title = r.get("title") if movie else r.get("name")
        date = r.get("release_date") if movie else r.get("first_air_date")
        values = {
            "title": title or "", "poster": f"{img}w342{r['poster_path']}",
            "fanart": f"{img}w1280{r['backdrop_path']}" if r.get("backdrop_path") else "",
            "logo": r.get("logo") or "",
            "year": (date or "")[:4], "plot": r.get("overview") or "", "tmdb": str(r.get("id")),
            "type": "movie" if movie else "tv", "rating": f"{r.get('vote_average') or 0:.1f}",
            "because": t("because", r["because"]) if r.get("because") else t("trending"),
            "path": f"{info.SEREN}?action={'moviesSearchResults' if movie else 'showsSearchResults'}&action_args="
                    + urllib.parse.quote(title or ""),
        }
        for k, v in values.items():
            HOME.setProperty(f"{P}{n}.{k}", v)
    HOME.setProperty(P + "label", t(part))
    HOME.setProperty(P + "count", str(len(items)))


def save_cache(part, items):
    try:
        xbmcvfs.mkdirs("special://profile/addon_data/skin.lucent/")
        with xbmcvfs.File(CACHE, "w") as fh:
            fh.write(json.dumps({"part": part, "time": time.time(), "items": items}))
    except Exception:  # noqa: BLE001
        pass


def load_cache():
    try:
        with xbmcvfs.File(CACHE) as fh:
            return json.loads(fh.read() or "{}")
    except Exception:  # noqa: BLE001
        return {}


def update(force=False):
    part = daypart()
    cache = load_cache()
    if not force and cache.get("part") == part and time.time() - cache.get("time", 0) < REFRESH and cache.get("items") \
            and all("logo" in r for r in cache["items"]):
        if HOME.getProperty(P + "count") != str(len(cache["items"])) or HOME.getProperty(P + "label") != t(part):
            publish(part, cache["items"])
        return
    if not force and time.time() - _LAST_TRY[0] < 15 * 60:
        return                              # the last try failed (offline, TMDB down): wait a while
    _LAST_TRY[0] = time.time()
    if not info.tmdb_key():
        return
    items = add_logos(recommend(KINDS[part]))
    if items:
        publish(part, items)
        save_cache(part, items)
        log(f"{part}: {len(items)} titles")



def open_item():
    """Click on a card: open the title's own page (Back returns to Home)."""
    n = xbmc.getInfoLabel("Container(8091).ListItem.Property(n)")
    HOME.setProperty("nuvio.open.tmdb", HOME.getProperty(f"{P}{n}.tmdb"))
    HOME.setProperty("nuvio.open.type", HOME.getProperty(f"{P}{n}.type"))
    HOME.setProperty("nuvio.open.path", HOME.getProperty(f"{P}{n}.path"))
    HOME.setProperty("nuvio.open.year", HOME.getProperty(f"{P}{n}.year"))
    HOME.clearProperty("nuvio.open.trakt")
    xbmc.executebuiltin("RunScript(special://skin/scripts/info.py,open,path)")


if __name__ == "__main__":
    import sys
    action = sys.argv[1] if len(sys.argv) > 1 else ""
    if action == "open":
        open_item()
    elif action == "refresh":
        update(force=True)
