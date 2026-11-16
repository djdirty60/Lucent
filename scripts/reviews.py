# -*- coding: utf-8 -*-
"""Lucent 2.1.30: the reviews screen (Lucent_Reviews.xml), opened with OK on a card of the Reviews tab of the info page.

    RunScript(special://skin/scripts/reviews.py,<number of the card>)

The reviews come from the info page (scripts/info.py load_reviews, Window(home).Property(nuvio.info.rev.json)), so
nothing is asked again. TMDB / Trakt switch the source, Without spoilers hides the comments Trakt marks as spoilers.
OK on a review shows the whole text; a spoiler is first only named, OK shows it."""
import json
import sys

import xbmc
import xbmcaddon
import xbmcgui

HOME = xbmcgui.Window(10000)
NL = xbmc.getLanguage(xbmc.ISO_639_1) == "nl"
CLOSE = (9, 10, 92, 216, 247, 257, 275, 61467, 61448)


def t(en, nl):
    return nl if NL else en


def short(text, size=260):
    flat = " ".join(text.split())
    return flat if len(flat) <= size else flat[:size].rsplit(" ", 1)[0] + "…"


class Reviews(xbmcgui.WindowXMLDialog):
    def setup(self, data, start):
        self.reviews = data.get("reviews") or []
        self.start = start
        self.src = self.reviews[start]["src"] if 0 <= start < len(self.reviews) else (self.reviews[0]["src"] if self.reviews else "TMDB")
        self.nospoil = False
        self.shown = set()                      # spoilers you chose to see
        self.items = []

    def onInit(self):
        info = xbmc.getInfoLabel
        self.setProperty("poster", info("ListItem.Art(poster)") or info("ListItem.Art(tvshow.poster)") or info("ListItem.Art(thumb)"))
        self.setProperty("fanart", info("ListItem.Art(fanart)") or info("ListItem.Art(tvshow.fanart)"))
        self.setProperty("title", info("ListItem.TVShowTitle") if info("ListItem.DBType") in ("season", "episode") else info("ListItem.Title"))
        self.setProperty("sub", " · ".join(x for x in (info("ListItem.Year"), info("ListItem.Genre").split(" / ")[0]) if x))
        scores = [float(r["rating"]) for r in self.reviews if r.get("rating")]
        if scores:
            avg = f"{sum(scores) / len(scores):.1f}"
            self.setProperty("avg", "★ " + (avg.replace(".", ",") + " gemiddeld" if NL else avg + " average"))
        self.setProperty("count", t(f"{len(self.reviews)} reviews", f"{len(self.reviews)} recensies"))
        self.setProperty("kicker", t("REVIEWS", "RECENSIES"))
        for src, key in (("TMDB", "tab_tmdb"), ("Trakt", "tab_trakt")):
            n = sum(1 for r in self.reviews if r["src"] == src)
            self.setProperty(key, f"{src} · {n}" if n else "")
        self.setProperty("nospoil_label", t("Without spoilers", "Zonder spoilers"))
        self.setProperty("has_spoilers", "1" if any(r.get("spoiler") for r in self.reviews) else "")
        self.setProperty("empty", t("No reviews here.", "Hier zijn geen recensies."))
        self.fill(select=self.start)
        self.setFocusId(200)

    def fill(self, select=-1):
        self.setProperty("src", self.src)
        self.setProperty("nospoil", "1" if self.nospoil else "")
        lst = self.getControl(200)
        lst.reset()
        self.items, items, pos = [], [], 0
        for index, r in enumerate(self.reviews):
            if r["src"] != self.src or (self.nospoil and r.get("spoiler")):
                continue
            hidden = r.get("spoiler") and index not in self.shown
            li = xbmcgui.ListItem(r.get("author") or "?", " · ".join(x for x in (r.get("when"), r["src"]) if x), offscreen=True)
            li.setProperty("rating", r.get("rating") or "")
            li.setProperty("short", "" if hidden else short(r.get("text") or ""))
            li.setProperty("hidden", t("Contains spoilers · press OK to show", "Bevat spoilers · druk op OK om te tonen") if hidden else "")
            li.setProperty("hint", "" if hidden else t("OK: read the whole review", "OK: hele recensie lezen"))
            if index == select:
                pos = len(items)
            items.append(li)
            self.items.append(index)
        lst.addItems(items)
        if items:
            lst.selectItem(pos)

    def onClick(self, cid):
        if cid in (101, 102):
            self.src = "TMDB" if cid == 101 else "Trakt"
            self.fill()
        elif cid == 103:
            self.nospoil = not self.nospoil
            self.fill()
        elif cid == 200:
            pos = self.getControl(200).getSelectedPosition()
            if not 0 <= pos < len(self.items):
                return
            index = self.items[pos]
            r = self.reviews[index]
            if r.get("spoiler") and index not in self.shown:
                self.shown.add(index)
                self.fill(select=index)
                return
            head = " · ".join(x for x in (r.get("author"), ("★ " + r["rating"]) if r.get("rating") else "", r.get("when"), r["src"]) if x)
            xbmcgui.Dialog().textviewer(head, r.get("text") or "")

    def onAction(self, action):
        if action.getId() in CLOSE:
            self.close()


def main():
    try:
        data = json.loads(HOME.getProperty("nuvio.info.rev.json") or "{}")
    except ValueError:
        data = {}
    if not data.get("reviews"):
        return
    start = int(sys.argv[1]) - 1 if len(sys.argv) > 1 and sys.argv[1].isdigit() else 0
    win = Reviews("Lucent_Reviews.xml", xbmcaddon.Addon("skin.lucent").getAddonInfo("path"), "Default", "1080i")
    win.setup(data, start)
    win.doModal()
    del win


if __name__ == "__main__":
    main()
