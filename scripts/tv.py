# -*- coding: utf-8 -*-
"""Lucent: the TV tab - your IPTV channels (Kodi PVR, e.g. IPTV Simple Client) with what is on now and next.

RunScript(special://skin/scripts/tv.py)   open the screen
Groups on the left, channels on the right (OK plays), Search filters by name.
"""
import calendar
import datetime
import json
import sys
import threading
import time

import xbmc
import xbmcgui

import sport_core as sc

WINDOW_XML = "Lucent_TV.xml"
ACTION_PREVIOUS_MENU = 10
ACTION_NAV_BACK = 92
SEARCH, GROUPS, CHANNELS = 101, 300, 200
MAX_ROWS = 1500

TX = {
    "title": ("TV", "TV"), "search": ("Search", "Zoeken"), "all": ("All channels", "Alle zenders"),
    "now": ("NOW", "NU"), "next": ("NEXT", "STRAKS"), "q_search": ("Channel name", "Naam van de zender"),
    "n_channels": ("{} channels", "{} zenders"), "more": ("first {} shown - use Search", "eerste {} getoond - gebruik Zoeken"),
    "empty": ("No TV channels found. Set up IPTV Simple Client (Settings > Add-ons > My add-ons > PVR clients) and restart Kodi.",
              "Geen tv-zenders gevonden. Stel IPTV Simple Client in (Instellingen > Add-ons > Mijn add-ons > PVR-clients) en start Kodi opnieuw."),
    "no_epg": ("No programme information", "Geen programma-informatie"), "hint": ("OK: watch   ◄: groups   Search: find a channel", "OK: kijken   ◄: groepen   Zoeken: een zender vinden"),
    "loading": ("Loading channels…", "Zenders laden…"),
}


def t(key, *args):
    text = TX[key][1 if sc.NL else 0]
    return text.format(*args) if args else text


def rpc(method, params=None):
    request = {"jsonrpc": "2.0", "id": 1, "method": method, "params": params or {}}
    try:
        return json.loads(xbmc.executeJSONRPC(json.dumps(request))).get("result") or {}
    except Exception as error:  # noqa: BLE001
        sc.log(f"tv rpc {method}: {error}")
        return {}


def stamp(value):
    try:
        return calendar.timegm(datetime.datetime.strptime(value, "%Y-%m-%d %H:%M:%S").timetuple())
    except (TypeError, ValueError):
        return 0


def hhmm(ts):
    return datetime.datetime.fromtimestamp(ts).strftime("%H:%M") if ts else ""


def groups():
    """[(groupid, label)] - 'All channels' first."""
    out = [("alltv", t("all"))]
    for g in rpc("PVR.GetChannelGroups", {"channeltype": "tv"}).get("channelgroups") or []:
        if g.get("channelgroupid") not in ("alltv", None) and g.get("label"):
            out.append((g["channelgroupid"], g["label"]))
    return out


def channel_rows(group):
    props = ["thumbnail", "channelnumber", "broadcastnow", "broadcastnext", "hidden"]
    data = rpc("PVR.GetChannels", {"channelgroupid": group, "properties": props})
    rows = []
    now = time.time()
    for ch in data.get("channels") or []:
        if ch.get("hidden"):
            continue
        cur, nxt = ch.get("broadcastnow") or {}, ch.get("broadcastnext") or {}
        start, end = stamp(cur.get("starttime")), stamp(cur.get("endtime"))
        pct = int((now - start) * 10 / (end - start)) + 1 if start and end > start and start <= now <= end else 0
        rows.append({"id": ch["channelid"], "name": ch.get("label") or ch.get("channel") or "", "num": str(ch.get("channelnumber", "")),
                     "logo": ch.get("thumbnail") or "", "now": cur.get("title") or "", "when": (f"{hhmm(start)} – {hhmm(end)}" if start else ""),
                     "prog": str(min(max(pct, 0), 10)) if pct else "", "next": nxt.get("title") or "",
                     "nextwhen": hhmm(stamp(nxt.get("starttime")))})
    return rows


class TV(xbmcgui.WindowXML):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.group = "alltv"
        self.query = ""
        self.groups = []
        self.token = 0
        self.ready = False
        self.closing = False

    def onInit(self):
        if self.ready:
            return
        self.ready = True
        for key in ("title", "search", "now", "next", "hint"):
            self.setProperty(f"tv.t.{key}", t(key))
        self.setProperty("tv.status", t("loading"))
        threading.Thread(target=self.load, daemon=True).start()

    def load(self):
        self.groups = groups()
        items = [xbmcgui.ListItem(label) for _gid, label in self.groups]
        control = self.getControl(GROUPS)
        control.reset()
        control.addItems(items)
        self.fill()
        self.setFocusId(CHANNELS)

    def fill(self):
        self.token += 1
        token = self.token
        rows = channel_rows(self.group)
        if self.query:
            q = sc.norm(self.query)
            rows = [r for r in rows if q in sc.norm(r["name"]) or q in sc.norm(r["now"])]
        if token != self.token or self.closing:
            return
        shown = rows[:MAX_ROWS]
        items = []
        for r in shown:
            item = xbmcgui.ListItem(r["name"], r["now"])
            item.setArt({"icon": r["logo"], "thumb": r["logo"]})
            for key in ("num", "when", "prog", "next", "nextwhen"):
                item.setProperty(key, r[key])
            item.setProperty("now", r["now"] or t("no_epg"))
            item.setProperty("cid", str(r["id"]))
            items.append(item)
        control = self.getControl(CHANNELS)
        control.reset()
        control.addItems(items)
        self.setProperty("tv.empty", t("empty") if not rows and not self.query and self.group == "alltv" else "")
        count = t("n_channels", len(rows))
        self.setProperty("tv.count", count + (f"  ·  {t('more', MAX_ROWS)}" if len(rows) > MAX_ROWS else ""))
        self.setProperty("tv.status", "")

    def onClick(self, cid):
        if cid == SEARCH:
            text = xbmcgui.Dialog().input(t("q_search"), defaultt=self.query)
            if text is not None:
                self.query = text.strip()
                self.setProperty("tv.query", self.query)
                threading.Thread(target=self.fill, daemon=True).start()
        elif cid == GROUPS:
            self.setFocusId(CHANNELS)
        elif cid == CHANNELS:
            item = self.getControl(CHANNELS).getSelectedItem()
            if item and item.getProperty("cid"):
                self.closing = True
                self.close()
                rpc("Player.Open", {"item": {"channelid": int(item.getProperty("cid"))}})

    def onAction(self, action):
        aid = action.getId()
        if aid in (ACTION_PREVIOUS_MENU, ACTION_NAV_BACK):
            self.closing = True
            self.close()
            return
        if self.getFocusId() == GROUPS:
            pos = self.getControl(GROUPS).getSelectedPosition()
            if 0 <= pos < len(self.groups) and self.groups[pos][0] != self.group:
                self.group = self.groups[pos][0]
                self.setProperty("tv.status", t("loading"))
                threading.Thread(target=self.fill, daemon=True).start()


def open_window():
    import xbmcaddon
    path = xbmcaddon.Addon("skin.lucent").getAddonInfo("path")
    window = TV(WINDOW_XML, path, "Default", "1080i")
    window.doModal()
    del window


if __name__ == "__main__":
    open_window()
