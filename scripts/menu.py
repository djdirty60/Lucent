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
import xbmcgui

VERSION = "1"
NTABS = 12
NWIDGETS = 10
SEREN = "plugin://plugin.video.seren/"
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
    "poster": ("Posters", "Posters"),
    "land": ("Landscape", "Liggend"),
    "remove_widget": ("Remove this widget", "Deze widget verwijderen"),
    "src_seren": ("Seren", "Seren"),
    "src_trakt": ("Trakt lists (liked or your own)", "Trakt-lijsten (leuk gevonden of eigen)"),
    "src_library": ("Kodi library", "Kodi-bibliotheek"),
    "src_browse": ("Browse an add-on…", "Bladeren in een add-on…"),
    "src_type": ("Type a path…", "Pad zelf typen…"),
    "use_folder": ("✔ Use this folder: {0}", "✔ Deze map gebruiken: {0}"),
    "empty_folder": ("This folder is empty or could not be opened.", "Deze map is leeg of kon niet worden geopend."),
    "no_seren": ("Seren is not installed.", "Seren is niet geïnstalleerd."),
    "no_lists": ("No Trakt lists found. Are you logged in to Trakt in Seren?",
                 "Geen Trakt-lijsten gevonden. Ben je in Seren ingelogd bij Trakt?"),
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
    "k_seren_search": ("Seren · Search", "Seren · Zoeken"),
    "k_seren_movies": ("Seren · Movies", "Seren · Films"),
    "k_seren_shows": ("Seren · TV shows", "Seren · Series"),
    "k_seren_mymovies": ("Seren · My movies", "Seren · Mijn films"),
    "k_seren_myshows": ("Seren · My shows", "Seren · Mijn series"),
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


def seren(query):
    return f"{SEREN}?{query}"


def videos(path):
    return f"ActivateWindow(Videos,{path},return)"


def xsp(content, rules=None, order="title"):
    """A smart-playlist filter for a library path (videodb://…?xsp=…)."""
    data = {"type": content, "order": {"direction": "descending" if order in ("rating", "dateadded", "lastplayed") else "ascending",
                                       "method": order}}
    if rules:
        data["rules"] = {"and": [{"field": f, "operator": op, "value": [v] if v else []} for f, op, v in rules]}
    return urllib.parse.quote(json.dumps(data, separators=(",", ":")))


WIDGETS_SEREN = [
    ("w_nextup", seren("action=showsNextUp"), "land"),
    ("w_ondeck", seren("action=onDeckMovies"), "land"),
    ("w_trend_m", seren("action=genericEndpoint&mediatype=movies&endpoint=trending"), "poster"),
    ("w_trend_s", seren("action=genericEndpoint&mediatype=shows&endpoint=trending"), "poster"),
    ("w_pop_m", seren("action=genericEndpoint&mediatype=movies&endpoint=popular"), "poster"),
    ("w_pop_s", seren("action=genericEndpoint&mediatype=shows&endpoint=popular"), "poster"),
    ("w_ant_m", seren("action=genericEndpoint&mediatype=movies&endpoint=anticipated"), "poster"),
    ("w_ant_s", seren("action=genericEndpoint&mediatype=shows&endpoint=anticipated"), "poster"),
    ("w_box", seren("action=genericEndpoint&mediatype=movies&endpoint=boxoffice"), "poster"),
    ("w_new_s", seren("action=showsNew"), "poster"),
    ("w_wl_m", seren("action=moviesMyWatchlist"), "poster"),
    ("w_wl_s", seren("action=showsMyWatchlist"), "poster"),
    ("w_upcoming", seren("action=myUpcomingEpisodes"), "land"),
    (("Trending movies (recent)", "Trending films (recent)"), seren("action=movieTrendingRecent"), "poster"),
    (("Popular movies (recent)", "Populaire films (recent)"), seren("action=moviePopularRecent"), "poster"),
    (("Trending shows (recent)", "Trending series (recent)"), seren("action=showsTrendingRecent"), "poster"),
    (("Popular shows (recent)", "Populaire series (recent)"), seren("action=showsPopularRecent"), "poster"),
    (("Recommended movies", "Aanbevolen films"), seren("action=moviesRecommended"), "poster"),
    (("Recommended shows", "Aanbevolen series"), seren("action=showsRecommended"), "poster"),
    (("Most played movies", "Meest afgespeelde films"), seren("action=genericEndpoint&mediatype=movies&endpoint=played"), "poster"),
    (("Most watched movies", "Meest bekeken films"), seren("action=genericEndpoint&mediatype=movies&endpoint=watched"), "poster"),
    (("Most collected movies", "Meest verzamelde films"), seren("action=genericEndpoint&mediatype=movies&endpoint=collected"), "poster"),
    (("Most played shows", "Meest afgespeelde series"), seren("action=genericEndpoint&mediatype=shows&endpoint=played"), "poster"),
    (("Most watched shows", "Meest bekeken series"), seren("action=genericEndpoint&mediatype=shows&endpoint=watched"), "poster"),
    (("Updated movies", "Bijgewerkte films"), seren("action=moviesUpdated"), "poster"),
    (("Updated shows", "Bijgewerkte series"), seren("action=showsUpdated"), "poster"),
    (("My movies (collection)", "Mijn films (collectie)"), seren("action=moviesMyCollection"), "poster"),
    (("My shows (collection)", "Mijn series (collectie)"), seren("action=showsMyCollection"), "poster"),
    (("Recently watched shows", "Recent bekeken series"), seren("action=showsRecentlyWatched"), "poster"),
    (("My recent episodes", "Mijn recente afleveringen"), seren("action=showsMyRecentEpisodes"), "land"),
    (("Shows in progress", "Series die je kijkt"), seren("action=showsMyProgress"), "poster"),
    (("Watched movies", "Bekeken films"), seren("action=myWatchedMovies"), "poster"),
]
WIDGETS_LIBRARY = [
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
WIDGETS_OTHER = [
    (("Favourites", "Favorieten"), "favourites://", "land"),
    (("Video add-ons", "Video-add-ons"), "addons://sources/video/", "poster"),
    (("Program add-ons", "Programma-add-ons"), "addons://sources/executable/", "poster"),
    (("Music add-ons", "Muziek-add-ons"), "addons://sources/audio/", "poster"),
    (("Recently updated add-ons", "Recent bijgewerkte add-ons"), "addons://recently_updated/", "poster"),
]
G = lambda en, nl: (en, nl)  # noqa: E731 - inline translation
ACTION_GROUPS = [
    (G("Seren", "Seren"), "icons/play.png", [
        ("k_seren_search", "icons/search.png", videos(seren("action=searchMenu"))),
        ("k_seren_movies", "icons/movies.png", videos(seren("action=moviesHome"))),
        ("k_seren_shows", "icons/tv.png", videos(seren("action=showsHome"))),
        ("k_seren_mymovies", "icons/movies.png", videos(seren("action=myMovies"))),
        ("k_seren_myshows", "icons/tv.png", videos(seren("action=myShows"))),
        (G("Seren · Trakt lists", "Seren · Trakt-lijsten"), "icons/trakt.png", videos(seren("action=myTraktLists&mediatype=movies"))),
        (G("Seren · Tools", "Seren · Gereedschap"), "icons/settings.png", videos(seren("action=toolsMenu"))),
        (G("Seren · Settings", "Seren · Instellingen"), "icons/settings.png", "Addon.OpenSettings(plugin.video.seren)"),
    ]),
    (G("Video library", "Videobibliotheek"), "icons/library.png", [
        ("k_library", "icons/library.png", videos("videodb://")),
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
    ]),
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


def default_tabs():
    """The menu of version 1.0, plus the rows and Trakt lists the user had chosen there."""
    home = []
    old_rows = [("w_nextup", 8001), ("w_ondeck", 8002), ("w_trend_m", 8003), ("w_trend_s", 8004)]
    seren_by_key = {k: (p, s) for k, p, s in WIDGETS_SEREN}
    lib_by_key = {k: (p, s) for k, p, s in WIDGETS_LIBRARY}
    for key, rid in old_rows:
        if not xbmc.getCondVisibility(f"Skin.HasSetting(nuvio.hide.{rid})"):
            home.append(widget(key, *seren_by_key[key]))
    for key, rid in (("w_recent_m", 8005), ("w_recent_e", 8006)):
        if not xbmc.getCondVisibility(f"Skin.HasSetting(nuvio.hide.{rid})"):
            home.append(widget(key, *lib_by_key[key]))
    for n in range(1, 7):
        path, label = get(f"nuvio.list{n}.path"), get(f"nuvio.list{n}.label")
        if path and len(home) < NWIDGETS:
            home.append({"label": label or tr("src_trakt"), "path": path, "style": "poster"})

    movies = [widget(k, *seren_by_key[k]) for k in ("w_ondeck", "w_trend_m", "w_pop_m", "w_ant_m", "w_box")]
    shows = [widget(k, *seren_by_key[k]) for k in ("w_nextup", "w_trend_s", "w_pop_s", "w_new_s", "w_upcoming")]
    library = [widget(k, *lib_by_key[k]) for k in ("w_recent_m", "w_recent_e", "w_inprog_s")]

    def tab(key, icon, action, widgets=None):
        return {"label": tr(key), "icon": f"icons/{icon}.png", "action": action, "widgets": widgets or []}

    return [
        tab("t_search", "search", videos(seren("action=searchMenu"))),
        tab("t_home", "home", SHOW_WIDGETS, home),
        tab("t_movies", "movies", videos(seren("action=moviesHome")), movies),
        tab("t_shows", "tv", videos(seren("action=showsHome")), shows),
        tab("t_library", "library", videos("videodb://"), library),
        tab("t_addons", "addons", "ActivateWindow(AddonBrowser)"),
        tab("t_favourites", "favourites", "ActivateWindow(favouritesbrowser)"),
        tab("t_calendar", "calendar", "RunScript(special://skin/scripts/agenda.py)"),
        tab("t_settings", "settings", "ActivateWindow(Settings)"),
        tab("t_power", "power", "ActivateWindow(ShutdownMenu)"),
    ], 2


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
                                    "style": self._read(f"nuvio.tab{t}.w{w}.style") or "poster"})
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
        for name in [f"nuvio.home.w{w}.{p}" for w in range(1, NWIDGETS + 1) for p in ("label", "path", "style")] + ["nuvio.homepos"]:
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
                for p in ("label", "path", "style"):
                    wanted[f"nuvio.tab{t}.w{w}.{p}"] = wd[p] if wd else ""
        start = self.start_tab()
        start_index = self.tabs.index(start) if start else -1
        wanted["nuvio.hometab"] = str(start_index + 1) if start else ""
        wanted["nuvio.homepos"] = str(start_index) if start else ""
        for w in range(1, NWIDGETS + 1):
            wd = start["widgets"][w - 1] if start and w <= len(start["widgets"]) else None
            for p in ("label", "path", "style"):
                wanted[f"nuvio.home.w{w}.{p}"] = wd[p] if wd else ""
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


def video_addons():
    busy(True)
    result = jsonrpc("Addons.GetAddons", {"type": "xbmc.addon.video", "enabled": True,
                                          "properties": ["name", "thumbnail"]})
    busy(False)
    addons = sorted(result.get("addons", []) or [], key=lambda a: a.get("name", "").lower())
    return [(clean(a.get("name")), a.get("addonid"), a.get("thumbnail")) for a in addons]


def browse(heading):
    """Walk through add-on folders and return (label, path) of the chosen folder, or None."""
    addons = video_addons()
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


def trakt_lists():
    if not xbmc.getCondVisibility("System.HasAddon(plugin.video.seren)"):
        xbmcgui.Dialog().ok(HEADING, tr("no_seren"))
        return None
    options = []
    busy(True)
    for action in ("myLikedLists", "myTraktLists"):
        for mediatype, type_key in (("movies", "t_movies"), ("shows", "t_shows")):
            entries = jsonrpc("Files.GetDirectory", {"directory": seren(f"action={action}&mediatype={mediatype}"),
                                                     "media": "files", "properties": ["title"]}).get("files", []) or []
            for entry in entries:
                path, name = entry.get("file", ""), clean(entry.get("label") or entry.get("title"))
                if path and name and "action=traktList" in path and path not in [o[1] for o in options]:
                    options.append((name, path, tr(type_key)))
    busy(False)
    if not options:
        xbmcgui.Dialog().ok(HEADING, tr("no_lists"))
        return None
    choice = select(tr("src_trakt"), [o[0] for o in options], True, ["icons/trakt.png"] * len(options),
                    [o[2] for o in options])
    return (options[choice][0], options[choice][1]) if choice >= 0 else None


# ----------------------------------------------------------------------------- editors
def pick_widget():
    sources = [tr("src_seren"), tr("src_trakt"), tr("src_library"), tr("src_browse"), tr("src_type"),
               tr(G("Favourites and add-ons", "Favorieten en add-ons")), tr(G("A playlist…", "Een afspeellijst…"))]
    icons = ["icons/play.png", "icons/trakt.png", "icons/library.png", "icons/addons.png", "icons/list.png",
             "icons/favourites.png", "icons/list.png"]
    source = select(tr("add_widget"), sources, True, icons)
    style = "poster"
    if source == 0:
        choice = select(tr("src_seren"), [tr(k) for k, _p, _s in WIDGETS_SEREN])
        if choice < 0:
            return None
        key, path, style = WIDGETS_SEREN[choice]
        label = tr(key)
    elif source == 1:
        picked = trakt_lists()
        if not picked:
            return None
        label, path = picked
    elif source == 2:
        choice = select(tr("src_library"), [tr(k) for k, _p, _s in WIDGETS_LIBRARY])
        if choice < 0:
            return None
        key, path, style = WIDGETS_LIBRARY[choice]
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
        actions = [tr("rename"), f"{tr('style')}: {tr(wd['style'])}", tr("up"), tr("down"), tr("remove_widget")]
        act = select(wd["label"], actions)
        if act == 0:
            wd["label"] = keyboard(tr("rename"), wd["label"]) or wd["label"]
        elif act == 1:
            wd["style"] = "land" if wd["style"] == "poster" else "poster"
        elif act == 2 and choice > 0:
            widgets[choice - 1], widgets[choice] = widgets[choice], widgets[choice - 1]
        elif act == 3 and choice < len(widgets) - 1:
            widgets[choice + 1], widgets[choice] = widgets[choice], widgets[choice + 1]
        elif act == 4:
            widgets.pop(choice)
        else:
            continue
        menu.save()


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
        group = select(tr("act_window"), [tr(g) for g, _i, _e in ACTION_GROUPS], True, [i for _g, i, _e in ACTION_GROUPS])
        if group < 0:
            return None, None
        entries = ACTION_GROUPS[group][2]
        pick = select(tr(ACTION_GROUPS[group][0]), [tr(k) for k, _i, _a in entries], True, [i for _k, i, _a in entries])
        if pick >= 0:
            key, icon, action = entries[pick]
            return action, (tr(key).split(" · ")[-1], icon)
    if choice == 2:
        picked = browse(tr("act_folder"))
        if picked:
            return videos(picked[1]), (picked[0], "icons/folder.png")
    if choice == 3:
        addons = video_addons()
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
    labels = [name for name in ICONS]
    icons = [f"icons/{name}.png" for name in ICONS]
    choice = select(tr("icon"), labels, True, icons)
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


def init():
    menu = Menu()
    if not menu.tabs:
        menu.set_defaults()
        put("nuvio.agenda.tab", "1")      # the default menu already has the Calendar tab
    menu.save()
    # select the start tab now that it is known (Home asked for this before the menu existed)
    pos = get("nuvio.homepos")
    if pos and xbmc.getCondVisibility("Window.IsActive(home)"):
        xbmc.executebuiltin(f"Control.SetFocus(9000,{pos})", True)
        xbmc.executebuiltin("SetFocus(9100)")


if __name__ == "__main__":
    arg = sys.argv[1] if len(sys.argv) > 1 else ""
    if arg == "init":
        init()
    elif arg == "reset":
        if xbmcgui.Dialog().yesno(HEADING, tr("reset_q")):
            m = Menu()
            m.set_defaults()
            m.save()
    else:
        editor()
