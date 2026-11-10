# -*- coding: utf-8 -*-
"""Bedtime for a profile: a time and/or a number of titles per day. Before the last one a full screen says it is the
last for today; after bedtime 'Sleep well!' and nothing plays, unless the PIN is typed. The next episode does not
start by itself after the last one."""
import datetime

import xbmcgui

import dialogs
import kids
import users
import util

T = util.T
FILE = "bedtime.json"
NIGHT_ENDS = 5          # until 05:00 it still counts as last night


def settings():
    user = users.current()
    return user.get("bedtime") or "", int(user.get("max_titles") or 0)


def _day():
    now = datetime.datetime.now()
    return (now - datetime.timedelta(days=1) if now.hour < NIGHT_ENDS else now).date().isoformat()


def _count():
    data = util.load_json(FILE, {}).get(users.current_id(), {})
    return data.get("count", 0) if data.get("day") == _day() else 0


def counted():
    data = util.load_json(FILE, {})
    mine = data.get(users.current_id(), {})
    data[users.current_id()] = {"day": _day(), "count": (mine.get("count", 0) if mine.get("day") == _day() else 0) + 1}
    util.save_json(FILE, data)


def _minutes_to_bedtime(at):
    try:
        hour, minute = (int(x) for x in at.split(":"))
    except ValueError:
        return None
    now = datetime.datetime.now()
    if now.hour < NIGHT_ENDS:
        return -1
    bed = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
    return (bed - now).total_seconds() / 60


class Screen(dialogs.Base):
    def onInit(self):
        self.fill(self.args["props"])
        self.setFocusId(10)

    def onClick(self, control):
        self.result = control
        self.close()


def _show(props):
    window = Screen("lucent_bedtime.xml", dialogs.PATH, "Default", "1080i", props=props)
    window.doModal()
    result = window.result
    del window
    return result


def check(meta):
    """Before playing. Returns (may play, is the last one)."""
    at, most = settings()
    if not at and not most:
        return True, False
    name = users.current()["name"]
    left = _minutes_to_bedtime(at) if at else None
    count = _count()
    over = (left is not None and left <= 0) or (most and count >= most)
    if over:
        choice = _show({"btitle": T("Welterusten!", "Sleep well!"), "btext": T("Het is bedtijd. Morgen kun je weer verder kijken.", "It is bedtime. You can watch again tomorrow."),
                        "b1": T("Oké", "OK"), "b2": T("Pincode", "PIN")})
        if choice == 11 and kids.ask_pin(T("Pincode", "PIN")):
            return True, True
        return False, False
    runtime = int(meta.get("runtime") or 45)
    last = (left is not None and left <= runtime) or (most and count + 1 >= most)
    if last:
        text = (T("Bedtijd voor %s is om %s. Daarna gaat Lucent niet verder.", "Bedtime for %s is at %s. After that Lucent does not go on.") % (name, at)
                if at else T("Dit is nummer %d van vandaag. Daarna gaat Lucent niet verder.", "This is number %d of today. After that Lucent does not go on.") % most)
        choice = _show({"btitle": T("Dit is de laatste voor vandaag", "This is the last one for today"), "btext": text,
                        "b1": T("Kijken", "Watch"), "b2": T("Pincode: nog één", "PIN: one more")})
        if choice is None:
            return False, False
        if choice == 11 and kids.ask_pin(T("Pincode", "PIN")):
            return True, False
    return True, bool(last)


def after_last():
    _show({"btitle": T("Welterusten!", "Sleep well!"), "btext": T("Dat was de laatste voor vandaag. Morgen kun je weer verder kijken.", "That was the last one for today. You can watch again tomorrow."),
           "b1": T("Oké", "OK"), "b2": ""})


def choose(user_id):
    """In 'Who is watching?': set bedtime and the number of titles per day for a profile."""
    person = next(u for u in users.everyone() if u["id"] == user_id)
    choice = xbmcgui.Dialog().select(T("Bedtijd voor %s", "Bedtime for %s") % person["name"],
                                     [T("Bedtijd: %s", "Bedtime: %s") % (person.get("bedtime") or T("uit", "off")),
                                      T("Per dag: %s", "Per day: %s") % (person.get("max_titles") or T("geen grens", "no limit"))])
    if choice == 0:
        typed = xbmcgui.Dialog().numeric(2, T("Bedtijd (leeg = uit)", "Bedtime (empty = off)"), person.get("bedtime") or "19:30")
        users.set_value(user_id, "bedtime", typed.strip() if typed and typed.strip() not in ("", "0:00", "00:00") else "")
    elif choice == 1:
        options = [T("Geen grens", "No limit")] + [str(n) for n in range(1, 11)]
        picked = xbmcgui.Dialog().select(T("Hoeveel films of afleveringen per dag?", "How many films or episodes per day?"), options)
        if picked >= 0:
            users.set_value(user_id, "max_titles", picked)
