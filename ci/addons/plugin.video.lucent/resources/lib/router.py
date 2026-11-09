# -*- coding: utf-8 -*-
"""Every menu and action of the add-on. The Lucent skin can use these same addresses."""
from concurrent.futures import ThreadPoolExecutor
import datetime
import urllib.parse

import xbmc
import xbmcgui
import xbmcplugin

import items
import library
import player
import report
import floppy
import mdblist
import simkl
import streams
import tmdb
import tracker
import trakt
import users
import usenet
import util

T = util.T
PAGE = 40
TMDB_LISTS = {
    "trending_movie": ("trending/movie/week", "movie"), "popular_movie": ("movie/popular", "movie"),
    "toprated_movie": ("movie/top_rated", "movie"), "nowplaying_movie": ("movie/now_playing", "movie"),
    "upcoming_movie": ("movie/upcoming", "movie"), "trending_tv": ("trending/tv/week", "tvshow"),
    "popular_tv": ("tv/popular", "tvshow"), "toprated_tv": ("tv/top_rated", "tvshow"),
    "airing_tv": ("tv/on_the_air", "tvshow"),
}
ACCOUNT_LISTS = ("watchlist_movie", "watchlist_tv", "collection_movie", "collection_tv")


def send(handle, rows, content="", more=None):
    if more:
        rows.append(items.folder(T("Volgende pagina", "Next page"), more, "DefaultFolder.png"))
    xbmcplugin.addDirectoryItems(handle, rows, len(rows))
    if content:
        xbmcplugin.setContent(handle, content)
    xbmcplugin.endOfDirectory(handle, cacheToDisc=False)


def _resume_table():
    """{key: (position, total)} from this device and from Trakt; Trakt wins."""
    table = {k: (v.get("position", 0), v.get("total", 0)) for k, v in util.load_json(player.LOCAL, {}).items() if v.get("total")}
    return table


def _resume_for(meta, table, paused):
    if meta["kind"] not in ("movie", "episode"):
        return None
    runtime = int(meta.get("runtime") or 0) * 60
    percent = paused.get(player.progress_key(meta))
    if percent and runtime:
        return runtime * percent / 100.0, runtime
    return table.get(player.progress_key(meta))


def _paused_table():
    table = {}
    for row in tracker.paused():
        if row.get("type") == "movie":
            table["movie:%s" % row["movie"]["ids"].get("tmdb")] = row.get("progress") or 0
        elif row.get("type") == "episode":
            table["ep:%s:%s:%s" % (row["show"]["ids"].get("tmdb"), row["episode"]["season"], row["episode"]["number"])] = row.get("progress") or 0
    return table


def send_titles(handle, titles, content, more=None):
    tracker.enrich(titles)
    films, shows = tracker.watched_movies(), tracker.watched_episodes()
    local, paused = _resume_table(), _paused_table()
    rows = []
    for meta in titles:
        last, counts, seen = "", None, False
        if meta["kind"] == "movie":
            seen, last = meta["tmdb"] in films, films.get(meta["tmdb"], "")
        elif meta["kind"] == "episode":
            when = shows.get(meta["tmdb"], {}).get((int(meta["season"]), int(meta["episode"])))
            seen, last = when is not None, when or ""
        else:
            shown = shows.get(meta["tmdb"], {})
            counts = (meta.get("episodes") or 0, len(shown))
            seen, last = bool(counts[0]) and counts[1] >= counts[0], max(shown.values()) if shown else ""
        rows.append(items.title_item(meta, seen, _resume_for(meta, local, paused), last, counts))
    send(handle, rows, content, more)


def home(handle, _params):
    rows = [
        items.folder(T("Films", "Movies"), util.url_for(action="menu", type="movie"), "DefaultMovies.png"),
        items.folder(T("Series", "Shows"), util.url_for(action="menu", type="tvshow"), "DefaultTVShows.png"),
        items.folder(T("Zoeken", "Search"), util.url_for(action="searchmenu"), "DefaultAddonsSearch.png"),
    ]
    rows[2:2] = [
        items.folder(T("Verder kijken", "Continue watching"), util.url_for(action="list", name="continue"), "DefaultInProgressShows.png"),
        items.folder(T("Volgende afleveringen", "Next up"), util.url_for(action="list", name="nextup"), "DefaultTVShows.png"),
        items.folder(T("Voor jou", "For you"), util.url_for(action="list", name="foryou"), "DefaultFolder.png"),
        items.folder(T("Kalender", "Calendar"), util.url_for(action="list", name="calendar"), "DefaultFolder.png"),
        items.folder(T("Mijn lijsten", "My lists"), util.url_for(action="traktmenu"), "DefaultFolder.png"),
        items.folder(T("Streamingdiensten", "Streaming services"), util.url_for(action="services"), "DefaultFolder.png"),
    ]
    if mdblist.available():
        rows.insert(8, items.folder("MDBList", util.url_for(action="mdblistmenu"), "DefaultFolder.png"))
    if floppy.available():
        rows.insert(-1, items.folder("Floppy", util.url_for(action="floppylists"), "DefaultFolder.png"))
    who = xbmcgui.ListItem(T("Profiel: %s", "Profile: %s") % users.current()["name"], offscreen=True)
    who.setProperty("IsPlayable", "false")
    rows.append((util.url_for(action="who"), who, False))
    send(handle, rows)


def menu(handle, params):
    if params.get("type") == "movie":
        entries = [(T("Trending", "Trending"), "trending_movie"), (T("Populair", "Popular"), "popular_movie"),
                   (T("Best beoordeeld", "Top rated"), "toprated_movie"), (T("Nu in de bioscoop", "In cinemas"), "nowplaying_movie"),
                   (T("Binnenkort", "Coming soon"), "upcoming_movie")]
    else:
        entries = [(T("Trending", "Trending"), "trending_tv"), (T("Populair", "Popular"), "popular_tv"),
                   (T("Best beoordeeld", "Top rated"), "toprated_tv"), (T("Lopende series", "On the air"), "airing_tv")]
    rows = [items.folder(label, util.url_for(action="list", name=name)) for label, name in entries]
    rows.append(items.folder(T("Genres", "Genres"), util.url_for(action="genres", type=params.get("type"))))
    send(handle, rows)


def trakt_menu(handle, _params):
    entries = [(T("Kijklijst films", "Watchlist movies"), "watchlist_movie"), (T("Kijklijst series", "Watchlist shows"), "watchlist_tv")]
    if tracker.logged_in():
        entries += [(T("Collectie films", "Collection movies"), "collection_movie"), (T("Collectie series", "Collection shows"), "collection_tv")]
    rows = [items.folder(label, util.url_for(action="list", name=name)) for label, name in entries]
    if tracker.has_lists():
        rows.append(items.folder(T("Mijn eigen lijsten", "My own lists"), util.url_for(action="traktlists", kind="mine")))
        rows.append(items.folder(T("Gelikete lijsten", "Liked lists"), util.url_for(action="traktlists", kind="liked")))
        rows.append(items.folder(T("Openbare lijsten", "Public lists"), util.url_for(action="publiclists")))
    entry = xbmcgui.ListItem(T("Bibliotheek nu bijwerken", "Update the library now"), offscreen=True)
    entry.setProperty("IsPlayable", "false")
    rows.append((util.url_for(action="library_sync"), entry, False))
    send(handle, rows)


def _query(params):
    return params.get("query") or xbmcgui.Dialog().input(T("Lijst zoeken", "Search lists"))


def trakt_lists(handle, params):
    kind = params.get("kind")
    query = None
    if kind == "search":
        query = _query(params)
        if not query:
            return xbmcplugin.endOfDirectory(handle, succeeded=False)
    rows = [items.folder(name, util.url_for(action="list", name="traktlist", user=owner, id=list_id))
            for owner, list_id, name in tracker.custom_lists(kind, query)]
    send(handle, rows)
    return None


def public_lists(handle, _params):
    send(handle, [items.folder(label, util.url_for(action="traktlists", kind=kind)) for label, kind in
                  ((T("Trending lijsten", "Trending lists"), "trending"), (T("Populaire lijsten", "Popular lists"), "popular"), (T("Lijst zoeken", "Search lists"), "search"))])


def floppy_lists(handle, _params):
    send(handle, [items.folder(name, util.url_for(action="list", name="floppylist", id=list_id)) for list_id, name in floppy.lists()])


def mdblist_menu(handle, _params):
    send(handle, [items.folder(label, util.url_for(action="mdblists", kind=kind)) for label, kind in
                  ((T("Mijn lijsten", "My lists"), "mine"), (T("Gelikete lijsten", "Liked lists"), "liked"), (T("Toplijsten", "Top lists"), "top"), (T("Lijst zoeken", "Search lists"), "search"))])


def mdblists(handle, params):
    kind = params.get("kind", "mine")
    query = None
    if kind == "search":
        query = _query(params)
        if not query:
            return xbmcplugin.endOfDirectory(handle, succeeded=False)
    send(handle, [items.folder(name, util.url_for(action="list", name="mdblist", id=list_id)) for list_id, name in mdblist.lists(kind, query)])
    return None


def genres(handle, params):
    api = "movie" if params.get("type") == "movie" else "tv"
    rows = [items.folder(g["name"], util.url_for(action="list", name="genre", type=params.get("type"), genre=g["id"]))
            for g in tmdb.get("genre/%s/list" % api, ttl=7 * tmdb.DAY).get("genres") or []]
    send(handle, rows)


def services(handle, _params):
    rows = []
    for provider, name, logo in tmdb.providers():
        url, item, folder = items.folder(name, util.url_for(action="service", provider=provider, name=name))
        item.setArt({"icon": logo, "thumb": logo, "poster": logo})
        rows.append((url, item, folder))
    send(handle, rows)


def service(handle, params):
    rows = [items.folder(label, util.url_for(action="list", name="provider", provider=params["provider"], type=kind)) for label, kind in
            ((T("Nieuwste eerst", "Newest first"), "all"), (T("Films", "Movies"), "movie"), (T("Series", "Shows"), "tvshow"))]
    send(handle, rows)


def search_menu(handle, _params):
    send(handle, [items.folder(T("Films zoeken", "Search movies"), util.url_for(action="search", type="movie")),
                  items.folder(T("Series zoeken", "Search shows"), util.url_for(action="search", type="tvshow"))])


def _slice(pairs, page):
    start = (page - 1) * PAGE
    return pairs[start:start + PAGE], len(pairs) > start + PAGE


def continue_titles(only=None):
    titles = []
    def load(row):
        try:
            if row.get("type") == "movie":
                meta = tmdb.details("movie", row["movie"]["ids"]["tmdb"])
            else:
                meta = player.title_meta("episode", row["show"]["ids"]["tmdb"], row["episode"]["season"], row["episode"]["number"])
        except (util.HttpError, KeyError, TypeError):
            return None
        if meta:
            meta["resume_percent"] = row.get("progress") or 0
        return meta
    with ThreadPoolExecutor(max_workers=6) as pool:
        titles = [m for m in pool.map(load, [r for r in tracker.paused() if not only or r.get("type") == only][:40]) if m]
    return titles


def next_up_titles():
    cached = util.cache_get("nextup", 300)
    if cached is not None:
        return cached

    def load(entry):
        try:
            return player.title_meta("episode", entry[0], int(entry[1]), int(entry[2]))
        except (util.HttpError, KeyError, TypeError):
            return None
    with ThreadPoolExecutor(max_workers=6) as pool:
        titles = [m for m in pool.map(load, tracker.next_up()) if m and tmdb.aired(m.get("premiered"))]
    util.cache_set("nextup", titles)
    return titles


def calendar_titles():
    """New episodes of what you follow: from a week ago up to a month ahead."""
    today = datetime.date.today()
    first, last = (today - datetime.timedelta(days=7)).isoformat(), (today + datetime.timedelta(days=30)).isoformat()

    def load(show):
        try:
            aired, coming = tmdb.on_air(show)
            found = []
            for episode in (aired, coming):
                if episode and first <= (episode.get("air_date") or "") <= last:
                    meta = player.title_meta("episode", show, episode["season_number"], episode["episode_number"])
                    if meta:
                        found.append(meta)
            return found
        except (util.HttpError, KeyError, TypeError):
            return []
    shows = list(tracker.watched_episodes())[:60] + [str(i) for _k, i in tracker.pairs("watchlist_tv")][:40]
    with ThreadPoolExecutor(max_workers=6) as pool:
        titles = [meta for found in pool.map(load, list(dict.fromkeys(shows))) for meta in found]
    return sorted(titles, key=lambda m: m.get("premiered") or "")


def for_you_titles():
    """Recommendations from what you watched last, without what you already saw."""
    films, shows = tracker.watched_movies(), tracker.watched_episodes()
    recent_films = sorted(films, key=lambda i: films[i], reverse=True)[:6]
    recent_shows = sorted(shows, key=lambda i: max(shows[i].values()) if shows[i] else "", reverse=True)[:6]

    def load(job):
        api, kind, tmdb_id = job
        try:
            return [(kind, r["id"]) for r in tmdb.get("%s/%s/recommendations" % (api, tmdb_id), ttl=tmdb.DAY).get("results") or []]
        except util.HttpError:
            return []
    jobs = [("movie", "movie", i) for i in recent_films] + [("tv", "tvshow", i) for i in recent_shows]
    with ThreadPoolExecutor(max_workers=6) as pool:
        results = list(pool.map(load, jobs))
    counts = {}
    for found in results:
        for pair in found:
            counts[pair] = counts.get(pair, 0) + 1
    fresh = [p for p in counts if not (p[0] == "movie" and str(p[1]) in films) and not (p[0] == "tvshow" and str(p[1]) in shows)]
    fresh.sort(key=lambda p: counts[p], reverse=True)
    return tmdb.many(fresh[:40])


def cast(handle, params):
    meta = tmdb.details(params.get("type", "movie"), params["tmdb"])
    rows = []
    for person in (meta or {}).get("cast") or []:
        url, item, folder = items.folder(person["name"], util.url_for(action="list", name="person", id=person.get("id")))
        item.setLabel2(person.get("role") or "")
        if person.get("thumb"):
            item.setArt({"thumb": person["thumb"], "poster": person["thumb"], "icon": person["thumb"]})
        rows.append((url, item, folder))
    send(handle, rows)


def list_titles(handle, params):
    name = params.get("name", "")
    page = int(params.get("page") or 1)
    more = False
    content = "movies"
    if name in TMDB_LISTS:
        path, kind = TMDB_LISTS[name]
        titles, more = tmdb.listing(path, kind, page)
    elif name == "genre":
        kind = params.get("type")
        titles, more = tmdb.listing("discover/" + ("movie" if kind == "movie" else "tv"), kind, page,
                                    with_genres=params["genre"], sort_by="popularity.desc")
    elif name == "calendar":
        titles, content = calendar_titles(), "episodes"
    elif name == "foryou":
        titles = for_you_titles()
    elif name == "person":
        titles = tmdb.many(tmdb.person_titles(params["id"]))
    elif name == "provider":
        titles, more = tmdb.newest_on(params["provider"], params.get("type", "all"), page)
    elif name == "similar":
        kind = params.get("type")
        titles, more = tmdb.listing("%s/%s/recommendations" % ("movie" if kind == "movie" else "tv", params["tmdb"]), kind, page)
    elif name == "continue":
        titles = continue_titles()
    elif name == "continue_movie":
        titles = continue_titles("movie")
    elif name == "continue_episode":
        titles, content = continue_titles("episode"), "episodes"
    elif name == "nextup":
        titles, content = next_up_titles(), "episodes"
    elif name in ACCOUNT_LISTS:
        slice_of, more = _slice(tracker.pairs(name), page)
        titles = tmdb.many(slice_of)
    elif name == "traktlist":
        found = tracker.list_pairs(params["user"], params["id"], page, PAGE)
        titles, more = tmdb.many(found), len(found) >= PAGE
    elif name == "floppylist":
        found, more = floppy.items(params["id"], page, PAGE)
        titles = tmdb.many(found)
    elif name == "mdblist":
        found, more = mdblist.items(params["id"], page, PAGE)
        titles = tmdb.many(found)
    else:
        titles = []
    if titles and all(t["kind"] == "tvshow" for t in titles):
        content = "tvshows"
    elif titles and all(t["kind"] == "episode" for t in titles):
        content = "episodes"
    next_url = util.url_for(**dict(params, page=page + 1)) if more and params.get("widget") != "1" else None     # a Home row has no next page
    send_titles(handle, titles, content, next_url)


def search(handle, params):
    query = params.get("query") or xbmcgui.Dialog().input(T("Zoeken", "Search"))
    if not query:
        return xbmcplugin.endOfDirectory(handle, succeeded=False)
    kind = params.get("type", "movie")
    page = int(params.get("page") or 1)
    titles, more = tmdb.listing("search/" + ("movie" if kind == "movie" else "tv"), kind, page, query=query, include_adult="false")
    next_url = util.url_for(action="search", type=kind, query=query, page=page + 1) if more else None
    send_titles(handle, titles, "movies" if kind == "movie" else "tvshows", next_url)
    return None


def seasons(handle, params):
    show = tmdb.details("tvshow", params["tmdb"])
    titles = []
    for raw in (show or {}).get("seasons") or []:
        titles.append(dict(show, kind="season", show=show["title"], season=raw["season_number"],
                           title=raw.get("name") or "", plot=raw.get("overview") or show["plot"],
                           poster=tmdb.image(raw.get("poster_path"), "w500") or show["poster"],
                           premiered=raw.get("air_date") or "", episodes=raw.get("episode_count") or 0))
    shown = tracker.watched_episodes().get(params["tmdb"], {})
    rows = []
    for meta in titles:
        count = sum(1 for s, _e in shown if s == meta["season"])
        total = meta["episodes"]
        rows.append(items.title_item(meta, bool(total) and count >= total, counts=(total, count)))
    send(handle, rows, "seasons")


def episodes(handle, params):
    show = tmdb.details("tvshow", params["tmdb"])
    raw_list = tmdb.season(params["tmdb"], params["season"]).get("episodes") or []
    titles = [tmdb.episode_meta(show, raw) for raw in raw_list if tmdb.aired(raw.get("air_date"))] if show else []
    send_titles(handle, titles, "episodes")


def _meta_for(params):
    return {"kind": params["type"], "tmdb": params["tmdb"], "season": params.get("season"), "episode": params.get("episode")}


def set_watched(params):
    tracker.set_watched(_meta_for(params), params.get("value") == "1")
    xbmc.executebuiltin("Container.Refresh")


def set_watchlist(params):
    tracker.set_watchlist(_meta_for(params), params.get("value") == "1")
    util.notify(T("Kijklijst bijgewerkt", "Watchlist updated"))


def title(handle, params):
    """One film or series by TMDB id, as a list of one: for the skin's info page."""
    kind = params.get("type", "movie")
    meta = tmdb.details(kind, params["tmdb"])
    send_titles(handle, [meta] if meta else [], "movies" if kind == "movie" else "tvshows")


SECTIONS = {"conn": -100, "play": -99, "trakt": -98, "account": -98, "library": -97, "services": -96}


def open_settings(params):
    """Opens the add-on's settings on one part: conn, play, trakt or library."""
    xbmc.executebuiltin("Addon.OpenSettings(%s)" % util.ADDON_ID)
    focus = SECTIONS.get(params.get("section", ""))
    if focus is not None:
        xbmc.sleep(400)
        xbmc.executebuiltin("SetFocus(%d)" % focus)


def trakt_status():
    """Puts the state of the account in Home window properties, for the skin."""
    library.publish_status()


def check_service(module, heading):
    ok, text = module.check()
    xbmcgui.Dialog().ok(heading if ok else T("Niet gelukt", "Failed"), text)


def test():
    ok, text = streams.check()
    xbmcgui.Dialog().ok("AIOStreams" if ok else T("Niet gelukt", "Failed"), text)


FOLDERS = {"": home, "menu": menu, "traktmenu": trakt_menu, "traktlists": trakt_lists, "genres": genres,
           "searchmenu": search_menu, "cast": cast, "publiclists": public_lists, "floppylists": floppy_lists, "services": services, "service": service, "mdblistmenu": mdblist_menu, "mdblists": mdblists, "title": title, "list": list_titles, "search": search, "seasons": seasons, "episodes": episodes}


def run(argv):
    handle = int(argv[1])
    params = dict(urllib.parse.parse_qsl((argv[2] if len(argv) > 2 else "").lstrip("?")))
    action = params.get("action", "")
    try:
        if action == "play":
            return player.play(params, handle)
        if action == "auth_trakt":
            linked = trakt.login()
            trakt_status()
            return linked
        if action == "logout_trakt":
            trakt.logout()
            return trakt_status()
        if action == "auth_simkl":
            linked = simkl.login()
            trakt_status()
            return linked
        if action == "logout_simkl":
            simkl.logout()
            return trakt_status()
        if action == "test_mdblist":
            return check_service(mdblist, "MDBList")
        if action == "report":
            return report.save()
        if action == "test_easynews":
            ok, text = usenet.check_easynews()
            return xbmcgui.Dialog().ok("Easynews" if ok else T("Niet gelukt", "Failed"), text)
        if action == "test_torbox":
            ok, text = usenet.check_torbox()
            return xbmcgui.Dialog().ok("TorBox" if ok else T("Niet gelukt", "Failed"), text)
        if action == "test_floppy":
            return check_service(floppy, "Floppy")
        if action == "make_testercode":
            import apikeys
            return apikeys.show_code()
        if action == "setup":
            import setup_ui
            return setup_ui.open_setup()
        if action == "who":
            import setup_ui
            return setup_ui.ask_who()
        if action == "ranking":
            import ranking_ui
            return ranking_ui.open_main()
        if action == "settings":
            return open_settings(params)
        if action == "trakt_status":
            return trakt_status()
        if action == "test":
            return test()
        if action == "library_sync":
            return library.run(manual=True)
        if action == "clear_cache":
            util.cache_clear()
            return util.notify(T("Cache gewist", "Cache cleared"))
        if action == "watched":
            return set_watched(params)
        if action == "watchlist":
            return set_watchlist(params)
        if action == "":
            import setup_ui
            if setup_ui.needed():
                setup_ui.open_setup()
            if len(users.everyone()) > 1 and not util.HOME.getProperty("lucent.video.who.asked"):
                util.HOME.setProperty("lucent.video.who.asked", "1")
                setup_ui.ask_who()
        if not tmdb.key():
            if params.get("widget") == "1":      # a row on Home: stay empty, never open a window
                return xbmcplugin.endOfDirectory(handle, succeeded=False)
            xbmcgui.Dialog().ok("Lucent", T("Vul eerst je TMDB-sleutel in bij de instellingen.", "Enter your TMDB key in the settings first."))
            return xbmcplugin.endOfDirectory(handle, succeeded=False)
        return FOLDERS[action](handle, params)
    except util.HttpError as error:
        util.log("%s: %s" % (action, error), xbmc.LOGERROR)
        util.notify(T("Ophalen is niet gelukt", "Could not load this"))
    except KeyError as error:
        util.log("%s: missing %s" % (action, error), xbmc.LOGERROR)
    if action in FOLDERS and handle >= 0:
        xbmcplugin.endOfDirectory(handle, succeeded=False)
    return None
