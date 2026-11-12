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
    ("Video-add-on: " if nl else "Video add-on: ") + (xbmc.getInfoLabel("System.AddonVersion(plugin.video.lucent)") or "-"),
    "",
    ("Code, nieuws en hulp: " if nl else "Code, news and help: ") + "https://github.com/djdirty60/Lucent",
    "",
    xbmc.getLocalizedString(31501),
    ("Licenties en naamsvermelding vind je onder Hulp en info > Licenties." if nl else "Licences and credits are under Help and info > Licences."),
]
xbmcgui.Dialog().textviewer(HEADING, "\n".join(lines))
