# -*- coding: utf-8 -*-
"""Backup and restore of everything you set up in Lucent Video: settings, keys, profiles, order of sources, lists the
library follows, and each profile's own files. Not included: the cache and the library's .strm files (written again by
themselves). The zip holds your keys and passwords: keep it private."""
import os
import time
import xml.etree.ElementTree as ET
import zipfile

import xbmc
import xbmcgui
import xbmcvfs

import util

T = util.T
SKIP_DIRS = ("library",)
SKIP_FILES = ("library.lock", "settings.xml")
PREFIX = "lucent-video-backup"


def _files():
    for root, dirs, files in os.walk(util.PROFILE):
        rel_root = os.path.relpath(root, util.PROFILE)
        if rel_root == ".":
            dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
        for name in files:
            rel = os.path.normpath(os.path.join(rel_root, name))
            if rel in SKIP_FILES or name.endswith(".tmp"):
                continue
            yield rel


def _settings():
    """Every setting with its current value, read through Kodi (the file on disk can lag behind)."""
    ids = []
    try:
        root = ET.parse(os.path.join(xbmcvfs.translatePath(util.ADDON.getAddonInfo("path")), "resources", "settings.xml")).getroot()
        ids = [s.get("id") for s in root.iter("setting") if s.get("id") and s.get("type") != "action"]
    except (ET.ParseError, OSError):
        pass
    return {key: util.ADDON.getSetting(key) for key in ids}


def make():
    folder = xbmcgui.Dialog().browse(3, T("Waar wil je de back-up bewaren?", "Where do you want to save the backup?"), "files")
    if not folder:
        return
    import json
    name = "%s-%s.zip" % (PREFIX, time.strftime("%Y%m%d-%H%M"))
    local = os.path.join(xbmcvfs.translatePath("special://temp/"), name)
    with zipfile.ZipFile(local, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("settings.json", json.dumps(_settings(), indent=1))
        for rel in _files():
            archive.write(os.path.join(util.PROFILE, rel), "files/" + rel.replace(os.sep, "/"))
    ok = xbmcvfs.copy(local, os.path.join(folder, name))
    xbmcvfs.delete(local)
    if ok:
        xbmcgui.Dialog().ok("Lucent", T("De back-up is bewaard als %s. Er staan je sleutels en wachtwoorden in: bewaar hem privé.",
                                        "The backup is saved as %s. It holds your keys and passwords: keep it private.") % name)
    else:
        xbmcgui.Dialog().ok("Lucent", T("Bewaren is niet gelukt. Kies een andere map.", "Saving failed. Choose another folder."))


def restore():
    path = xbmcgui.Dialog().browse(1, T("Kies je back-up", "Choose your backup"), "files", ".zip")
    if not path:
        return
    if not xbmcgui.Dialog().yesno("Lucent", T("Alles van Lucent Video op dit apparaat wordt vervangen door de back-up. Doorgaan?",
                                              "Everything of Lucent Video on this device is replaced by the backup. Continue?")):
        return
    import json
    local = os.path.join(xbmcvfs.translatePath("special://temp/"), "lucent-video-restore.zip")
    if not xbmcvfs.copy(path, local):
        xbmcgui.Dialog().ok("Lucent", T("Het bestand kan niet worden gelezen.", "The file cannot be read."))
        return
    try:
        with zipfile.ZipFile(local) as archive:
            names = archive.namelist()
            if "settings.json" not in names:
                raise zipfile.BadZipFile("not a Lucent Video backup")
            values = json.loads(archive.read("settings.json").decode("utf-8"))
            base = os.path.realpath(util.PROFILE)
            for member in names:
                if not member.startswith("files/") or member.endswith("/"):
                    continue
                target = os.path.realpath(os.path.join(base, member[len("files/"):]))
                if not target.startswith(base + os.sep):          # never outside Lucent Video's own folder
                    continue
                os.makedirs(os.path.dirname(target), exist_ok=True)
                with open(target, "wb") as handle:
                    handle.write(archive.read(member))
    except (zipfile.BadZipFile, ValueError, OSError) as error:
        util.log("restore failed: %s" % type(error).__name__)
        xbmcgui.Dialog().ok("Lucent", T("Dit is geen geldige back-up van Lucent Video.", "This is not a valid Lucent Video backup."))
        return
    finally:
        xbmcvfs.delete(local)
    for key, value in (values or {}).items():                 # through Kodi, which keeps settings in memory
        if isinstance(value, str):
            util.ADDON.setSetting(key, value)
    util.cache_clear()
    xbmcgui.Dialog().ok("Lucent", T("De back-up is teruggezet.", "The backup is restored."))
    xbmc.executebuiltin("Container.Refresh")


def menu():
    choice = xbmcgui.Dialog().select("Lucent", [T("Back-up maken", "Make a backup"), T("Back-up terugzetten", "Restore a backup")])
    if choice == 0:
        make()
    elif choice == 1:
        restore()
