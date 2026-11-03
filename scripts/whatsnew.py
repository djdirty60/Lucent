"""What's new: the changes of every version in a pop-up (Dutch when Kodi is in Dutch and a Dutch line exists)."""
import html
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
text = html.unescape(news.group(1).strip()) if news else ""          # &#10; is a new line, &gt; a '>'
entries = []
for line in text.splitlines():                                     # one version per line: '1.33.0 - Beta 3: ...'
    m = re.match(r"\s*(\d+\.\d+\.\d+)(?:\s*-\s*([^:]{1,30}))?:\s(.*)", line)
    if m:
        entries.append((m.group(1) + (f"  ·  {m.group(2).strip()}" if m.group(2) else ""), m.group(3)))
    elif entries and line.strip():
        entries[-1] = (entries[-1][0], entries[-1][1] + " " + line.strip())
dutch = xbmc.getLanguage(xbmc.ISO_639_1) == "nl"
nl = {}
if dutch:
    for line in read("resources/changelog_nl.txt").splitlines():
        m = re.match(r"(\d+\.\d+\.\d+):\s(.*)", line.strip())
        if m:
            nl[m.group(1)] = m.group(2)
for version in nl:
    if version not in [v.split()[0] for v, _ in entries]:
        entries.insert(0, (version, nl[version]))
out = []
for version, text in entries:
    out.append(f"[B]{version}[/B]")
    out.append(nl.get(version.split()[0], text.strip()))
    out.append("")
xbmcgui.Dialog().textviewer(xbmc.getLocalizedString(31530), "[CR]".join(out))
