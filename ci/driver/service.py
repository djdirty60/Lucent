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


def nav_test():
    """Up / down between rows (a poster row on top), wrapping at the ends, and Back: first item, top row, menu."""
    fid = lambda: lab("System.CurrentControlID")  # noqa: E731
    xbmc.executebuiltin("SetFocus(9100)")
    mon.waitForAbort(1.5)
    out = [f"start={fid()} toprow={HOME.getProperty('lucent.toprow')}"]
    for key in ("Down", "Down", "Down", "Up", "Up", "Up"):
        xbmc.executebuiltin(f"Action({key})")
        mon.waitForAbort(1.2)
        out.append(f"{key}->{fid()}")
    log("nav: " + " ".join(out))
    xbmc.executebuiltin("Action(Down)")
    mon.waitForAbort(1.2)
    xbmc.executebuiltin("Action(Down)")
    mon.waitForAbort(1.2)
    for _ in range(3):
        xbmc.executebuiltin("Action(Right)")
        mon.waitForAbort(0.6)
    out = [f"at={fid()} item={lab('Container(' + fid() + ').CurrentItem')}"]
    for _ in range(3):
        xbmc.executebuiltin("Action(Back)")
        mon.waitForAbort(1.2)
        f = fid()
        out.append(f"Back->{f} item={lab('Container(' + f + ').CurrentItem')}")
    log("back: " + " ".join(out))
    xbmc.executebuiltin("Control.SetFocus(9000,0)")
    mon.waitForAbort(1)


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


def sidemenu_test():
    """Media window: Left opens the view menu, Back must close it and stay in the same folder."""
    fid = lambda: lab("System.CurrentControlID")  # noqa: E731
    xbmc.executebuiltin("ActivateWindow(Videos,plugin://plugin.video.fakeseren/?list=folder,return)")
    mon.waitForAbort(5)
    xbmc.executebuiltin("Container.Update(plugin://plugin.video.fakeseren/?list=fast&from=1)")
    mon.waitForAbort(5)
    path0 = lab("Container.FolderPath")
    log(f"side: window={lab('System.CurrentWindow')} path={path0[-30:]} focus={fid()} items={lab('Container.NumItems')}")
    for attempt in range(2):
        xbmc.executebuiltin("Action(Left)")
        mon.waitForAbort(1.5)
        inmenu = cond("ControlGroup(9050).HasFocus")
        log(f"side: {attempt} after Left focus={fid()} menu={inmenu}")
        if attempt == 0:
            shot("9a-sidemenu")
        xbmc.executebuiltin("Action(Back)")
        mon.waitForAbort(2.5)
        path1 = lab("Container.FolderPath")
        log(f"side: {attempt} after Back focus={fid()} menu={cond('ControlGroup(9050).HasFocus')} "
            f"samefolder={path1 == path0} path={path1[-30:]} window={lab('System.CurrentWindow')}")
    shot("9b-after-back")
    for view in (50, 56):
        xbmc.executebuiltin(f"Container.SetViewMode({view})")
        mon.waitForAbort(2)
        xbmc.executebuiltin(f"SetFocus({view})")
        mon.waitForAbort(1)
        xbmc.executebuiltin("Action(Left)")
        mon.waitForAbort(1.5)
        left = fid()
        xbmc.executebuiltin("Action(Right)")
        mon.waitForAbort(1.5)
        log(f"side: view {view} visible={cond(f'Control.IsVisible({view})')} Left->{left} Right->{fid()} "
            f"samefolder={lab('Container.FolderPath') == path0}")
    xbmc.executebuiltin("ActivateWindow(home)")
    mon.waitForAbort(3)


def power_test():
    """Power dialog: own buttons on top, hidden Kodi buttons gone, a click runs the action and closes the dialog."""
    vis = lambda c: cond(f"Control.IsVisible({c})")  # noqa: E731
    xbmc.executebuiltin("ActivateWindow(ShutdownMenu)")
    mon.waitForAbort(2)
    log(f"power: standard quit={vis(9101)} settings={vis(9108)} c1={vis(9121)} focus={lab('System.CurrentControlID')}")
    xbmc.executebuiltin("Dialog.Close(all,true)")
    mon.waitForAbort(1)
    # the editor opens (it imports menu.py) and shows its list
    xbmc.executebuiltin("RunScript(special://skin/scripts/powermenu.py)")
    mon.waitForAbort(4)
    labels = [lab(f"Container(3).ListItemAbsolute({i}).Label") for i in range(int(lab("Container(3).NumItems") or 0))]
    log(f"power: editor open={cond('Window.IsVisible(selectdialog)')} items={labels}")
    shot("10a-editor")
    xbmc.executebuiltin("Dialog.Close(all,true)")
    mon.waitForAbort(2)
    xbmc.executebuiltin('Skin.SetString(lucent.pm.c1.label,"File Manager")')
    xbmc.executebuiltin('Skin.SetString(lucent.pm.c1.action,"ActivateWindow(FileManager)")')
    xbmc.executebuiltin('Skin.SetString(lucent.pm.c2.label,"Test, with comma")')
    xbmc.executebuiltin('Skin.SetString(lucent.pm.c2.action,"SetProperty(cipm,clicked,home)")')
    xbmc.executebuiltin("Skin.SetBool(lucent.pm.hide.quit)")
    xbmc.executebuiltin("Skin.SetBool(lucent.pm.hide.settings)")
    mon.waitForAbort(1)
    xbmc.executebuiltin("ActivateWindow(ShutdownMenu)")
    mon.waitForAbort(2)
    log(f"power: custom quit={vis(9101)} settings={vis(9108)} c1={vis(9121)}:{lab('Control.GetLabel(9121)')} "
        f"c2={vis(9122)}:{lab('Control.GetLabel(9122)')} c3={vis(9123)} focus={lab('System.CurrentControlID')}")
    shot("10b-power-custom")
    xbmc.executebuiltin("SetFocus(9122)")
    mon.waitForAbort(1)
    xbmc.executebuiltin("Action(Select)")
    mon.waitForAbort(2)
    log(f"power: c2 click prop={HOME.getProperty('cipm')} dialog={cond('Window.IsVisible(ShutdownMenu)')}")
    xbmc.executebuiltin("ActivateWindow(ShutdownMenu)")
    mon.waitForAbort(2)
    xbmc.executebuiltin("SetFocus(9121)")
    mon.waitForAbort(1)
    xbmc.executebuiltin("Action(Select)")
    mon.waitForAbort(3)
    log(f"power: c1 click filemanager={cond('Window.IsActive(filemanager)')} dialog={cond('Window.IsVisible(ShutdownMenu)')}")
    shot("10c-filemanager")
    xbmc.executebuiltin("ActivateWindow(home)")
    mon.waitForAbort(2)
    xbmc.executebuiltin("RunScript(special://skin/scripts/powermenu.py,reset)")
    mon.waitForAbort(3)
    log(f"power: after reset c1={lab('Skin.String(lucent.pm.c1.action)')!r} hidequit={cond('Skin.HasSetting(lucent.pm.hide.quit)')}")


def sport_test():
    """Sport tab without TV channels: the 'no channels' text must not sit on top of the buttons."""
    xbmc.executebuiltin("RunScript(special://skin/scripts/sport.py)")
    for _ in range(60):
        mon.waitForAbort(1)
        if cond("Window.IsVisible(Lucent_Sport.xml)") and int(lab("Container(200).NumItems") or 0) > 0:
            break
    mon.waitForAbort(6)
    for n in range(4):
        item = lab("Container(200).ListItem.Label") or lab("Container(200).ListItem.Property(hname)")
        log(f"sport: item {n} n={lab('Container(200).NumItems')} {item} nochan={lab('Window(1).Property(sport.t.nochan)') or lab('Window.Property(sport.t.nochan)')!r} "
            f"remind={lab('Container(200).ListItem.Property(remindtext)')!r} rec={lab('Container(200).ListItem.Property(rectext)')!r} "
            f"ch1={lab('Container(200).ListItem.Property(ch1name)')!r} b321={cond('Control.IsVisible(321)')}")
        shot(f"11-sport-{n}")
        xbmc.executebuiltin("Action(Down)")
        mon.waitForAbort(2)
    xbmc.executebuiltin("SetFocus(9300)")
    mon.waitForAbort(2)
    log(f"sport: focus 9300 -> {lab('System.CurrentControlID')}")
    shot("11-sport-focus")
    xbmc.executebuiltin("Dialog.Close(all,true)")
    xbmc.executebuiltin("ActivateWindow(home)")
    mon.waitForAbort(2)


def row(cid, n=6):
    return [f"{lab(f'Container({cid}).ListItemAbsolute({i}).Label')}/{lab(f'Container({cid}).ListItemAbsolute({i}).Year')}/"
            f"{lab(f'Container({cid}).ListItemAbsolute({i}).Rating')}" for i in range(n)]


def sort_test():
    """Home row 1 (8101, poster): the widget's sort option re-orders the row."""
    xbmc.executebuiltin("Control.SetFocus(9000,0)")
    mon.waitForAbort(3)
    log(f"sort: default n={lab('Container(8101).NumItems')} {row(8101)}")
    for key in ("title", "year", "rating", "dateadded", ""):
        for name in ("nuvio.home.w1.sort", "nuvio.tab1.w1.sort"):
            xbmc.executebuiltin(f"Skin.SetString({name},{key})" if key else f"Skin.Reset({name})")
        mon.waitForAbort(6)
        log(f"sort: {key or 'source'} n={lab('Container(8101).NumItems')} {row(8101)}")
        shot(f"12-sort-{key or 'source'}")
    # the menu editor stores the choice (load, change, save through menu.py itself)
    import sys
    sys.path.insert(0, xbmcvfs_translate("special://skin/scripts"))
    try:
        import menu
        m = menu.Menu()
        m.tabs[0]["widgets"][0]["sort"] = "title"
        m.save()
        mon.waitForAbort(4)
        log(f"sort: via menu.py tab={lab('Skin.String(nuvio.tab1.w1.sort)')!r} home={lab('Skin.String(nuvio.home.w1.sort)')!r} "
            f"names={[n for _k, n in menu.SORTS()]} row={row(8101, 4)}")
        m = menu.Menu()
        log(f"sort: reloaded menu.py sort={m.tabs[0]['widgets'][0].get('sort')!r} label={m.tabs[0]['widgets'][0]['label']!r}")
    except Exception as error:  # noqa: BLE001
        log(f"sort: menu.py error {error!r}")


def xbmcvfs_translate(path):
    import xbmcvfs
    return xbmcvfs.translatePath(path)


def osd_test():
    """Player menu: OK on play/pause must keep the focus on that button."""
    xbmc.executebuiltin("Skin.Reset(nuvio.autosubs)")      # no subtitle list popping up during this test
    mon.waitForAbort(1)
    xbmc.executebuiltin("PlayMedia(/tmp/ci/test.mkv)")
    for _ in range(30):
        mon.waitForAbort(1)
        if xbmc.Player().isPlayingVideo():
            break
    mon.waitForAbort(4)
    xbmc.executebuiltin("Dialog.Close(all,true)")
    mon.waitForAbort(1)
    xbmc.executebuiltin("ActivateWindow(videoosd)")
    mon.waitForAbort(2)
    out = [f"open focus={lab('System.CurrentControlID')} paused={cond('Player.Paused')}"]
    for n in range(4):
        xbmc.executebuiltin("Action(Select)")
        mon.waitForAbort(2)
        out.append(f"OK{n + 1}: focus={lab('System.CurrentControlID')} paused={cond('Player.Paused')} "
                   f"label={lab('Control.GetLabel(103)')!r} tex={'play' if cond('Player.Paused') else 'pause'}")
        if n == 0:
            shot("13-osd-paused")
    for key in ("Left", "Right", "Right", "Left", "Up", "Down"):
        xbmc.executebuiltin(f"Action({key})")
        mon.waitForAbort(1)
        out.append(f"{key}->{lab('System.CurrentControlID')}")
    log("osd: " + " | ".join(out))
    shot("13-osd-after")
    xbmc.executebuiltin("PlayerControl(Stop)")
    mon.waitForAbort(3)


def key(name, hold=0.0):
    import subprocess
    try:
        if hold:
            subprocess.run(["xdotool", "keydown", name], timeout=5)
            time.sleep(hold)
            subprocess.run(["xdotool", "keyup", name], timeout=5)
        else:
            subprocess.run(["xdotool", "key", name], timeout=5)
    except Exception as error:  # noqa: BLE001
        log(f"xdotool error {error!r}")


def state():
    return (f"ctx={cond('Window.IsVisible(contextmenu)')} info={cond('Window.IsVisible(movieinformation)')} "
            f"window={lab('System.CurrentWindow')} item={lab('ListItem.Label')!r} dbtype={lab('ListItem.DBType')}")


def ctx_test():
    """'OK on a film opens its page' on: a short OK opens the page, holding OK still opens the context menu."""
    xbmc.executebuiltin("Skin.SetBool(nuvio.ok.movie.page)")
    mon.waitForAbort(1)
    xbmc.executebuiltin("RunScript(special://skin/scripts/keymap.py)")
    mon.waitForAbort(3)
    km = xbmcvfs_translate("special://profile/keymaps/lucent-ok-page.xml")
    log(f"ctx: keymap exists={os.path.exists(km)} longpress={'longpress' in open(km).read() if os.path.exists(km) else None}")
    xbmc.executebuiltin("ActivateWindow(Videos,plugin://plugin.video.fakeseren/?list=fast,return)")
    for _ in range(20):                             # wait for the list, then step off ".." onto a film
        mon.waitForAbort(1)
        if int(lab("Container.NumItems") or 0) > 0:
            break
    mon.waitForAbort(2)
    for _ in range(4):
        if lab("ListItem.DBType") == "movie":
            break
        xbmc.executebuiltin("Action(Down)")
        mon.waitForAbort(1.5)
    log(f"ctx: start {state()}")
    for n in range(3):
        key("Return", hold=1.5)
        mon.waitForAbort(2)
        log(f"ctx: hold OK #{n + 1}: {state()}")
        if n == 0:
            shot("14-ctx-hold")
        xbmc.executebuiltin("Dialog.Close(all,true)")
        mon.waitForAbort(2)
    key("Return")
    mon.waitForAbort(3)
    log(f"ctx: short OK: {state()}")
    shot("14-ctx-short")
    xbmc.executebuiltin("Dialog.Close(all,true)")
    mon.waitForAbort(2)
    key("c")
    mon.waitForAbort(2)
    log(f"ctx: C key: {state()}")
    xbmc.executebuiltin("Dialog.Close(all,true)")
    xbmc.executebuiltin("ActivateWindow(home)")
    mon.waitForAbort(2)


def main():
    for _ in range(180):
        if cond("Window.IsActive(home)") and HOME.getProperty("nuvio.started"):
            break
        mon.waitForAbort(1)
    log(f"home ready skin={lab('Skin.CurrentTheme')} {lab('System.AddonVersion(skin.lucent)')} "
        f"lib={lab('System.AddonVersion(script.lucent.library)')} helper={HOME.getProperty('lucent.helper.running')}")
    xbmc.executebuiltin("Dialog.Close(all,true)")
    xbmc.executebuiltin("Control.SetFocus(9000,0)")
    watch("home1", 40)
    shot("1-home")
    ctx_test()
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
