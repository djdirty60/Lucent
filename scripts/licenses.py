"""Skin settings > About > Licences and credits: show them in a pop-up."""
import xbmc
import xbmcgui


def L(n):
    return xbmc.getLocalizedString(n)


DATA = [
    ("The Movie Database (TMDB)", 31513, "https://www.themoviedb.org"),
    ("Trakt", 31514, "https://trakt.tv"),
    ("TVmaze", 31515, "https://www.tvmaze.com"),
    ("ESPN", 31516, "https://www.espn.com"),
]
SOFTWARE = [
    ("Seren", 31518, "https://github.com/nixgates/plugin.video.seren"),
    ("YouTube", 31519, "https://github.com/anxdpanic/plugin.video.youtube"),
    ("A4KSubtitles", 31520, "https://github.com/a4k-openproject/a4kSubtitles"),
    (31521, 31522, "https://github.com/xbmc/repo-resources"),
    ("Inter", 31523, "https://rsms.me/inter"),
    ("Nuvio Arc", 31524, "https://github.com/ysosrs123/NuvioTV-Fork"),
    ("Kodi", 31525, "https://kodi.tv"),
]


def block(title, rows):
    out = [f"[B][COLOR FF8F9BA6]{L(title)}[/COLOR][/B]", ""]
    for name, text, url in rows:
        name = L(name) if isinstance(name, int) else name
        out += [f"[B]{name}[/B]", L(text), f"[COLOR FF8F9BA6]{url}[/COLOR]", ""]
    return out


lines = [f"Lucent {xbmc.getInfoLabel('System.AddonVersion(skin.lucent)')}", "", *block(31512, DATA), *block(31517, SOFTWARE)]
xbmcgui.Dialog().textviewer(L(31510), "[CR]".join(lines))
