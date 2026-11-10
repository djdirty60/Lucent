# -*- coding: utf-8 -*-
"""Every menu and action of the add-on. The Lucent skin can use these same addresses."""
from concurrent.futures import ThreadPoolExecutor
import datetime
import urllib.parse

import xbmc
import xbmcgui
import xbmcplugin

import items
import kids
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
"trending_tv": ("trending/tv/week", "tvshow"),
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
    titles = kids.keep(titles)
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


def _action(label, url, icon="DefaultAddonProgram.png"):
    """A row that does something instead of opening a list."""
    item = xbmcgui.ListItem(label, offscreen=True)
    item.setArt({"icon": icon, "thumb": icon})
    item.setProperty("IsPlayable", "false")
    return url, item, False


def home(handle, _params):
    """Watching first, then browsing, then your own things, then the tools."""
    if not tmdb.key():                  # nothing to browse yet: only the way to get started
        send(handle, [_action(T("Installatie-assistent: sleutels instellen", "Setup assistant: set your keys"), util.url_for(action="setup")),
                      _action(T("Profiel: %s", "Profile: %s") % users.current()["name"], util.url_for(action="who"), "DefaultUser.png"),
                      items.folder(T("Instellingen en hulp", "Settings and help"), util.url_for(action="tools"), "DefaultAddonProgram.png")])
        return
    rows = [
        items.folder(T("Verder kijken", "Continue watching"), util.url_for(action="list", name="continue"), "DefaultInProgressShows.png"),
        items.folder(T("Volgende afleveringen", "Next up"), util.url_for(action="list", name="nextup"), "DefaultTVShows.png"),
        items.folder(T("Films", "Movies"), util.url_for(action="menu", type="movie"), "DefaultMovies.png"),
        items.folder(T("Series", "Shows"), util.url_for(action="menu", type="tvshow"), "DefaultTVShows.png"),
        items.folder(T("Kompas", "Kompas"), util.url_for(action="kompasmenu"), "DefaultAddonsRecentlyUpdated.png"),
        _action(T("Wat zullen we kijken?", "What shall we watch?"), util.url_for(action="pick"), "DefaultAddonsRecentlyUpdated.png"),
        items.folder(T("Streamingdiensten", "Streaming services"), util.url_for(action="services"), "DefaultNetwork.png"),
        items.folder(T("Mijn lijsten", "My lists"), util.url_for(action="traktmenu"), "DefaultPlaylist.png"),
        items.folder(T("Zoeken", "Search"), util.url_for(action="searchmenu"), "DefaultAddonsSearch.png"),
        _action(T("Profiel: %s", "Profile: %s") % users.current()["name"], util.url_for(action="who"), "DefaultUser.png"),
        items.folder(T("Instellingen en hulp", "Settings and help"), util.url_for(action="tools"), "DefaultAddonProgram.png"),
    ]
    send(handle, rows)


def kompas_menu(handle, _params):
    """Kompas: the page, its rows (each can go on Home with 'Add to Home') and your taste."""
    import kompas
    if not kompas.on():
        return send(handle, [items.folder(T("Voor jou", "For you"), util.url_for(action="list", name="foryou"), "DefaultRecentlyAddedMovies.png")])
    data = util.load_json(kompas.ROWS, {})
    because = data.get("because")
    rows = [_action(T("Kompas: kies wat je wilt kijken", "Kompas: choose what to watch"), util.url_for(action="kompas_page"), "DefaultAddonsRecentlyUpdated.png"),
            items.folder(T("Voor jou gekozen", "Picked for you"), util.url_for(action="list", name="kompas_foryou"), "DefaultRecentlyAddedMovies.png")]
    if because:
        rows.append(items.folder(T("Omdat je %s keek", "Because you watched %s") % because, util.url_for(action="list", name="kompas_because"), "DefaultRecentlyAddedMovies.png"))
    rows += [items.folder(T("Verborgen parels", "Hidden gems"), util.url_for(action="list", name="kompas_gems"), "DefaultRecentlyAddedMovies.png"),
             items.folder(T("Nieuw voor jou", "New for you"), util.url_for(action="list", name="kompas_new"), "DefaultRecentlyAddedMovies.png"),
             items.folder(T("Trending voor jou", "Trending for you"), util.url_for(action="list", name="kompas_trending"), "DefaultRecentlyAddedMovies.png")]
    for saved in kompas.saved_rows():
        url, item, folder = items.folder(saved["label"], util.url_for(action="list", name="kompas_saved", id=saved["id"]), "DefaultPlaylist.png")
        item.addContextMenuItems([(T("Deze rij verwijderen", "Remove this row"), "RunPlugin(%s)" % util.url_for(action="kompas_unsave", id=saved["id"]))])
        rows.append((url, item, folder))
    rows.append(_action(T("Jouw smaak", "Your taste"), util.url_for(action="kompas_taste"), "DefaultUser.png"))
    send(handle, rows)


def menu(handle, params):
    movie = params.get("type") == "movie"
    if movie:
        entries = [(T("Trending", "Trending"), "trending_movie"), (T("Populair", "Popular"), "popular_movie"),
                   (T("Best beoordeeld", "Top rated"), "toprated_movie"), (T("Nu in de bioscoop", "In cinemas"), "nowplaying_movie"),
                   (T("Binnenkort", "Coming soon"), "upcoming_movie")]
    else:
        entries = [(T("Trending", "Trending"), "trending_tv"), (T("Populair", "Popular"), "popular_tv"),
                   (T("Nieuwe series", "New series"), "new_tv"),
                   (T("Best beoordeeld", "Top rated"), "toprated_tv"), (T("Lopende series", "On the air"), "airing_tv"),
                   (T("Binnenkort", "Coming soon"), "upcoming_tv"), (T("Kalender: nieuwe afleveringen", "Calendar: new episodes"), "calendar"),
                   (T("Nieuwe seizoenen aangekondigd", "New seasons announced"), "new_seasons")]
    rows = [items.folder(label, util.url_for(action="list", name=name)) for label, name in entries]
    rows.append(items.folder(T("Genres", "Genres"), util.url_for(action="genres", type=params.get("type"))))
    rows.append(items.folder(T("Studio's", "Studios") if movie else T("Netwerken", "Networks"), util.url_for(action="studios", type=params.get("type"))))
    rows.append(items.folder(T("Per decennium", "By decade"), util.url_for(action="decades", type=params.get("type"))))
    rows.append(items.folder(T("Prijswinnaars", "Award winners"), util.url_for(action="awards", type=params.get("type"))))
    rows.append(items.folder(T("Films zoeken", "Search movies") if movie else T("Series zoeken", "Search shows"),
                             util.url_for(action="search", type="movie" if movie else "tvshow"), "DefaultAddonsSearch.png"))
    send(handle, rows)


def trakt_menu(handle, _params):
    """Everything that is yours: watchlists, collection and lists of every service you use."""
    import prefetch
    entries = [(T("Klaar voor vanavond", "Ready for tonight"), "tonight")] if prefetch.tonight() else []
    entries += [(T("Kijklijst films", "Watchlist movies"), "watchlist_movie"), (T("Kijklijst series", "Watchlist shows"), "watchlist_tv")]
    if tracker.logged_in():
        entries += [(T("Collectie films", "Collection movies"), "collection_movie"), (T("Collectie series", "Collection shows"), "collection_tv")]
    rows = [items.folder(label, util.url_for(action="list", name=name)) for label, name in entries]
    if tracker.has_lists():
        rows.append(items.folder(T("Mijn eigen lijsten", "My own lists"), util.url_for(action="traktlists", kind="mine")))
        rows.append(items.folder(T("Gelikete lijsten", "Liked lists"), util.url_for(action="traktlists", kind="liked")))
        rows.append(items.folder(T("Openbare lijsten", "Public lists"), util.url_for(action="publiclists")))
    if mdblist.available():
        rows.append(items.folder("MDBList", util.url_for(action="mdblistmenu")))
    if floppy.available():
        rows.append(items.folder("Floppy", util.url_for(action="floppylists")))
    send(handle, rows)


def studios(handle, params):
    import browse
    kind = params.get("type", "movie")
    rows = []
    for number, name, logo in browse.companies(kind):
        url, item, folder = items.folder(name, util.url_for(action="list", name="company", type=kind, id=number))
        if logo:
            item.setArt({"icon": logo, "thumb": logo, "clearlogo": logo})
        rows.append((url, item, folder))
    send(handle, rows)


def decades(handle, params):
    import browse
    kind = params.get("type", "movie")
    send(handle, [items.folder(T("Jaren '%02d", "%ds") % (start % 100) if start < 2000 else "%ds" % start,
                               util.url_for(action="list", name="decade", type=kind, start=start)) for start in browse.DECADES])


def awards(handle, params):
    import browse
    kind = params.get("type", "movie")
    send(handle, [items.folder(label, util.url_for(action="list", name="award", key=key))
                  for key, (label, what, _w) in browse.AWARDS.items() if what == kind])


def tools(handle, _params):
    rows = [
        _action(T("Instellingen openen", "Open settings"), util.url_for(action="settings")),
        _action(T("Installatie-assistent", "Setup assistant"), util.url_for(action="setup")),
        _action(T("Ondertitels en geluid instellen", "Set up subtitles and sound"), util.url_for(action="subs_setup")),
        _action(T("Intro overslaan instellen", "Set up skip intro"), util.url_for(action="skip_setup")),
        _action(T("Volgorde van bronnen", "Order of sources"), util.url_for(action="ranking")),
        _action(T("Bibliotheek nu bijwerken", "Update the library now"), util.url_for(action="library_sync"), "DefaultAddonLibrary.png"),
        _action(T("Kiezen wat in de bibliotheek komt", "Choose what goes in the library"), util.url_for(action="library_choose"), "DefaultAddonLibrary.png"),
        _action(T("Je kijkjaar", "Your year of watching"), util.url_for(action="year")),
        _action(T("Back-up maken of terugzetten", "Backup and restore"), util.url_for(action="backup")),
        _action(T("Foutrapport maken", "Make an error report"), util.url_for(action="report")),
        _action(T("Cache wissen", "Clear cache"), util.url_for(action="clear_cache")),
    ]
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
    import services
    rows = [items.folder(T("Nieuwste eerst", "Newest first"), util.url_for(action="list", name="provider", provider=params["provider"], type="all"))]
    rows += [items.folder(services.label(kind), util.url_for(action="list", name="service_list", provider=params["provider"], kind=kind))
             for kind in services.KINDS]
    send(handle, rows)


HISTORY = "search_history.json"


def search_menu(handle, _params):
    rows = [items.folder(T("Films zoeken", "Search movies"), util.url_for(action="search", type="movie"), "DefaultAddonsSearch.png"),
            items.folder(T("Series zoeken", "Search shows"), util.url_for(action="search", type="tvshow"), "DefaultAddonsSearch.png"),
            _action(T("Typ met je telefoon", "Type with your phone"), util.url_for(action="remote"), "DefaultAddonsSearch.png")]
    history = util.load_json(HISTORY, [])
    for kind, query in history:
        word = T("Film", "Movie") if kind == "movie" else T("Serie", "Show")
        rows.append(items.folder("%s: %s" % (word, query), util.url_for(action="search", type=kind, query=query), "DefaultAddonsSearch.png"))
    if history:
        rows.append((util.url_for(action="clear_history"), xbmcgui.ListItem(T("Zoekgeschiedenis wissen", "Clear search history"), offscreen=True), False))
    send(handle, rows)


def remember_search(kind, query):
    history = [entry for entry in util.load_json(HISTORY, []) if entry != [kind, query]]
    util.save_json(HISTORY, ([[kind, query]] + history)[:15])


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
    """Episodes still to come of what you follow, from today up to two months ahead, the first one first."""
    today = datetime.date.today()
    first, last = today.isoformat(), (today + datetime.timedelta(days=60)).isoformat()

    def load(show):
        try:
            _aired, coming = tmdb.on_air(show)
            if not coming:
                return []
            episodes = tmdb.season(show, coming["season_number"]).get("episodes") or [coming]
            found = []
            for episode in episodes:
                if first <= (episode.get("air_date") or "") <= last:
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
    """A list of titles. A row on Home (&widget=1) is served from its saved copy at once and refreshed after."""
    import widgets
    name = params.get("name", "")
    if name == "service_row":
        import services
        return send(handle, services.tiles())
    if name == "service_catalog":
        import services
        return send(handle, services.catalog_tiles())
    if name in ("lib_newseasons", "lib_newepisodes"):
        import librows
        return librows.send_row(handle, name)
    page = int(params.get("page") or 1)
    import hide
    cached = widgets.get(params) if widgets.wanted(params) else None
    if cached:
        send_titles(handle, hide.keep(cached.get("titles") or [], name), cached.get("content") or "")
        if widgets.is_old(params, cached):
            try:
                titles, content, _more = gather(params)
            except Exception as error:      # noqa: BLE001 - the copy stays; try again next time
                util.log("row %s not refreshed: %s" % (name, type(error).__name__))
                return None
            changed = not widgets.same(cached, titles, content)
            if titles or not cached.get("titles"):
                widgets.put(params, titles, content)
            if changed and titles:
                widgets.bump()
        return None
    titles, content, more = gather(params)
    if widgets.wanted(params) and titles:
        widgets.put(params, titles, content)
    next_url = util.url_for(**dict(params, page=page + 1)) if more and params.get("widget") != "1" else None     # a Home row has no next page
    send_titles(handle, hide.keep(titles, name), content, next_url)
    return None


def gather(params):
    """(titles, content, more pages?) of one list."""
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
    elif name == "new_seasons":
        import newseason
        titles, content = newseason.titles(), "tvshows"
    elif name == "tonight":
        import prefetch
        titles = prefetch.tonight_titles()
    elif name == "company":
        import browse
        titles, more = browse.company_titles(params.get("type", "movie"), params["id"], page)
        content = "movies" if params.get("type") == "movie" else "tvshows"
    elif name == "decade":
        import browse
        titles, more = browse.decade_titles(params.get("type", "movie"), params["start"], page)
        content = "movies" if params.get("type") == "movie" else "tvshows"
    elif name == "award":
        import browse
        titles, more = browse.award_titles(params["key"], page)
        content = "movies" if browse.AWARDS[params["key"]][1] == "movie" else "tvshows"
    elif name == "alerts":
        import alerts
        titles = alerts.titles()
    elif name.startswith("kompas"):
        import kompas
        titles = kompas.row_titles(name, params)
    elif name == "service_list":
        import services
        titles, more = services.titles(params["provider"], params.get("kind", "newmovie"), page)
        content = "movies" if params.get("kind", "").endswith("movie") else "tvshows"
    elif name == "new_tv":
        titles, more = tmdb.new_series(page)
        content = "tvshows"
    elif name in ("upcoming_movie", "upcoming_tv"):
        kind = "movie" if name == "upcoming_movie" else "tvshow"
        titles, more = tmdb.upcoming(kind, page)
        content = "movies" if kind == "movie" else "tvshows"
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
    return titles, content, more


def search(handle, params):
    query = params.get("query") or xbmcgui.Dialog().input(T("Zoeken", "Search"))
    if not query:
        return xbmcplugin.endOfDirectory(handle, succeeded=False)
    kind = params.get("type", "movie")
    page = int(params.get("page") or 1)
    if page == 1:
        remember_search(kind, query.strip())
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
    """Also for titles from other add-ons (the skin's info page): any TMDB id, movie, tvshow, season or episode."""
    meta, watched = _meta_for(params), params.get("value") == "1"
    if meta["kind"] in ("tvshow", "season") and not tracker.active() and not tmdb.key():
        return util.notify(T("Zonder TMDB-sleutel weet Lucent niet welke afleveringen er zijn", "Without a TMDB key Lucent does not know the episodes"))
    try:
        tracker.set_watched(meta, watched)
    except util.HttpError as error:
        util.log("watched: %s" % error)
        return util.notify(T("Je account is niet bereikbaar, er is niets gewijzigd", "Your account cannot be reached, nothing was changed"))
    util.log("marked %s %s %s" % (meta["kind"], meta["tmdb"], "watched" if watched else "unwatched"))
    util.notify(T("Gemarkeerd als bekeken", "Marked as watched") if watched else T("Gemarkeerd als niet bekeken", "Marked as unwatched"))
    import widgets
    widgets.mark_old(account_only=True)
    xbmc.executebuiltin("Container.Refresh")


def title_menu(params):
    """All of Lucent Video's options for one title, as one menu (for a '...' button on the skin's info page; works for
    titles from other add-ons too): choose source, ready for tonight, watched, intro, library and lists, trailer, cast,
    similar, rate."""
    meta = _meta_for(params)
    full = tmdb.details("movie" if meta["kind"] == "movie" else "tvshow", meta["tmdb"]) if tmdb.key() else None
    if full:
        meta = dict(full, kind=meta["kind"], season=meta.get("season"), episode=meta.get("episode"))
    meta.setdefault("title", "")
    if meta["kind"] == "movie":
        seen = meta["tmdb"] in tracker.watched_movies()
    elif meta["kind"] == "episode":
        seen = (int(meta["season"]), int(meta["episode"])) in tracker.watched_episodes().get(str(meta["tmdb"]), {})
    else:
        seen = False
    entries = items.context(meta, seen)
    if meta["kind"] in ("movie", "tvshow"):
        entries.insert(0, (T("Bibliotheek en lijsten", "Library and lists"), "RunPlugin(%s)" % util.url_for(action="lists", type=meta["kind"], tmdb=meta["tmdb"])))
    picked = xbmcgui.Dialog().contextmenu([label for label, _command in entries])
    if picked >= 0:
        command = entries[picked][1]
        if command.startswith("Container.Update("):          # from a dialog: open the list in the Videos window
            command = "ActivateWindow(Videos,%s,return)" % command[len("Container.Update("):-1]
        xbmc.executebuiltin(command)


def set_watchlist(params):
    tracker.set_watchlist(_meta_for(params), params.get("value") == "1")
    import widgets
    widgets.mark_old(account_only=True)
    util.notify(T("Kijklijst bijgewerkt", "Watchlist updated"))


def title(handle, params):
    """One film or series by TMDB id, as a list of one: for the skin's info page."""
    kind = params.get("type", "movie")
    meta = tmdb.details(kind, params["tmdb"])
    send_titles(handle, [meta] if meta else [], "movies" if kind == "movie" else "tvshows")


SECTIONS = {"general": -100, "account": -99, "trakt": -99, "sources": -98, "conn": -98, "play": -97, "subs": -96, "skip": -95,
            "library": -94, "services": -93}
SUBTITLE_ACTIONS = ("subtitles", "subs_auto", "subs_background", "subs_prefetch", "subs_key", "subs_mode", "subs_audio", "subs_default",
                    "subs_settings", "skip_settings", "subs_setup", "skip_setup", "skip_install", "skip_auto", "skip_choose")


def _once(name, job):
    """Only one at a time (the service and Kodi's search can ask within seconds)."""
    if util.HOME.getProperty(name):
        return None
    util.HOME.setProperty(name, "1")
    try:
        return job()
    finally:
        util.HOME.clearProperty(name)


def subtitle_action(action):
    """Subtitles, spoken language and skip intro (taken over from the Lucent skin)."""
    import subs_live
    if action == "subtitles":
        return subs_live.open_once(auto=False)
    if action == "subs_auto":
        return subs_live.open_once(auto=True)
    if action == "subs_background":
        return _once("lucent.subs.bg", subs_live.background)
    if action == "subs_prefetch":
        import subs_extra
        return _once("lucent.subs.prefetch", subs_extra.prefetch)
    if action == "subs_key":
        return subs_live.enter_key()
    if action == "subs_mode":
        return subs_live.choose_mode()
    if action == "subs_audio":
        return subs_live.choose_audio()
    if action == "subs_default":
        import subwatch
        return subwatch.set_default()
    if action in ("subs_settings", "skip_settings"):
        return open_settings({"section": action.split("_")[0]})
    import subsetup
    if action == "skip_install":
        return subsetup.install_skip()
    if action == "skip_auto":
        subsetup.toggle_skip_auto()
        return util.notify(subsetup.skip_state())
    if action == "skip_choose":
        import skipdup
        skipdup.choose()
        return subsetup.subconf.publish()
    return subsetup.wizard(action.split("_")[0])


def open_settings(params):
    """Opens the add-on's settings on one part: general, account, sources, play, library or services."""
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


FOLDERS = {"kompasmenu": kompas_menu, "": home, "menu": menu, "tools": tools, "studios": studios, "decades": decades, "awards": awards, "traktmenu": trakt_menu, "traktlists": trakt_lists, "genres": genres,
           "searchmenu": search_menu, "cast": cast, "publiclists": public_lists, "floppylists": floppy_lists, "services": services, "service": service, "mdblistmenu": mdblist_menu, "mdblists": mdblists, "title": title, "list": list_titles, "search": search, "seasons": seasons, "episodes": episodes}


def run(argv):
    handle = int(argv[1])
    params = dict(urllib.parse.parse_qsl((argv[2] if len(argv) > 2 else "").lstrip("?")))
    action = params.get("action", "")
    try:
        if action in ("play", "seasons") and params.get("tmdb"):
            import kompas
            kompas.opened(params.get("type") or "tvshow", params["tmdb"])
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
        if action == "cast_popup":
            import castui
            return castui.open_cast(params.get("type", "movie"), params["tmdb"])
        if action == "pick":
            import pick
            return pick.open_pick()
        if action == "year":
            import year
            return year.open_year()
        if action == "alerts_now":
            import alerts
            return alerts.run()
        if action == "abo_choose":
            import abo
            return abo.choose()
        if action == "learn_forget":
            import learn
            return learn.forget()
        if action == "service_open":
            import services
            return services.open_service(params)
        if action == "backup":
            import backup
            return backup.menu()
        if action == "clear_history":
            util.save_json(HISTORY, [])
            return xbmc.executebuiltin("Container.Refresh")
        if action == "trailer":
            meta = tmdb.details(params.get("type", "movie"), params["tmdb"])
            if meta and meta.get("trailer"):
                return xbmc.executebuiltin("PlayMedia(%s)" % meta["trailer"])
            return util.notify(T("Geen trailer gevonden", "No trailer found"))
        if action == "remote":
            import remote
            return remote.open_screen()
        if action == "prefetch_now":
            import prefetch
            return prefetch.run()
        if action == "newseason_now":
            import newseason
            return newseason.run()
        if action == "introskip":
            import introskip
            return introskip.toggle(params["tmdb"])
        if action == "tonight_add":
            import prefetch
            return prefetch.add_tonight(params)
        if action == "account_info":
            import accountinfo
            return accountinfo.show(params.get("service", ""))
        if action == "test_debrid":
            import debrid
            ok, text = debrid.check(params.get("service", ""))
            return xbmcgui.Dialog().ok("Lucent" if ok else T("Niet gelukt", "Failed"), text)
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
        if action == "library_choose":
            if tracker.active() is not trakt:
                return xbmcgui.Dialog().ok("Lucent", T("Kiezen kan alleen met Trakt. Met Simkl gaat alles wat je volgt in de bibliotheek.",
                                                     "Choosing works with Trakt only. With Simkl everything you follow goes in the library."))
            if trakt.choose_library() and xbmcgui.Dialog().yesno("Lucent", T("Bibliotheek nu bijwerken?", "Update the library now?")):
                return library.run(manual=True)
            return None
        if action == "title_menu":
            return title_menu(params)
        if action == "lists":
            import lists
            return lists.open_lists(params.get("type", "movie"), params["tmdb"])
        if action in SUBTITLE_ACTIONS:
            return subtitle_action(action)
        if action == "hide_languages":
            import hide
            return hide.choose()
        if action == "widgets_refresh":
            import widgets
            return widgets.refresh_all()
        if action == "library_add":
            return library.add_one(params.get("type", "movie"), params["tmdb"])
        if action == "library_remove":
            return library.remove_one(params.get("type", "movie"), params["tmdb"])
        if action == "library_skip":
            return library.skip(params["tmdb"], params["season"], params.get("episode"))
        if action == "library_status":
            return library.publish_counts()
        if action.startswith("kompas_"):
            import kompas
            return kompas.action(action, params)
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
        if not tmdb.key() and action not in ("tools", ""):
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
