# -*- coding: utf-8 -*-
"""Settings for subtitles, spoken language and skip intro, taken over from the Lucent skin.

The code that came from the skin asked Skin.HasSetting / Skin.String with the skin's names. Here those names map to
Lucent Video's own settings, so that code reads the same as before. Keys are only ever read from the settings,
never logged."""
import os
import shutil

import xbmc
import xbmcaddon
import xbmcvfs

import util

ADDON_ID = util.ADDON_ID
DATA = xbmcvfs.translatePath("special://profile/addon_data/%s/" % ADDON_ID)
SKIN_DATA = xbmcvfs.translatePath("special://profile/addon_data/skin.lucent/")
SUBS_ADDON = "service.subtitles.lucent"

# skin name -> (Lucent Video setting, kind). Kinds: bool, not (the skin stored 'off'), str, bg (mode), ai (mode)
NAMES = {
    "nuvio.autosubs": ("subs_auto", "bool"),
    "lucent.subs.mode": ("subs_mode", "bg"),
    "lucent.subs.bg.ai": ("subs_mode", "ai"),
    "lucent.subs.alwayson": ("subs_always", "bool"),
    "lucent.subs.langfix.off": ("subs_langfix", "not"),
    "lucent.subs.sameaudio.keep": ("subs_quiet_same", "not"),
    "lucent.subs.native.off": ("subs_swap", "not"),
    "lucent.subs.autosync.off": ("subs_autosync", "not"),
    "lucent.subs.next.off": ("subs_next", "not"),
    "lucent.subs.wanted.off": ("subs_wanted", "not"),
    "lucent.subs.ai.keephi": ("subs_ai_keephi", "bool"),
    "lucent.audio.lang1": ("audio_lang1", "str"),
    "lucent.audio.lang2": ("audio_lang2", "str"),
    "lucent.audio.label": ("audio_label", "str"),
    "lucent.ai.provider": ("ai_provider", "str"),
    "lucent.gemini.key": ("ai_gemini_key", "str"),
    "lucent.openrouter.key": ("ai_openrouter_key", "str"),
    "lucent.claude.key": ("ai_claude_key", "str"),
    "lucent.openrouter.model": ("ai_openrouter_model", "str"),
    "lucent.claude.model": ("ai_claude_model", "str"),
    "lucent.skipby": ("skip_by", "str"),
}


_SHARED = {"addon": None}


def _addon():
    """A fresh object (the service runs for days), or the one object a series of writes shares: several objects
    writing one after the other can put each other's old values back."""
    return _SHARED["addon"] or xbmcaddon.Addon(ADDON_ID)


def on(name):
    """Skin.HasSetting(name), from Lucent Video's settings."""
    setting, kind = NAMES[name]
    value = _addon().getSetting(setting)
    if kind == "bool":
        return value.lower() == "true"
    if kind == "not":
        return value.lower() == "false"
    if kind == "ai":
        return value == "2"
    return bool(value)


def text(name):
    """Skin.String(name), from Lucent Video's settings."""
    setting, kind = NAMES[name]
    value = (_addon().getSetting(setting) or "").strip()
    if kind == "bg":
        return "background" if value in ("1", "2") else ""
    return value


def put(name, value):
    """Skin.SetString / SetBool / Reset, into Lucent Video's settings."""
    setting, kind = NAMES[name]
    addon = _addon()
    if kind == "bool":
        addon.setSetting(setting, "true" if value else "false")
    elif kind == "not":
        addon.setSetting(setting, "false" if value else "true")
    elif kind in ("bg", "ai"):
        addon.setSetting(setting, str(value))
    else:
        addon.setSetting(setting, str(value or ""))


def mode():
    """0 show the list, 1 pick by itself in the background, 2 the same, otherwise translate with AI."""
    try:
        return int(_addon().getSetting("subs_mode") or 0)
    except ValueError:
        return 0


def set_mode(value):
    _addon().setSetting("subs_mode", str(value))


def data_dir(name):
    path = os.path.join(DATA, name)
    os.makedirs(path, exist_ok=True)
    return path + os.sep


# ------------------------------------------------------------------ once: take over what the skin had
SKIN_BOOLS = ("nuvio.autosubs", "lucent.subs.alwayson", "lucent.subs.langfix.off", "lucent.subs.sameaudio.keep",
              "lucent.subs.native.off", "lucent.subs.autosync.off", "lucent.subs.next.off", "lucent.subs.wanted.off",
              "lucent.subs.ai.keephi")
SKIN_STRINGS = ("lucent.audio.lang1", "lucent.audio.lang2", "lucent.audio.label", "lucent.ai.provider", "lucent.gemini.key",
                "lucent.openrouter.key", "lucent.claude.key", "lucent.openrouter.model", "lucent.claude.model", "lucent.skipby")
SKIN_KEYS = ("lucent.gemini.key", "lucent.openrouter.key", "lucent.claude.key")


def _copy_tree(source, target):
    if not os.path.isdir(source):
        return 0
    copied = 0
    for root, _dirs, files in os.walk(source):
        rel = os.path.relpath(root, source)
        os.makedirs(os.path.join(target, rel), exist_ok=True)
        for name in files:
            dest = os.path.join(target, rel, name)
            if not os.path.exists(dest):
                shutil.copy2(os.path.join(root, name), dest)
                copied += 1
    return copied


def migrate():
    """When the Lucent skin is the active skin and this was not done yet: its subtitle settings and files come over.
    The AI keys in the skin are cleared afterwards. Home property lucent.video.subs.migrated=1 tells the skin."""
    addon = _addon()
    if addon.getSetting("subs_migrated") == "true":
        util.HOME.setProperty("lucent.video.subs.migrated", "1")
        return
    _SHARED["addon"] = addon
    try:
        _migrate(addon)
    finally:
        _SHARED["addon"] = None


def _migrate(addon):
    if addon.getSetting("subs_migrated") == "true":
        util.HOME.setProperty("lucent.video.subs.migrated", "1")
        return
    if xbmc.getSkinDir() != "skin.lucent":
        return                                   # nothing to take over (another skin): try again next start
    if any(xbmc.getCondVisibility("Skin.HasSetting(%s)" % n) for n in SKIN_BOOLS) or \
            any(xbmc.getInfoLabel("Skin.String(%s)" % n) for n in SKIN_STRINGS):
        for name in SKIN_BOOLS:
            put(name, xbmc.getCondVisibility("Skin.HasSetting(%s)" % name))
        background = xbmc.getInfoLabel("Skin.String(lucent.subs.mode)") == "background"
        set_mode((2 if xbmc.getCondVisibility("Skin.HasSetting(lucent.subs.bg.ai)") else 1) if background else 0)
        for name in SKIN_STRINGS:
            value = xbmc.getInfoLabel("Skin.String(%s)" % name)
            if value:
                put(name, value)
    copied = _copy_tree(os.path.join(SKIN_DATA, "subs_extra"), os.path.join(DATA, "subs_extra"))
    copied += _copy_tree(os.path.join(SKIN_DATA, "subs_ai"), os.path.join(DATA, "subs_ai"))
    for name in SKIN_KEYS:
        if xbmc.getInfoLabel("Skin.String(%s)" % name):
            xbmc.executebuiltin("Skin.SetString(%s,)" % name)
    addon.setSetting("subs_migrated", "true")
    util.HOME.setProperty("lucent.video.subs.migrated", "1")
    util.log("subtitle settings taken over from the skin (%d files)" % copied)


# ------------------------------------------------------------------ short state lines for the skin
def publish():
    T = util.T
    if not on("nuvio.autosubs"):
        state = T("Niet automatisch", "Not automatic")
    else:
        state = [T("Automatisch · lijst", "Automatic · list"), T("Automatisch · op de achtergrond", "Automatic · in the background"),
                 T("Automatisch · op de achtergrond + AI", "Automatic · in the background + AI")][min(mode(), 2)]
    util.HOME.setProperty("lucent.video.subs.state", state)
    try:
        import skipdup
        util.HOME.setProperty("lucent.video.skip.state", skipdup.state_line())
    except Exception as error:      # noqa: BLE001
        util.log("skip state: %s" % type(error).__name__)
