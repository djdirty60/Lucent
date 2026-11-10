# -*- coding: utf-8 -*-
"""Family profiles: everybody has their own account, progress and lists. The first profile keeps the existing files."""
import os
import shutil
import time

import xbmcaddon

import util

T = util.T
COLORS = ["FF3B5F86", "FF8A4F7D", "FF4C8A5F", "FFB0723C", "FF7A6BC2", "FF3C8C93", "FFA8505A", "FF6C7F3A"]
MAIN = "main"


def _data():
    data = util.load_json(util.USERS, {})
    if not data.get("users"):
        data = {"current": MAIN, "users": [{"id": MAIN, "name": T("Profiel 1", "Profile 1"), "color": COLORS[0]}]}
    return data


def everyone():
    return _data()["users"]


def current_id():
    return util.current_user()


def current():
    return next((u for u in everyone() if u["id"] == current_id()), everyone()[0])


def choose(user_id):
    data = _data()
    data["current"] = user_id
    util.save_json(util.USERS, data)


def add(name, tracker):
    data = _data()
    user = {"id": "u%d" % int(time.time()), "name": name, "color": COLORS[len(data["users"]) % len(COLORS)], "tracker": tracker}
    data["users"].append(user)
    data["current"] = user["id"]
    util.save_json(util.USERS, data)
    return user


def rename(user_id, name):
    data = _data()
    for user in data["users"]:
        if user["id"] == user_id:
            user["name"] = name
    util.save_json(util.USERS, data)


def remove(user_id):
    """The first profile stays."""
    if user_id == MAIN:
        return
    data = _data()
    data["users"] = [u for u in data["users"] if u["id"] != user_id]
    if data["current"] == user_id:
        data["current"] = MAIN
    util.save_json(util.USERS, data)
    shutil.rmtree(os.path.join(util.PROFILE, "users", user_id), ignore_errors=True)


def tracker_choice():
    """0 Trakt, 1 Simkl, 2 only this device."""
    user = current()
    if user["id"] == MAIN:
        return util.number("tracker", 0)
    return int(user.get("tracker", 2))


def set_tracker(value):
    if current_id() == MAIN:
        xbmcaddon.Addon(util.ADDON_ID).setSetting("tracker", str(value))
        return
    data = _data()
    for user in data["users"]:
        if user["id"] == current_id():
            user["tracker"] = value
    util.save_json(util.USERS, data)


def set_value(user_id, name, value):
    data = _data()
    for user in data["users"]:
        if user["id"] == user_id:
            user[name] = value
    util.save_json(util.USERS, data)


def settings_value(name):
    """Values for all profiles together, such as the PIN hash."""
    return (_data().get("shared") or {}).get(name, "")


def set_settings_value(name, value):
    data = _data()
    data.setdefault("shared", {})[name] = value
    util.save_json(util.USERS, data)
