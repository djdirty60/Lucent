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
        self.closed = False

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
        if not getattr(self, "watching", False):
            self.watching = True
            threading.Thread(target=self.watch, daemon=True).start()

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
    window.setup(args[0], name, logo)
    window.doModal()
    window.closed = True
    del window


main()
