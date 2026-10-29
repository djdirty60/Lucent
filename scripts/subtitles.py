# -*- coding: utf-8 -*-
"""Lucent: the subtitle service (Lucent Ondertitels, else A4KSubtitles).

RunScript(special://skin/scripts/subtitles.py,default)   make A4KSubtitles the default service for films and series
Watcher: used by the Lucent helper (helper.py) - when a film or episode (for example from Seren) starts without
subtitles in your language, open the subtitle list - only when "Search subtitles automatically" is on in Skin settings
The "Search subtitles" button in the player menu opens Kodi's own subtitle search, which then uses that service.
"""
import json
import sys

import xbmc
import xbmcgui

OWN_ID = "service.subtitles.lucent"
A4K_ID = "service.subtitles.a4ksubtitles"
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
    """Lucent's own subtitle add-on when it is there, else A4KSubtitles."""
    for aid in (OWN_ID, A4K_ID):
        if xbmc.getCondVisibility(f"System.HasAddon({aid})"):
            return aid
    return ""


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
            xbmc.log(f"[skin.lucent subtitles] {setting}: {error}", xbmc.LOGINFO)
            ok = False
    say("done" if ok else "failed", xbmcgui.NOTIFICATION_INFO if ok else xbmcgui.NOTIFICATION_WARNING,
        "Lucent Ondertitels" if addon_id == OWN_ID else "A4KSubtitles")


def wanted_codes():
    """Language codes (ISO 639-1 / 2) of the language the Kodi interface uses."""
    codes = {xbmc.getLanguage(xbmc.ISO_639_1).lower(), xbmc.getLanguage(xbmc.ISO_639_2).lower()}
    if "nl" in codes or "dut" in codes:
        codes |= {"nl", "nld", "dut"}
    return {c for c in codes if c}


class Watcher(xbmc.Player):
    def __init__(self):
        super().__init__()
        self.monitor = xbmc.Monitor()

    def onAVStarted(self):  # noqa: N802 - Kodi callback name
        try:
            self.look()
        except Exception as error:  # noqa: BLE001 - never break playback
            xbmc.log(f"[skin.lucent subtitles] {error}", xbmc.LOGINFO)

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
        if not xbmc.getCondVisibility("Skin.HasSetting(nuvio.autosubs)") or not service_id():
            return
        if not self.isPlayingVideo() or xbmc.getCondVisibility("VideoPlayer.Content(livetv) | Player.IsInternetStream + String.IsEmpty(VideoPlayer.Title)"):
            return
        if self.is_youtube():
            return                                       # trailers and other YouTube videos: never search subtitles
        if self.monitor.waitForAbort(4):                  # let Kodi pick the streams and the subtitle first
            return
        if not self.isPlayingVideo() or self.is_youtube():
            return
        have = {s.lower() for s in (self.getAvailableSubtitleStreams() or [])}
        if have & wanted_codes():
            return
        if xbmc.getCondVisibility("Skin.HasSetting(lucent.subs.native.off)"):
            xbmc.executebuiltin("ActivateWindow(subtitlesearch)")
        else:
            xbmc.executebuiltin("RunScript(special://skin/scripts/subs_live.py)")   # Lucent's live list



def switch_once():
    """Once, when Lucent Ondertitels has just been installed: it becomes the default instead of A4KSubtitles
    (only when A4KSubtitles or nothing was the default - another choice of your own is left alone)."""
    xbmc.executebuiltin('Skin.SetString(lucent.subs.switched,"1")')
    query = {"jsonrpc": "2.0", "id": 1, "method": "Settings.GetSettingValue", "params": {"setting": "subtitles.movie"}}
    try:
        current = json.loads(xbmc.executeJSONRPC(json.dumps(query))).get("result", {}).get("value") or ""
    except Exception:  # noqa: BLE001
        current = ""
    if current in ("", A4K_ID):
        set_default()


if __name__ == "__main__":
    arg = sys.argv[1] if len(sys.argv) > 1 else ""
    if arg == "default":
        set_default()
    elif arg == "switch":
        switch_once()

