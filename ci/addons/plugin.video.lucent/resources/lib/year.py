# -*- coding: utf-8 -*-
"""'Your year of watching': hours, films and episodes of this year, the most watched series and favourite kinds.
For everybody together (titles counted once) or one profile."""
from concurrent.futures import ThreadPoolExecutor
import datetime
import threading

import xbmcgui

import dialogs
import tmdb
import tracker
import users
import util

T = util.T


def _watched(user_id, year):
    util.OVERRIDE_USER = user_id
    try:
        films = {i for i, when in tracker.watched_movies().items() if str(when or "").startswith(year)}
        episodes = {(show, key) for show, eps in tracker.watched_episodes().items() for key, when in eps.items() if str(when or "").startswith(year)}
    finally:
        util.OVERRIDE_USER = None
    return films, episodes


def stats(user_ids, year):
    films, episodes = set(), set()
    for user_id in user_ids:
        f, e = _watched(user_id, year)
        films |= f
        episodes |= e
    per_show = {}
    for show, _key in episodes:
        per_show[show] = per_show.get(show, 0) + 1
    with ThreadPoolExecutor(max_workers=8) as pool:
        film_meta = [m for m in pool.map(lambda i: tmdb.details("movie", i), list(films)) if m]
        show_meta = {m["tmdb"]: m for m in pool.map(lambda i: tmdb.details("tvshow", i), list(per_show)) if m}
    minutes = sum(int(m.get("runtime") or 110) for m in film_meta)
    minutes += sum(count * int((show_meta.get(s) or {}).get("runtime") or 45) for s, count in per_show.items())
    genres = {}
    for meta in film_meta:
        for g in meta.get("genres") or []:
            genres[g] = genres.get(g, 0) + 1
    for show, count in per_show.items():
        for g in (show_meta.get(show) or {}).get("genres") or []:
            genres[g] = genres.get(g, 0) + count
    top = max(per_show, key=per_show.get) if per_show else None
    return {"hours": int(round(minutes / 60.0)), "films": len(films), "episodes": len(episodes),
            "top": show_meta.get(top), "top_count": per_show.get(top, 0), "top_minutes": per_show.get(top, 0) * int((show_meta.get(top) or {}).get("runtime") or 45),
            "genres": sorted(genres.items(), key=lambda kv: kv[1], reverse=True)[:4]}


class Year(dialogs.Base):
    def onInit(self):
        self.year = str(datetime.date.today().year)
        self.people = users.everyone()
        self.choices = [(T("Iedereen", "Everybody"), [u["id"] for u in self.people])] + [(u["name"], [u["id"]]) for u in self.people]
        self.at = 0
        row = self.getControl(100)
        for label, _ids in self.choices:
            row.addItem(xbmcgui.ListItem(label, offscreen=True))
        self.show()

    def show(self):
        label, ids = self.choices[self.at]
        row = self.getControl(100)
        for n in range(row.size()):
            row.getListItem(n).setProperty("on", "1" if n == self.at else "")
        if len(ids) > 1:
            title = T("Jullie kijkjaar %s", "Your year of watching %s") % self.year
        else:
            title = T("Kijkjaar %s van %s", "Year of watching %s: %s") % (self.year, label)
        self.fill({"ytitle": title, "empty": T("Even tellen...", "Counting...")})
        threading.Thread(target=self._load, args=(ids,), daemon=True).start()

    def _load(self, ids):
        try:
            data = stats(ids, self.year)
        except util.HttpError:
            data = None
        if not data or not (data["films"] or data["episodes"]):
            self.fill({"empty": T("Dit jaar is er nog niets bekeken.", "Nothing watched yet this year."), "num0": "", "num1": "", "num2": "",
                       "cap0": "", "cap1": "", "cap2": "", "toptitle": "", "tophead": "", "topsub": "", "topposter": "", "genhead": "",
                       "g0": "", "g1": "", "g2": "", "g3": ""})
            return
        props = {"empty": "", "num0": data["hours"], "cap0": T("uur gekeken", "hours watched"), "num1": data["films"], "cap1": T("films", "films"),
                 "num2": data["episodes"], "cap2": T("afleveringen", "episodes"), "genhead": T("FAVORIETE SOORTEN", "FAVOURITE KINDS")}
        top = data["top"]
        if top:
            props.update(tophead=T("MEEST BEKEKEN SERIE", "MOST WATCHED SERIES"), toptitle=top["title"], topposter=top.get("poster") or "",
                         topsub=T("%d afleveringen · %d uur", "%d episodes · %d hours") % (data["top_count"], round(data["top_minutes"] / 60.0)),
                         bg=top.get("fanart") or "")
        biggest = data["genres"][0][1] if data["genres"] else 1
        for n in range(4):
            name, count = data["genres"][n] if n < len(data["genres"]) else ("", 0)
            props["g%d" % n] = name
            if name:
                self.getControl(801 + n).setWidth(max(40, int(800 * count / biggest)))
        self.fill(props)

    def onClick(self, control):
        if control == 100:
            self.at = self.getControl(100).getSelectedPosition()
            self.show()


def open_year():
    import ranking_ui
    ranking_ui.open_screen(Year, "lucent_year.xml")
