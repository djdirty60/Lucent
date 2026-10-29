# -*- coding: utf-8 -*-
"""Lucent: A4KSubtitles as the subtitle service.

RunScript(special://skin/scripts/subtitles.py,default)   make A4KSubtitles the default service for films and series
RunScript(special://skin/scripts/subtitles.py,service)   background helper (started from Home): when a film or episode (for example from
                                                         Seren) starts without subtitles in your language, open the subtitle search
                                                         - only when "Search subtitles automatically" is on in Skin settings
The "Search subtitles" button in the player menu opens Kodi's own subtitle search, which then uses that service.
"""
import json
import sys
import time

import xbmc
import xbmcgui

ADDON_ID = "service.subtitles.a4ksubtitles"
HOME = xbmcgui.Window(10000)
RUNNING = "nuvio.subs.running"
NL = xbmc.getLanguage(xbmc.ISO_639_1) == "nl"
TEXT = {
    "done": ("A4KSubtitles is now the default subtitle service", "A4KSubtitles is nu de standaard ondertitelservice"),
    "missing": ("A4KSubtitles is not installed", "A4KSubtitles is niet geïnstalleerd"),
    "failed": ("Could not change the setting", "Kon de instelling niet wijzigen"),
}


def say(key, icon=xbmcgui.NOTIFICATION_INFO):
    xbmcgui.Dialog().notification("Lucent", TEXT[key][1 if NL else 0], icon, 4000)


def set_default():
    if not xbmc.getCondVisibility(f"System.HasAddon({ADDON_ID})"):
        say("missing", xbmcgui.NOTIFICATION_WARNING)
        return
    ok = True
    for setting in ("subtitles.movie", "subtitles.tv"):
        query = {"jsonrpc": "2.0", "id": 1, "method": "Settings.SetSettingValue", "params": {"setting": setting, "value": ADDON_ID}}
        try:
            ok = ok and "error" not in json.loads(xbmc.executeJSONRPC(json.dumps(query)))
        except Exception as error:  # noqa: BLE001
            xbmc.log(f"[skin.lucent subtitles] {setting}: {error}", xbmc.LOGINFO)
            ok = False
    say("done" if ok else "failed", xbmcgui.NOTIFICATION_INFO if ok else xbmcgui.NOTIFICATION_WARNING)


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
        if not xbmc.getCondVisibility("Skin.HasSetting(nuvio.autosubs)") or not xbmc.getCondVisibility(f"System.HasAddon({ADDON_ID})"):
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
        xbmc.executebuiltin("ActivateWindow(subtitlesearch)")


def run_service():
    if time.time() - float(HOME.getProperty(RUNNING) or 0) < 120:
        return
    watcher = Watcher()
    while not watcher.monitor.abortRequested():
        HOME.setProperty(RUNNING, f"{time.time():.1f}")
        if watcher.monitor.waitForAbort(30):
            break
    HOME.clearProperty(RUNNING)


if __name__ == "__main__":
    arg = sys.argv[1] if len(sys.argv) > 1 else ""
    if arg == "default":
        set_default()
    elif arg == "service":
        run_service()
