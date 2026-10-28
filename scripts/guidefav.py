# -*- coding: utf-8 -*-
"""Lucent: make the channel group that is selected in the TV guide your favourite (opens first), or undo that."""
import xbmc
import xbmcgui

NL = xbmc.getLanguage(xbmc.ISO_639_1) == "nl"
KEY = "lucent.guide.group"


def run():
    label = xbmc.getInfoLabel("Container(11).ListItem.Label").strip()
    if not label:
        return
    current = xbmc.getInfoLabel(f"Skin.String({KEY})")
    if current == label:
        xbmc.executebuiltin(f"Skin.Reset({KEY})", True)
        text = "Geen favoriete groep meer" if NL else "No favourite group any more"
    else:
        xbmc.executebuiltin(f'Skin.SetString({KEY},"{label.replace(chr(34), chr(39))}")', True)
        text = f"{label} opent voortaan als eerste" if NL else f"{label} now opens first"
    xbmcgui.Dialog().notification("TV", text, "special://skin/resources/icon.png", 3500, False)


if __name__ == "__main__":
    run()
