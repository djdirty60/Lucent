# -*- coding: utf-8 -*-
"""Kompas screens: the Kompas page, Your taste, 'Do you like this?' (one title at a time) and the question after a film."""
import random
import threading

import xbmc
import xbmcgui

import dialogs
import kompas
import tmdb
import users
import util

T = util.T
CONTEXT = (117, 101)       # menu button, long press


def _info(meta):
    bits = [T("Film", "Film") if meta["kind"] == "movie" else T("Serie", "Series")]
    if meta.get("year"):
        bits.append(str(meta["year"]))
    if meta.get("runtime"):
        bits.append("%d min" % int(meta["runtime"]))
    if meta.get("rating"):
        bits.append("★ %.1f" % float(meta["rating"]))
    return " · ".join(bits)


def _open(cls, xml, **kwargs):
    import ranking_ui
    ranking_ui.open_screen(cls, xml, **kwargs)


COUNTRIES = {"US": ("VS", "US"), "GB": ("VK", "UK"), "NL": ("Nederland", "Netherlands"), "BE": ("België", "Belgium"), "FR": ("Frankrijk", "France"),
             "DE": ("Duitsland", "Germany"), "ES": ("Spanje", "Spain"), "IT": ("Italië", "Italy"), "CA": ("Canada", "Canada"),
             "JP": ("Japan", "Japan"), "KR": ("Zuid-Korea", "South Korea"), "SE": ("Zweden", "Sweden"), "DK": ("Denemarken", "Denmark"),
             "NO": ("Noorwegen", "Norway"), "AU": ("Australië", "Australia"), "IE": ("Ierland", "Ireland"), "IN": ("India", "India"),
             "MX": ("Mexico", "Mexico"), "CN": ("China", "China"), "NZ": ("Nieuw-Zeeland", "New Zealand")}


# ------------------------------------------------------------------ the Kompas page
class Page(dialogs.Base):
    def onInit(self):
        self.people = users.everyone()
        self.with_ids = [users.current_id()]
        self.filters = {"kind": "movie", "minutes": 0, "mood": None, "tone": 0}
        self.found, self.shown = [], set()
        self.fill({"ktitle": "Kompas", "more3": T("Nog drie", "Three more"), "lighter": T("Lichter", "Lighter"), "darker": T("Donkerder", "Darker"),
                   "newer": T("Nieuwer", "Newer"), "gems": T("Verborgen parels", "Hidden gems"), "filters": T("Meer filters", "More filters"),
                   "saverow": T("Bewaar als rij", "Save as row")})
        self.top_row()
        self.mood_row()
        self.toggles()
        if kompas.needs_start() and len(self.with_ids) == 1 and not util.HOME.getProperty("lucent.video.kompas.started"):
            util.HOME.setProperty("lucent.video.kompas.started", "1")
            threading.Thread(target=self._first_time, daemon=True).start()
        else:
            self.refresh()

    def _first_time(self):
        if xbmcgui.Dialog().yesno("Kompas", T("Kompas kent je nog niet. Wil je eerst een paar titels laten zien die je mooi vindt?",
                                              "Kompas does not know you yet. Do you first want to show a few titles you like?"),
                                  nolabel=T("Later", "Later"), yeslabel=T("Ja", "Yes")):
            open_start()
        self.refresh()

    def who_label(self):
        names = [p["name"] for p in self.people if p["id"] in self.with_ids]
        return " + ".join(names) if len(names) <= 2 else T("%d kijkers", "%d viewers") % len(names)

    def top_row(self):
        row = self.getControl(110)
        at = max(0, row.getSelectedPosition())
        row.reset()
        for key, nl, en in kompas.KINDS:
            item = xbmcgui.ListItem(T(nl, en), offscreen=True)
            item.setProperty("on", "1" if self.filters["kind"] == key else "")
            row.addItem(item)
        minutes = next(t for t in kompas.TIMES if t[0] == self.filters["minutes"])
        for label, on in ((T(minutes[1], minutes[2]), bool(self.filters["minutes"])), (self.who_label(), len(self.with_ids) > 1)):
            item = xbmcgui.ListItem(label, offscreen=True)
            item.setProperty("on", "1" if on else "")
            row.addItem(item)
        row.selectItem(at)

    def mood_row(self):
        row = self.getControl(120)
        at = max(0, row.getSelectedPosition())
        row.reset()
        for key, nl, en, _m, _t in kompas.MOODS:
            item = xbmcgui.ListItem(T(nl, en), offscreen=True)
            item.setProperty("on", "1" if self.filters.get("mood") == key else "")
            row.addItem(item)
        row.selectItem(at)

    def toggles(self):
        extra = any(self.filters.get(k) for k in ("decade", "region", "award", "family", "complete"))
        self.fill({"t_lighter": "1" if self.filters.get("tone") == -1 else "", "t_darker": "1" if self.filters.get("tone") == 1 else "",
                   "t_newer": "1" if self.filters.get("newer") else "", "t_gems": "1" if self.filters.get("gems") else "",
                   "t_filters": "1" if extra else ""})

    def refresh(self):
        self.fill({"empty": T("Even zoeken...", "Searching...")})
        self.getControl(200).reset()
        threading.Thread(target=self._load, daemon=True).start()

    def _load(self):
        try:
            self.found = kompas.page_picks(dict(self.filters), list(self.with_ids), self.shown)
        except util.HttpError:
            self.found = []
        for meta in self.found:
            self.shown.add("%s:%s" % (meta["kind"], meta["tmdb"]))
        row = self.getControl(200)
        row.reset()
        for meta in self.found:
            item = xbmcgui.ListItem(meta["title"], offscreen=True)
            item.setLabel2(_info(meta))
            item.setProperty("reason", meta.get("reason") or "")
            item.setArt({"fanart": meta.get("fanart") or meta.get("poster"), "poster": meta.get("poster")})
            row.addItem(item)
        self.fill({"empty": "" if self.found else T("Niets gevonden. Probeer andere keuzes.", "Nothing found. Try other choices."),
                   "bg": self.found[0].get("fanart") if self.found else ""})
        if self.found and self.getFocusId() not in (110, 120) and not 301 <= self.getFocusId() <= 307:
            self.setFocusId(200)

    def _people(self):
        names = [p["name"] for p in self.people]
        picked = xbmcgui.Dialog().multiselect(T("Wie kijkt er mee?", "Who is watching?"), names,
                                              preselect=[n for n, p in enumerate(self.people) if p["id"] in self.with_ids])
        if picked:
            self.with_ids = [self.people[n]["id"] for n in picked]

    def more_filters(self):
        import browse
        f = self.filters
        none = T("alle", "all")
        decade = ("%ss" % f["decade"]) if f.get("decade") else none
        region = next((T(r[1], r[2]) for r in kompas.REGIONS if r[0] == f.get("region")), none)
        award = browse.AWARDS[f["award"]][0] if f.get("award") else none
        options = [T("Decennium: %s", "Decade: %s") % decade, T("Land of regio: %s", "Country or region: %s") % region,
                   T("Prijzen: %s", "Acclaim: %s") % award,
                   T("Familieavond (tot 12 jaar, geen horror): %s", "Family night (12 and under, no horror): %s") % (T("aan", "on") if f.get("family") else T("uit", "off")),
                   T("Alleen afgelopen series: %s", "Complete series only: %s") % (T("aan", "on") if f.get("complete") else T("uit", "off")),
                   T("Alle filters wissen", "Clear all filters")]
        choice = xbmcgui.Dialog().select(T("Meer filters", "More filters"), options)
        if choice == 0:
            decades = [None] + [str(d) for d in range(2020, 1949, -10)]
            picked = xbmcgui.Dialog().select(T("Decennium", "Decade"), [none] + ["%ss" % d for d in decades[1:]])
            if picked >= 0:
                f["decade"] = decades[picked]
        elif choice == 1:
            picked = xbmcgui.Dialog().select(T("Land of regio", "Country or region"), [none] + [T(r[1], r[2]) for r in kompas.REGIONS])
            if picked >= 0:
                f["region"] = kompas.REGIONS[picked - 1][0] if picked else None
        elif choice == 2:
            keys = list(browse.AWARDS)
            picked = xbmcgui.Dialog().select(T("Prijzen", "Acclaim"), [none] + [browse.AWARDS[k][0] for k in keys])
            if picked >= 0:
                f["award"] = keys[picked - 1] if picked else None
        elif choice == 3:
            f["family"] = not f.get("family")
        elif choice == 4:
            f["complete"] = not f.get("complete")
            if f["complete"]:
                f["kind"] = "tvshow"
        elif choice == 5:
            for key in ("decade", "region", "award", "family", "complete", "newer", "gems"):
                f.pop(key, None)
            f["tone"] = 0
        return choice >= 0

    def label_of_row(self):
        f = self.filters
        bits = [T(k[1], k[2]) for k in kompas.KINDS if k[0] == f["kind"]]
        bits += [T(m[1], m[2]) for m in kompas.MOODS if m[0] == f.get("mood")]
        if f.get("tone"):
            bits.append(T("Lichter", "Lighter") if f["tone"] < 0 else T("Donkerder", "Darker"))
        if f.get("gems"):
            bits.append(T("Verborgen parels", "Hidden gems"))
        if f.get("newer"):
            bits.append(T("Nieuwer", "Newer"))
        if f.get("decade"):
            bits.append("%ss" % f["decade"])
        bits += [T(r[1], r[2]) for r in kompas.REGIONS if r[0] == f.get("region")]
        if f.get("minutes"):
            bits.append(next(T(t[1], t[2]) for t in kompas.TIMES if t[0] == f["minutes"]))
        return "Kompas: " + " · ".join(bits)

    def onClick(self, control):
        f = self.filters
        if control == 110:
            at = self.getControl(110).getSelectedPosition()
            if at < len(kompas.KINDS):
                f["kind"] = kompas.KINDS[at][0]
            elif at == len(kompas.KINDS):
                order = [t[0] for t in kompas.TIMES]
                f["minutes"] = order[(order.index(f["minutes"]) + 1) % len(order)]
            else:
                self._people()
            self.top_row()
            return self.refresh()
        if control == 120:
            key = kompas.MOODS[self.getControl(120).getSelectedPosition()][0]
            f["mood"] = None if f.get("mood") == key else key
            self.mood_row()
            return self.refresh()
        if control == 301:
            return self.refresh()
        if control in (302, 303):
            wanted = -1 if control == 302 else 1
            f["tone"] = 0 if f.get("tone") == wanted else wanted
        elif control == 304:
            f["newer"] = not f.get("newer")
        elif control == 305:
            f["gems"] = not f.get("gems")
        elif control == 306:
            if not self.more_filters():
                return self.toggles()
            self.top_row()
        elif control == 307:
            label = xbmcgui.Dialog().input(T("Naam van de rij", "Name of the row"), self.label_of_row())
            if label:
                kompas.save_row(dict(f), label)
                util.notify(T("Bewaard. Je vindt de rij bij Kompas en kunt hem op Home zetten.", "Saved. The row is under Kompas and can go on Home."))
            return None
        elif control == 200 and self.found:
            return self.choose(self.found[self.getControl(200).getSelectedPosition()])
        self.toggles()
        return self.refresh()

    def choose(self, meta):
        self.close()
        others = ",".join(i for i in self.with_ids if i != users.current_id())
        kompas.opened(meta["kind"], meta["tmdb"])
        if meta["kind"] == "movie":
            xbmc.executebuiltin("PlayMedia(%s)" % util.url_for(action="play", type="movie", tmdb=meta["tmdb"], **{"with": others}))
        else:
            xbmc.executebuiltin("ActivateWindow(Videos,%s,return)" % util.url_for(action="seasons", tmdb=meta["tmdb"]))

    def onAction(self, action):
        if action.getId() in dialogs.BACK:
            return self.close()
        if self.getFocusId() == 200 and self.found:
            at = self.getControl(200).getSelectedPosition()
            if 0 <= at < len(self.found):
                self.fill({"bg": self.found[at].get("fanart") or ""})
                if action.getId() in CONTEXT:
                    return self.context(self.found[at])
        return None

    def context(self, meta):
        options = [T("Meer zoals dit", "More like this"), T("Op kijklijst", "Add to watchlist"), T("Niet voor mij", "Not for me")]
        choice = xbmcgui.Dialog().contextmenu(options)
        if choice == 0:
            self.close()
            xbmc.executebuiltin("ActivateWindow(Videos,%s,return)" % util.url_for(action="list", name="similar", type=meta["kind"], tmdb=meta["tmdb"]))
        elif choice == 1:
            import tracker
            tracker.set_watchlist(meta, True)
            util.notify(T("Op je kijklijst", "On your watchlist"))
        elif choice == 2:
            kompas.rate(meta["kind"], meta["tmdb"], -1)
            self.refresh()


def open_page():
    if not kompas.on():
        return xbmcgui.Dialog().ok("Kompas", T("Kompas staat uit. Zet het aan bij Instellingen > Algemeen.", "Kompas is off. Turn it on under Settings > General."))
    _open(Page, "lucent_kompas.xml")
    return None


# ------------------------------------------------------------------ your taste
class Taste(dialogs.Base):
    def onInit(self):
        self.show()

    def show(self):
        taste = kompas.profile(fresh=True)
        facets, names = taste.get("facets") or {}, taste.get("names") or {}
        props = {"ttitle": T("Jouw smaak", "Your taste"), "who": users.current()["name"], "genhead": T("SOORTEN", "GENRES"),
                 "drivehead": T("WAT JE KIEZEN STUURT", "WHAT SHAPES YOUR PICKS"), "placehead": T("DECENNIA EN LANDEN", "DECADES AND COUNTRIES"),
                 "note": T("Alles blijft op dit apparaat. Beoordeel titels om Kompas sneller te leren, of begin opnieuw.",
                           "Everything stays on this device. Rate titles to teach Kompas faster, or start fresh."),
                 "b_rate": T("Titels beoordelen", "Rate titles"), "b_reset": T("Opnieuw beginnen", "Start fresh"), "b_off": T("Kompas uitzetten", "Turn Kompas off"),
                 "empty": "" if taste.get("count") else T("Kompas kent je nog niet. Kijk iets of beoordeel een paar titels.", "Kompas does not know you yet. Watch something or rate a few titles.")}
        top = taste.get("top")
        if top:
            props.update(tophead=T("JOUW TOPTITEL", "YOUR TOP TITLE"), toptitle=top.get("t") or "", topposter=tmdb.image(top.get("pp"), "w500"))
            meta = tmdb.details(top["kind"], top["id"])
            props["bg"] = (meta or {}).get("fanart") or ""
        genres = sorted(((v, names.get("g:%s" % k, "")) for k, v in (facets.get("g") or {}).items() if v > 0), reverse=True)[:4]
        for n in range(4):
            props["g%d" % n] = genres[n][1] if n < len(genres) else ""
        lines = []
        for facet, nl, en in (("d", "Regisseur %s", "Director %s"), ("c", "Acteur %s", "Actor %s"), ("w", "Schrijver %s", "Writer %s")):
            best = sorted(((v, k) for k, v in (facets.get(facet) or {}).items() if v > 0.3), reverse=True)[:2]
            lines += [T(nl, en) % names.get("%s:%s" % (facet, k), "") for _v, k in best]
        if not util.NL:
            lines += ["Theme: %s" % names.get("k:%s" % k, "") for _v, k in sorted(((v, k) for k, v in (facets.get("k") or {}).items() if v > 0.4), reverse=True)[:2]]
        props["drivers"] = "[CR]".join(lines[:5])
        decades = [k for _v, k in sorted(((v, k) for k, v in (facets.get("dec") or {}).items() if v > 0), reverse=True)[:2]]
        countries = [k for _v, k in sorted(((v, k) for k, v in (facets.get("o") or {}).items() if v > 0), reverse=True)[:3]]
        place = []
        if decades:
            place.append(T("Vooral jaren %s", "Mostly the %s") % T(" en ".join(d[2:] if int(d) < 2000 else d for d in decades), " and ".join(d + "s" for d in decades)))
        if countries:
            named = [T(*COUNTRIES[c]) if c in COUNTRIES else c for c in countries]
            place.append(T("%s", "%s") % (", ".join(named[:-1]) + T(" en ", " and ") + named[-1] if len(named) > 1 else named[0]))
        pop = taste.get("pop") or 3.0
        place.append(T("Eerder onbekend dan populair", "Rather little known than popular") if pop < 2.8 else
                     T("Vooral bekende titels", "Mostly well-known titles") if pop > 3.5 else T("Bekend en onbekend door elkaar", "Well known and little known mixed"))
        props["places"] = "[CR]".join(place)
        self.fill(props)
        for n in range(4):
            width = int(620 * genres[n][0]) if n < len(genres) else 0
            try:
                self.getControl(801 + n).setWidth(max(24, width))
            except RuntimeError:
                pass
        self.setFocusId(10)

    def onClick(self, control):
        if control == 10:
            self.close()
            open_start(rate_watched=True)
        elif control == 11:
            if forget():
                self.show()
        elif control == 12:
            if xbmcgui.Dialog().yesno("Kompas", T("Kompas uitzetten? De rijen van Kompas worden dan leeg en de vraag na een film komt niet meer.",
                                                  "Turn Kompas off? Its rows become empty and the question after a film stops.")):
                util.ADDON.setSetting("kompas_on", "false")
                kompas.publish()
                self.close()


def open_taste():
    _open(Taste, "lucent_taste.xml")


def forget():
    if not xbmcgui.Dialog().yesno("Kompas", T("Opnieuw beginnen? Je beoordelingen in Kompas worden gewist. Wat je gekeken hebt blijft.",
                                              "Start fresh? Your Kompas ratings are cleared. What you watched stays.")):
        return False
    for name in (kompas.RATINGS, kompas.PROFILE, kompas.ROWS, kompas.SHOWN):
        util.save_json(name, {})
    util.HOME.clearProperty("lucent.video.kompas.started")
    util.notify(T("Kompas begint opnieuw", "Kompas starts fresh"))
    return True


# ------------------------------------------------------------------ one at a time: 'Do you like this?' (D)
def _well_known():
    pairs = []
    for api, kind, pages in (("movie", "movie", (1, 2, 3)), ("tv", "tvshow", (1, 2))):
        for page in pages:
            try:
                rows = tmdb.get("discover/" + api, ttl=7 * 86400, sort_by="vote_count.desc", page=page, include_adult="false").get("results") or []
            except util.HttpError:
                rows = []
            pairs += [(kind, str(r["id"])) for r in rows]
    random.shuffle(pairs)
    return pairs


def _watched_unrated():
    import tracker
    rated = kompas.ratings()
    try:
        films, shows = tracker.watched_movies(), tracker.watched_episodes()
    except util.HttpError:
        return []
    pairs = [("movie", i) for i in sorted(films, key=lambda i: films[i] or "", reverse=True)[:40]]
    pairs += [("tvshow", i) for i in sorted(shows, key=lambda i: max(shows[i].values()) if shows[i] else "", reverse=True)[:20]]
    return [p for p in pairs if "%s:%s" % p not in rated]


class OneByOne(dialogs.Base):
    def onInit(self):
        self.rate_mode = self.args.get("rate_watched")
        self.queue = _watched_unrated() if self.rate_mode else [p for p in _well_known() if "%s:%s" % p not in kompas.ratings()]
        self.yes = 0
        self.need = 5
        if self.rate_mode:
            self.fill({"stitle": T("Wat vond je ervan?", "What did you think?"), "b1": T("Geweldig", "Great"), "b2": T("Leuk", "Nice"),
                       "b3": T("Niet voor mij", "Not for me"), "b4": T("Overslaan", "Skip")})
        else:
            self.fill({"stitle": T("Vind je dit mooi?", "Do you like this?"), "b1": T("Ja, mooi", "Yes, I like it"),
                       "b2": T("Niet gezien", "Not seen"), "b3": T("Niet mijn ding", "Not my thing"), "b4": ""})
        self.next()

    def next(self):
        self.current = None
        while self.queue:
            kind, tmdb_id = self.queue.pop(0)
            meta = tmdb.details(kind, tmdb_id)
            if meta and meta.get("poster"):
                self.current = meta
                break
        if not self.current:
            self.fill({"poster": "", "name": "", "info": "", "empty": T("Dat waren ze allemaal. Dank je!", "That was all of them. Thank you!")})
            return
        left = max(0, self.need - self.yes)
        sub = (T("Kompas leert van elke keuze", "Kompas learns from every choice") if self.rate_mode else
               T("Nog %d nodig", "%d more needed") % left if left else T("Genoeg om te beginnen. Ga gerust door.", "Enough to begin. Feel free to go on."))
        self.fill({"poster": self.current["poster"], "bg": self.current.get("fanart") or "", "name": self.current["title"],
                   "info": _info(self.current), "ssub": sub, "empty": ""})

    def onClick(self, control):
        if not self.current:
            return self.close()
        kind, tmdb_id = self.current["kind"], self.current["tmdb"]
        if self.rate_mode:
            value = {10: 2, 11: 1, 12: -1}.get(control)
            if value is not None:
                kompas.rate(kind, tmdb_id, value)
        else:
            value = {10: 1, 11: None, 12: -1}.get(control)
            if control != 11:
                kompas.rate(kind, tmdb_id, value, send=False)
            if control == 10:
                self.yes += 1
        return self.next()


def open_start(rate_watched=False):
    import ranking_ui
    ranking_ui.open_screen(OneByOne, "lucent_start.xml", rate_watched=rate_watched)
    threading.Thread(target=kompas.run, daemon=True).start()       # new rows with what was just learned


# ------------------------------------------------------------------ after a film (A)
class Rate(dialogs.Base):
    def onInit(self):
        meta = self.args["meta"]
        self.fill({"kicker": T("JE HEBT %s UITGEKEKEN", "YOU FINISHED %s") % (meta.get("title") or "").upper(), "rtitle": T("Wat vond je ervan?", "What did you think?"),
                   "b1": T("Geweldig", "Great"), "b2": T("Leuk", "Nice"), "b3": T("Niet voor mij", "Not for me"),
                   "hint": T("Overslaan met Terug · uit te zetten in de instellingen", "Skip with Back · can be turned off in the settings"),
                   "bg": meta.get("fanart") or ""})
        self.setFocusId(10)

    def onClick(self, control):
        self.result = {10: 2, 11: 1, 12: -1}.get(control)
        self.close()


def rate_after(meta):
    full = tmdb.details("movie", meta["tmdb"]) or meta
    window = Rate("lucent_rate.xml", dialogs.PATH, "Default", "1080i", meta=full)
    window.doModal()
    value = window.result
    del window
    if value is not None:
        kompas.rate("movie", meta["tmdb"], value)
        util.notify(T("Bedankt, Kompas onthoudt het", "Thanks, Kompas remembers it"))


def rate_one(kind, tmdb_id):
    """'Rate' in the menu of a title."""
    options = [T("Geweldig", "Great"), T("Leuk", "Nice"), T("Niet voor mij", "Not for me"), T("Beoordeling wissen", "Clear rating")]
    meta = tmdb.details(kind, tmdb_id) or {"title": ""}
    choice = xbmcgui.Dialog().select(T("Wat vond je van %s?", "What did you think of %s?") % meta.get("title"), options)
    if choice < 0:
        return
    kompas.rate(kind, tmdb_id, [2, 1, -1, None][choice], send=choice < 3)
    util.notify(T("Kompas onthoudt het", "Kompas remembers it"))
