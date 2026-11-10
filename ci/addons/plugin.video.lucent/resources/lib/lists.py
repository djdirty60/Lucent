# -*- coding: utf-8 -*-
"""'Library and lists' for any film or series (also from other add-ons): one window with ticks that shows where the
title is now. Tick = add, untick = remove.

    RunPlugin(plugin://plugin.video.lucent/?action=lists&type=movie|tvshow&tmdb=<id>)

Rows: watchlist, Trakt collection, the Kodi library, your own Trakt lists, your Simkl list (one status at a time) and
your own static MDBList lists. Without an account: the watchlist and the library on this device."""
import xbmcgui

import library
import mdblist
import simkl
import tmdb
import tracker
import trakt
import util

T = util.T
SIMKL_STATUS = [("plantowatch", "Simkl: wil ik zien", "Simkl: plan to watch"), ("watching", "Simkl: bezig", "Simkl: watching"),
                ("completed", "Simkl: gezien", "Simkl: completed"), ("hold", "Simkl: even gestopt", "Simkl: on hold"),
                ("dropped", "Simkl: afgehaakt", "Simkl: dropped")]


def _pair(kind, tmdb_id):
    return ("movie" if kind == "movie" else "tvshow", str(tmdb_id))


def _in(pairs, kind, tmdb_id):
    return _pair(kind, tmdb_id) in {(k, str(i)) for k, i in pairs}


# ------------------------------------------------------------------ Trakt
def _trakt_body(kind, tmdb_id):
    return {("movies" if kind == "movie" else "shows"): [{"ids": {"tmdb": int(tmdb_id)}}]}


def _trakt_list_items(list_id):
    return trakt.pairs_from(trakt.cached("users/me/lists/%s/items/movie,show" % list_id, 300) or [])


def _trakt_rows(kind, tmdb_id):
    rows = [(T("Collectie (Trakt)", "Collection (Trakt)"), _in(tracker.pairs("collection_movie" if kind == "movie" else "collection_tv"), kind, tmdb_id),
             lambda add: trakt.call("sync/collection" + ("" if add else "/remove"), data=_trakt_body(kind, tmdb_id)))]
    for _owner, list_id, name in trakt.custom_lists("mine"):
        def change(add, list_id=list_id):
            trakt.call("users/me/lists/%s/items%s" % (list_id, "" if add else "/remove"), data=_trakt_body(kind, tmdb_id))
            util.cache_drop("trakt" + "users/me/lists/%s/items/movie,show" % list_id)
        rows.append((T("Trakt-lijst: %s", "Trakt list: %s") % name, _in(_trakt_list_items(list_id), kind, tmdb_id), change))
    return rows


# ------------------------------------------------------------------ Simkl (one status at a time)
def _simkl_status(kind, tmdb_id):
    bucket = "movies" if kind == "movie" else "shows"
    for row, entry in simkl._rows(simkl._library(), bucket):        # noqa: SLF001 - same add-on
        if simkl._id(entry) == str(tmdb_id):                         # noqa: SLF001
            return row.get("status")
    return None


def _simkl_rows(kind, tmdb_id):
    now = _simkl_status(kind, tmdb_id)
    meta = {"kind": kind, "tmdb": str(tmdb_id)}
    bucket = "movies" if kind == "movie" else "shows"
    rows = []
    for status, nl, en in SIMKL_STATUS:
        if status == "plantowatch":
            continue                                # that is the watchlist row
        if kind == "movie" and status in ("watching", "hold"):
            continue

        def change(add, status=status):
            if add:
                simkl.call("sync/add-to-list", data={bucket: [{"to": status, "ids": simkl._ids(meta)}]})     # noqa: SLF001
            else:
                simkl.call("sync/history/remove", data={bucket: [{"ids": simkl._ids(meta)}]})
            simkl.forget_lists()
        rows.append((T(nl, en), now == status, change))
    return rows


# ------------------------------------------------------------------ MDBList (own static lists)
def _mdb_static():
    data = util.cache_get("mdblistlists/user", 900)
    if data is None:
        data, _ = util.http(mdblist._url("lists/user"))                # noqa: SLF001
        util.cache_set("mdblistlists/user", data)
    rows = data.get("lists") or [] if isinstance(data, dict) else data or []
    return [(row["id"], row.get("name") or "") for row in rows if row.get("id") and not row.get("dynamic")]


def _mdb_rows(kind, tmdb_id):
    rows = []
    for list_id, name in _mdb_static():
        found = util.cache_get("mdbitems%s" % list_id, 300)
        if found is None:
            found, _more = mdblist.items(list_id, 1, 1000)
            util.cache_set("mdbitems%s" % list_id, found)

        def change(add, list_id=list_id):
            body = {("movies" if kind == "movie" else "shows"): [{"tmdb": int(tmdb_id)}]}
            util.http(mdblist._url("lists/%s/items/%s" % (list_id, "add" if add else "remove")), data=body)    # noqa: SLF001
            util.cache_drop("mdbitems%s" % list_id)
        rows.append((T("MDBList: %s", "MDBList: %s") % name, _in(found, kind, tmdb_id), change))
    return rows


# ------------------------------------------------------------------ the window
def rows_for(kind, tmdb_id):
    """[(label, on now, change(add))]."""
    meta = {"kind": kind, "tmdb": str(tmdb_id)}
    watch = _in(tracker.pairs("watchlist_movie" if kind == "movie" else "watchlist_tv"), kind, tmdb_id)
    rows = [(T("Kijklijst", "Watchlist"), watch, lambda add: tracker.set_watchlist(meta, add)),
            (T("Kodi-bibliotheek", "Kodi library"), library.has(kind, tmdb_id),
             lambda add: library.add_one(kind, tmdb_id) if add else library.remove_one(kind, tmdb_id, ask=False))]
    account = tracker.active()
    for part in ((_trakt_rows,) if account is trakt else (_simkl_rows,) if account is simkl else ()) + ((_mdb_rows,) if mdblist.available() else ()):
        try:
            rows += part(kind, tmdb_id)
        except util.HttpError as error:
            util.log("lists: %s" % error)
    return rows


def open_lists(kind, tmdb_id):
    kind = "movie" if kind == "movie" else "tvshow"
    meta = tmdb.details(kind, tmdb_id) if tmdb.key() else None
    title = (meta or {}).get("title") or T("Bibliotheek en lijsten", "Library and lists")
    try:
        rows = rows_for(kind, tmdb_id)
    except util.HttpError as error:
        util.log("lists: %s" % error)
        return util.notify(T("Je account is niet bereikbaar", "Your account cannot be reached"))
    picked = xbmcgui.Dialog().multiselect(title, [label for label, _on, _do in rows], preselect=[n for n, row in enumerate(rows) if row[1]])
    if picked is None:
        return None
    done = []
    for number, (label, on, change) in enumerate(rows):
        wanted = number in picked
        if wanted == on:
            continue
        try:
            change(wanted)
            done.append(("+ " if wanted else "- ") + label)
        except util.HttpError as error:
            util.log("lists %s: %s" % (label, error))
            util.notify(T("Niet gelukt: %s", "Did not work: %s") % label)
    tracker.forget_lists()
    import widgets
    widgets.mark_old(account_only=True)
    if done:
        util.notify(", ".join(done))
    return True
