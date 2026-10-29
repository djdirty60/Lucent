"""About Lucent: version, what it is, credits and where to find it - in one pop-up."""
import xbmc
import xbmcgui

HEADING = "Lucent " + xbmc.getInfoLabel("System.AddonVersion(skin.lucent)")
nl = xbmc.getLanguage(xbmc.ISO_639_1) == "nl"
lines = [
    xbmc.getLocalizedString(31174),
    "",
    f"Kodi {xbmc.getInfoLabel('System.BuildVersionShort')}",
    "Skin: Lucent " + xbmc.getInfoLabel("System.AddonVersion(skin.lucent)"),
    "Lucent Bibliotheek: " + (xbmc.getInfoLabel("System.AddonVersion(script.lucent.library)") or "-"),
    "",
    ("Code, nieuws en hulp: " if nl else "Code, news and help: ") + "https://github.com/djdirty60/Lucent",
    "",
    xbmc.getLocalizedString(31501),
    ("Licenties en naamsvermelding vind je onder Over > Licenties." if nl else "Licences and credits are under About > Licences."),
]
xbmcgui.Dialog().textviewer(HEADING, "\n".join(lines))
