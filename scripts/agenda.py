# -*- coding: utf-8 -*-
"""Lucent: the Calendar screen - Week | List | Month - of the series and films in your Trakt collection.

RunScript(special://skin/scripts/agenda.py)           open the calendar
RunScript(special://skin/scripts/agenda.py,follow)    switch the bell (notification) of the item on the info page on / off
RunScript(special://skin/scripts/agenda.py,state)     info page: is this item followed? (Window(home) nuvio.agenda.followed)
RunScript(special://skin/scripts/agenda.py,service)   background helper for the "new episode" pop-up
RunScript(special://skin/scripts/agenda.py,ensure_tab) add the Calendar tab to the side menu (once)

The window is xml/Lucent_Agenda.xml (see gen_agenda.py); this file fills its lists and handles the buttons.
"""
import datetime
import sys

import xbmc
import xbmcgui

import agenda_core as core

WINDOW_XML = "Lucent_Agenda.xml"
ACTION_PREVIOUS_MENU = 10
ACTION_NAV_BACK = 92

VIEW_BUTTONS = {101: "week", 102: "list", 103: "month"}
LIST, BELL_LIST, OPEN_LIST, STOP_LIST = 200, 301, 302, 303
WEEK_PREV, WEEK_DAYS, WEEK_NEXT = 411, range(412, 419), 419
CHIPS = {421: "all", 422: "tv", 423: "movie"}
CARDS, BELL_WEEK = 430, 431
MONTH_PREV, MONTH_NEXT, GRID = 511, 512, 520

_NL = core._NL
TX = {
    "week": ("Week", "Week"), "list": ("List", "Lijst"), "month": ("Month", "Maand"),
    "all": ("All", "Alles"), "tv": ("Series", "Series"), "movie": ("Films", "Films"),
    "today": ("Today", "Vandaag"), "tomorrow": ("Tomorrow", "Morgen"),
    "open_show": ("Open series", "Serie openen"), "open_movie": ("Open film", "Film openen"),
    "bell_on": ("Notifications on", "Meldingen aan"), "bell_off": ("Notifications off", "Meldingen uit"),
    "unfollow": ("Remove from calendar", "Uit kalender halen"),
    "next_of": ("Next of {0}", "Volgende van {0}"),
    "times": ("Times in local time ({0})", "Tijden in lokale tijd ({0})"),
    "powered": ("Data from TMDB and TVmaze", "Gegevens van TMDB en TVmaze"),
    "episodes": ("{0} episodes", "{0} afleveringen"), "episode": ("1 episode", "1 aflevering"),
    "none_day": ("Nothing on this day", "Niets op deze dag"),
    "aired_on": ("Aired on {0}", "Uitgezonden op {0}"), "airs_on": ("Airs on {0}", "Verschijnt op {0}"),
    "empty_title": ("Nothing to show yet", "Nog niets om te tonen"),
    "empty_text": ("The calendar shows the series and films of your Trakt collection (Seren library). Log in to Trakt in "
                   "Seren and add series to your library; they show up here by themselves. Or open a series or film and "
                   "choose the bell on its info page.",
                   "De kalender toont de series en films uit je Trakt-collectie (Seren-bibliotheek). Log in bij Trakt in "
                   "Seren en zet series in je bibliotheek; ze komen dan vanzelf hier te staan. Of open een serie of film en "
                   "kies de bel op de infopagina."),
    "loading": ("Loading the calendar…", "Kalender laden…"),
}


def t(key, *args):
    text = TX[key][1 if _NL else 0]
    return text.format(*args) if args else text


def parse(value):
    return datetime.date.fromisoformat(value)


def add_days(d, n):
    return d + datetime.timedelta(days=n)


def monday(d):
    return add_days(d, -d.weekday())


def nice_day(d, long=True):
    today = core.today()
    if d == today:
        return t("today")
    if d == add_days(today, 1):
        return t("tomorrow")
    return core.day_long(d) if long else core.day_short(d)


def meta(ev):
    parts = [ev.get("network") or ""]
    if ev.get("rating"):
        parts.append(f"★ {core.number(ev['rating'])}")
    parts.append(ev.get("genre") or "")
    return "  ·  ".join(p for p in parts if p)


def ep_title(ev):
    """Second line of a row: 'S10 A3 · Streets of Fire', or for a film where it is shown."""
    if ev["kind"] == "tv":
        return f"{core.ep_code(ev)}  ·  {ev['title']}" if ev["title"] else core.ep_code(ev)
    gap = (core.today() - parse(ev["date"])).days
    if ev.get("digital"):
        return core.tr("digital")
    return core.tr("cinema") if 0 <= gap <= 90 else core.tr("cinema_soon") if gap < 0 else core.tr("film")


def when_line(ev):
    d = parse(ev["date"])
    text = t("today") if d == core.today() else core.day_long(d)
    return f"{text} · {ev['time']}" if ev["time"] else text


def listitem(label, label2="", thumb="", **props):
    item = xbmcgui.ListItem(label, label2)
    if thumb:
        item.setArt({"thumb": thumb, "poster": thumb})
    for key, value in props.items():
        item.setProperty(key, "" if value is None else str(value))
    return item


def group_by_show(events):
    """One card per series and day: two episodes on one day become '2 episodes · S1 E5–E6'."""
    out = []
    for ev in events:
        for card in out:
            if card["show"] == ev["show"] and card["date"] == ev["date"] and ev["kind"] == "tv":
                card["more"].append(ev)
                break
        else:
            out.append(dict(ev, more=[ev]))
    return out


class Agenda(xbmcgui.WindowXML):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.view = "list"
        self.anchor = core.today()          # week view: any day in the week shown; month view: any day in the month
        self.selected = core.today()        # week view: the day whose cards are shown
        self.chip = "all"
        self.events = []
        self.ready = False
        self.week_key = ""

    # ------------------------------------------------------------------ window events
    def onInit(self):
        if self.ready:
            return
        self.ready = True
        for key in ("week", "list", "month", "all", "tv", "movie", "open_show", "open_movie", "bell_on", "bell_off",
                    "unfollow", "empty_title", "empty_text", "powered"):
            self.setProperty(f"agenda.t.{key}", t(key))
        import time
        self.setProperty("agenda.t.times", t("times", time.strftime("%Z") or ""))
        for i, name in enumerate(core.WEEKDAYS_SHORT[core.LANG]):
            self.setProperty(f"agenda.wd{i}", name.capitalize())
        self.setProperty("agenda.view", self.view)
        self.load()
        self.show_view(self.view, focus=True)

    def onAction(self, action):
        if action.getId() in (ACTION_PREVIOUS_MENU, ACTION_NAV_BACK):
            self.close()

    def onFocus(self, control_id):
        if control_id in WEEK_DAYS:
            day = monday(self.anchor) + datetime.timedelta(days=control_id - WEEK_DAYS[0])
            if day != self.selected:
                self.selected = day
                self.fill_cards()
            self.setProperty("agenda.selday", str(control_id - WEEK_DAYS[0] + 1))

    def onClick(self, control_id):
        if control_id in VIEW_BUTTONS:
            self.show_view(VIEW_BUTTONS[control_id], focus=True)
        elif control_id == LIST:
            self.open_selected(LIST)
        elif control_id == CARDS:
            self.open_selected(CARDS)
        elif control_id == OPEN_LIST:
            self.open_selected(LIST)
        elif control_id == BELL_LIST:
            self.toggle_bell(LIST)
        elif control_id == BELL_WEEK:
            self.toggle_bell(CARDS)
        elif control_id == STOP_LIST:
            self.unfollow(LIST)
        elif control_id == WEEK_PREV:
            self.shift_week(-7)
        elif control_id == WEEK_NEXT:
            self.shift_week(7)
        elif control_id in WEEK_DAYS:
            self.setFocusId(CARDS)
        elif control_id in CHIPS:
            self.chip = CHIPS[control_id]
            self.fill_week()
        elif control_id == MONTH_PREV:
            self.shift_month(-1)
        elif control_id == MONTH_NEXT:
            self.shift_month(1)
        elif control_id == GRID:
            self.open_selected(GRID)

    # ------------------------------------------------------------------ data
    def load(self):
        self.events = core.all_events()
        self.setProperty("agenda.empty", "" if core.load_follow()["shows"] else "1")

    def reload(self):
        focus = self.getFocusId()
        self.load()
        self.show_view(self.view, focus=False)
        if focus:
            try:
                self.setFocusId(focus)
            except Exception:  # noqa: BLE001
                pass

    def events_on(self, day):
        key = day.isoformat()
        return [e for e in self.events if e["date"] == key]

    # ------------------------------------------------------------------ views
    def show_view(self, view, focus):
        self.view = view
        self.setProperty("agenda.view", view)
        for button, name in VIEW_BUTTONS.items():
            self.setProperty(f"agenda.is.{name}", "1" if name == view else "")
        if view == "list":
            self.fill_list()
            target = LIST
        elif view == "week":
            self.fill_week()
            target = WEEK_DAYS[0] + (self.selected - monday(self.anchor)).days
        else:
            self.fill_month()
            target = GRID
        if focus and not self.getProperty("agenda.empty"):
            self.setFocusId(target)
        elif focus:
            self.setFocusId(102)

    # -- list
    def fill_list(self):
        lo, hi = add_days(core.today(), -7).isoformat(), add_days(core.today(), 90).isoformat()
        events = [e for e in self.events if lo <= e["date"] <= hi]
        items, first_today, last_date = [], 0, ""
        by_show = {}
        for ev in self.events:
            by_show.setdefault(ev["show"], []).append(ev)
        for ev in events:
            d = parse(ev["date"])
            header = nice_day(d) if ev["date"] != last_date else ""
            if header and not first_today and ev["date"] >= core.today().isoformat():
                first_today = len(items)
            last_date = ev["date"]
            upcoming = [e for e in by_show[ev["show"]] if (e["date"], e["time"]) > (ev["date"], ev["time"])][:2]
            nxt = {}
            for n, e in enumerate(upcoming, start=1):
                nxt[f"next{n}_title"] = ep_title(e)
                nxt[f"next{n}_sub"] = when_line(e)
                nxt[f"next{n}_thumb"] = e["still"]
            extra = {"headerdate": core.day_short(d) if d == core.today() and header else "",
                     "nextlabel": t("next_of", ev["name"]) if upcoming else ""}
            items.append(listitem(
                ev["name"], ep_title(ev), ev["still"] or ev["poster"], header=header, time=ev["time"], datecol=core.day_short(d),
                notify="1" if ev["notify"] else "", showkey=ev["show"], tmdb=ev["tmdb"], kind=ev["kind"], backdrop=ev["backdrop"],
                poster=ev["poster"], when=when_line(ev), dtitle=ep_title(ev), meta=meta(ev), plot=ev["plot"],
                still=ev["still"], bellText=t("bell_on") if ev["notify"] else t("bell_off"),
                openText=t("open_movie") if ev["kind"] == "movie" else t("open_show"), **nxt, **extra))
        control = self.getControl(LIST)
        control.reset()
        control.addItems(items)
        if items:
            control.selectItem(first_today)

    # -- week
    def shift_week(self, days):
        self.anchor = add_days(self.anchor, days)
        self.selected = add_days(self.selected, days)
        self.fill_week()
        self.setFocusId(WEEK_DAYS[0] + (self.selected - monday(self.anchor)).days)

    def fill_week(self):
        start = monday(self.anchor)
        for n in range(7):
            d = add_days(start, n)
            count = len([e for e in self.events_on(d) if self.chip in ("all", e["kind"])])
            prefix = f"agenda.day{n + 1}."
            self.setProperty(prefix + "dow", t("today") if d == core.today() else core.WEEKDAYS_SHORT[core.LANG][d.weekday()])
            self.setProperty(prefix + "num", str(d.day))
            self.setProperty(prefix + "dots", "●" * min(count, 3))
            self.setProperty(prefix + "today", "1" if d == core.today() else "")
        if not start <= self.selected <= add_days(start, 6):
            self.selected = start
        for name in CHIPS.values():
            self.setProperty(f"agenda.chip.{name}", "1" if name == self.chip else "")
        self.fill_cards()

    def fill_cards(self):
        events = [e for e in self.events_on(self.selected) if self.chip in ("all", e["kind"])]
        items = []
        for card in group_by_show(events):
            first, last = card["more"][0], card["more"][-1]
            multi = len(card["more"]) > 1
            code = (f"{core.ep_code(first)}–{last['episode']}" if multi else core.ep_code(first)) if first["kind"] == "tv" else ""
            caption = t("episodes", len(card["more"])) if multi else (first["title"] or ep_title(first))
            sub = "  ·  ".join(x for x in ((core.tr("time_unknown") if not first["time"] else ""), first["network"]) if x)
            items.append(listitem(
                card["name"], caption, first["still"] or first["poster"], time=first["time"], epcode=code,
                caption2=sub or first["network"], notify="1" if card["notify"] else "", showkey=card["show"], tmdb=card["tmdb"],
                kind=card["kind"], backdrop=card["backdrop"], hwhen=t("airs_on" if card["date"] > core.today().isoformat() else "aired_on",
                                                                      when_line(first)),
                hsub=f"{core.ep_code(first)}  ·  {first['title']}" if first["kind"] == "tv" and not multi else (code if multi else ep_title(first)),
                hmeta=meta(first), plot=first["plot"],
                bellText=t("bell_on") if card["notify"] else t("bell_off")))
        control = self.getControl(CARDS)
        control.reset()
        control.addItems(items)
        self.setProperty("agenda.week.empty", "" if items else t("none_day"))
        self.setProperty("agenda.weektitle", core.day_long(self.selected))

    # -- month
    def shift_month(self, months):
        first = self.anchor.replace(day=1)
        month = first.month - 1 + months
        self.anchor = first.replace(year=first.year + month // 12, month=month % 12 + 1)
        self.fill_month()

    def fill_month(self):
        first = self.anchor.replace(day=1)
        self.anchor = first
        self.setProperty("agenda.monthtitle", core.month_title(first))
        start = monday(first)
        items, pick = [], 0
        for n in range(42):
            d = add_days(start, n)
            events = self.events_on(d)
            if d == core.today() or (not pick and d == first and core.today().month != first.month):
                pick = n
            lead = events[0] if events else None
            props = {"day": d.day, "inmonth": "1" if d.month == first.month else "", "today": "1" if d == core.today() else "",
                     "more": f"+{len(events) - 1}" if len(events) > 1 else "", "dayname": core.day_long(d),
                     "count": (t("episodes", len(events)) if len(events) > 1 else t("episode")) if events else t("none_day"),
                     "has": "1" if events else ""}
            for i, ev in enumerate(events[:3], start=1):
                props[f"e{i}_time"] = ev["time"] or ""
                props[f"e{i}_name"] = ev["name"]
                props[f"e{i}_sub"] = "  ·  ".join(x for x in (ep_title(ev), ev.get("network")) if x)
                props[f"e{i}_thumb"] = ev["still"] or ev["poster"]
                props[f"e{i}_code"] = core.ep_code(ev)
            items.append(listitem(str(d.day), "", (lead["poster"] or lead["still"]) if lead else "", **props))
        control = self.getControl(GRID)
        control.reset()
        control.addItems(items)
        control.selectItem(pick)

    # ------------------------------------------------------------------ actions
    def current(self, control_id):
        try:
            return self.getControl(control_id).getSelectedItem()
        except Exception:  # noqa: BLE001
            return None

    def open_selected(self, control_id):
        item = self.current(control_id)
        if not item:
            return
        if control_id == GRID:
            day = self.events_on(add_days(monday(self.anchor.replace(day=1)), self.getControl(GRID).getSelectedPosition()))
            if not day:
                return
            name, kind, tmdb = day[0]["name"], day[0]["kind"], day[0]["tmdb"]
        else:
            name, kind = item.getLabel(), item.getProperty("kind") or "tv"
            tmdb = item.getProperty("tmdb")
        self.close()
        core.open_in_seren(name, kind, int(tmdb) if str(tmdb).isdigit() else None)

    def toggle_bell(self, control_id):
        item = self.current(control_id)
        if not item:
            return
        key = item.getProperty("showkey")
        rec = core.load_follow()["shows"].get(key)
        if rec:
            core.set_notify(key, not rec.get("notify", False))
            self.reload()

    def unfollow(self, control_id):
        item = self.current(control_id)
        if not item:
            return
        position = self.getControl(control_id).getSelectedPosition()
        core.unfollow(item.getProperty("showkey"))
        self.reload()
        control = self.getControl(control_id)
        if control.size():
            control.selectItem(min(position, control.size() - 1))


def open_window():
    import xbmcaddon
    path = xbmcaddon.Addon("skin.lucent").getAddonInfo("path")
    if core.stale():
        xbmc.executebuiltin("ActivateWindow(busydialognocancel)")
        try:
            core.refresh()
        except Exception as error:  # noqa: BLE001
            core.log(f"refresh failed: {error}")
        finally:
            xbmc.executebuiltin("Dialog.Close(busydialognocancel)")
    window = Agenda(WINDOW_XML, path, "Default", "1080i")
    window.doModal()
    del window


def ensure_tab():
    """Add the Calendar tab to the side menu once (before Settings)."""
    if xbmc.getInfoLabel("Skin.String(nuvio.agenda.tab)"):
        return
    if not xbmc.getInfoLabel("Skin.String(nuvio.menu.version)"):
        return                              # the menu is not written yet; next time
    xbmc.executebuiltin('Skin.SetString(nuvio.agenda.tab,"1")', True)
    import menu
    m = menu.Menu()
    action = "RunScript(special://skin/scripts/agenda.py)"
    if any(tab["action"] == action for tab in m.tabs) or len(m.tabs) >= menu.NTABS:
        return
    at = next((i for i, tab in enumerate(m.tabs) if tab["action"] == "ActivateWindow(Settings)"), len(m.tabs))
    start = m.start_tab()
    m.tabs.insert(at, {"label": menu.tr("t_calendar"), "icon": "icons/calendar.png", "action": action,
                       "widgets": [], "actionlabel": ""})
    m.start = start
    m.save()


if __name__ == "__main__":
    action = sys.argv[1] if len(sys.argv) > 1 else "open"
    if action == "follow":
        core.follow_button()
    elif action == "state":
        core.state()
    elif action == "service":
        core.run_service()
    elif action == "ensure_tab":
        ensure_tab()
    else:
        open_window()
