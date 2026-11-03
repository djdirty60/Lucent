# -*- coding: utf-8 -*-
"""Lucent: choose the channel group that the TV guide opens with (your favourite), or none.

The star button above the groups opens a list of all groups (the ones in the guide's group list, id 11): pick one and
the guide opens with it from then on; 'No favourite' goes back to Kodi's own choice (the last group you used).
Before, the button took the group that was selected in the list - but on the way up to the button you always passed
the groups above it, so only the first group could ever become the favourite.
"""
import xbmc
import xbmcgui

NL = xbmc.getLanguage(xbmc.ISO_639_1) == "nl"
KEY = "lucent.guide.group"
PATH_KEY = "lucent.guide.grouppath"     # Kodi's own folder of that group, for the TV tab on Home


def groups():
    count = int(xbmc.getInfoLabel("Container(11).NumItems") or 0)
    out = []
    for index in range(count):
        label = xbmc.getInfoLabel(f"Container(11).ListItemAbsolute({index}).Label").strip()
        if label and label not in out:
            out.append(label)
    return out


def run():
    names = groups()
    if not names:
        return
    current = xbmc.getInfoLabel(f"Skin.String({KEY})")
    none = "Geen favoriet (Kodi kiest zelf)" if NL else "No favourite (Kodi chooses)"
    labels = [none] + [f"★  {n}" if n == current else n for n in names]
    preselect = names.index(current) + 1 if current in names else 0
    pick = xbmcgui.Dialog().select("Favoriete groep - opent als eerste" if NL else "Favourite group - opens first",
                                   labels, preselect=preselect)
    if pick < 0:
        return
    if pick == 0:
        xbmc.executebuiltin(f"Skin.Reset({KEY})", True)
        xbmc.executebuiltin(f"Skin.Reset({PATH_KEY})", True)
        text = "Geen favoriete groep meer" if NL else "No favourite group any more"
    else:
        label = names[pick - 1]
        xbmc.executebuiltin(f'Skin.SetString({KEY},"{label.replace(chr(34), chr(39))}")', True)
        remember_path(label)
        text = f"{label} opent voortaan als eerste" if NL else f"{label} now opens first"
        open_group(label)
    try:
        import tabpanels                    # the TV tab on Home shows the same group
        tabpanels.tv_path()
    except Exception as error:  # noqa: BLE001
        xbmc.log(f"[Lucent] guidefav: tv tab {error}", xbmc.LOGINFO)
    xbmcgui.Dialog().notification("TV", text, "special://skin/resources/icon.png", 3500, False)


def remember_path(label):
    """Keep the guide's own path of the group: the TV tab on Home lists exactly that folder."""
    for index in range(int(xbmc.getInfoLabel("Container(11).NumItems") or 0)):
        if xbmc.getInfoLabel(f"Container(11).ListItemAbsolute({index}).Label").strip() == label:
            path = xbmc.getInfoLabel(f"Container(11).ListItemAbsolute({index}).FolderPath")
            if path.startswith("pvr://"):
                xbmc.executebuiltin(f'Skin.SetString({PATH_KEY},"{path}")', True)
            return


def open_group(label):
    """Show the chosen group right away (as if you picked it in the list)."""
    for index in range(int(xbmc.getInfoLabel("Container(11).NumItems") or 0)):
        if xbmc.getInfoLabel(f"Container(11).ListItemAbsolute({index}).Label").strip() == label:
            xbmc.executebuiltin(f"SetFocus(11,{index},absolute)")
            xbmc.sleep(300)
            xbmc.executebuiltin("Action(Select)")
            return


def from_settings():
    """Settings > Live TV: choose the favourite group without opening the guide (Kodi's own list of groups)."""
    import json
    import urllib.parse
    reply = json.loads(xbmc.executeJSONRPC(json.dumps({"jsonrpc": "2.0", "id": 1, "method": "PVR.GetChannelGroups",
                                                        "params": {"channeltype": "tv"}})))
    names = [g.get("label") or "" for g in (reply.get("result") or {}).get("channelgroups") or [] if g.get("label")]
    if not names:
        xbmcgui.Dialog().ok("TV", "Nog geen zendergroepen (eerst de Xtream-inlog)." if NL else "No channel groups yet (Xtream login first).")
        return
    current = xbmc.getInfoLabel(f"Skin.String({KEY})")
    none = "Geen favoriet (Kodi kiest zelf)" if NL else "No favourite (Kodi chooses)"
    labels = [none] + [f"★  {n}" if n == current else n for n in names]
    pick = xbmcgui.Dialog().select("Favoriete groep - opent als eerste" if NL else "Favourite group - opens first",
                                   labels, preselect=names.index(current) + 1 if current in names else 0)
    if pick < 0:
        return
    if pick == 0:
        xbmc.executebuiltin(f"Skin.Reset({KEY})", True)
        xbmc.executebuiltin(f"Skin.Reset({PATH_KEY})", True)
    else:
        label = names[pick - 1]
        xbmc.executebuiltin(f'Skin.SetString({KEY},"{label.replace(chr(34), chr(39))}")', True)
        path = f"pvr://channels/tv/{urllib.parse.quote(label, safe='')}/"     # the guide's own form; the guide corrects it on its next visit
        xbmc.executebuiltin(f'Skin.SetString({PATH_KEY},"{path}")', True)
    try:
        import tabpanels
        tabpanels.tv_path()
    except Exception as error:  # noqa: BLE001
        xbmc.log(f"[Lucent] guidefav: tv tab {error}", xbmc.LOGINFO)


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "settings":
        from_settings()
    else:
        run()
