# -*- coding: utf-8 -*-
"""Lucent Ondertitels: Kodi's subtitle add-on entry (search / manualsearch / download)."""
import json
import os
import sys
import urllib.parse

import xbmc
import xbmcaddon
import xbmcgui
import xbmcplugin

sys.path.insert(0, os.path.join(xbmcaddon.Addon().getAddonInfo("path"), "resources", "lib"))
import core  # noqa: E402

HANDLE = int(sys.argv[1])
PARAMS = dict(urllib.parse.parse_qsl(sys.argv[2].lstrip("?")))
NL = xbmc.getLanguage(xbmc.ISO_639_1) == "nl"


def t(en, nl):
    return nl if NL else en


def languages():
    names = [n for n in (PARAMS.get("languages") or "").split(",") if n]
    codes = []
    for name in [PARAMS.get("preferredlanguage", "")] + names:
        code = core.to_code(name)
        if code and code not in codes:
            codes.append(code)
    return codes or ["en"]


def search(query=""):
    langs = languages()
    video = core.current_video()
    if query:
        video["query"] = query
    if not core.setting("os_key").strip() and not core.setting("subdl_key").strip() and not query:
        xbmcgui.Dialog().notification(t("Lucent Subtitles", "Lucent Ondertitels"),
                                      t("Tip: add your OpenSubtitles / SubDL keys in the add-on settings",
                                        "Tip: vul je OpenSubtitles- / SubDL-sleutel in bij de instellingen van de add-on"),
                                      xbmcgui.NOTIFICATION_INFO, 5000)
    rows = core.search(video, langs)
    items = []
    for r in rows:
        label = core.SOURCES[r["src"]][2]
        li = xbmcgui.ListItem(label=core.lang_name(r["lang"]), label2=f"{r['release'] or video.get('title')}  ·  {label}")
        li.setArt({"icon": str(r["score"]), "thumb": r["lang"]})
        li.setProperty("sync", "true" if r["sync"] else "false")
        li.setProperty("hearing_imp", "true" if r["hi"] else "false")
        url = f"plugin://{core.ADDON.getAddonInfo('id')}/?" + urllib.parse.urlencode(
            {"action": "download", "item": json.dumps({k: r[k] for k in ("src", "id", "lang", "release")})})
        items.append((url, li, False))
    xbmcplugin.addDirectoryItems(HANDLE, items, len(items))


def download():
    try:
        item = json.loads(PARAMS.get("item") or "{}")
        path = core.download(item, core.current_video())
    except Exception as error:  # noqa: BLE001
        core.log(f"download: {error}")
        message = t("Daily download limit of OpenSubtitles reached", "Daglimiet van OpenSubtitles bereikt") \
            if str(error) == "limit" else t("Download failed", "Downloaden mislukt")
        xbmcgui.Dialog().notification(t("Lucent Subtitles", "Lucent Ondertitels"), message, xbmcgui.NOTIFICATION_WARNING, 4000)
        return
    xbmcplugin.addDirectoryItem(HANDLE, path, xbmcgui.ListItem(label=path), False)


try:
    action = PARAMS.get("action", "")
    if action == "search":
        search()
    elif action == "manualsearch":
        search(PARAMS.get("searchstring", "").strip())
    elif action == "download":
        download()
except Exception as error:  # noqa: BLE001 - never leave Kodi waiting
    core.log(f"{PARAMS.get('action')}: {error}")
finally:
    xbmcplugin.endOfDirectory(HANDLE)
