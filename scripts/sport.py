# -*- coding: utf-8 -*-
"""Lucent: the Sport screen - My sport | All games | Tables - with the IPTV channels that show each game.

RunScript(special://skin/scripts/sport.py)             open the screen
RunScript(special://skin/scripts/sport.py,ensure_tab)  add the Sport tab to the side menu (once)

The window is xml/Lucent_Sport.xml (gen_sport.py). Data: sport_core.py (ESPN), guide: sport_epg.py (Kodi PVR).
"""
import datetime
import re
import sys
import threading
import time

import xbmc
import xbmcgui

import agenda_core as ac
import sport_core as sc
import sport_epg as epg
import sport_plan as plan

WINDOW_XML = "Lucent_Sport.xml"
ACTION_PREVIOUS_MENU = 10
ACTION_NAV_BACK = 92
ACTION_STOP = 13
VIEW_BUTTONS = {101: "mine", 102: "all", 103: "tables", 104: "follow"}
F_CHIPS, F_SEARCH, F_ORDER, F_MORE, F_SPORTS, F_COMPS, F_BTN, F_TEAMS = 520, 521, 522, 523, 530, 540, 550, 560
SPORT_ORDER = ("soccer", "basketball", "football", "hockey", "baseball", "rugby", "racing", "golf", "tennis", "mma", "aussie")
FOLLOW_BUTTON = 104
LIST = 200
DAY_BUTTONS = range(111, 118)
DAY_PREV, DAY_NEXT = 110, 118
CHANNEL_BUTTONS = {311: 1, 312: 2, 313: 3, 314: 4, 341: 1, 342: 2, 343: 3, 344: 4}
HERO_LIST = 150
HERO_CHANNELS = (341, 342, 343, 344)
SECTION_LISTS = tuple(range(211, 221))
FOLLOW_HOME, FOLLOW_AWAY, SHOW_TABLE = 321, 322, 323
FIX_BUTTON, REMIND_BUTTON, RECORD_BUTTON = 331, 332, 333
LEAGUE_LIST, TABLE_LIST, T_SPORTS = 400, 410, 395
EPG_LEAGUE = "tv"
ACTION_MOVE_LEFT, ACTION_MOVE_RIGHT = 1, 2
HERO_MAX = 6
SPORT_ICON = "special://skin/media/icons/sport.png"
SPORT_ICONS = {"soccer", "basketball", "football", "hockey", "baseball", "rugby", "aussie", "racing", "tennis", "golf", "mma"}


def sport_icon(sport):
    return f"special://skin/media/icons/sport_{sport}.png" if sport in SPORT_ICONS else SPORT_ICON
LETTERS = {"W": "W", "D": "G", "L": "V"} if sc.NL else {}


def nice_day(d):
    today = ac.today()
    if d == today:
        return sc.t("today")
    if d == today + datetime.timedelta(days=1):
        return sc.t("tomorrow")
    if d == today - datetime.timedelta(days=1):
        return sc.t("yesterday")
    return ac.day_long(d)


def league_name(key):
    return sc.LEAGUES[key]["name"] if key in sc.LEAGUES else sc.t("tvguide")


def when_line(ev):
    d = sc.local_day(ev["start"])
    text = nice_day(d) if d == ac.today() else ac.day_long(d)
    return f"{text}  ·  {sc.local_time(ev['start'])}"


def short_when(ev):
    d = sc.local_day(ev["start"])
    text = nice_day(d) if abs((d - ac.today()).days) <= 1 else ac.day_short(d)
    return f"{text}  ·  {sc.local_time(ev['start'])}"


def score_text(ev):
    if ev["kind"] != "teams":
        return ""
    if ev["state"] in ("in", "post") and ev["home"].get("score") != "" and ev["away"].get("score") != "":
        return f"{ev['home']['score']} – {ev['away']['score']}"
    return "v"


def name_events(follow, data):
    """Followed free names ('Max Verstappen') become games of their own, taken from the TV guide titles."""
    out, seen = [], set()
    if not follow["names"]:
        return out
    now = time.time()
    for cid, start, end, title, plot in data.get("rows", []):
        if end < now - 3 * 3600 or start > now + (sc.DAYS_AHEAD * 86400):
            continue
        text = sc.norm(f"{title} {plot}")
        for name in follow["names"]:
            if sc.has_phrase(text, sc.norm(name)):
                key = (start, sc.norm(title))
                if key in seen:
                    break
                seen.add(key)
                out.append({"id": f"{EPG_LEAGUE}:{cid}:{start}", "league": EPG_LEAGUE, "kind": "event", "start": start,
                            "state": "in" if start <= now <= end else "post" if end < now else "pre", "status": "",
                            "home": {}, "away": {}, "title": title, "sub": name, "venue": "", "round": "", "lg": "",
                            "cid": cid})
                break
    return out


def colour(hex_value, alpha="FF"):
    """ESPN gives 'd4121a'; Kodi wants 'AARRGGBB'. Unknown colour -> a calm grey-blue."""
    hex_value = (hex_value or "").strip("# ")
    if len(hex_value) != 6 or any(c not in "0123456789abcdefABCDEF" for c in hex_value):
        hex_value = "3a4a5c"
    return alpha + hex_value.upper()


def listitem(label, label2="", icon="", **props):
    item = xbmcgui.ListItem(label, label2)
    if icon:
        item.setArt({"icon": icon, "thumb": icon})
    for key, value in props.items():
        item.setProperty(key, "" if value is None else str(value))
    return item


class Sport(xbmcgui.WindowXML):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.view = "mine"
        self.anchor = ac.today()
        self.day = ac.today()
        self.events = []             # what the list shows (dicts)
        self.by_id = {}
        self.hero_events = []
        self.hero_index = 0
        self.follow = sc.load_follow()
        self.ready = False
        self.closing = False
        self.table_key = ""
        self.marks = set()
        self.team_name = ""
        self.team_events = []
        self.table_token = 0
        self.table_pos = -1
        self.guide_busy = False
        self.has_pvr = False
        self.sections_shown = 0
        self.f_sport = "soccer"
        self.f_league = ""
        self.f_token = 0
        self.f_dirty = False
        self.f_has_teams = False
        self.f_teams = []
        self.error = ""
        self.loaded = False
        self.last_tint = None

    # ------------------------------------------------------------------ window events
    def onInit(self):
        if self.ready:
            return
        self.ready = True
        for key in ("title", "mine", "all", "tables", "follow", "watch", "gp", "gd", "pts", "powered", "notable", "hint", "hint_all", "previewhint", "fullhint", "stoptext", "f_search", "f_order", "f_more", "f_hint", "f_noteams"):
            self.setProperty(f"sport.t.{key}", sc.t(key))
        self.check_pvr()
        self.restore_preview()
        if not sc.all_cached():
            self.setProperty("sport.loadtitle", sc.t("loading_title"))
            self.setProperty("sport.loadtext", sc.t("loading_text"))
            self.setProperty("sport.loading", "1")
        self.view = "mine" if sc.has_follow() else "all"
        self.render()
        self.setFocusId(102 if self.view == "all" else 101)
        threading.Thread(target=self.background, daemon=True).start()

    def check_pvr(self):
        """Is there a TV guide? Asked again when the screen opens and when the guide has been read."""
        self.has_pvr = len(epg.channels()) > 0
        if self.has_pvr and not epg.load().get("rows"):
            text = sc.t("pvr_noepg") if epg.is_fresh() else sc.t("nochan")
        else:
            text = sc.t("nochan") if self.has_pvr else epg.diagnose()
        self.setProperty("sport.t.nochan", text)

    def onClose(self):
        self.closing = True

    def onAction(self, action):
        aid = action.getId()
        if aid in (ACTION_PREVIOUS_MENU, ACTION_NAV_BACK) and self.view == "team":
            self.view = "tables"
            self.setProperty("sport.t.title", sc.t("title"))
            self.render()
            self.setFocusId(TABLE_LIST)
            return
        if aid in (ACTION_PREVIOUS_MENU, ACTION_NAV_BACK):
            self.closing = True
            self.close()      # a channel in the TV window keeps playing until Stop channel is used
            return
        if aid == ACTION_STOP and epg.active()[0]:
            self.stop_preview()
            return
        if self.getFocusId() == LEAGUE_LIST:
            self.table_token += 1
            token = self.table_token
            threading.Timer(0.45, self.table_after, args=(token,)).start()
        elif self.getFocusId() == T_SPORTS:
            self.table_token += 1
            threading.Timer(0.45, self.sport_after, args=(self.table_token,)).start()
        if self.view in ("mine", "all"):
            self.tint()
        if self.view == "follow" and self.getFocusId() in (F_SPORTS, F_COMPS):
            self.f_token += 1
            threading.Timer(0.4, self.follow_after, args=(self.f_token, self.getFocusId())).start()

    def onClick(self, cid):
        if cid in VIEW_BUTTONS:
            if self.view == "follow" and VIEW_BUTTONS[cid] != "follow" and self.f_dirty:
                self.f_dirty = False
                threading.Thread(target=self.after_follow_change, daemon=True).start()
            self.view = VIEW_BUTTONS[cid]
            self.marks = set()
            self.setProperty("sport.t.title", sc.t("title"))
            self.render()
        elif cid in (F_SEARCH, F_ORDER, F_MORE):
            {F_SEARCH: self.search_follow, F_ORDER: self.change_order, F_MORE: self.follow_menu}[cid]()
            self.f_dirty = True
            self.render(keep_focus=True)
        elif cid == F_CHIPS:
            self.unfollow_chip()
        elif cid == F_SPORTS:
            self.setFocusId(F_COMPS)
        elif cid == F_COMPS:
            self.setFocusId(F_TEAMS if self.f_has_teams else F_BTN)
        elif cid == F_BTN:
            self.toggle_league()
        elif cid == F_TEAMS:
            self.toggle_team_card()
        elif cid in DAY_BUTTONS:
            self.day = self.anchor + datetime.timedelta(days=cid - DAY_BUTTONS[0])
            self.render()
            self.setFocusId(LIST if self.events else cid)
        elif cid == DAY_PREV:
            self.shift_days(-7)
        elif cid == DAY_NEXT:
            self.shift_days(7)
        elif cid == FIX_BUTTON:
            self.fix_channel()
        elif cid == REMIND_BUTTON:
            self.set_reminder()
        elif cid == RECORD_BUTTON:
            self.set_recording()
        elif cid == 334:
            self.stop_preview()
        elif cid in HERO_CHANNELS:
            self.preview_channel(CHANNEL_BUTTONS[cid])
        elif cid in CHANNEL_BUTTONS:
            self.preview_channel(CHANNEL_BUTTONS[cid])
        elif cid in (FOLLOW_HOME, FOLLOW_AWAY):
            self.toggle_team("home" if cid == FOLLOW_HOME else "away")
        elif cid == SHOW_TABLE:
            self.open_table()
        elif cid == T_SPORTS:
            self.setFocusId(LEAGUE_LIST)
        elif cid == LEAGUE_LIST:
            self.setFocusId(TABLE_LIST)
        elif cid == TABLE_LIST:
            self.open_team_card()
        elif cid == HERO_LIST or cid in SECTION_LISTS:
            ev, item = self.current()
            if ev and item:
                self.open_game(ev)
        elif cid == LIST:
            ev, item = self.current()
            if item and item.getProperty("hero") and item.getProperty("ch1cid"):
                self.play_channel(1)
            elif ev:
                self.open_game(ev)

    # ------------------------------------------------------------------ background work
    def status(self, text=""):
        self.setProperty("sport.status", text)

    def set_progress(self, done, total):
        self.setProperty("sport.progress", str(min(10, int(done * 10 / max(total, 1)))) if total else "")

    def background(self):
        """Fetch the games and read the IPTV guide without keeping the screen waiting."""
        first_time = not sc.all_cached()
        try:
            if first_time:
                self.setProperty("sport.loadtitle", sc.t("loading_title"))
                self.setProperty("sport.loadtext", sc.t("loading_text"))
                self.setProperty("sport.loading", "1")
            else:
                self.status(sc.t("updating"))
            if not self.has_pvr:
                self.check_pvr()

            def games_progress(done, total):
                self.set_progress(done, total)
                if first_time:
                    self.setProperty("sport.loadtext", sc.t("loading_pct", int(done * 100 / max(total, 1))))

            changed = sc.refresh(progress=games_progress)
            if sc.LAST_FAIL[0] and sc.LAST_FAIL[0] == sc.LAST_FAIL[1]:
                self.error = sc.t("neterr", sc.LAST_FAIL[2] or "?")
            elif sc.DAYFAIL[0]:
                self.error = sc.t("dayerr", sc.DAYFAIL[0], sc.DAYFAIL[1], sc.DAYFAIL[2] or "?")
            for league in {t["league"] for t in sc.load_follow()["teams"] if t.get("league") in sc.LEAGUES and t["league"] != sc.NATIONAL_LEAGUE}:
                sc.standings(league)             # for "2nd in Eredivisie"
                changed = True
            self.loaded = True
            self.setProperty("sport.loading", "")
            self.setProperty("sport.progress", "")
            self.status(self.error)
            if (changed or first_time or self.view == "mine") and not self.closing:
                self.render(keep_focus=not first_time)
            if self.has_pvr and not epg.is_fresh() and not self.closing:
                self.guide_busy = True
                last = [0]

                def progress(done, total):
                    pct = int(done * 100 / max(total, 1))
                    if pct != last[0]:
                        last[0] = pct
                        self.status(sc.t("guide", pct))
                        self.set_progress(done, total)

                self.status(sc.t("guide", 0))
                epg.scan(progress=progress, abort=lambda: self.closing)
                self.guide_busy = False
                self.check_pvr()
                if not self.closing:
                    self.render(keep_focus=True)
        except Exception as error:  # noqa: BLE001
            sc.log(f"background: {error}")
        finally:
            self.guide_busy = False
            self.loaded = True
            if not self.closing:
                self.setProperty("sport.loading", "")
                self.setProperty("sport.progress", "")
                self.status(self.error)

    # ------------------------------------------------------------------ data -> list
    def pick_events(self):
        self.follow = sc.load_follow()
        data = epg.load() if self.has_pvr else {}
        if self.view in ("mine", "team"):
            return [], data
        day_events = sc.events_on(self.day)
        live, coming, done = sc.order(day_events)
        return sorted(live + coming + done, key=lambda e: e["start"]), data

    def event_item(self, ev, data, header="", headersub=""):
        label, label2, props = self.event_props(ev, data, header, headersub)
        return listitem(label, label2, **props)

    def event_props(self, ev, data, header="", headersub=""):
        kind_event = ev["kind"] == "event"
        chans = self.channels_of(ev, data)
        best = chans[0]["name"] if chans else ""
        live = ev["state"] == "in"
        label = ev["title"] if kind_event else f"{ev['home'].get('name', '')} – {ev['away'].get('name', '')}"
        status = ev["status"] if ev["state"] != "pre" else ""
        props = {
            "time": sc.local_time(ev["start"]), "status": status, "live": "1" if live else "",
            "hname": ev["home"].get("name", ""), "aname": ev["away"].get("name", ""),
            "hrec": ev["home"].get("rec", ""), "arec": ev["away"].get("rec", ""),
            "hlogo": ev["home"].get("logo", ""), "alogo": ev["away"].get("logo", ""),
            "mid": score_text(ev), "lgicon": ev.get("lg", ""), "isevent": "1" if kind_event else "",
            "league": league_name(ev["league"]), "chan": best, "chanicon": (chans[0].get("icon") or "") if chans else "",
            "when": when_line(ev), "venue": "  ·  ".join(x for x in (ev.get("venue"), ev.get("round")) if x),
            "header": header, "headersub": headersub, "evid": ev["id"],
            "hcol": colour(ev["home"].get("color"), "66"), "acol": colour(ev["away"].get("color") or ev["away"].get("alt"), "66"),
        }
        shown = ev["state"] in ("in", "post")
        props["hscore"] = str(ev["home"].get("score", "")) if shown and not kind_event else ""
        props["ascore"] = str(ev["away"].get("score", "")) if shown and not kind_event else ""
        props["hbar"] = colour(ev["home"].get("color"))
        props["abar"] = colour(ev["away"].get("color") or ev["away"].get("alt"))
        props["herochip"] = sc.t("livenow") if live else short_when(ev)
        props["heroline"] = props["venue"]
        if kind_event and ev.get("sub") and ev["league"] != EPG_LEAGUE:
            props["when"] = f"{ev['sub']}  ·  {when_line(ev)}"
        guessed = [] if chans or ev["state"] == "post" or not data or kind_event else epg.guess_channels(ev, data)
        for n, chan in enumerate(chans or guessed, 1):
            bits = [chan["tag"]]
            if chan["q"]:
                bits.append(chan["q"])
            if chan["live"]:
                bits.insert(0, sc.t("livenow"))
            props[f"ch{n}name"] = chan["name"]
            props[f"ch{n}sub"] = "  ·  ".join(bits)
            props[f"ch{n}cid"] = chan["cid"]
            props[f"ch{n}icon"] = chan.get("icon") or ""
            props[f"ch{n}tag"] = (chan["tag"] or "").upper()
            props[f"ch{n}q"] = chan["q"] or ""
            props[f"ch{n}live"] = "1" if chan["live"] else ""
        props.update(self.plan_props(ev))
        foot = short_when(ev)
        if props.get("badge"):
            foot = f"{props['badge']}  ·  {foot}"
        props["foot"] = foot
        if not kind_event:
            for who, side in (("home", ev["home"]), ("away", ev["away"])):
                if side.get("name"):
                    followed = sc.is_following_team(self.follow, side)
                    props[f"follow{who}"] = f"✓ {side['name']}" if followed else sc.t("follow_team", side["name"])
            if ev["league"] in sc.LEAGUES:
                props["table"] = sc.t("show_table")
        return label, ev.get("sub", "") if kind_event else "", props

    def plan_props(self, ev):
        """Texts of the three action buttons and the small badge on the row."""
        out = {}
        if ev["state"] == "post" or ev["league"] == EPG_LEAGUE:
            return out
        mode = plan.reminder_mode(ev["id"])
        rec = plan.recording(ev["id"])
        out["fixtext"] = plan.t("btn_fix")
        out["remindtext"] = plan.t("btn_switch_on" if mode == "switch" else "btn_remind_on" if mode else "btn_remind")
        out["rectext"] = plan.t("btn_rec_on" if rec else "btn_rec")
        badges = [plan.t("badge_rec")] if rec else []
        if mode:
            badges.append(plan.t("badge_switch" if mode == "switch" else "badge_remind"))
        out["badge"] = "  ·  ".join(badges)
        return out

    def channels_of(self, ev, data):
        if ev["league"] == EPG_LEAGUE:
            raw = data.get("names", {}).get(str(ev.get("cid")), "")
            return [{"cid": ev["cid"], "name": epg.clean_name(raw) or raw, "q": epg.quality_of(raw), "score": 3,
                     "tag": sc.t("sure"), "live": ev["state"] == "in", "title": ev["title"], "start": ev["start"],
                     "icon": data.get("icons", {}).get(str(ev.get("cid")), "")}]
        found = epg.channels_for(ev, data) if data else []
        return plan.with_fixes(ev, found, data or {})

    def render(self, keep_focus=False):
        self.setProperty("sport.view", self.view)
        for name in ("mine", "all", "tables"):
            self.setProperty(f"sport.is.{name}", "1" if name == self.view else "")
        if self.view == "tables":
            self.setProperty("sport.empty", "")
            self.fill_leagues()
            return
        if self.view == "follow":
            self.setProperty("sport.empty", "")
            self.fill_follow(keep_focus)
            return
        events, data = self.pick_events()
        self.hero_events = []
        if self.view == "team":
            self.setProperty("sport.t.title", self.team_name)
            self.events = self.team_events
            self.by_id = {e["id"]: e for e in self.team_events}
            items = [self.event_item(ev, data) for ev in self.team_events]
        elif self.view == "mine":
            self.fill_mine(data, keep_focus)
            self.getControl(LIST).reset()
            self.fill_days()
            if self.hero_events or self.sections_shown:
                self.setProperty("sport.empty", "")
            else:
                self.empty_state()
            return
        else:
            self.events = events
            self.by_id = {e["id"]: e for e in events}
            items = [self.event_item(ev, data) for ev in events]
            self.setProperty("sport.listtitle", nice_day(self.day).upper() if abs((self.day - ac.today()).days) <= 1 else ac.day_long(self.day).upper())
            self.setProperty("sport.listcount", sc.t("list_n", len(events)) if events else "")
        self.setProperty("sport.hashero", "1" if self.hero_events else "")
        control = self.getControl(LIST)
        position = control.getSelectedPosition() if keep_focus else 0
        control.reset()
        control.addItems(items)
        if items:
            control.selectItem(min(max(position, 0), len(items) - 1))
        self.fill_days()
        if items:
            self.setProperty("sport.empty", "")
        else:
            self.empty_state()

    def mine_data(self, data):
        """Hero games and one block per team / competition / name you follow (your order): ([events], [section dicts])."""
        follow = self.follow
        today = ac.today()
        by_id = {}

        def local_ok(e):
            return sc.local_day(e["start"]) >= today - datetime.timedelta(days=1)

        rows = []
        for key, kind, ident, title in sc.sections(follow):
            logo = ""
            if kind == "team":
                team = next((t for t in follow["teams"] if sc.team_ident(t) == ident), {"id": ident, "name": title})
                events, sub, logo = sc.events_of_team(ident, title), sc.place_text(team), team.get("logo", "")
            elif kind == "league":
                events, sub = [e for e in sc.all_cached() if e["league"] == ident], ""
            else:
                events, sub = name_events({"names": [ident]}, data), sc.t("tvguide")
            live = [e for e in events if e["state"] == "in"]
            coming = sorted((e for e in events if e["state"] == "pre"), key=lambda e: e["start"])
            done = sorted((e for e in events if e["state"] == "post" and local_ok(e)), key=lambda e: -e["start"])
            shown = sorted(live + coming[:4] + done[:1],
                           key=lambda e: (e["state"] != "in", e["state"] == "post", e["start"] if e["state"] != "post" else -e["start"]))
            if not logo and shown:
                logo = shown[0].get("lg", "")
            rows.append({"title": title, "sub": sub, "logo": logo, "events": shown, "kind": kind})
        everything = {}
        for row in rows:
            for e in row["events"]:
                everything[e["id"]] = e
        live_all = sorted((e for e in everything.values() if e["state"] == "in"), key=lambda e: e["start"])
        coming_all = sorted((e for e in everything.values() if e["state"] == "pre"), key=lambda e: e["start"])
        # the big card is only for your favourites: games of followed teams (and names); no favourites -> no big card
        fav = {}
        for row in rows:
            if row["kind"] in ("team", "name"):
                for e in row["events"]:
                    fav[e["id"]] = e
        pool = [e for e in live_all + coming_all if e["id"] in fav]
        hero = pool[:HERO_MAX]
        sections = []
        if live_all or coming_all:
            sections.append({"title": sc.t("liveup"), "sub": f"{len(live_all)} live" if live_all else "", "logo": SPORT_ICON,
                             "events": (live_all + coming_all)[:8]})
        sections += rows                      # followed teams show up even without games (and without IPTV)
        for sec in sections:
            for e in sec["events"]:
                by_id[e["id"]] = e
        for e in hero:
            by_id[e["id"]] = e
        self.by_id = by_id
        self.events = list(by_id.values())
        return hero, sections

    def fill_mine(self, data, keep_focus=False):
        hero, sections = self.mine_data(data)
        self.hero_events = hero
        keep = {}
        if keep_focus:
            for cid in (HERO_LIST,) + SECTION_LISTS:
                try:
                    keep[cid] = self.getControl(cid).getSelectedPosition()
                except Exception:  # noqa: BLE001
                    keep[cid] = 0
        self.setProperty("sport.hashero", "1" if hero else "")
        items = []
        for n, ev in enumerate(hero, 1):
            label, label2, props = self.event_props(ev, data)
            props["heroof"] = f"{n} / {len(hero)}"
            items.append(listitem(label, label2, **props))
        self.fill_list(HERO_LIST, items, keep.get(HERO_LIST, 0))
        self.sections_shown = min(len(sections), len(SECTION_LISTS))
        for k, cid in enumerate(SECTION_LISTS):
            if k < len(sections):
                sec = sections[k]
                evs = sec["events"]
                self.setProperty(f"sport.sec{k + 1}.title", sec["title"])
                self.setProperty(f"sport.sec{k + 1}.sub", sec["sub"])
                self.setProperty(f"sport.sec{k + 1}.logo", sec["logo"] or SPORT_ICON)
                self.setProperty(f"sport.sec{k + 1}.count", sc.t("n_games", len(evs)) if evs else "")
                self.setProperty(f"sport.sec{k + 1}.on", "1")
                cards = [self.event_item(ev, data) for ev in evs]
                if not cards:
                    cards = [listitem(sc.t("nogames"), "", isevent="1", league=sec["title"], lgicon=sec["logo"], foot="", hcol="66" + "3A4A5C", acol="66" + "3A4A5C")]
                self.fill_list(cid, cards, keep.get(cid, 0))
            else:
                self.setProperty(f"sport.sec{k + 1}.on", "")
                self.fill_list(cid, [], 0)
        self.last_tint = None
        self.tint()

    def fill_list(self, cid, items, position=0):
        control = self.getControl(cid)
        control.reset()
        control.addItems(items)
        if items:
            control.selectItem(min(max(position, 0), len(items) - 1))

    def tint(self):
        """The background takes the colours of the game you are looking at."""
        fid = self.getFocusId()
        cid = HERO_LIST if fid in HERO_CHANNELS else fid
        if self.view == "all":
            cid = LIST
        elif cid != HERO_LIST and cid not in SECTION_LISTS:
            if not self.getProperty("sport.bgA") and self.hero_events:
                cid = HERO_LIST
            else:
                return
        try:
            item = self.getControl(cid).getSelectedItem()
        except Exception:  # noqa: BLE001
            return
        if not item:
            return
        pair = (item.getProperty("hcol"), item.getProperty("acol"))
        if pair != self.last_tint:
            self.last_tint = pair
            self.setProperty("sport.bgA", pair[0])
            self.setProperty("sport.bgB", pair[1])


    # ------------------------------------------------------------------ game page
    def game_layout(self, ev):
        if ev["kind"] == "teams":
            return "teams"
        return "race" if ev["league"] in sc.LEAGUES and sc.LEAGUES[ev["league"]]["sport"] == "racing" else "event"

    def countdown(self, ev):
        if ev["state"] == "in":
            return ev.get("status") or "LIVE"
        if ev["state"] == "post":
            return sc.t("g_over")
        left = int(ev["start"] - time.time())
        if left <= 0:
            return ""
        days, hours, mins = left // 86400, left % 86400 // 3600, left % 3600 // 60
        if days:
            return sc.t("g_in_dh", days, hours)
        return sc.t("g_in_h", hours, mins) if hours else sc.t("g_in_m", mins)

    def progress(self, ev):
        """0..10 for the bar under LIVE: minute / 90 (HT = 5, finished = 10)."""
        if ev["state"] == "post":
            return 10
        if ev["state"] != "in":
            return 0
        text = (ev.get("status") or "").upper()
        if text.startswith("HT") or "HALF" in text:
            return 5
        m = re.match(r"\s*(\d+)", text)
        return max(1, min(10, round(int(m.group(1)) / 9))) if m else 1

    def game_props(self, ev):
        data = epg.load() if self.has_pvr else {}
        label, label2, props = self.event_props(ev, data)
        d = sc.local_day(ev["start"])
        props.update(label=label, label2=label2, layout=self.game_layout(ev), dayshort=ac.day_short(d).upper(),
                     clock=sc.local_time(ev["start"]), countdown=self.countdown(ev),
                     crumb=f"‹ {sc.t('title')}     {props['league']}" + (f"  ·  {props['venue']}" if props["venue"] else ""))
        if ev["kind"] == "teams":
            props["hsub"] = props["asub"] = ""
            props["info1"] = ev.get("venue", "")
            props["info2"] = ev.get("round", "")
            props["prog"] = str(self.progress(ev))
            props["score"] = (f"{props['hscore']} – {props['ascore']}" if props.get("hscore") != "" and props.get("ascore") != "" and ev["state"] in ("in", "post") else "")
        else:
            props["info1"] = ev.get("venue", "")
            props["info2"] = ev.get("round", "")
        if props["layout"] == "race":
            mates = sorted((e for e in sc.all_cached() if e["league"] == ev["league"] and e["kind"] == "event" and e["title"] == ev["title"]),
                           key=lambda e: e["start"])[:6]
            for n, e in enumerate(mates, 1):
                props[f"s{n}name"] = e.get("sub") or e["title"]
                props[f"s{n}when"] = f"{ac.day_short(sc.local_day(e['start']))}  {sc.local_time(e['start'])}"
                props[f"s{n}now"] = "1" if e["id"] == ev["id"] else ""
        return props

    def game_extra(self, ev):
        """Slow part (form, standings): returns {name: value} for the page, filled in once it is ready."""
        out = {}
        if ev["kind"] != "teams" or ev["league"] not in sc.LEAGUES:
            return out
        key = ev["league"]
        marks = {s.get("id") for s in (ev["home"], ev["away"]) if s.get("id")}
        try:
            for side, who in (("h", "home"), ("a", "away")):
                team = ev[who]
                card = sc.team_card(key, team.get("id", ""), team.get("name", ""))
                row = card["row"]
                rec = "-".join(str(x) for x in (row.get("w"), row.get("d"), row.get("l")) if x not in ("", None))
                out[f"{side}sub"] = "  ·  ".join(x for x in (rec, sc.t("g_home" if who == "home" else "g_away")) if x)
                if row.get("rank"):
                    out[f"{side}place"] = f"{row['rank']}e" if sc.NL else str(row["rank"])
                for n in range(5):
                    letter = card["recent"][n][1][0] if n < len(card["recent"]) else ""
                    out[f"{side}f{n + 1}"] = LETTERS.get(letter, letter)
                    out[f"{side}fc{n + 1}"] = sc.FORM_COLOURS.get(letter, "")
            rows = [r for r in sc.table_rows(key, marks) if r.get("id")]
            keep = set(range(min(2, len(rows))))
            for i, r in enumerate(rows):
                if r["id"] in marks:
                    keep |= {i - 1, i, i + 1}
            picked = [rows[i] for i in sorted(keep) if 0 <= i < len(rows)][:7]
            for n, r in enumerate(picked, 1):
                out[f"t{n}rank"], out[f"t{n}team"] = str(r.get("rank", "")), r.get("team", "")
                out[f"t{n}gp"], out[f"t{n}gd"], out[f"t{n}pts"] = str(r.get("gp", "")), str(r.get("gd", "")), str(r.get("pts", ""))
                out[f"t{n}mine"] = "1" if r["id"] in marks else ""
            if picked:
                out["tabletitle"] = sc.t("g_standings", league_name(key).upper())
        except Exception as error:  # noqa: BLE001
            sc.log(f"game_extra: {error}")
        return out

    def game_detail(self, ev):
        try:
            return sc.match_detail(ev) if ev["kind"] == "teams" else {}
        except Exception as error:  # noqa: BLE001
            sc.log(f"match_detail: {error}")
            return {}

    def open_game(self, ev):
        while True:
            props = self.game_props(ev)
            window = GameInfo("Lucent_SportGame.xml", self.path(), "Default", "1080i")
            window.setup(ev, props, self)
            window.doModal()
            result = window.result
            del window
            if result.startswith("play"):
                cid = props.get(f"ch{result[4:]}cid")
                if cid:
                    self.closing = True
                    self.close()
                    epg.play(cid)
                return
            if result == "table":
                self.open_table(ev)
                return
            if result == "remind":
                self.remind_event(ev)
            elif result == "record":
                self.set_recording(ev)
            elif result == "fix":
                self.fix_channel(ev)
            elif result == "done":
                return
            elif result in ("home", "away"):
                if self.club_popup(ev, result):
                    return
            else:
                self.render(keep_focus=True)
                return

    def game_menu(self, ev, item):
        """OK on a game: watch on a channel, remind, record, fix the channel, follow a team, show the table."""
        options, actions = [], []
        for n in range(1, 5):
            if item.getProperty(f"ch{n}cid"):
                options.append(f"{sc.t('play_on')} {item.getProperty(f'ch{n}name')}  ·  {item.getProperty(f'ch{n}sub')}")
                actions.append(("play", n))
        if item.getProperty("remindtext"):
            options += [item.getProperty("remindtext"), item.getProperty("rectext"), item.getProperty("fixtext")]
            actions += [("remind", 0), ("record", 0), ("fix", 0)]
        for who in ("home", "away"):
            if item.getProperty(f"follow{who}"):
                options.append(item.getProperty(f"follow{who}"))
                actions.append((who, 0))
        if item.getProperty("table"):
            options.append(item.getProperty("table"))
            actions.append(("table", 0))
        if not options:
            return
        title = item.getLabel() if ev["kind"] == "event" else f"{item.getLabel()}  ·  {item.getProperty('when')}"
        pick = xbmcgui.Dialog().select(title, options)
        if pick < 0:
            return
        action, n = actions[pick]
        if action == "play":
            self.play_channel(n, item)
        elif action == "remind":
            self.remind_event(ev)
        elif action == "record":
            self.set_recording(ev)
        elif action == "fix":
            self.fix_channel(ev)
        elif action in ("home", "away"):
            self.toggle_team(action, ev)
        elif action == "table":
            self.open_table(ev)


    # ------------------------------------------------------------------ Follow page
    def sport_of_team(self, team):
        league = team.get("league")
        if league == sc.NATIONAL_LEAGUE:
            return "soccer"
        return sc.LEAGUES[league]["sport"] if league in sc.LEAGUES else ""

    def fill_follow(self, keep_focus=False):
        self.fill_chips()
        self.fill_sports()
        self.fill_comps()

    def fill_chips(self):
        follow = sc.load_follow()
        chips = []
        for key, kind, ident, title in sc.sections(follow):
            logo = ""
            if kind == "team":
                logo = next((t.get("logo", "") for t in follow["teams"] if sc.team_ident(t) == ident), "")
            chips.append(listitem(title, "", icon=logo, key=key, kind=kind, ident=ident))
        self.setProperty("sport.f.has", "1" if chips else "")
        self.setProperty("sport.f.count", sc.t("f_following", len(chips)))
        pos = self.getControl(F_CHIPS).getSelectedPosition()
        self.fill_list(F_CHIPS, chips, pos)

    def fill_sports(self):
        follow = sc.load_follow()
        sports = [sp for sp in SPORT_ORDER if any(v["sport"] == sp for v in sc.LEAGUES.values())]
        sports += sorted({v["sport"] for v in sc.LEAGUES.values()} - set(sports))
        items = []
        for sp in sports:
            n = (sum(1 for k in follow["leagues"] if k in sc.LEAGUES and sc.LEAGUES[k]["sport"] == sp)
                 + sum(1 for t in follow["teams"] if self.sport_of_team(t) == sp)
                 + (len(follow["names"]) if sp == "racing" else 0))
            items.append(listitem(sc.sport_name(sp), "", icon=sport_icon(sp), sport=sp, badge=str(n) if n else ""))
        self.f_sports = sports
        self.fill_list(F_SPORTS, items, sports.index(self.f_sport) if self.f_sport in sports else 0)

    def comp_keys(self):
        keys = [k for k, v in sc.LEAGUES.items() if v["sport"] == self.f_sport]
        first = ("ned.1", "ned.2", "ned.cup", "bel.1") if sc.NL else ("eng.1", "esp.1", "ger.1", "ita.1")
        return sorted(keys, key=lambda k: (first.index(k) if k in first else 9, not sc.LEAGUES[k]["default"], sc.LEAGUES[k]["name"]))

    def fill_comps(self, reload=True):
        follow = sc.load_follow()
        keys = self.comp_keys()
        items = []
        for k in keys:
            lg = sc.LEAGUES[k]
            sub = sc.t("f_followed") if k in follow["leagues"] else (sc.t("f_teams") if lg["kind"] == "teams" else sc.t("f_competition"))
            items.append(listitem(lg["name"], sub, icon=sport_icon(lg["sport"]), key=k, followed="1" if k in follow["leagues"] else ""))
        if self.f_league not in keys:
            self.f_league = keys[0] if keys else ""
        self.fill_list(F_COMPS, items, keys.index(self.f_league) if self.f_league in keys else 0)
        if reload:
            self.show_league()
        else:
            self.set_follow_button()

    def show_league(self):
        key = self.f_league
        if not key:
            return
        self.set_follow_button()
        self.f_has_teams = False
        self.setProperty("sport.f.noteams", "")
        threading.Thread(target=self.load_teams, args=(key, self.f_token), daemon=True).start()

    def set_follow_button(self):
        key = self.f_league
        if key:
            name = sc.LEAGUES[key]["name"]
            self.setProperty("sport.f.btn", sc.t("f_stop", name) if key in sc.load_follow()["leagues"] else sc.t("f_follow", name))

    def load_teams(self, key, token):
        """Teams of a competition as colour cards (alphabetical). Fetches when ESPN has not been asked yet."""
        try:
            lg = sc.LEAGUES[key]
            if lg["kind"] != "teams":
                self.fill_list(F_TEAMS, [], 0)
                self.setProperty("sport.f.noteams", "1")
                return
            teams = sc.teams_of(key)
            if not teams and not sc.load_cache()["leagues"].get(key):
                sc.refresh(keys=[key])
                teams = sc.teams_of(key)
            if key != self.f_league or self.closing:
                return
            follow = sc.load_follow()
            colours = sc.colour_map()
            items = []
            for tid, name, logo in teams:
                mine = sc.is_following_team(follow, {"id": tid, "name": name})
                base = colours.get(tid, "FF3A4A5C")
                items.append(listitem(name, "", icon=logo, tid=tid, logo=logo, mine="1" if mine else "",
                                      tcol="99" + base[2:], tcol2="22" + base[2:]))
            self.f_teams = teams
            self.f_has_teams = bool(items)
            self.setProperty("sport.f.noteams", "" if items else "1")
            self.fill_list(F_TEAMS, items, 0)
        except Exception as error:  # noqa: BLE001
            sc.log(f"load_teams {key}: {error}")

    def follow_after(self, token, focus):
        if token != self.f_token or self.closing or self.view != "follow":
            return
        if focus == F_SPORTS:
            item = self.getControl(F_SPORTS).getSelectedItem()
            if item and item.getProperty("sport") != self.f_sport:
                self.f_sport = item.getProperty("sport")
                self.f_league = ""
                self.fill_comps()
        elif focus == F_COMPS:
            item = self.getControl(F_COMPS).getSelectedItem()
            if item and item.getProperty("key") != self.f_league:
                self.f_league = item.getProperty("key")
                self.show_league()

    def toggle_league(self):
        key = self.f_league
        if not key:
            return
        follow = sc.load_follow()
        if key in follow["leagues"]:
            follow["leagues"].remove(key)
        else:
            follow["leagues"].append(key)
        sc.save_follow(follow)
        self.f_dirty = True
        self.refresh_follow_lists()

    def toggle_team_card(self):
        item = self.getControl(F_TEAMS).getSelectedItem()
        if not item or not self.f_league:
            return
        side_ = {"id": item.getProperty("tid"), "name": item.getLabel(), "logo": item.getProperty("logo")}
        followed = sc.toggle_team(self.f_league, side_)
        item.setProperty("mine", "1" if followed else "")
        xbmcgui.Dialog().notification(sc.t("title"), sc.t("follow_team" if followed else "unfollow_team", side_["name"]),
                                      xbmcgui.NOTIFICATION_INFO, 2000, False)
        self.f_dirty = True
        self.refresh_follow_lists()

    def unfollow_chip(self):
        item = self.getControl(F_CHIPS).getSelectedItem()
        if not item:
            return
        kind, ident = item.getProperty("kind"), item.getProperty("ident")
        follow = sc.load_follow()
        if kind == "team":
            follow["teams"] = [t for t in follow["teams"] if sc.team_ident(t) != ident]
        elif kind == "league":
            follow["leagues"] = [k for k in follow["leagues"] if k != ident]
        else:
            follow["names"] = [n for n in follow["names"] if n != ident]
        sc.save_follow(follow)
        self.f_dirty = True
        self.refresh_follow_lists()
        self.fill_teams_marks()

    def fill_teams_marks(self):
        follow = sc.load_follow()
        control = self.getControl(F_TEAMS)
        for i in range(control.size()):
            it = control.getListItem(i)
            it.setProperty("mine", "1" if sc.is_following_team(follow, {"id": it.getProperty("tid"), "name": it.getLabel()}) else "")

    def refresh_follow_lists(self):
        """Redraw the strip, the badges and the follow button without losing your place."""
        self.fill_chips()
        pos = self.getControl(F_SPORTS).getSelectedPosition()
        self.fill_sports()
        self.getControl(F_SPORTS).selectItem(pos)
        pos = self.getControl(F_COMPS).getSelectedPosition()
        self.fill_comps(reload=False)
        self.getControl(F_COMPS).selectItem(pos)

    def empty_state(self):
        if self.view == "mine" and not sc.has_follow():
            title, text = sc.t("empty_title"), sc.t("empty_mine")
        elif self.view == "mine":
            title, text = sc.t("empty_day"), ""
        elif not sc.all_cached():
            title, text = sc.t("empty_title"), sc.t("empty_net") if not self.ready else sc.t("loading")
        else:
            title, text = sc.t("empty_day"), ""
        self.setProperty("sport.empty.title", title)
        self.setProperty("sport.empty.text", text)
        self.setProperty("sport.empty", "1")

    def fill_days(self):
        self.setProperty("sport.hasdays", "1" if self.view == "all" else "")
        for n in range(7):
            d = self.anchor + datetime.timedelta(days=n)
            name = nice_day(d) if abs((d - ac.today()).days) <= 1 else ac.day_short(d)
            self.setProperty(f"sport.day{n + 1}.name", name)
            self.setProperty(f"sport.day{n + 1}.sel", "1" if d == self.day else "")

    def shift_days(self, step):
        low, high = ac.today() - datetime.timedelta(days=sc.DAYS_BACK), ac.today() + datetime.timedelta(days=sc.DAYS_AHEAD - 6)
        self.anchor = min(max(self.anchor + datetime.timedelta(days=step), low), high)
        if not self.anchor <= self.day <= self.anchor + datetime.timedelta(days=6):
            self.day = self.anchor
        self.render()

    # ------------------------------------------------------------------ item actions
    def focus_list(self):
        fid = self.getFocusId()
        if fid in SECTION_LISTS or fid == HERO_LIST:
            return fid
        if fid in HERO_CHANNELS:
            return HERO_LIST
        return LIST

    def current(self):
        item = self.getControl(self.focus_list()).getSelectedItem()
        if not item:
            return None, None
        return self.by_id.get(item.getProperty("evid")), item

    def preview_channel(self, n):
        """OK on a channel next to the big card: watch it in the small window; OK on the same channel again: full screen."""
        item = self.current()[1]
        cid = item.getProperty(f"ch{n}cid") if item else ""
        if not cid:
            return
        if epg.active()[0] == str(cid):
            epg.fullscreen()
            return
        name = item.getProperty(f"ch{n}name")
        epg.set_active(cid, name)
        self.setProperty("sport.preview", str(cid))
        self.setProperty("sport.preview.name", name)
        threading.Thread(target=self.start_preview, args=(cid,), daemon=True).start()

    def restore_preview(self):
        cid, name = epg.active()
        self.setProperty("sport.preview", cid)
        self.setProperty("sport.preview.name", name)

    def stop_preview(self):
        epg.stop()
        self.setProperty("sport.preview", "")
        self.setProperty("sport.preview.name", "")

    def start_preview(self, cid):
        """Start the channel behind this page (windowed). When Kodi cannot do that, play it and come back to this page."""
        path = epg.channel_path(cid)
        if path:
            xbmc.Player().play(path, windowed=True)
            return
        if epg.play_windowed(cid):
            return
        wid = xbmcgui.getCurrentWindowId()
        epg.play(cid)
        for _ in range(50):
            time.sleep(0.2)
            if xbmc.getCondVisibility("Player.HasVideo"):
                time.sleep(0.5)
                if not self.closing:
                    xbmc.executebuiltin(f"ActivateWindow({wid})")
                return

    def play_channel(self, n, item=None):
        item = item or self.current()[1]
        if not item:
            return
        cid = item.getProperty(f"ch{n}cid")
        if cid:
            self.closing = True
            self.close()
            epg.play(cid)

    def toggle_team(self, who, ev=None):
        ev = ev or self.current()[0]
        if not ev or ev["kind"] != "teams":
            return
        side = ev[who]
        followed = sc.toggle_team(ev["league"], side)
        xbmcgui.Dialog().notification(sc.t("title"), sc.t("follow_team" if followed else "unfollow_team", side["name"]),
                                      xbmcgui.NOTIFICATION_INFO, 2500, False)
        self.render(keep_focus=True)

    def fix_channel(self, ev=None):
        ev = ev or self.current()[0]
        if not ev:
            return
        dialog = xbmcgui.Dialog()
        chans = plan.all_channels()
        if not chans:
            dialog.notification(sc.t("title"), sc.t("noguide"), xbmcgui.NOTIFICATION_INFO, 3000, False)
            return
        options = ([plan.t("fix_clear")] if plan.fixed_cids(ev) else []) + [label for _cid, label in chans]
        pick = dialog.select(plan.t("fix_pick"), options)
        if pick < 0:
            return
        if plan.fixed_cids(ev) and pick == 0:
            plan.clear_fix_game(ev)
            self.render(keep_focus=True)
            return
        cid = chans[pick - (1 if plan.fixed_cids(ev) else 0)][0]
        scopes = [("game", plan.t("fix_game")), ("league", plan.t("fix_league", league_name(ev["league"])))]
        team_ident = ""
        if ev["kind"] == "teams":
            follow = sc.load_follow()
            mine = next((s for s in (ev["home"], ev["away"]) if sc.is_following_team(follow, s)), ev["home"])
            team_ident = mine.get("id") or mine.get("name")
            scopes.append(("team", plan.t("fix_team", mine.get("name", ""))))
        sel = dialog.select(plan.t("fix_scope"), [label for _k, label in scopes])
        if sel < 0:
            return
        plan.set_fix(ev, scopes[sel][0], cid, team_ident)
        self.render(keep_focus=True)

    def set_reminder(self):
        self.remind_event(self.current()[0])

    def remind_event(self, ev):
        if not ev or ev["state"] == "post":
            return
        modes = [("", plan.t("r_off")), ("remind", plan.t("r_remind")), ("switch", plan.t("r_switch"))]
        current = plan.reminder_mode(ev["id"])
        pick = xbmcgui.Dialog().select(plan.t("r_title"), [label for _m, label in modes],
                                       preselect=[m for m, _l in modes].index(current))
        if pick < 0:
            return
        data = epg.load() if self.has_pvr else {}
        chans = self.channels_of(ev, data)
        plan.set_reminder(ev, modes[pick][0], chans[0]["cid"] if chans else 0)
        self.render(keep_focus=True)

    def set_recording(self, ev=None):
        ev = ev or self.current()[0]
        if not ev or ev["state"] == "post":
            return
        dialog = xbmcgui.Dialog()
        if plan.recording(ev["id"]):
            if dialog.yesno(plan.t("btn_rec_on"), plan.t("rec_cancel"), nolabel=sc.t("q_cancel"), yeslabel=plan.t("rec_cancel")):
                plan.cancel_recording(ev["id"])
                self.render(keep_focus=True)
            return
        data = epg.load() if self.has_pvr else {}
        chans = self.channels_of(ev, data)
        if not chans:
            dialog.notification(sc.t("title"), plan.t("rec_nochan"), xbmcgui.NOTIFICATION_INFO, 3500, False)
            return
        cid = chans[0]["cid"]
        if len(chans) > 1:
            pick = dialog.select(sc.t("watch"), [f"{c['name']}  ·  {c['tag']}" for c in chans])
            if pick < 0:
                return
            cid = chans[pick]["cid"]
        hours = [1, 2, 3, 4, 5, 6]
        h = dialog.select(plan.t("rec_hours"), [plan.t("rec_hour") if n == 1 else plan.t("rec_hours_n", n) for n in hours],
                          preselect=2)
        if h < 0:
            return
        plan.set_recording(ev, cid, hours[h])
        self.render(keep_focus=True)

    def open_table(self, ev=None):
        ev = ev or self.current()[0]
        if not ev or ev["league"] not in sc.LEAGUES:
            return
        self.table_key = ev["league"]
        self.marks = {s.get("id") for s in (ev["home"], ev["away"]) if s.get("id")} if ev["kind"] == "teams" else set()
        self.view = "tables"
        self.render()
        self.setFocusId(TABLE_LIST)

    # ------------------------------------------------------------------ tables
    def table_sports(self):
        sports = []
        for k, v in sc.LEAGUES.items():
            if v["kind"] == "teams" and v["sport"] not in sports:
                sports.append(v["sport"])
        order = {s: i for i, s in enumerate(SPORT_ORDER)}
        sports.sort(key=lambda s: order.get(s, 99))
        return sports

    def fill_leagues(self, keep_sport=False):
        sports = self.table_sports()
        if not keep_sport or getattr(self, "t_sport", None) not in sports:
            current = sc.LEAGUES.get(self.table_key, {}).get("sport")
            self.t_sport = current if current in sports else (sports[0] if sports else "soccer")
        if not keep_sport:                      # the sport buttons stay as they are while you move along them
            chips = self.getControl(T_SPORTS)
            chips.reset()
            chips.addItems([listitem(sc.sport_name(s), sport=s) for s in sports])
            chips.selectItem(sports.index(self.t_sport) if self.t_sport in sports else 0)
            self.t_sports_shown = sports
        keys = [k for k, v in sc.LEAGUES.items() if v["kind"] == "teams" and v["sport"] == self.t_sport]
        active, position = set(sc.league_keys()), {k: i for i, k in enumerate(sc.LEAGUES)}
        keys.sort(key=lambda k: (k not in self.follow["leagues"], k not in active, position[k]))
        control = self.getControl(LEAGUE_LIST)
        control.reset()
        control.addItems([listitem(sc.LEAGUES[k]["name"], key=k) for k in keys])
        self.league_keys_shown = keys
        index = keys.index(self.table_key) if self.table_key in keys else 0
        control.selectItem(index)
        self.table_key = keys[index] if keys else ""
        self.table_pos = index
        if keys:
            self.load_table(self.table_key)
        else:
            self.getControl(TABLE_LIST).reset()

    def sport_after(self, token):
        if token != self.table_token or self.closing:
            return
        try:
            pos = self.getControl(T_SPORTS).getSelectedPosition()
        except Exception:  # noqa: BLE001
            return
        shown = getattr(self, "t_sports_shown", [])
        if 0 <= pos < len(shown) and shown[pos] != self.t_sport:
            self.t_sport = shown[pos]
            self.marks = set()
            self.table_key = ""
            self.fill_leagues(keep_sport=True)

    def table_after(self, token):
        if token != self.table_token or self.closing:
            return
        try:
            pos = self.getControl(LEAGUE_LIST).getSelectedPosition()
        except Exception:  # noqa: BLE001
            return
        if pos != self.table_pos and 0 <= pos < len(self.league_keys_shown):
            self.table_pos = pos
            self.marks = set()
            self.table_key = self.league_keys_shown[pos]
            self.load_table(self.table_key)

    def load_table(self, key):
        try:
            rows = sc.table_rows(key, self.marks)
        except Exception as error:  # noqa: BLE001 - the extras (form, colours) must never hide the table itself
            sc.log(f"table {key}: {error}")
            try:
                rows = [dict(r, form=[], teamcol="", chg=0, edge="", mine=False) for r in sc.standings(key)]
            except Exception as error2:  # noqa: BLE001
                sc.log(f"table {key} (standings): {error2}")
                rows = []
        control = self.getControl(TABLE_LIST)
        control.reset()
        items = []
        for row in rows:
            if "header" in row:
                items.append(listitem(row["header"], header=row["header"]))
                continue
            props = {"rank": row.get("rank", ""), "gp": row.get("gp", ""), "gd": row.get("gd", ""), "pts": row.get("pts", ""),
                     "teamid": row.get("id", ""), "edge": row.get("edge", ""), "mine": "1" if row.get("mine") else "",
                     "ring": ("66" + row["teamcol"][2:]) if row.get("teamcol") else ""}
            chg = row.get("chg", 0)
            props["chg"] = f"▲{chg}" if chg > 0 else f"▼{-chg}" if chg < 0 else ""
            props["chgcol"] = "FF3FB950" if chg > 0 else "FFE5534B"
            for n in range(5):
                letter = row["form"][n] if n < len(row.get("form", [])) else ""
                props[f"f{n + 1}"] = letter
                props[f"f{n + 1}c"] = sc.FORM_COLOURS.get(letter, "")
            items.append(listitem(row.get("team", ""), icon=row.get("logo", ""), **props))
        control.addItems(items)
        self.setProperty("sport.notable", "" if items else "1")
        for n, (col, text) in enumerate(sc.legend(rows), 1):
            self.setProperty(f"sport.leg{n}.col", col)
            self.setProperty(f"sport.leg{n}.text", text)
        for n in range(len(sc.legend(rows)) + 1, 5):
            self.setProperty(f"sport.leg{n}.col", "")
            self.setProperty(f"sport.leg{n}.text", "")

    def open_team_card(self):
        item = self.getControl(TABLE_LIST).getSelectedItem()
        if not item or item.getProperty("header") or not item.getProperty("teamid"):
            return
        logo = item.getArt("icon") if hasattr(item, "getArt") else ""
        self.show_team_card(self.table_key, item.getProperty("teamid"), item.getLabel(), logo)

    def show_team_card(self, key, team_id, name, logo):
        """The team card. Returns True when it moved on (played a channel or opened the team's games)."""
        card = sc.team_card(key, team_id, name)
        data = epg.load() if self.has_pvr else {}
        chans = self.channels_of(card["next"], data) if card["next"] else []
        window = TeamCard("Lucent_SportTeam.xml", self.path(), "Default", "1080i")
        window.setup(key, team_id, name, logo, card, chans, sc.is_following_team(sc.load_follow(), {"id": team_id, "name": name}))
        window.doModal()
        result = window.result
        del window
        if result == "watch" and chans:
            self.closing = True
            self.close()
            epg.play(chans[0]["cid"])
            return True
        elif result == "remind" and card["next"]:
            self.by_id[card["next"]["id"]] = card["next"]
            self.remind_event(card["next"])
        elif result == "follow":
            sc.toggle_team(key, {"id": team_id, "name": name, "logo": logo})
            if self.view == "tables":
                self.load_table(self.table_key)
        elif result == "games":
            self.show_team_games(name, card)
            return True
        return False

    def show_team_games(self, name, card):
        self.team_name = name
        self.team_events = card["games"] + [e for e, _r in card["recent"]]
        self.view = "team"
        self.render()
        self.setFocusId(LIST)

    def club_popup(self, ev, who):
        """Click on a club on the game page: now / last / next game, Watch now, Follow, All their games, Team info.
        Returns True when the game page should not come back."""
        side = ev[who]
        key, team_id, name = ev["league"], side.get("id", ""), side.get("name", "")
        card = sc.team_card(key, team_id, name)
        data = epg.load() if self.has_pvr else {}
        live = next((e for e in card["games"] if e["state"] == "in"), ev if ev["state"] == "in" else None)
        nxt = next((e for e in card["games"] if e["state"] == "pre"), None)
        watch_ev = live or nxt
        chans = self.channels_of(watch_ev, data) if watch_ev else []
        followed = sc.is_following_team(sc.load_follow(), {"id": team_id, "name": name})

        def vs(game):
            mine_home = (team_id and game["home"].get("id") == team_id) or sc.norm(game["home"].get("name")) == sc.norm(name)
            other = game["away" if mine_home else "home"]
            return ("vs " if mine_home else "@ ") + other.get("name", "")

        info = {"name": name, "logo": side.get("logo", ""), "sub": sc.league_name_of(key),
                "col": colour_of(side), "followtext": sc.t("unfollow_team" if followed else "follow_team", name),
                "now": f"{vs(live)}  ·  {live.get('status') or 'LIVE'}" if live else "",
                "nowscore": f"{live['home'].get('score', '')}–{live['away'].get('score', '')}" if live else "",
                "last": "", "lastscore": "", "lastc": "", "lastl": "",
                "next": f"{vs(nxt)}  ·  {when_line(nxt)}" if nxt else sc.t("c_nonext"),
                "nextchan": f"{chans[0]['name']}  ·  {chans[0]['tag']}" if chans else "",
                "canwatch": "1" if chans else ""}
        if card["recent"]:
            last, (letter, score, _opp, _home) = card["recent"][0]
            info.update(last=f"{vs(last)}  ·  {ac.day_short(sc.local_day(last['start']))}", lastscore=score,
                        lastc=sc.FORM_COLOURS.get(letter, ""), lastl=LETTERS.get(letter, letter))
        window = ClubPopup("Lucent_SportClub.xml", self.path(), "Default", "1080i")
        window.setup(info)
        window.doModal()
        result = window.result
        del window
        if result == "watch" and chans:
            self.closing = True
            self.close()
            epg.play(chans[0]["cid"])
            return True
        if result == "follow":
            self.toggle_team(who, ev)
        elif result == "games":
            self.show_team_games(name, card)
            return True
        elif result == "info":
            return self.show_team_card(key, team_id, name, side.get("logo", ""))
        return False

    def path(self):
        import xbmcaddon
        return xbmcaddon.Addon("skin.lucent").getAddonInfo("path")

    # ------------------------------------------------------------------ follow menu
    def follow_menu(self):
        dialog = xbmcgui.Dialog()
        entries = [(sc.t("m_search"), self.search_follow), (sc.t("m_leagues"), self.choose_leagues),
                   (sc.t("m_teams"), self.choose_teams), (sc.t("m_countries"), self.choose_countries), (sc.t("m_name"), self.add_name),
                   (sc.t("m_order"), self.change_order), (sc.t("m_manage"), self.manage),
                   (plan.t("auto_off" if plan.load_plan()["auto"] is False else "auto_on"), self.toggle_auto)]
        if self.has_pvr:
            entries.append((sc.t("m_guide"), None))
        choice = dialog.select(sc.t("follow"), [e[0] for e in entries])
        if choice < 0:
            return
        handler = entries[choice][1]
        if handler is None:
            threading.Thread(target=self.rescan, daemon=True).start()
            return
        handler()
        threading.Thread(target=self.after_follow_change, daemon=True).start()

    def toggle_auto(self):
        on = plan.toggle_auto()
        xbmcgui.Dialog().notification(sc.t("title"), plan.t("auto_on" if on else "auto_off"), xbmcgui.NOTIFICATION_INFO, 3000, False)

    def search_follow(self):
        text = xbmcgui.Dialog().input(sc.t("q_search"))
        if not text or not text.strip():
            return
        text = text.strip()
        hits = sc.search_catalog(text)
        labels = [h[2] for h in hits] + [sc.t("as_name", text)]
        pick = xbmcgui.Dialog().select(sc.t("m_search"), labels)
        if pick < 0:
            return
        follow = sc.load_follow()
        if pick == len(hits):
            if text not in follow["names"]:
                follow["names"].append(text)
        else:
            kind, ident, _label, extra = hits[pick]
            if kind == "country":
                name = sc.country_label(ident)
                if not any(sc.norm(t["name"]) == sc.norm(name) for t in follow["teams"]):
                    follow["teams"].append({"league": sc.NATIONAL_LEAGUE, "id": "", "name": name, "logo": ""})
            elif kind == "league":
                if ident not in follow["leagues"]:
                    follow["leagues"].append(ident)
            elif not any(t["id"] == ident for t in follow["teams"]):
                league, name, logo = (extra.split("|") + ["", "", ""])[:3]
                follow["teams"].append({"league": league, "id": ident, "name": name, "logo": logo})
        sc.save_follow(follow)

    def change_order(self):
        rows = sc.sections()
        if len(rows) < 2:
            return
        dialog = xbmcgui.Dialog()
        pick = dialog.select(sc.t("m_order"), [r[3] for r in rows])
        if pick < 0:
            return
        move = dialog.select(sc.t("q_move"), [sc.t("first"), sc.t("up"), sc.t("down")])
        if move < 0:
            return
        keys = [r[0] for r in rows]
        key = keys.pop(pick)
        at = 0 if move == 0 else max(pick - 1, 0) if move == 1 else min(pick + 1, len(keys))
        keys.insert(at, key)
        sc.save_order(keys)

    def rescan(self):
        if self.guide_busy:
            return
        self.guide_busy = True
        try:
            self.status(sc.t("guide", 0))
            epg.scan(progress=lambda d, t: self.status(sc.t("guide", int(d * 100 / max(t, 1)))), abort=lambda: self.closing)
        finally:
            self.guide_busy = False
            self.status("")
            if not self.closing:
                self.render(keep_focus=True)

    def after_follow_change(self):
        self.status(sc.t("loading"))
        try:
            sc.refresh()
        finally:
            self.status("")
        if not self.closing:
            if self.view == "tables":
                self.view = "mine"
            self.render()

    def choose_leagues(self):
        """First the sport, then the competitions of that sport (a tick list)."""
        dialog = xbmcgui.Dialog()
        sports = []
        for lg in sc.LEAGUES.values():
            if lg["sport"] not in sports:
                sports.append(lg["sport"])
        follow = sc.load_follow()
        labels = []
        for sp in sports:
            keys = [k for k, v in sc.LEAGUES.items() if v["sport"] == sp]
            on = sum(1 for k in keys if k in follow["leagues"])
            labels.append(f"{sc.sport_name(sp)}  ({len(keys)})" + (f"  ·  {on} ✓" if on else ""))
        pick = dialog.select(sc.t("m_leagues"), labels)
        if pick < 0:
            return
        keys = [k for k, v in sc.LEAGUES.items() if v["sport"] == sports[pick]]
        pre = [i for i, k in enumerate(keys) if k in follow["leagues"]]
        picked = dialog.multiselect(sc.sport_name(sports[pick]), [sc.LEAGUES[k]["name"] for k in keys], preselect=pre)
        if picked is None:
            return
        chosen = {keys[i] for i in picked}
        follow = sc.load_follow()
        follow["leagues"] = [k for k in follow["leagues"] if k not in keys] + [k for k in keys if k in chosen]
        sc.save_follow(follow)

    def choose_teams(self):
        keys = [k for k, v in sc.LEAGUES.items() if v["kind"] == "teams"]
        labels = [f"{sc.sport_name(sc.LEAGUES[k]['sport'])}  ·  {sc.LEAGUES[k]['name']}" for k in keys]
        pick = xbmcgui.Dialog().select(sc.t("q_league"), labels)
        if pick < 0:
            return
        key = keys[pick]
        xbmc.executebuiltin("ActivateWindow(busydialognocancel)")
        try:
            teams = sc.teams_of(key)
        finally:
            xbmc.executebuiltin("Dialog.Close(busydialognocancel)")
        if not teams:
            xbmcgui.Dialog().notification(sc.t("title"), sc.t("notable"), xbmcgui.NOTIFICATION_INFO, 3000, False)
            return
        follow = sc.load_follow()
        have = {t["id"] for t in follow["teams"]}
        pre = [i for i, (tid, _n, _l) in enumerate(teams) if tid in have]
        picked = xbmcgui.Dialog().multiselect(sc.LEAGUES[key]["name"], [name for _i, name, _l in teams], preselect=pre)
        if picked is None:
            return
        chosen = {teams[i][0] for i in picked}
        listed = {tid for tid, _n, _l in teams}
        follow["teams"] = [t for t in follow["teams"] if t["id"] not in listed] + [
            {"league": key, "id": tid, "name": name, "logo": logo} for tid, name, logo in teams if tid in chosen]
        sc.save_follow(follow)

    def choose_countries(self):
        names = sorted(sc.COUNTRY_NL.values())
        follow = sc.load_follow()
        have = {sc.norm(t["name"]) for t in follow["teams"]}
        pre = [i for i, n in enumerate(names) if sc.norm(n) in have]
        picked = xbmcgui.Dialog().multiselect(sc.t("m_countries"), names, preselect=pre)
        if picked is None:
            return
        chosen = {names[i] for i in picked}
        listed = set(names)
        follow["teams"] = [t for t in follow["teams"] if t["name"] not in listed] + [
            {"league": sc.NATIONAL_LEAGUE, "id": "", "name": n, "logo": ""} for n in sorted(chosen)]
        sc.save_follow(follow)

    def add_name(self):
        text = xbmcgui.Dialog().input(sc.t("q_name"))
        if text and text.strip():
            follow = sc.load_follow()
            if text.strip() not in follow["names"]:
                follow["names"].append(text.strip())
                sc.save_follow(follow)

    def manage(self):
        follow = sc.load_follow()
        rows = ([("leagues", k, f"{sc.sport_name(sc.LEAGUES[k]['sport'])}  ·  {sc.LEAGUES[k]['name']}")
                 for k in follow["leagues"] if k in sc.LEAGUES]
                + [("teams", sc.team_ident(t), t["name"]) for t in follow["teams"]]
                + [("names", n, n) for n in follow["names"]])
        if not rows:
            return
        picked = xbmcgui.Dialog().multiselect(sc.t("q_remove"), [r[2] for r in rows])
        if not picked:
            return
        for i in picked:
            kind, ident, _ = rows[i]
            if kind == "teams":
                follow["teams"] = [t for t in follow["teams"] if sc.team_ident(t) != ident]
            else:
                follow[kind] = [x for x in follow[kind] if x != ident]
        sc.save_follow(follow)


def focus_first(window, ids):
    """Focus the first of these controls that is visible. Controls shown by a window property only count a moment
    after the property is set, so setFocusId is tried again for about two seconds."""
    for _ in range(25):
        for cid in ids:
            try:
                window.setFocusId(cid)
                if window.getFocusId() == cid:
                    return
            except Exception:  # noqa: BLE001
                pass
        xbmc.sleep(80)


class GameInfo(xbmcgui.WindowXMLDialog):
    """The page of one game; its layout depends on the kind of game (teams / race / event)."""
    CLICKS = {311: "play1", 312: "play2", 313: "play3", 314: "play4", 332: "remind", 333: "record", 321: "home", 322: "away",
              331: "fix", 323: "table"}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.result = ""
        self.ev = None
        self.props = {}
        self.parent = None
        self.alive = True

    def setup(self, ev, props, parent):
        self.ev, self.props, self.parent = ev, props, parent

    def onInit(self):
        for key, value in self.props.items():
            self.setProperty(f"g.{key}", "" if value is None else str(value))
        for key, text in (("watch", sc.t("watch")), ("nochan", self.parent.getProperty("sport.t.nochan")), ("form", sc.t("g_form")),
                          ("info", sc.t("g_info")), ("matchinfo", sc.t("g_matchinfo")), ("fulltable", sc.t("g_fulltable")),
                          ("sessions", sc.t("g_sessions")), ("teamstats", sc.t("g_teamstats")), ("top", sc.t("g_top")),
                          ("scoring", sc.t("g_scoring")), ("nodata", sc.t("g_nodata")), ("showing", sc.t("g_showing")),
                          ("previewhint", sc.t("previewhint"))):
            self.setProperty(f"g.t.{key}", text)
        self.setProperty("g.t.stoptext", sc.t("stoptext"))
        cid, name = epg.active()
        self.setProperty("g.preview", cid)
        self.setProperty("g.preview.name", name)
        focus_first(self, (311, 332, 321, 322, 323, 331))
        threading.Thread(target=self.extra, daemon=True).start()

    def extra(self):
        for key, value in self.parent.game_extra(self.ev).items():
            if not self.alive:
                return
            self.setProperty(f"g.{key}", value)
        for key, value in self.parent.game_detail(self.ev).items():
            if not self.alive:
                return
            self.setProperty(f"g.{key}", value)

    def preview(self, n):
        """OK on a channel: watch it in the TV window of this page; OK on the same channel again: full screen."""
        cid = self.props.get(f"ch{n}cid")
        if not cid:
            return
        if epg.active()[0] == str(cid):
            epg.fullscreen()
            return
        name = self.props.get(f"ch{n}name", "")
        epg.set_active(cid, name)
        self.setProperty("g.preview", str(cid))
        self.setProperty("g.preview.name", name)
        threading.Thread(target=self.parent.start_preview, args=(cid,), daemon=True).start()

    def onClick(self, cid):
        if cid in (311, 312, 313, 314):
            self.preview(cid - 310)
            return
        if cid == 334:
            epg.stop()
            self.setProperty("g.preview", "")
            self.setProperty("g.preview.name", "")
            return
        if cid in (321, 322):
            # the club pop-up opens on top of this page, so the page stays where it is
            if self.parent.club_popup(self.ev, "home" if cid == 321 else "away"):
                self.result = "done"
                self.alive = False
                self.close()
            return
        if cid in self.CLICKS:
            self.result = self.CLICKS[cid]
            self.alive = False
            self.close()

    def onAction(self, action):
        if action.getId() in (ACTION_PREVIOUS_MENU, ACTION_NAV_BACK):
            self.alive = False
            self.close()      # the channel keeps playing
        elif action.getId() == ACTION_STOP and epg.active()[0]:
            epg.stop()
            self.setProperty("g.preview", "")
            self.setProperty("g.preview.name", "")


def colour_of(side):
    value = (side.get("color") or "").strip("#")
    return "FF" + value.upper() if len(value) == 6 else "FF2A3441"


class ClubPopup(xbmcgui.WindowXMLDialog):
    """Small pop-up for a club: now / last / next game and four buttons."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.result = ""
        self.info = {}

    def setup(self, info):
        self.info = info

    def onInit(self):
        for key, value in self.info.items():
            self.setProperty(f"club.{key}", value)
        for key, text in (("now", sc.t("c_now")), ("last", sc.t("c_last1")), ("next", sc.t("c_next1")), ("watch", sc.t("c_watch")),
                          ("games", sc.t("c_theirgames")), ("info", sc.t("c_teaminfo"))):
            self.setProperty(f"club.t.{key}", text)
        focus_first(self, (801, 802, 803, 804))

    def onClick(self, cid):
        names = {801: "watch", 802: "follow", 803: "games", 804: "info"}
        if cid in names:
            self.result = names[cid]
            self.close()

    def onAction(self, action):
        if action.getId() in (ACTION_PREVIOUS_MENU, ACTION_NAV_BACK):
            self.close()


class TeamCard(xbmcgui.WindowXMLDialog):
    """The team card: record, home/away form, last three results, next game, Watch / Remind me, Follow, all games."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.result = ""
        self.info = {}

    def setup(self, key, team_id, name, logo, card, chans, followed):
        self.info = {"key": key, "id": team_id, "name": name, "logo": logo, "card": card, "chans": chans, "followed": followed}

    def onInit(self):
        i, card = self.info, self.info["card"]
        row = card["row"]
        self.setProperty("card.name", i["name"])
        self.setProperty("card.logo", i["logo"])
        place = f"{row['rank']}e" if row.get("rank") and sc.NL else str(row.get("rank", ""))
        self.setProperty("card.sub", f"{sc.league_name_of(i['key'])}  ·  {place}" if place else sc.league_name_of(i["key"]))
        rec = "-".join(x for x in (row.get("w"), row.get("d"), row.get("l")) if x != "" and x is not None)
        self.setProperty("card.record", f"{sc.t('c_record')}: {rec}   ·   {row.get('pts', '')} {sc.t('pts')}" if rec else "")
        self.setProperty("card.home", f"{sc.t('c_home')}: {card['home']}")
        self.setProperty("card.away", f"{sc.t('c_away')}: {card['away']}")
        for n in range(5):
            letter = card["recent"][n][1][0] if n < len(card["recent"]) else ""
            self.setProperty(f"card.f{n + 1}", LETTERS.get(letter, letter))
            self.setProperty(f"card.f{n + 1}c", sc.FORM_COLOURS.get(letter, ""))
        for n in range(3):
            if n < len(card["last3"]):
                ev, (letter, score, opp, home) = card["last3"][n]
                self.setProperty(f"card.r{n + 1}", f"{sc.local_time(ev['start']) and ac.day_short(sc.local_day(ev['start']))}   {'vs' if home else '@'} {opp}")
                self.setProperty(f"card.r{n + 1}s", score)
                self.setProperty(f"card.r{n + 1}c", sc.FORM_COLOURS[letter])
            else:
                for suffix in ("", "s", "c"):
                    self.setProperty(f"card.r{n + 1}{suffix}", "")
        nxt = card["next"]
        self.setProperty("card.next", f"{when_line(nxt)}   {nxt['home'].get('name', '')} – {nxt['away'].get('name', '')}" if nxt else sc.t("c_nonext"))
        chans = i["chans"]
        self.setProperty("card.nextchan", f"{chans[0]['name']}  ·  {chans[0]['tag']}" if chans else "")
        self.setProperty("card.canwatch", "1" if chans else "")
        self.setProperty("card.canremind", "1" if nxt else "")
        self.setProperty("card.followtext", sc.t("unfollow_team" if i["followed"] else "follow_team", i["name"]))
        self.setProperty("card.t.watch", sc.t("c_watch"))
        self.setProperty("card.t.remind", plan.t("btn_remind"))
        self.setProperty("card.t.games", sc.t("c_games"))
        self.setProperty("card.t.last", sc.t("c_last"))
        self.setProperty("card.t.next", sc.t("c_next"))
        focus_first(self, (301, 303, 304))

    def onClick(self, cid):
        names = {301: "watch", 302: "remind", 303: "follow", 304: "games"}
        if cid in names:
            self.result = names[cid]
            self.close()

    def onAction(self, action):
        if action.getId() in (ACTION_PREVIOUS_MENU, ACTION_NAV_BACK):
            self.close()


def open_window():
    import xbmcaddon
    path = xbmcaddon.Addon("skin.lucent").getAddonInfo("path")
    window = Sport(WINDOW_XML, path, "Default", "1080i")
    window.doModal()
    del window


def add_tab(flag, label_key, icon, action, before=("ActivateWindow(Settings)",)):
    """Put a tab in the side menu once (before Settings)."""
    if xbmc.getInfoLabel(f"Skin.String({flag})"):
        return
    if not xbmc.getInfoLabel("Skin.String(nuvio.menu.version)"):
        return                              # the menu is not written yet; next time
    xbmc.executebuiltin(f'Skin.SetString({flag},"1")', True)
    import menu
    m = menu.Menu()
    if any(tab["action"] == action for tab in m.tabs) or len(m.tabs) >= menu.NTABS:
        return
    at = next((i for i, tab in enumerate(m.tabs) if tab["action"] in before), len(m.tabs))
    start = m.start_tab()
    m.tabs.insert(at, {"label": menu.tr(label_key), "icon": icon, "action": action, "widgets": [], "actionlabel": ""})
    m.start = start
    m.save()


def ensure_tab():
    """The Sport and TV tabs in the side menu (once each)."""
    add_tab("nuvio.sport.tab", "t_sport", "icons/sport.png", "RunScript(special://skin/scripts/sport.py)")
    add_tab("nuvio.tv.tab", "t_tv", "icons/tv.png", "RunScript(special://skin/scripts/tv.py)",
            before=("RunScript(special://skin/scripts/sport.py)", "ActivateWindow(Settings)"))


if __name__ == "__main__":
    action = sys.argv[1] if len(sys.argv) > 1 else "open"
    if action == "ensure_tab":
        ensure_tab()
    elif action == "service":
        plan.run_service()
    else:
        open_window()
