# -*- coding: utf-8 -*-
"""Lucent: the Back button stops the video while you are watching, and Enter on a keyboard finishes typing.

Kodi skins cannot change what Back does in the full screen player, so this writes a small keymap
(special://profile/keymaps/lucent-back-stop.xml) and asks Kodi to reload its keymaps. It only
changes the full screen video; on the on-screen keyboard the Enter key of a real keyboard means Done
(instead of typing the key that is highlighted); menus, the OSD and the pause screen keep their normal Back.
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
            <backspace>Stop</backspace>
            <escape>Stop</escape>
            <browser_back>Stop</browser_back>
        </keyboard>
        <remote>
            <back>Stop</back>
        </remote>
    </FullscreenVideo>
    <VirtualKeyboard>
        <keyboard>
            <return>Enter</return>
            <enter>Enter</enter>
        </keyboard>
    </VirtualKeyboard>
</keymap>
"""


def log(text):
    xbmc.log(f"[skin.lucent] keymap: {text}", xbmc.LOGINFO)


def current():
    if not xbmcvfs.exists(PATH):
        return None
    with xbmcvfs.File(PATH) as fh:
        return fh.read()


def main():
    enabled = xbmc.getInfoLabel("Skin.String(nuvio.backstop)") != "off"
    have = current()
    if enabled and have != KEYMAP:
        xbmcvfs.mkdirs(DIR)
        with xbmcvfs.File(PATH, "w") as fh:
            fh.write(KEYMAP)
        xbmc.executebuiltin("Action(reloadkeymaps)")
        log("Back now stops the video")
    elif not enabled and have is not None:
        xbmcvfs.delete(PATH)
        xbmc.executebuiltin("Action(reloadkeymaps)")
        log("removed")


if __name__ == "__main__":
    main()
