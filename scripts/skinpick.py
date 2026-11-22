# -*- coding: utf-8 -*-
"""Lucent 3.0.7: Settings › Lucent › Change skin (Reddit: going back to another skin took a long search).

A list of the installed skins; the one you pick becomes the skin (Kodi's own setting lookandfeel.skin).

    RunScript(special://skin/scripts/skinpick.py)
"""
import json

import xbmc
import xbmcgui

NL = xbmc.getLanguage(xbmc.ISO_639_1) == "nl"


def rpc(method, params):
    return json.loads(xbmc.executeJSONRPC(json.dumps({"jsonrpc": "2.0", "id": 1, "method": method, "params": params}))).get("result") or {}


def main():
    skins = rpc("Addons.GetAddons", {"type": "xbmc.gui.skin", "enabled": True, "properties": ["name", "thumbnail"]}).get("addons") or []
    current = xbmc.getSkinDir()
    skins.sort(key=lambda s: (s["addonid"] != current, (s.get("name") or s["addonid"]).lower()))
    items = []
    for skin in skins:
        li = xbmcgui.ListItem(skin.get("name") or skin["addonid"])
        li.setLabel2(("Nu in gebruik" if NL else "In use now") if skin["addonid"] == current else skin["addonid"])
        if skin.get("thumbnail"):
            li.setArt({"icon": skin["thumbnail"], "thumb": skin["thumbnail"]})
        items.append(li)
    pick = xbmcgui.Dialog().select("Andere skin kiezen" if NL else "Change skin", items, useDetails=True)
    if pick < 0 or skins[pick]["addonid"] == current:
        return
    chosen = skins[pick]
    name = chosen.get("name") or chosen["addonid"]
    if not xbmcgui.Dialog().yesno("Andere skin kiezen" if NL else "Change skin",
                                  (f"Overschakelen naar {name}?\n\nTerug naar Lucent kan via Instellingen › Interface › Skin."
                                   if NL else f"Switch to {name}?\n\nYou can go back to Lucent under Settings › Interface › Skin.")):
        return
    xbmc.log(f"[skin.lucent] skinpick: {current} -> {chosen['addonid']}", xbmc.LOGINFO)
    rpc("Settings.SetSettingValue", {"setting": "lookandfeel.skin", "value": chosen["addonid"]})


if __name__ == "__main__":
    main()
