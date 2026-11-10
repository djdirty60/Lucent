# -*- coding: utf-8 -*-
"""Search subtitles by itself when a film or episode from Lucent Video starts without one in your language.

With the Lucent skin this is left to the skin (Lucent Ondertitels and its own setting), so the search never opens twice.
Your language = Kodi's 'Preferred subtitle language' and the language of the Kodi interface.
"""
import json

import xbmc

import util

SKIN = "skin.lucent"


def _setting(name):
    query = {"jsonrpc": "2.0", "id": 1, "method": "Settings.GetSettingValue", "params": {"setting": name}}
    try:
        return json.loads(xbmc.executeJSONRPC(json.dumps(query))).get("result", {}).get("value")
    except (ValueError, TypeError):
        return None


def _code(value):
    value = (value or "").strip().lower()
    if not value or value in ("und", "unk", "unknown", "mul", "zxx"):
        return ""
    if value in ("dut", "nld"):
        return "nl"
    if len(value) == 2:
        return value
    try:
        code = (xbmc.convertLanguage(value, xbmc.ISO_639_1) or "").lower()
    except Exception:          # Kodi does not know it
        code = ""
    return code if len(code) == 2 else ""


def mine():
    langs = {_code(xbmc.getLanguage(xbmc.ISO_639_1))}
    pref = _setting("locale.subtitlelanguage")
    if isinstance(pref, str) and pref not in ("default", "none", "forced_only", "original"):
        langs.add(_code(pref))
    return {c for c in langs if c}


def wanted(meta):
    if not util.flag("subs_auto") or xbmc.getSkinDir() == SKIN:
        return False
    service = _setting("subtitles.tv" if meta.get("kind") == "episode" else "subtitles.movie")
    return bool(service)


def check(player, meta):
    """Called a few seconds after the start."""
    if not wanted(meta) or not player.isPlayingVideo():
        return
    langs = mine()
    if not langs:
        return
    try:
        audio = _code(xbmc.getInfoLabel("VideoPlayer.AudioLanguage"))
        have = {_code(s) for s in player.getAvailableSubtitleStreams() or []}
    except RuntimeError:
        return
    if audio in langs or have & langs:
        return
    util.log("no subtitle in %s: opening the subtitle search" % ",".join(sorted(langs)))
    xbmc.executebuiltin("ActivateWindow(subtitlesearch)")
