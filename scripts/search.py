# -*- coding: utf-8 -*-
"""Lucent 3.0.1: the search screen (Lucent_Search.xml), GitHub #34.

Search in a video add-on of your choice (the button at the top goes to the next installed one) or in the Kodi
library. What you search shows as rows: movies and shows from that add-on, actors (TMDb, OK opens their page) and
what you have in the Kodi library. The last searches stay in a list, OK searches them again.

    RunScript(special://skin/scripts/search.py)            the Search tab of the menu
    RunScript(special://skin/scripts/search.py,provider)   Skin settings > Search: the add-on it starts with
    RunScript(special://skin/scripts/search.py,tab)        Skin settings > Search: what the Search tab opens
"""
import json
import sys
import threading
import time
import urllib.parse

import xbmc
import xbmcaddon
import xbmcgui
import xbmcvfs

NL = xbmc.getLanguage(xbmc.ISO_639_1) == "nl"
HOME = xbmcgui.Window(10000)
HISTORY = "special://profile/addon_data/skin.lucent/search_history.json"
CLOSE = (9, 10, 92, 216, 247, 257, 275, 61467, 61448)
LIBRARY = "library"
LV = "plugin.video.lucent"
ROWS = (301, 302, 303, 304, 305)
KEYS = ("movie", "tvshow", "people", "libmovie", "libtvshow")      # the rows, in the same order

# the add-ons the screen knows, in the order of the button: (id, movies, shows); {q} = the search term, url-encoded
PROVIDERS = [
    (LV, "plugin://plugin.video.lucent/?action=search&type=movie&query={q}",
     "plugin://plugin.video.lucent/?action=search&type=tvshow&query={q}"),
    ("plugin.video.fen", "plugin://plugin.video.fen/?mode=build_movie_list&action=tmdb_movies_search&query={q}",
     "plugin://plugin.video.fen/?mode=build_tvshow_list&action=tmdb_tv_search&query={q}"),
    ("plugin.video.fenlight", "plugin://plugin.video.fenlight/?mode=build_movie_list&action=tmdb_movies_search&query={q}",
     "plugin://plugin.video.fenlight/?mode=build_tvshow_list&action=tmdb_tv_search&query={q}"),
    ("plugin.video.redlight", "plugin://plugin.video.redlight/?mode=build_movie_list&action=tmdb_movies_search&key_id={q}",
     "plugin://plugin.video.redlight/?mode=build_tvshow_list&action=tmdb_tv_search&key_id={q}"),    # 3.0.3 (#34)
    ("plugin.video.pov", "plugin://plugin.video.pov/?mode=build_movie_list&action=tmdb_movies_search&query={q}",
     "plugin://plugin.video.pov/?mode=build_tvshow_list&action=tmdb_tv_search&query={q}"),
    ("plugin.video.umbrella", "plugin://plugin.video.umbrella/?action=movieSearchterm&name={q}",
     "plugin://plugin.video.umbrella/?action=tvSearchterm&name={q}"),
    ("plugin.video.seren", "plugin://plugin.video.seren/?action=moviesSearchResults&actionArgs={q}",
     "plugin://plugin.video.seren/?action=showsSearchResults&actionArgs={q}"),
]

T = {
    "heading": ("Search", "Zoeken"),
    "sub": ("Search a movie, show or actor", "Zoek een film, serie of acteur"),
    "in": ("Search in: {0}", "Zoeken in: {0}"),
    "hint": ("OK = next add-on", "OK = volgende add-on"),
    "new": ("New search", "Nieuwe zoekopdracht"),
    "recent": ("Recent searches", "Laatst gezocht"),
    "empty": ("Nothing searched yet. Choose New search.", "Nog niets gezocht. Kies Nieuwe zoekopdracht."),
    "results": ("Results for “{0}”", "Resultaten voor “{0}”"),
    "results_sub": ("In {0}  ·  Back = recent searches", "In {0}  ·  Terug = laatst gezocht"),
    "ask": ("Search", "Zoeken"),
    "movies": ("Movies", "Films"),
    "shows": ("Shows", "Series"),
    "people": ("Actors", "Acteurs"),
    "libmovies": ("Movies in your Kodi library", "Films in je Kodi-bibliotheek"),
    "libshows": ("Shows in your Kodi library", "Series in je Kodi-bibliotheek"),
    "busy": ("Searching…", "Bezig met zoeken…"),
    "none": ("Nothing found", "Niets gevonden"),
    "no_key": ("Needs a TMDb key (Skin settings > Integrations)", "Heeft een TMDb-sleutel nodig (Skin-instellingen > Integraties)"),
    "none_for": ("Nothing found for \u201c{0}\u201d", "Niets gevonden voor \u201c{0}\u201d"),
    "nothing": ("Nothing to search: switch on Movies, Shows or Actors in Skin settings > Search.",
                "Niets om te zoeken: zet Films, Series of Acteurs aan in Skin-instellingen > Zoeken."),
    "library": ("Kodi library", "Kodi-bibliotheek"),
    "clear": ("Clear all recent searches?", "Alle laatste zoekopdrachten wissen?"),
    "pick": ("Search in by default", "Standaard zoeken in"),
    "tab": ("Search tab opens", "Zoek-tab opent"),
    "tab_own": ("Lucent search screen", "Zoekscherm van Lucent"),
    "tab_lv": ("Search menu of Lucent Video", "Zoekmenu van Lucent Video"),
}


def tr(key, *args):
    text = T[key][1 if NL else 0]
    return text.format(*args) if args else text


def log(text):
    xbmc.log(f"[skin.lucent] search: {text}", xbmc.LOGINFO)


def installed():
    """The add-ons of PROVIDERS that are installed, then the Kodi library: [(id, name)]."""
    found = []
    for addon_id, _m, _s in PROVIDERS:
        if xbmc.getCondVisibility(f"System.HasAddon({addon_id})"):
            try:
                name = xbmcaddon.Addon(addon_id).getAddonInfo("name")
            except Exception:  # noqa: BLE001 - disabled or broken
                continue
            found.append((addon_id, name))
    found.append((LIBRARY, tr("library")))
    return found


def current(providers):
    chosen = xbmc.getInfoLabel("Skin.String(lucent.search.provider)")
    ids = [p[0] for p in providers]
    return chosen if chosen in ids else ids[0]


def set_provider(addon_id, providers):
    xbmc.executebuiltin(f"Skin.SetString(lucent.search.provider,{addon_id})")
    name = dict(providers).get(addon_id, "")
    xbmc.executebuiltin(f"Skin.SetString(lucent.search.provider.label,{name})")


def load_history():
    try:
        with xbmcvfs.File(HISTORY) as fh:
            data = json.loads(fh.read() or "[]")
        return [h for h in data if isinstance(h, dict) and h.get("q")]
    except (ValueError, OSError):
        return []


def save_history(history):
    xbmcvfs.mkdirs("special://profile/addon_data/skin.lucent/")
    with xbmcvfs.File(HISTORY, "w") as fh:
        fh.write(json.dumps(history[:20]))


def library_url(kind, term):
    rules = {"rules": {"and": [{"field": "title", "operator": "contains", "value": [term]}]},
             "type": "movies" if kind == "movie" else "tvshows"}
    base = "videodb://movies/titles/" if kind == "movie" else "videodb://tvshows/titles/"
    return base + "?xsp=" + urllib.parse.quote(json.dumps(rules))


def people(term):
    """Actors and actresses with this name on TMDb (the key of Lucent, else of the video add-on): [ListItem]."""
    import info
    if not info.tmdb_key():
        return None
    try:
        found = info.tmdb("search/person", query=term).get("results") or []
    except Exception as error:  # noqa: BLE001
        log(f"people: {type(error).__name__}")
        return []
    items = []
    for person in [p for p in found if p.get("id")][:20]:
        li = xbmcgui.ListItem(person.get("name", ""), offscreen=True)
        photo = person.get("profile_path")
        if photo:
            li.setArt({"icon": f"https://image.tmdb.org/t/p/w342{photo}", "thumb": f"https://image.tmdb.org/t/p/w342{photo}"})
        li.setProperty("person", str(person["id"]))
        items.append(li)
    return items


def open_action(cid):
    """What OK on the selected title of result row cid does, as a Kodi command."""
    info = lambda name: xbmc.getInfoLabel(f"Container({cid}).ListItem.{name}")  # noqa: E731
    path = info("FolderPath") or info("FileNameAndPath")
    if not path:
        return ""
    if xbmc.getCondVisibility(f"Container({cid}).ListItem.IsFolder"):
        return f'ActivateWindow(Videos,"{path}",return)'
    tmdb = info("UniqueID(tmdb)")
    if info("DBType") == "movie" and tmdb.isdigit() and xbmc.getCondVisibility("Skin.HasSetting(nuvio.ok.movie.page)"):
        HOME.setProperty("nuvio.open.tmdb", tmdb)
        HOME.setProperty("nuvio.open.type", "movie")
        HOME.clearProperty("nuvio.open.trakt")
        return "RunScript(special://skin/scripts/info.py,open,path)"
    return f'PlayMedia("{path}")'


class Search(xbmcgui.WindowXMLDialog):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.providers = installed()
        self.provider = current(self.providers)
        self.history = load_history()
        self.term = ""
        self.gen = 0                            # one number per search: an older watcher stops
        self.after = None                       # what to do once the screen is closed (open a person page)
        self.start = None

    def onInit(self):
        for key in ("heading", "sub", "hint", "new", "recent", "empty", "busy", "none", "nothing"):
            self.setProperty(key, tr(key))
        self.show_provider()
        self.fill_history()
        if self.start:
            term, self.start = self.start, None
            self.search(term)
        else:
            self.setProperty("mode", "history")
            self.setFocusId(200 if self.history else 102)

    def show_provider(self):
        names = dict(self.providers)
        self.setProperty("provider", tr("in", names.get(self.provider, "")))
        ids = [p[0] for p in self.providers]
        at = ids.index(self.provider) if self.provider in ids else 0
        self.setProperty("dots", "  ".join("●" if n == at else "○" for n in range(len(ids))) if len(ids) > 1 else "")

    def fill_history(self):
        names = dict(self.providers)
        lst = self.getControl(200)
        lst.reset()
        items = []
        for entry in self.history:
            li = xbmcgui.ListItem(entry["q"], names.get(entry.get("p"), entry.get("n", "")), offscreen=True)
            items.append(li)
        lst.addItems(items)

    def next_provider(self):
        ids = [p[0] for p in self.providers]
        at = ids.index(self.provider) if self.provider in ids else -1
        self.provider = ids[(at + 1) % len(ids)]
        set_provider(self.provider, self.providers)
        self.show_provider()
        if self.term and self.getProperty("mode") == "results":
            self.search(self.term)

    def ask(self):
        term = xbmcgui.Dialog().input(tr("ask"), defaultt=self.term)
        if term and term.strip():
            self.search(term.strip())

    def search(self, term):
        self.term = term
        names = dict(self.providers)
        entry = {"q": term, "p": self.provider, "n": names.get(self.provider, ""), "t": int(time.time())}
        self.history = [entry] + [h for h in self.history if (h.get("q", "").lower(), h.get("p")) != (term.lower(), self.provider)]
        save_history(self.history)
        self.fill_history()
        HOME.setProperty("lucent.search.last", json.dumps([term, self.provider]))
        self.setProperty("heading", tr("results", term))
        self.setProperty("sub", tr("results_sub", names.get(self.provider, "")))
        q = urllib.parse.quote_plus(term)
        on = lambda name: not xbmc.getCondVisibility(f"Skin.HasSetting(lucent.search.no{name})")  # noqa: E731
        urls = {"movie": "", "tvshow": "", "libmovie": "", "libtvshow": ""}
        if self.provider == LIBRARY:
            if on("movies"):
                urls["movie"] = library_url("movie", term)
            if on("shows"):
                urls["tvshow"] = library_url("tvshow", term)
        else:
            row = next((p for p in PROVIDERS if p[0] == self.provider), None)
            if row and on("movies"):
                urls["movie"] = row[1].format(q=q)
            if row and on("shows"):
                urls["tvshow"] = row[2].format(q=q)
            if on("lib"):
                urls["libmovie"] = library_url("movie", term) if on("movies") else ""
                urls["libtvshow"] = library_url("tvshow", term) if on("shows") else ""
        titles = {"movie": tr("movies"), "tvshow": tr("shows"), "people": tr("people"),
                  "libmovie": tr("libmovies"), "libtvshow": tr("libshows")}
        for key, title in titles.items():
            self.setProperty(f"title.{key}", title)
        # clear first, so a row whose address stays the same still loads again
        self.gen += 1
        for key in KEYS:
            self.setProperty(f"url.{key}", "")
            self.setProperty(f"empty.{key}", "")
        self.setProperty("allempty", "")
        self.setProperty("mode", "results")
        xbmc.sleep(50)
        for key, url in urls.items():
            self.setProperty(f"url.{key}", url)
        log(f"'{term}' in {self.provider}")
        self.getControl(303).reset()
        if xbmc.getCondVisibility("Skin.HasSetting(lucent.search.people)"):
            self.setProperty("url.people", "1")
            self.setProperty("wait.people", "1")
            found = people(term)
            self.setProperty("wait.people", "")
            if found is None:
                self.setProperty("none.people", tr("no_key"))
            else:
                self.setProperty("none.people", tr("none"))
                self.getControl(303).addItems(found)
                if not found:
                    self.setProperty("empty.people", "1")
        if not any(self.getProperty(f"url.{key}") for key in KEYS):
            self.setProperty("nothing", tr("nothing"))
            self.setProperty("allempty", "1")
            self.setFocusId(102)
            return
        threading.Thread(target=self.watch, args=(self.gen, term), daemon=True).start()

    def watch(self, gen, term):
        """While the rows load: hide the ones that stay empty, put the focus on the top row with something in it."""
        started = time.time()
        quiet = {}
        focused = False
        while time.time() - started < 30 and gen == self.gen and not xbmc.Monitor().abortRequested():
            states = []                                     # per row: "items", "empty", "loading" or "off"
            for key, cid in zip(KEYS, ROWS):
                if not self.getProperty(f"url.{key}"):
                    states.append("off")
                elif self.getProperty(f"empty.{key}"):
                    states.append("empty")
                elif xbmc.getCondVisibility(f"Integer.IsGreater(Container({cid}).NumItems,0)"):
                    states.append("items")
                elif xbmc.getCondVisibility(f"Container({cid}).IsUpdating") or self.getProperty(f"wait.{key}") \
                        or time.time() - started < 1.5:
                    quiet[key] = 0
                    states.append("loading")
                else:                                       # not loading and nothing in it, twice in a row: empty
                    quiet[key] = quiet.get(key, 0) + 1
                    if quiet[key] >= 2 and key != "people":
                        self.setProperty(f"empty.{key}", "1")
                        states.append("empty")
                    elif key == "people":
                        states.append("message")            # the people row shows its own message (no key)
                    else:
                        states.append("loading")
            if not focused:
                for state, cid in zip(states, ROWS):
                    if state == "loading":
                        break
                    if state == "items":
                        if self.getFocusId() in (0, 101, 102, 103, 9001, 9002, 9100) or self.getFocusId() in ROWS:
                            self.setFocusId(cid)
                        focused = True
                        break
            if "loading" not in states:
                if "items" not in states:
                    self.setProperty("nothing", tr("none_for", term))
                    self.setProperty("allempty", "1")
                    self.setFocusId(102)
                return
            xbmc.sleep(250)

    def back_to_history(self):
        self.term = ""
        self.gen += 1
        self.setProperty("allempty", "")
        HOME.clearProperty("lucent.search.last")
        for key in ("movie", "tvshow", "people", "libmovie", "libtvshow"):
            self.setProperty(f"url.{key}", "")
        self.setProperty("heading", tr("heading"))
        self.setProperty("sub", tr("sub"))
        self.setProperty("mode", "history")
        self.setFocusId(200 if self.history else 102)

    def onClick(self, control_id):
        if control_id == 101:
            self.next_provider()
        elif control_id == 102:
            self.ask()
        elif control_id == 103:
            if xbmcgui.Dialog().yesno(tr("heading"), tr("clear")):
                self.history = []
                save_history([])
                self.fill_history()
                self.setFocusId(102)
        elif control_id == 200:
            pos = self.getControl(200).getSelectedPosition()
            if 0 <= pos < len(self.history):
                entry = self.history[pos]
                if entry.get("p") in dict(self.providers) and entry.get("p") != self.provider:
                    self.provider = entry["p"]
                    set_provider(self.provider, self.providers)
                    self.show_provider()
                self.search(entry["q"])
        elif control_id == 303:
            item = self.getControl(303).getSelectedItem()
            if item and item.getProperty("person"):
                self.after = f"RunScript(special://skin/scripts/info.py,person,{item.getProperty('person')})"
                self.close()

    def rows(self):
        """The result rows you can go to: shown and with something in them."""
        return [cid for cid in ROWS if xbmc.getCondVisibility(f"Control.IsVisible({cid}) + Integer.IsGreater(Container({cid}).NumItems,0)")]

    def onAction(self, action):
        focus = self.getFocusId()
        if action.getId() in (3, 4) and focus in ROWS:         # Up / Down between the result rows
            rows = self.rows()
            at = rows.index(focus) if focus in rows else 0
            if action.getId() == 4 and at + 1 < len(rows):
                self.setFocusId(rows[at + 1])
            elif action.getId() == 3:
                self.setFocusId(rows[at - 1] if at > 0 else 101)
            return
        if action.getId() in (7, 100) and focus in (301, 302, 304, 305):
            # OK on a title: this screen closes and opens it (a folder in Videos, a film plays or opens its page);
            # coming back to Search shows the same results
            self.after = open_action(focus)
            log(f"open from row {focus}: {self.after}")
            if self.after:
                self.close()
            return
        if action.getId() == 4 and focus in (101, 102, 103) and self.getProperty("mode") == "results":
            rows = self.rows()
            if rows:
                self.setFocusId(rows[0])
            return
        if action.getId() in CLOSE:
            if action.getId() in (10, 92) and self.getProperty("mode") == "results":
                self.back_to_history()
                return
            HOME.clearProperty("lucent.search.last")
            self.close()


def choose_provider():
    providers = installed()
    names = [p[1] for p in providers]
    ids = [p[0] for p in providers]
    pick = xbmcgui.Dialog().select(tr("pick"), names, preselect=ids.index(current(providers)))
    if pick >= 0:
        set_provider(ids[pick], providers)


def choose_tab():
    options = [("", tr("tab_own"))]
    if xbmc.getCondVisibility(f"System.HasAddon({LV})"):
        options.append(("lv", tr("tab_lv")))
    now = xbmc.getInfoLabel("Skin.String(lucent.search.tab)")
    keys = [o[0] for o in options]
    pick = xbmcgui.Dialog().select(tr("tab"), [o[1] for o in options], preselect=keys.index(now) if now in keys else 0)
    if pick < 0:
        return
    xbmc.executebuiltin(f"Skin.SetString(lucent.search.tab,{options[pick][0]})" if options[pick][0]
                        else "Skin.Reset(lucent.search.tab)")


def main():
    action = sys.argv[1] if len(sys.argv) > 1 else ""
    if action == "provider":
        return choose_provider()
    if action == "tab":
        return choose_tab()
    if xbmc.getInfoLabel("Skin.String(lucent.search.tab)") == "lv" and xbmc.getCondVisibility(f"System.HasAddon({LV})"):
        xbmc.executebuiltin(f"ActivateWindow(Videos,plugin://{LV}/?action=searchmenu,return)")
        return None
    win = Search("Lucent_Search.xml", xbmcaddon.Addon("skin.lucent").getAddonInfo("path"), "Default", "1080i")
    try:
        last = json.loads(HOME.getProperty("lucent.search.last") or "null")
    except ValueError:
        last = None
    if last and len(last) == 2:
        if last[1] in dict(win.providers):
            win.provider = last[1]
        win.start = last[0]
    win.doModal()
    after = win.after
    del win
    if after:
        xbmc.executebuiltin(after)
    return None


if __name__ == "__main__":
    main()
