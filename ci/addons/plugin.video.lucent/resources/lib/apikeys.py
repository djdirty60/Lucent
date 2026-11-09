# -*- coding: utf-8 -*-
"""The add-on's own keys. They never live in the code: they come from the settings or a private keys.json.
A tester code is that file as url-safe base64, only to carry it over in one piece. Nothing here is ever logged."""
import base64
import json
import os

import xbmcgui
import xbmcvfs

import keys
import util

T = util.T
FILE = "keys.json"
FIELDS = ("tmdb", "trakt_client_id", "simkl_client_id")


def stored():
    data = util.load_json(FILE, {})
    return data if isinstance(data, dict) else {}


def exists():
    return os.path.exists(os.path.join(util.PROFILE, FILE))


def tmdb():
    return util.setting("tmdb_key") or stored().get("tmdb") or keys.TMDB_KEY


def trakt_id():
    return util.setting("trakt_id") or stored().get("trakt_client_id") or keys.TRAKT_CLIENT_ID


def simkl_id():
    return util.setting("simkl_id") or stored().get("simkl_client_id") or keys.SIMKL_CLIENT_ID


def valid(data):
    """Only the expected fields, all plain text, and at least a TMDB key. Returns a clean copy or None."""
    if not isinstance(data, dict) or not data or set(data) - set(FIELDS):
        return None
    if not all(isinstance(value, str) and value.strip() and value.strip().isalnum() for value in data.values()):
        return None
    if "tmdb" not in data:
        return None
    return {name: value.strip() for name, value in data.items()}


def encode(data):
    raw = json.dumps(data, separators=(",", ":")).encode("utf-8")
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def decode(code):
    text = "".join((code or "").split())
    text = text.replace("+", "-").replace("/", "_").rstrip("=")
    try:
        return valid(json.loads(base64.urlsafe_b64decode((text + "=" * (-len(text) % 4)).encode("ascii")).decode("utf-8")))
    except (ValueError, UnicodeError):
        return None


def _store(data):
    if not data:
        return False
    util.save_json(FILE, data)
    util.cache_clear()
    util.notify(T("Sleutels ingesteld", "Keys are set"))
    return True


def enter_code():
    code = xbmcgui.Dialog().input(T("Testercode invoeren", "Enter tester code"))
    if not code:
        return False
    if _store(decode(code)):
        return True
    xbmcgui.Dialog().ok("Lucent", T("Deze testercode klopt niet. Controleer de code en probeer het opnieuw.",
                                    "This tester code is not valid. Check it and try again."))
    return False


def choose_file():
    path = xbmcgui.Dialog().browse(1, T("Sleutelbestand kiezen", "Choose key file"), "files", ".json")
    if not path:
        return False
    handle = xbmcvfs.File(path)
    try:
        text = handle.read()
    finally:
        handle.close()
    try:
        data = valid(json.loads(text))
    except ValueError:
        data = None
    if _store(data):
        return True
    xbmcgui.Dialog().ok("Lucent", T("Dit bestand is geen geldig sleutelbestand.", "This file is not a valid key file."))
    return False


def show_code():
    data = valid(stored())
    if not data:
        xbmcgui.Dialog().ok("Lucent", T("Er is nog geen sleutelbestand op dit apparaat.", "There is no key file on this device yet."))
        return
    xbmcgui.Dialog().textviewer(T("Jouw testercode, alleen privé delen", "Your tester code, share privately only"), encode(data))
