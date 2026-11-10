# -*- coding: utf-8 -*-
"""Kids profiles: a profile can have an age limit. Titles above it, or without a known age rating, are left out,
and they cannot be played from that profile either. A PIN (stored only as a hash) guards leaving a kids profile."""
import hashlib
import re

import xbmcgui

import users
import util

T = util.T
AGES = [0, 6, 9, 12, 16]                      # 0 = no limit
RATING = {"AL": 0, "G": 0, "TV-Y": 0, "TV-G": 0, "6": 6, "TV-Y7": 7, "PG": 9, "TV-PG": 9, "9": 9, "12": 12, "PG-13": 13,
          "14": 14, "TV-14": 14, "16": 16, "R": 17, "TV-MA": 17, "NC-17": 18, "18": 18}


def limit():
    return int(users.current().get("max_age") or 0)


def age_of(meta):
    rating = str(meta.get("mpaa") or "").upper().replace("RATED ", "").strip()
    if rating in RATING:
        return RATING[rating]
    number = re.match(r"^(\d{1,2})\+?$", rating)
    return int(number.group(1)) if number else None


def allowed(meta):
    top = limit()
    if not top:
        return True
    age = age_of(meta)
    return age is not None and age <= top


def keep(titles):
    return titles if not limit() else [m for m in titles if allowed(m)]


def _hash(pin):
    return hashlib.sha256(("lucent-video:" + pin).encode("utf-8")).hexdigest()




def ask_pin(reason):
    """True when there is no PIN or the right one was typed."""
    saved = users.settings_value("pin")
    if not saved:
        return True
    typed = xbmcgui.Dialog().numeric(0, reason, bsHidden=True)
    if typed and _hash(typed) == saved:
        return True
    if typed:
        util.notify(T("Pincode klopt niet", "Wrong PIN"))
    return False


def set_pin():
    if not ask_pin(T("Huidige pincode", "Current PIN")):
        return
    first = xbmcgui.Dialog().numeric(0, T("Nieuwe pincode (leeg = geen pincode)", "New PIN (empty = no PIN)"), bsHidden=True)
    if not first:
        users.set_settings_value("pin", "")
        util.notify(T("Pincode uitgezet", "PIN turned off"))
        return
    if xbmcgui.Dialog().numeric(0, T("Nog een keer", "Once more"), bsHidden=True) != first:
        util.notify(T("De pincodes zijn niet gelijk", "The PINs do not match"))
        return
    users.set_settings_value("pin", _hash(first))
    util.notify(T("Pincode ingesteld", "PIN set"))


def choose_limit(user_id):
    names = [T("Geen grens", "No limit")] + [T("Tot en met %d jaar", "Up to %d years") % a for a in AGES[1:]]
    person = next(u for u in users.everyone() if u["id"] == user_id)
    now = AGES.index(int(person.get("max_age") or 0)) if int(person.get("max_age") or 0) in AGES else 0
    choice = xbmcgui.Dialog().select(T("Leeftijdsgrens voor %s", "Age limit for %s") % person["name"], names, preselect=now)
    if choice < 0:
        return
    if AGES[choice] < int(person.get("max_age") or 0) or not person.get("max_age") or ask_pin(T("Pincode", "PIN")):
        users.set_value(user_id, "max_age", AGES[choice])
