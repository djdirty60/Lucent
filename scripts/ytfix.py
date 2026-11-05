"""Lucent: trailer fix for the YouTube add-on (switch: Settings > Watching > YouTube trailer fix).

YouTube add-on 7.4.x asks Google for the video as the 'android_vr' client. Since summer 2026 Google answers that client
with 403 Forbidden after about a minute (it wants a PO token the add-on does not send), so trailers stop at ~1:05.
Known issue: github.com/anxdpanic/plugin.video.youtube/issues/1481. The workaround tested there: skip that client.

This changes exactly that one entry in the add-on's player_client.py, only when the file has the text we expect, keeps
a backup, does it again after a YouTube update and does nothing once YouTube changed the code itself. Switched off,
the original entry goes back. Side effect named in the issue: the watch history of a signed-in YouTube account may not
update.
"""
import os
import shutil
import sys

import xbmc
import xbmcvfs

FILE = "special://home/addons/plugin.video.youtube/resources/lib/youtube_plugin/youtube/client/player_client.py"
BACKUP_DIR = "special://profile/addon_data/skin.lucent/ytfix/"
OFF = "Skin.HasSetting(lucent.ytfix.off)"
ORIGINAL = ("            ('auth_enabled|no_kids|av1|vp9.2|avc1|surround_sound', (\n"
            "                'android_vr',\n"
            "            )),\n")
FIXED = ("            ('auth_enabled|no_kids|av1|vp9.2|avc1|surround_sound', (\n"
         "                # 'android_vr',  # lucent-ytfix: Google stops this client after ~1 minute (issue #1481)\n"
         "            )),\n")


def log(text):
    xbmc.log(f"[skin.lucent] ytfix: {text}", xbmc.LOGINFO)


def state(text):
    """'fixed', 'original', 'unknown' (YouTube changed this part: leave it alone)."""
    if FIXED in text:
        return "fixed"
    if ORIGINAL in text:
        return "original"
    return "unknown"


def _write(path, text):
    tmp = path + ".lucent-tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        fh.write(text)
    os.replace(tmp, path)
    cache = os.path.join(os.path.dirname(path), "__pycache__")       # the next start of YouTube compiles it again
    if os.path.isdir(cache):
        for name in os.listdir(cache):
            if name.startswith("player_client."):
                try:
                    os.remove(os.path.join(cache, name))
                except OSError:
                    pass


def check():
    """Called by the helper: put the fix in (or take it out when switched off). Returns the state afterwards."""
    if not xbmc.getCondVisibility("System.HasAddon(plugin.video.youtube)"):
        return "no youtube"
    path = xbmcvfs.translatePath(FILE)
    try:
        with open(path, encoding="utf-8") as fh:
            text = fh.read()
    except OSError as error:
        log(f"cannot read the YouTube add-on: {error}")
        return "unreadable"
    now = state(text)
    want_off = xbmc.getCondVisibility(OFF)
    try:
        if now == "original" and not want_off:
            version = xbmc.getInfoLabel("System.AddonVersion(plugin.video.youtube)") or "unknown"
            backup = xbmcvfs.translatePath(BACKUP_DIR)
            os.makedirs(backup, exist_ok=True)
            shutil.copyfile(path, os.path.join(backup, f"player_client-{version}.py"))
            _write(path, text.replace(ORIGINAL, FIXED, 1))
            log(f"fix applied to YouTube {version} (backup kept)")
            return "fixed"
        if now == "fixed" and want_off:
            _write(path, text.replace(FIXED, ORIGINAL, 1))
            log("fix taken out again (switched off)")
            return "original"
    except OSError as error:
        log(f"cannot change the YouTube add-on: {error}")
        return "readonly"
    if now == "unknown":
        log("YouTube changed this part of its code: nothing to do")
    return now


def label():
    """For the settings: what the fix does right now."""
    nl = xbmc.getLanguage(xbmc.ISO_639_1) == "nl"
    if xbmc.getCondVisibility(OFF):
        return "uit" if nl else "off"
    try:
        with open(xbmcvfs.translatePath(FILE), encoding="utf-8") as fh:
            now = state(fh.read())
    except OSError:
        return "YouTube niet gevonden" if nl else "YouTube not found"
    return {"fixed": "aan" if nl else "on", "original": "wordt toegepast" if nl else "being applied",
            "unknown": "niet nodig (YouTube is bijgewerkt)" if nl else "not needed (YouTube was updated)"}[now]


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "toggle":
        xbmc.executebuiltin("Skin.ToggleSetting(lucent.ytfix.off)")
        xbmc.sleep(300)
    result = check()
    xbmc.executebuiltin(f'Skin.SetString(lucent.ytfix.state,"{label()}")')
    log(f"state: {result}")
