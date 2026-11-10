# -*- coding: utf-8 -*-
"""The cast of a film or series as a pop-up: a row of round portraits in a panel, the film stays visible behind it.
OK opens everything with that actor."""
import xbmc
import xbmcgui

import dialogs
import tmdb
import util

T = util.T


class Cast(dialogs.Base):
    def onInit(self):
        meta = self.args["meta"]
        self.people = [p for p in meta.get("cast") or [] if p.get("name")]
        bits = [str(meta["year"])] if meta.get("year") else []
        bits += (meta.get("genres") or [])[:2]
        if meta.get("runtime"):
            bits.append("%d min" % int(meta["runtime"]))
        self.fill({"title": meta["title"], "logo": meta.get("logo") or "", "fanart": meta.get("fanart") or "", "info": " · ".join(bits),
                   "head": T("ACTEURS", "CAST") if self.people else T("Geen acteurs bekend", "No cast known")})
        row = self.getControl(100)
        for person in self.people:
            item = xbmcgui.ListItem(person["name"], person.get("role") or "", offscreen=True)
            item.setArt({"thumb": person.get("thumb") or ""})
            item.setProperty("letter", "".join(w[:1] for w in person["name"].split()[:2]).upper())
            row.addItem(item)
        self.hint()
        self.setFocusId(100)

    def hint(self):
        at = self.getControl(100).getSelectedPosition()
        if 0 <= at < len(self.people):
            self.fill({"hint": T("OK: films en series met %s", "OK: films and series with %s") % self.people[at]["name"]})

    def onAction(self, action):
        if action.getId() in dialogs.BACK:
            return self.close()
        self.hint()
        return None

    def onClick(self, _control):
        at = self.getControl(100).getSelectedPosition()
        if 0 <= at < len(self.people):
            person = self.people[at]
            self.close()
            xbmc.executebuiltin("ActivateWindow(Videos,%s,return)" % util.url_for(action="list", name="person", id=person.get("id")))


def open_cast(kind, tmdb_id):
    meta = tmdb.details("movie" if kind == "movie" else "tvshow", tmdb_id)
    if not meta:
        return util.notify(T("Acteurs niet gevonden", "Cast not found"))
    import ranking_ui
    ranking_ui.open_screen(Cast, "lucent_cast.xml", meta=meta)
    return None
