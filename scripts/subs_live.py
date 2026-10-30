# -*- coding: utf-8 -*-
"""Lucent: live subtitle list.

RunScript(special://skin/scripts/subs_live.py)        open the list (player menu button, automatic search)
RunScript(special://skin/scripts/subs_live.py,key)    enter / change the Gemini key for AI translations

Kodi's own subtitle search asks one add-on at a time. This window asks every installed subtitle add-on at the same
time: each one gets a hidden list in Lucent_Subtitles.xml that loads by itself; this script reads those lists as they
arrive and keeps one sorted list on screen - your language first, then the subtitles that are in sync with the video,
then the best rated. Every row says which add-on it comes from. The film pauses while the window is open.

With a Gemini key a row "Translate with AI" is added (subs_ai.py): it takes the best English subtitle and lets Google
Gemini translate it into your language, starting where you are watching. A translation is kept for next time.
"""
import json
import os
import sys
import threading
import time
import urllib.parse

import xbmc
import xbmcaddon
import xbmcgui

NL = xbmc.getLanguage(xbmc.ISO_639_1) == "nl"
LIST, BTN_CLOSE, BTN_OFF, BTN_SEARCH, BTN_SYNC = 500, 9501, 9502, 9503, 9504
AUTO_CLOSE = 20                                       # seconds an automatically opened list waits for you
SOURCES = 8
TIMEOUT = 30
KEY_SETTING = "lucent.gemini.key"


def t(en, nl):
    return nl if NL else en


def log(text):
    xbmc.log(f"[skin.lucent] subs_live: {text}", xbmc.LOGINFO)


def rpc(method, params=None):
    req = {"jsonrpc": "2.0", "id": 1, "method": method, "params": params or {}}
    return json.loads(xbmc.executeJSONRPC(json.dumps(req))).get("result", {})


def cond(text):
    return xbmc.getCondVisibility(text)


# ----------------------------------------------------------------------------- languages
LANGS = {  # ISO 639-1 -> (English name as subtitle add-ons use it, Dutch name)
    "nl": ("Dutch", "Nederlands"), "en": ("English", "Engels"), "de": ("German", "Duits"), "fr": ("French", "Frans"),
    "es": ("Spanish", "Spaans"), "it": ("Italian", "Italiaans"), "pt": ("Portuguese", "Portugees"),
    "pb": ("Portuguese (Brazil)", "Portugees (Brazilië)"), "da": ("Danish", "Deens"), "sv": ("Swedish", "Zweeds"),
    "no": ("Norwegian", "Noors"), "fi": ("Finnish", "Fins"), "pl": ("Polish", "Pools"), "tr": ("Turkish", "Turks"),
    "ar": ("Arabic", "Arabisch"), "ru": ("Russian", "Russisch"), "uk": ("Ukrainian", "Oekraïens"), "el": ("Greek", "Grieks"),
    "cs": ("Czech", "Tsjechisch"), "hu": ("Hungarian", "Hongaars"), "ro": ("Romanian", "Roemeens"), "bg": ("Bulgarian", "Bulgaars"),
    "hr": ("Croatian", "Kroatisch"), "sr": ("Serbian", "Servisch"), "sl": ("Slovenian", "Sloveens"), "he": ("Hebrew", "Hebreeuws"),
    "zh": ("Chinese", "Chinees"), "ja": ("Japanese", "Japans"), "ko": ("Korean", "Koreaans"), "hi": ("Hindi", "Hindi"),
    "id": ("Indonesian", "Indonesisch"), "vi": ("Vietnamese", "Vietnamees"), "th": ("Thai", "Thai"), "fa": ("Persian", "Perzisch"),
}
NAME_TO_CODE = {v[0].lower(): k for k, v in LANGS.items()}


def my_code():
    return (xbmc.getLanguage(xbmc.ISO_639_1) or "en").lower()


def full_name(code, fallback):
    code = (code or "").lower()
    if code in LANGS:
        return LANGS[code][1 if NL else 0]
    return fallback or code.upper()


def search_languages():
    """English names to ask the add-ons for: Kodi's subtitle languages + your own language + English."""
    names = []
    try:
        value = rpc("Settings.GetSettingValue", {"setting": "subtitles.languages"}).get("value") or []
        names = [v for v in value if isinstance(v, str)]
    except Exception:  # noqa: BLE001
        pass
    mine = LANGS.get(my_code(), (xbmc.getLanguage(xbmc.ENGLISH_NAME), ""))[0]
    for name in (mine, "English"):
        if name and name not in names:
            names.append(name)
    return names, mine


def subtitle_addons():
    found = rpc("Addons.GetAddons", {"type": "xbmc.subtitle.module", "enabled": True, "properties": ["name"]})
    addons = [(a["addonid"], a.get("name") or a["addonid"]) for a in found.get("addons", [])]
    own = [a for a in addons if a[0] == "service.subtitles.lucent"]
    return (own or addons)[:SOURCES]                   # Lucent Ondertitels asks all sites itself


# ----------------------------------------------------------------------------- the window
class SubsWindow(xbmcgui.WindowXMLDialog):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.sources = []
        self.results = []           # dicts
        self.done = {}
        self.started = time.time()
        self.closing = False
        self.lock = threading.Lock()
        self.ai_row = None
        self.after = ""

    # -- setup
    def setup(self, sources, languages, mine):
        self.sources = sources
        self.mine = mine
        self.languages = languages
        self.gen = 0
        self.make_urls()

    def make_urls(self, searchstring=""):
        params = {"action": "manualsearch" if searchstring else "search", "languages": ",".join(self.languages),
                  "preferredlanguage": self.mine}
        if searchstring:
            params["searchstring"] = searchstring
        query = urllib.parse.urlencode(params)
        self.urls = [f"plugin://{aid}/?{query}" for aid, _name in self.sources]

    def restart(self, searchstring):
        """Zelf zoeken: ask every add-on again with your own words."""
        with self.lock:
            self.gen += 1
            self.results, self.done = [], {}
            self.started = time.time()
        self.make_urls(searchstring)
        for n in range(1, SOURCES + 1):
            self.clearProperty(f"src.{n}")
        xbmc.sleep(200)
        self.setProperty("busy", "1")
        self.setProperty("empty", t("Searching…", "Zoeken…"))
        self.redraw()
        for n, url in enumerate(self.urls, start=1):
            self.setProperty(f"src.{n}", url)
        threading.Thread(target=self.watch, args=(self.gen,), daemon=True).start()

    def onInit(self):
        title = xbmc.getInfoLabel("VideoPlayer.TVShowTitle")
        if title:
            title += f"  ·  S{xbmc.getInfoLabel('VideoPlayer.Season')} E{xbmc.getInfoLabel('VideoPlayer.Episode')}"
        else:
            title = xbmc.getInfoLabel("VideoPlayer.Title")
            year = xbmc.getInfoLabel("VideoPlayer.Year")
            title += f" ({year})" if year else ""
        self.setProperty("title", title)
        self.setProperty("busy", "1")
        self.setProperty("empty", t("Searching…", "Zoeken…"))
        for n, url in enumerate(self.urls, start=1):
            self.setProperty(f"src.{n}", url)      # the hidden lists start loading now, all at once
        self.redraw()                                   # the film's own rows (on / off, built-in subtitles) at once
        threading.Thread(target=self.watch, args=(self.gen,), daemon=True).start()
        threading.Thread(target=self.guard, daemon=True).start()

    def status(self):
        total = len(self.sources)
        ready = len(self.done)
        found = len(self.results)
        if ready < total:
            text = t(f"{ready} of {total} services answered  ·  {found} found",
                     f"{ready} van {total} diensten klaar  ·  {found} gevonden")
        else:
            text = t(f"{found} found", f"{found} gevonden")
            self.clearProperty("busy")
            if not found:
                self.setProperty("empty", t("No subtitles found.", "Geen ondertitels gevonden."))
        self.setProperty("status", text)

    # -- read the hidden lists as they fill
    def watch(self, gen=0):
        monitor = xbmc.Monitor()
        seen_busy = set()
        while not self.closing and gen == self.gen and not monitor.abortRequested() and len(self.done) < len(self.sources):
            for n in range(1, len(self.sources) + 1):
                if n in self.done:
                    continue
                cid = 600 + n
                updating = cond(f"Container({cid}).IsUpdating")
                count = int(xbmc.getInfoLabel(f"Container({cid}).NumItems") or 0)
                if updating:
                    seen_busy.add(n)
                    continue
                waited = time.time() - self.started
                if count > 0 or (n in seen_busy and waited > 1.5) or waited > TIMEOUT:
                    if gen != self.gen:
                        return
                    self.read(n, cid, count, timed_out=waited > TIMEOUT and not count)
            if monitor.waitForAbort(0.3):
                break
        if not self.closing and gen == self.gen:
            self.status()

    def guard(self):
        """The video stopped (or another one started) while the list is open: close it, so it can be opened again."""
        monitor, gone = xbmc.Monitor(), 0
        self.touched = time.time()
        while not self.closing and not monitor.abortRequested():
            if getattr(self, "auto", False) and time.time() - self.touched > AUTO_CLOSE:
                log("opened by itself and not used: closing")
                self.finish()
                return
            gone = gone + 1 if not xbmc.Player().isPlayingVideo() else 0
            if gone >= 4:
                xbmc.log("[skin.lucent] subs_live: the video stopped - closing the list", xbmc.LOGINFO)
                self.close()
                return
            if monitor.waitForAbort(0.5):
                return

    def read(self, n, cid, count, timed_out=False):
        aid, name = self.sources[n - 1]
        rows = []
        for i in range(count):
            base = f"Container({cid}).ListItemAbsolute({i})."
            path = xbmc.getInfoLabel(base + "FileNameAndPath")
            if not path:
                continue
            code = (xbmc.getInfoLabel(base + "Thumb") or "").lower()
            code = code.rsplit("/", 1)[-1].split(".")[0][:3] if code else ""
            lang = xbmc.getInfoLabel(base + "Label")
            if code not in LANGS:
                code = NAME_TO_CODE.get(lang.lower(), code)
            try:
                rating = int(float(xbmc.getInfoLabel(base + "Icon").rsplit("/", 1)[-1].split(".")[0] or 0))
            except ValueError:
                rating = 0
            rows.append({
                "path": path, "code": code, "lang": full_name(code, lang), "release": xbmc.getInfoLabel(base + "Label2"),
                "source": name, "sync": xbmc.getInfoLabel(base + "Property(sync)") == "true",
                "hi": xbmc.getInfoLabel(base + "Property(hearing_imp)") == "true", "rating": rating,
            })
        log(f"{aid}: {len(rows)} subtitles{' (no answer in time)' if timed_out else ''}")
        with self.lock:
            self.done[n] = len(rows)
            self.results.extend(rows)
            self.redraw()

    # -- the visible list
    def sort_key(self, r):
        mine = r["code"] == my_code()
        return (not mine, r["code"] != "en", not r["sync"], -r["rating"], r["lang"], r["release"].lower())

    def local_items(self, fresh=False):
        """Above the found subtitles: switch subtitles on / off, and the film's own subtitles in your languages (the
        others behind one row). Read once and kept: asking the player again on every redraw is not needed."""
        if not fresh and getattr(self, "_local", None) is not None:
            return self._local
        items = []
        on = cond("VideoPlayer.SubtitlesEnabled")
        li = xbmcgui.ListItem(t("Subtitles: on", "Ondertiteling: aan") if on else t("Subtitles: off", "Ondertiteling: uit"))
        li.setLabel2(t("Choose to switch them off", "Kies om ze uit te zetten") if on else t("Choose to switch them on", "Kies om ze aan te zetten"))
        li.setProperty("code", "CC")
        li.setProperty("pillcol", "FF2E8B5E" if on else "33FFFFFF")
        li.setProperty("source", "Kodi")
        li.setProperty("path", "toggle:")
        items.append(li)
        try:
            props = rpc("Player.GetProperties", {"playerid": 1, "properties": ["subtitles", "currentsubtitle"]})
        except Exception:  # noqa: BLE001
            props = {}
        current = (props.get("currentsubtitle") or {}).get("index", -1)
        wanted = {NAME_TO_CODE.get(n.lower(), "") for n in self.languages} | {my_code()}
        others = []
        for sub in props.get("subtitles") or []:
            code = (sub.get("language") or "").lower()[:3]
            code2 = {"dut": "nl", "nld": "nl", "eng": "en", "ger": "de", "deu": "de", "fre": "fr", "fra": "fr", "spa": "es",
                     "ita": "it", "por": "pt", "ukr": "uk", "rus": "ru", "pol": "pl", "swe": "sv", "dan": "da", "nor": "no",
                     "fin": "fi", "tur": "tr", "ara": "ar"}.get(code, code[:2])
            li = xbmcgui.ListItem(full_name(code2, sub.get("language") or t("Unknown", "Onbekend")))
            flags = [sub.get("name") or ""]
            if sub.get("isforced") and "forc" not in flags[0].lower() and "geforc" not in flags[0].lower():
                flags.append(t("forced", "geforceerd"))
            if sub.get("isimpaired"):
                flags.append(t("hearing impaired", "slechthorend"))
            li.setLabel2("  ·  ".join(f for f in flags if f) or t("Subtitle in the film", "Ondertitel in de film"))
            li.setProperty("code", (code2 or "?").upper()[:3])
            li.setProperty("pillcol", "FF2E8B5E" if code2 == my_code() else "33FFFFFF")
            li.setProperty("source", t("In the film", "In de film"))
            if on and sub.get("index") == current:
                li.setProperty("badges", t("✓ showing now", "✓ staat nu aan"))
            li.setProperty("path", f"stream:{sub.get('index')}")
            if code2 in wanted or (on and sub.get("index") == current):
                items.append(li)
            else:
                others.append(li)
        if others:
            li = xbmcgui.ListItem(t(f"Other languages in the film ({len(others)})", f"Andere talen in de film ({len(others)})"))
            li.setLabel2(", ".join(o.getLabel() for o in others[:6]) + ("…" if len(others) > 6 else ""))
            li.setProperty("code", "+")
            li.setProperty("pillcol", "33FFFFFF")
            li.setProperty("source", t("In the film", "In de film"))
            li.setProperty("path", "otherstreams:")
            items.append(li)
        self._local, self._others = items, others
        return items

    def redraw(self):
        focus_path = ""
        try:
            item = self.getControl(LIST).getSelectedItem()
            focus_path = item.getProperty("path") if item else ""
        except RuntimeError:
            pass
        rows = sorted(self.results, key=self.sort_key)
        local = self.local_items()
        items = []
        if self.ai_possible(rows):
            ai = xbmcgui.ListItem(t(f"Translate into {LANGS.get(my_code(), ('',''))[0] or 'your language'} with AI",
                                    f"Vertalen naar het {full_name(my_code(), '')} met AI"))
            ai.setLabel2(t("Google Gemini translates the best English subtitle, from where you are watching",
                           "Google Gemini vertaalt de beste Engelse ondertitel, vanaf waar je nu kijkt"))
            ai.setProperty("code", "AI")
            ai.setProperty("pillcol", "FF7B5CFF")
            ai.setProperty("source", "Gemini")
            ai.setProperty("path", "ai:")
            ai.setProperty("mine", "1")
            items.append(ai)
        cached = ai_cached_path()
        if cached:
            li = xbmcgui.ListItem(full_name(my_code(), "") + t("  (AI translation)", "  (AI-vertaling)"))
            li.setLabel2(t("Translated before - opens at once", "Eerder vertaald - opent meteen"))
            li.setProperty("code", my_code().upper())
            li.setProperty("pillcol", "FF7B5CFF")
            li.setProperty("source", t("Kept", "Bewaard"))
            li.setProperty("path", "cached:" + cached)
            li.setProperty("mine", "1")
            items.insert(0, li)
        for r in rows:
            li = xbmcgui.ListItem(r["lang"])
            li.setLabel2(r["release"])
            li.setProperty("code", (r["code"] or "?").upper()[:3])
            li.setProperty("pillcol", "FF2E8B5E" if r["code"] == my_code() else "33FFFFFF")
            li.setProperty("source", r["source"])
            badges = []
            if r["sync"]:
                badges.append(t("✓ in sync", "✓ loopt gelijk"))
            if r["hi"]:
                badges.append(t("CC hearing impaired", "CC slechthorend"))
            if r["rating"]:
                badges.append("★" * min(r["rating"], 5))
            li.setProperty("badges", "   ".join(badges))
            li.setProperty("path", r["path"])
            li.setProperty("mine", "1" if r["code"] == my_code() else "")
            items.append(li)
        first_found = len(local) if items else 0          # the cursor starts on the first found subtitle
        self.setProperty("onlylocal", "" if items else "1")     # "Searching…" / "None found" under the film's own rows
        items = local + items
        try:
            ctl = self.getControl(LIST)
            ctl.reset()
            ctl.addItems(items)
            pos = next((i for i, li in enumerate(items) if li.getProperty("path") == focus_path), first_found)
            ctl.selectItem(pos)
            if items and not getattr(self, "moved", False) and self.getFocusId() != LIST:
                self.setFocusId(LIST)                 # the first results: straight into the list
            elif not items and self.getFocusId() not in (BTN_CLOSE, BTN_OFF, BTN_SEARCH, BTN_SYNC):
                self.setFocusId(BTN_CLOSE)            # an empty list cannot hold the focus
        except RuntimeError:
            pass
        self.status()

    def ai_possible(self, rows):
        if not xbmc.getInfoLabel(f"Skin.String({KEY_SETTING})") or my_code() == "en":
            return False
        return any(r["code"] == "en" for r in rows)

    # -- choosing
    def onClick(self, cid):
        if cid == BTN_CLOSE:
            self.finish()
        elif cid == BTN_SYNC:
            item = self.getControl(LIST).getSelectedItem()
            if item and not item.getProperty("path").startswith(("ai:", "cached:", "toggle:", "stream:", "otherstreams:")):
                self.choose(item.getProperty("path"), force_sync=True)
        elif cid == BTN_SEARCH:
            default = xbmc.getInfoLabel("VideoPlayer.TVShowTitle") or xbmc.getInfoLabel("VideoPlayer.Title")
            words = xbmcgui.Dialog().input(t("Search subtitles for", "Ondertitels zoeken voor"), default).strip()
            if words:
                self.restart(words)
        elif cid == BTN_OFF:
            xbmc.Player().showSubtitles(False)
            self.finish()
        elif cid == LIST:
            item = self.getControl(LIST).getSelectedItem()
            if item:
                self.choose(item.getProperty("path"))

    def choose(self, path, force_sync=False):
        player = xbmc.Player()
        if path == "toggle:":
            player.showSubtitles(not cond("VideoPlayer.SubtitlesEnabled"))
            xbmc.sleep(300)
            self.local_items(fresh=True)
            self.redraw()
            return
        if path == "otherstreams:":
            others = getattr(self, "_others", [])
            pick = xbmcgui.Dialog().select(t("Subtitles in the film", "Ondertitels in de film"),
                                           [f"{o.getLabel()}  ·  {o.getLabel2()}" for o in others])
            if pick < 0:
                return
            path = others[pick].getProperty("path")
        if path.startswith("stream:"):
            try:
                rpc("Player.SetSubtitle", {"playerid": 1, "subtitle": int(path[7:]), "enable": True})
            except Exception as error:  # noqa: BLE001
                log(f"stream: {error}")
            self.finish()
            return
        if path.startswith("cached:"):
            player.setSubtitles(path[7:])
            self.finish()
            return
        if path == "ai:":
            english = [r for r in sorted(self.results, key=self.sort_key) if r["code"] == "en"]
            if not english:
                return
            self.setProperty("busy", "1")
            local = download(english[0]["path"])
            self.clearProperty("busy")
            if not local:
                xbmcgui.Dialog().notification("Lucent", t("Download failed", "Downloaden mislukt"), xbmcgui.NOTIFICATION_WARNING, 3000)
                return
            self.after = local                      # translated after the window is closed and the film plays on
            self.finish()
            return
        self.setProperty("busy", "1")
        local = download(path)
        if not local:
            self.clearProperty("busy")
            xbmcgui.Dialog().notification("Lucent", t("Download failed", "Downloaden mislukt"), xbmcgui.NOTIFICATION_WARNING, 3000)
            return
        row = next((r for r in self.results if r["path"] == path), {})
        auto = not xbmc.getCondVisibility("Skin.HasSetting(lucent.subs.autosync.off)")
        if force_sync or (auto and row and not row.get("sync")):
            local = self.synced(local, path) or local
        self.clearProperty("busy")
        player.setSubtitles(local)
        player.showSubtitles(True)
        self.finish()

    def synced(self, local, path):
        """Line this subtitle up with one that is marked 'in sync' (any language); '' when not possible / not needed."""
        refs = [r for r in sorted(self.results, key=lambda r: (r["code"] != "en", -r["rating"]))
                if r.get("sync") and r["path"] != path]
        if not refs:
            if path:
                xbmcgui.Dialog().notification("Lucent", t("No subtitle marked in sync to compare with", "Geen gelijklopende ondertitel om mee te vergelijken"),
                                              xbmcgui.NOTIFICATION_INFO, 3000)
            return ""
        try:
            import subs_ai
            import subs_sync
            text = subs_ai.read_text(local)               # read now: the add-on may reuse its download folder
            ref_local = download(refs[0]["path"])
            if not ref_local:
                return ""
            out, message = subs_sync.sync_text(text, subs_ai.read_text(ref_local), "live")
        except Exception as error:  # noqa: BLE001
            log(f"sync: {error}")
            return ""
        if not out and local:                             # keep our own copy: the add-on's file may be gone
            keep = os.path.join(subs_ai.DIR, f"keep.{int(time.time())}.srt")
            try:
                os.makedirs(subs_ai.DIR, exist_ok=True)
                with open(keep, "w", encoding="utf-8") as fh:
                    fh.write(text)
                out = keep
            except Exception:  # noqa: BLE001
                out = ""
        xbmcgui.Dialog().notification("Lucent", message, xbmcgui.NOTIFICATION_INFO, 4000)
        return out

    def finish(self):
        self.closing = True
        self.close()

    def onAction(self, action):
        self.touched = time.time()                    # you are using the list: it does not close by itself
        aid = action.getId()
        if aid in (9, 10, 92, 216, 247, 257, 275, 61467, 61448):
            self.finish()
            return
        if aid in (1, 2, 3, 4):                       # left / right / up / down
            self.moved = True
            focus = self.getFocusId()
            if focus not in (BTN_CLOSE, BTN_OFF, BTN_SEARCH, BTN_SYNC) and not self.list_size():
                self.setFocusId(BTN_CLOSE)            # nothing in the list (yet): never stuck, go to the buttons

    def list_size(self):
        try:
            return self.getControl(LIST).size()
        except RuntimeError:
            return 0


def download(path):
    """Ask the add-on for this subtitle: it answers with a list holding the local file."""
    try:
        files = rpc("Files.GetDirectory", {"directory": path, "media": "files"}).get("files") or []
    except Exception as error:  # noqa: BLE001
        log(f"download: {error}")
        return ""
    for f in files:
        name = f.get("file") or ""
        if name and not name.startswith("plugin://"):
            return name
    return ""


def ai_cached_path():
    try:
        import subs_ai
        return subs_ai.cached_for_current(my_code())
    except Exception:  # noqa: BLE001
        return ""


def skin_path():
    return xbmcaddon.Addon("skin.lucent").getAddonInfo("path")


def open_list(auto=False):
    player = xbmc.Player()
    if not player.isPlayingVideo():
        return
    sources = subtitle_addons()
    if not sources:
        xbmcgui.Dialog().notification("Lucent", t("No subtitle add-on installed", "Geen ondertitel-add-on geïnstalleerd"),
                                      xbmcgui.NOTIFICATION_WARNING, 4000)
        return
    paused_by_us = False
    # opened by hand: hold the film while you choose. Not when the list opens by itself: pausing a film that has just
    # started makes Seren think it failed, and Seren starts it all over again.
    if not auto and not cond("Player.Paused"):
        player.pause()
        paused_by_us = True
    languages, mine = search_languages()
    window = SubsWindow("Lucent_Subtitles.xml", skin_path(), "Default", "1080i")
    window.setup(sources, languages, mine)
    window.auto = auto                                # opened by itself: closes after AUTO_CLOSE s when you do nothing
    after = ""
    try:
        window.doModal()
        after = window.after
    finally:
        window.closing = True
        del window
        if paused_by_us and cond("Player.Paused"):
            player.pause()
    xbmcgui.Window(10000).clearProperty("lucent.subs.open")     # the list is closed: it may be opened again
    if after:
        import subs_ai
        subs_ai.translate_and_load(after, my_code())


def enter_key():
    old = xbmc.getInfoLabel(f"Skin.String({KEY_SETTING})")
    key = xbmcgui.Dialog().input(t("Gemini API key (free at aistudio.google.com)", "Gemini-sleutel (gratis op aistudio.google.com)"),
                                 old).strip()
    xbmc.executebuiltin(f"Skin.SetString({KEY_SETTING},{key})" if key else f"Skin.Reset({KEY_SETTING})")


def settled(monitor, player):
    """Automatic opening: wait until the film really plays (Seren checks the first seconds of playback)."""
    end = time.time() + 90
    while time.time() < end:
        if monitor.waitForAbort(1) or not player.isPlayingVideo():
            return False
        try:
            if player.getTime() >= 5 and not cond("Player.Paused | Window.IsActive(busydialog) | Window.IsActive(busydialognocancel)"):
                return True
        except RuntimeError:
            pass
    return False


def open_once(auto=False):
    """Only one list at a time: the automatic search and Kodi's own search can both ask for it within seconds."""
    home = xbmcgui.Window(10000)
    try:
        recent = time.time() - float(home.getProperty("lucent.subs.open") or 0) < 120
    except ValueError:
        recent = False
    if recent and cond("Window.IsVisible(Lucent_Subtitles.xml)"):
        return                                             # really open already (a stale mark no longer blocks it)
    if auto and not settled(xbmc.Monitor(), xbmc.Player()):
        return
    home.setProperty("lucent.subs.open", f"{time.time():.1f}")
    try:
        tidy()
        open_list(auto)
    finally:
        home.clearProperty("lucent.subs.open")


def tidy():
    """Remove our own synced copies and half-finished files older than two weeks (the AI translations stay)."""
    import subs_ai
    try:
        old = time.time() - 14 * 86400
        for name in os.listdir(subs_ai.DIR):
            full = os.path.join(subs_ai.DIR, name)
            if (name.startswith(("sync.", "keep.")) or name.endswith(".part")) and os.path.getmtime(full) < old:
                os.remove(full)
    except OSError:
        pass


if __name__ == "__main__":
    arg = sys.argv[1] if len(sys.argv) > 1 else "open"
    if arg == "key":
        enter_key()
    else:
        open_once(auto=arg == "auto")
