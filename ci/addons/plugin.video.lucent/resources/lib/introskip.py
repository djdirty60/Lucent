# -*- coding: utf-8 -*-
"""Skip intros by themselves, per series. Uses TheIntroDB (plugin.video.tidb), which the Lucent skin installs:
before an episode starts, its 'skip by itself' settings (intro, recap, preview) are set for this series. Series
without a choice keep TheIntroDB's own setting."""
import xbmc
import xbmcaddon

import util

T = util.T
TIDB = "plugin.video.tidb"
KEYS = ("auto_skip_intro", "auto_skip_recap", "auto_skip_preview")
FILE = "intro_skip.json"


def available():
    return xbmc.getCondVisibility("System.HasAddon(%s)" % TIDB)


def _tidb():
    return xbmcaddon.Addon(TIDB)


def prepare(meta):
    if meta.get("kind") != "episode" or not available():
        return
    data = util.load_json(FILE, {})
    choice = data.get("series", {}).get(str(meta["tmdb"]))
    addon = _tidb()
    if "default" not in data:                     # TheIntroDB's own setting, kept to put back for other series
        data["default"] = {k: addon.getSetting(k) for k in KEYS}
        util.save_json(FILE, data)
    wanted = {k: ("true" if choice else "false") for k in KEYS} if choice is not None else data["default"]
    for name, value in wanted.items():
        if addon.getSetting(name) != value:
            addon.setSetting(name, value)


def toggle(show):
    if not available():
        util.notify(T("Installeer eerst TheIntroDB (Lucent-instellingen › Intro overslaan)", "Install TheIntroDB first (Lucent settings › Skip intro)"))
        return
    data = util.load_json(FILE, {})
    series = data.setdefault("series", {})
    now = not series.get(str(show), False)
    series[str(show)] = now
    util.save_json(FILE, data)
    util.notify(T("Intro's van deze serie worden vanzelf overgeslagen", "Intros of this series are skipped by themselves") if now
                else T("Intro's van deze serie niet meer vanzelf overslaan", "Intros of this series are no longer skipped by themselves"))

