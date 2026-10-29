# -*- coding: utf-8 -*-
"""Lucent: the Back button stops the video while you are watching.

Kodi skins cannot change what Back does in the full screen player, so this writes a small keymap
(special://profile/keymaps/lucent-back-stop.xml) and asks Kodi to reload its keymaps. It only
changes the full screen video; menus, the OSD and the pause screen keep their normal Back.
(Until 1.31.27 this file also made the Enter key finish the on-screen keyboard. Many remotes - CoreELEC especially -
send their OK button as the Enter key, so OK on a letter closed the keyboard. That part is gone; the file is rewritten.)
Set Skin.String(nuvio.backstop) to "off" (or delete the file) to get the old behaviour back.
Runs from the Home screen; it does nothing when the file is already right.
"""
import xbmc
import xbmcvfs

DIR = "special://profile/keymaps/"
PATH = DIR + "lucent-back-stop.xml"
KEYMAP = """<keymap>
    <FullscreenVideo>
        <keyboard>
            <backspace>RunScript(special://skin/scripts/fsback.py)</backspace>
            <escape>RunScript(special://skin/scripts/fsback.py)</escape>
            <browser_back>RunScript(special://skin/scripts/fsback.py)</browser_back>
        </keyboard>
        <remote>
            <back>RunScript(special://skin/scripts/fsback.py)</back>
        </remote>
    </FullscreenVideo>
</keymap>
"""


def log(text):
    xbmc.log(f"[skin.lucent] keymap: {text}", xbmc.LOGINFO)


def current():
    if not xbmcvfs.exists(PATH):
        return None
    with xbmcvfs.File(PATH) as fh:
        return fh.read()


OK_PATH = DIR + "lucent-ok-page.xml"
OK_KEYMAP = """<keymap>
    <videos>   <!-- Kodi's keymap name for MyVideoNav.xml (the video lists); "MyVideoNav" itself is not recognised -->
        <keyboard>
            <return>RunScript(special://skin/scripts/openitem.py)</return>
            <enter>RunScript(special://skin/scripts/openitem.py)</enter>
        </keyboard>
        <remote>
            <select>RunScript(special://skin/scripts/openitem.py)</select>
        </remote>
    </videos>
</keymap>
"""


HOME_PATH = DIR + "lucent-home.xml"
BTN = "ActivateWindow(Home)"
def _home_keymap():
    body = (
        "        <keyboard>\n"
        "            <browser_home>%(b)s</browser_home>\n"
        "            <home>%(b)s</home>\n"
        "            <homepage>%(b)s</homepage>\n"
        "        </keyboard>\n"
        "        <remote>\n"
        "            <start>%(b)s</start>\n"
        "            <rootmenu>%(b)s</rootmenu>\n"
        "            <homepage>%(b)s</homepage>\n"
        "        </remote>\n"
    ) % {"b": BTN}
    out = "<keymap>\n"
    # the info page (movieinformation) and the players have their own sections in Kodi's keymaps, so they are named too
    # (not in <global>: there the Home key of a keyboard stays "first item of the list")
    for win in ("MovieInformation", "FullscreenVideo", "VideoOSD", "SeekBar", "VideoMenu"):
        out += "    <%s>\n%s    </%s>\n" % (win, body, win)
    out += "    <global>\n%s    </global>\n" % body.replace("            <home>%s</home>\n" % BTN, "")
    return out + "</keymap>\n"


HOME_KEYMAP = _home_keymap()


def read(path):
    if not xbmcvfs.exists(path):
        return None
    with xbmcvfs.File(path) as fh:
        return fh.read()


def sync(path, text, wanted):
    """Make the keymap file exist with this text (wanted) or not exist. True when something changed."""
    have = read(path)
    if wanted and have != text:
        xbmcvfs.mkdirs(DIR)
        with xbmcvfs.File(path, "w") as fh:
            fh.write(text)
        return True
    if not wanted and have is not None:
        xbmcvfs.delete(path)
        return True
    return False


def main():
    changed = sync(PATH, KEYMAP, xbmc.getInfoLabel("Skin.String(nuvio.backstop)") != "off")
    # OK opens the page first for films / episodes in the Kodi video lists (Seren folders): only when chosen in Skin settings
    ok_wanted = xbmc.getCondVisibility("Skin.HasSetting(nuvio.ok.movie.page) | Skin.HasSetting(nuvio.ok.episode.page)")
    changed = sync(OK_PATH, OK_KEYMAP, ok_wanted) or changed
    # the Home button of the remote goes to the Home screen from every window (switch off: Skin.String(nuvio.homekey) = off)
    changed = sync(HOME_PATH, HOME_KEYMAP, xbmc.getInfoLabel("Skin.String(nuvio.homekey)") != "off") or changed
    if changed:
        xbmc.executebuiltin("Action(reloadkeymaps)")
        log("keymaps updated")


if __name__ == "__main__":
    main()
