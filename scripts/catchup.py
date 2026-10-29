# -*- coding: utf-8 -*-
"""Lucent: carry on where you stopped in a replay (catch-up) programme.

Kodi remembers where you stopped for films and recordings, but not for a programme you watch back through the channel's
replay. Lucent notes the position every 10 seconds while such a programme plays; when you open the same programme again it
asks whether to carry on from there (no answer in 10 seconds = carry on).
The helper creates the Watcher once and calls tick() every 10 seconds.
"""
import json
import time

import xbmc
import xbmcgui
import xbmcvfs

FILE = "special://profile/addon_data/skin.lucent/catchup_resume.json"
KEEP_DAYS = 14
MIN_POS = 60                 # less than a minute in: just start from the beginning
END_MARGIN = 120             # in the last 2 minutes: it counts as seen
NL = xbmc.getLanguage(xbmc.ISO_639_1) == "nl"


def t(en, nl):
    return nl if NL else en


def load():
    try:
        with xbmcvfs.File(FILE) as fh:
            data = json.loads(fh.read() or "{}")
        return data if isinstance(data, dict) else {}
    except Exception:  # noqa: BLE001
        return {}


def save(data):
    cutoff = time.time() - KEEP_DAYS * 86400
    data = {k: v for k, v in data.items() if v.get("at", 0) > cutoff}
    try:
        xbmcvfs.mkdirs("special://profile/addon_data/skin.lucent/")
        with xbmcvfs.File(FILE, "w") as fh:
            fh.write(json.dumps(data))
    except Exception:  # noqa: BLE001
        pass


def playing_replay():
    return xbmc.getCondVisibility("Pvr.IsPlayingEpgTag + Player.HasVideo")


def key_now():
    parts = [xbmc.getInfoLabel(f"VideoPlayer.{n}") for n in ("ChannelName", "Title", "StartTime")]
    return "|".join(parts) if all(parts) else ""


def clock(seconds):
    seconds = int(seconds)
    return f"{seconds // 3600}:{seconds % 3600 // 60:02d}:{seconds % 60:02d}" if seconds >= 3600 else f"{seconds // 60}:{seconds % 60:02d}"


class Watcher(xbmc.Player):
    def __init__(self):
        super().__init__()
        self.key = ""

    def onAVStarted(self):  # noqa: N802 - Kodi callback name
        self.key = ""
        try:
            if not playing_replay() or xbmc.getCondVisibility("Skin.HasSetting(lucent.catchup.off)"):
                return
            self.key = key_now()
            saved = load().get(self.key) if self.key else None
            if not saved or saved.get("pos", 0) < MIN_POS:
                return
            start_over = xbmcgui.Dialog().yesno(
                t("Replay", "Terugkijken"), t(f"Carry on where you stopped ({clock(saved['pos'])})?", f"Verdergaan waar je bleef ({clock(saved['pos'])})?"),
                nolabel=t("Carry on", "Verdergaan"), yeslabel=t("From the start", "Vanaf het begin"), autoclose=10000)
            if not start_over and self.isPlayingVideo():
                self.seekTime(float(saved["pos"]))
        except Exception as error:  # noqa: BLE001 - never break playback
            xbmc.log(f"[skin.lucent] catchup: {error}", xbmc.LOGINFO)

    def onPlayBackStopped(self):  # noqa: N802
        self.key = ""

    def onPlayBackEnded(self):  # noqa: N802
        self.key = ""

    def tick(self):
        """Every 10 seconds: note the position of a replay that plays."""
        if not self.key or not self.isPlayingVideo() or not playing_replay():
            return
        try:
            pos, total = self.getTime(), self.getTotalTime()
        except RuntimeError:
            return
        data = load()
        if pos < MIN_POS:
            return
        if total and pos > total - END_MARGIN:
            if self.key in data:
                del data[self.key]
                save(data)
            return
        data[self.key] = {"pos": int(pos), "total": int(total or 0), "at": time.time()}
        save(data)
