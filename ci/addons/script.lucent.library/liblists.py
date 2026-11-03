"""Lucent Bibliotheek: your own Trakt lists as a source for the library, next to the Trakt collection.

    RunScript(script.lucent.library,chooselists)     tick the lists that belong to the library

Trakt's collection can be capped; your own lists are not. Films and series in the chosen lists are written to the
Kodi library just like the collected ones (lib.export / lib.export_shows add them to what Seren gives).
If Trakt cannot be reached, the last copy of the lists is used, so nothing is removed because of a hiccup.
"""
import json
import os
import time

import xbmc
import xbmcgui

import lib

CHOICE = os.path.join(lib.DATA, "lists.json")         # {"lists": [{"id", "name"}], "movie": <where new films go>, "show": ...}
CACHE = os.path.join(lib.DATA, "listcache.json")      # the last copy of the lists and the episodes of their series
NL = lib.NL
REFRESH_RUNNING = 20 * 3600       # episodes of a running series are asked again after 20 hours
REFRESH_ENDED = 7 * 86400         # of an ended series once a week
PAGE_SIZE = 250
PAGE_CAP = 80
SEASON_BUDGET = 60                # series asked for their episodes per run (a big list fills in over a few runs)


def t(en, nl):
    return nl if NL else en


def log(text):
    lib.log(f"lists: {text}")


def _read():
    data = lib.read_json(CHOICE, {}) or {}
    return data if isinstance(data, dict) else {}


def chosen():
    """[{'id', 'name'}] of the lists that make up the library (besides the collection)."""
    data = _read()
    out, seen = [], set()
    for entry in (data.get("lists") or []) + [data.get("movie"), data.get("show")]:   # older files had only movie / show
        if isinstance(entry, dict) and entry.get("id") and entry["id"] not in seen:
            seen.add(entry["id"])
            out.append({"id": entry["id"], "name": entry.get("name", "")})
    return out


def _trakt():
    import quick
    return quick.Trakt()


# ----------------------------------------------------------------------------- choosing
def choose():
    """Tick the lists that belong to the library (as many as you like, or none: only the collection)."""
    try:
        trakt = _trakt()
        lists = trakt.call("users/me/lists") or []
    except Exception as error:  # noqa: BLE001
        log(f"choose: {error}")
        xbmcgui.Dialog().ok(t("Lucent Library", "Lucent Bibliotheek"),
                            t("Your Trakt lists could not be loaded. Check the Trakt login in Seren.",
                              "Je Trakt-lijsten konden niet geladen worden. Kijk of Trakt in Seren is ingelogd."))
        return
    if not lists:
        xbmcgui.Dialog().ok(t("Lucent Library", "Lucent Bibliotheek"),
                            t("You have no lists of your own on Trakt yet.", "Je hebt nog geen eigen lijsten op Trakt."))
        return
    current = {c["id"] for c in chosen()}
    labels = [f"{lst.get('name', '')}  ·  {lst.get('item_count', 0)}" for lst in lists]
    pre = [n for n, lst in enumerate(lists) if (lst.get("ids") or {}).get("trakt") in current]
    picks = xbmcgui.Dialog().multiselect(t("Lists for the library (none = only the Trakt collection)",
                                           "Lijsten voor de bibliotheek (geen = alleen de Trakt-collectie)"), labels, preselect=pre)
    if picks is None:
        return
    picked = [{"id": (lists[n].get("ids") or {}).get("trakt"), "name": lists[n].get("name", "")} for n in picks]
    choice = {"lists": picked}
    choice.update(_targets(trakt, picked))
    lib.write_json(CHOICE, choice)
    label()
    log(f"chosen: {choice}")
    if picked and xbmcgui.Dialog().yesno(t("Lucent Library", "Lucent Bibliotheek"),
                                         t("Update the library now with these lists?",
                                           "De bibliotheek nu bijwerken met deze lijsten?")):
        xbmc.executebuiltin("RunScript(script.lucent.library)")


def _targets(trakt, picked):
    """Where a new film / series goes (the Library row on the info page): the chosen list with the most of that kind."""
    if not picked:
        return {}
    counts = {}
    for lst in picked:
        for kind in ("movie", "show"):
            try:
                data = trakt.call(f"users/me/lists/{lst['id']}/items/{kind}?page=1&limit=100") or []
            except Exception as error:  # noqa: BLE001
                log(f"count {lst['name']} {kind}s: {error}")
                data = []
            counts[(lst["id"], kind)] = len(data) if isinstance(data, list) else 0
    out = {}
    for kind in ("movie", "show"):
        best = max(picked, key=lambda lst: counts.get((lst["id"], kind), 0))
        out[kind] = best if counts.get((best["id"], kind), 0) or len(picked) == 1 else picked[0]
    return out


def label():
    """The skin shows the chosen lists under the button (Skin.String lucent.lib.lists)."""
    text = " · ".join(c["name"] for c in chosen())
    xbmc.executebuiltin(f"Skin.SetString(lucent.lib.lists,{text.replace(',', ' ')})" if text else "Skin.Reset(lucent.lib.lists)")


# ----------------------------------------------------------------------------- reading the lists
def _items(trakt, cache, kind):
    """Films or series of the chosen lists ({trakt id: full Trakt record}); the last copy when Trakt fails."""
    lists = {c["id"] for c in chosen()}               # every chosen list: a film on a series list counts too
    if not lists:
        return None
    out, ok = {}, True
    mon = xbmc.Monitor()
    for list_id in sorted(lists):
        this = set()
        try:
            for page in range(1, PAGE_CAP + 1):           # Trakt gives 100 items without page / limit
                data = trakt.call(f"users/me/lists/{list_id}/items/{kind}?extended=full&page={page}&limit={PAGE_SIZE}")
                if not isinstance(data, list) or not data:
                    break
                first = ((data[0].get(kind) or {}).get("ids") or {}).get("trakt")
                if page > 1 and str(first) in this:
                    break                                    # Trakt ignores pages here and gave the same again
                for entry in data:
                    rec = entry.get(kind) or {}
                    tid = (rec.get("ids") or {}).get("trakt")
                    if tid:
                        this.add(str(tid))
                        rec["_listed"] = entry.get("listed_at")
                        out[str(tid)] = rec
                if mon.waitForAbort(0.3):                    # Trakt may give fewer than asked: go on until an empty page
                    break
        except Exception as error:  # noqa: BLE001
            log(f"list {list_id} {kind}s: {error}")
            ok = False
    old = cache.get(kind) or {}
    if not ok or (not out and old.get("items")):
        if old.get("items"):
            log(f"{kind}s: Trakt did not answer well, the last copy is used ({len(old['items'])})")
            return old["items"]
    cache[kind] = {"t": time.time(), "items": out}
    return out


def movie_rows(have):
    """Rows like lib.read_collection for the films in your lists that are not collected already."""
    if not chosen():
        return []
    import quick
    cache = lib.read_json(CACHE, {}) or {}
    try:
        trakt = _trakt()
        items = _items(trakt, cache, "movie")
    except Exception as error:  # noqa: BLE001
        log(f"films: {error}")
        items = (cache.get("movie") or {}).get("items")
    lib.write_json(CACHE, cache)
    rows = []
    for tid, m in (items or {}).items():
        if int(tid) in have:
            continue
        ids = m.get("ids") or {}
        info = {"title": m.get("title") or f"Trakt {tid}", "year": m.get("year"), "plot": m.get("overview"),
                "genre": m.get("genres") or [], "mpaa": m.get("certification"), "premiered": m.get("released"),
                "tagline": m.get("tagline"), "trailer": m.get("trailer"), "rating": m.get("rating"),
                "votes": m.get("votes"), "duration": (m.get("runtime") or 0) * 60}
        rows.append({"trakt": int(tid), "tmdb": ids.get("tmdb"), "imdb": ids.get("imdb"), "info": info,
                     "args": quick.seren_args({"mediatype": "movie", "trakt_id": int(tid)}), "watched": 0,
                     "collected_at": m.get("_listed"), "raw": False, "listed": True})
    if rows:
        log(f"films from your lists: {len(rows)}")
    return rows


def show_entries(have):
    """{show trakt id: show} like lib.read_shows for the series in your lists that Seren has no episodes of."""
    if not chosen():
        return {}
    import quick
    cache = lib.read_json(CACHE, {}) or {}
    try:
        trakt = _trakt()
        items = _items(trakt, cache, "show")
    except Exception as error:  # noqa: BLE001
        log(f"series: {error}")
        trakt, items = None, (cache.get("show") or {}).get("items")
    known = cache.setdefault("eps", {})
    todo = [tid for tid in (items or {}) if int(tid) not in have]
    now = time.time()

    def due(tid):
        c = known.get(tid)
        if not c:
            return True
        ended = str((items[tid] or {}).get("status") or "").lower() in ("ended", "canceled")
        return now - c.get("t", 0) > (REFRESH_ENDED if ended else REFRESH_RUNNING)

    asked = 0
    for tid in sorted((x for x in todo if due(x)), key=lambda x: (known.get(x) or {}).get("t", 0)):
        if trakt is None or asked >= SEASON_BUDGET:
            break
        try:
            seasons = trakt.call(f"shows/{tid}/seasons?extended=full,episodes") or []
        except Exception as error:  # noqa: BLE001
            log(f"series {tid} episodes: {error}")
            continue
        asked += 1
        eps = []
        for season in seasons:
            number = season.get("number") or 0
            if number <= 0:
                continue
            sid = (season.get("ids") or {}).get("trakt")
            for ep in season.get("episodes") or []:
                eps.append([(ep.get("ids") or {}).get("trakt"), number, ep.get("number") or 0, sid, ep.get("first_aired") or "",
                            ep.get("title") or "", ep.get("overview") or "", ep.get("runtime") or 0])
        known[tid] = {"t": now, "eps": eps}
    for tid in [k for k in known if k not in (items or {})]:
        known.pop(tid)                                        # left the list: forget its episodes
    lib.write_json(CACHE, cache)
    wait = time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime(now - lib.EPISODE_WAIT_HOURS * 3600))
    shows = {}
    for tid in todo:
        c = known.get(tid)
        if not c:
            continue                                          # its episodes come in a next run
        s = items[tid] or {}
        ids = s.get("ids") or {}
        show = {"trakt_id": int(tid), "tmdb_id": ids.get("tmdb"), "tvdb_id": ids.get("tvdb"), "imdb_id": ids.get("imdb"),
                "info": {"title": s.get("title") or f"Trakt {tid}", "year": s.get("year"), "plot": s.get("overview"),
                         "genre": s.get("genres") or [], "mpaa": s.get("certification"), "premiered": s.get("first_aired"),
                         "status": s.get("status"), "rating": s.get("rating"), "votes": s.get("votes")},
                "raw": False, "episodes": [], "art": {}, "cast": [], "season_art": {}, "fresh": set(), "new_info": {},
                "listed": True}
        for etid, season, number, season_id, aired, title, plot, runtime in c["eps"]:
            if not etid or not aired:
                continue
            if aired[:19] > wait:
                if aired[:19] <= time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime(now)):
                    show["fresh"].add((season, number))       # on TV less than a day ago: kept when already there
                continue
            args = quick.seren_args({"mediatype": "episode", "trakt_id": etid, "trakt_show_id": int(tid),
                                     "trakt_season_id": season_id})
            show["episodes"].append((etid, season, number, args, 0, None))
            show["new_info"][etid] = {"title": title, "plot": plot, "aired": aired[:10], "duration": runtime * 60}
        if show["episodes"] or show["fresh"]:
            shows[int(tid)] = show
    if shows:
        log(f"series from your lists: {len(shows)}")
    return shows
