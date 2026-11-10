# -*- coding: utf-8 -*-
"""Your subtitle languages: Kodi's 'Preferred subtitle language' and the language of the Kodi interface.
(The automatic search itself is in subwatch.py and works for every video.)"""
import json

import xbmc



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
