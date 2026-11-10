"""Lucent: one streaming service in a pop-up - its six lists under each other (Lucent_Service.xml).

  RunScript(special://skin/scripts/service.py,<TMDb provider id>,<name>,<logo url>[,lucentvideo])

The lists come from Lucent Library (TMDb, saved copies), or from Lucent Video when the fourth argument is lucentvideo
(or Lucent Library is not installed). OK on a title opens its page, Back closes the pop-up.
"""
import sys
import threading
import urllib.parse

import xbmc
import xbmcaddon
import xbmcgui

HOME = xbmcgui.Window(10000)
NL = xbmc.getLanguage(xbmc.ISO_639_1) == "nl"
KINDS = [("newmovie", "New movies", "Nieuwe films"), ("newtv", "New series", "Nieuwe series"),
         ("popmovie", "Popular movies", "Populaire films"), ("poptv", "Popular series", "Populaire series"),
         ("topmovie", "Top rated movies", "Best beoordeelde films"), ("toptv", "Top rated series", "Best beoordeelde series")]
CLOSE = (9, 10, 92, 216, 247, 257, 275, 61467, 61448)


def t(en, nl):
    return nl if NL else en


class Service(xbmcgui.WindowXMLDialog):
    def setup(self, pid, name, logo, source=""):
        self.pid, self.name, self.logo = pid, name, logo
        self.lv = source == "lucentvideo" or not xbmc.getCondVisibility("System.HasAddon(script.lucent.library)")
        self.closed = False

    def onInit(self):
        self.setProperty("svc.name", self.name)
        self.setProperty("svc.logo", self.logo)
        self.setProperty("svc.sub", t("New, popular and top rated", "Nieuw, populair en best beoordeeld"))
        self.setProperty("svc.hint", t("Up: buttons and lists  ·  left / right: browse  ·  OK: open  ·  Back: close",
                                       "Omhoog: knoppen en lijsten  ·  links / rechts: bladeren  ·  OK: openen  ·  Terug: sluiten"))
        for key, en, nl in (("movies", "Films", "Films"), ("series", "Series", "Series"), ("new", "New", "Nieuw"),
                            ("pop", "Popular", "Populair"), ("top", "Top", "Top"), ("watch", "Watch", "Bekijken"),
                            ("trailer", "Trailer", "Trailer"), ("list", "My list", "Mijn lijst"),
                            ("empty", "Nothing here (yet) for this service.", "Hier staat (nog) niets voor deze dienst.")):
            self.setProperty(f"svc.t.{key}", t(en, nl))
        if not self.getProperty("svc.kind"):
            self.setProperty("svc.kind", "movie")
            self.setProperty("svc.cat", "new")
        self.show_list()
        self.setFocusId(801)
        if not getattr(self, "watching", False):
            self.watching = True
            threading.Thread(target=self.watch, daemon=True).start()

    def show_list(self):
        """The list for Films / Series and New / Popular / Top."""
        kind = "movie" if self.getProperty("svc.kind") == "movie" else "tv"
        cat = self.getProperty("svc.cat") or "new"
        key = f"{cat}{kind}"
        label = next((t(en, nl) for k, en, nl in KINDS if k == key), "")
        self.setProperty("svc.rowlabel", label)
        if self.lv:
            self.setProperty("row", f"plugin://plugin.video.lucent/?action=list&name=service_list&provider={self.pid}&kind={key}&widget=1")
        else:
            self.setProperty("row", f"plugin://script.lucent.library/?action=tmdbbrowse&list=prov_{self.pid}_{key}")
        threading.Thread(target=self.to_start, daemon=True).start()

    def to_start(self):
        """Another list: start at its first title (the list kept the place of the previous one)."""
        mon = xbmc.Monitor()
        for _ in range(40):
            if mon.waitForAbort(0.15) or self.closed:
                return
            if not xbmc.getCondVisibility("Container(801).IsUpdating") and xbmc.getCondVisibility("Integer.IsGreater(Container(801).NumItems,0)"):
                break
        try:
            self.getControl(801).selectItem(0)
        except Exception as error:  # noqa: BLE001
            xbmc.log(f"[skin.lucent] service.py: back to the first title: {error}", xbmc.LOGINFO)

    def onClick(self, cid):
        switch = {701: ("svc.kind", "movie"), 702: ("svc.kind", "tv"), 711: ("svc.cat", "new"), 712: ("svc.cat", "pop"), 713: ("svc.cat", "top")}
        if cid in switch:
            name, value = switch[cid]
            if self.getProperty(name) != value:
                self.setProperty(name, value)
                self.show_list()
            return
        if cid == 902:
            self.trailer()
            return
        if cid == 903:
            xbmc.executebuiltin("RunScript(special://skin/scripts/info.py,lists,801)")
            return
        if cid not in (801, 901):
            return
        base = "Container(801).ListItem."
        tmdb_id = xbmc.getInfoLabel(base + "Property(tmdb_id)") or xbmc.getInfoLabel(base + "UniqueID(tmdb)")
        if not tmdb_id:
            return
        kind = "tv" if xbmc.getInfoLabel(base + "DBType") == "tvshow" else "movie"
        HOME.setProperty("nuvio.open.tmdb", tmdb_id)
        HOME.setProperty("nuvio.open.type", kind)
        HOME.setProperty("nuvio.open.year", xbmc.getInfoLabel(base + "Year"))
        HOME.setProperty("nuvio.open.path", "")
        HOME.clearProperty("nuvio.open.trakt")
        xbmc.executebuiltin("RunScript(special://skin/scripts/info.py,open,path)")

    def trailer(self):
        """The title's trailer from TMDb, played through the YouTube add-on."""
        base = "Container(801).ListItem."
        tmdb_id = xbmc.getInfoLabel(base + "Property(tmdb_id)") or xbmc.getInfoLabel(base + "UniqueID(tmdb)")
        kind = "tv" if xbmc.getInfoLabel(base + "DBType") == "tvshow" else "movie"
        key = ""
        if tmdb_id.isdigit():
            try:
                import info
                lang = "nl" if NL else "en"
                videos = info.tmdb(f"{kind}/{tmdb_id}/videos", include_video_language=f"{lang},en,null").get("results") or []
                videos = [v for v in videos if v.get("site") == "YouTube" and v.get("key")]
                order = ["Trailer", "Teaser", "Clip"]
                videos.sort(key=lambda v: (order.index(v.get("type")) if v.get("type") in order else 99, not v.get("official")))
                key = videos[0]["key"] if videos else ""
            except Exception as error:  # noqa: BLE001
                xbmc.log(f"[skin.lucent] service.py trailer: {error}", xbmc.LOGINFO)
        if not key:
            xbmcgui.Dialog().notification(self.name or "Lucent", t("No trailer found", "Geen trailer gevonden"), xbmcgui.NOTIFICATION_INFO, 3000)
            return
        self.close()
        xbmc.executebuiltin(f"PlayMedia(plugin://plugin.video.youtube/play/?video_id={key})")

    def watch(self):
        """While the pop-up is open: when a title page opened from it is left with Play, the pop-up goes away.
        It sits above everything, so the seasons of a series opened behind it and it looked as if Play did nothing.
        (A title in the lists opens its page through Lucent Library, so this watches instead of hooking the click.)"""
        mon = xbmc.Monitor()
        page = False
        HOME.clearProperty("lucent.svc.folder")
        while not self.closed and not mon.abortRequested():
            folder = HOME.getProperty("lucent.svc.folder")
            if folder:                                  # a series was clicked: its seasons open (info.py seasons)
                HOME.clearProperty("lucent.svc.folder")
                self.close()
                mon.waitForAbort(0.3)
                xbmc.executebuiltin(f'ActivateWindow(Videos,"{folder}",return)')
                return
            if xbmc.getCondVisibility("Window.IsVisible(movieinformation) | Window.IsVisible(1180)"):
                page = True
            elif page:
                if mon.waitForAbort(1.5):            # a next page (similar title, a person ...) may come up
                    return
                if xbmc.getCondVisibility("Window.IsVisible(movieinformation) | Window.IsVisible(1180)"):
                    continue
                page = False
                leave = HOME.getProperty("nuvio.open.leave")
                folder = HOME.getProperty("nuvio.open.folder")
                xbmc.log(f"[skin.lucent] service.py: page closed, leave={leave!r} folder={bool(folder)}", xbmc.LOGINFO)
                if leave or xbmc.getCondVisibility("Player.HasVideo"):
                    self.close()
                    # Play on a series page: Kodi cannot open the seasons under this pop-up, so it is done here
                    if folder and not xbmc.getCondVisibility("Player.HasVideo"):
                        mon.waitForAbort(0.3)
                        xbmc.executebuiltin(f'ActivateWindow(Videos,"{folder}",return)')
                    return
            if mon.waitForAbort(0.3):
                return

    def close(self):
        self.closed = True
        super().close()

    def onAction(self, action):
        if action.getId() in CLOSE:
            self.close()


def main():
    args = sys.argv[1:]
    if not args or not args[0].isdigit():
        return
    name = urllib.parse.unquote(args[1]) if len(args) > 1 else ""
    logo = urllib.parse.unquote(args[2]) if len(args) > 2 else ""
    window = Service("Lucent_Service.xml", xbmcaddon.Addon("skin.lucent").getAddonInfo("path"), "Default", "1080i")
    window.setup(args[0], name, logo, args[3] if len(args) > 3 else "")
    window.doModal()
    window.closed = True
    del window


main()
