"""What's new: the changes of every version in a pop-up (Dutch when Kodi is in Dutch and a Dutch line exists)."""
import re

import xbmc
import xbmcgui
import xbmcvfs

SKIN = "special://skin/"


def read(path):
    try:
        f = xbmcvfs.File(SKIN + path)
        data = f.read()
        f.close()
        return data if isinstance(data, str) else data.decode("utf-8", "replace")
    except Exception:  # noqa: BLE001
        return ""


news = re.search(r"<news>(.*?)</news>", read("addon.xml"), re.S)
entries = re.findall(r"(\d+\.\d+\.\d+):\s(.*?)(?=\s\d+\.\d+\.\d+:\s|$)", news.group(1).strip() if news else "", re.S)
dutch = xbmc.getLanguage(xbmc.ISO_639_1) == "nl"
nl = {}
if dutch:
    for line in read("resources/changelog_nl.txt").splitlines():
        m = re.match(r"(\d+\.\d+\.\d+):\s(.*)", line.strip())
        if m:
            nl[m.group(1)] = m.group(2)
for version in nl:
    if version not in [v for v, _ in entries]:
        entries.insert(0, (version, nl[version]))
out = []
for version, text in entries:
    out.append(f"[B]{version}[/B]")
    out.append(nl.get(version, text.strip()))
    out.append("")
xbmcgui.Dialog().textviewer(xbmc.getLocalizedString(31530), "[CR]".join(out))
