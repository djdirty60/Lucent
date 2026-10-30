"""Drives the Lucent Home screen in a real Kodi and writes what every row shows over time."""
import json
import os
import time

import xbmc
import xbmcgui

OUT = "/tmp/ci/out"
TAG = open("/tmp/ci/tag").read().strip() if os.path.exists("/tmp/ci/tag") else "run"
mon = xbmc.Monitor()
HOME = xbmcgui.Window(10000)
T0 = time.time()
samples, events = [], []


def log(t):
    xbmc.log(f"[cidriver] {t}", xbmc.LOGINFO)
    events.append([round(time.time() - T0, 1), t])


def cond(c):
    return xbmc.getCondVisibility(c)


def lab(x):
    return xbmc.getInfoLabel(x)


def snap(phase):
    rows = {}
    for n in range(1, 11):
        for base, marker in ((8100, 9900), (8200, 9910)):
            cid = base + n
            rows[str(cid)] = [lab(f"Container({cid}).NumItems"), cond(f"Control.IsVisible({marker + n})"),
                              cond(f"Container({cid}).IsUpdating")]
    samples.append({"t": round(time.time() - T0, 1), "phase": phase, "tab": lab("Container(9000).ListItem.Label"),
                    "window": lab("System.CurrentWindow"), "dialog": cond("System.HasVisibleModalDialog"),
                    "refresh": HOME.getProperty("lucent.rowsrefresh"), "ok": [HOME.getProperty(f"lucent.rowok.{n}") for n in range(1, 11)],
                    "wr": [HOME.getProperty(f"lucent.wr.{n}") for n in range(1, 11)], "rows": rows})


def shot(name):
    os.makedirs(OUT, exist_ok=True)
    xbmc.executebuiltin(f"TakeScreenshot({OUT}/{TAG}-{name}.png,sync)")
    mon.waitForAbort(2)


def watch(phase, seconds, step=1.0):
    end = time.time() + seconds
    while time.time() < end and not mon.abortRequested():
        if cond("System.HasVisibleModalDialog"):
            xbmc.executebuiltin("Dialog.Close(all,true)")
        snap(phase)
        mon.waitForAbort(step)


def psnap(phase):
    try:
        pos = round(xbmc.Player().getTime(), 1) if xbmc.Player().isPlayingVideo() else -1
    except RuntimeError:
        pos = -1
    samples.append({"t": round(time.time() - T0, 1), "phase": phase, "pos": pos, "playing": xbmc.Player().isPlayingVideo(),
                    "paused": cond("Player.Paused"), "list": cond("Window.IsVisible(Lucent_Subtitles.xml)"),
                    "mark": HOME.getProperty("lucent.subs.open"), "rows": {}, "tab": "", "window": lab("System.CurrentWindow"),
                    "dialog": False, "refresh": "", "wr": []})


def pwatch(phase, seconds):
    end = time.time() + seconds
    while time.time() < end and not mon.abortRequested():
        psnap(phase)
        mon.waitForAbort(0.5)


def list_rows():
    n = int(lab("Container(500).NumItems") or 0)
    return [[lab(f"Container(500).ListItemAbsolute({i}).Label"), lab(f"Container(500).ListItemAbsolute({i}).Property(path)")[:40]]
            for i in range(min(n, 8))]


def subs_test():
    """The subtitle list: opens by itself after about 5 s without pausing; shows On/Off and the film's own subtitle
    streams above the found ones; choosing a stream switches to it; closes when the video stops; the OSD subtitle
    button opens it; the search button is gone."""
    log("subs: play 1")
    xbmc.executebuiltin("PlayMedia(/tmp/ci/test.mkv)")
    pwatch("subs-play1", 14)
    log(f"subs: rows {list_rows()} focus={lab('Container(500).CurrentItem')}")
    log(f"subs: before choose lang={lab('VideoPlayer.SubtitlesLanguage')} on={cond('VideoPlayer.SubtitlesEnabled')}")
    shot("7-subs-auto")
    rows = list_rows()
    nl = next((i for i, r in enumerate(rows) if r[1].startswith("stream:") and "Dutch" in r[0] or "Neder" in r[0]), -1)
    if nl >= 0:
        xbmc.executebuiltin(f"Control.SetFocus(500,{nl})")
        mon.waitForAbort(1)
        xbmc.executebuiltin("Action(Select)")
    pwatch("subs-chosen", 4)
    log(f"subs: after choose lang={lab('VideoPlayer.SubtitlesLanguage')} on={cond('VideoPlayer.SubtitlesEnabled')} "
        f"list={cond('Window.IsVisible(Lucent_Subtitles.xml)')}")
    shot("7b-subs-chosen")
    log("subs: OSD button")
    xbmc.executebuiltin("ActivateWindow(videoosd)")
    mon.waitForAbort(2)
    log(f"subs: osd search button visible={cond('Control.IsVisible(118)')} subtitle button visible={cond('Control.IsVisible(111)')}")
    shot("7c-osd")
    xbmc.executebuiltin("Control.SetFocus(111)")
    mon.waitForAbort(1)
    xbmc.executebuiltin("Action(Select)")
    pwatch("subs-osd", 5)
    log(f"subs: list from OSD={cond('Window.IsVisible(Lucent_Subtitles.xml)')} paused={cond('Player.Paused')} rows={list_rows()[:3]}")
    shot("7d-osd-list")
    xbmc.executebuiltin("Control.SetFocus(500,0)")
    mon.waitForAbort(1)
    before = cond("VideoPlayer.SubtitlesEnabled")
    xbmc.executebuiltin("Action(Select)")
    pwatch("subs-toggle", 3)
    log(f"subs: toggle {before} -> {cond('VideoPlayer.SubtitlesEnabled')} list still open={cond('Window.IsVisible(Lucent_Subtitles.xml)')} row0={list_rows()[:1]}")
    log("subs: stop")
    xbmc.executebuiltin("PlayerControl(Stop)")
    pwatch("subs-stopped", 6)
    log(f"subs: after stop list={cond('Window.IsVisible(Lucent_Subtitles.xml)')}")


def main():
    for _ in range(180):
        if cond("Window.IsActive(home)") and HOME.getProperty("nuvio.started"):
            break
        mon.waitForAbort(1)
    log(f"home ready skin={lab('Skin.CurrentTheme')} {lab('System.AddonVersion(skin.lucent)')} "
        f"lib={lab('System.AddonVersion(script.lucent.library)')} helper={HOME.getProperty('lucent.helper.running')}")
    xbmc.executebuiltin("Dialog.Close(all,true)")
    xbmc.executebuiltin("Control.SetFocus(9000,0)")
    watch("home1", 50)
    shot("1-home")
    log("switch to Films")
    xbmc.executebuiltin("Control.SetFocus(9000,1)")
    watch("films1", 120)
    shot("2-films")
    log("back to Home")
    xbmc.executebuiltin("Control.SetFocus(9000,0)")
    watch("home2", 20)
    log("Films again")
    xbmc.executebuiltin("Control.SetFocus(9000,1)")
    watch("films2", 30)
    shot("3-films-again")
    xbmc.executebuiltin("SetFocus(9100)")
    watch("films2-rows", 6)
    shot("4-films-rows")
    for step in range(1, 6):                       # scroll down through the rows like a person with a remote
        xbmc.executebuiltin("Action(Down)")
        watch(f"down{step}", 6)
        log(f"down {step}: focus={xbmc.getInfoLabel('System.CurrentControlID')} label={xbmc.getInfoLabel('Container.ListItem.Label')}")
        shot(f"5-down{step}")
    watch("idle", 60)                               # nothing touched: the rows must stay put (no jumping)
    shot("6-idle")
    subs_test()
    os.makedirs(OUT, exist_ok=True)
    json.dump({"tag": TAG, "events": events, "samples": samples}, open(f"{OUT}/{TAG}.json", "w"))
    log("done")
    xbmc.executebuiltin("Quit")


try:
    main()
except Exception as error:  # noqa: BLE001
    log(f"driver error {error!r}")
    os.makedirs(OUT, exist_ok=True)
    json.dump({"tag": TAG, "events": events, "samples": samples, "error": repr(error)}, open(f"{OUT}/{TAG}.json", "w"))
    xbmc.executebuiltin("Quit")
