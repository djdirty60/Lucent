# -*- coding: utf-8 -*-
"""Kodi helpers, HTTP and a small file cache. Secrets (the AIOStreams address, tokens) are never logged."""
import hashlib
import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request

import xbmc
import xbmcaddon
import xbmcgui
import xbmcvfs

ADDON_ID = "plugin.video.lucent"
BASE = "plugin://%s/" % ADDON_ID
ADDON = xbmcaddon.Addon(ADDON_ID)
NL = xbmc.getLanguage(xbmc.ISO_639_1) == "nl"
HOME = xbmcgui.Window(10000)
PROFILE = xbmcvfs.translatePath("special://profile/addon_data/%s/" % ADDON_ID)
CACHE = os.path.join(xbmcvfs.translatePath("special://temp/"), "lucent_video")


def T(nl, en):
    return nl if NL else en


def log(text, level=xbmc.LOGINFO):
    xbmc.log("[lucent.video] %s" % text, level)


def setting(name):
    return (xbmcaddon.Addon(ADDON_ID).getSetting(name) or "").strip()     # a fresh object: the service runs for days


def flag(name):
    return setting(name).lower() == "true"


def number(name, default):
    try:
        return int(setting(name))
    except ValueError:
        return default


def notify(text, heading="Lucent"):
    xbmcgui.Dialog().notification(heading, text, xbmcgui.NOTIFICATION_INFO, 4000)


def url_for(**params):
    clean = {k: v for k, v in params.items() if v not in (None, "")}
    return BASE + "?" + urllib.parse.urlencode(sorted(clean.items()))


class HttpError(Exception):
    def __init__(self, status, detail=None):
        Exception.__init__(self, "HTTP %s" % status)
        self.status = status
        self.detail = detail or {}


def http(url, data=None, headers=None, timeout=20, method=None, form=None, raw=None):
    """Returns (parsed json or None, response headers). The error never holds the URL."""
    head = {"User-Agent": "Lucent-Video/0.1", "Accept": "application/json"}
    head.update(headers or {})
    body = None
    if data is not None:
        body = json.dumps(data).encode("utf-8")
        head["Content-Type"] = "application/json"
    elif raw is not None:
        body, head["Content-Type"] = raw
    elif form is not None:
        body = urllib.parse.urlencode(form).encode("utf-8")
        head["Content-Type"] = "application/x-www-form-urlencoded"
    request = urllib.request.Request(url, data=body, headers=head, method=method)
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            raw = response.read()
            return (json.loads(raw.decode("utf-8")) if raw else None), dict(response.headers)
    except urllib.error.HTTPError as error:
        try:
            detail = json.loads(error.read().decode("utf-8"))
        except (ValueError, OSError):
            detail = {}
        raise HttpError(error.code, detail if isinstance(detail, dict) else {}) from None
    except (urllib.error.URLError, OSError, ValueError) as error:
        raise HttpError(type(error).__name__) from None


def _cache_path(key):
    return os.path.join(CACHE, hashlib.sha1(_user_key(key).encode("utf-8")).hexdigest() + ".json")


def cache_get(key, ttl):
    path = _cache_path(key)
    try:
        if time.time() - os.path.getmtime(path) > ttl:
            return None
        with open(path, encoding="utf-8") as handle:
            return json.load(handle)
    except (OSError, ValueError):
        return None


def cache_set(key, value):
    try:
        os.makedirs(CACHE, exist_ok=True)
        path = _cache_path(key)
        with open(path + ".tmp", "w", encoding="utf-8") as handle:
            json.dump(value, handle)
        os.replace(path + ".tmp", path)
    except (OSError, TypeError, ValueError):
        pass


def cache_drop(key):
    try:
        os.remove(_cache_path(key))
    except OSError:
        pass


def cache_clear():
    try:
        for name in os.listdir(CACHE):
            os.remove(os.path.join(CACHE, name))
    except OSError:
        pass


USERS = "users.json"
PER_USER = {"kompas_profile.json", "kompas_ratings.json", "kompas_rows.json", "kompas_shown.json", "kompas_saved.json", "search_history.json", "trakt.json", "simkl.json", "simkl_state.json", "watched.json", "watchlist.json", "progress.json", "last_release.json"}


OVERRIDE_USER = None      # set for a moment while marking a title for someone who watched along


def current_user():
    if OVERRIDE_USER:
        return OVERRIDE_USER
    try:
        with open(os.path.join(PROFILE, USERS), encoding="utf-8") as handle:
            return json.load(handle).get("current") or "main"
    except (OSError, ValueError):
        return "main"


def _path(name):
    """The first profile keeps its files where they always were; the others get their own folder."""
    user = current_user()
    if name in PER_USER and user != "main":
        return os.path.join(PROFILE, "users", user, name)
    return os.path.join(PROFILE, name)


def _user_key(key):
    """Account answers are cached per person; TMDB answers are shared."""
    user = current_user()
    return "%s|%s" % (user, key) if user != "main" and key.startswith(("trakt", "simkl", "nextup")) \
        and not key.startswith("traktsearch/") else key


def load_json(name, default):
    try:
        with open(_path(name), encoding="utf-8") as handle:
            return json.load(handle)
    except (OSError, ValueError):
        return default


def save_json(name, value):
    path = _path(name)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path + ".tmp", "w", encoding="utf-8") as handle:
        json.dump(value, handle)
    os.replace(path + ".tmp", path)
