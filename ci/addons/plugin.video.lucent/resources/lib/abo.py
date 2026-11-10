# -*- coding: utf-8 -*-
"""Watch on your own subscription: when a title is also on a streaming service you pay for (Netflix, Videoland ...),
Lucent asks whether to open that app instead. You choose your subscriptions once (Settings > Sources).
Opening an app works on Android devices (Fire TV, Google TV, Shield); elsewhere Lucent only tells you where it is."""
import xbmc
import xbmcgui

import tmdb
import util

T = util.T
FILE = "subscriptions.json"
# name part (lower case) -> Android package names to try, TV versions first
APPS = [
    ("netflix", ["com.netflix.ninja", "com.netflix.mediaclient"]),
    ("disney", ["com.disney.disneyplus"]),
    ("videoland", ["nl.rtl.videoland.v2", "nl.rtl.videoland"]),
    ("hbo", ["com.wbd.stream", "com.hbo.hbonow"]),
    ("max", ["com.wbd.stream"]),
    ("amazon", ["com.amazon.amazonvideo.livingroom", "com.amazon.avod.thirdpartyclient"]),
    ("prime", ["com.amazon.amazonvideo.livingroom", "com.amazon.avod.thirdpartyclient"]),
    ("apple tv", ["com.apple.atve.androidtv.appletv", "com.apple.atve.amazon.appletv"]),
    ("skyshowtime", ["com.skyshowtime.skyshowtime.google", "com.skyshowtime.skyshowtime.amazon"]),
    ("npo", ["nl.uitzendinggemist"]),
    ("paramount", ["com.cbs.ott", "com.cbs.app"]),
    ("pathé", ["nl.pathe.thuis"]),
]


def mine():
    return util.load_json(FILE, [])


def choose():
    try:
        services = tmdb.providers()
    except util.HttpError:
        util.notify(T("De diensten kunnen nu niet worden opgehaald", "The services cannot be loaded now"))
        return
    have = {int(entry[0]) for entry in mine()}
    names = [name for _pid, name, _logo in services]
    picked = xbmcgui.Dialog().multiselect(T("Welke abonnementen heb je?", "Which subscriptions do you have?"), names,
                                          preselect=[n for n, (pid, _name, _logo) in enumerate(services) if int(pid) in have])
    if picked is None:
        return
    util.save_json(FILE, [[services[n][0], services[n][1]] for n in picked])
    util.notify(T("%d abonnementen bewaard", "%d subscriptions saved") % len(picked))


def on_mine(meta):
    """The name of one of your subscriptions that has this title, or ''."""
    own = {int(pid): name for pid, name in mine()}
    if not own or meta.get("kind") not in ("movie", "episode", "tvshow"):
        return ""
    api = "movie" if meta["kind"] == "movie" else "tv"
    try:
        found = tmdb.get("%s/%s/watch/providers" % (api, meta["tmdb"]), ttl=tmdb.DAY).get("results", {}).get(tmdb.region(), {})
    except util.HttpError:
        return ""
    for row in found.get("flatrate") or []:
        if int(row.get("provider_id") or 0) in own:
            return own[int(row["provider_id"])]
    return ""


def packages(name):
    low = name.lower()
    return next((apps for part, apps in APPS if part in low), [])


def offer(meta):
    """True when the app was opened (then Lucent does not play)."""
    if not util.flag("abo_ask"):
        return False
    name = on_mine(meta)
    if not name:
        return False
    android = xbmc.getCondVisibility("System.Platform.Android")
    apps = packages(name) if android else []
    if not apps:
        util.notify(T("Ook op %s, met je eigen abonnement", "Also on %s, with your own subscription") % name)
        return False
    choice = xbmcgui.Dialog().select(T("%s staat ook op %s" % (meta.get("show") or meta["title"], name), "%s is also on %s" % (meta.get("show") or meta["title"], name)),
                                     [T("Hier kijken met Lucent", "Watch here with Lucent"), T("Openen in de app van %s", "Open in the %s app") % name])
    if choice != 1:
        return False
    xbmc.executebuiltin("StartAndroidActivity(%s)" % apps[0])
    util.log("opened the app for %s" % name)
    return True
