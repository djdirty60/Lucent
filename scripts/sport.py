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
LEAGUE_LIST, TABLE_LIST = 400, 410
EPG_LEAGUE = "tv"


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
        elif cid in CHANNEL_BUTTONS:
            self.play_channel(CHANNEL_BUTTONS[cid])
        elif cid in (FOLLOW_HOME, FOLLOW_AWAY):
            self.toggle_team("home" if cid == FOLLOW_HOME else "away")
        elif cid == SHOW_TABLE:
            self.open_table()
        elif cid == LEAGUE_LIST:
            self.setFocusId(TABLE_LIST)

    # ------------------------------------------------------------------ background work
    def status(self, text=""):
        self.setProperty("sport.status", text)

    def background(self):
        """Fetch the games and read the IPTV guide without keeping the screen waiting."""
        try:
            if not sc.all_cached():
                self.status(sc.t("loading"))
            changed = sc.refresh(progress=None)
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
            events = sc.mine_events()
            events += name_events(self.follow, data)
            live = [e for e in events if e["state"] == "in"]
            rest = sorted((e for e in events if e["state"] != "in"), key=lambda e: e["start"])
            return live + [e for e in rest if e["state"] == "pre"] + [e for e in rest if e["state"] == "post"][-6:], data
        day_events = sc.events_on(self.day)
        live, coming, done = sc.order(day_events)
        return sorted(live + coming + done, key=lambda e: e["start"]), data

    def event_item(self, ev, data, header=""):
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
            "header": header, "evid": ev["id"],
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
        if not kind_event:
            for who, side in (("home", ev["home"]), ("away", ev["away"])):
                if side.get("name"):
                    followed = sc.is_following_team(self.follow, side)
                    props[f"follow{who}"] = sc.t("unfollow_team" if followed else "follow_team", side["name"])
            if ev["league"] in sc.LEAGUES:
                props["table"] = sc.t("show_table")
        return listitem(label, ev.get("sub", "") if kind_event else "", **props)

    def channels_of(self, ev, data):
        if ev["league"] == EPG_LEAGUE:
            raw = data.get("names", {}).get(str(ev.get("cid")), "")
            return [{"cid": ev["cid"], "name": epg.clean_name(raw) or raw, "q": epg.quality_of(raw), "score": 3,
                     "tag": sc.t("sure"), "live": ev["state"] == "in", "title": ev["title"], "start": ev["start"]}]
        if not data:
            return []
        return epg.channels_for(ev, data)

    def render(self, keep_focus=False):
        self.setProperty("sport.view", self.view)
        for name in ("mine", "all", "tables"):
            self.setProperty(f"sport.is.{name}", "1" if name == self.view else "")
        if self.view == "tables":
            self.setProperty("sport.empty", "")
            self.fill_leagues()
            return
        events, data = self.pick_events()
        self.events = events
        items, last_day = [], None
        for ev in events:
            day = sc.local_day(ev["start"])
            header = ""
            if self.view == "mine" and day != last_day:
                header = nice_day(day)
            last_day = day
            item = self.event_item(ev, data, header)
            if header and day not in (ac.today(), ac.today() + datetime.timedelta(days=1)):
                item.setProperty("headerdate", "")
            items.append(item)
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
        return next((e for e in self.events if e["id"] == item.getProperty("evid")), None), item

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
        options = [sc.t("m_leagues"), sc.t("m_teams"), sc.t("m_name"), sc.t("m_manage")]
        if self.has_pvr:
            options.append(sc.t("m_guide"))
        choice = dialog.select(sc.t("follow"), options)
        if choice == 0:
            self.choose_leagues()
        elif choice == 1:
            self.choose_teams()
        elif choice == 2:
            self.add_name()
        elif choice == 3:
            self.manage()
        elif choice == 4:
            threading.Thread(target=self.rescan, daemon=True).start()
            return
        if choice >= 0:
            threading.Thread(target=self.after_follow_change, daemon=True).start()

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
                + [("teams", t["id"], t["name"]) for t in follow["teams"]]
                + [("names", n, n) for n in follow["names"]])
        if not rows:
            return
        picked = xbmcgui.Dialog().multiselect(sc.t("q_remove"), [r[2] for r in rows])
        if not picked:
            return
        for i in picked:
            kind, ident, _ = rows[i]
            if kind == "teams":
                follow["teams"] = [t for t in follow["teams"] if t["id"] != ident]
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
    else:
        open_window()
