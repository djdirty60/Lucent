# -*- coding: utf-8 -*-
"""Lucent: edit the side menu (tabs) and the widgets of every tab.

RunScript(special://skin/scripts/menu.py)          open the editor
RunScript(special://skin/scripts/menu.py,init)     write the default menu if there is none yet
RunScript(special://skin/scripts/menu.py,reset)    ask, then restore the default menu

Everything is stored in skin strings (see gen_home.py for the names), so Home.xml can read it.
"""
import json
import re
import sys
import urllib.parse

import xbmc
import xbmcaddon
import xbmcgui
import xbmcvfs

VERSION = "1"
NTABS = 12
NWIDGETS = 10
SEREN = "plugin://plugin.video.seren/"         # only to turn old Seren rows (before 2.0) into the video add-on rows
HEADING = "Lucent"

# ----------------------------------------------------------------------------- texts
_NL = xbmc.getLanguage(xbmc.ISO_639_1) == "nl"
T = {
    "menu": ("Menu and widgets", "Menu en widgets"),
    "add_tab": ("+ Add a tab", "+ Tab toevoegen"),
    "reset": ("Restore the default menu", "Standaardmenu herstellen"),
    "reset_q": ("Restore the default menu? Your own tabs and widgets will be removed.",
                "Standaardmenu herstellen? Je eigen tabs en widgets worden verwijderd."),
    "widgets_n": ("{0} widgets", "{0} widgets"),
    "no_widgets": ("no widgets (shows the start tab's)", "geen widgets (toont die van de start-tab)"),
    "start": ("start tab", "start-tab"),
    "manage_widgets": ("Widgets on this tab", "Widgets op deze tab"),
    "rename": ("Name", "Naam"),
    "icon": ("Icon", "Pictogram"),
    "action": ("When clicked", "Bij klikken"),
    "up": ("Move up", "Omhoog"),
    "down": ("Move down", "Omlaag"),
    "make_start": ("Make this the start tab", "Maak dit de start-tab"),
    "remove_tab": ("Remove this tab", "Deze tab verwijderen"),
    "remove_tab_q": ("Remove the tab \"{0}\" and its widgets?", "De tab \"{0}\" en zijn widgets verwijderen?"),
    "max_tabs": ("You can have at most {0} tabs.", "Je kunt maximaal {0} tabs hebben."),
    "max_widgets": ("A tab can have at most {0} widgets.", "Een tab kan maximaal {0} widgets hebben."),
    "add_widget": ("+ Add a widget", "+ Widget toevoegen"),
    "style": ("Style", "Stijl"),
    "sort": ("Sort", "Sorteren"),
    "limit": ("Number of titles", "Aantal titels"),
    "title_img": ("Title picture (instead of the name)", "Titelafbeelding (in plaats van de naam)"),
    "bg_img": ("Background while in this row", "Achtergrond in deze rij"),
    "title_hide": ("Hide the title of this row", "Titel van deze rij verbergen"),
    "title_show": ("Show the title of this row again", "Titel van deze rij weer tonen"),
    "own_set": ("your own", "eigen"),
    "own_none": ("none", "geen"),
    "img_file": ("Choose a picture…", "Kies een afbeelding…"),
    "img_url": ("Type an address (http… or a path)…", "Adres typen (http… of een pad)…"),
    "img_none": ("No picture of my own", "Geen eigen afbeelding"),
    "icon_own": ("Picture of my own…", "Eigen afbeelding…"),
    "edit_services": ("Choose the streaming services…", "Streamingdiensten kiezen…"),
    "same_changed": ("Also changed on {0} other tab(s) with the same widget", "Ook aangepast op {0} andere tab(s) met dezelfde widget"),
    "poster": ("Posters", "Posters"),
    "land": ("Landscape", "Liggend"),
    "remove_widget": ("Remove this widget", "Deze widget verwijderen"),
    "src_trakt": ("Trakt lists (liked or your own)", "Trakt-lijsten (leuk gevonden of eigen)"),
    "src_library": ("Kodi library", "Kodi-bibliotheek"),
    "src_browse": ("Browse an add-on…", "Bladeren in een add-on…"),
    "src_type": ("Type a path…", "Pad zelf typen…"),
    "use_folder": ("✔ Use this folder: {0}", "✔ Deze map gebruiken: {0}"),
    "empty_folder": ("This folder is empty or could not be opened.", "Deze map is leeg of kon niet worden geopend."),
    "loading": ("Loading…", "Laden…"),
    "act_widgets": ("Show the widgets of this tab", "De widgets van deze tab tonen"),
    "act_window": ("Open a Kodi screen…", "Een Kodi-scherm openen…"),
    "act_folder": ("Open a folder of an add-on…", "Een map van een add-on openen…"),
    "act_addon": ("Start an add-on…", "Een add-on starten…"),
    "act_fav": ("Open a favourite…", "Een favoriet openen…"),
    "act_type": ("Type a Kodi command…", "Zelf een Kodi-opdracht typen…"),
    "no_favs": ("You have no favourites yet.", "Je hebt nog geen favorieten."),
    "saved": ("Saved", "Opgeslagen"),
    "new_tab": ("New tab", "Nieuwe tab"),
    # default tab names
    "t_search": ("Search", "Zoeken"),
    "t_home": ("Home", "Start"),
    "t_movies": ("Movies", "Films"),
    "t_shows": ("TV shows", "Series"),
    "t_library": ("Library", "Bibliotheek"),
    "t_addons": ("Add-ons", "Add-ons"),
    "t_favourites": ("Favourites", "Favorieten"),
    "t_calendar": ("Calendar", "Kalender"),
    "t_sport": ("Sport", "Sport"),
    "t_tv": ("TV", "TV"),
    "t_settings": ("Settings", "Instellingen"),
    "t_power": ("Power", "Afsluiten"),
    # widget names
    "w_nextup": ("Continue watching · Shows", "Verder kijken · Series"),
    "w_ondeck": ("Continue watching · Movies", "Verder kijken · Films"),
    "w_trend_m": ("Trending movies", "Trending films"),
    "w_trend_s": ("Trending shows", "Trending series"),
    "w_pop_m": ("Popular movies", "Populaire films"),
    "w_pop_s": ("Popular shows", "Populaire series"),
    "w_ant_m": ("Most anticipated movies", "Meest verwachte films"),
    "w_ant_s": ("Most anticipated shows", "Meest verwachte series"),
    "w_box": ("Box office", "Box office"),
    "w_wl_m": ("Watchlist · Movies", "Kijklijst · Films"),
    "w_wl_s": ("Watchlist · Shows", "Kijklijst · Series"),
    "w_upcoming": ("Upcoming episodes", "Binnenkort: afleveringen"),
    "w_new_s": ("New shows", "Nieuwe series"),
    "w_recent_m": ("Recently added movies", "Recent toegevoegde films"),
    "w_recent_e": ("Recently added episodes", "Recent toegevoegde afleveringen"),
    "w_inprog_s": ("Shows in progress", "Series die je kijkt"),
    "w_all_m": ("All movies", "Alle films"),
    "w_all_s": ("All shows", "Alle series"),
    # Kodi screens
    "k_library": ("Video library", "Videobibliotheek"),
    "k_lib_m": ("Library · Movies", "Bibliotheek · Films"),
    "k_lib_s": ("Library · Shows", "Bibliotheek · Series"),
    "k_files": ("Video files", "Videobestanden"),
    "k_addons": ("Add-on browser", "Add-ons"),
    "k_vaddons": ("Video add-ons", "Video-add-ons"),
    "k_favs": ("Favourites", "Favorieten"),
    "k_settings": ("Settings", "Instellingen"),
    "k_skinsettings": ("Skin settings", "Skin-instellingen"),
    "k_music": ("Music", "Muziek"),
    "k_pictures": ("Pictures", "Foto's"),
    "k_power": ("Power menu", "Afsluitmenu"),
}


def tr(key, *args):
    text = (key if isinstance(key, tuple) else T[key])[1 if _NL else 0]
    return text.format(*args) if args else text


# ----------------------------------------------------------------------------- skin strings
def get(name):
    return xbmc.getInfoLabel(f"Skin.String({name})")


def put(name, value):
    value = (value or "").replace('"', "'")
    if value:
        xbmc.executebuiltin(f'Skin.SetString({name},"{value}")', True)
    else:
        xbmc.executebuiltin(f"Skin.Reset({name})", True)


def videos(path):
    return f"ActivateWindow(Videos,{path},return)"


def xsp(content, rules=None, order="title"):
    """A smart-playlist filter for a library path (videodb://…?xsp=…)."""
    data = {"type": content, "order": {"direction": "descending" if order in ("rating", "dateadded", "lastplayed") else "ascending",
                                       "method": order}}
    if rules:
        data["rules"] = {"and": [{"field": f, "operator": op, "value": [v] if v else []} for f, op, v in rules]}
    return urllib.parse.quote(json.dumps(data, separators=(",", ":")))


WIDGETS_LIBRARY = [                               # the Kodi library (works with every add-on that fills it)
    ("w_recent_m", "videodb://recentlyaddedmovies/", "poster"),
    ("w_recent_e", "videodb://recentlyaddedepisodes/", "land"),
    ("w_inprog_s", "videodb://inprogresstvshows/", "poster"),
    ("w_all_m", "videodb://movies/titles/", "poster"),
    ("w_all_s", "videodb://tvshows/titles/", "poster"),
    (("Random movies", "Willekeurige films"), "videodb://movies/titles/?xsp=" + xsp("movies", order="random"), "poster"),
    (("Unwatched movies", "Niet bekeken films"), "videodb://movies/titles/?xsp=" + xsp("movies", rules=[("playcount", "is", "0")], order="dateadded"), "poster"),
    (("Movies in progress", "Films die je kijkt"), "videodb://movies/titles/?xsp=" + xsp("movies", rules=[("inprogress", "true", "")], order="lastplayed"), "land"),
    (("Top rated movies", "Best beoordeelde films"), "videodb://movies/titles/?xsp=" + xsp("movies", order="rating"), "poster"),
    (("Random shows", "Willekeurige series"), "videodb://tvshows/titles/?xsp=" + xsp("tvshows", order="random"), "poster"),
    (("Unwatched shows", "Niet bekeken series"), "videodb://tvshows/titles/?xsp=" + xsp("tvshows", rules=[("playcount", "is", "0")], order="dateadded"), "poster"),
    (("Movie sets", "Filmreeksen"), "videodb://movies/sets/", "poster"),
    (("Movie genres", "Filmgenres"), "videodb://movies/genres/", "land"),
    (("TV genres", "Seriegenres"), "videodb://tvshows/genres/", "land"),
    (("Music videos", "Muziekvideo's"), "videodb://musicvideos/titles/", "land"),
    (("Recently added albums", "Recent toegevoegde albums"), "musicdb://recentlyaddedalbums/", "poster"),
    (("Recently played albums", "Recent afgespeelde albums"), "musicdb://recentlyplayedalbums/", "poster"),
    (("Most played albums", "Meest afgespeelde albums"), "musicdb://top100/albums/", "poster"),
    (("Random albums", "Willekeurige albums"), "musicdb://albums/?xsp=" + xsp("albums", order="random"), "poster"),
    (("Artists", "Artiesten"), "musicdb://artists/", "poster"),
    (("Video sources", "Videobronnen"), "sources://video/", "land"),
]
LV = "plugin://plugin.video.lucent/?action=list&widget=1&name="
WIDGETS_LV = [                                      # the video add-on (plugin.video.lucent): rows without a 'next page' item
    (("Films · Trending", "Films · Trending"), LV + "trending_movie", "poster"),
    (("Films · Popular", "Films · Populair"), LV + "popular_movie", "poster"),
    (("Films · Top rated", "Films · Best beoordeeld"), LV + "toprated_movie", "poster"),
    (("Films · In cinemas", "Films · In de bioscoop"), LV + "nowplaying_movie", "poster"),
    (("Films · Coming soon", "Films · Binnenkort"), LV + "upcoming_movie", "poster"),
    (("Series · Trending", "Series · Trending"), LV + "trending_tv", "poster"),
    (("Series · Popular", "Series · Populair"), LV + "popular_tv", "poster"),
    (("Series · Top rated", "Series · Best beoordeeld"), LV + "toprated_tv", "poster"),
    (("Series · On the air", "Series · Nu op tv"), LV + "airing_tv", "poster"),
    (("Series · Coming soon", "Series · Binnenkort"), LV + "upcoming_tv", "poster"),
    (("Series · New", "Series · Nieuw"), LV + "new_tv", "poster"),
    (("Continue watching", "Verder kijken"), LV + "continue", "land"),
    (("Continue watching · Films", "Verder kijken · Films"), LV + "continue_movie", "land"),
    (("Continue watching · Episodes", "Verder kijken · Afleveringen"), LV + "continue_episode", "land"),
    (("Next up", "Volgende afleveringen"), LV + "nextup", "land"),
    (("Series · Continue watching and next up", "Series · Verder kijken en volgende aflevering"), LV + "watching", "land"),
    (("Watchlist · Films", "Kijklijst · Films"), LV + "watchlist_movie", "poster"),
    (("Watchlist · Series", "Kijklijst · Series"), LV + "watchlist_tv", "poster"),
    (("Watchlist · Coming soon", "Kijklijst · Komt binnenkort uit"), LV + "coming_watchlist", "poster"),
    (("Collection · Films", "Collectie · Films"), LV + "collection_movie", "poster"),
    (("Collection · Series", "Collectie · Series"), LV + "collection_tv", "poster"),
    (("Calendar · New episodes", "Kalender · Nieuwe afleveringen"), LV + "calendar", "land"),
    (("For you", "Voor jou"), LV + "foryou", "poster"),
    (("Ready in top quality", "Klaar in topkwaliteit"), LV + "alerts", "land"),
    (("Ready for tonight", "Klaargezet voor vanavond"), LV + "tonight", "land"),
    (("Series · New seasons announced", "Series · Nieuwe seizoenen aangekondigd"), LV + "new_seasons", "poster"),
    (("Films · Oscar: Best Picture", "Films · Oscar: beste film"), LV + "award&key=oscar_picture", "poster"),
    (("Films · Oscar: Best Animated Feature", "Films · Oscar: beste animatiefilm"), LV + "award&key=oscar_animated", "poster"),
    (("Films · Palme d'Or (Cannes)", "Films · Gouden Palm (Cannes)"), LV + "award&key=palme", "poster"),
    (("Series · Emmy: Best Drama", "Series · Emmy: beste dramaserie"), LV + "award&key=emmy_drama", "poster"),
    (("Series · Emmy: Best Comedy", "Series · Emmy: beste comedyserie"), LV + "award&key=emmy_comedy", "poster"),
]


def pick_lv_list():
    """Your own and liked lists of Trakt and MDBList, and your Floppy lists, as a row (no 'next page' item)."""
    base = "plugin://plugin.video.lucent/?action="
    found = []
    busy(True)
    for folder, tag in (("traktlists&kind=mine", "Trakt"), ("traktlists&kind=liked", "Trakt"), ("mdblists&kind=mine", "MDBList"),
                        ("mdblists&kind=liked", "MDBList"), ("floppylists", "Floppy")):
        for f in jsonrpc("Files.GetDirectory", {"directory": base + folder, "media": "files"}).get("files", []) or []:
            path = f.get("file", "")
            if "action=list" in path and path not in [x[1] for x in found]:
                found.append((clean(f.get("label")), path, tag))
    busy(False)
    if not found:
        xbmcgui.Dialog().ok(HEADING, tr(G("No lists found. Log in to Trakt or set your MDBList key or Floppy in your video add-on.",
                                          "Geen lijsten gevonden. Log in bij Trakt of vul je MDBList-sleutel of Floppy in bij je video-add-on.")))
        return None
    pick = select(tr(G("Your lists", "Je lijsten")), [f[0] for f in found], True, ["icons/list.png"] * len(found), [f[2] for f in found])
    if pick < 0:
        return None
    name, path, _tag = found[pick]
    return name, path + ("&" if "?" in path else "?") + "widget=1", "poster"


def pick_lv_person():
    """Search a person on TMDb (the key of Lucent, else of the video add-on): a row with their best-known films and series."""
    name = keyboard(tr(G("Name of the actor or actress", "Naam van de acteur of actrice")))
    if not name:
        return None
    import json
    import urllib.parse
    import urllib.request
    import xbmcaddon
    import info
    key = info.tmdb_key()
    if not key:
        try:
            key = (xbmcaddon.Addon("plugin.video.lucent").getSetting("tmdb_key") or "").strip() \
                if xbmc.getCondVisibility("System.HasAddon(plugin.video.lucent)") else ""
        except Exception:  # noqa: BLE001
            key = ""
    if not key:
        xbmcgui.Dialog().ok(HEADING, tr(G("Lucent needs a TMDb key for this (Skin settings > Integrations).",
                                          "Lucent heeft hiervoor een TMDb-sleutel nodig (Skin-instellingen > Integraties).")))
        return None
    busy(True)
    try:
        url = "https://api.themoviedb.org/3/search/person?" + urllib.parse.urlencode({"api_key": key, "query": name})
        with urllib.request.urlopen(url, timeout=15) as response:
            people = json.loads(response.read().decode("utf-8")).get("results") or []
    except Exception as error:  # noqa: BLE001
        xbmc.log(f"[skin.lucent] menu: person search failed: {type(error).__name__}", xbmc.LOGWARNING)
        people = []
    busy(False)
    people = [p for p in people if p.get("id")][:20]
    if not people:
        notify(tr(G("Nobody found with that name", "Niemand gevonden met die naam")))
        return None
    known = lambda p: ", ".join(k.get("title") or k.get("name") or "" for k in (p.get("known_for") or [])[:2])  # noqa: E731
    pick = select(tr(G("Who do you mean?", "Wie bedoel je?")), [p.get("name", "") for p in people], True,
                  [f"https://image.tmdb.org/t/p/w185{p['profile_path']}" if p.get("profile_path") else "icons/user.png" for p in people],
                  [known(p) for p in people])
    if pick < 0:
        return None
    person = people[pick]
    return person.get("name", ""), LV + f"person&id={person['id']}", "poster"


def has_lv():
    return xbmc.getCondVisibility("System.HasAddon(plugin.video.lucent)")


def log(text):
    xbmc.log(f"[skin.lucent] menu: {text}", xbmc.LOGINFO)


def lv_ready():
    """The video add-on has a TMDB key (its own setting or the tester code's keys.json): its rows can fill."""
    if not has_lv():
        return False
    try:
        if xbmc.getCondVisibility("System.HasAddon(plugin.video.lucent)") and \
                xbmcaddon.Addon("plugin.video.lucent").getSetting("tmdb_key"):
            return True
    except Exception:  # noqa: BLE001
        return False
    return xbmcvfs.exists("special://profile/addon_data/plugin.video.lucent/keys.json")


def use_lv():
    """The default rows come from the video add-on: it is installed."""
    return has_lv()


LVA = "plugin://plugin.video.lucent/?action="
SEREN_TO_LV = [  # (part of a Seren row address, the video add-on row name): the first match wins
    ("showsNextUp", "nextup"), ("onDeckMovies", "continue_movie"),
    ("mediatype=movies&endpoint=trending", "trending_movie"), ("mediatype=shows&endpoint=trending", "trending_tv"),
    ("mediatype=movies&endpoint=popular", "popular_movie"), ("mediatype=shows&endpoint=popular", "popular_tv"),
    ("mediatype=movies&endpoint=anticipated", "upcoming_movie"), ("mediatype=shows&endpoint=anticipated", "upcoming_tv"),
    ("endpoint=boxoffice", "nowplaying_movie"), ("showsNew", "new_tv"), ("moviesMyWatchlist", "watchlist_movie"),
    ("showsMyWatchlist", "watchlist_tv"), ("myUpcomingEpisodes", "calendar"), ("movieTrendingRecent", "trending_movie"),
    ("moviePopularRecent", "popular_movie"), ("showsTrendingRecent", "trending_tv"), ("showsPopularRecent", "popular_tv"),
    ("moviesRecommended", "foryou"), ("showsRecommended", "foryou"), ("moviesMyCollection", "collection_movie"),
    ("mediatype=shows", "popular_tv"), ("action=shows", "popular_tv"), ("", "popular_movie")]
SEREN_TABS = [("action=searchMenu", "searchmenu"), ("action=moviesHome", "menu&type=movie"), ("action=showsHome", "menu&type=tvshow")]


LIB_TO_LV = [  # (part of a Lucent Library row address, the video add-on row name): the first match wins
    ("kind=continue&only=movie", "continue_movie"), ("kind=continue&only=tv", "continue_episode"), ("kind=continue", "continue"),
    ("kind=nextup", "nextup"), ("kind=newepisodes", "nextup"), ("kind=newseasons", "nextup"),
    ("kind=newin&only=tv", "collection_tv"), ("kind=newin", "collection_movie"),
    ("list=trakt_watchlist_movie", "watchlist_movie"), ("list=trakt_watchlist_tv", "watchlist_tv"),
    ("list=trakt_recommended", "foryou"), ("list=trakt_trending_movie", "trending_movie"), ("list=trakt_trending_tv", "trending_tv"),
    ("list=trakt_anticipated_movie", "upcoming_movie"), ("list=trakt_anticipated_tv", "upcoming_tv"),
    ("list=trending_movie", "trending_movie"), ("list=trending_tv", "trending_tv"), ("list=popular_movie", "popular_movie"),
    ("list=popular_tv", "popular_tv"), ("list=toprated_movie", "toprated_movie"), ("list=toprated_tv", "toprated_tv"),
    ("list=nowplaying_movie", "nowplaying_movie"), ("list=upcoming_movie", "upcoming_movie"), ("list=airing_tv", "airing_tv"),
    ("_tv", "popular_tv"), ("", "popular_movie")]


def lv_path(path, seren_too=True, lib_too=False):
    """The the video add-on row for a Seren row, a Lucent Library streaming row, or (lib_too: Lucent Library is not
    installed) any other Lucent Library row; '' when there is none."""
    if seren_too and path.startswith(SEREN):
        return LV + next(name for part, name in SEREN_TO_LV if part in path)
    if path.startswith("plugin://script.lucent.library/?action=providers"):
        return LV + "service_row"
    found = re.search(r"^plugin://script\.lucent\.library/\?action=tmdb\w*&list=prov_(\d+)_(\w+)$", path)
    if found:
        return LV + f"service_list&provider={found.group(1)}&kind={found.group(2)}"
    if lib_too and path.startswith("plugin://script.lucent.library/"):
        return LV + next(name for part, name in LIB_TO_LV if part in path)
    return ""


def lv_convert():
    """Old Seren rows and the streaming rows of Lucent Library become the video add-on rows.
    Runs from Home until there is nothing left to change and the video add-on has its key."""
    if not has_lv():
        return
    seren_too, services_too = True, lv_ready()        # old Seren rows (from before 2.0) become the video add-on rows
    lib_too = True                                      # Lucent Library is no longer used: its rows never fill
    menu = Menu()
    changed = False
    for tab in menu.tabs:
        if seren_too and tab["action"].startswith(f"ActivateWindow(Videos,{SEREN}"):
            new = next((videos(LVA + lv) for part, lv in SEREN_TABS if part in tab["action"]), "")
            if new:
                tab["action"], changed = new, True
        for wd in tab["widgets"]:
            path = wd["path"]
            if path.startswith(SEREN) and not seren_too:
                continue
            if not path.startswith(SEREN) and not services_too and not lib_too:
                continue
            new = lv_path(path, seren_too, lib_too)
            if new and new != path:
                wd["path"], changed = new, True
    if changed:
        menu.save()
        log(f"rows moved to the video add-on (seren={seren_too}, services={services_too}, library={lib_too})")
        xbmc.executebuiltin("Container.Refresh")
    if services_too:
        put("lucent.lvrows", "done4")                       # done4: Lucent Library rows converted too (1.39.0)


def lv_knows(name):
    """True when the installed the video add-on knows this row (it can also go back to an older version)."""
    try:
        with open(xbmcvfs.translatePath("special://home/addons/plugin.video.lucent/resources/lib/router.py"), encoding="utf-8") as fh:
            return f'"{name}"' in fh.read()
    except OSError:
        return False


def pick_lv():
    """A the video add-on row: one of its lists, or a streaming service (newest first)."""
    service = tr(G("A streaming service (newest first)…", "Een streamingdienst (nieuwste eerst)…"))
    own = tr(G("One of your lists (Trakt, MDBList, Floppy)…", "Een van je lijsten (Trakt, MDBList, Floppy)…"))
    actor = tr(G("An actor or actress…", "Een acteur of actrice…"))
    newer = ("coming_watchlist", "watching")                   # rows only newer versions of the video add-on know
    rows = [r for r in WIDGETS_LV if not any(r[1].endswith("name=" + n) for n in newer) or
            any(r[1].endswith("name=" + n) and lv_knows(n) for n in newer)]
    labels = [tr(k) for k, _p, _s in rows] + [own, actor, service]
    choice = select(tr(G("Your video add-on", "Je video-add-on")), labels)
    if choice < 0:
        return None
    if choice < len(rows):
        key, path, style = rows[choice]
        return tr(key), path, style
    if choice == len(rows):
        return pick_lv_list()
    if choice == len(rows) + 1:
        return pick_lv_person()
    busy(True)
    entries = jsonrpc("Files.GetDirectory", {"directory": "plugin://plugin.video.lucent/?action=services",
                                             "media": "files", "properties": ["title", "thumbnail"]}).get("files", []) or []
    busy(False)
    entries = [e for e in entries if "provider=" in e.get("file", "")]
    if not entries:
        xbmcgui.Dialog().ok(HEADING, tr(G("No services found. Your video add-on needs its TMDb key.",
                                          "Geen diensten gevonden. Je video-add-on heeft zijn TMDb-sleutel nodig.")))
        return None
    pick = select(tr(G("Streaming services", "Streamingdiensten")), [clean(e.get("label") or e.get("title")) for e in entries],
                  True, [e.get("thumbnail", "") for e in entries])
    if pick < 0:
        return None
    import urllib.parse
    q = urllib.parse.parse_qs(entries[pick]["file"].split("?", 1)[1])
    pid, pname = (q.get("provider") or [""])[0], clean(entries[pick].get("label") or "")
    if not pid:
        return None
    return f"{pname} · {tr(G('Newest', 'Nieuwste'))}", LV + f"provider&provider={pid}&type=all", "poster"


WIDGETS_OTHER = [
    (("Favourites", "Favorieten"), "favourites://", "land"),
    (("Video add-ons", "Video-add-ons"), "addons://sources/video/", "poster"),
    (("Program add-ons", "Programma-add-ons"), "addons://sources/executable/", "poster"),
    (("Music add-ons", "Muziek-add-ons"), "addons://sources/audio/", "poster"),
    (("Recently updated add-ons", "Recent bijgewerkte add-ons"), "addons://recently_updated/", "poster"),
    (("All installed add-ons", "Alle geïnstalleerde add-ons"), "addons://user/", "poster"),
    (("Installed video add-ons", "Geïnstalleerde video-add-ons"), "addons://user/xbmc.addon.video", "poster"),
    (("Installed program add-ons", "Geïnstalleerde programma-add-ons"), "addons://user/xbmc.addon.executable", "poster"),
    (("Add-ons with an update", "Add-ons met een update"), "addons://outdated/", "poster"),
    (("Add-ons to install: video", "Video-add-ons om te installeren"), "addons://repository/xbmc.addon.video", "poster"),
    (("Pictures", "Afbeeldingen"), "sources://pictures/", "land"),
    (("Music sources", "Muziekbronnen"), "sources://music/", "land"),
    (("TV channels", "TV-zenders"), "pvr://channels/tv/", "land"),
]
G = lambda en, nl: (en, nl)  # noqa: E731 - inline translation
ACTION_GROUPS = [
    (G("Video library", "Videobibliotheek"), "icons/library.png", [
        ("k_library", "icons/library.png", videos("videodb://")),
        (G("Search the library", "Bibliotheek doorzoeken"), "icons/search.png", "VideoLibrary.Search"),
        ("k_lib_m", "icons/movies.png", videos("videodb://movies/titles/")),
        ("k_lib_s", "icons/tv.png", videos("videodb://tvshows/titles/")),
        (G("Movie sets", "Filmreeksen"), "icons/movies.png", videos("videodb://movies/sets/")),
        (G("Movie genres", "Filmgenres"), "icons/movies.png", videos("videodb://movies/genres/")),
        (G("TV genres", "Seriegenres"), "icons/tv.png", videos("videodb://tvshows/genres/")),
        (G("Recently added movies", "Recent toegevoegde films"), "icons/movies.png", videos("videodb://recentlyaddedmovies/")),
        (G("Recently added episodes", "Recent toegevoegde afleveringen"), "icons/tv.png", videos("videodb://recentlyaddedepisodes/")),
        (G("Shows in progress", "Series die je kijkt"), "icons/tv.png", videos("videodb://inprogresstvshows/")),
        (G("Music videos", "Muziekvideo's"), "icons/music.png", videos("videodb://musicvideos/titles/")),
        ("k_files", "icons/files.png", videos("sources://video/")),
        (G("Video playlists", "Video-afspeellijsten"), "icons/list.png", videos("special://videoplaylists/")),
        (G("Update video library", "Videobibliotheek bijwerken"), "icons/refresh.png", "UpdateLibrary(video)"),
        (G("Clean video library", "Videobibliotheek opschonen"), "icons/refresh.png", "CleanLibrary(video)"),
    ]),
    (G("Music and pictures", "Muziek en foto's"), "icons/music.png", [
        ("k_music", "icons/music.png", "ActivateWindow(Music)"),
        (G("Artists", "Artiesten"), "icons/music.png", "ActivateWindow(Music,musicdb://artists/,return)"),
        (G("Albums", "Albums"), "icons/music.png", "ActivateWindow(Music,musicdb://albums/,return)"),
        (G("Songs", "Nummers"), "icons/music.png", "ActivateWindow(Music,musicdb://songs/,return)"),
        (G("Music playlists", "Muziek-afspeellijsten"), "icons/list.png", "ActivateWindow(Music,special://musicplaylists/,return)"),
        (G("Update music library", "Muziekbibliotheek bijwerken"), "icons/refresh.png", "UpdateLibrary(music)"),
        ("k_pictures", "icons/pictures.png", "ActivateWindow(Pictures)"),
    ]),
    (G("Add-ons and favourites", "Add-ons en favorieten"), "icons/addons.png", [
        ("k_addons", "icons/addons.png", "ActivateWindow(AddonBrowser)"),
        ("k_vaddons", "icons/addons.png", videos("addons://sources/video/")),
        (G("Program add-ons", "Programma-add-ons"), "icons/addons.png", "ActivateWindow(Programs,addons://sources/executable/,return)"),
        (G("Music add-ons", "Muziek-add-ons"), "icons/music.png", "ActivateWindow(Music,addons://sources/audio/,return)"),
        (G("Install from zip file", "Installeren vanuit zip-bestand"), "icons/download.png", "InstallFromZip"),
        (G("Check for add-on updates", "Zoeken naar add-on-updates"), "icons/refresh.png", "UpdateAddonRepos"),
        ("k_favs", "icons/favourites.png", "ActivateWindow(favouritesbrowser)"),
    ]),
    (G("Settings", "Instellingen"), "icons/settings.png", [
        ("k_settings", "icons/settings.png", "ActivateWindow(Settings)"),
        ("k_skinsettings", "icons/settings.png", "ActivateWindow(SkinSettings)"),
        (G("Player", "Speler"), "icons/play.png", "ActivateWindow(PlayerSettings)"),
        (G("Media", "Media"), "icons/library.png", "ActivateWindow(MediaSettings)"),
        (G("Interface", "Interface"), "icons/view.png", "ActivateWindow(InterfaceSettings)"),
        (G("Services", "Diensten"), "icons/globe.png", "ActivateWindow(ServiceSettings)"),
        (G("System", "Systeem"), "icons/settings.png", "ActivateWindow(SystemSettings)"),
        (G("Profiles", "Profielen"), "icons/user.png", "ActivateWindow(Profiles)"),
        (G("File manager", "Bestandsbeheer"), "icons/files.png", "ActivateWindow(FileManager)"),
        (G("System information", "Systeeminformatie"), "icons/info.png", "ActivateWindow(SystemInfo)"),
        (G("Event log", "Gebeurtenissenlogboek"), "icons/list.png", "ActivateWindow(EventLog)"),
        (G("Screen calibration", "Beeld kalibreren"), "icons/view.png", "ActivateWindow(ScreenCalibration)"),
    ] + [(G(f"{name} settings", f"{name}-instellingen"), "icons/settings.png", f"RunAddon({addon})")   # the box's own settings (network, updates ...)
         for addon, name in (("service.coreelec.settings", "CoreELEC"), ("service.libreelec.settings", "LibreELEC"))
         if xbmc.getCondVisibility(f"System.HasAddon({addon})")]),
    (G("Power and system", "Afsluiten en systeem"), "icons/power.png", [
        ("k_power", "icons/power.png", "ActivateWindow(ShutdownMenu)"),
        (G("Quit Kodi", "Kodi afsluiten"), "icons/power.png", "Quit"),
        (G("Restart device", "Apparaat herstarten"), "icons/refresh.png", "Reboot"),
        (G("Shut down device", "Apparaat uitzetten"), "icons/power.png", "Powerdown"),
        (G("Sleep", "Slaapstand"), "icons/power.png", "Suspend"),
        (G("Start screensaver", "Schermbeveiliging starten"), "icons/eye.png", "ActivateScreensaver"),
        (G("Log off profile", "Profiel afmelden"), "icons/user.png", "System.LogOff"),
        (G("Reload skin", "Skin herladen"), "icons/refresh.png", "ReloadSkin()"),
    ]),
]
# flat list, also used to describe an action
KODI_SCREENS = [entry for _g, _i, entries in ACTION_GROUPS for entry in entries]

ICONS = ["home", "search", "movies", "tv", "library", "star", "trakt", "favourites", "list", "eye", "play",
         "trailer", "calendar", "download", "addons", "folder", "files", "music", "pictures", "globe", "user",
         "bookmark", "info", "settings", "power"]
SHOW_WIDGETS = "SetFocus(9100)"


def widget(key, path, style):
    return {"label": tr(key), "path": path, "style": style}


def addon_widgets():
    """Rows shown when the Add-ons item is focused: video, program, music add-ons."""
    return [{"label": tr_pair(n), "path": p, "style": "land"} for n, p, _st in WIDGETS_OTHER[1:4]]


def tr_pair(pair):
    return pair[1] if xbmc.getLanguage(xbmc.ISO_639_1) == "nl" else pair[0]


def plain_tabs():
    """The default menu without a video add-on: the Kodi library, search, add-ons and favourites."""
    rows = {p: (n, st) for n, p, st in WIDGETS_LIBRARY}

    def row(path):
        name, style = rows[path]
        return {"label": tr(name), "path": path, "style": style}

    by_en = {(n if isinstance(n, tuple) else T[n])[0]: p for n, p, _s in WIDGETS_LIBRARY}
    pick = by_en.__getitem__                          # a library row by its English name
    home = [row(pick("Movies in progress")), row("videodb://inprogresstvshows/"), row("videodb://recentlyaddedmovies/"),
            row("videodb://recentlyaddedepisodes/"), row(pick("Random movies"))]
    movies = [row("videodb://recentlyaddedmovies/"), row(pick("Movies in progress")), row(pick("Unwatched movies")),
              row(pick("Top rated movies")), row("videodb://movies/genres/")]
    shows = [row("videodb://inprogresstvshows/"), row("videodb://recentlyaddedepisodes/"),
             row(pick("Unwatched shows")), row("videodb://tvshows/genres/")]

    def tab(key, icon, action, widgets=None):
        return {"label": tr(key), "icon": f"icons/{icon}.png", "action": action, "widgets": widgets or []}

    return [
        tab("t_search", "search", "VideoLibrary.Search"),
        tab("t_home", "home", SHOW_WIDGETS, home),
        tab("t_movies", "movies", videos("videodb://movies/titles/"), movies),
        tab("t_shows", "tv", videos("videodb://tvshows/titles/"), shows),
        tab("t_addons", "addons", "ActivateWindow(AddonBrowser)", addon_widgets()),
        tab("t_favourites", "favourites", "ActivateWindow(favouritesbrowser)"),
        tab("t_settings", "settings", "ActivateWindow(Settings)"),
        tab("t_power", "power", "ActivateWindow(ShutdownMenu)"),
    ], 2


def lv_tabs():
    """The default menu with the video add-on: its rows on the tabs, its search and menus behind them."""
    lib_by_key = {k: (p, s) for k, p, s in WIDGETS_LIBRARY}
    names = {r[1].split("name=", 1)[1]: (r[0], r[2]) for r in WIDGETS_LV}
    names["new_tv"] = (("Series · New", "Series · Nieuw"), "poster")

    def row(name):
        label, style = names[name]
        return {"label": tr_pair(label), "path": LV + name, "style": style}

    home = [row("continue"), row("nextup"), row("trending_movie"), row("trending_tv"),
            widget("w_recent_m", *lib_by_key["w_recent_m"]), widget("w_recent_e", *lib_by_key["w_recent_e"])]
    movies = [row("continue_movie"), row("trending_movie"), row("popular_movie"), row("upcoming_movie"), row("nowplaying_movie")]
    shows = [row("nextup"), row("trending_tv"), row("popular_tv"), row("new_tv"), row("calendar")]
    library = [widget(k, *lib_by_key[k]) for k in ("w_recent_m", "w_recent_e", "w_inprog_s")]

    def tab(key, icon, action, widgets=None):
        return {"label": tr(key), "icon": f"icons/{icon}.png", "action": action, "widgets": widgets or []}

    return [
        tab("t_search", "search", videos(LVA + "searchmenu")),
        tab("t_home", "home", SHOW_WIDGETS, home),
        tab("t_movies", "movies", videos(LVA + "menu&type=movie"), movies),
        tab("t_shows", "tv", videos(LVA + "menu&type=tvshow"), shows),
        tab("t_library", "library", videos("videodb://"), library),
        tab("t_addons", "addons", "ActivateWindow(AddonBrowser)", addon_widgets()),
        tab("t_favourites", "favourites", "ActivateWindow(favouritesbrowser)"),
        tab("t_calendar", "calendar", "RunScript(special://skin/scripts/agenda.py)"),
        tab("t_settings", "settings", "ActivateWindow(Settings)"),
        tab("t_power", "power", "ActivateWindow(ShutdownMenu)"),
    ], 2


def default_tabs():
    """The default menu: the video add-on's rows when it is installed, else the Kodi library (plain_tabs)."""
    return lv_tabs() if has_lv() else plain_tabs()


# ----------------------------------------------------------------------------- load / save
class Menu:
    def __init__(self):
        self.snapshot = {}
        self.tabs = []
        for t in range(1, NTABS + 1):
            label = self._read(f"nuvio.tab{t}.label")
            if not label:
                continue
            widgets = []
            for w in range(1, NWIDGETS + 1):
                path = self._read(f"nuvio.tab{t}.w{w}.path")
                if path:
                    widgets.append({"label": self._read(f"nuvio.tab{t}.w{w}.label"), "path": path,
                                    "style": self._read(f"nuvio.tab{t}.w{w}.style") or "poster",
                                    "sort": self._read(f"nuvio.tab{t}.w{w}.sort"),
                                    "limit": self._read(f"nuvio.tab{t}.w{w}.limit"),
                                    "timg": self._read(f"nuvio.tab{t}.w{w}.timg"), "bg": self._read(f"nuvio.tab{t}.w{w}.bg"),
                                    "notitle": self._read(f"nuvio.tab{t}.w{w}.notitle")})
            self.tabs.append({"label": label, "icon": self._read(f"nuvio.tab{t}.icon"),
                              "action": self._read(f"nuvio.tab{t}.action"), "widgets": widgets,
                              "actionlabel": self._read(f"nuvio.tab{t}.actionlabel"),
                              "slot": t})
        # remember the start tab by object, so it follows moves
        start_slot = self._read("nuvio.hometab")
        self.start = None
        for tab in self.tabs:
            if str(tab["slot"]) == start_slot:
                self.start = tab
        for name in [f"nuvio.home.w{w}.{p}" for w in range(1, NWIDGETS + 1) for p in ("label", "path", "style", "sort", "limit", "timg", "bg", "notitle")] + ["nuvio.homepos"]:
            self._read(name)

    def _read(self, name):
        value = get(name)
        self.snapshot[name] = value
        return value

    def set_defaults(self):
        tabs, start_index = default_tabs()
        self.tabs = tabs
        self.start = tabs[start_index - 1]

    def start_tab(self):
        if self.start in self.tabs:
            return self.start
        for tab in self.tabs:
            if tab["action"] == SHOW_WIDGETS:
                return tab
        for tab in self.tabs:
            if tab["widgets"]:
                return tab
        return self.tabs[0] if self.tabs else None

    def save(self):
        wanted = {}
        for t in range(1, NTABS + 1):
            tab = self.tabs[t - 1] if t <= len(self.tabs) else None
            wanted[f"nuvio.tab{t}.label"] = tab["label"] if tab else ""
            wanted[f"nuvio.tab{t}.icon"] = tab["icon"] if tab else ""
            wanted[f"nuvio.tab{t}.action"] = tab["action"] if tab else ""
            wanted[f"nuvio.tab{t}.actionlabel"] = tab.get("actionlabel", "") if tab else ""
            for w in range(1, NWIDGETS + 1):
                wd = tab["widgets"][w - 1] if tab and w <= len(tab["widgets"]) else None
                for p in ("label", "path", "style", "sort", "limit", "timg", "bg", "notitle"):
                    wanted[f"nuvio.tab{t}.w{w}.{p}"] = wd.get(p, "") if wd else ""
        start = self.start_tab()
        start_index = self.tabs.index(start) if start else -1
        wanted["nuvio.hometab"] = str(start_index + 1) if start else ""
        wanted["nuvio.homepos"] = str(start_index) if start else ""
        for w in range(1, NWIDGETS + 1):
            wd = start["widgets"][w - 1] if start and w <= len(start["widgets"]) else None
            for p in ("label", "path", "style", "sort", "limit", "timg", "bg", "notitle"):
                wanted[f"nuvio.home.w{w}.{p}"] = wd.get(p, "") if wd else ""
        wanted["nuvio.menu.version"] = VERSION

        changes = [(k, v) for k, v in wanted.items() if self.snapshot.get(k, get(k)) != v]
        progress = None
        if len(changes) > 30:
            progress = xbmcgui.DialogProgressBG()
            progress.create(HEADING, tr("menu"))
        for n, (name, value) in enumerate(changes):
            put(name, value)
            self.snapshot[name] = value
            if progress:
                progress.update(int(n * 100 / len(changes)))
        if progress:
            progress.close()
        for n, tab in enumerate(self.tabs, start=1):
            tab["slot"] = n


# ----------------------------------------------------------------------------- helpers
def clean(label):
    return re.sub(r"\[/?(COLOR|B|I|UPPERCASE|LOWERCASE|CAPITALIZE)[^\]]*\]", "", label or "").strip()


def jsonrpc(method, params):
    request = {"jsonrpc": "2.0", "id": 1, "method": method, "params": params}
    try:
        return json.loads(xbmc.executeJSONRPC(json.dumps(request))).get("result", {}) or {}
    except Exception as error:  # noqa: BLE001 - never crash the skin
        xbmc.log(f"[skin.lucent] menu.py {method} failed: {error}", xbmc.LOGWARNING)
        return {}


def busy(on):
    xbmc.executebuiltin("ActivateWindow(busydialognocancel)" if on else "Dialog.Close(busydialognocancel)")


def select(heading, labels, details=False, icons=None, label2s=None):
    items = []
    for n, label in enumerate(labels):
        item = xbmcgui.ListItem(label, (label2s[n] if label2s else ""))
        if icons and icons[n]:
            item.setArt({"icon": icons[n], "thumb": icons[n]})
        items.append(item)
    return xbmcgui.Dialog().select(heading, items, useDetails=details)


def keyboard(heading, default=""):
    text = xbmcgui.Dialog().input(heading, default)
    return text.strip() if text else ""


def notify(text):
    xbmcgui.Dialog().notification(HEADING, text, xbmcgui.NOTIFICATION_INFO, 2500)


def video_addons(kinds=("xbmc.addon.video",)):
    """[(name, id, icon)] of the enabled add-ons of these kinds (video, and program add-ons where asked)."""
    busy(True)
    found = {}
    for kind in kinds:
        result = jsonrpc("Addons.GetAddons", {"type": kind, "enabled": True, "properties": ["name", "thumbnail"]})
        for a in result.get("addons", []) or []:
            found.setdefault(a.get("addonid"), a)
    busy(False)
    addons = sorted(found.values(), key=lambda a: a.get("name", "").lower())
    return [(clean(a.get("name")), a.get("addonid"), a.get("thumbnail")) for a in addons]


ALL_ADDONS = ("xbmc.addon.video", "xbmc.addon.executable")    # video and program add-ons (e.g. a dashboard)


def browse(heading):
    """Walk through add-on folders and return (label, path) of the chosen folder, or None."""
    addons = video_addons(ALL_ADDONS)
    if not addons:
        return None
    choice = select(heading, [a[0] for a in addons], True, [a[2] for a in addons])
    if choice < 0:
        return None
    stack = [(addons[choice][0], f"plugin://{addons[choice][1]}/")]
    while stack:
        name, path = stack[-1]
        busy(True)
        files = jsonrpc("Files.GetDirectory", {"directory": path, "media": "files",
                                               "properties": ["title", "thumbnail"]}).get("files", []) or []
        busy(False)
        folders = [f for f in files if f.get("filetype") == "directory" and f.get("file")]
        labels = [tr("use_folder", name)] + [clean(f.get("label") or f.get("title")) for f in folders]
        icons = [""] + [f.get("thumbnail", "") for f in folders]
        if not folders and len(stack) > 1 and not files:
            notify(tr("empty_folder"))
        choice = select(" / ".join(s[0] for s in stack), labels, True, icons)
        if choice < 0:
            stack.pop()
            continue
        if choice == 0:
            return name, path
        folder = folders[choice - 1]
        stack.append((clean(folder.get("label") or folder.get("title")), folder["file"]))
    return None


def pick_favourite():
    """A favourite that is a folder (a library node, an add-on folder, a smart playlist ...) as a widget: (name, path)."""
    favs = jsonrpc("Favourites.GetFavourites", {"properties": ["path", "window", "windowparameter", "thumbnail"]}).get("favourites") or []
    found = []
    for f in favs:
        path = f.get("windowparameter") if f.get("type") == "window" else f.get("path") if f.get("type") == "media" else ""
        path = (path or "").strip().strip('"')
        if path and not path.lower().startswith(("script://", "runscript")) and (path.endswith("/") or "://" in path or path.endswith(".xsp")):
            found.append((clean(f.get("title")), path, f.get("thumbnail") or "icons/favourites.png"))
    if not found:
        xbmcgui.Dialog().ok(HEADING, tr(G("None of your favourites is a folder that can be a widget (a library list, an add-on folder ...).",
                                          "Geen van je favorieten is een map die een widget kan zijn (een bibliotheeklijst, een map van een add-on ...).")))
        return None
    choice = select(tr(G("Favourites", "Favorieten")), [f[0] for f in found], True, [f[2] for f in found], [f[1] for f in found])
    return (found[choice][0], found[choice][1]) if choice >= 0 else None


def pick_playlist():
    found = []
    for folder in ("special://profile/playlists/video/", "special://profile/playlists/mixed/", "special://profile/playlists/music/"):
        files = jsonrpc("Files.GetDirectory", {"directory": folder, "media": "files"}).get("files", []) or []
        found += [(clean(f.get("label")), f.get("file")) for f in files if f.get("file", "").endswith((".xsp", ".m3u", ".m3u8"))]
    if not found:
        xbmcgui.Dialog().ok(HEADING, tr(G("You have no playlists yet. Make one in Kodi under Videos → Playlists.",
                                          "Je hebt nog geen afspeellijsten. Maak er een in Kodi via Video's → Afspeellijsten.")))
        return None
    choice = select(tr(G("Playlists", "Afspeellijsten")), [f[0] for f in found], True, ["icons/list.png"] * len(found))
    return found[choice] if choice >= 0 else None


# ----------------------------------------------------------------------------- editors
def pick_widget():
    sources = ["", "", tr("src_library"), tr("src_browse"), tr("src_type"),
               tr(G("Favourites and add-ons", "Favorieten en add-ons")), tr(G("A playlist…", "Een afspeellijst…")),
               tr(G("Lucent fast lists (TMDb)", "Lucent snelle lijsten (TMDb)")), tr(G("One of your favourites…", "Een van je favorieten…"))]
    icons = ["icons/play.png", "icons/trakt.png", "icons/library.png", "icons/addons.png", "icons/list.png",
             "icons/favourites.png", "icons/list.png", "icons/star.png", "icons/favourites.png"]
    # an add-on folder first (what you know from other skins); 0 and 1 were Seren's rows and lists (gone in 2.0)
    order = [3, 2, 8, 5, 6, 7, 4]
    order.remove(7)                                     # the fast TMDb lists of Lucent Library: the video add-on has them now
    if has_lv():                                        # the video add-on: its own rows first
        sources.append(tr(G("Your video add-on", "Je video-add-on")))
        icons.append("icons/play.png")
        order.insert(0, 9)
    pick = select(tr("add_widget"), [sources[i] for i in order], True, [icons[i] for i in order])
    source = order[pick] if pick >= 0 else -1
    style = "poster"
    if source == 9:
        picked = pick_lv()
        if not picked:
            return None
        label, path, style = picked
    elif source == 2:
        rows = WIDGETS_LIBRARY
        choice = select(tr("src_library"), [tr(k) for k, _p, _s in rows])
        if choice < 0:
            return None
        key, path, style = rows[choice]
        label = tr(key)
    elif source == 3:
        picked = browse(tr("src_browse"))
        if not picked:
            return None
        label, path = picked
    elif source == 5:
        choice = select(sources[5], [tr(k) for k, _p, _s in WIDGETS_OTHER])
        if choice < 0:
            return None
        key, path, style = WIDGETS_OTHER[choice]
        label = tr(key)
    elif source == 8:
        picked = pick_favourite()
        if not picked:
            return None
        label, path = picked
    elif source == 6:
        picked = pick_playlist()
        if not picked:
            return None
        label, path = picked
    elif source == 4:
        path = keyboard(tr("src_type"), "plugin://")
        if not path:
            return None
        label = path
    else:
        return None
    label = keyboard(tr("rename"), label) or label
    styles = ["poster", "land"]
    choice = select(tr("style"), [tr("poster"), tr("land")])
    if choice >= 0:
        style = styles[choice]
    return {"label": label, "path": path, "style": style}


def edit_widgets(menu, tab):
    while True:
        widgets = tab["widgets"]
        labels = [f"{w['label']}" for w in widgets] + [tr("add_widget")]
        label2s = [tr(w["style"]) for w in widgets] + [""]
        choice = select(f"{tab['label']} · {tr('manage_widgets')}", labels, True,
                        ["icons/list.png"] * len(widgets) + ["icons/plus.png"], label2s)
        if choice < 0:
            return
        if choice == len(widgets):
            if len(widgets) >= NWIDGETS:
                xbmcgui.Dialog().ok(HEADING, tr("max_widgets", NWIDGETS))
                continue
            new = pick_widget()
            if new:
                widgets.append(new)
                menu.save()
            continue
        wd = widgets[choice]
        own = lambda key: tr("own_set") if wd.get(key) else tr("own_none")  # noqa: E731
        options = []                                # (key, text): what the action is, not where it is in the list
        if "action=providers" in wd.get("path", "") or "name=service_row" in wd.get("path", ""):
            options.append(("services", tr("edit_services")))
        options += [("rename", tr("rename")),
                    ("change", tr(G("Change to another widget…", "Wijzigen naar een andere widget…"))),
                    ("style", f"{tr('style')}: {tr(wd['style'])}"),
                    ("sort", f"{tr('sort')}: {sort_name(wd.get('sort', ''))}"),
                    ("limit", f"{tr('limit')}: {limit_name(wd.get('limit', ''))}"),
                    ("timg", f"{tr('title_img')}: {own('timg')}"),
                    ("bg", f"{tr('bg_img')}: {own('bg')}"),
                    ("notitle", tr("title_show") if wd.get("notitle") else tr("title_hide")),
                    ("place", tr(G("Place: {0} of {1}", "Plaats: {0} van {1}"), choice + 1, len(widgets))),
                    ("remove", tr("remove_widget"))]
        pick_act = select(wd["label"], [text for _key, text in options])
        if pick_act < 0:
            continue
        act = options[pick_act][0]
        shared = True                               # the same widget on other tabs gets the same change
        if act == "services":
            import streamedit                       # in this script: a second script's list would clash with this one
            streamedit.editor()
            continue
        if act == "rename":
            wd["label"] = keyboard(tr("rename"), wd["label"]) or wd["label"]
        elif act == "change":
            new = pick_widget()
            if not new:
                continue
            wd["path"], wd["label"], wd["style"] = new["path"], new["label"], new.get("style") or wd["style"]
            wd["timg"] = ""                         # the title picture belonged to the old widget
            shared = False                          # a new widget: the others with the old address stay as they are
        elif act == "style":
            wd["style"] = "land" if wd["style"] == "poster" else "poster"
        elif act == "sort":
            pick = select(tr("sort"), [name for _key, name in SORTS()])
            if pick < 0:
                continue
            wd["sort"] = SORTS()[pick][0]
        elif act == "limit":
            pick = select(tr("limit"), [name for _key, name in LIMITS()])
            if pick < 0:
                continue
            wd["limit"] = LIMITS()[pick][0]
            source_page(wd)
        elif act in ("timg", "bg"):
            img = pick_image(tr("title_img") if act == "timg" else tr("bg_img"), wd.get(act, ""))
            if img is None:
                continue
            wd[act] = img
        elif act == "notitle":
            wd["notitle"] = "" if wd.get("notitle") else "1"
        elif act == "place":
            places = [tr(G("Place {0}", "Plaats {0}"), n + 1) + (f"  ·  {w['label']}" if n != choice else "  ·  " + tr(G("(here now)", "(nu hier)")))
                      for n, w in enumerate(widgets)]
            to = select(tr(G("Where should '{0}' go?", "Waar moet '{0}' komen?"), wd["label"]), places)
            if to < 0 or to == choice:
                continue
            widgets.insert(to, widgets.pop(choice))
            shared = False
        elif act == "remove":
            widgets.pop(choice)
            shared = False
        if shared:
            same = copy_to_same(menu, tab, wd)
            if same:
                notify(tr("same_changed", same))
        menu.save()


SHARED = ("label", "style", "sort", "limit", "timg", "bg", "notitle")


def copy_to_same(menu, tab, wd):
    """Name, style, sort and pictures of this widget also for the same widget (same address) on the other tabs.
    Returns how many were changed."""
    count = 0
    for other in menu.tabs:
        if other is tab:
            continue
        for w in other["widgets"]:
            if w.get("path") == wd.get("path") and any(w.get(k, "") != wd.get(k, "") for k in SHARED):
                for k in SHARED:
                    w[k] = wd.get(k, "")
                count += 1
    return count


def pick_image(heading, current=""):
    """A picture of your own: a file (also on the network), an address, or none. None = cancelled, '' = none."""
    options = [tr("img_file"), tr("img_url")] + ([tr("img_none")] if current else [])
    choice = select(heading, options)
    if choice == 0:
        path = xbmcgui.Dialog().browseSingle(2, heading, "files", ".png|.jpg|.jpeg|.webp|.gif", True)
        return path or None
    if choice == 1:
        text = keyboard(heading, current)
        return text or None
    if choice == 2:
        return ""
    return None


def SORTS():
    """(Kodi sort method for the Home row, name). Empty = the order of the source."""
    return [("", tr(G("As the source gives it", "Zoals de bron het geeft"))),
            ("title", tr(G("A–Z (title)", "A–Z (titel)"))),
            ("year", tr(G("Year (newest first)", "Jaar (nieuwste eerst)"))),
            ("rating", tr(G("Rating (highest first)", "Beoordeling (hoogste eerst)"))),
            ("dateadded", tr(G("Date added (newest first)", "Datum toegevoegd (nieuwste eerst)"))),
            ("lastplayed", tr(G("Last watched (newest first)", "Laatst bekeken (nieuwste eerst)"))),
            ("playcount", tr(G("Most watched first", "Meest bekeken eerst"))),
            ("random", tr(G("Random", "Willekeurig")))]


def LIMITS():
    """How many titles a Home row shows. Empty = 25 (fast, also on small boxes); 0 = all the source gives."""
    return [("", tr(G("25 (standard)", "25 (standaard)"))), ("50", "50"), ("100", "100"),
            ("0", tr(G("All (can make Home slower)", "Alle (kan Home trager maken)")))]


def source_page(wd):
    """The skin can only show what the source gives. Add-ons decide their own page size; say so."""
    want = {"": 25, "0": 100}.get(wd.get("limit", ""))
    try:
        want = want or int(wd.get("limit"))
    except (TypeError, ValueError):
        return
    path = wd.get("path", "")
    if path.startswith("plugin://plugin.video.lucent/"):
        return                                      # the video add-on has its own setting for the number of titles
    elif path.startswith("plugin://") and want > 25:
        notify(tr(G("The add-on decides how many titles it gives per page",
                    "De add-on bepaalt zelf hoeveel titels hij per pagina geeft")))


def limit_name(key):
    for k, name in LIMITS():
        if k == key:
            return name
    return LIMITS()[0][1]


def sort_name(key):
    for k, name in SORTS():
        if k == key:
            return name
    return SORTS()[0][1]


def addon_title(addon_id):
    return xbmc.getInfoLabel(f"System.AddonTitle({addon_id})") or addon_id


def describe_action(action, label=""):
    """A short, readable description of what a tab opens."""
    if action == SHOW_WIDGETS:
        return tr("act_widgets")
    for key, _icon, act in KODI_SCREENS:
        if act == action:
            return tr(key)
    if label:
        return label
    plugin = re.search(r"plugin://([^/?,)]+)", action)
    if plugin:
        return tr(G("Folder in {0}", "Map in {0}"), clean(addon_title(plugin.group(1))))
    run = re.match(r"RunAddon\(([^)]+)\)", action)
    if run:
        return tr(G("Start {0}", "{0} starten"), clean(addon_title(run.group(1))))
    return action if len(action) < 50 else action[:47] + "…"


def pick_action():
    options = [tr("act_widgets"), tr("act_window"), tr("act_folder"), tr("act_addon"), tr("act_fav"), tr("act_type")]
    icons = ["icons/home.png", "icons/view.png", "icons/folder.png", "icons/addons.png",
             "icons/favourites.png", "icons/list.png"]
    choice = select(tr("action"), options, True, icons)
    if choice == 0:
        return SHOW_WIDGETS, None
    while choice == 1:
        groups = ACTION_GROUPS
        group = select(tr("act_window"), [tr(g) for g, _i, _e in groups], True, [i for _g, i, _e in groups])
        if group < 0:
            return None, None
        entries = groups[group][2]
        pick = select(tr(groups[group][0]), [tr(k) for k, _i, _a in entries], True, [i for _k, i, _a in entries])
        if pick >= 0:
            key, icon, action = entries[pick]
            return action, (tr(key).split(" · ")[-1], icon)
    if choice == 2:
        picked = browse(tr("act_folder"))
        if picked:
            return videos(picked[1]), (picked[0], "icons/folder.png")
    if choice == 3:
        addons = video_addons(ALL_ADDONS)
        pick = select(tr("act_addon"), [a[0] for a in addons], True, [a[2] for a in addons])
        if pick >= 0:
            name, addonid, _thumb = addons[pick]
            return f"RunAddon({addonid})", (name, "icons/addons.png")
    if choice == 4:
        favs = jsonrpc("Favourites.GetFavourites", {"properties": ["path", "window", "windowparameter", "thumbnail"]})
        favs = favs.get("favourites") or []
        if not favs:
            xbmcgui.Dialog().ok(HEADING, tr("no_favs"))
            return None, None
        pick = select(tr("act_fav"), [clean(f.get("title")) for f in favs], True, [f.get("thumbnail", "") for f in favs])
        if pick >= 0:
            fav = favs[pick]
            if fav.get("type") == "window":
                action = f"ActivateWindow({fav.get('window')},{fav.get('windowparameter', '')},return)"
            elif fav.get("type") == "media":
                action = f"PlayMedia({fav.get('path')})"
            elif fav.get("type") == "script":
                action = f"RunScript({fav.get('path')})"
            else:
                action = fav.get("path", "")
            return action, (clean(fav.get("title")), "icons/star.png")
    if choice == 5:
        action = keyboard(tr("act_type"), "ActivateWindow(Videos,plugin://,return)")
        if action:
            return action, None
    return None, None


def pick_icon(current):
    labels = [name for name in ICONS] + [tr("icon_own")]
    icons = [f"icons/{name}.png" for name in ICONS] + ["icons/pictures.png"]
    choice = select(tr("icon"), labels, True, icons)
    if choice == len(ICONS):                         # a picture of your own (shown in its own colours)
        img = pick_image(tr("icon"), "" if current.startswith("icons/") else current)
        return img if img else current
    return icons[choice] if choice >= 0 else current


def edit_tab(menu, tab):
    while True:
        start = menu.start_tab() is tab
        actions = [f"{tr('manage_widgets')}  ({len(tab['widgets'])})", f"{tr('rename')}: {tab['label']}",
                   tr("icon"), f"{tr('action')}: {describe_action(tab['action'], tab.get('actionlabel', ''))}", tr("up"), tr("down")]
        if not start:
            actions.append(tr("make_start"))
        actions.append(tr("remove_tab"))
        choice = select(tab["label"], actions)
        if choice < 0:
            return
        index = menu.tabs.index(tab)
        name = actions[choice]
        if choice == 0:
            edit_widgets(menu, tab)
            continue
        if choice == 1:
            tab["label"] = keyboard(tr("rename"), tab["label"]) or tab["label"]
        elif choice == 2:
            tab["icon"] = pick_icon(tab["icon"])
        elif choice == 3:
            action, suggest = pick_action()
            if not action:
                continue
            tab["action"] = action
            tab["actionlabel"] = suggest[0] if suggest else ""
        elif choice == 4 and index > 0:
            menu.tabs[index - 1], menu.tabs[index] = tab, menu.tabs[index - 1]
        elif choice == 5 and index < len(menu.tabs) - 1:
            menu.tabs[index + 1], menu.tabs[index] = tab, menu.tabs[index + 1]
        elif name == tr("make_start"):
            menu.start = tab
        elif name == tr("remove_tab"):
            if xbmcgui.Dialog().yesno(HEADING, tr("remove_tab_q", tab["label"])):
                menu.tabs.remove(tab)
                menu.save()
                return
            continue
        else:
            continue
        menu.save()


def add_tab(menu):
    if len(menu.tabs) >= NTABS:
        xbmcgui.Dialog().ok(HEADING, tr("max_tabs", NTABS))
        return
    action, suggest = pick_action()
    if not action:
        return
    label, icon = suggest or (tr("new_tab"), "icons/star.png")
    label = keyboard(tr("rename"), label) or label
    tab = {"label": label, "icon": icon, "action": action, "actionlabel": suggest[0] if suggest else "",
           "widgets": [], "slot": 0}
    menu.tabs.append(tab)
    menu.save()
    edit_tab(menu, tab)


def editor():
    menu = Menu()
    if not menu.tabs:
        menu.set_defaults()
        menu.save()
    while True:
        start = menu.start_tab()
        labels, label2s, icons = [], [], []
        for tab in menu.tabs:
            labels.append(tab["label"] + (f"  ·  {tr('start')}" if tab is start else ""))
            n = len(tab["widgets"])
            label2s.append(f"{describe_action(tab['action'], tab.get('actionlabel', ''))}  ·  " + (tr("widgets_n", n) if n else tr("no_widgets")))
            icons.append(tab["icon"])
        labels += [tr("add_tab"), tr("reset")]
        label2s += ["", ""]
        icons += ["icons/plus.png", "icons/refresh.png"]
        choice = select(tr("menu"), labels, True, icons, label2s)
        if choice < 0:
            break
        if choice < len(menu.tabs):
            edit_tab(menu, menu.tabs[choice])
        elif choice == len(menu.tabs):
            add_tab(menu)
        elif xbmcgui.Dialog().yesno(HEADING, tr("reset_q")):
            menu.set_defaults()
            menu.save()
    notify(tr("saved"))


def add_here():
    """Context menu "Add to Home as widget" (from the video add-on): the folder under the cursor becomes a widget on a tab you pick.
    The folder comes in Window(home).Property(lucent.addw.path / .label)."""
    home = xbmcgui.Window(10000)
    path, label = home.getProperty("lucent.addw.path"), clean(home.getProperty("lucent.addw.label"))
    home.clearProperty("lucent.addw.path")
    home.clearProperty("lucent.addw.label")
    if not path:
        return
    menu = Menu()
    if not menu.tabs:
        menu.set_defaults()
    tabs = [t for t in menu.tabs if t["action"] == SHOW_WIDGETS or t["widgets"]]
    labels = [t["label"] for t in tabs] + [tr("add_tab").lstrip("+ ").strip()]
    label2s = [tr("widgets_n", len(t["widgets"])) if t["widgets"] else tr(G("no widgets yet", "nog geen widgets")) for t in tabs] + [""]
    icons = [t["icon"] for t in tabs] + ["icons/plus.png"]
    choice = select(tr(G("Add \"{0}\" to which tab?", "\"{0}\" toevoegen aan welke tab?"), label or path), labels, True, icons, label2s)
    if choice < 0:
        return
    if choice == len(tabs):
        if len(menu.tabs) >= NTABS:
            xbmcgui.Dialog().ok(HEADING, tr("max_tabs", NTABS))
            return
        name = keyboard(tr("rename"), label or tr("new_tab")) or label or tr("new_tab")
        tab = {"label": name, "icon": "icons/star.png", "action": SHOW_WIDGETS, "actionlabel": "", "widgets": [], "slot": 0}
        start = menu.start_tab()
        at = menu.tabs.index(start) + 1 if start in menu.tabs else len(menu.tabs)
        menu.tabs.insert(at, tab)                    # right after the start tab
        menu.start = start
    else:
        tab = tabs[choice]
    if len(tab["widgets"]) >= NWIDGETS:
        xbmcgui.Dialog().ok(HEADING, tr("max_widgets", NWIDGETS))
        return
    name = keyboard(tr("rename"), label or path) or label or path
    style = select(tr("style"), [tr("poster"), tr("land")])
    tab["widgets"].append({"label": name, "path": path, "style": "land" if style == 1 else "poster"})
    menu.save()
    notify(tr(G("Widget added to {0}", "Widget toegevoegd aan {0}"), tab["label"]))


def init():
    menu = Menu()
    if not menu.tabs:
        menu.set_defaults()
        put("nuvio.agenda.tab", "1")      # the default menu already has the Calendar tab (the plain menu wants none)
    menu.save()
    # select the start tab now that it is known (Home asked for this before the menu existed)
    pos = get("nuvio.homepos")
    if pos and xbmc.getCondVisibility("Window.IsActive(home)"):
        xbmc.executebuiltin(f"Control.SetFocus(9000,{pos})", True)
        if xbmc.getCondVisibility("Control.IsVisible(9991)"):        # only when the start tab has rows already
            xbmc.executebuiltin("SetFocus(9100)")


def addons_once():
    """One time for existing menus: give an Add-ons item without rows its add-on rows."""
    if get("lucent.addonw4"):
        return
    put("lucent.addonw4", "1")
    menu = Menu()
    changed = False
    for tab in menu.tabs:
        is_addons = "AddonBrowser" in tab["action"] or "addons" in tab.get("icon", "").lower() \
            or tab["label"].strip().lower() in ("add-ons", "addons")
        mine = all(w["path"].startswith(("addons://", "favourites://")) for w in tab["widgets"])
        if is_addons and mine:
            tab["widgets"] = addon_widgets()
            changed = True
    if changed:
        menu.save()
        xbmc.executebuiltin("Container.Refresh")


if __name__ == "__main__":
    arg = sys.argv[1] if len(sys.argv) > 1 else ""
    if arg == "init":
        init()
    elif arg == "addons":
        addons_once()
    elif arg == "lv":
        lv_convert()
    elif arg == "addwidget":
        add_here()
    elif arg == "reset":
        if xbmcgui.Dialog().yesno(HEADING, tr("reset_q")):
            m = Menu()
            m.set_defaults()
            m.save()
    else:
        editor()
