# -*- coding: utf-8 -*-
"""Live subtitle list (taken over from the Lucent skin).

RunPlugin(plugin://plugin.video.lucent/?action=subtitles)        open the list (player menu button)
action=subs_auto / subs_background / subs_prefetch                    used by the service
action=subs_key / subs_mode / subs_audio                              AI service and key, automatic search, spoken language

Kodi's own subtitle search asks one add-on at a time. This window asks every installed subtitle add-on at the same
time: each one gets a hidden list in lucent_subtitles.xml that loads by itself; this script reads those lists as they
arrive and keeps one sorted list on screen - your language first, then the subtitles that are in sync with the video,
then the best rated. Every row says which add-on it comes from. The film pauses while the window is open.

With an AI key a row "Translate with AI" is added (subs_ai.py): it takes the best English subtitle and lets the chosen
service (Google Gemini, OpenRouter or Claude) translate it into your language, starting where you are watching. A translation is kept for next time.
"""
import json
import os
import threading
import time
import urllib.parse

import subconf
import xbmc
import xbmcgui

NL = xbmc.getLanguage(xbmc.ISO_639_1) == "nl"
LIST, BTN_CLOSE, BTN_OFF, BTN_SEARCH, BTN_SYNC, BTN_TIME = 500, 9501, 9502, 9503, 9504, 9505
AUTO_CLOSE = 20                                       # seconds an automatically opened list waits for you
SOURCES = 8
TIMEOUT = 30
KEY_SETTING = "lucent.gemini.key"


def t(en, nl):
    return nl if NL else en


def log(text):
    xbmc.log(f"[lucent.video] subtitles: {text}", xbmc.LOGINFO)


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


_MINE = {}


def my_code():
    """Your subtitle language: Kodi's 'Preferred subtitle language' (Settings > Player > Language) when that is a real
    language, otherwise the language of the Kodi interface. Works for every language."""
    if "code" not in _MINE:
        code = ""
        try:
            pref = rpc("Settings.GetSettingValue", {"setting": "locale.subtitlelanguage"}).get("value")
            if isinstance(pref, str) and pref not in ("", "default", "original", "none", "forced_only"):
                code = NAME_TO_CODE.get(pref.lower()) or (xbmc.convertLanguage(pref, xbmc.ISO_639_1) or "").lower()
        except Exception:  # noqa: BLE001
            code = ""
        _MINE["code"] = code if len(code) == 2 else (xbmc.getLanguage(xbmc.ISO_639_1) or "en").lower()
    return _MINE["code"]


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
    mine = LANGS.get(my_code(), (xbmc.convertLanguage(my_code(), xbmc.ENGLISH_NAME) or xbmc.getLanguage(xbmc.ENGLISH_NAME), ""))[0]
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
        try:
            import subs_extra
            self.pref = subs_extra.preference()
        except Exception:  # noqa: BLE001
            self.pref = None
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
        for key, en, nl in (("heading", "Subtitles", "Ondertitels"), ("b_close", "Close", "Sluiten"), ("b_off", "Turn off subtitles", "Ondertitels uit"),
                            ("b_search", "Search yourself", "Zelf zoeken"), ("b_sync", "Sync", "Gelijkzetten"), ("b_time", "Time & look", "Tijd & opmaak"),
                            ("busyword", "Searching…", "Zoeken…")):
            self.setProperty(key, t(en, nl))
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
            if getattr(self, "auto", False) and not any(r["code"] == my_code() for r in self.results) and not getattr(self, "wished", False):
                self.wished = True
                try:
                    import subs_extra
                    subs_extra.want(my_code())             # check again later, and say so when one turns up
                except Exception as error:  # noqa: BLE001
                    log(f"wish list: {error}")
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
                xbmc.log("[lucent.video] subs_live: the video stopped - closing the list", xbmc.LOGINFO)
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
        rank = 2
        if mine and getattr(self, "pref", None):
            import subs_extra
            rank = subs_extra.pref_rank(*subs_extra.split_label2(r["release"]), self.pref)
        return (not mine, rank, r["code"] != "en", not r["sync"], -r["rating"], r["lang"], r["release"].lower())

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
            service = ai_name()
            ai.setLabel2(t(f"{service} translates the best English subtitle, from where you are watching",
                           f"{service} vertaalt de beste Engelse ondertitel, vanaf waar je nu kijkt"))
            ai.setProperty("code", "AI")
            ai.setProperty("pillcol", "FF7B5CFF")
            ai.setProperty("source", service)
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
            elif not items and self.getFocusId() not in (BTN_CLOSE, BTN_OFF, BTN_SEARCH, BTN_SYNC, BTN_TIME):
                self.setFocusId(BTN_CLOSE)            # an empty list cannot hold the focus
        except RuntimeError:
            pass
        self.status()

    def ai_possible(self, rows):
        if not ai_ready() or my_code() == "en":
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
        elif cid == BTN_TIME:
            import subs_extra
            subs_extra.menu(my_code())
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
            english = sorted([r for r in sorted(self.results, key=self.sort_key) if r["code"] == "en"],
                             key=lambda r: r.get("hi", False))          # a normal one before a hearing-impaired one
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
        auto = not subconf.on("lucent.subs.autosync.off")
        if force_sync or (auto and row and not row.get("sync")):
            local = self.synced(local, path) or local
        self.clearProperty("busy")
        code = row.get("code") or my_code()
        self.load_after = (local, code)            # switched on after the window closes (open_list)
        try:
            import subs_extra
            if code == my_code():
                release, source = subs_extra.split_label2(row.get("release", ""))
                subs_extra.remember(release, source)
                subs_extra.unwant()
        except Exception as error:  # noqa: BLE001
            log(f"remember: {error}")
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
            if focus not in (BTN_CLOSE, BTN_OFF, BTN_SEARCH, BTN_SYNC, BTN_TIME) and not self.list_size():
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


def activate(local, mine="", seconds=30):
    """Load a subtitle file and make sure it really is the one shown. player.setSubtitles() only adds the file:
    a stream Kodi chose before (for example a Russian 'forced' track the film marks as default) can stay selected,
    and Seren or Kodi can switch back a few seconds later. So select it ourselves and keep an eye on it for a while."""
    player, monitor = xbmc.Player(), xbmc.Monitor()
    try:
        import subs_extra
        local = subs_extra.with_offset(local)            # a time you set for this video before
    except Exception as error:  # noqa: BLE001
        log(f"offset: {error}")
    player.setSubtitles(local)
    player.showSubtitles(True)
    stem = os.path.splitext(os.path.basename(local))[0].lower()
    steady, end = 0, time.time() + seconds
    while time.time() < end and steady < 3:
        if monitor.waitForAbort(1.5) or not player.isPlayingVideo():
            return False
        try:
            props = rpc("Player.GetProperties", {"playerid": 1, "properties": ["subtitles", "currentsubtitle", "subtitleenabled"]})
        except Exception:  # noqa: BLE001
            continue
        subs = props.get("subtitles") or []
        named = [x for x in subs if stem and stem in (x.get("name") or "").lower()]
        def code_of(x):
            c = (x.get("language") or "").lower()
            return {"dut": "nl", "nld": "nl"}.get(c) or NAME_TO_CODE.get(c) or (xbmc.convertLanguage(c, xbmc.ISO_639_1) or "").lower() or c[:2]
        same = [x for x in subs if mine and code_of(x) == mine and not x.get("isforced")]
        pool = named or same
        if not pool:
            continue
        ours = max(pool, key=lambda x: x.get("index", -1))       # a file added just now comes last
        current = props.get("currentsubtitle") or {}
        if current.get("index") == ours.get("index") and props.get("subtitleenabled"):
            steady += 1
            continue
        steady = 0
        log(f"subtitle {current.get('language')} / {current.get('index')} was shown, switching to {ours.get('language')} / {ours.get('index')}")
        rpc("Player.SetSubtitle", {"playerid": 1, "subtitle": ours["index"], "enable": True})
    return steady >= 3


def ai_cached_path():
    try:
        import subs_ai
        return subs_ai.cached_for_current(my_code())
    except Exception:  # noqa: BLE001
        return ""


def skin_path():
    import dialogs
    return dialogs.PATH


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
    window = SubsWindow("lucent_subtitles.xml", skin_path(), "Default", "1080i")
    window.setup(sources, languages, mine)
    window.auto = auto                                # opened by itself: closes after AUTO_CLOSE s when you do nothing
    after, load_after = "", None
    try:
        window.doModal()
        after = window.after
        load_after = getattr(window, "load_after", None)
    finally:
        window.closing = True
        del window
        if paused_by_us and cond("Player.Paused"):
            player.pause()
    xbmcgui.Window(10000).clearProperty("lucent.subs.open")     # the list is closed: it may be opened again
    if load_after:
        activate(load_after[0], load_after[1], 20)
    if after:
        import subs_ai
        subs_ai.translate_and_load(after, my_code())


def ai_name():
    try:
        import subs_ai
        return subs_ai.provider_name()
    except Exception:  # noqa: BLE001
        return "AI"


def ai_ready():
    try:
        import subs_ai
        return subs_ai.has_key()
    except Exception:  # noqa: BLE001
        return bool(subconf.text(KEY_SETTING))


def enter_key():
    """Settings > Subtitles and sound > AI translation: choose the service, then its key (and for OpenRouter / Claude the model)."""
    import subs_ai
    order = ["gemini", "openrouter", "claude"]
    hints = {"gemini": t("free key at aistudio.google.com", "gratis sleutel op aistudio.google.com"),
             "openrouter": t("one key for many models, openrouter.ai", "één sleutel voor veel modellen, openrouter.ai"),
             "claude": t("Anthropic, key at console.anthropic.com", "Anthropic, sleutel op console.anthropic.com")}
    current = subs_ai.provider()
    rows = []
    for p in order:
        name, key_setting, _m, _d = subs_ai.PROVIDERS[p]
        state = t("key set", "sleutel ingesteld") if subs_ai.skin_string(key_setting) else t("no key", "geen sleutel")
        rows.append(xbmcgui.ListItem(("✓ " if p == current else "") + name, f"{hints[p]}  ·  {state}"))
    pick = xbmcgui.Dialog().select(t("AI translation: which service?", "AI-vertaling: welke dienst?"), rows, useDetails=True,
                                   preselect=order.index(current))
    if pick < 0:
        return
    p = order[pick]
    name, key_setting, model_setting, default_model = subs_ai.PROVIDERS[p]
    subconf.put(subs_ai.PROVIDER_SETTING, p)
    old = subs_ai.skin_string(key_setting)
    key = xbmcgui.Dialog().input(t(f"{name} key (empty = remove)", f"{name}-sleutel (leeg = verwijderen)"), old).strip()
    subconf.put(key_setting, key)
    if key and model_setting:
        model = xbmcgui.Dialog().input(t(f"Model (empty = {default_model})", f"Model (leeg = {default_model})"),
                                       subs_ai.skin_string(model_setting)).strip()
        subconf.put(model_setting, model)


def choose_audio():
    """Settings > Subtitles and sound > Spoken language: a first and a second choice for the sound (subtitles.fix_audio)."""
    order = ["nl", "en"] + sorted((k for k in LANGS if k not in ("nl", "en", "pb")), key=lambda k: full_name(k, k))
    picks = []
    for n, head in enumerate((t("Spoken language: first choice", "Gesproken taal: eerste keuze"),
                              t("Spoken language: second choice", "Gesproken taal: tweede keuze"))):
        none = t("No preference (Kodi decides)", "Geen voorkeur (Kodi beslist)") if n == 0 else t("No second choice", "Geen tweede keuze")
        options = [k for k in order if k not in picks]
        current = subconf.text(f"lucent.audio.lang{n + 1}")
        rows = [none] + [full_name(k, k.upper()) for k in options]
        pre = options.index(current) + 1 if current in options else 0
        i = xbmcgui.Dialog().select(head, rows, preselect=pre)
        if i < 0:
            return
        if i == 0:
            break
        picks.append(options[i - 1])
    for n in (1, 2):
        value = picks[n - 1] if len(picks) >= n else ""
        subconf.put(f"lucent.audio.lang{n}", value)
    text = " / ".join(full_name(k, k.upper()) for k in picks)   # no comma: Skin.SetString would split on it
    subconf.put("lucent.audio.label", text)
    subconf.publish()


def choose_mode():
    """Settings > Subtitles and sound > Search automatically: off / show the list / pick it myself in the background."""
    options = [("off", t("Off", "Uit"), t("Nothing happens when a video starts", "Er gebeurt niets als een video start")),
               ("list", t("Show the list", "Lijst laten zien"),
                t("The subtitle list opens and you choose", "De ondertitellijst gaat open en jij kiest")),
               ("background", t("Choose by itself, in the background", "Zelf kiezen, op de achtergrond"),
                t("The best subtitle in your language is turned on without a window. Nothing found: nothing is shown",
                  "De best passende ondertitel in jouw taal gaat aan, zonder venster. Niets gevonden: je ziet niets")),
               ("background_ai", t("Choose by itself, otherwise AI", "Zelf kiezen, anders AI-vertaling"),
                t("As above; nothing in your language but an English one: AI translates it (needs an AI key)",
                  "Zoals hierboven; niets in jouw taal maar wel Engels: de AI vertaalt hem (AI-sleutel nodig)"))]
    if not subconf.on("nuvio.autosubs"):
        now = "off"
    else:
        now = "list"
        if subconf.text("lucent.subs.mode") == "background":
            now = "background_ai" if subconf.on("lucent.subs.bg.ai") else "background"
    rows = [xbmcgui.ListItem(("✓ " if k == now else "") + label, hint) for k, label, hint in options]
    pick = xbmcgui.Dialog().select(t("Search subtitles automatically", "Automatisch ondertitels zoeken"), rows,
                                   useDetails=True, preselect=[o[0] for o in options].index(now))
    if pick < 0:
        return
    key = options[pick][0]
    subconf.put("nuvio.autosubs", key != "off")
    if key != "off":
        subconf.set_mode({"list": 0, "background": 1, "background_ai": 2}[key])
    subconf.publish()
    if key == "background_ai" and not ai_ready():
        if xbmcgui.Dialog().yesno(t("AI translation", "AI-vertaling"),
                                  t("There is no AI key yet. Set one now?", "Er is nog geen AI-sleutel. Nu instellen?")):
            enter_key()


def lang_of(entry):
    """Language code of a search result read through JSON-RPC (label = language name, thumbnail = its code)."""
    label = (entry.get("label") or "").strip().lower()
    if label in NAME_TO_CODE:
        return NAME_TO_CODE[label]
    for k, v in LANGS.items():
        if label == v[1].lower():
            return k
    thumb = (entry.get("thumbnail") or (entry.get("art") or {}).get("thumb") or "").lower()
    thumb = urllib.parse.unquote(thumb.replace("image://", "")).strip("/").rsplit("/", 1)[-1].split(".")[0]
    return thumb[:2] if thumb[:2] in LANGS or len(thumb) == 2 else ""


def use_prefetched(mine):
    """The subtitle for this episode was got ready during the previous one: switch it on at once."""
    try:
        import subs_extra
        entry = subs_extra.prefetched(mine)
    except Exception as error:  # noqa: BLE001
        log(f"prefetched: {error}")
        return False
    if not entry:
        return False
    log(f"ready from the previous episode: {entry['path']}")
    xbmcgui.Dialog().notification("Lucent", t(f"{full_name(mine, mine.upper())} subtitle on", f"Ondertitel ({full_name(mine, mine.upper())}) staat aan"),
                                  xbmcgui.NOTIFICATION_INFO, 3000)
    activate(entry["path"], mine, 30)          # in this script: a thread would stop when the script ends
    return True


def background():
    """A video started without a subtitle in your language: ask the subtitle add-ons quietly, download the best
    match in your language and switch it on. Nothing in your language: nothing is shown at all - unless
    'and otherwise AI' is chosen and there is an English one: then that one is translated."""
    import subs_extra
    player, monitor = xbmc.Player(), xbmc.Monitor()
    if not settled(monitor, player):
        return
    try:
        started_with = player.getPlayingFile()
    except RuntimeError:
        return
    mine = my_code()
    try:
        import subwatch
        if subwatch.audio_is_mine():
            log("background: the sound is in your language - no subtitle")
            return
    except Exception as error:  # noqa: BLE001
        log(f"same-language check: {error}")
    if use_prefetched(mine):
        return
    sources = subtitle_addons()
    if not sources:
        return
    languages, mine_name = search_languages()
    query = urllib.parse.urlencode({"action": "search", "languages": ",".join(languages), "preferredlanguage": mine_name})
    pref = subs_extra.preference()
    best, english = None, None
    for aid, name in sources:
        if monitor.abortRequested() or not player.isPlayingVideo():
            return
        try:
            files = rpc("Files.GetDirectory", {"directory": f"plugin://{aid}/?{query}", "media": "files",
                                               "properties": ["thumbnail", "art"],
                                               "sort": {"method": "none"}}).get("files") or []
        except Exception as error:  # noqa: BLE001
            log(f"background {aid}: {error}")
            continue
        pick = subs_extra.best_of(files, mine, pref)       # the add-on lists its best first; your series' group wins
        log(f"background {aid}: {len(files)} results, {'one' if pick else 'none'} in {mine}")
        if pick:
            best = (pick, name)
            break
        if english is None:
            english = next((f for f in files if f.get("file") and lang_of(f) == "en"), None)
    try:
        if not player.isPlayingVideo() or player.getPlayingFile() != started_with:
            return                                         # another video by now
    except RuntimeError:
        return
    if cond("VideoPlayer.SubtitlesEnabled") and not cond("String.IsEmpty(VideoPlayer.SubtitlesLanguage)"):
        current = (xbmc.getInfoLabel("VideoPlayer.SubtitlesLanguage") or "").strip().lower()
        code = NAME_TO_CODE.get(current) or (xbmc.convertLanguage(current, xbmc.ISO_639_1) or "").lower() or current[:2]
        if code == mine:
            return                                         # you chose one in your language yourself meanwhile
    if not best:
        subs_extra.want(mine)                              # check again later; say so when one turns up
        if subconf.on("lucent.subs.bg.ai") and mine != "en" and ai_ready():
            cached = ai_cached_path()
            if cached:
                log("background: AI translation from before")
                activate(cached, mine)
                return
            if english:
                local = download(english["file"])
                if local:
                    log("background: nothing in your language - translating the English one with AI")
                    import subs_ai
                    subs_ai.translate_and_load(local, mine)
                    return
        log(f"background: nothing in {mine} - nothing shown")
        return
    local = download(best[0]["file"])
    if not local:
        log("background: download failed - nothing shown")
        return
    release, source = subs_extra.split_label2(best[0].get("label2", ""))
    log(f"background: {release or best[0]['file']} from {best[1]} downloaded")
    xbmcgui.Dialog().notification("Lucent", t(f"{full_name(mine, mine.upper())} subtitle on", f"Ondertitel ({full_name(mine, mine.upper())}) staat aan"),
                                  xbmcgui.NOTIFICATION_INFO, 3000)
    subs_extra.remember(release, source)
    subs_extra.unwant()
    ok = activate(local, mine)
    log(f"background: switched on {'and steady' if ok else 'but could not confirm it'}")

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
    if recent and cond("Window.IsVisible(lucent_subtitles.xml)"):
        return                                             # really open already (a stale mark no longer blocks it)
    if auto and not settled(xbmc.Monitor(), xbmc.Player()):
        return
    if auto and use_prefetched(my_code()):
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
