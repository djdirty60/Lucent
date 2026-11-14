"""What's new (example A): the versions on the left, the chosen version with every change under its own heading on the right.
OK on a change opens it on its own (example B): a picture, the whole explanation, how to use it in steps and a button
that takes you there.

The newest versions come from resources/whatsnew.json (a heading and an icon per change, Dutch and English).
Older versions come from addon.xml's <news> (English) or resources/changelog_nl.txt (Dutch); their text is split
into headings where it says 'Heading: ...'.
2.1.8: the updates of your video add-on are in the same list (its resources/whatsnew.json, when it is installed), by
date and with a label with the add-on's name; without that file the window is as before.
"""
import html
import json
import re
import threading

import xbmc
import xbmcgui
import xbmcvfs

SKIN = "special://skin/"
VIDEO_NEWS = "special://home/addons/plugin.video.lucent/resources/whatsnew.json"


def video_name():
    return xbmc.getInfoLabel("System.AddonTitle(plugin.video.lucent)") or "Lucent Video"
NL = xbmc.getLanguage(xbmc.ISO_639_1) == "nl"
MONTHS_NL = ["jan", "feb", "mrt", "apr", "mei", "jun", "jul", "aug", "sep", "okt", "nov", "dec"]
MONTHS_EN = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
CLOSE = (9, 10, 92, 216, 247, 257, 275, 61467, 61448)
ICONS = [("sport", "sport"), ("speler", "info"), ("player", "info"), ("wedstrijd", "sport"), ("game", "sport"),
         ("tv", "tv"), ("zender", "tv"), ("channel", "tv"), ("gids", "tv"), ("guide", "tv"),
         ("bibliothe", "library"), ("library", "library"), ("ondertitel", "subtitles"), ("subtitle", "subtitles"),
         ("instelling", "settings"), ("setting", "settings"), ("stream", "play"), ("agenda", "calendar"),
         ("kalender", "calendar"), ("calendar", "calendar"), ("home", "home"), ("zoek", "search"), ("search", "search"),
         ("update", "refresh"), ("serie", "movies"), ("film", "movies"), ("menu", "layout"), ("widget", "layout"),
         ("trakt", "trakt"), ("audio", "audio"), ("geluid", "audio"), ("sound", "audio")]


def t(en, nl):
    return nl if NL else en


def read(path):
    try:
        f = xbmcvfs.File(SKIN + path)
        data = f.read()
        f.close()
        return data if isinstance(data, str) else data.decode("utf-8", "replace")
    except Exception:  # noqa: BLE001
        return ""


def icon_for(heading):
    low = heading.lower()
    return next((ic for key, ic in ICONS if key in low), "sparkle")


def split_items(text):
    """'Player info: a. Settings: b.' -> [(icon, 'Player info', 'a.'), (icon, 'Settings', 'b.')]."""
    text = re.sub(r"\s+", " ", text).strip()
    parts = re.split(r"(?<=[.;!])\s+(?=[A-Z0-9][^.:;!?]{1,42}:\s)", text)
    items, general = [], t("Improved", "Verbeterd")
    for part in parts:
        m = re.match(r"([A-Z0-9][^.:;!?]{1,42}):\s(.*)", part)
        head, body = (m.group(1).strip(), m.group(2).strip()) if m else (general, part.strip())
        if len(body) > 280:                                  # three lines at most: cut at a sentence when possible
            cut = body[:280].rsplit(". ", 1)[0]
            body = (cut + "." if len(cut) > 120 else body[:277].rsplit(" ", 1)[0]) + " …"
        if body:
            items.append((icon_for(head), head[:1].upper() + head[1:], body[:1].upper() + body[1:], {}))
    return items


def nice_date(iso):
    try:
        y, m, d = (int(x) for x in iso.split("-"))
        month = (MONTHS_NL if NL else MONTHS_EN)[m - 1]
        return f"{d} {month}", f"{d} {month} {y}"
    except (ValueError, AttributeError, IndexError):
        return "", ""


def versions():
    """[{'v', 'tag', 'short', 'long', 'items': [(icon, heading, text)]}], newest first."""
    out, seen = [], set()
    try:
        data = json.loads(read("resources/whatsnew.json") or "{}")
    except ValueError:
        data = {}
    for entry in data.get("versions") or []:
        items = [(it[0], it[1] if NL else it[3], it[2] if NL else it[4], it[5] if len(it) > 5 and isinstance(it[5], dict) else {})
                 for it in entry.get("items") or [] if len(it) >= 5]
        short, long = nice_date(entry.get("date", ""))
        out.append({"v": entry["v"], "tag": entry.get("tag", "") if NL else entry.get("tag_en", entry.get("tag", "")),
                    "short": short, "long": long, "items": items})
        seen.add(entry["v"])
    news = re.search(r"<news>(.*?)</news>", read("addon.xml"), re.S)
    older = []
    for line in html.unescape(news.group(1).strip() if news else "").splitlines():   # '1.33.0 - Beta 3: ...'
        m = re.match(r"\s*(\d+\.\d+\.\d+)(?:\s*-\s*([^:]{1,30}))?:\s(.*)", line)
        if m:
            older.append([m.group(1), (m.group(2) or "").strip(), m.group(3)])
    if NL:
        dutch = {}
        for line in read("resources/changelog_nl.txt").splitlines():
            m = re.match(r"(\d+\.\d+\.\d+):\s(.*)", line.strip())
            if m:
                dutch[m.group(1)] = m.group(2)
        for row in older:
            row[2] = dutch.pop(row[0], row[2])
        older += [[v, "", text] for v, text in dutch.items()]
    for v, tag, text in older:
        if v in seen:
            continue
        seen.add(v)
        tag = tag.replace("Beta", "Bèta") if NL else tag
        out.append({"v": v, "tag": tag, "short": "", "long": "", "items": split_items(text)})
    out.sort(key=lambda e: [int(x) for x in e["v"].split(".")], reverse=True)
    return merge_video(out)


def video_versions():
    """The updates of your video add-on from its own whatsnew.json; [] when it is not installed or the file is broken."""
    try:
        if not xbmcvfs.exists(VIDEO_NEWS):
            return []
        fh = xbmcvfs.File(VIDEO_NEWS)
        data = json.loads(fh.read() or "{}")
        fh.close()
    except Exception:  # noqa: BLE001 - a broken file changes nothing
        return []
    out = []
    for entry in (data.get("versions") or []) if isinstance(data, dict) else []:
        try:
            items = [(it[0], it[1] if NL else it[3], it[2] if NL else it[4], {})
                     for it in entry.get("items") or [] if isinstance(it, list) and len(it) >= 5]
            label = (entry.get("label") if NL else entry.get("label_en") or entry.get("label")) or str(entry.get("v", ""))
            short, long = nice_date(entry.get("date", ""))
            if label and items:
                out.append({"v": label, "tag": "", "short": short, "long": long, "items": items, "video": True,
                            "date": entry.get("date", ""), "at": entry.get("at", "")})
        except Exception:  # noqa: BLE001
            continue
    out.sort(key=lambda e: e["date"], reverse=True)
    return out


def merge_video(skin):
    """Skin versions and video add-on updates in one list, newest first. 2.1.8: by the moment they were published ('at',
    UTC) when both have it, else by date (an add-on update without a time goes above a skin version of the same day);
    skin versions without a date (the oldest ones) stay at the bottom in their own order."""
    video = video_versions()
    if not video:
        return skin
    try:
        known = {e["v"]: e.get("at") or e.get("date", "") for e in json.loads(read("resources/whatsnew.json") or "{}").get("versions") or []
                 if isinstance(e, dict) and e.get("v")}
    except ValueError:
        known = {}
    rows = [(known.get(e["v"], ""), 0, i, e) for i, e in enumerate(skin)]
    rows += [(e.get("at") or (e["date"] + "T99") if e["date"] else "", 1, i, e) for i, e in enumerate(video)]
    dated = sorted([r for r in rows if r[0]], key=lambda r: (r[0], r[1], -r[2]), reverse=True)
    return [r[3] for r in dated] + [r[3] for r in rows if not r[0]]


def count_word(n):
    return t(f"{n} change" if n == 1 else f"{n} changes", f"{n} wijziging" if n == 1 else f"{n} wijzigingen")


class WhatsNew(xbmcgui.WindowXMLDialog):
    def onInit(self):
        self.data = versions()
        self.closing, self.shown = False, -1
        rows = []
        for e in self.data:
            li = xbmcgui.ListItem(e["v"], " · ".join(x for x in (e["short"], count_word(len(e["items"]))) if x))
            li.setProperty("tag", e["tag"])
            if e.get("video"):
                li.setProperty("vid", video_name())
            rows.append(li)
        lst = self.getControl(100)
        lst.reset()
        lst.addItems(rows)
        self.setProperty("wn.hint", t("Up / down: choose a version  ·  Right: read  ·  Back: close",
                                      "Omhoog / omlaag: versie kiezen  ·  Rechts: lezen  ·  Terug: sluiten"))
        self.setProperty("wn.hint2", t("OK: more explanation and a picture  ·  Left: versions  ·  Back: close",
                                       "OK: meer uitleg en een afbeelding  ·  Links: versies  ·  Terug: sluiten"))
        self.show_version(0)
        self.setFocusId(100)
        threading.Thread(target=self.follow, daemon=True).start()

    def follow(self):
        """Show the version under the cursor (also when it moves by mouse or page keys)."""
        mon = xbmc.Monitor()
        while not self.closing and not mon.abortRequested():
            try:
                pos = self.getControl(100).getSelectedPosition()
                if pos != self.shown and pos >= 0:
                    self.show_version(pos)
            except Exception:  # noqa: BLE001
                pass
            if mon.waitForAbort(0.15):
                break

    def show_version(self, pos):
        if not 0 <= pos < len(self.data):
            return
        e = self.data[pos]
        self.shown = pos
        self.setProperty("wn.title", f"{video_name()} · {e['v']}" if e.get("video") else f"Lucent {e['v']}")
        self.setProperty("wn.tag", e["tag"])
        self.setProperty("wn.sub", " · ".join(x for x in (e["long"], count_word(len(e["items"]))) if x))
        items = []
        for icon, head, text, extra in e["items"]:
            li = xbmcgui.ListItem(head, text)
            li.setArt({"icon": f"icons/{icon}.png"})
            li.setProperty("more", "1")                  # OK: the change on its own, with more explanation
            items.append(li)
        lst = self.getControl(200)
        lst.reset()
        lst.addItems(items)

    def onClick(self, control_id):
        if control_id == 200:
            pos = self.getControl(200).getSelectedPosition()
            e = self.data[self.shown] if 0 <= self.shown < len(self.data) else None
            if not e or not 0 <= pos < len(e["items"]):
                return
            item = Item("Lucent_WhatsNewItem.xml", xbmcvfs.translatePath(SKIN), "Default", "1080i", version=e, pos=pos)
            item.doModal()
            go, last = item.go, item.pos
            del item
            if go:                                   # 'Try it now': close What's new and go there
                self.closing = True
                self.close()
                xbmc.executebuiltin(go)
            else:
                self.getControl(200).selectItem(last)

    def onAction(self, action):
        if action.getId() in CLOSE:
            if action.getId() in (92, 10) and self.getFocusId() == 200:
                self.setFocusId(100)                 # Back from the changes: to the versions first
                return
            self.closing = True
            self.close()


class Item(xbmcgui.WindowXMLDialog):
    """One change on its own: picture, whole text, steps; Previous / Next go through the changes of this version."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args)
        self.version, self.pos, self.go = kwargs["version"], kwargs["pos"], ""

    def onInit(self):
        self.setProperty("wi.try", t("Try it now", "Nu proberen"))
        self.setProperty("wi.close", t("Close", "Sluiten"))
        self.setProperty("wi.prev", t("Previous", "Vorige"))
        self.setProperty("wi.next", t("Next", "Volgende"))
        self.fill()
        self.setFocusId(9000)

    def fill(self):
        items = self.version["items"]
        icon, head, text, extra = items[self.pos]
        more = extra.get("more_nl" if NL else "more_en") or text
        steps = extra.get("steps_nl" if NL else "steps_en") or []
        name = f"{video_name()} · {self.version['v']}" if self.version.get("video") else f"Lucent {self.version['v']}"
        self.setProperty("wi.ver", name + (f"  ·  {self.version['long']}" if self.version.get("long") else ""))
        self.setProperty("wi.head", head)
        self.setProperty("wi.text", more)
        self.setProperty("wi.icon", f"icons/{icon}.png")
        self.setProperty("wi.image", extra.get("image", ""))
        self.setProperty("wi.caption", "")
        for n in range(1, 5):
            self.setProperty(f"wi.step{n}", steps[n - 1] if n <= len(steps) else "")
        self.setProperty("wi.go", extra.get("go", ""))
        self.setProperty("wi.pos", f"{self.pos + 1} / {len(items)}" if len(items) > 1 else "")
        self.setProperty("wi.hasprev", "1" if self.pos > 0 else "")
        self.setProperty("wi.hasnext", "1" if self.pos < len(items) - 1 else "")

    def onClick(self, control_id):
        if control_id == 10:
            self.go = self.getProperty("wi.go")
            self.close()
        elif control_id in (11, 12):
            self.pos = max(0, min(len(self.version["items"]) - 1, self.pos + (1 if control_id == 12 else -1)))
            self.fill()
            if not self.getProperty("wi.hasnext" if control_id == 12 else "wi.hasprev"):
                self.setFocusId(13)                  # the button just went away: keep the cursor on a button
        elif control_id == 13:
            self.close()

    def onAction(self, action):
        if action.getId() in CLOSE:
            self.close()


if __name__ == "__main__":
    w = WhatsNew("Lucent_WhatsNew.xml", xbmcvfs.translatePath(SKIN), "Default", "1080i")
    w.doModal()
    w.closing = True
    del w
