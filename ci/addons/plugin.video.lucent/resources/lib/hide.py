# -*- coding: utf-8 -*-
"""Keeping lists clean: titles in languages you chose to hide, and films and series you cannot watch yet.

- Hidden languages (setting hide_languages, chosen with action=hide_languages): by the title's original language.
- Only what you can watch (setting only_digital, on by default): a film stays out until its digital, disc or TV
  release (TMDB release dates), a series until its first episode has aired.
Languages are only hidden in lists for discovering titles (your own lists hold what you put there yourself).
'Only what you can watch' counts everywhere, your watchlist and own lists too, except in lists that are about what
is not out yet or what you are already watching: Coming soon, In cinemas, the calendar, new seasons, Continue
watching, Next up, Ready for tonight, alerts, the Kodi library rows and search."""
import datetime

import xbmcgui

import util

T = util.T
LANGUAGES = [("zh", "Chinees (Mandarijn)", "Chinese (Mandarin)"), ("cn", "Chinees (Kantonees)", "Chinese (Cantonese)"),
             ("ko", "Koreaans", "Korean"), ("ja", "Japans", "Japanese"), ("hi", "Hindi", "Hindi"), ("ta", "Tamil", "Tamil"),
             ("te", "Telugu", "Telugu"), ("th", "Thai", "Thai"), ("tl", "Filipijns", "Filipino"), ("id", "Indonesisch", "Indonesian"),
             ("tr", "Turks", "Turkish"), ("ru", "Russisch", "Russian"), ("es", "Spaans", "Spanish"), ("pt", "Portugees", "Portuguese")]
# lists that are about discovering titles; everything else is left alone
DISCOVER = ("trending_movie", "popular_movie", "toprated_movie", "trending_tv", "popular_tv", "toprated_tv", "airing_tv", "genre",
            "similar", "foryou", "new_tv", "company", "decade", "award", "provider", "service_list", "person", "kompas_foryou",
            "kompas_because", "kompas_gems", "kompas_new", "kompas_trending", "kompas_saved")
# 'only what you can watch' leaves these alone
NOT_YET = ("upcoming_movie", "upcoming_tv", "nowplaying_movie", "calendar", "new_seasons", "continue", "continue_movie",
           "continue_episode", "nextup", "tonight", "alerts", "lib_newseasons", "lib_newepisodes", "search")


def languages():
    return {code.strip() for code in util.setting("hide_languages").split(",") if code.strip()}


def can_watch(meta):
    if meta.get("kind") not in ("movie", "tvshow"):
        return True
    if "digital" not in meta:                      # saved before this check existed: keep it
        return True
    day = meta.get("digital") or ""
    return bool(day) and day <= datetime.date.today().isoformat()


def keep(titles, name=""):
    hidden = languages() if not name or name in DISCOVER else set()
    digital = util.setting("only_digital").lower() != "false" and name not in NOT_YET
    if not hidden and not digital:
        return titles
    return [m for m in titles if not (m.get("lang") and m["lang"] in hidden) and (not digital or can_watch(m))]


def choose():
    """Settings button: tick the languages to hide."""
    hidden = languages()
    names = [T(nl, en) for _code, nl, en in LANGUAGES]
    picked = xbmcgui.Dialog().multiselect(T("Welke talen verbergen?", "Which languages to hide?"), names,
                                          preselect=[n for n, entry in enumerate(LANGUAGES) if entry[0] in hidden])
    if picked is None:
        return
    util.ADDON.setSetting("hide_languages", ",".join(LANGUAGES[n][0] for n in picked))
    import widgets
    widgets.mark_old()
    util.notify(T("Lijsten worden bijgewerkt", "Lists are being updated"))
