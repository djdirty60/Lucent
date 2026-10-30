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


def streaming_test():
    log("stream: tab Streaming")
    xbmc.executebuiltin("Control.SetFocus(9000,2)")
    watch("stream", 60)
    shot("8-streaming")
    last = samples[-1]["rows"]
    log(f"stream: tab={lab('Container(9000).ListItem.Label')} 8201={last['8201']} 8102={last['8102']}")
    xbmc.executebuiltin("SetFocus(9100)")
    mon.waitForAbort(2)
    log(f"stream: focus={lab('System.CurrentControlID')} item={lab('Container(8201).ListItem.Label')} "
        f"logo={lab('Container(8201).ListItem.Art(clearlogo)')[-12:]} fanart={lab('Container(8201).ListItem.Art(fanart)')[-14:]}")
    shot("8b-streaming-focus")
    xbmc.executebuiltin("Action(Select)")
    mon.waitForAbort(8)
    pop = cond("Window.IsVisible(Lucent_Service.xml)")
    counts = [lab(f"Container({c}).NumItems") for c in range(801, 807)]
    log(f"stream: popup={pop} rows={counts} focus={lab('System.CurrentControlID')} title={lab('Container(801).ListItem.Label')} "
        f"logo={lab('Window(1).Property(svc.logo)')[-14:]}")
    shot("8c-popup")
    xbmc.executebuiltin("Action(Down)")
    mon.waitForAbort(1)
    xbmc.executebuiltin("Action(Down)")
    mon.waitForAbort(1)
    xbmc.executebuiltin("Action(Right)")
    mon.waitForAbort(2)
    log(f"stream: after down down right focus={lab('System.CurrentControlID')} item={lab('Container(803).ListItem.Label')} "
        f"pos={lab('Container(803).CurrentItem')}")
    shot("8d-popup-moved")
    xbmc.executebuiltin("Action(Select)")
    mon.waitForAbort(10)
    log(f"stream: after OK info={cond('Window.IsVisible(movieinformation)')} popup={cond('Window.IsVisible(Lucent_Service.xml)')} "
        f"window={lab('System.CurrentWindow')}")
    shot("8e-info")
    xbmc.executebuiltin("Action(Back)")
    mon.waitForAbort(4)
    log(f"stream: after Back info={cond('Window.IsVisible(movieinformation)')} popup={cond('Window.IsVisible(Lucent_Service.xml)')}")
    xbmc.executebuiltin("Action(Back)")
    mon.waitForAbort(3)
    log(f"stream: after 2nd Back popup={cond('Window.IsVisible(Lucent_Service.xml)')} window={lab('System.CurrentWindow')}")
    xbmc.executebuiltin("ActivateWindow(home)")
    mon.waitForAbort(3)


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
    log("subs: play 1")
    xbmc.executebuiltin("PlayMedia(/tmp/ci/test.mkv)")
    pwatch("subs-play1", 14)
    rows = list_rows()
    log(f"subs: rows {rows}")
    log(f"subs: playing={xbmc.Player().isPlayingVideo()} paused={cond('Player.Paused')} lang={lab('VideoPlayer.SubtitlesLanguage')}")
    shot("7-subs-auto")
    other = next((i for i, r in enumerate(rows) if r[1].startswith("otherstreams")), -1)
    if other >= 0:
        xbmc.executebuiltin(f"Control.SetFocus(500,{other})")
        mon.waitForAbort(1)
        xbmc.executebuiltin("Action(Select)")
        mon.waitForAbort(2)
        log(f"subs: other dialog open={cond('Window.IsVisible(selectdialog)')} item={lab('Container(3).ListItem.Label')}")
        shot("7b-other-dialog")
        xbmc.executebuiltin("Action(Select)")
        mon.waitForAbort(2)
    log(f"subs: after other lang={lab('VideoPlayer.SubtitlesLanguage')} list={cond('Window.IsVisible(Lucent_Subtitles.xml)')}")
    log("subs: OSD")
    xbmc.executebuiltin("ActivateWindow(videoosd)")
    mon.waitForAbort(2)
    log(f"subs: osd search visible={cond('Control.IsVisible(118)')} focus={lab('System.CurrentControlID')}")
    # the progress bar: up from the buttons, then right / left must move the film
    xbmc.executebuiltin("Action(Up)")
    mon.waitForAbort(1)
    for key in ("Right", "Right", "Left", "Left", "Left"):
        before = xbmc.Player().getTime()
        xbmc.executebuiltin(f"Action({key})")
        mon.waitForAbort(4)
        after = xbmc.Player().getTime()
        log(f"seek: {key}: {before:.1f} -> {after:.1f} = {after - before - 4:+.1f} s (besides 4 s playing) paused={cond('Player.Paused')} focus={lab('System.CurrentControlID')}")
    shot("7c-seek")
    xbmc.executebuiltin("Action(Down)")
    mon.waitForAbort(1)
    log(f"seek: focus after Down={lab('System.CurrentControlID')}")
    xbmc.executebuiltin("Control.SetFocus(111)")
    mon.waitForAbort(1)
    xbmc.executebuiltin("Action(Select)")
    pwatch("subs-osd", 4)
    log(f"subs: list from OSD={cond('Window.IsVisible(Lucent_Subtitles.xml)')} rows={list_rows()[:4]}")
    xbmc.executebuiltin("Control.SetFocus(500,1)")
    mon.waitForAbort(1)
    xbmc.executebuiltin("Action(Right)")
    mon.waitForAbort(1)
    log(f"subs: Right from list -> focus={lab('System.CurrentControlID')}")
    shot("7d-osd-list")
    xbmc.executebuiltin("PlayerControl(Stop)")
    pwatch("subs-stopped", 5)
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
    streaming_test()
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
