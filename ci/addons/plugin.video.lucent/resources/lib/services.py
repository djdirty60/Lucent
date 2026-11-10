# -*- coding: utf-8 -*-
"""The streaming services row and each service's six lists, the same as the Lucent skin had them from Lucent Library.

Rows for the skin (all with &widget=1):
  action=list&name=service_row                         the services as tiles; a click opens the service
  action=list&name=service_list&provider=<id>&kind=<k>  k: newmovie newtv popmovie poptv topmovie toptv

  action=list&name=service_catalog                     every service of your country (and the US), for the skin's editor:
                                                       properties provider_id, provider_name and logo_path

The services are the ones chosen in the skin: first addon_data/plugin.video.lucent/services.json, then Lucent Library's
old services.json; without a choice Lucent's standard list. A service your country does not have (Hulu, Peacock ... outside the US) is read for the US.
"""
import time
import urllib.parse

import xbmc
import xbmcvfs

import tmdb
import util

T = util.T
FILE = "providers.json"
VERSION = 1
KEEP = 7 * 86400
OWN_CHOICE = "special://profile/addon_data/plugin.video.lucent/services.json"
LIBRARY_CHOICE = "special://profile/addon_data/script.lucent.library/tmdb/services.json"
SKIN_ART = "special://skin/media/services/"
PACKS = {"white": "resource.images.studios.white", "coloured": "resource.images.studios.coloured"}

KINDS = {  # kind -> (TMDB type, Lucent kind, extra discover parameters, Dutch, English)
    "newmovie": ("movie", "movie", {"sort_by": "primary_release_date.desc", "vote_count.gte": 10}, "Nieuwe films", "New movies"),
    "newtv": ("tv", "tvshow", {"sort_by": "first_air_date.desc", "vote_count.gte": 5}, "Nieuwe series", "New series"),
    "popmovie": ("movie", "movie", {"sort_by": "popularity.desc"}, "Populaire films", "Popular movies"),
    "poptv": ("tv", "tvshow", {"sort_by": "popularity.desc"}, "Populaire series", "Popular series"),
    "topmovie": ("movie", "movie", {"sort_by": "vote_average.desc", "vote_count.gte": 500}, "Best beoordeelde films", "Top rated movies"),
    "toptv": ("tv", "tvshow", {"sort_by": "vote_average.desc", "vote_count.gte": 200}, "Best beoordeelde series", "Top rated series"),
}

WANTED = [  # (key, names TMDB uses), in this order
    ("netflix", ["netflix"]), ("disney", ["disney plus", "disney+"]), ("hbo", ["hbo max", "max", "hbo"]),
    ("apple", ["apple tv plus", "apple tv+", "apple tv"]), ("hulu", ["hulu"]), ("starz", ["starz"]),
    ("paramount", ["paramount plus", "paramount+", "paramount plus premium", "paramount+ premium", "paramount plus essential"]),
    ("peacock", ["peacock premium", "peacock", "peacock premium plus"]), ("mgm", ["mgm plus", "mgm+"]),
    ("amc", ["amc plus", "amc+"]), ("discovery", ["discovery plus", "discovery+"]),
    ("prime", ["amazon prime video", "prime video", "amazon video"]),
]
PACK_NAMES = {
    "netflix": ["Netflix"], "disney": ["Disney+", "Disney Plus"], "hbo": ["HBO Max", "Max", "HBO"],
    "apple": ["Apple TV+", "Apple TV Plus", "Apple TV"], "hulu": ["Hulu"], "starz": ["Starz", "STARZ"],
    "paramount": ["Paramount+", "Paramount Plus"], "peacock": ["Peacock"], "mgm": ["MGM+", "MGM Plus", "Mgm"],
    "amc": ["AMC+", "AMC Plus"], "discovery": ["Discovery+", "discovery+", "Discovery Plus"],
    "prime": ["Prime Video", "Amazon Prime Video", "Amazon"],
}
WHITE_FIRST = ("apple", "hbo")


def label(kind):
    entry = KINDS.get(kind)
    return T(entry[3], entry[4]) if entry else kind


def _exists(path):
    try:
        return xbmcvfs.exists(path)
    except Exception:          # a missing resource add-on
        return False


def _catalog(region):
    """{lower-case name: TMDB provider} of one country, films and series together."""
    found = {}
    for api in ("movie", "tv"):
        for row in tmdb.get("watch/providers/%s" % api, ttl=7 * tmdb.DAY, watch_region=region).get("results") or []:
            name = (row.get("provider_name") or "").strip()
            if row.get("provider_id") and row.get("logo_path") and name:
                found.setdefault(name.lower(), row)
    return found


def key_of(name):
    low = (name or "").lower().replace("+", " plus")
    for key, names in WANTED:
        if any(low == n.replace("+", " plus") for n in names):
            return key
    return ""


def skin_art(key):
    """(logo, animation) the Lucent skin brings for this service, or ('', '')."""
    if not key:
        return "", ""
    logo, hover = SKIN_ART + key + ".png", SKIN_ART + key + "-hover.gif"
    return (logo if _exists(logo) else ""), (hover if _exists(hover) else "")


def _variants(name):
    out = [name]
    for old, new in ((" Plus", "+"), ("Plus", "+"), (" Amazon Channel", ""), (" Standard with Ads", ""), (" with Ads", ""),
                     (" Premium", ""), ("Amazon Prime Video", "Prime Video"), ("HBO Max", "Max"), ("HBO Max", "HBO")):
        if old in name:
            out.append(name.replace(old, new).strip())
    return list(dict.fromkeys(n for n in out if n))


def wide_logo(name, key=""):
    """A see-through logo: the skin's own, else a logo pack, else the company logo on TMDB with exactly this name."""
    key = key or key_of(name)
    own = skin_art(key)[0]
    if own:
        return own
    names = PACK_NAMES.get(key, []) + _variants(name)
    for pack in (["white", "coloured"] if key in WHITE_FIRST else ["coloured", "white"]):
        folder = "special://home/addons/%s/resources/" % PACKS[pack]
        for candidate in names:
            for variant in dict.fromkeys((candidate, candidate.lower())):
                if _exists(folder + variant + ".png"):
                    return "resource://%s/%s.png" % (PACKS[pack], variant)
    for candidate in _variants(name)[:3]:
        try:
            rows = tmdb.get("search/company", ttl=30 * tmdb.DAY, query=candidate).get("results") or []
        except util.HttpError:
            return ""
        exact = [r for r in rows if r.get("logo_path") and (r.get("name") or "").strip().lower() == candidate.lower()]
        if exact:
            return tmdb.image(exact[0]["logo_path"], "w500")
    return ""


def _chosen_in_skin():
    """{"items": [{id, name, logo, region, key, off, image?}]} written by the skin's editor; an empty file is no choice."""
    import json
    for path in (OWN_CHOICE, LIBRARY_CHOICE):
        try:
            with open(xbmcvfs.translatePath(path), encoding="utf-8") as handle:
                own = json.load(handle).get("items") or []
        except (OSError, ValueError, AttributeError):
            continue
        if own:
            return [p for p in own if not p.get("off") and p.get("id")]
    return []


def chosen():
    """[{id, name, logo, region, key, wide}] of the services in the row."""
    own = _chosen_in_skin()
    if own:
        return own
    saved = util.load_json(FILE, {})
    region = tmdb.region()
    if saved.get("items") and saved.get("region") == region and saved.get("v") == VERSION and time.time() - saved.get("time", 0) < KEEP:
        return saved["items"]
    try:
        lists = {region: _catalog(region)}
        if region != "US":
            lists["US"] = _catalog("US")
    except util.HttpError:
        return saved.get("items") or []
    found = []
    for key, names in WANTED:
        for country in ([region, "US"] if region != "US" else ["US"]):
            hit = next((lists[country][n] for n in names if n in lists.get(country, {})), None)
            if hit:
                found.append({"id": hit["provider_id"], "name": hit["provider_name"], "logo": hit["logo_path"], "region": country, "key": key})
                break
    for entry in found:
        entry["wide"] = wide_logo(entry["name"], entry["key"])
    if found:
        util.save_json(FILE, {"time": time.time(), "region": region, "v": VERSION, "items": found})
    return found or saved.get("items") or []


def region_of(provider):
    for entry in chosen():
        if str(entry.get("id")) == str(provider):
            return entry.get("region") or tmdb.region()
    return tmdb.region()


def titles(provider, kind, page=1):
    """One of the six lists of a service: (titles, more pages?)."""
    api, lucent_kind, extra, _nl, _en = KINDS[kind]
    params = {"with_watch_providers": provider, "watch_region": region_of(provider), "with_watch_monetization_types": "flatrate",
              "include_adult": "false"}
    params.update(extra)
    today = time.strftime("%Y-%m-%d")
    if kind == "newmovie":
        params["primary_release_date.lte"] = today
    elif kind == "newtv":
        params["first_air_date.lte"] = today
    return tmdb.listing("discover/" + api, lucent_kind, page, **params)


def tiles():
    """The row of services: (url, ListItem, folder) with the same art and properties the skin used before."""
    import xbmcgui
    rows = []
    for entry in chosen():
        logo = entry.get("image") or tmdb.image(entry.get("logo"), "w500")
        wide = entry.get("wide") or logo
        tile, props = logo, {"lucent_open": "1"}
        own_logo, hover = skin_art(entry.get("key") or key_of(entry.get("name")))
        fanart = ""
        if not entry.get("image") and own_logo:
            props.update(svclogo=own_logo, svchover=hover)
            wide = own_logo
        elif entry.get("wide") and not entry.get("image"):
            props["svclogo"] = entry["wide"]
            try:
                first = (titles(entry["id"], "poptv")[0] or [{}])[0]
                fanart = first.get("fanart") or ""
            except (util.HttpError, IndexError):
                fanart = ""
            tile = fanart or "special://skin/media/default_landscape.png"
        item = xbmcgui.ListItem(entry["name"], offscreen=True)
        item.setArt({"poster": logo, "thumb": logo, "icon": logo, "landscape": tile, "clearlogo": wide, "fanart": fanart})
        item.getVideoInfoTag().setPlot(T("Nieuw, populair en best beoordeeld op %s", "New, popular and top rated on %s") % entry["name"])
        for key, value in props.items():
            item.setProperty(key, value)
        item.setProperty("IsPlayable", "false")
        url = util.url_for(action="service_open", provider=entry["id"], name=entry["name"], logo=wide if wide != logo else "")
        rows.append((url, item, False))
    return rows


def open_service(params):
    """A click on a service: the skin's pop-up when the skin has one, otherwise Lucent Video's own folder."""
    if xbmc.getSkinDir() == "skin.lucent" and _exists("special://skin/scripts/service.py"):
        quote = lambda v: urllib.parse.quote(v or "", safe="")      # noqa: E731
        xbmc.executebuiltin("RunScript(special://skin/scripts/service.py,%s,%s,%s,lucentvideo)"
                            % (quote(params.get("provider")), quote(params.get("name")), quote(params.get("logo"))))
        return
    xbmc.executebuiltin("ActivateWindow(Videos,%s,return)" % util.url_for(action="service", provider=params.get("provider"), name=params.get("name")))


def catalog():
    """[{id, name, logo, region}] of every service in your country, then the US ones your country does not have."""
    region = tmdb.region()
    out, names = [], set()
    for country in ([region, "US"] if region != "US" else ["US"]):
        try:
            rows = sorted(_catalog(country).values(), key=lambda r: (r.get("display_priorities") or {}).get(country, r.get("display_priority", 999)))
        except util.HttpError:
            continue
        for row in rows:
            name = row["provider_name"].strip()
            if name.lower() in names:
                continue
            names.add(name.lower())
            out.append({"id": row["provider_id"], "name": name, "logo": row["logo_path"], "region": country})
    return out


def catalog_tiles():
    import xbmcgui
    rows = []
    for entry in catalog():
        logo = tmdb.image(entry["logo"], "w500")
        item = xbmcgui.ListItem(entry["name"], offscreen=True)
        item.setLabel2(entry["region"])
        item.setArt({"icon": logo, "thumb": logo, "poster": logo})
        for key, value in (("provider_id", str(entry["id"])), ("provider_name", entry["name"]), ("logo_path", entry["logo"]),
                           ("provider_region", entry["region"]), ("provider_key", key_of(entry["name"]))):
            item.setProperty(key, value)
        item.setProperty("IsPlayable", "false")
        rows.append((util.url_for(action="service_open", provider=entry["id"], name=entry["name"]), item, False))
    return rows