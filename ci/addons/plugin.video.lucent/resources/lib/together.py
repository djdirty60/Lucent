# -*- coding: utf-8 -*-
"""Watching together: before a film or episode starts you tick who watches along. When it is watched, it is marked
as seen for every one of them, each in their own account (Trakt, Simkl or only this device)."""
import threading

import xbmcgui

import users
import util

T = util.T
_LOCK = threading.Lock()


def ask(params):
    """The ids of the other profiles watching along, or [] . Uses the answer of the previous episode for the next one."""
    if params.get("with") is not None:
        return [i for i in params["with"].split(",") if i]
    people = [u for u in users.everyone() if u["id"] != users.current_id()]
    if not people or not util.flag("together") or params.get("autoplay") == "1":
        return []
    picked = xbmcgui.Dialog().multiselect(T("Wie kijkt er mee?", "Who watches along?"), [u["name"] for u in people])
    return [people[n]["id"] for n in picked or []]


def mark(meta, others):
    """Marks this title as watched for each profile that watched along."""
    import tracker
    for user_id in others or []:
        with _LOCK:
            util.OVERRIDE_USER = user_id
            try:
                tracker.set_watched(meta, True)
            except util.HttpError as error:
                util.log("watching together: %s" % error)
            finally:
                util.OVERRIDE_USER = None
    if others:
        names = [u["name"] for u in users.everyone() if u["id"] in others]
        util.notify(T("Ook bekeken voor %s", "Also watched for %s") % ", ".join(names))
