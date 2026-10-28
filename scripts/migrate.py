# -*- coding: utf-8 -*-
"""Lucent: take over the settings of the old skin (skin.nuvioarc, "Nuvio Arc").

Runs once, from the Home screen, the first time Lucent starts. It copies every skin
setting (menu, widgets, colours, switches) and your own logo folders, so nothing
has to be set up again. Afterwards it marks Skin.String(nuvio.migrated).
"""
import xml.etree.ElementTree as ET

import xbmc
import xbmcgui
import xbmcvfs

OLD = "special://profile/addon_data/skin.nuvioarc/"
NEW = "special://profile/addon_data/skin.lucent/"
_NL = xbmc.getLanguage(xbmc.ISO_639_1) == "nl"


def log(text):
    xbmc.log(f"[skin.lucent] migrate: {text}", xbmc.LOGINFO)


def quote(value):
    return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'


def copy_folder(name):
    src, dst = OLD + name + "/", NEW + name + "/"
    if not xbmcvfs.exists(src):
        return
    xbmcvfs.mkdirs(dst)
    _dirs, files = xbmcvfs.listdir(src)
    for f in files:
        if not xbmcvfs.exists(dst + f):
            xbmcvfs.copy(src + f, dst + f)


def migrate():
    path = OLD + "settings.xml"
    if not xbmcvfs.exists(path):
        log("no old settings")
        return 0
    with xbmcvfs.File(path) as fh:
        raw = fh.read()
    try:
        root = ET.fromstring(raw)
    except ET.ParseError as error:
        log(f"old settings unreadable: {error}")
        return 0
    count = 0
    for setting in root.iter("setting"):
        sid, kind, value = setting.get("id") or "", setting.get("type") or "", setting.text or ""
        if not sid or sid == "nuvio.migrated":
            continue
        if kind == "bool":
            if value.strip().lower() == "true":
                xbmc.executebuiltin(f"Skin.SetBool({sid})")
                count += 1
        elif value:
            xbmc.executebuiltin(f"Skin.SetString({sid},{quote(value)})")
            count += 1
    for folder in ("logos", "flags"):
        copy_folder(folder)
    log(f"took over {count} settings from Nuvio Arc")
    return count


if __name__ == "__main__":
    if not xbmc.getInfoLabel("Skin.String(nuvio.migrated)"):
        n = migrate()
        xbmc.executebuiltin('Skin.SetString(nuvio.migrated,"1")', True)
        if not xbmc.getInfoLabel("Skin.String(nuvio.menu.version)"):
            xbmc.executebuiltin("RunScript(special://skin/scripts/menu.py,init)")
        else:
            xbmc.executebuiltin("RunScript(special://skin/scripts/settings.py,sync)")
        if n:
            xbmcgui.Dialog().notification(
                "Lucent", "Instellingen van Nuvio Arc overgenomen" if _NL else "Settings taken over from Nuvio Arc",
                "special://skin/resources/icon.png", 5000)
