"""Lucent: one streaming service in a pop-up - its six lists under each other (Lucent_Service.xml).

  RunScript(special://skin/scripts/service.py,<TMDb provider id>,<name>,<logo url>)

The lists come from Lucent Library (TMDb, saved copies). OK on a title opens its page, Back closes the pop-up.
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
    def setup(self, pid, name, logo):
        self.pid, self.name, self.logo = pid, name, logo

    def onInit(self):
        self.setProperty("svc.name", self.name)
        self.setProperty("svc.logo", self.logo)
        self.setProperty("svc.sub", t("New, popular and top rated", "Nieuw, populair en best beoordeeld"))
        self.setProperty("svc.hint", t("Up / down: another list  ·  left / right: browse  ·  OK: open  ·  Back: close",
                                       "Omhoog / omlaag: andere lijst  ·  links / rechts: bladeren  ·  OK: openen  ·  Terug: sluiten"))
        for n, (kind, en, nl) in enumerate(KINDS, start=1):
            self.setProperty(f"row.{n}.label", t(en, nl))
            self.setProperty(f"row.{n}", f"plugin://script.lucent.library/?action=tmdbbrowse&list=prov_{self.pid}_{kind}")
        self.setFocusId(801)

    def onClick(self, cid):
        if not 801 <= cid <= 806:
            return
        base = f"Container({cid}).ListItem."
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
        threading.Thread(target=self.follow, daemon=True).start()

    def follow(self):
        """When Play on the title page opens the series (Seren's seasons) or starts a film, this pop-up must go away:
        it sits above everything, so the seasons opened behind it and it looked as if Play did nothing."""
        mon = xbmc.Monitor()
        for _ in range(40):                       # wait for the page
            if xbmc.getCondVisibility("Window.IsVisible(movieinformation)") or mon.waitForAbort(0.25):
                break
        while not mon.abortRequested():              # pages can follow each other (similar titles, a person ...)
            while xbmc.getCondVisibility("Window.IsVisible(movieinformation)"):
                if mon.waitForAbort(0.25):
                    return
            if mon.waitForAbort(1.5):
                return
            if not xbmc.getCondVisibility("Window.IsVisible(movieinformation) | Window.IsVisible(1180)"):
                break
            while xbmc.getCondVisibility("Window.IsVisible(1180)"):     # a person / studio page on top
                if mon.waitForAbort(0.25):
                    return
        if HOME.getProperty("nuvio.open.leave") or xbmc.getCondVisibility(
                "Window.IsActive(videos) | Player.HasVideo | Window.IsActive(busydialog) | Window.IsActive(busydialognocancel)"):
            self.close()

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
    window.setup(args[0], name, logo)
    window.doModal()
    del window


main()
