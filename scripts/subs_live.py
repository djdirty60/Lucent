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
        self.status()
        threading.Thread(target=self.watch, args=(self.gen,), daemon=True).start()

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

    def redraw(self):
        focus_path = ""
        try:
            item = self.getControl(LIST).getSelectedItem()
            focus_path = item.getProperty("path") if item else ""
        except RuntimeError:
            pass
        rows = sorted(self.results, key=self.sort_key)
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
        try:
            ctl = self.getControl(LIST)
            ctl.reset()
            ctl.addItems(items)
            pos = next((i for i, li in enumerate(items) if li.getProperty("path") == focus_path), 0)
            ctl.selectItem(pos)
            if not self.getFocusId() or self.getFocusId() == LIST or not focus_path:
                if items and self.getFocusId() not in (BTN_CLOSE, BTN_OFF, BTN_SEARCH, BTN_SYNC):
                    self.setFocusId(LIST)
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
            if item and not item.getProperty("path").startswith(("ai:", "cached:")):
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
        if action.getId() in (9, 10, 92, 216, 247, 257, 275, 61467, 61448):
            self.finish()


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


def open_list():
    player = xbmc.Player()
    if not player.isPlayingVideo():
        return
    sources = subtitle_addons()
    if not sources:
        xbmcgui.Dialog().notification("Lucent", t("No subtitle add-on installed", "Geen ondertitel-add-on geïnstalleerd"),
                                      xbmcgui.NOTIFICATION_WARNING, 4000)
        return
    paused_by_us = False
    if not cond("Player.Paused"):
        player.pause()
        paused_by_us = True
    languages, mine = search_languages()
    window = SubsWindow("Lucent_Subtitles.xml", skin_path(), "Default", "1080i")
    window.setup(sources, languages, mine)
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


def open_once():
    """Only one list at a time: the automatic search and Kodi's own search can both ask for it within seconds."""
    home = xbmcgui.Window(10000)
    try:
        if time.time() - float(home.getProperty("lucent.subs.open") or 0) < 120:
            return
    except ValueError:
        pass
    home.setProperty("lucent.subs.open", f"{time.time():.1f}")
    try:
        tidy()
        open_list()
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
        open_once()
