"""What's new (example A): the versions on the left, the chosen version with every change under its own heading on the right.

The newest versions come from resources/whatsnew.json (a heading and an icon per change, Dutch and English).
Older versions come from addon.xml's <news> (English) or resources/changelog_nl.txt (Dutch); their text is split
into headings where it says 'Heading: ...'.
"""
import html
import json
import re
import threading

import xbmc
import xbmcgui
import xbmcvfs

SKIN = "special://skin/"
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
            items.append((icon_for(head), head[:1].upper() + head[1:], body[:1].upper() + body[1:]))
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
        items = [(it[0], it[1] if NL else it[3], it[2] if NL else it[4]) for it in entry.get("items") or [] if len(it) >= 5]
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
    return out


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
            rows.append(li)
        lst = self.getControl(100)
        lst.reset()
        lst.addItems(rows)
        self.setProperty("wn.hint", t("Up / down: choose a version  ·  Right: read  ·  Back: close",
                                      "Omhoog / omlaag: versie kiezen  ·  Rechts: lezen  ·  Terug: sluiten"))
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
        self.setProperty("wn.title", f"Lucent {e['v']}")
        self.setProperty("wn.tag", e["tag"])
        self.setProperty("wn.sub", " · ".join(x for x in (e["long"], count_word(len(e["items"]))) if x))
        items = []
        for icon, head, text in e["items"]:
            li = xbmcgui.ListItem(head, text)
            li.setArt({"icon": f"icons/{icon}.png"})
            items.append(li)
        lst = self.getControl(200)
        lst.reset()
        lst.addItems(items)

    def onAction(self, action):
        if action.getId() in CLOSE:
            if action.getId() in (92, 10) and self.getFocusId() == 200:
                self.setFocusId(100)                 # Back from the changes: to the versions first
                return
            self.closing = True
            self.close()


if __name__ == "__main__":
    w = WhatsNew("Lucent_WhatsNew.xml", xbmcvfs.translatePath(SKIN), "Default", "1080i")
    w.doModal()
    w.closing = True
    del w
