# -*- coding: utf-8 -*-
"""Lucent: everything that has to happen once when Kodi starts, in ONE Python start.

    RunScript(special://skin/scripts/startup.py)      from Home.xml, only the first time Home opens

Before this, Home started five or six separate scripts at the same time (key maps, rating logos, the Calendar and
Sport tabs, the helper). Every one of them is its own Python interpreter, and on a small box they all compete with
Seren and the widgets that load at that moment. Now the quick jobs run here after each other, and the long-running
helper is started last, in this same interpreter.
"""
import xbmc


def log(text):
    xbmc.log(f"[skin.lucent] startup: {text}", xbmc.LOGINFO)


def step(name, func):
    try:
        func()
    except Exception as error:  # noqa: BLE001 - one job must never stop the others
        log(f"{name}: {error}")


def run():
    import keymap
    step("keymap", keymap.main)
    import settings
    step("logos", settings.scan_logos)
    import agenda
    step("calendar tab", agenda.ensure_tab)
    if xbmc.getCondVisibility("Pvr.HasTVChannels"):
        import sport
        step("sport tab", sport.ensure_tab)
    import helper
    helper.run()                                     # keeps running until Kodi stops or the skin is updated


if __name__ == "__main__":
    run()
