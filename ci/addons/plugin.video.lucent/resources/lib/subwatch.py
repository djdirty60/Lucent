# -*- coding: utf-8 -*-
"""Language rules and the automatic subtitle search on every video (taken over from the Lucent skin).

Runs in Lucent Video's service, for videos from Lucent Video, Seren, Fen, the library and others (never YouTube):
spoken language (first and second choice), a wrong subtitle language off, no subtitle when the sound is already your
language, subtitles always on, and when your language is missing: the live list, a quiet pick in the background or
Kodi's own search. Also: Lucent Ondertitels as Kodi's default subtitle service (action=subs_default).
A series' own remembered sound and subtitle (streammem.py, set 7 s after the start) wins over these rules.
"""
import json
import time

import subconf
import xbmc
import xbmcgui

OWN_ID = "service.subtitles.lucent"
OLD_IDS = ("service.subtitles.a4ksubtitles",)    # only to recognise the old default once
HOME = xbmcgui.Window(10000)
NL = xbmc.getLanguage(xbmc.ISO_639_1) == "nl"
TEXT = {
    "done": ("{0} is now the default subtitle service", "{0} is nu de standaard ondertitelservice"),
    "missing": ("No subtitle add-on installed", "Geen ondertitel-add-on geïnstalleerd"),
    "failed": ("Could not change the setting", "Kon de instelling niet wijzigen"),
}


def say(key, icon=xbmcgui.NOTIFICATION_INFO, name=""):
    xbmcgui.Dialog().notification("Lucent", TEXT[key][1 if NL else 0].format(name), icon, 4000)


def service_id():
    return OWN_ID if xbmc.getCondVisibility(f"System.HasAddon({OWN_ID})") else ""


def set_default():
    addon_id = service_id()
    if not addon_id:
        say("missing", xbmcgui.NOTIFICATION_WARNING)
        return
    ok = True
    for setting in ("subtitles.movie", "subtitles.tv"):
        query = {"jsonrpc": "2.0", "id": 1, "method": "Settings.SetSettingValue", "params": {"setting": setting, "value": addon_id}}
        try:
            ok = ok and "error" not in json.loads(xbmc.executeJSONRPC(json.dumps(query)))
        except Exception as error:  # noqa: BLE001
            xbmc.log(f"[lucent.video] subtitles: {setting}: {error}", xbmc.LOGINFO)
            ok = False
    say("done" if ok else "failed", xbmcgui.NOTIFICATION_INFO if ok else xbmcgui.NOTIFICATION_WARNING,
        "Lucent Ondertitels")


def wanted_codes():
    """Language codes (ISO 639-1 / 2) of the language the Kodi interface uses."""
    codes = {xbmc.getLanguage(xbmc.ISO_639_1).lower(), xbmc.getLanguage(xbmc.ISO_639_2).lower()}
    if "nl" in codes or "dut" in codes:
        codes |= {"nl", "nld", "dut"}
    return {c for c in codes if c}


# ISO 639-2 codes that Kodi's own conversion may not know (B and T forms both occur in films)
ALIASES = {"dut": "nl", "nld": "nl", "ger": "de", "deu": "de", "fre": "fr", "fra": "fr", "chi": "zh", "zho": "zh",
           "cze": "cs", "ces": "cs", "gre": "el", "ell": "el", "per": "fa", "fas": "fa", "rum": "ro", "ron": "ro",
           "slo": "sk", "slk": "sk", "alb": "sq", "sqi": "sq", "arm": "hy", "hye": "hy", "geo": "ka", "kat": "ka",
           "ice": "is", "isl": "is", "mac": "mk", "mkd": "mk", "may": "ms", "msa": "ms", "bur": "my", "mya": "my",
           "baq": "eu", "eus": "eu", "wel": "cy", "cym": "cy", "tib": "bo", "bod": "bo", "pob": "pt", "spa": "es"}


def lang2(value):
    """Any language code or English language name -> two-letter code ('' when unknown)."""
    value = (value or "").strip().lower()
    if not value or value in ("und", "unk", "unknown", "mis", "mul", "zxx"):
        return ""
    value = value.split("-")[0].split("_")[0] if len(value) > 3 and value[2:3] in "-_" else value
    if value in ALIASES:
        return ALIASES[value]
    if len(value) == 2:
        return value
    try:
        code = (xbmc.convertLanguage(value, xbmc.ISO_639_1) or "").lower()
    except Exception:  # noqa: BLE001
        code = ""
    return code if len(code) == 2 else ""


def setting(name):
    query = {"jsonrpc": "2.0", "id": 1, "method": "Settings.GetSettingValue", "params": {"setting": name}}
    try:
        return json.loads(xbmc.executeJSONRPC(json.dumps(query))).get("result", {}).get("value")
    except Exception:  # noqa: BLE001
        return None


def my_languages(audio=""):
    """The subtitle languages you asked for: Kodi's 'Preferred subtitle language' (Settings > Player > Language)
    and the language of the Kodi interface. Works for every language, not only Dutch."""
    langs = {lang2(xbmc.getLanguage(xbmc.ISO_639_1))}
    pref = setting("locale.subtitlelanguage")
    if isinstance(pref, str):
        if pref == "original":
            langs.add(lang2(audio))
        elif pref not in ("default", "none", "forced_only"):
            langs.add(lang2(pref))
    return {c for c in langs if c}


def rpc(method, params):
    query = {"jsonrpc": "2.0", "id": 1, "method": method, "params": params}
    return json.loads(xbmc.executeJSONRPC(json.dumps(query))).get("result") or {}


def language_name(code):
    try:
        from subs_live import full_name
        return full_name(code, code.upper())
    except Exception:  # noqa: BLE001
        return code.upper()


def fix_audio():
    """Skin settings > Subtitles > Spoken language: use the sound in your first choice, otherwise your second choice.
    Only right after the start; when neither is in the film, Kodi's own choice stays."""
    first = subconf.text("lucent.audio.lang1")
    second = subconf.text("lucent.audio.lang2")
    if not first:
        return
    props = rpc("Player.GetProperties", {"playerid": 1, "properties": ["audiostreams", "currentaudiostream"]})
    streams = props.get("audiostreams") or []
    current = props.get("currentaudiostream") or {}
    xbmc.log(f"[lucent.video] subtitles: sound: want {first}/{second or '-'}, now {current.get('language')}, "
             f"{len(streams)} tracks", xbmc.LOGDEBUG)
    if len(streams) < 2:
        return

    def usable(a):                                     # not the director's commentary or an audio description
        name = (a.get("name") or "").lower()
        return not any(w in name for w in ("comment", "kommentar", "description", "audiodescri", "beschrijving"))

    for want in (first, second):
        if not want:
            continue
        if lang2(current.get("language")) == want and usable(current):
            return                                     # already your choice
        match = [a for a in streams if lang2(a.get("language")) == want and usable(a)]
        if match:
            best = max(match, key=lambda a: (bool(a.get("isdefault")), int(a.get("channels") or 0)))
            rpc("Player.SetAudioStream", {"playerid": 1, "stream": best["index"]})
            xbmc.log(f"[lucent.video] subtitles: sound {current.get('language')} -> {best.get('language')} (your {'first' if want == first else 'second'} choice)", xbmc.LOGINFO)
            xbmc.sleep(500)
            return


def audio_is_mine():
    """True when the sound being played is in your own language (Settings > Player > Language / Kodi's language)."""
    if subconf.on("lucent.subs.sameaudio.keep"):
        return False
    props = rpc("Player.GetProperties", {"playerid": 1, "properties": ["currentaudiostream"]})
    audio = lang2((props.get("currentaudiostream") or {}).get("language"))
    return bool(audio) and audio in my_languages()


def quiet_if_same_language():
    """The sound is already in your language: no subtitle needed. A full subtitle that is on goes off; a 'forced'
    one stays (it only translates signs and bits in another language). Returns True when the sound is yours."""
    if not audio_is_mine():
        return False
    props = rpc("Player.GetProperties", {"playerid": 1, "properties": ["currentsubtitle", "subtitleenabled"]})
    current = props.get("currentsubtitle") or {}
    keep = current.get("isforced") and lang2(current.get("language")) in my_languages()   # forced, in your language
    if props.get("subtitleenabled") and current and not keep:
        xbmc.Player().showSubtitles(False)
        xbmc.log(f"[lucent.video] subtitles: sound is in your language: subtitle {current.get('language')} switched off", xbmc.LOGINFO)
    return True


def fix_language():
    """Kodi picked a subtitle from the film in a language you never asked for (for example a Russian 'forced' track
    that the film marks as 'default' when the film has none in your language). Use a subtitle of the film in your
    own language instead, or switch the subtitles off. A 'forced' track in the language you hear is kept: it only
    translates signs and foreign speech. Only right after the start: what you choose yourself is never changed."""
    if subconf.on("lucent.subs.langfix.off") or not xbmc.getCondVisibility("VideoPlayer.SubtitlesEnabled"):
        return
    props = rpc("Player.GetProperties", {"playerid": 1, "properties": ["subtitles", "currentsubtitle", "currentaudiostream"]})
    current = props.get("currentsubtitle") or {}
    if not current or current.get("index") is None:
        return
    if str(current.get("name") or "").lower().endswith((".srt", ".ass", ".ssa", ".sub", ".vtt", ".smi")):
        return                                           # a subtitle file that was loaded on purpose
    audio = lang2((props.get("currentaudiostream") or {}).get("language"))
    mine = my_languages(audio)
    code = lang2(current.get("language"))
    if not mine or not code or code in mine:
        return                                           # your language, or a language Kodi does not know: leave it
    if current.get("isforced") and audio and code == audio:
        return
    better = [s for s in props.get("subtitles") or [] if lang2(s.get("language")) in mine]
    better.sort(key=lambda s: (bool(s.get("isforced")), bool(s.get("isimpaired"))))   # full ones first
    name = language_name(code)
    if better:
        rpc("Player.SetSubtitle", {"playerid": 1, "subtitle": better[0]["index"], "enable": True})
        xbmc.log(f"[lucent.video] subtitles: {code} subtitle -> {better[0].get('language')} (your language)", xbmc.LOGINFO)
        return
    xbmc.Player().showSubtitles(False)
    xbmc.log(f"[lucent.video] subtitles: {code} subtitle switched off: not one of your languages {sorted(mine)}", xbmc.LOGINFO)
    xbmcgui.Dialog().notification("Lucent", f"{name} subtitles switched off" if not NL else f"Ondertitel ({name}) uitgezet",
                                  xbmcgui.NOTIFICATION_INFO, 4000)


ALWAYS = "lucent.subs.alwayson"


def always_on():
    """Settings > Watching > Subtitles always on: a new video starts with a subtitle on (also when the sound is in your
    language). Your own languages first (Kodi's preferred subtitle language / your language), full ones before 'forced'
    ones; with no language set, the first full subtitle. Nothing to choose: nothing happens (the automatic search may
    still bring one)."""
    if not subconf.on(ALWAYS) or xbmc.getCondVisibility("VideoPlayer.SubtitlesEnabled"):
        return
    props = rpc("Player.GetProperties", {"playerid": 1, "properties": ["subtitles", "currentaudiostream"]})
    subs = props.get("subtitles") or []
    if not subs:
        return
    mine = my_languages(lang2((props.get("currentaudiostream") or {}).get("language")))
    full = [x for x in subs if not x.get("isforced")]
    pick = ([x for x in full if lang2(x.get("language")) in mine] or [x for x in subs if lang2(x.get("language")) in mine]
            or ([] if mine else (full or subs)))
    if not pick:
        return
    rpc("Player.SetSubtitle", {"playerid": 1, "subtitle": pick[0]["index"], "enable": True})
    xbmc.log(f"[lucent.video] subtitles: always on: subtitle {pick[0].get('language') or pick[0].get('name')} switched on", xbmc.LOGINFO)


class Watcher(xbmc.Player):
    def __init__(self):
        super().__init__()
        self.monitor = xbmc.Monitor()

    def onAVStarted(self):  # noqa: N802 - Kodi callback name
        HOME.setProperty("lucent.play.start", f"{time.time():.1f}")   # helper.py: a search right after the start
        try:
            self.look()
        except Exception as error:  # noqa: BLE001 - never break playback
            xbmc.log(f"[lucent.video] subtitles: {error}", xbmc.LOGINFO)

    def next_episode_later(self):
        """An episode: after a few minutes of watching, get the next episode's subtitle ready (subs_extra.prefetch)."""
        if not xbmc.getInfoLabel("VideoPlayer.TVShowTitle") or subconf.on("lucent.subs.next.off"):
            return
        try:
            started = self.getPlayingFile()
        except RuntimeError:
            return

        def later():
            while not self.monitor.waitForAbort(15):
                try:
                    if not self.isPlayingVideo() or self.getPlayingFile() != started:
                        return
                    if self.getTime() >= 180:
                        break
                except RuntimeError:
                    return
            else:
                return
            xbmc.executebuiltin("plugin://plugin.video.lucent/?action=subs_prefetch")
        import threading
        threading.Thread(target=later, daemon=True).start()

    def check_again(self):
        """Seren (or Kodi) can pick the film's subtitle again some seconds after the start: look once more."""
        def later():
            if self.monitor.waitForAbort(12) or not self.isPlayingVideo() or HOME.getProperty("lucent.video.memory") == "1":
                return
            try:
                if subconf.on(ALWAYS):
                    fix_language()
                    always_on()
                elif not quiet_if_same_language():
                    fix_language()
            except Exception as error:  # noqa: BLE001
                xbmc.log(f"[lucent.video] subtitles: language check (again): {error}", xbmc.LOGINFO)
        import threading
        threading.Thread(target=later, daemon=True).start()

    def is_youtube(self):
        """A YouTube video (a trailer, or something started from the YouTube add-on)."""
        if HOME.getProperty("nuvio.trailer.playing"):
            return True
        names = [xbmc.getInfoLabel("Player.Filenameandpath"), xbmc.getInfoLabel("Player.Folderpath")]
        try:
            names.append(self.getPlayingFile())
        except RuntimeError:
            pass
        text = " ".join(n for n in names if n).lower()
        return any(word in text for word in ("plugin.video.youtube", "youtube.com", "googlevideo.com", "youtu.be"))

    def look(self):
        xbmc.log("[lucent.video] subtitles: a video started: checking sound and subtitle", xbmc.LOGDEBUG)
        if not self.isPlayingVideo() or xbmc.getCondVisibility("VideoPlayer.Content(livetv) | Player.IsInternetStream + String.IsEmpty(VideoPlayer.Title)"):
            return
        if self.is_youtube():
            return                                       # trailers and other YouTube videos: never search subtitles
        if self.monitor.waitForAbort(4):                  # let Kodi pick the streams and the subtitle first
            return
        if not self.isPlayingVideo() or self.is_youtube():
            return
        remembered = HOME.getProperty("lucent.video.memory") == "1"     # streammem.py sets this series' own choice
        try:
            if not remembered:
                fix_audio()                              # the sound first: the subtitle check looks at it
        except Exception as error:  # noqa: BLE001 - never break playback
            xbmc.log(f"[lucent.video] subtitles: sound check: {error}", xbmc.LOGINFO)
        try:
            if not remembered and not subconf.on(ALWAYS) and quiet_if_same_language():
                self.check_again()                       # Seren may switch one on a little later
                return                                   # sound in your language: no subtitle, no search
        except Exception as error:  # noqa: BLE001 - never break playback
            xbmc.log(f"[lucent.video] subtitles: same-language check: {error}", xbmc.LOGINFO)
        try:
            if not remembered:
                fix_language()
        except Exception as error:  # noqa: BLE001 - never break playback
            xbmc.log(f"[lucent.video] subtitles: language check: {error}", xbmc.LOGINFO)
        try:
            if not remembered:
                always_on()
        except Exception as error:  # noqa: BLE001 - never break playback
            xbmc.log(f"[lucent.video] subtitles: always on: {error}", xbmc.LOGINFO)
        if not subconf.on("nuvio.autosubs") or not service_id():
            self.check_again()
            return
        self.next_episode_later()
        have = {s.lower() for s in (self.getAvailableSubtitleStreams() or [])}
        if have & wanted_codes():
            return
        self.check_again()
        if subconf.text("lucent.subs.mode") == "background":
            xbmc.executebuiltin("RunPlugin(plugin://plugin.video.lucent/?action=subs_background)")   # quietly, no window
        elif subconf.on("lucent.subs.native.off"):
            xbmc.executebuiltin("ActivateWindow(subtitlesearch)")
        else:
            xbmc.executebuiltin("RunPlugin(plugin://plugin.video.lucent/?action=subs_auto)")   # Lucent's live list (opens once the film really plays)



def switch_once():
    """Once, when Lucent Ondertitels has just been installed: it becomes the default instead of the old service
    (only when that or nothing was the default - another choice of your own is left alone), and the old service's
    own automatic search is switched off so it no longer pops up next to Lucent's list."""
    import xbmcaddon
    xbmcaddon.Addon("plugin.video.lucent").setSetting("subs_switched", "true")
    query = {"jsonrpc": "2.0", "id": 1, "method": "Settings.GetSettingValue", "params": {"setting": "subtitles.movie"}}
    try:
        current = json.loads(xbmc.executeJSONRPC(json.dumps(query))).get("result", {}).get("value") or ""
    except Exception:  # noqa: BLE001
        current = ""
    if current in ("",) + OLD_IDS:
        set_default()
    for old in OLD_IDS:
        if xbmc.getCondVisibility(f"System.HasAddon({old})"):
            off = {"jsonrpc": "2.0", "id": 1, "method": "Addons.SetAddonEnabled", "params": {"addonid": old, "enabled": False}}
            xbmc.executeJSONRPC(json.dumps(off))
            xbmc.log(f"[lucent.video] subtitles: {old} switched off (Lucent Ondertitels replaces it)", xbmc.LOGINFO)
