# -*- coding: utf-8 -*-
"""'What shall we watch?': tick who watches and what you feel like, Lucent shows three titles none of you saw yet."""
import random
import threading

import xbmc
import xbmcgui

import dialogs
import kids
import tmdb
import tracker
import users
import util

T = util.T
TIMES = [(T("Elke duur", "Any length"), 0), (T("Tot 90 min", "Up to 90 min"), 90), (T("Tot 2 uur", "Up to 2 hours"), 120)]
KINDS = [(T("Film en serie", "Film and series"), "both"), (T("Film", "Film"), "movie"), (T("Serie", "Series"), "tvshow")]
GENRES = [(T("Alle soorten", "All kinds"), None, None), (T("Komedie", "Comedy"), 35, 35), (T("Spanning", "Thrillers"), 53, 9648),
          (T("Actie", "Action"), 28, 10759), (T("Drama", "Drama"), 18, 18), (T("Familie", "Family"), 10751, 10751),
          (T("Sciencefiction", "Science fiction"), 878, 10765), (T("Animatie", "Animation"), 16, 16), (T("Documentaire", "Documentary"), 99, 99)]


def seen_by(user_ids):
    """Film ids and series ids that any of these people watched (series: at least one episode)."""
    films, shows = set(), set()
    for user_id in user_ids:
        util.OVERRIDE_USER = user_id
        try:
            films |= set(tracker.watched_movies())
            shows |= set(tracker.watched_episodes())
        finally:
            util.OVERRIDE_USER = None
    return films, shows


def suggestions(user_ids, minutes, kind, genre, for_kids, count=3):
    films, shows = seen_by(user_ids)
    wanted = ["movie", "tvshow"] if kind == "both" else [kind]
    pool = []
    for what in wanted:
        api = "movie" if what == "movie" else "tv"
        params = {"sort_by": "popularity.desc", "include_adult": "false", "vote_count.gte": 150 if what == "movie" else 80}
        genre_id = genre[1] if what == "movie" else genre[2]
        if genre_id:
            params["with_genres"] = genre_id
        if minutes:
            params["with_runtime.lte"] = minutes
        if for_kids:
            if what == "movie":
                params.update(certification_country="NL", **{"certification.lte": "6"})
            else:
                params["with_genres"] = ",".join(str(g) for g in (genre_id, 10762) if g)
        done = films if what == "movie" else shows
        try:
            first = tmdb.get("discover/" + api, ttl=12 * 3600, page=1, **params)
        except util.HttpError:
            continue
        pages = [1] + random.sample(range(2, min(int(first.get("total_pages") or 1), 10) + 1), min(2, max(0, min(int(first.get("total_pages") or 1), 10) - 1)))
        for page in pages:
            try:
                rows = first.get("results") if page == 1 else tmdb.get("discover/" + api, ttl=12 * 3600, page=page, **params).get("results")
            except util.HttpError:
                rows = []
            pool += [(what, str(r["id"])) for r in rows or [] if str(r["id"]) not in done]
    random.shuffle(pool)
    out = []
    for pair in list(dict.fromkeys(pool)):
        meta = tmdb.details(*pair)
        import hide
        if meta and meta.get("fanart") and kids.allowed(meta) and hide.keep([meta], "foryou") and (not for_kids or meta["kind"] != "movie" or (kids.age_of(meta) or 99) <= 6):
            out.append(meta)
        if len(out) >= count:
            break
    return out


class Pick(dialogs.Base):
    def onInit(self):
        self.people = users.everyone()
        self.with_ids = {users.current_id()}
        self.time, self.kind, self.genre, self.kids = 2, 0, 0, bool(kids.limit())
        self.found = []
        self.fill({"ptitle": T("Wat zullen we kijken?", "What shall we watch?"), "again": T("Drie nieuwe voorstellen", "Three new suggestions")})
        self.faces()
        self.chips()
        self.refresh()

    def faces(self):
        row = self.getControl(110)
        row.reset()
        for person in self.people:
            item = xbmcgui.ListItem(person["name"], offscreen=True)
            item.setProperty("letter", person["name"][:1].upper())
            item.setProperty("color", person["color"])
            item.setProperty("on", "1" if person["id"] in self.with_ids else "")
            row.addItem(item)
        row.setWidth(108 * len(self.people))
        self.getControl(120).setPosition(96 + 108 * len(self.people) + 24, 122)

    def chips(self):
        row = self.getControl(120)
        at = max(0, row.getSelectedPosition())
        row.reset()
        for label, on in ((TIMES[self.time][0], self.time != 0), (KINDS[self.kind][0], self.kind != 0), (GENRES[self.genre][0], self.genre != 0),
                          (T("Voor de kinderen", "For the children"), self.kids)):
            item = xbmcgui.ListItem(label, offscreen=True)
            item.setProperty("on", "1" if on else "")
            row.addItem(item)
        row.selectItem(at)

    def refresh(self):
        self.fill({"empty": T("Even zoeken...", "Searching...")})
        self.getControl(200).reset()
        threading.Thread(target=self._load, daemon=True).start()

    def _load(self):
        try:
            self.found = suggestions(list(self.with_ids), TIMES[self.time][1], KINDS[self.kind][1], GENRES[self.genre], self.kids)
        except util.HttpError:
            self.found = []
        row = self.getControl(200)
        row.reset()
        for meta in self.found:
            item = xbmcgui.ListItem(meta["title"], offscreen=True)
            bits = [T("Film", "Film") if meta["kind"] == "movie" else T("Serie", "Series")]
            if meta.get("runtime"):
                bits.append("%d min" % int(meta["runtime"]))
            bits += (meta.get("genres") or [])[:1]
            item.setLabel2(" · ".join(bits))
            item.setArt({"fanart": meta.get("fanart") or meta.get("poster"), "poster": meta.get("poster")})
            row.addItem(item)
        self.fill({"empty": "" if self.found else T("Niets gevonden. Probeer andere keuzes.", "Nothing found. Try other choices."),
                   "bg": self.found[0].get("fanart") if self.found else ""})
        if self.found and self.getFocusId() not in (110, 120, 300):
            self.setFocusId(200)

    def onClick(self, control):
        if control == 110:
            person = self.people[self.getControl(110).getSelectedPosition()]
            self.with_ids ^= {person["id"]}
            self.with_ids = self.with_ids or {users.current_id()}
            self.faces()
            return self.refresh()
        if control == 120:
            at = self.getControl(120).getSelectedPosition()
            if at == 0:
                self.time = (self.time + 1) % len(TIMES)
            elif at == 1:
                self.kind = (self.kind + 1) % len(KINDS)
            elif at == 2:
                self.genre = (self.genre + 1) % len(GENRES)
            elif not kids.limit():                   # a kids profile always stays on 'for the children'
                self.kids = not self.kids
            self.chips()
            return self.refresh()
        if control == 300:
            return self.refresh()
        if control == 200 and self.found:
            meta = self.found[self.getControl(200).getSelectedPosition()]
            self.close()
            others = ",".join(i for i in self.with_ids if i != users.current_id())
            if meta["kind"] == "movie":
                xbmc.executebuiltin("PlayMedia(%s)" % util.url_for(action="play", type="movie", tmdb=meta["tmdb"], **{"with": others}))
            else:
                xbmc.executebuiltin("ActivateWindow(Videos,%s,return)" % util.url_for(action="seasons", tmdb=meta["tmdb"]))
        return None

    def onAction(self, action):
        if action.getId() in dialogs.BACK:
            return self.close()
        if self.getFocusId() == 200 and self.found:
            at = self.getControl(200).getSelectedPosition()
            if 0 <= at < len(self.found):
                self.fill({"bg": self.found[at].get("fanart") or ""})
        return None


def open_pick():
    import ranking_ui
    ranking_ui.open_screen(Pick, "lucent_pick.xml")
