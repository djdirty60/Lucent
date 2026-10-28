# -*- coding: utf-8 -*-
"""Lucent: the Sport screen - My sport | All games | Tables - with the IPTV channels that show each game.

RunScript(special://skin/scripts/sport.py)             open the screen
RunScript(special://skin/scripts/sport.py,ensure_tab)  add the Sport tab to the side menu (once)

The window is xml/Lucent_Sport.xml (gen_sport.py). Data: sport_core.py (ESPN), guide: sport_epg.py (Kodi PVR).
"""
import datetime
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
VIEW_BUTTONS = {101: "mine", 102: "all", 103: "tables"}
FOLLOW_BUTTON = 104
LIST = 200
DAY_BUTTONS = range(111, 118)
DAY_PREV, DAY_NEXT = 110, 118
CHANNEL_BUTTONS = {311: 1, 312: 2, 313: 3, 314: 4}
FOLLOW_HOME, FOLLOW_AWAY, SHOW_TABLE = 321, 322, 323
FIX_BUTTON, REMIND_BUTTON, RECORD_BUTTON = 331, 332, 333
LEAGUE_LIST, TABLE_LIST = 400, 410
EPG_LEAGUE = "tv"
ACTION_MOVE_LEFT, ACTION_MOVE_RIGHT = 1, 2
HERO_MAX = 6


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
        self.table_token = 0
        self.table_pos = -1
        self.guide_busy = False
        self.has_pvr = False

    # ------------------------------------------------------------------ window events
    def onInit(self):
        if self.ready:
            return
        self.ready = True
        for key in ("title", "mine", "all", "tables", "follow", "watch", "gp", "gd", "pts", "powered", "notable"):
            self.setProperty(f"sport.t.{key}", sc.t(key))
        self.has_pvr = len(epg.channels()) > 0
        self.setProperty("sport.t.nochan", sc.t("nochan") if self.has_pvr else sc.t("noguide"))
        self.view = "mine" if sc.has_follow() else "all"
        self.render()
        self.setFocusId(102 if self.view == "all" else 101)
        threading.Thread(target=self.background, daemon=True).start()

    def onClose(self):
        self.closing = True

    def onAction(self, action):
        aid = action.getId()
        if aid in (ACTION_PREVIOUS_MENU, ACTION_NAV_BACK):
            self.closing = True
            self.close()
            return
        if aid in (ACTION_MOVE_LEFT, ACTION_MOVE_RIGHT) and self.getFocusId() == LIST and self.view == "mine":
            item = self.getControl(LIST).getSelectedItem()
            if item and item.getProperty("hero"):
                self.flip_hero(1 if aid == ACTION_MOVE_RIGHT else -1)
                return
        if self.getFocusId() == LEAGUE_LIST:
            self.table_token += 1
            token = self.table_token
            threading.Timer(0.45, self.table_after, args=(token,)).start()

    def onClick(self, cid):
        if cid in VIEW_BUTTONS:
            self.view = VIEW_BUTTONS[cid]
            self.render()
        elif cid == FOLLOW_BUTTON:
            self.follow_menu()
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
        elif cid in CHANNEL_BUTTONS:
            self.play_channel(CHANNEL_BUTTONS[cid])
        elif cid in (FOLLOW_HOME, FOLLOW_AWAY):
            self.toggle_team("home" if cid == FOLLOW_HOME else "away")
        elif cid == SHOW_TABLE:
            self.open_table()
        elif cid == LEAGUE_LIST:
            self.setFocusId(TABLE_LIST)
        elif cid == LIST:
            ev, item = self.current()
            if item and item.getProperty("hero") and item.getProperty("ch1cid"):
                self.play_channel(1)
            elif item and item.getProperty("ch1cid"):
                self.setFocusId(311)

    # ------------------------------------------------------------------ background work
    def status(self, text=""):
        self.setProperty("sport.status", text)

    def background(self):
        """Fetch the games and read the IPTV guide without keeping the screen waiting."""
        try:
            if not sc.all_cached():
                self.status(sc.t("loading"))
            changed = sc.refresh(progress=None)
            for league in {t["league"] for t in sc.load_follow()["teams"] if t.get("league") in sc.LEAGUES and t["league"] != sc.NATIONAL_LEAGUE}:
                sc.standings(league)             # for "2nd in Eredivisie"
                changed = True
            if changed and not self.closing:
                self.render(keep_focus=True)
            if self.has_pvr and not epg.is_fresh() and not self.closing:
                self.guide_busy = True
                last = [0]

                def progress(done, total):
                    pct = int(done * 100 / max(total, 1))
                    if pct != last[0]:
                        last[0] = pct
                        self.status(sc.t("guide", pct))

                self.status(sc.t("guide", 0))
                epg.scan(progress=progress, abort=lambda: self.closing)
                self.guide_busy = False
                if not self.closing:
                    self.render(keep_focus=True)
        except Exception as error:  # noqa: BLE001
            sc.log(f"background: {error}")
        finally:
            self.guide_busy = False
            if not self.closing:
                self.status("")

    # ------------------------------------------------------------------ data -> list
    def pick_events(self):
        self.follow = sc.load_follow()
        data = epg.load() if self.has_pvr else {}
        if self.view == "mine":
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
            "hlogo": ev["home"].get("logo", ""), "alogo": ev["away"].get("logo", ""),
            "mid": score_text(ev), "lgicon": ev.get("lg", ""), "isevent": "1" if kind_event else "",
            "league": league_name(ev["league"]), "chan": best,
            "when": when_line(ev), "venue": "  ·  ".join(x for x in (ev.get("venue"), ev.get("round")) if x),
            "header": header, "headersub": headersub, "evid": ev["id"],
            "hcol": colour(ev["home"].get("color"), "66"), "acol": colour(ev["away"].get("color") or ev["away"].get("alt"), "66"),
        }
        if kind_event and ev.get("sub") and ev["league"] != EPG_LEAGUE:
            props["when"] = f"{ev['sub']}  ·  {when_line(ev)}"
        for n, chan in enumerate(chans, 1):
            bits = [chan["tag"]]
            if chan["q"]:
                bits.append(chan["q"])
            if chan["live"]:
                bits.insert(0, sc.t("livenow"))
            props[f"ch{n}name"] = chan["name"]
            props[f"ch{n}sub"] = "  ·  ".join(bits)
            props[f"ch{n}cid"] = chan["cid"]
        props.update(self.plan_props(ev))
        if not kind_event:
            for who, side in (("home", ev["home"]), ("away", ev["away"])):
                if side.get("name"):
                    followed = sc.is_following_team(self.follow, side)
                    props[f"follow{who}"] = sc.t("unfollow_team" if followed else "follow_team", side["name"])
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
                     "tag": sc.t("sure"), "live": ev["state"] == "in", "title": ev["title"], "start": ev["start"]}]
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
        events, data = self.pick_events()
        self.hero_events = []
        if self.view == "mine":
            items = self.mine_items(data)
        else:
            self.events = events
            self.by_id = {e["id"]: e for e in events}
            items = [self.event_item(ev, data) for ev in events]
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

    def mine_items(self, data):
        """Hero card, 'Live & Upcoming', then one block per team / competition / name you follow (your order)."""
        follow = self.follow
        now = time.time()
        today = ac.today()
        by_id, items = {}, []

        def add(ev):
            by_id[ev["id"]] = ev

        def block(events):
            live = [e for e in events if e["state"] == "in"]
            coming = sorted((e for e in events if e["state"] == "pre"), key=lambda e: e["start"])
            done = sorted((e for e in events if e["state"] == "post" and local_ok(e)), key=lambda e: -e["start"])
            return live, coming, done

        def local_ok(e):
            return sc.local_day(e["start"]) >= today - datetime.timedelta(days=1)

        rows = []
        for key, kind, ident, title in sc.sections(follow):
            if kind == "team":
                team = next((t for t in follow["teams"] if sc.team_ident(t) == ident), {"id": ident, "name": title})
                events, sub = sc.events_of_team(ident, title), sc.place_text(team)
            elif kind == "league":
                events, sub = [e for e in sc.all_cached() if e["league"] == ident], ""
            else:
                events, sub = name_events({"names": [ident]}, data), sc.t("tvguide")
            live, coming, done = block(events)
            rows.append((title, sub, live + coming[:4] + done[:1], live, coming))
        everything = {}
        for _t, _s, shown, _l, _c in rows:
            for e in shown:
                everything[e["id"]] = e
        live_all = sorted((e for e in everything.values() if e["state"] == "in"), key=lambda e: e["start"])
        coming_all = sorted((e for e in everything.values() if e["state"] == "pre"), key=lambda e: e["start"])
        upcoming = (live_all + coming_all)[:8]
        self.hero_events = (live_all + coming_all)[:HERO_MAX]
        self.hero_index = 0
        if self.hero_events:
            ev = self.hero_events[0]
            label, label2, props = self.event_props(ev, data)
            props["hero"] = "1"
            props["heroof"] = self.hero_count()
            items.append(listitem(label, label2, **props))
            add(ev)
        for n, ev in enumerate(upcoming):
            header = headersub = ""
            if n == 0:
                header = sc.t("liveup")
                headersub = f"{len(live_all)} live" if live_all else ""
            items.append(self.event_item(ev, data, header, headersub))
            add(ev)
        for title, sub, shown, _live, _coming in rows:
            first = True
            for ev in sorted(shown, key=lambda e: (e["state"] != "in", e["state"] == "post", e["start"] if e["state"] != "post" else -e["start"])):
                items.append(self.event_item(ev, data, title if first else "", sub if first else ""))
                add(ev)
                first = False
        self.by_id = by_id
        self.events = list(by_id.values())
        return items

    def hero_count(self):
        return f"{self.hero_index + 1} / {len(self.hero_events)}"

    def flip_hero(self, step):
        if len(self.hero_events) < 2:
            return
        self.hero_index = (self.hero_index + step) % len(self.hero_events)
        ev = self.hero_events[self.hero_index]
        data = epg.load() if self.has_pvr else {}
        label, label2, props = self.event_props(ev, data)
        props["hero"] = "1"
        props["heroof"] = self.hero_count()
        item = self.getControl(LIST).getListItem(0)
        item.setLabel(label)
        item.setLabel2(label2)
        for key, value in props.items():
            item.setProperty(key, "" if value is None else str(value))
        self.by_id[ev["id"]] = ev

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
    def current(self):
        item = self.getControl(LIST).getSelectedItem()
        if not item:
            return None, None
        return self.by_id.get(item.getProperty("evid")), item

    def play_channel(self, n):
        ev, item = self.current()
        if not item:
            return
        cid = item.getProperty(f"ch{n}cid")
        if cid:
            self.closing = True
            self.close()
            epg.play(cid)

    def toggle_team(self, who):
        ev, item = self.current()
        if not ev or ev["kind"] != "teams":
            return
        side = ev[who]
        followed = sc.toggle_team(ev["league"], side)
        xbmcgui.Dialog().notification(sc.t("title"), sc.t("follow_team" if followed else "unfollow_team", side["name"]),
                                      xbmcgui.NOTIFICATION_INFO, 2500, False)
        self.render(keep_focus=True)

    def fix_channel(self):
        ev, _item = self.current()
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
        ev, _item = self.current()
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

    def set_recording(self):
        ev, _item = self.current()
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

    def open_table(self):
        ev, _ = self.current()
        if not ev or ev["league"] not in sc.LEAGUES:
            return
        self.table_key = ev["league"]
        self.view = "tables"
        self.render()
        self.setFocusId(TABLE_LIST)

    # ------------------------------------------------------------------ tables
    def fill_leagues(self):
        keys = [k for k, v in sc.LEAGUES.items() if v["kind"] == "teams"]
        keys.sort(key=lambda k: (k not in self.follow["leagues"], k not in sc.league_keys(), list(sc.LEAGUES).index(k)))
        control = self.getControl(LEAGUE_LIST)
        control.reset()
        control.addItems([listitem(sc.LEAGUES[k]["name"], key=k) for k in keys])
        self.league_keys_shown = keys
        index = keys.index(self.table_key) if self.table_key in keys else 0
        control.selectItem(index)
        self.table_key = keys[index]
        self.table_pos = index
        self.load_table(self.table_key)

    def table_after(self, token):
        if token != self.table_token or self.closing:
            return
        try:
            pos = self.getControl(LEAGUE_LIST).getSelectedPosition()
        except Exception:  # noqa: BLE001
            return
        if pos != self.table_pos and 0 <= pos < len(self.league_keys_shown):
            self.table_pos = pos
            self.table_key = self.league_keys_shown[pos]
            self.load_table(self.table_key)

    def load_table(self, key):
        rows = sc.standings(key)
        control = self.getControl(TABLE_LIST)
        control.reset()
        items = []
        for row in rows:
            if "header" in row:
                items.append(listitem(row["header"], header=row["header"]))
            else:
                items.append(listitem(row["team"], icon=row["logo"], rank=row["rank"], gp=row["gp"], gd=row["gd"], pts=row["pts"]))
        control.addItems(items)
        self.setProperty("sport.notable", "" if items else "1")

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
        keys = list(sc.LEAGUES)
        labels = [f"{sc.sport_name(sc.LEAGUES[k]['sport'])}  ·  {sc.LEAGUES[k]['name']}" for k in keys]
        pre = [i for i, k in enumerate(keys) if k in self.follow["leagues"]]
        picked = xbmcgui.Dialog().multiselect(sc.t("m_leagues"), labels, preselect=pre)
        if picked is None:
            return
        follow = sc.load_follow()
        follow["leagues"] = [keys[i] for i in picked]
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


def open_window():
    import xbmcaddon
    path = xbmcaddon.Addon("skin.lucent").getAddonInfo("path")
    window = Sport(WINDOW_XML, path, "Default", "1080i")
    window.doModal()
    del window


def ensure_tab():
    """Add the Sport tab to the side menu once (before Settings)."""
    if xbmc.getInfoLabel("Skin.String(nuvio.sport.tab)"):
        return
    if not xbmc.getInfoLabel("Skin.String(nuvio.menu.version)"):
        return                              # the menu is not written yet; next time
    xbmc.executebuiltin('Skin.SetString(nuvio.sport.tab,"1")', True)
    import menu
    m = menu.Menu()
    action = "RunScript(special://skin/scripts/sport.py)"
    if any(tab["action"] == action for tab in m.tabs) or len(m.tabs) >= menu.NTABS:
        return
    at = next((i for i, tab in enumerate(m.tabs) if tab["action"] == "ActivateWindow(Settings)"), len(m.tabs))
    start = m.start_tab()
    m.tabs.insert(at, {"label": menu.tr("t_sport"), "icon": "icons/sport.png", "action": action,
                       "widgets": [], "actionlabel": ""})
    m.start = start
    m.save()


if __name__ == "__main__":
    action = sys.argv[1] if len(sys.argv) > 1 else "open"
    if action == "ensure_tab":
        ensure_tab()
    elif action == "service":
        plan.run_service()
    else:
        open_window()
