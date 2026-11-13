"""Drives the Lucent Home screen in a real Kodi and writes what every row shows over time."""
import json
import os
import time

import xbmc
import xbmcgui
import xbmcvfs

OUT = "/tmp/ci/out"
TAG = open("/tmp/ci/tag").read().strip() if os.path.exists("/tmp/ci/tag") else "run"
mon = xbmc.Monitor()
HOME = xbmcgui.Window(10000)
T0 = time.time()
samples, events = [], []


HOME_READY = {}


def log(t):
    xbmc.log(f"[cidriver] {t}", xbmc.LOGINFO)
    events.append([round(time.time() - T0, 1), t])
    try:                                              # save as we go: a run cut off by the time limit still has its results
        os.makedirs(OUT, exist_ok=True)
        with open(f"{OUT}/{TAG}.json", "w") as fh:
            json.dump({"tag": TAG, "events": events, "samples": samples, "partial": True}, fh)
    except Exception:  # noqa: BLE001
        pass


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
    cid = 6 if int(lab("Container(6).NumItems") or 0) else 3
    labels = [lab(f"Container({cid}).ListItemAbsolute({i}).Label") for i in range(int(lab(f"Container({cid}).NumItems") or 0))]
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


def series_test():
    """Streaming: the service row has only the wanted services; a series page's Play opens its seasons in Seren."""
    res = json.loads(xbmc.executeJSONRPC(json.dumps({"jsonrpc": "2.0", "id": 1, "method": "Files.GetDirectory",
                                                    "params": {"directory": "plugin://script.lucent.library/?action=providers", "media": "files"}})))
    names = [f.get("label") for f in (res.get("result") or {}).get("files") or []]
    log(f"series: providers ({len(names)}) {names}")
    for kind, tmdb_id in (("movie", "1001"), ("tv", "1002")):
        HOME.setProperty("nuvio.open.tmdb", tmdb_id)
        HOME.setProperty("nuvio.open.type", kind)
        HOME.setProperty("nuvio.open.trakt", "4242")
        xbmc.executebuiltin("RunScript(special://skin/scripts/info.py,open,path)")
        for _ in range(20):
            mon.waitForAbort(1)
            if cond("Window.IsVisible(movieinformation)"):
                break
        mon.waitForAbort(2)
        log(f"series: {kind} page={cond('Window.IsVisible(movieinformation)')} dbtype={lab('ListItem.DBType')} "
            f"folder={cond('ListItem.IsFolder')} path={lab('ListItem.FileNameAndPath')[:90]!r}")
        if kind == "tv":
            shot("15-series-page")
            xbmc.executebuiltin("SetFocus(8)")
            mon.waitForAbort(1)
            xbmc.executebuiltin("Action(Select)")
            for _ in range(15):
                mon.waitForAbort(1)
                if cond("Window.IsActive(videos)") and int(lab("Container.NumItems") or 0) > 0:
                    break
            mon.waitForAbort(2)
            log(f"series: after Play window={lab('System.CurrentWindow')} page={cond('Window.IsVisible(movieinformation)')} "
                f"path={lab('Container.FolderPath')[:90]!r} items={lab('Container.NumItems')}")
            shot("15-series-after-play")
        xbmc.executebuiltin("Dialog.Close(all,true)")
        xbmc.executebuiltin("ActivateWindow(home)")
        mon.waitForAbort(3)


def art_of(directory):
    res = json.loads(xbmc.executeJSONRPC(json.dumps({"jsonrpc": "2.0", "id": 1, "method": "Files.GetDirectory",
                                                    "params": {"directory": directory, "media": "files", "properties": ["art"]}})))
    return [(f.get("label"), (f.get("art") or {}).get("thumb", "")[-28:]) for f in (res.get("result") or {}).get("files") or []]


def custom_test():
    """Own title picture / background / hidden title per widget, own tab icon, own streaming services list."""
    star = "special://skin/media/icons/star.png"
    bgimg = "special://home/addons/plugin.video.fakeseren/icon.png"
    xbmc.executebuiltin("Control.SetFocus(9000,0)")
    mon.waitForAbort(2)
    xbmc.executebuiltin("SetFocus(9100)")
    mon.waitForAbort(2)
    log(f"custom: before fanart={lab('$VAR[LucentHomeFanart]')[-30:]!r} w1label={lab('$VAR[NuvioW1Label]')!r}")
    shot("16-before")
    sys.path.insert(0, xbmcvfs_translate("special://skin/scripts"))
    try:
        import menu
        m = menu.Menu()
        wd = m.tabs[0]["widgets"][0]
        wd["timg"], wd["bg"] = star, "special://skin/media/icons/tv.png"
        wd2 = m.tabs[0]["widgets"][1]
        wd2["notitle"] = "1"
        m.tabs[0]["icon"] = bgimg
        m.save()
        mon.waitForAbort(4)
        log(f"custom: saved timg={lab('Skin.String(nuvio.home.w1.timg)')[-20:]!r} tab={lab('Skin.String(nuvio.tab1.w1.timg)')[-20:]!r} "
            f"bg={lab('Skin.String(nuvio.home.w1.bg)')[-20:]!r} notitle2={lab('Skin.String(nuvio.home.w2.notitle)')!r} icon={lab('Skin.String(nuvio.tab1.icon)')[-20:]!r}")
        log(f"custom: vars timg={lab('$VAR[NuvioW1TitleImg]')[-20:]!r} bg={lab('$VAR[NuvioW1Bg]')[-20:]!r} "
            f"fanart={lab('$VAR[LucentHomeFanart]')[-30:]!r} row={HOME.getProperty('nuvio.row')}")
        shot("16-after")
        m = menu.Menu()
        log(f"custom: reloaded {m.tabs[0]['widgets'][0].get('timg', '')[-20:]!r} {m.tabs[0]['widgets'][1].get('notitle')!r}")
    except Exception as error:  # noqa: BLE001
        log(f"custom: menu error {error!r}")
    # streaming services: the standard list, then your own list with your own picture
    lib = "plugin://script.lucent.library/?action=providers"
    log(f"custom: services standard {[a for a, _b in art_of(lib)]}")
    cat = art_of("plugin://script.lucent.library/?action=provcatalog")
    log(f"custom: catalog ({len(cat)}) {[a for a, _b in cat][:20]}")
    d = xbmcvfs_translate("special://profile/addon_data/script.lucent.library/tmdb/")
    os.makedirs(d, exist_ok=True)
    json.dump({"items": [{"id": 1899, "name": "HBO Max", "logo": "/h.png", "region": "US"},
                         {"id": 8, "name": "Netflix", "logo": "/n.png", "region": "US", "image": bgimg},
                         {"id": 900, "name": "Fubo", "logo": "/f.png", "region": "US"}]}, open(d + "services.json", "w"))
    log(f"custom: services own {art_of(lib)}")
    xbmc.executebuiltin("RunScript(special://skin/scripts/streamedit.py,reset)")
    mon.waitForAbort(3)
    log(f"custom: services after reset {[a for a, _b in art_of(lib)]} file={os.path.exists(d + 'services.json')}")
    xbmc.executebuiltin("RunScript(special://skin/scripts/streamedit.py)")
    mon.waitForAbort(4)
    cid = 6 if int(lab("Container(6).NumItems") or 0) else 3
    labels = [lab(f"Container({cid}).ListItemAbsolute({i}).Label") for i in range(int(lab(f"Container({cid}).NumItems") or 0))]
    log(f"custom: editor open={cond('Window.IsVisible(selectdialog)')} items={labels}")
    shot("16-editor")
    xbmc.executebuiltin("Dialog.Close(all,true)")
    mon.waitForAbort(2)


def popup_test():
    """Streaming pop-up: OK on a series opens its page; Play there opens the seasons and the pop-up goes away."""
    xbmc.executebuiltin("RunScript(special://skin/scripts/service.py,8,Netflix,)")
    for _ in range(20):
        mon.waitForAbort(1)
        if cond("Window.IsVisible(Lucent_Service.xml)") and int(lab("Container(802).NumItems") or 0) > 0:
            break
    mon.waitForAbort(2)
    xbmc.executebuiltin("SetFocus(802)")
    mon.waitForAbort(1.5)
    log(f"popup: open={cond('Window.IsVisible(Lucent_Service.xml)')} focus={lab('System.CurrentControlID')} "
        f"item={lab('Container(802).ListItem.Label')!r} dbtype={lab('Container(802).ListItem.DBType')}")
    xbmc.executebuiltin("Action(Select)")
    for _ in range(20):
        mon.waitForAbort(1)
        if cond("Window.IsVisible(movieinformation)"):
            break
    mon.waitForAbort(2)
    log(f"popup: page={cond('Window.IsVisible(movieinformation)')} dbtype={lab('ListItem.DBType')} path={lab('ListItem.FileNameAndPath')[:70]!r}")
    xbmc.executebuiltin("SetFocus(8)")
    mon.waitForAbort(1)
    xbmc.executebuiltin("Action(Select)")
    for _ in range(15):
        mon.waitForAbort(1)
        if not cond("Window.IsVisible(Lucent_Service.xml)") and cond("Window.IsActive(videos)"):
            break
    mon.waitForAbort(2)
    log(f"popup: after Play popup={cond('Window.IsVisible(Lucent_Service.xml)')} window={lab('System.CurrentWindow')} "
        f"videos={cond('Window.IsActive(videos)')} path={lab('Container.FolderPath')[:70]!r} items={lab('Container.NumItems')}")
    shot("17-popup-play")
    xbmc.executebuiltin("Dialog.Close(all,true)")
    xbmc.executebuiltin("ActivateWindow(home)")
    mon.waitForAbort(3)
    # Back from a page keeps the pop-up (only Play closes it)
    xbmc.executebuiltin("RunScript(special://skin/scripts/service.py,8,Netflix,)")
    mon.waitForAbort(6)
    xbmc.executebuiltin("SetFocus(802)")
    mon.waitForAbort(1.5)
    xbmc.executebuiltin("Action(Select)")
    for _ in range(20):
        mon.waitForAbort(1)
        if cond("Window.IsVisible(movieinformation)"):
            break
    mon.waitForAbort(2)
    xbmc.executebuiltin("Action(Back)")
    mon.waitForAbort(4)
    log(f"popup: after Back page={cond('Window.IsVisible(movieinformation)')} popup={cond('Window.IsVisible(Lucent_Service.xml)')}")
    xbmc.executebuiltin("Dialog.Close(all,true)")
    xbmc.executebuiltin("ActivateWindow(home)")
    mon.waitForAbort(2)


def direct_test():
    """A series in the streaming pop-up (and in a TMDb row on Home) opens straight on its seasons; a film on its page."""
    for row, label in ((802, "series"), (801, "film")):
        xbmc.executebuiltin("RunScript(special://skin/scripts/service.py,8,Netflix,)")
        for _ in range(20):
            mon.waitForAbort(1)
            if cond("Window.IsVisible(Lucent_Service.xml)") and int(lab(f"Container({row}).NumItems") or 0) > 0:
                break
        mon.waitForAbort(2)
        xbmc.executebuiltin(f"SetFocus({row})")
        mon.waitForAbort(1.5)
        item = lab(f"Container({row}).ListItem.Label")
        xbmc.executebuiltin("Action(Select)")
        for _ in range(15):
            mon.waitForAbort(1)
            if cond("Window.IsActive(videos) | Window.IsVisible(movieinformation)") and not cond("Window.IsVisible(Lucent_Service.xml)"):
                break
            if cond("Window.IsVisible(movieinformation)"):
                break
        mon.waitForAbort(2)
        log(f"direct: {label} {item!r}: popup={cond('Window.IsVisible(Lucent_Service.xml)')} page={cond('Window.IsVisible(movieinformation)')} "
            f"videos={cond('Window.IsActive(videos)')} path={lab('Container.FolderPath')[:60]!r} items={lab('Container.NumItems')}")
        shot(f"18-direct-{label}")
        xbmc.executebuiltin("Dialog.Close(all,true)")
        xbmc.executebuiltin("ActivateWindow(home)")
        mon.waitForAbort(3)


def logo_test():
    """The streaming services row: each tile shows the service's transparent logo (from the logo packs)."""
    res = json.loads(xbmc.executeJSONRPC(json.dumps({"jsonrpc": "2.0", "id": 1, "method": "Files.GetDirectory",
                     "params": {"directory": "plugin://script.lucent.library/?action=providers", "media": "files", "properties": ["art"]}})))
    log(f"logos: {[(f.get('label'), (f.get('art') or {}).get('clearlogo', '')[-28:]) for f in (res.get('result') or {}).get('files') or []]}")
    xbmc.executebuiltin("Control.SetFocus(9000,2)")
    for _ in range(40):
        mon.waitForAbort(1)
        if int(lab("Container(8201).NumItems") or 0) > 0:
            break
    mon.waitForAbort(8)
    xbmc.executebuiltin("SetFocus(9100)")
    mon.waitForAbort(3)
    log(f"logos: tab={lab('Container(9000).ListItem.Label')} focus={lab('System.CurrentControlID')} n={lab('Container(8201).NumItems')} "
        f"svclogo={lab('Container(8201).ListItem.Property(svclogo)')[-28:]!r} hover={lab('Container(8201).ListItem.Property(svchover)')[-28:]!r} "
        f"labels.hide={cond('Skin.HasSetting(nuvio.posterlabels.hide)')} last={lab('Container(8201).ListItemAbsolute(11).Label')!r}")
    shot("19-logos")
    xbmc.executebuiltin("Action(Right)")
    mon.waitForAbort(1)
    xbmc.executebuiltin("Action(Right)")
    mon.waitForAbort(2)
    shot("19-logos-right")
    mon.waitForAbort(1)
    shot("19-logos-right2")
    xbmc.executebuiltin("Control.SetFocus(9000,0)")
    mon.waitForAbort(2)


def poster_test():
    """Poster rows: a picture with and without the names under the posters (preview)."""
    xbmc.executebuiltin("Control.SetFocus(9000,1)")
    mon.waitForAbort(25)
    xbmc.executebuiltin("SetFocus(9100)")
    mon.waitForAbort(3)
    log(f"poster: focus={lab('System.CurrentControlID')} n={lab('Container(8101).NumItems')} {lab('Container(8102).NumItems')}")
    shot("20-posters-labels")
    xbmc.executebuiltin("Skin.SetBool(nuvio.posterlabels.hide)")
    mon.waitForAbort(3)
    shot("20-posters-nolabels")
    xbmc.executebuiltin("Action(Down)")
    mon.waitForAbort(3)
    shot("20-posters-nolabels-down")
    xbmc.executebuiltin("Skin.Reset(nuvio.posterlabels.hide)")


def sel_items():
    for cid in (6, 3):
        n = int(lab(f"Container({cid}).NumItems") or 0)
        if n and cond(f"Control.IsVisible({cid})"):
            return cid, [lab(f"Container({cid}).ListItemAbsolute({i}).Label") + "|" + lab(f"Container({cid}).ListItemAbsolute({i}).Label2") for i in range(n)]
    return 0, []


def pick(index):
    cid, _items = sel_items()
    xbmc.executebuiltin(f"SetFocus({cid},{index},absolute)")
    mon.waitForAbort(1)
    xbmc.executebuiltin("Action(Select)")
    mon.waitForAbort(2)


def edit_test():
    """Streaming services editor: switch a service off, move one to another place (run as menu.py runs it)."""
    import threading
    sys.path.insert(0, xbmcvfs_translate("special://skin/scripts"))
    lib = "plugin://script.lucent.library/?action=providers"
    import streamedit
    th = threading.Thread(target=streamedit.editor)
    th.start()
    mon.waitForAbort(4)
    cid, items = sel_items()
    log(f"edit: open={cond('Window.IsVisible(selectdialog)')} {items[:4]} ... {len(items)}")
    pick(1)                                            # Disney
    cid, opts = sel_items()
    log(f"edit: options {opts}")
    pick(0)                                            # hide / switch off
    xbmc.executebuiltin("Action(Back)")
    mon.waitForAbort(2)
    cid, items = sel_items()
    log(f"edit: after off {items[:3]}")
    pick(0)                                            # Netflix
    pick(1)                                            # place
    cid, places = sel_items()
    log(f"edit: places {places[:4]}")
    pick(3)                                            # to place 4
    xbmc.executebuiltin("Action(Back)")
    mon.waitForAbort(2)
    cid, items = sel_items()
    log(f"edit: after move {items[:5]}")
    shot("21-editor")
    xbmc.executebuiltin("Action(Back)")
    mon.waitForAbort(2)
    th.join(5)
    log(f"edit: row now {[a for a, _b in art_of(lib)]}")


def same_test():
    """A widget that is on two tabs: changing it on one tab changes it on the other too."""
    sys.path.insert(0, xbmcvfs_translate("special://skin/scripts"))
    import menu
    m = menu.Menu()
    wd = m.tabs[0]["widgets"][0]
    copy = dict(wd)
    m.tabs[1]["widgets"].append(copy)
    m.save()
    mon.waitForAbort(2)
    m = menu.Menu()
    wd = m.tabs[0]["widgets"][0]
    wd["style"], wd["sort"], wd["label"] = "land", "title", "Renamed"
    try:
        n = menu.copy_to_same(m, m.tabs[0], wd)
    except AttributeError:
        n = "no copy_to_same"
    m.save()
    mon.waitForAbort(3)
    t2 = len(m.tabs[1]["widgets"])
    log(f"same: copied={n} tab2.w{t2}: label={lab(f'Skin.String(nuvio.tab2.w{t2}.label)')!r} style={lab(f'Skin.String(nuvio.tab2.w{t2}.style)')!r} "
        f"sort={lab(f'Skin.String(nuvio.tab2.w{t2}.sort)')!r} tab1.w1={lab('Skin.String(nuvio.tab1.w1.label)')!r}")
    res = json.loads(xbmc.executeJSONRPC(json.dumps({"jsonrpc": "2.0", "id": 1, "method": "Addons.GetAddonDetails",
                                                    "params": {"addonid": "script.lucent.library", "properties": ["extrainfo", "enabled", "version"]}})))
    log(f"same: library addon {str(res.get('result') or res.get('error'))[:200]}")


def settings_test():
    """Skin settings: the Menu and widgets pane, and the order in Kodi's settings (Lucent category)."""
    fid = lambda: lab("System.CurrentControlID")  # noqa: E731
    xbmc.executebuiltin("ActivateWindow(SkinSettings)")
    mon.waitForAbort(3)
    xbmc.executebuiltin("SetFocus(9000,2,absolute)")
    mon.waitForAbort(1.5)
    log(f"settings: cat={lab('Container(9000).ListItem.Label')!r} sub={lab('Container(9000).ListItem.Property(sub)')!r}")
    xbmc.executebuiltin("Action(Right)")
    mon.waitForAbort(1.5)
    seen = []
    for _ in range(6):
        seen.append(fid())
        xbmc.executebuiltin("Action(Down)")
        mon.waitForAbort(0.8)
    log(f"settings: pane 3 focus path {seen}")
    shot("22-skinsettings-menu")
    xbmc.executebuiltin("SetFocus(9000,1,absolute)")
    mon.waitForAbort(1.5)
    xbmc.executebuiltin("Action(Right)")
    mon.waitForAbort(1)
    xbmc.executebuiltin("SetFocus(2201)")
    mon.waitForAbort(1)
    xbmc.executebuiltin("Action(Select)")
    mon.waitForAbort(1)
    seen = []
    for _ in range(4):
        xbmc.executebuiltin("Action(Down)")
        mon.waitForAbort(0.8)
        seen.append(fid())
    log(f"settings: pane 2 after opening Startscherm {seen}")
    xbmc.executebuiltin("Action(Select)")
    xbmc.executebuiltin("SetFocus(2201)")
    xbmc.executebuiltin("Action(Select)")
    mon.waitForAbort(1)
    xbmc.executebuiltin("ActivateWindow(home)")
    mon.waitForAbort(2)
    xbmc.executebuiltin("ActivateWindow(Settings)")
    mon.waitForAbort(3)
    n = int(lab("Container(9000).NumItems") or 0)
    cats = [lab(f"Container(9000).ListItemAbsolute({i}).Property(cat)") for i in range(n)]
    if "lucent" in cats:
        xbmc.executebuiltin(f"SetFocus(9000,{cats.index('lucent')},absolute)")
        mon.waitForAbort(2)
    items = [lab(f"Container(9100).ListItemAbsolute({i}).Label") for i in range(int(lab("Container(9100).NumItems") or 0))]
    log(f"settings: kodi menu lucent items {items}")
    shot("22-settings-lucent")
    xbmc.executebuiltin("ActivateWindow(home)")
    mon.waitForAbort(2)


def ctxmenu_test():
    """A Lucent Library film: its context menu has Seren's options."""
    xbmc.executebuiltin('ActivateWindow(Videos,"special://profile/addon_data/script.lucent.library/movies/Test Film (2020)/",return)')
    mon.waitForAbort(4)
    for _ in range(4):
        if lab("ListItem.Label").endswith(".strm") or "Test Film" in lab("ListItem.Label"):
            break
        xbmc.executebuiltin("Action(Down)")
        mon.waitForAbort(1)
    log(f"ctxmenu: item={lab('ListItem.Label')!r} path={lab('ListItem.FileNameAndPath')[-50:]!r} dbtype={lab('ListItem.DBType')!r}")
    xbmc.executebuiltin("Action(ContextMenu)")
    mon.waitForAbort(2)
    labels = []
    for i in range(1000, 1030):
        if cond(f"Control.IsVisible({i})"):
            labels.append(lab(f"Control.GetLabel({i})"))
    log(f"ctxmenu: open={cond('Window.IsVisible(contextmenu)')} items={labels}")
    shot("23-ctxmenu")
    xbmc.executebuiltin("Dialog.Close(all,true)")
    xbmc.executebuiltin("ActivateWindow(home)")
    mon.waitForAbort(2)

def resume_test():
    """Stop a film / episode half way: saved locally, and starting it again jumps back there."""
    import xbmcvfs
    rfile = xbmcvfs.translatePath("special://profile/addon_data/script.lucent.library/resume.json")
    player = xbmc.Player()
    for kind, uid in (("movie", {"tmdb": "123", "imdb": "tt0000123"}), ("episode", {"tmdb": "999"})):
        def item():
            li = xbmcgui.ListItem("Resume " + kind)
            tag = li.getVideoInfoTag()
            tag.setMediaType(kind)
            tag.setTitle("Resume " + kind)
            if kind == "episode":
                tag.setTvShowTitle("Resume Show")
                tag.setSeason(1)
                tag.setEpisode(2)
            tag.setUniqueIDs(uid)
            return li
        player.play("/tmp/ci/test.mkv", item())
        for _ in range(20):
            if player.isPlayingVideo() and player.getTotalTime() > 0:
                break
            mon.waitForAbort(0.5)
        mon.waitForAbort(6)
        player.seekTime(70)
        mon.waitForAbort(4)
        at = player.getTime()
        player.stop()
        mon.waitForAbort(3)
        try:
            saved = json.load(open(rfile))
        except Exception as error:  # noqa: BLE001
            saved = {"error": repr(error)}
        log(f"resume {kind}: stopped at {int(at)} saved={ {k: v.get('pos') for k, v in saved.items() if isinstance(v, dict)} }")
        player.play("/tmp/ci/test.mkv", item())
        for _ in range(20):
            if player.isPlayingVideo() and player.getTotalTime() > 0:
                break
            mon.waitForAbort(0.5)
        mon.waitForAbort(8)
        log(f"resume {kind}: started again, now at {int(player.getTime())}")
        shot(f"24-resume-{kind}")
        player.seekTime(115)
        mon.waitForAbort(3)
        player.stop()
        mon.waitForAbort(3)
        try:
            saved = json.load(open(rfile))
        except Exception:  # noqa: BLE001
            saved = {}
        log(f"resume {kind}: after watching to the end keys={list(saved)}")
    xbmc.executebuiltin("ActivateWindow(home)")
    mon.waitForAbort(2)

def widgetctx_test():
    """A film in a Lucent row on Home: its context menu has Seren's options too."""
    xbmc.executebuiltin("ActivateWindow(home)")
    mon.waitForAbort(2)
    found = None
    for _try in range(30):
        for cid in [8100 + n for n in range(1, 11)] + [8200 + n for n in range(1, 11)]:
            num = lab(f"Container({cid}).NumItems")
            for pos in range(int(num) if num.isdigit() else 0):
                path = lab(f"Container({cid}).ListItemAbsolute({pos}).FileNameAndPath")
                if "tmdbopen" in path and "type=movie" in path:
                    found = (cid, pos)
                    break
            if found:
                break
        if found:
            break
        mon.waitForAbort(3)
    log(f"widgetctx: film found at {found}")
    if not found:
        return
    xbmc.executebuiltin(f"Control.SetFocus({found[0]},{found[1]},absolute)")
    mon.waitForAbort(2)
    log(f"widgetctx: focus={lab('System.CurrentControlId')} item={lab('ListItem.Label')!r} path={lab('ListItem.FileNameAndPath')[:60]!r}")
    xbmc.executebuiltin("Action(ContextMenu)")
    mon.waitForAbort(2)
    labels = [lab(f"Control.GetLabel({i})") for i in range(1000, 1030) if cond(f"Control.IsVisible({i})")]
    log(f"widgetctx: open={cond('Window.IsVisible(contextmenu)')} items={labels}")
    shot("25-widgetctx")
    xbmc.executebuiltin("Dialog.Close(all,true)")
    mon.waitForAbort(1)

def limit_test():
    """Number of titles per row: 25 by default, 50, or all."""
    xbmc.executebuiltin("ActivateWindow(home)")
    xbmc.executebuiltin("Control.SetFocus(9000,0)")
    for _ in range(60):
        if lab("Container(8104).NumItems") not in ("", "0"):
            break
        mon.waitForAbort(2)
    for value in ("", "50", "0", "100", ""):
        for name in ("nuvio.tab1.w4", "nuvio.home.w4"):
            xbmc.executebuiltin(f"Skin.SetString({name}.limit,{value})" if value else f"Skin.Reset({name}.limit)")
        mon.waitForAbort(12)
        log(f"limit {value or 'standard'}: row 8104 has {lab('Container(8104).NumItems')} titles "
            f"(var={lab('$VAR[NuvioW4Limit]')!r})")
    shot("26-limit")

def digital_test():
    """Hide films until their digital release: half of the TMDb films come out digitally in 2027."""
    xbmc.executebuiltin("ActivateWindow(home)")
    xbmc.executebuiltin("Control.SetFocus(8101,0)")
    for _ in range(5):
        mon.waitForAbort(1)
        xbmc.executebuiltin("Action(Down)")
    for _ in range(150):
        if lab("Container(8106).NumItems") not in ("", "0"):
            break
        mon.waitForAbort(2)
    for on in (False, True, False):
        xbmc.executebuiltin("Skin.SetBool(lucent.hide.undigital)" if on else "Skin.Reset(lucent.hide.undigital)")
        HOME.setProperty("lucent.wr.6", str(time.time()))
        mon.waitForAbort(8)
        log(f"digital {'on' if on else 'off'}: row 8106 has {lab('Container(8106).NumItems')} films")

def watched_test():
    """No pop-up for an episode you already saw: Seren's Trakt copy says watched."""
    import sqlite3
    import sys
    import xbmcvfs
    sys.path.append(xbmcvfs.translatePath("special://skin/scripts"))
    path = xbmcvfs.translatePath("special://profile/addon_data/plugin.video.seren/traktSync.db")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    con = sqlite3.connect(path)
    con.execute("CREATE TABLE IF NOT EXISTS shows (trakt_id INTEGER, tmdb_id INTEGER)")
    con.execute("CREATE TABLE IF NOT EXISTS episodes (trakt_show_id INTEGER, season INTEGER, number INTEGER, watched INTEGER)")
    con.execute("CREATE TABLE IF NOT EXISTS movies (tmdb_id INTEGER, watched INTEGER)")
    con.execute("INSERT INTO shows VALUES (77, 5555)")
    con.execute("INSERT INTO episodes VALUES (77, 2, 3, 1)")
    con.execute("INSERT INTO episodes VALUES (77, 2, 4, 0)")
    con.execute("INSERT INTO movies VALUES (6666, 1)")
    con.commit()
    con.close()
    import agenda_core
    for ev in ({"kind": "tv", "tmdb": 5555, "season": 2, "episode": 3}, {"kind": "tv", "tmdb": 5555, "season": 2, "episode": 4},
               {"kind": "tv", "tmdb": 9, "season": 1, "episode": 1}, {"kind": "movie", "tmdb": 6666, "season": 0, "episode": 0}):
        log(f"watchedcheck {ev['kind']} {ev['tmdb']} S{ev['season']}E{ev['episode']}: {agenda_core.already_watched(ev)}")

def postersize_test():
    """Big posters (default) and small posters: the row title stays under the hero, small rows peek."""
    for small in (False, True, False):
        xbmc.executebuiltin("Skin.SetBool(lucent.posters.small)" if small else "Skin.Reset(lucent.posters.small)")
        xbmc.executebuiltin("ReloadSkin()")
        mon.waitForAbort(8)
        xbmc.executebuiltin("ActivateWindow(home)")
        xbmc.executebuiltin("Control.SetFocus(8101,0)")
        mon.waitForAbort(6)
        tag = "small" if small else "big"
        shot(f"27-posters-{tag}-row1")
        xbmc.executebuiltin("Action(Down)")
        mon.waitForAbort(3)
        log(f"postersize {tag}: focus={lab('System.CurrentControlId')} labelshidden={cond('Skin.HasSetting(nuvio.posterlabels.hide)')}")
        shot(f"27-posters-{tag}-row2")

def libsplit_test():
    """Library rows with only films / only series: Kodi opens them without errors."""
    base = "plugin://script.lucent.library/?action=lib&kind="
    for kind in ("continue", "continue&only=movie", "continue&only=tv", "newin&only=movie", "newin&only=tv"):
        res = json.loads(xbmc.executeJSONRPC(json.dumps({"jsonrpc": "2.0", "id": 1, "method": "Files.GetDirectory",
                                                         "params": {"directory": base + kind, "media": "video"}})))
        files = (res.get('result') or {}).get('files') or []
        log(f"libsplit {kind}: {'error ' + str(res['error']) if 'error' in res else [f.get('label') for f in files]}")
    import sys
    import xbmcvfs
    sys.path.append(xbmcvfs.translatePath("special://skin/scripts"))
    import menu
    log(f"libsplit menu: {[menu.tr(k) for k, p, _s in menu.WIDGETS_LIBRARY if 'only=' in p]}")

def trailer_test():
    """A trailer from the page: full screen at once (not behind the page), and the page comes back afterwards."""
    xbmc.executebuiltin('ActivateWindow(Videos,"videodb://movies/titles/",return)')
    mon.waitForAbort(4)
    for _ in range(4):
        if lab("ListItem.Label") == "Lib Film":
            break
        xbmc.executebuiltin("Action(Down)")
        mon.waitForAbort(1)
    xbmc.executebuiltin("Action(Info)")
    mon.waitForAbort(4)
    log(f"trailer: page open={cond('Window.IsActive(movieinformation)')} item={lab('ListItem.Label')!r}")
    t0 = time.time()
    xbmc.executebuiltin("PlayMedia(/tmp/ci/test.mkv)")
    xbmc.executebuiltin("SetProperty(nuvio.open.leave,1,home)")
    xbmc.executebuiltin("RunScript(special://skin/scripts/trailerback.py)")
    seen = []
    while time.time() - t0 < 8:
        state = (xbmc.Player().isPlayingVideo(), cond("Window.IsActive(fullscreenvideo)"), cond("Window.IsActive(movieinformation)"))
        if not seen or seen[-1][1:] != state:
            seen.append((round(time.time() - t0, 1),) + state)
        mon.waitForAbort(0.1)
    log(f"trailer: (time, playing, fullscreen, page) {seen}")
    shot("28-trailer-playing")
    xbmc.Player().stop()
    mon.waitForAbort(5)
    log(f"trailer: after stop page open={cond('Window.IsActive(movieinformation)')} window={lab('System.CurrentWindow')!r}")
    shot("28-trailer-after")
    xbmc.executebuiltin("Dialog.Close(all,true)")
    xbmc.executebuiltin("ActivateWindow(home)")
    mon.waitForAbort(2)

def audio_test():
    """Spoken language: first choice Dutch (not in the film), second English: the English 5.1, not the commentary."""
    xbmc.executebuiltin("Skin.SetString(lucent.audio.lang1,nl)")
    xbmc.executebuiltin("Skin.SetString(lucent.audio.lang2,en)")
    mon.waitForAbort(8)                              # the helper starts its watcher
    for run in (1, 2):
        xbmc.executebuiltin("PlayMedia(/tmp/ci/audio.mkv)")
        mon.waitForAbort(25)
        res = json.loads(xbmc.executeJSONRPC(json.dumps({"jsonrpc": "2.0", "id": 1, "method": "Player.GetProperties",
                                                         "params": {"playerid": 1, "properties": ["currentaudiostream", "audiostreams"]}})))
        r = res.get("result") or {}
        cur = r.get("currentaudiostream") or {}
        if run == 3 and xbmcvfs.exists("special://skin/scripts/subtitles.py"):   # gone from the skin in 1.37.0
            import sys
            sys.path.append(xbmcvfs.translatePath("special://skin/scripts"))
            import subtitles as subs
            log(f"audio direct: lang2(eng)={subs.lang2('eng')!r} lang1={lab('Skin.String(lucent.audio.lang1)')!r}")
            try:
                subs.fix_audio()
            except Exception as error:  # noqa: BLE001
                log(f"audio direct error {error!r}")
            mon.waitForAbort(2)
            res = json.loads(xbmc.executeJSONRPC(json.dumps({"jsonrpc": "2.0", "id": 1, "method": "Player.GetProperties",
                                                             "params": {"playerid": 1, "properties": ["currentaudiostream", "audiostreams"]}})))
            r = res.get("result") or {}
            cur = r.get("currentaudiostream") or {}
        log(f"audio state: play.start={HOME.getProperty('lucent.play.start')!r} now={time.time():.1f} trailer={HOME.getProperty('nuvio.trailer.playing')!r} title={lab('VideoPlayer.Title')!r} inet={cond('Player.IsInternetStream')}")
        log(f"audio run {run}: now {cur.get('language')} {cur.get('name')!r} ch={cur.get('channels')} of {[(a.get('language'), a.get('name')) for a in r.get('audiostreams') or []]}")
        xbmc.Player().stop()
        mon.waitForAbort(3)
    xbmc.executebuiltin("Skin.Reset(lucent.audio.lang1)")
    xbmc.executebuiltin("Skin.Reset(lucent.audio.lang2)")

def menumove_test():
    """1.35.1: the list options moved from Settings > Lucent to Skin settings (Layout > Lists and posters, Look, Integrations)."""
    for f in ("2206", "2501"):
        xbmc.executebuiltin(f"Skin.SetBool(lucent.ss.open.{f})")
    xbmc.executebuiltin("ActivateWindow(SkinSettings)")
    mon.waitForAbort(2.5)
    n = int(lab("Container(9000).NumItems") or 0)
    labels = [lab(f"Container(9000).ListItemAbsolute({i}).Label") for i in range(n)]
    log(f"menumove: cats {labels}")
    for cat, first, ids, name in ((1, 1230, (2206, 1230, 1231, 1232, 1233, 1234), "layout"), (0, 1112, (1111, 1112), "look"),
                                  (4, 1525, (1509, 1525), "integrations")):
        xbmc.executebuiltin(f"SetFocus(9000,{cat},absolute)")
        mon.waitForAbort(1.2)
        xbmc.executebuiltin("Action(Right)")
        mon.waitForAbort(0.6)
        xbmc.executebuiltin(f"SetFocus({first})")
        mon.waitForAbort(0.8)
        vis = {i: cond(f"Control.IsVisible({i})") for i in ids}
        log(f"menumove {name}: focus={lab('System.CurrentControlId')} visible={vis}")
        shot(f"menumove-{name}")
        path = [lab("System.CurrentControlId")]
        for _ in range(7):
            xbmc.executebuiltin("Action(Down)")
            mon.waitForAbort(0.35)
            path.append(lab("System.CurrentControlId"))
        log(f"menumove {name}: down path {path}")
    xbmc.executebuiltin("SetFocus(1230)")
    mon.waitForAbort(0.5)
    before = cond("Skin.HasSetting(lucent.mf.off)")
    xbmc.executebuiltin("SetFocus(9000,1,absolute)")
    mon.waitForAbort(1)
    xbmc.executebuiltin("Action(Right)")
    mon.waitForAbort(0.5)
    xbmc.executebuiltin("SetFocus(1230)")
    mon.waitForAbort(0.5)
    xbmc.executebuiltin("Action(Select)")
    mon.waitForAbort(0.8)
    log(f"menumove toggle: mf.off {before} -> {cond('Skin.HasSetting(lucent.mf.off)')}")
    xbmc.executebuiltin("Skin.Reset(lucent.mf.off)")
    for f in ("2206", "2501"):
        xbmc.executebuiltin(f"Skin.Reset(lucent.ss.open.{f})")
    xbmc.executebuiltin("ActivateWindow(home)")
    mon.waitForAbort(2)


def navwalk_test():
    """Every pane of the skin settings, all folds open: Down and Up through every row; report where focus sticks."""
    import re
    import xbmcvfs
    xml = open(xbmcvfs.translatePath("special://skin/xml/SkinSettings.xml"), encoding="utf-8").read()
    folds = sorted(set(re.findall(r"lucent\.ss\.open\.(\d+)", xml)))
    for f in folds:
        xbmc.executebuiltin(f"Skin.SetBool(lucent.ss.open.{f})")
    fid = lambda: lab("System.CurrentControlID")  # noqa: E731
    xbmc.executebuiltin("ActivateWindow(SkinSettings)")
    mon.waitForAbort(3)
    n = int(lab("Container(9000).NumItems") or 0)
    for c in range(n):
        xbmc.executebuiltin(f"SetFocus(9000,{c},absolute)")
        mon.waitForAbort(1.2)
        name = lab("Container(9000).ListItem.Label")
        xbmc.executebuiltin("Action(Right)")
        mon.waitForAbort(0.8)
        for direction in ("Down", "Up"):
            path = [fid()]
            for _ in range(45):
                xbmc.executebuiltin(f"Action({direction})")
                mon.waitForAbort(0.35)
                path.append(fid())
                if path[-1] == path[0] and len(path) > 2:
                    break
            stuck = [path[i] for i in range(1, len(path)) if path[i] == path[i - 1]]
            log(f"navwalk {c} {name!r} {direction}: {len(set(path))} rows, stuck at {sorted(set(stuck))}, path {path}")
        xbmc.executebuiltin("SetFocus(9000)")
        mon.waitForAbort(0.5)
    for f in folds:
        xbmc.executebuiltin(f"Skin.Reset(lucent.ss.open.{f})")
    xbmc.executebuiltin("ActivateWindow(home)")
    mon.waitForAbort(2)

def setup_test():
    """Setup assistant: the steps Subtitles and Look show their buttons."""
    xbmc.executebuiltin("RunScript(special://skin/scripts/setup.py)")
    mon.waitForAbort(4)
    for step in (5, 7):
        xbmc.executebuiltin(f"SetFocus(100,{step},absolute)")
        mon.waitForAbort(0.5)
        xbmc.executebuiltin("Action(Select)")
        mon.waitForAbort(2)
        acts = [lab(f"Window.Property(act{n})") for n in range(1, 5)]
        log(f"setup step {step}: {lab('Window.Property(stepno)')!r} buttons {acts}")
        shot(f"29-setup-{step}")
    xbmc.executebuiltin("Dialog.Close(all,true)")
    xbmc.executebuiltin("ActivateWindow(home)")
    mon.waitForAbort(2)

def maint_test():
    """Maintenance: zip files, old temp files and the old log go; two cached pictures are removed the proper way."""
    import sys
    import xbmcvfs
    sys.path.append(xbmcvfs.translatePath("special://skin/scripts"))
    import maintenance as m
    pk = xbmcvfs.translatePath("special://home/addons/packages/")
    os.makedirs(pk, exist_ok=True)
    open(os.path.join(pk, "old.addon-1.0.zip"), "wb").write(b"x" * 300000)
    tmp = os.path.join(xbmcvfs.translatePath("special://temp/"), "lucent-ci-old.tmp")
    open(tmp, "wb").write(b"y" * 1000)
    os.utime(tmp, (time.time() - 5 * 86400, time.time() - 5 * 86400))
    fresh = os.path.join(xbmcvfs.translatePath("special://temp/"), "lucent-ci-new.tmp")
    open(fresh, "wb").write(b"z")
    pics = m.old_pictures(-1)                       # every picture counts as old
    log(f"maint: found pkgs={len(m.packages())} temp={[os.path.basename(f) for f in m.temp_files()]} pictures={len(pics)}")
    two = [p for p in pics if p[1] and os.path.exists(p[1])][:2]
    freed = m.delete(m.packages()) + m.delete(m.temp_files()) + m.remove_pictures(two)
    left = [os.path.exists(p[1]) for p in two]
    still = {p[0] for p in m.old_pictures(-1)}
    log(f"maint: freed {m.size_text(freed)}; packages left {len(m.packages())}; old tmp gone {not os.path.exists(tmp)}; "
        f"new tmp kept {os.path.exists(fresh)}; picture files left {left}; picture ids left {[p[0] in still for p in two]}")
    xbmc.executebuiltin("Skin.SetBool(lucent.maint.auto)")
    xbmc.executebuiltin("Skin.Reset(lucent.maint.last)")
    mon.waitForAbort(1)
    m.auto()
    log(f"maint: auto ran, last={lab('Skin.String(lucent.maint.last)')!r}")
    xbmc.executebuiltin("Skin.Reset(lucent.maint.auto)")
    xbmc.executebuiltin("ActivateWindow(SkinSettings)")
    mon.waitForAbort(2)
    n = int(lab("Container(9000).NumItems") or 0)
    labels = [lab(f"Container(9000).ListItemAbsolute({i}).Label") for i in range(n)]
    if "Advanced" in labels:
        xbmc.executebuiltin(f"SetFocus(9000,{labels.index('Advanced')},absolute)")
        mon.waitForAbort(1)
        xbmc.executebuiltin("Action(Right)")
        mon.waitForAbort(0.5)
        path = [lab("System.CurrentControlID")]
        for _ in range(10):
            xbmc.executebuiltin("Action(Down)")
            mon.waitForAbort(0.35)
            path.append(lab("System.CurrentControlID"))
        log(f"maint: advanced pane path {path}")
        xbmc.executebuiltin("SetFocus(1809)")
        mon.waitForAbort(0.5)
        xbmc.executebuiltin("Action(Select)")
        mon.waitForAbort(3)
        log(f"maint: menu open={cond('Window.IsVisible(selectdialog)')} heading={lab('Control.GetLabel(1)')!r}")
        shot("30-maintenance")
        xbmc.executebuiltin("Dialog.Close(all,true)")
    xbmc.executebuiltin("ActivateWindow(home)")
    mon.waitForAbort(2)

def sameaudio_test():
    """Sound in your language (English here): the English subtitle goes off. Russian sound: it stays on."""
    log(f"same: kodi language={xbmc.getLanguage(xbmc.ISO_639_1)!r}")
    for a in ("eng", "rus"):
        xbmc.executebuiltin(f"PlayMedia(/tmp/ci/same-{a}.mkv)")
        mon.waitForAbort(25)
        log(f"same {a} sound: subtitle on={cond('VideoPlayer.SubtitlesEnabled')} lang={lab('VideoPlayer.SubtitlesLanguage')!r}")
        xbmc.Player().stop()
        mon.waitForAbort(3)

def skip_test():
    """TheIntroDB's skip window in the Lucent look: Kodi takes the skin's overlay.xml; the add-on sets the text."""
    import threading
    import xbmcaddon
    path = xbmcaddon.Addon("plugin.video.tidb").getAddonInfo("path")
    win = xbmcgui.WindowXMLDialog("overlay.xml", path, "default", "1080i")

    def later():
        mon.waitForAbort(2)
        try:
            win.getControl(3001).setLabel("Skip intro")
        except Exception as error:  # noqa: BLE001
            log(f"skip: label error {error!r}")
        mon.waitForAbort(1.5)
        log(f"skip: window={lab('System.CurrentWindow')!r} focus={lab('System.CurrentControlID')} label={lab('Control.GetLabel(3001)')!r}")
        shot("31-skip")
        win.close()
    threading.Thread(target=later).start()
    win.doModal()
    del win
    xbmc.executebuiltin("RunScript(special://skin/scripts/setup.py)")
    mon.waitForAbort(4)
    xbmc.executebuiltin("SetFocus(100,5,absolute)")
    mon.waitForAbort(0.5)
    xbmc.executebuiltin("Action(Select)")
    mon.waitForAbort(2)
    log(f"skip: setup {lab('Window.Property(stepno)')!r} buttons {[lab(f'Window.Property(act{n})') for n in range(1, 5)]}")
    xbmc.executebuiltin("Dialog.Close(all,true)")
    xbmc.executebuiltin("ActivateWindow(home)")
    mon.waitForAbort(2)

def skipkey_test():
    """Setup > Skip intro: a filled-in TheIntroDB API key gives an orange warning and a first button that removes it."""
    import xbmcaddon
    tidb = xbmcaddon.Addon("plugin.video.tidb")
    tidb.setSetting("introdb_api_key", "wrongkey123")
    log(f"skipkey: before key={tidb.getSetting('introdb_api_key')!r}")
    xbmc.executebuiltin("RunScript(special://skin/scripts/setup.py)")
    mon.waitForAbort(4)
    xbmc.executebuiltin("SetFocus(100,5,absolute)")
    mon.waitForAbort(0.5)
    xbmc.executebuiltin("Action(Select)")
    mon.waitForAbort(3)
    log(f"skipkey: step {lab('Window.Property(stepno)')!r} status={lab('Window.Property(status)')!r} color={lab('Window.Property(statecolor)')!r} "
        f"buttons {[lab(f'Window.Property(act{n})') for n in range(1, 5)]}")
    shot("33-skipkey-before")
    xbmc.executebuiltin("SetFocus(301)")
    mon.waitForAbort(0.5)
    xbmc.executebuiltin("Action(Select)")
    mon.waitForAbort(3)
    log(f"skipkey: after key={xbmcaddon.Addon('plugin.video.tidb').getSetting('introdb_api_key')!r} test={xbmcaddon.Addon('plugin.video.tidb').getSetting('test_api_key_now')!r} "
        f"status={lab('Window.Property(status)')!r} buttons {[lab(f'Window.Property(act{n})') for n in range(1, 5)]}")
    shot("33-skipkey-after")
    xbmc.executebuiltin("Dialog.Close(all,true)")
    xbmc.executebuiltin("ActivateWindow(home)")
    mon.waitForAbort(2)


def sportA_test():
    """Sport > All games: live games as cards (list 205) on top, then the games per competition (list 200)."""
    xbmc.executebuiltin("RunScript(special://skin/scripts/sport.py)")
    for _ in range(60):
        mon.waitForAbort(1)
        if cond("Window.IsVisible(Lucent_Sport.xml)"):
            break
    mon.waitForAbort(3)
    xbmc.executebuiltin("SetFocus(102)")
    mon.waitForAbort(1)
    xbmc.executebuiltin("Action(Select)")
    for _ in range(60):
        mon.waitForAbort(1)
        if int(lab("Container(200).NumItems") or 0) > 0:
            break
    mon.waitForAbort(4)
    P = lambda k: lab(f"Container(200).ListItem.Property({k})")  # noqa: E731
    C = lambda k: lab(f"Container(205).ListItem.Property({k})")  # noqa: E731
    n = int(lab("Container(200).NumItems") or 0)
    heads = [lab(f"Container(200).ListItemAbsolute({i}).Property(header)") + "/" + lab(f"Container(200).ListItemAbsolute({i}).Property(headersub)") for i in range(n)]
    ncards = int(lab("Container(205).NumItems") or 0)
    log(f"sportA: items={n} cards={ncards} live={lab('Window(Lucent_Sport.xml).Property(sport.live)') or lab('Window.Property(sport.live)')!r} strip visible={cond('Control.IsVisible(205)')}")
    log(f"sportA: competitions in order {[h for h in heads if h != '/']}")
    xbmc.executebuiltin("SetFocus(114)")
    mon.waitForAbort(1)
    xbmc.executebuiltin("Action(Down)")
    mon.waitForAbort(1.5)
    log(f"sportA: day strip Down -> focus={lab('System.CurrentControlID')}")
    shot("32-sportA-top")
    if ncards:
        for step in range(min(3, ncards)):
            log(f"sportA: card {step}: {C('hname')}-{C('aname')} {C('score')!r} min={C('min')!r} chan={C('chan')!r} prog={C('prog')!r} "
                f"panel={P('hname')}-{P('aname')} same={C('evid') == P('evid')} focus={lab('System.CurrentControlID')}")
            xbmc.executebuiltin("Action(Right)")
            mon.waitForAbort(1.5)
        shot("32-sportA-right")
        xbmc.executebuiltin("Action(Down)")
        mon.waitForAbort(1.5)
        log(f"sportA: cards Down -> focus={lab('System.CurrentControlID')}")
        xbmc.executebuiltin("SetFocus(200,0,absolute)")
        mon.waitForAbort(1.5)
        xbmc.executebuiltin("Action(Up)")
        mon.waitForAbort(1.5)
        log(f"sportA: list top Up -> focus={lab('System.CurrentControlID')}")
    xbmc.executebuiltin("SetFocus(200,0,absolute)")
    mon.waitForAbort(1.5)
    for _ in range(4):
        xbmc.executebuiltin("Action(Down)")
        mon.waitForAbort(1.2)
    log(f"sportA: after 4x down: {P('hname')!r} header={P('header')!r} focus={lab('System.CurrentControlID')}")
    shot("32-sportA-list")
    xbmc.executebuiltin("SetFocus(101)")
    mon.waitForAbort(1)
    xbmc.executebuiltin("Action(Select)")
    mon.waitForAbort(5)
    log(f"sportA: mine view strip visible={cond('Control.IsVisible(205)')} view={lab('Window.Property(sport.view)')!r}")
    shot("32-sportA-mine")
    xbmc.executebuiltin("Dialog.Close(all,true)")
    xbmc.executebuiltin("ActivateWindow(home)")
    mon.waitForAbort(2)


def tables_test():
    """Sport > Tables (T1+T2): competitions as tabs, table with W/D/L, club panel that follows the selected row."""
    xbmc.executebuiltin("RunScript(special://skin/scripts/sport.py)")
    for _ in range(60):
        mon.waitForAbort(1)
        if cond("Window.IsVisible(Lucent_Sport.xml)"):
            break
    mon.waitForAbort(3)
    xbmc.executebuiltin("SetFocus(103)")
    mon.waitForAbort(1)
    xbmc.executebuiltin("Action(Select)")
    for _ in range(40):
        mon.waitForAbort(1)
        if int(lab("Container(410).NumItems") or 0) > 0:
            break
    mon.waitForAbort(4)
    W = lambda k: lab(f"Window(Lucent_Sport.xml).Property(sport.tc.{k})") or lab(f"Window.Property(sport.tc.{k})")  # noqa: E731
    R = lambda k: lab(f"Container(410).ListItem.Property({k})")  # noqa: E731
    log(f"tables: league={lab('Container(400).ListItem.Label')!r} n={lab('Container(410).NumItems')} focus={lab('System.CurrentControlID')} "
        f"row={lab('Container(410).ListItem.Label')!r} gp/w/d/l/gd/pts={[R(k) for k in ('gp', 'w', 'd', 'l', 'gd', 'pts')]} "
        f"legend={[lab(f'Window.Property(sport.leg{n}.text)') for n in range(1, 5)]}")
    log(f"tables: panel on={W('on')!r} name={W('name')!r} sub={W('sub')!r} form={[W(f'f{n}') for n in range(1, 6)]} "
        f"r1={W('r1')!r} {W('r1s')!r} home={W('home')!r} away={W('away')!r} next={W('next')!r} chan={W('nextchan')!r}")
    shot("34-tables-top")
    for _ in range(3):
        xbmc.executebuiltin("Action(Down)")
        mon.waitForAbort(1.5)
    log(f"tables: after 3x down row={lab('Container(410).ListItem.Label')!r} panel={W('name')!r} sub={W('sub')!r} r1={W('r1')!r}")
    shot("34-tables-down")
    xbmc.executebuiltin("Action(Up)")
    mon.waitForAbort(0.5)
    xbmc.executebuiltin("SetFocus(400)")
    mon.waitForAbort(1)
    xbmc.executebuiltin("Action(Right)")
    mon.waitForAbort(4)
    log(f"tables: league right -> {lab('Container(400).ListItem.Label')!r} n={lab('Container(410).NumItems')} row={lab('Container(410).ListItem.Label')!r} panel={W('name')!r}")
    shot("34-tables-league2")
    xbmc.executebuiltin("Dialog.Close(all,true)")
    xbmc.executebuiltin("ActivateWindow(home)")
    mon.waitForAbort(2)


def mine_test():
    """My sport M3: follow the home team of a live football game, then My sport shows it as a live scoreboard."""
    import sys as _sys
    _sys.path.insert(0, xbmcvfs.translatePath("special://skin/scripts"))
    import sport_core as sc
    live = [e for e in sc.all_cached() if e["state"] == "in" and e["kind"] == "teams"]
    soccer = [e for e in live if sc.LEAGUES.get(e["league"], {}).get("sport") == "soccer"] or live
    log(f"mine: live games={len(live)} football={len(soccer)}")
    if not soccer:
        soccer = sorted((e for e in sc.all_cached() if e["state"] == "pre" and e["kind"] == "teams"
                         and sc.LEAGUES.get(e["league"], {}).get("sport") == "soccer"), key=lambda e: e["start"])[:1]
    if not soccer:
        return
    ev = soccer[0]
    sc.toggle_team(ev["league"], ev["home"])
    log(f"mine: following {ev['home'].get('name')!r} ({ev['league']}) {ev.get('status')!r}")
    xbmc.executebuiltin("RunScript(special://skin/scripts/sport.py)")
    for _ in range(60):
        mon.waitForAbort(1)
        if cond("Window.IsVisible(Lucent_Sport.xml)"):
            break
    mon.waitForAbort(4)
    xbmc.executebuiltin("SetFocus(101)")
    mon.waitForAbort(0.5)
    xbmc.executebuiltin("Action(Select)")
    mon.waitForAbort(12)
    H = lambda k: lab(f"Container(150).ListItem.Property({k})")  # noqa: E731
    WP = lambda k: lab(f"Window.Property({k})")  # noqa: E731
    log(f"mine: hero n={lab('Container(150).NumItems')} {H('hname')}-{H('aname')} mid={H('mid')!r} when={H('when')!r} prog={H('prog')!r} "
        f"hgoals={H('hgoals')!r} agoals={H('agoals')!r}")
    log(f"mine: sections {[(WP(f'sport.sec{n}.title'), WP(f'sport.sec{n}.sub'), WP(f'sport.sec{n}.count')) for n in range(1, 4)]}")
    log(f"mine: top={H('topline')!r} watch={H('watchlabel')!r} cols={H('hfull')!r}/{H('afull')!r} week={lab('Container(209).NumItems')} also={lab('Container(160).NumItems')}")
    shot("35-mine-live")
    xbmc.executebuiltin("SetFocus(209)")
    mon.waitForAbort(1.5)
    shot("35-mine-week")
    sc.toggle_team(ev["league"], ev["home"])
    xbmc.executebuiltin("Dialog.Close(all,true)")
    xbmc.executebuiltin("ActivateWindow(home)")
    mon.waitForAbort(2)


def follow_test():
    """Follow page F3: cards of what you follow, + Add opens Search / Browse / Countries / Drivers & players."""
    xbmc.executebuiltin("RunScript(special://skin/scripts/sport.py)")
    for _ in range(60):
        mon.waitForAbort(1)
        if cond("Window.IsVisible(Lucent_Sport.xml)"):
            break
    mon.waitForAbort(3)
    xbmc.executebuiltin("SetFocus(104)")
    mon.waitForAbort(0.5)
    xbmc.executebuiltin("Action(Select)")
    mon.waitForAbort(4)
    C = lambda k: lab(f"Container(570).ListItem.Property({k})")  # noqa: E731
    log(f"follow: cards={lab('Container(570).NumItems')} first={lab('Container(570).ListItem.Label')!r} sub={C('sub')!r} next={C('next')!r} "
        f"goals={C('goals')!r} remind={C('remind')!r} count={lab('Window.Property(sport.f.count)')!r}")
    shot("36-follow-cards")
    xbmc.executebuiltin("SetFocus(571)")
    mon.waitForAbort(0.5)
    xbmc.executebuiltin("Action(Select)")
    mon.waitForAbort(3)
    log(f"follow: add={lab('Window.Property(sport.f.add)')!r} tab={lab('Window.Property(sport.f.tab)')!r} focus={lab('System.CurrentControlID')} "
        f"tabs={[lab(f'Container(575).ListItemAbsolute({i}).Label') for i in range(4)]}")
    xbmc.executebuiltin("Action(Select)")
    mon.waitForAbort(2)
    xbmc.executeJSONRPC(json.dumps({"jsonrpc": "2.0", "id": 1, "method": "Input.SendText", "params": {"text": "Ajax", "done": True}}))
    mon.waitForAbort(3)
    R = lambda k: lab(f"Container(582).ListItem.Property({k})")  # noqa: E731
    log(f"follow: search q={lab('Window.Property(sport.f.query)')!r} results={lab('Container(582).NumItems')} focus={lab('System.CurrentControlID')} "
        f"first={lab('Container(582).ListItem.Label')!r}/{lab('Container(582).ListItem.Label2')!r} btn={R('btn')!r}")
    shot("36-follow-search")
    xbmc.executebuiltin("Action(Select)")
    mon.waitForAbort(1.5)
    log(f"follow: after OK btn={R('btn')!r} mine={R('mine')!r}")
    xbmc.executebuiltin("SetFocus(575)")
    mon.waitForAbort(0.5)
    xbmc.executebuiltin("Action(Right)")
    mon.waitForAbort(2)
    log(f"follow: tab -> {lab('Window.Property(sport.f.tab)')!r} sports={lab('Container(530).NumItems')} comps={lab('Container(540).NumItems')}")
    shot("36-follow-browse")
    xbmc.executebuiltin("Action(Right)")
    mon.waitForAbort(1.5)
    xbmc.executebuiltin("Action(Down)")
    mon.waitForAbort(1.5)
    log(f"follow: tab -> {lab('Window.Property(sport.f.tab)')!r} countries={lab('Container(590).NumItems')} focus={lab('System.CurrentControlID')} first={lab('Container(590).ListItem.Label')!r}")
    xbmc.executebuiltin("Action(Select)")
    mon.waitForAbort(1)
    log(f"follow: country mine={lab('Container(590).ListItem.Property(mine)')!r}")
    shot("36-follow-countries")
    xbmc.executebuiltin("SetFocus(575)")
    mon.waitForAbort(0.5)
    xbmc.executebuiltin("Action(Right)")
    mon.waitForAbort(1.5)
    log(f"follow: tab -> {lab('Window.Property(sport.f.tab)')!r} names={lab('Container(596).NumItems')} first={lab('Container(596).ListItem.Label')!r}")
    shot("36-follow-names")
    xbmc.executebuiltin("Action(Back)")
    mon.waitForAbort(4)
    log(f"follow: back add={lab('Window.Property(sport.f.add)')!r} cards={lab('Container(570).NumItems')} labels={[lab(f'Container(570).ListItemAbsolute({i}).Label') for i in range(4)]} focus={lab('System.CurrentControlID')}")
    shot("36-follow-after")
    xbmc.executebuiltin("SetFocus(570,0,absolute)")
    mon.waitForAbort(1)
    xbmc.executebuiltin("Action(Select)")
    mon.waitForAbort(2)
    log(f"follow: card menu window={lab('System.CurrentWindow')!r} dialog={cond('Window.IsActive(contextmenu)')}")
    shot("36-follow-menu")
    xbmc.executebuiltin("Action(Back)")
    mon.waitForAbort(1)
    tk = xbmcvfs.translatePath("special://profile/keymaps/lucent-touch.xml")
    log(f"touch keymap exists={os.path.exists(tk)}")
    xbmc.executebuiltin("Dialog.Close(all,true)")
    xbmc.executebuiltin("ActivateWindow(home)")
    mon.waitForAbort(2)


def f1_test():
    """F1 game page: the track drawing turns white and lies on a dark glass panel."""
    import sys as _sys
    _sys.path.insert(0, xbmcvfs.translatePath("special://skin/scripts"))
    import sport_core as sc
    races = [e for e in sc.all_cached() if e["league"] == "f1" and e["state"] != "post"]
    races.sort(key=lambda e: ("race" not in (e.get("sub") or "").lower(), e["start"]))
    log(f"f1: events={len(races)} first={(races[0].get('title'), races[0].get('sub'), races[0]['id']) if races else None}")
    try:
        c = sc.circuit_info("617", "f1")
        log(f"f1: circuit 617 dark={c.get('dark')!r} png={c.get('png')!r} photo={c.get('photo')!r}")
    except Exception as error:  # noqa: BLE001
        log(f"f1: circuit_info error {error!r}")
    if not races:
        return
    xbmc.executebuiltin(f"RunScript(special://skin/scripts/sport.py,game,{races[0]['id']})")
    for _ in range(40):
        mon.waitForAbort(1)
        if lab("Window.Property(g.circname)") and lab("Window.Property(g.circimg)"):
            break
    mon.waitForAbort(4)
    img = lab("Window.Property(g.circimg)")
    log(f"f1: photo={lab('Window.Property(g.circphoto)')[-40:]!r} page layout={lab('Window.Property(g.layout)')!r} circ={lab('Window.Property(g.circname)')!r} img={img.rsplit('/', 1)[-1]!r} "
        f"white={lab('Window.Property(g.circpng)')!r} tiles={[lab(f'Window.Property(g.circt{n}v)') for n in range(1, 5)]}")
    local = xbmcvfs.translatePath(img) if img.startswith("special://") else ""
    if local and os.path.exists(local):
        import struct
        raw = open(local, "rb").read()
        log(f"f1: white png size={len(raw)} type={raw[25]} wh={struct.unpack('>II', raw[16:24])}")
    shot("37-f1-page")
    xbmc.executebuiltin("Dialog.Close(all,true)")
    mon.waitForAbort(1)
    xbmc.executebuiltin("Dialog.Close(all,true)")
    xbmc.executebuiltin("ActivateWindow(home)")
    mon.waitForAbort(2)


def probe_test():
    """Where can a stadium photo come from? ESPN game summary, ESPN team page, TheSportsDB."""
    import sys as _sys
    import urllib.request
    _sys.path.insert(0, xbmcvfs.translatePath("special://skin/scripts"))
    import sport_core as sc

    def get(url):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            return json.loads(urllib.request.urlopen(req, timeout=20).read().decode("utf-8", "replace"))
        except Exception as error:  # noqa: BLE001
            return {"error": repr(error)}
    games = [e for e in sc.all_cached() if e["league"] in ("ned.1", "eng.1", "nba", "nfl") and e["kind"] == "teams"][:4]
    for ev in games:
        eid = ev["id"].split(":", 1)[-1]
        d = get(f"{sc.ESPN}{sc.LEAGUES[ev['league']]['path']}/summary?event={eid}")
        venue = (d.get("gameInfo") or {}).get("venue") or {}
        log(f"probe summary {ev['league']} {ev['home'].get('name')}: venue={venue.get('fullName')!r} images={[i.get('href') for i in venue.get('images') or []][:3]} err={d.get('error')}")
        t = get(f"{sc.ESPN}{sc.LEAGUES[ev['league']]['path']}/teams/{ev['home'].get('id')}")
        team = t.get("team") or {}
        fv = (team.get("franchise") or {}).get("venue") or team.get("venue") or {}
        log(f"probe team {ev['home'].get('name')}: keys={sorted(team)[:25]} venue={fv.get('fullName')!r} images={[i.get('href') for i in fv.get('images') or []][:3]}")
    for key in ("3", "123"):
        d = get(f"https://www.thesportsdb.com/api/v1/json/{key}/searchteams.php?t=Ajax")
        teams = d.get("teams") or []
        log(f"probe tsdb key {key}: n={len(teams)} err={d.get('error')} stadium={(teams[0].get('strStadium'), teams[0].get('strStadiumThumb') or teams[0].get('strVenueThumb'), teams[0].get('strFanart1')) if teams else None}")


def club_test():
    """Club page: logo behind the games, club colours, stadium photo in the TV window; All games: stadium of the home team."""
    import sys as _sys
    _sys.path.insert(0, xbmcvfs.translatePath("special://skin/scripts"))
    import sport_core as sc
    row = next((r for r in sc.standings("ned.1") if "Ajax" in (r.get("team") or "")), None)
    log(f"club: ajax row={(row or {}).get('id')!r}")
    if not row:
        return
    xbmc.executebuiltin(f"RunScript(special://skin/scripts/sport.py,team,ned.1,{row['id']},{row['team']})")
    for _ in range(30):
        mon.waitForAbort(1)
        if lab("Window.Property(sport.view)") == "team" and lab("Window.Property(sport.stadium)"):
            break
    mon.waitForAbort(3)
    W = lambda k: lab(f"Window.Property({k})")  # noqa: E731
    log(f"club: view={W('sport.view')!r} games={lab('Container(200).NumItems')} logo={W('sport.teamlogo')[-40:]!r} bg={W('sport.bgA')!r} "
        f"stadium={W('sport.stadium')[-60:]!r} name={W('sport.stadium.name')!r}")
    shot("38-club")
    xbmc.executebuiltin("SetFocus(102)")
    mon.waitForAbort(0.5)
    xbmc.executebuiltin("Action(Select)")
    mon.waitForAbort(4)
    xbmc.executebuiltin("SetFocus(200,1,absolute)")
    mon.waitForAbort(1)
    xbmc.executebuiltin("Action(Down)")
    for _ in range(15):
        mon.waitForAbort(1)
        if W("sport.stadium"):
            break
    log(f"club: all games on {lab('Container(200).ListItem.Property(hname)')!r} stadium={W('sport.stadium')[-60:]!r} name={W('sport.stadium.name')!r}")
    shot("38-allgames-stadium")
    xbmc.executebuiltin("Dialog.Close(all,true)")
    xbmc.executebuiltin("ActivateWindow(home)")
    mon.waitForAbort(2)


def guide_test():
    """TV guide G1 (no channels in CI: only the frame, the header and the buttons)."""
    xbmc.executebuiltin("ActivateWindow(TVGuide)")
    mon.waitForAbort(6)
    log(f"guide: window={lab('System.CurrentWindow')!r} focus={lab('System.CurrentControlID')} groups={lab('Container(11).NumItems')}")
    shot("39-guide")
    xbmc.executebuiltin("ActivateWindow(home)")
    mon.waitForAbort(2)


def browse_test():
    """Issue #3: the file browser that add-ons open (Dialog().browse) must list the files, not only '..'."""
    import threading
    for typ, mask, start in ((1, "", "special://skin/xml/"), (1, ".xml", "special://skin/xml/"), (2, "", "special://skin/media/"),
                             (1, "", "special://skin/")):
        def later(typ=typ, mask=mask):
            mon.waitForAbort(4)
            n = lab("Container(450).NumItems")
            log(f"browse: type={typ} mask={mask!r} window={lab('System.CurrentWindow')!r} focus={lab('System.CurrentControlID')} "
                f"items450={n} items451={lab('Container(451).NumItems')} first={[lab(f'Container(450).ListItemAbsolute({i}).Label') for i in range(4)]} "
                f"vis450={cond('Control.IsVisible(450)')} vis451={cond('Control.IsVisible(451)')}")
            shot(f"40-browse-{typ}-{mask.strip('.') or 'all'}")
            xbmc.executebuiltin("Action(Back)")
        t = threading.Thread(target=later)
        t.start()
        xbmcgui.Dialog().browse(typ, "Test", "files", mask, False, False, start)
        t.join()
        mon.waitForAbort(1)


def w1_test():
    """Game page W1: a football game (a finished one has statistics and a timeline)."""
    import sys as _sys
    _sys.path.insert(0, xbmcvfs.translatePath("special://skin/scripts"))
    import sport_core as sc
    games = [e for e in sc.all_cached() if e["kind"] == "teams" and sc.LEAGUES.get(e["league"], {}).get("sport") == "soccer"]
    games.sort(key=lambda e: ({"in": 0, "post": 1, "pre": 2}[e["state"]], -e["start"] if e["state"] == "post" else e["start"]))
    log(f"w1: games={len(games)} first={(games[0]['home'].get('name'), games[0]['away'].get('name'), games[0]['state']) if games else None}")
    if not games:
        return
    xbmc.executebuiltin(f"RunScript(special://skin/scripts/sport.py,game,{games[0]['id']})")
    for _ in range(30):
        mon.waitForAbort(1)
        if lab("Window.Property(g.layout)") == "teams" and lab("Window.Property(g.st1l)"):
            break
    mon.waitForAbort(4)
    W = lambda k: lab(f"Window.Property(g.{k})")  # noqa: E731
    log(f"w1: top={W('topline')!r} mid={W('bigmid')!r} sub={W('bigsub')!r} lines={W('hline')!r}/{W('aline')!r} goals={W('hgoals')!r}/{W('agoals')!r} "
        f"stats={[W(f'st{n}l') + ':' + W(f'st{n}h') + '-' + W(f'st{n}a') + '/' + W(f'st{n}k') for n in range(1, 5)]} "
        f"timeline={[W(f'tl{n}m') + ' ' + W(f'tl{n}k') + ' ' + W(f'tl{n}x') for n in range(1, 4)]} table={W('tabletitle')!r} focus={lab('System.CurrentControlID')}")
    log(f"w1: remind={W('remindtext')!r} rec={W('rectext')!r} vis1330={cond('Control.IsVisible(1330)')} vis1332={cond('Control.IsVisible(1332)')} table={W('table')!r}")
    shot("41-w1")
    xbmc.executebuiltin("Dialog.Close(all,true)")
    mon.waitForAbort(1)
    xbmc.executebuiltin("Dialog.Close(all,true)")
    xbmc.executebuiltin("ActivateWindow(home)")
    mon.waitForAbort(2)


def w3_test():
    """Game page for basketball (W3): points per quarter, top players, team stats."""
    import sys as _sys
    _sys.path.insert(0, xbmcvfs.translatePath("special://skin/scripts"))
    import sport_core as sc
    games = [e for e in sc.all_cached() if e["kind"] == "teams" and e["league"] == "nba"]
    games.sort(key=lambda e: ({"in": 0, "post": 1, "pre": 2}[e["state"]], -e["start"] if e["state"] == "post" else e["start"]))
    log(f"w3: games={len(games)} first={(games[0]['home'].get('name'), games[0]['state']) if games else None}")
    if not games:
        return
    xbmc.executebuiltin(f"RunScript(special://skin/scripts/sport.py,game,{games[0]['id']})")
    for _ in range(30):
        mon.waitForAbort(1)
        if lab("Window.Property(g.layout)") == "teams" and lab("Window.Property(g.tp1n)"):
            break
    mon.waitForAbort(3)
    W = lambda k: lab(f"Window.Property(g.{k})")  # noqa: E731
    log(f"w3: mid={W('bigmid')!r} qn={W('qn')!r} q={[W(f'qh{i}') + '/' + W(f'qa{i}') for i in range(1, 5)]} "
        f"stats={[W(f'st{n}l') + ':' + W(f'st{n}h') + '-' + W(f'st{n}a') for n in range(1, 5)]} top={[W(f'tp{n}n') + ' ' + W(f'tp{n}v') for n in range(1, 5)]}")
    shot("42-w3")
    xbmc.executebuiltin("Dialog.Close(all,true)")
    mon.waitForAbort(1)
    xbmc.executebuiltin("Dialog.Close(all,true)")
    xbmc.executebuiltin("ActivateWindow(home)")
    mon.waitForAbort(2)


def pagelimit_test():
    """Number of titles: choosing 100 for a Seren row offers to raise Seren's page limit (20) and does it."""
    import sys as _sys
    import threading
    import xbmcaddon
    _sys.path.insert(0, xbmcvfs.translatePath("special://skin/scripts"))
    import menu
    ser = xbmcaddon.Addon("plugin.video.seren")
    log(f"limit: before={ser.getSetting('item.limit')!r}")
    t = threading.Thread(target=menu.source_page, args=({"limit": "100", "path": "plugin://plugin.video.seren/?action=x"},), daemon=True)
    t.start()
    for _ in range(15):
        mon.waitForAbort(1)
        if cond("Window.IsActive(yesnodialog)"):
            break
    log(f"limit: dialog={cond('Window.IsActive(yesnodialog)')} text={lab('Control.GetLabel(9)')!r}")
    shot("50-limit-ask")
    xbmc.executebuiltin("SendClick(11)")
    t.join(10)
    mon.waitForAbort(1)
    log(f"limit: after={xbmcaddon.Addon('plugin.video.seren').getSetting('item.limit')!r}")
    shot("51-limit-done")
    # a non-Seren add-on: only a notification, no question
    menu.source_page({"limit": "50", "path": "plugin://plugin.video.youtube/"})
    mon.waitForAbort(1)
    log(f"limit: other dialog={cond('Window.IsActive(yesnodialog)')}")
    xbmc.executebuiltin("Dialog.Close(all,true)")
    mon.waitForAbort(1)


def panels_test():
    """Tabs without rows of their own (Calendar, TV, Sport, Add-ons, Settings, Power) show their own screen."""
    import sys as _sys
    import datetime as _dt
    _sys.path.insert(0, xbmcvfs.translatePath("special://skin/scripts"))
    import menu
    import tabpanels
    m = menu.Menu()
    for label, action in (("TV", "RunScript(special://skin/scripts/tv.py)"), ("Sport", "RunScript(special://skin/scripts/sport.py)"),
                          ("Add-ons", "ActivateWindow(AddonBrowser)"), ("Settings", "ActivateWindow(Settings)"), ("Power", "ActivateWindow(ShutdownMenu)")):
        if not any(t["action"] == action for t in m.tabs) and len(m.tabs) < menu.NTABS:
            m.tabs.append({"label": label, "icon": "icons/tv.png", "action": action, "widgets": [], "actionlabel": ""})
    m.save()
    # a week of calendar items
    data = xbmcvfs.translatePath("special://profile/addon_data/skin.lucent/")
    os.makedirs(data, exist_ok=True)
    art = "special://home/addons/plugin.video.fakeseren/icon.png"
    today = _dt.date.today()
    evs = []
    for n, (name, days, at) in enumerate((("The Northern Line", 20, "21:00"), ("Harbor Lights", 21, "20:00"), ("Kitchen Wars", 30, ""), ("Silent Peak", 40, ""))):
        evs.append({"kind": "tv" if n < 3 else "movie", "key": f"k{n}", "name": name, "title": "De laatste halte" if n == 0 else "",
                    "season": 3, "episode": 5 + n, "date": (today + _dt.timedelta(days=days)).isoformat(), "time": at,
                    "still": art, "backdrop": art, "network": "HBO Max" if n == 0 else "", "plot": "Mara ontdekt wie er achter de verdwenen trein zit.",
                    "tmdb": 100 + n, "logo": "", "digital": True})
    json.dump({"shows": {"tv:1": {"name": "x", "kind": "tv", "tmdb": 1, "notify": True}}, "synced": time.time()}, open(data + "agenda_follow.json", "w"))
    import agenda_core
    json.dump({"v": agenda_core.CACHE_VERSION, "shows": {"tv:1": {"events": evs, "fetched": time.time()}}}, open(data + "agenda_cache.json", "w"))
    tabpanels.update()
    rows = [("1", "Ajax", "PSV", "2", "1", "LIVE 67'", "1", "D2122E", "ED1C24"), ("2", "Feyenoord", "AZ", "", "", "18:45", "", "E30613", "C8102E"),
            ("3", "Real Madrid", "Barcelona", "", "", "21:00", "", "1C3C8C", "A50044")]
    def set_sport():
      for n, (i, hn, an, hs, as_, when, live, hc, ac) in enumerate(rows, 1):
        for k, v in {"id": i, "hname": hn, "aname": an, "hs": hs, "as": as_, "when": when, "live": live, "hcol": hc, "acol": ac,
                     "hlogo": art, "alogo": art, "league": "Eredivisie", "kick": ("LIVE · EREDIVISIE · 67'" if live else f"{when} · EREDIVISIE"),
                     "big": f"{hs} – {as_}" if hs else when}.items():
            HOME.setProperty(f"lucent.ps.{n}.{k}", v)
    set_sport()
    log(f"panels: cal1={HOME.getProperty('lucent.pc.1.title')!r} day={HOME.getProperty('lucent.pc.1.day')!r} cal4={HOME.getProperty('lucent.pc.4.title')!r} sub4={HOME.getProperty('lucent.pc.4.sub')!r}")
    xbmc.executebuiltin("ActivateWindow(home)")
    mon.waitForAbort(3)
    wanted = [("cal", "agenda.py", 9310), ("tv", "scripts/tv.py", 9320), ("sport", "scripts/sport.py", 9330),
              ("addons", "AddonBrowser", 9340), ("settings", "ActivateWindow(Settings)", 9350), ("power", "ShutdownMenu", 9360)]
    count = int(lab("Container(9000).NumItems") or 0)
    acts = []
    for i in range(count):
        xbmc.executebuiltin(f"Control.SetFocus(9000,{i})")
        mon.waitForAbort(0.4)
        acts.append(lab("Container(9000).ListItem.Property(act)"))
    log(f"panels: tabs={[a[-30:] for a in acts]}")
    for name, needle, cid in wanted:
        idx = next((i for i, a in enumerate(acts) if needle in a), None)
        if idx is None:
            log(f"panels: {name} tab missing")
            continue
        xbmc.executebuiltin(f"Control.SetFocus(9000,{idx})")
        tabpanels.update()                  # the helper may have cleared the test values
        set_sport()
        mon.waitForAbort(2)
        set_sport()
        mon.waitForAbort(1)
        log(f"panels: {name} ps1={HOME.getProperty('lucent.ps.1.id')!r} pc1={HOME.getProperty('lucent.pc.1.title')!r} panel={cond('Control.IsVisible(' + str(cid) + ')')} rows9100={cond('Control.IsVisible(9100)')} items={lab(f'Container({cid}).NumItems')}")
        shot(f"6{wanted.index((name, needle, cid))}-{name}-menu")
        xbmc.executebuiltin("Action(Right)")
        mon.waitForAbort(2)
        log(f"panels: {name} right focus={xbmc.getInfoLabel('System.CurrentControlId')} has={cond(f'Control.HasFocus({cid})')} label={lab(f'Container({cid}).ListItem.Label')!r}")
        shot(f"6{wanted.index((name, needle, cid))}-{name}-in")
        xbmc.executebuiltin("Action(Left)")
        mon.waitForAbort(1)
    # back to the start tab: its rows again
    xbmc.executebuiltin("Control.SetFocus(9000,0)")
    mon.waitForAbort(3)
    log(f"panels: back start rows9100={cond('Control.IsVisible(9100)')} panel={cond('Control.IsVisible(9310)')}")


def updater_test():
    """The update check reads the newest list (cache-busting address) and the new zip can be downloaded."""
    import sys as _sys
    _sys.path.insert(0, xbmcvfs.translatePath("special://skin/scripts"))
    import updater
    try:
        found = updater.fetch_available()
        log(f"upd: skin={found.get('skin.lucent', ('?',))[0]} library={found.get('script.lucent.library', ('?',))[0]}")
        ups = updater.available_updates()
        log(f"upd: updates={[(u['id'], u['have'], u['version']) for u in ups]}")
        skin = next((u for u in ups if u["id"] == "skin.lucent"), None)
        if skin:
            path = updater.download_zip(skin)
            log(f"upd: zip {os.path.getsize(path)} bytes")
    except Exception as error:  # noqa: BLE001
        log(f"upd: error {error!r}")


def readme_test():
    """Screenshots for the README: Home, side menu, the tab screens, the views, calendar, settings, keyboard."""
    import sys as _sys
    import datetime as _dt
    _sys.path.insert(0, xbmcvfs.translatePath("special://skin/scripts"))
    import menu
    import tabpanels
    import agenda_core
    FS = "plugin://plugin.video.fakeseren/?list="
    ART = "special://home/addons/plugin.video.fakeseren/art/"

    def w(label, kind, style):
        return {"label": label, "path": FS + kind, "style": style}
    home = [w("Continue watching · Shows", "se", "land"), w("Trending movies", "sm", "poster"), w("Popular shows", "ss", "poster")]
    tab = lambda label, icon, action, widgets=None: {"label": label, "icon": f"icons/{icon}.png", "action": action,  # noqa: E731
                                                     "widgets": widgets or [], "actionlabel": ""}
    m = menu.Menu()
    m.tabs = [tab("Search", "search", "ActivateWindow(Videos,plugin://plugin.video.fakeseren/?list=sm,return)"),
              tab("Home", "home", menu.SHOW_WIDGETS, home),
              tab("Movies", "movies", "ActivateWindow(Videos,plugin://plugin.video.fakeseren/?list=sm,return)", [w("Trending movies", "sm", "poster"), w("Continue watching · Shows", "se", "land")]),
              tab("Shows", "tv", "ActivateWindow(Videos,plugin://plugin.video.fakeseren/?list=ss,return)", [w("Popular shows", "ss", "poster")]),
              tab("Calendar", "calendar", "RunScript(special://skin/scripts/agenda.py)"),
              tab("TV", "tv", "RunScript(special://skin/scripts/tv.py)"),
              tab("Sport", "sport", "RunScript(special://skin/scripts/sport.py)"),
              tab("Add-ons", "addons", "ActivateWindow(AddonBrowser)"),
              tab("Settings", "settings", "ActivateWindow(Settings)"),
              tab("Power", "power", "ActivateWindow(ShutdownMenu)")]
    m.start = m.tabs[1]
    m.save()
    # calendar data
    data = xbmcvfs.translatePath("special://profile/addon_data/skin.lucent/")
    os.makedirs(data, exist_ok=True)
    today = _dt.date.today()
    names = [("Glasswork", 0, "21:00"), ("Red Harbour", 1, "20:00"), ("Lumen", 2, "22:00"), ("Night Ferry", 3, ""), ("Northbound", 5, ""), ("Copper Sky", 6, "")]
    evs = []
    for n, (name, days, at) in enumerate(names):
        evs.append({"kind": "tv" if n != 4 else "movie", "key": f"k{n}", "show": f"tv:{n}", "name": name, "title": f"Chapter {5 + n}" if n != 4 else "",
                    "season": 2, "episode": 7 + n, "date": (today + _dt.timedelta(days=days)).isoformat(), "time": at,
                    "still": f"{ART}f{n}.jpg", "backdrop": f"{ART}f{n}.jpg", "poster": f"{ART}p{n}.jpg", "network": ["HBO Max", "Netflix", "Apple TV+", "Disney+", "", "Prime Video"][n],
                    "plot": "A fictional placeholder synopsis used for this screenshot. The real text comes from TMDB.",
                    "tmdb": 100 + n, "logo": "", "digital": True, "rating": 8.1, "genre": "Drama", "runtime": 52})
    json.dump({"shows": {"tv:1": {"name": "x", "kind": "tv", "tmdb": 1, "notify": True}}, "synced": time.time()}, open(data + "agenda_follow.json", "w"))
    json.dump({"v": agenda_core.CACHE_VERSION, "shows": {"tv:1": {"events": evs, "fetched": time.time()}}}, open(data + "agenda_cache.json", "w"))
    rows = [("1", "Ajax", "PSV", "2", "1", "LIVE 67'", "1", "D2122E", "ED1C24", 0, 1), ("2", "Feyenoord", "AZ", "", "", "18:45", "", "E30613", "C8102E", 2, 3),
            ("3", "Real Madrid", "Barcelona", "", "", "21:00", "", "1C3C8C", "A50044", 4, 5)]

    def set_sport():
        for n, (i, hn, an, hs, as_, when, live, hc, ac, hl, al) in enumerate(rows, 1):
            for k, v in {"id": i, "hname": hn, "aname": an, "hs": hs, "as": as_, "when": when, "live": live, "hcol": hc, "acol": ac,
                         "hlogo": f"{ART}c{hl}.png", "alogo": f"{ART}c{al}.png", "league": "Eredivisie" if n < 3 else "LaLiga",
                         "kick": ("LIVE · EREDIVISIE · 67'" if live else f"{when} · {'EREDIVISIE' if n < 3 else 'LALIGA'}"),
                         "big": f"{hs} – {as_}" if hs else when}.items():
                HOME.setProperty(f"lucent.ps.{n}.{k}", v)
    xbmc.executebuiltin("ReloadSkin()")
    mon.waitForAbort(6)
    xbmc.executebuiltin("Dialog.Close(all,true)")
    xbmc.executebuiltin("ActivateWindow(home)")
    mon.waitForAbort(3)
    # Home
    xbmc.executebuiltin("Control.SetFocus(9000,1)")
    mon.waitForAbort(2)
    xbmc.executebuiltin("SetFocus(9100)")
    mon.waitForAbort(14)
    log(f"readme: home rows {lab('Container(8101).NumItems')} {lab('Container(8201).NumItems')} focus={lab('System.CurrentControlId')}")
    shot("r-home")
    xbmc.executebuiltin("Control.SetFocus(9000,2)")
    mon.waitForAbort(8)
    shot("r-sidebar")
    # the tab screens
    for idx, name, cid in ((4, "calendar", 9310), (6, "sport", 9330), (8, "settings", 9350), (9, "power", 9360), (7, "addons", 9340)):
        tabpanels.update()
        set_sport()
        xbmc.executebuiltin(f"Control.SetFocus(9000,{idx})")
        mon.waitForAbort(3)
        set_sport()
        xbmc.executebuiltin(f"SetFocus({cid})")
        mon.waitForAbort(3)
        log(f"readme: {name} focus={lab('System.CurrentControlId')} items={lab(f'Container({cid}).NumItems')}")
        shot(f"r-tab-{name}")
    # views (without the '..' item, focus on the second title)
    xbmc.executeJSONRPC(json.dumps({"jsonrpc": "2.0", "id": 1, "method": "Settings.SetSettingValue",
                                    "params": {"setting": "filelists.showparentdiritems", "value": False}}))
    xbmc.executebuiltin("ActivateWindow(Videos,plugin://plugin.video.fakeseren/?list=sm,return)")
    mon.waitForAbort(6)
    for view, name in ((51, "posters"), (52, "poster-wall"), (50, "list"), (57, "showcase")):
        xbmc.executebuiltin(f"Container.SetViewMode({view})")
        mon.waitForAbort(2)
        xbmc.executebuiltin(f"SetFocus({view},1)")
        mon.waitForAbort(4)
        log(f"readme: view {name} visible={cond(f'Control.IsVisible({view})')} items={lab('Container.NumItems')}")
        shot(f"r-view-{name}")
    xbmc.executebuiltin("Container.Update(plugin://plugin.video.fakeseren/?list=se,replace)")
    mon.waitForAbort(6)
    xbmc.executebuiltin("Container.SetViewMode(55)")
    mon.waitForAbort(2)
    xbmc.executebuiltin("SetFocus(55,0)")
    mon.waitForAbort(4)
    log(f"readme: episodes visible={cond('Control.IsVisible(55)')}")
    shot("r-view-episodes")
    xbmc.executebuiltin("ActivateWindow(home)")
    mon.waitForAbort(3)
    # calendar window
    xbmc.executebuiltin("RunScript(special://skin/scripts/agenda.py)")
    mon.waitForAbort(8)
    shot("r-calendar")
    xbmc.executebuiltin("Action(Back)")
    mon.waitForAbort(3)
    # settings, skin settings, keyboard
    xbmc.executebuiltin("ActivateWindow(Settings)")
    mon.waitForAbort(4)
    shot("r-settings")
    xbmc.executebuiltin("ActivateWindow(SkinSettings)")
    mon.waitForAbort(5)
    shot("r-skin-settings")
    xbmc.executebuiltin("ActivateWindow(home)")
    mon.waitForAbort(3)
    xbmc.executebuiltin("Skin.SetString(ci.keyboard)")
    mon.waitForAbort(4)
    shot("r-keyboard")
    xbmc.executebuiltin("Dialog.Close(all,true)")
    mon.waitForAbort(2)


def filebrowser_test():
    """Issue #3: an add-on asks for pictures (thumbnails view 451) or zip files: the files must be visible."""
    import threading
    folder = "special://home/addons/plugin.video.fakeseren/art/"
    for name, args in (("images", (2, "Choose a picture", "files", ".jpg|.png", True, False, folder)),
                       ("zips", (1, "Choose a backup", "files", ".zip", True, False, "special://temp/zips/"))):
        if name == "zips":
            os.makedirs(xbmcvfs.translatePath("special://temp/zips/"), exist_ok=True)
            for i in range(6):
                open(xbmcvfs.translatePath(f"special://temp/zips/build{i}.zip"), "wb").write(b"PK\x05\x06" + b"\x00" * 18)
        t = threading.Thread(target=lambda: xbmcgui.Dialog().browse(*args), daemon=True)
        t.start()
        for _ in range(15):
            mon.waitForAbort(1)
            if cond("Window.IsActive(filebrowser)"):
                break
        mon.waitForAbort(3)
        log(f"fb: {name} active={cond('Window.IsActive(filebrowser)')} list450={cond('Control.IsVisible(450)')} n450={lab('Container(450).NumItems')} "
            f"thumbs451={cond('Control.IsVisible(451)')} n451={lab('Container(451).NumItems')} focus={lab('System.CurrentControlId')}")
        shot(f"r-fb-{name}")
        xbmc.executebuiltin("Dialog.Close(filebrowser,true)")
        mon.waitForAbort(2)


def pvr_test():
    """Live TV with IPTV Simple: TV tab, TV guide, a channel playing with its OSD."""
    def rpc(method, params=None):
        return json.loads(xbmc.executeJSONRPC(json.dumps({"jsonrpc": "2.0", "id": 1, "method": method, "params": params or {}}))).get("result") or {}
    for _ in range(90):
        if cond("Pvr.HasTVChannels"):
            break
        mon.waitForAbort(1)
    chans = (rpc("PVR.GetChannels", {"channelgroupid": "alltv"}) or {}).get("channels") or []
    log(f"pvr: has={cond('Pvr.HasTVChannels')} channels={[c.get('label') for c in chans]}")
    if not chans:
        return
    mon.waitForAbort(8)                     # the guide is read a bit later
    bc = rpc("PVR.GetBroadcasts", {"channelid": chans[0]["channelid"], "properties": ["title", "starttime", "endtime"]}).get("broadcasts") or []
    log(f"pvr: broadcasts ch1={len(bc)} first={[b.get('title') for b in bc[:3]]}")
    # TV tab on Home
    import sys as _sys
    _sys.path.insert(0, xbmcvfs.translatePath("special://skin/scripts"))
    import menu
    import tabpanels
    m = menu.Menu()
    if not any("tv.py" in t["action"] for t in m.tabs):
        m.tabs.append({"label": "TV", "icon": "icons/tv.png", "action": "RunScript(special://skin/scripts/tv.py)",
                       "widgets": [{"label": "TV channels", "path": "pvr://channels/tv/", "style": "land"}], "actionlabel": ""})
        m.save()
    tabpanels.update()
    xbmc.executebuiltin("ActivateWindow(home)")
    mon.waitForAbort(3)
    m = menu.Menu()
    idx = next(i for i, t in enumerate(m.tabs) if "tv.py" in t["action"])
    xbmc.executebuiltin(f"Control.SetFocus(9000,{idx})")
    mon.waitForAbort(4)
    xbmc.executebuiltin("SetFocus(9320)")
    mon.waitForAbort(4)
    log(f"pvr: tvtab rows9100={cond('Control.IsVisible(9100)')} w1={lab('Container(9000).ListItem.Property(w1.path)')!r} path={HOME.getProperty('lucent.ptv.path')!r} items={lab('Container(9320).NumItems')} focus={lab('System.CurrentControlId')} "
        f"now={lab('Container(9320).ListItem.EpgEventTitle')!r}")
    shot("p-tvtab")
    # TV guide
    xbmc.executebuiltin("ActivateWindow(TVGuide)")
    mon.waitForAbort(8)
    shot("p-guide")
    xbmc.executebuiltin("ActivateWindow(home)")
    mon.waitForAbort(2)
    # play a channel and open the OSD
    rpc("Player.Open", {"item": {"channelid": chans[2]["channelid"]}})
    for _ in range(20):
        mon.waitForAbort(1)
        if cond("Pvr.IsPlayingTv"):
            break
    mon.waitForAbort(4)
    log(f"pvr: playing={cond('Pvr.IsPlayingTv')} title={lab('VideoPlayer.Title')!r} channel={lab('VideoPlayer.ChannelName')!r}")
    xbmc.executebuiltin("ActivateWindow(videoosd)")
    mon.waitForAbort(4)
    for _ in range(10):
        mon.waitForAbort(1)
        if HOME.getProperty("live.g.1.title"):
            break
    mon.waitForAbort(1)
    log(f"pvr: osd={cond('Window.IsActive(videoosd)')} focus={lab('System.CurrentControlId')} guide={[HOME.getProperty(f'live.g.{n}.title') for n in range(1, 7)]} "
        f"now1={HOME.getProperty('live.g.1.now')!r} up={HOME.getProperty('live.g.up')!r} down={HOME.getProperty('live.g.down')!r} items={lab('Container(460).NumItems')}")
    shot("p-osd")
    xbmc.executebuiltin("Action(Right)")
    mon.waitForAbort(1.5)
    log(f"pvr: right focus={lab('System.CurrentControlId')} item={lab('Container(460).ListItem.Label')!r} n={lab('Container(460).ListItem.Property(n)')!r}")
    shot("p-osd-next")
    xbmc.executebuiltin("Action(Select)")                  # remind me for the next programme
    mon.waitForAbort(2)
    try:
        rem = json.load(open(xbmcvfs.translatePath("special://profile/addon_data/skin.lucent/live_reminders.json")))
    except Exception as error:  # noqa: BLE001
        rem = repr(error)
    log(f"pvr: reminders={rem}")
    xbmc.executebuiltin("Action(Down)")
    mon.waitForAbort(1.5)
    log(f"pvr: down focus={lab('System.CurrentControlId')}")
    shot("p-osd-buttons")
    xbmc.executebuiltin("SetFocus(477)")
    mon.waitForAbort(1)
    xbmc.executebuiltin("Action(Select)")
    mon.waitForAbort(1.5)
    log(f"pvr: more focus={lab('System.CurrentControlId')} settings={cond('Skin.HasSetting(lucent.livesettings)')}")
    shot("p-osd-more")
    xbmc.executebuiltin("SetFocus(401)")
    xbmc.executebuiltin("Action(Select)")
    mon.waitForAbort(1.5)
    log(f"pvr: back focus={lab('System.CurrentControlId')} settings={cond('Skin.HasSetting(lucent.livesettings)')}")
    # clean channel logos (tv-logos) in the list Lucent writes for IPTV Simple
    xbmc.executebuiltin("Dialog.Close(all,true)")
    xbmc.executebuiltin("PlayerControl(Stop)")
    mon.waitForAbort(3)
    import channels
    import xtream
    cfg = channels.load()
    path = channels.pick_instance(cfg)
    ok = bool(path) and channels.remember_original(cfg, path)
    cfg["logos"] = True
    res = channels.build_file(cfg) if ok else None
    if res:
        channels.point_to_file(cfg)
        channels.save(cfg)

        class Busy:
            def update(self, *a):
                pass

            def iscanceled(self):
                return False
        state = xtream.restart_addon(Busy())
    else:
        state = "-"
    mon.waitForAbort(5)
    chans = (rpc("PVR.GetChannels", {"channelgroupid": "alltv", "properties": ["icon", "thumbnail"]}) or {}).get("channels") or []
    log(f"pvr: logos instance={bool(path)} built={res} restart={state} icons={[(c.get('label'), (c.get('icon') or c.get('thumbnail') or '')[-30:]) for c in chans]}")
    xbmc.executebuiltin("ActivateWindow(TVGuide)")
    mon.waitForAbort(8)
    shot("p-guide-logos")
    xbmc.executebuiltin("ActivateWindow(home)")
    mon.waitForAbort(2)
    xbmc.executebuiltin("Dialog.Close(all,true)")
    xbmc.executebuiltin("PlayerControl(Stop)")
    mon.waitForAbort(3)


def chanrows_test():
    """Game page channel rows: the first row readable when not focused, names without the provider's marks."""
    import sys as _sys
    _sys.path.insert(0, xbmcvfs.translatePath("special://skin/scripts"))
    import sport_core as sc
    names = ["┃NL┃ ZIGGO SPORT 2 ┃", "|NL| ZIGGO SPORT", "┃PT┃ SPORT TV 1", "[RO] DIGI SPORT 1", "NL: Ziggo Sport 2 FHD"]
    log(f"chan: clean={[(sc.display_channel(n), sc.channel_country(n)) for n in names]}")
    xbmc.executebuiltin("RunScript(special://skin/scripts/sport.py)")
    for _ in range(40):
        mon.waitForAbort(1)
        if [e for e in sc.all_cached() if e["kind"] == "teams"]:
            break
    xbmc.executebuiltin("Dialog.Close(all,true)")
    xbmc.executebuiltin("Action(Back)")
    mon.waitForAbort(2)
    try:
        pass
    except Exception as error:  # noqa: BLE001
        import traceback
        log(f"chan: refresh {error!r} {traceback.format_exc()[-600:]}")
    games = [e for e in sc.all_cached() if e["kind"] == "teams" and sc.LEAGUES.get(e["league"], {}).get("sport") == "soccer"]
    games.sort(key=lambda e: ({"in": 0, "post": 1, "pre": 2}[e["state"]], -e["start"] if e["state"] == "post" else e["start"]))
    if not games:
        # no games in the test: the game page on its own, with made-up properties
        import xbmcaddon
        win = xbmcgui.WindowXMLDialog("Lucent_SportGame.xml", xbmcaddon.Addon("skin.lucent").getAddonInfo("path"), "Default", "1080i")
        for k, v in {"layout": "teams", "hname": "Ajax", "aname": "AZ", "bigmid": "2 – 1", "topline": "Eredivisie", "remindtext": "Remind me",
                     "rectext": "Record", "t.watchcap": "WATCH ON YOUR CHANNELS"}.items():
            win.setProperty(f"g.{k}", v)
        rows = [("ZIGGO SPORT 2", "NL  ·  Live now  ·  Broadcasting  ·  4K"), ("ZIGGO SPORT", "NL  ·  Live now  ·  Broadcasting"),
                ("SPORT TV 1", "PT  ·  Broadcasting  ·  4K"), ("DIGI SPORT 1", "RO  ·  Live now  ·  Broadcasting")]
        for n, (name, sub) in enumerate(rows, 1):
            win.setProperty(f"g.ch{n}name", name)
            win.setProperty(f"g.ch{n}sub", sub)
        win.show()
        mon.waitForAbort(3)
        xbmc.executebuiltin("SetFocus(1311)")
        mon.waitForAbort(1.5)
        shot("c-rows-1")
        xbmc.executebuiltin("SetFocus(1313)")
        mon.waitForAbort(1.5)
        log(f"chan: page focus={lab('System.CurrentControlId')} vis1311={cond('Control.IsVisible(1311)')}")
        shot("c-rows-3")
        steps = []
        xbmc.executebuiltin("SetFocus(1332)")
        mon.waitForAbort(1)
        steps.append(lab("System.CurrentControlId"))
        for key in ("Up", "Up", "Up", "Up", "Down", "Down", "Down", "Down"):
            xbmc.executebuiltin(f"Action({key})")
            mon.waitForAbort(0.8)
            steps.append(f"{key}:{lab('System.CurrentControlId')}")
        log(f"chan: nav {steps}")
        win.close()
        del win
        return
    xbmc.executebuiltin(f"RunScript(special://skin/scripts/sport.py,game,{games[0]['id']})")
    for _ in range(30):
        mon.waitForAbort(1)
        if lab("Window.Property(g.layout)") == "teams":
            break
    mon.waitForAbort(3)
    win = xbmcgui.Window(xbmcgui.getCurrentWindowId())
    rows = [("ZIGGO SPORT 2", "NL  ·  Live now  ·  Broadcasting  ·  4K"), ("ZIGGO SPORT", "NL  ·  Live now  ·  Broadcasting"),
            ("SPORT TV 1", "PT  ·  Broadcasting  ·  4K"), ("DIGI SPORT 1", "RO  ·  Live now  ·  Broadcasting")]
    for n, (name, sub) in enumerate(rows, 1):
        win.setProperty(f"g.ch{n}name", name)
        win.setProperty(f"g.ch{n}sub", sub)
    if not win.getProperty("g.remindtext"):
        win.setProperty("g.remindtext", "Remind me")
    mon.waitForAbort(1)
    xbmc.executebuiltin("SetFocus(1311)")
    mon.waitForAbort(1.5)
    shot("c-rows-1")
    xbmc.executebuiltin("SetFocus(1313)")
    mon.waitForAbort(1.5)
    log(f"chan: focus={lab('System.CurrentControlId')} vis1311={cond('Control.IsVisible(1311)')} name1={lab('Window.Property(g.ch1name)')!r}")
    shot("c-rows-3")
    steps = []
    xbmc.executebuiltin("SetFocus(1332)")
    mon.waitForAbort(1)
    steps.append(lab("System.CurrentControlId"))
    for key in ("Up", "Up", "Up", "Up", "Down", "Down", "Down", "Down"):
        xbmc.executebuiltin(f"Action({key})")
        mon.waitForAbort(0.8)
        steps.append(f"{key}:{lab('System.CurrentControlId')}")
    log(f"chan: nav {steps}")
    xbmc.executebuiltin("Dialog.Close(all,true)")
    mon.waitForAbort(1)
    xbmc.executebuiltin("ActivateWindow(home)")
    mon.waitForAbort(2)


def sportosd_test():
    """The sport layer of the TV player (P1-P5) with a game made up in the window properties."""
    def rpc(method, params=None):
        return json.loads(xbmc.executeJSONRPC(json.dumps({"jsonrpc": "2.0", "id": 1, "method": method, "params": params or {}}))).get("result") or {}
    for _ in range(90):
        if cond("Pvr.HasTVChannels"):
            break
        mon.waitForAbort(1)
    chans = (rpc("PVR.GetChannels", {"channelgroupid": "alltv"}) or {}).get("channels") or []
    if not chans:
        log("sosd: no channels")
        return
    rpc("Player.Open", {"item": {"channelid": chans[2]["channelid"]}})
    for _ in range(20):
        mon.waitForAbort(1)
        if cond("Pvr.IsPlayingTv"):
            break
    mon.waitForAbort(26)                      # the helper's first round for this channel has run
    art = "special://home/addons/plugin.video.fakeseren/art/"
    base = {"on": "1", "h": "AJA", "a": "AZ", "hs": "2", "as": "1", "clock": "67'", "hname": "Ajax", "aname": "AZ", "hlogo": art + "c0.png", "alogo": art + "c4.png",
            "hcol": "FFD2122E", "acol": "FF1C3C8C", "sport": "soccer", "league": "Eredivisie", "id": "x", "title": "Ajax – AZ", "race": ""}
    det = {"hgoals": "12' Brobbey  ·  58' Taylor", "agoals": "44' Pavlidis"}
    for n, (l, h, a, k) in enumerate((("Possession", "58%", "42%", 6), ("Shots", "14", "7", 7), ("On target", "6", "3", 7), ("Corners", "5", "2", 7),
                                      ("Fouls", "9", "12", 4), ("Yellow cards", "1", "2", 3)), 1):
        det.update({f"st{n}l": l, f"st{n}h": h, f"st{n}a": a, f"st{n}k": str(k)})
    for n, (m, t, x) in enumerate((("58'", "AJA", "Taylor"), ("44'", "AZ", "Pavlidis"), ("12'", "AJA", "Brobbey")), 1):
        det.update({f"sc{n}m": m, f"sc{n}t": t, f"sc{n}x": x})
    for n, (m, k, x) in enumerate((("58'", "goal", "Goal Taylor (Ajax)"), ("51'", "yellow", "Yellow card Mijnans (AZ)"), ("44'", "goal", "Goal Pavlidis (AZ)"),
                                   ("12'", "goal", "Goal Brobbey (Ajax)")), 1):
        det.update({f"tl{n}m": m, f"tl{n}k": k, f"tl{n}x": x})
    tab = {}
    for n, (r, t, gp, gd, pts, mine) in enumerate(((1, "PSV", 12, "+24", 31, ""), (2, "Ajax", 12, "+15", 27, "1"), (3, "AZ", 12, "+10", 24, "1"), (4, "Feyenoord", 12, "+9", 22, "")), 1):
        tab.update({f"{n}rank": str(r), f"{n}team": t, f"{n}gp": str(gp), f"{n}gd": gd, f"{n}pts": str(pts), f"{n}mine": mine})

    def put(prefix, d):
        for k, v in d.items():
            HOME.setProperty(prefix + k, v)
    put("live.sc.", base)
    put("live.d.", det)
    put("live.t.", tab)
    mon.waitForAbort(2)
    log(f"sosd: vis9700={cond('Control.IsVisible(9700)')} ")
    log(f"sosd: board win={lab('System.CurrentWindow')!r} full={cond('Window.IsActive(fullscreenvideo)')} cond={cond('Pvr.IsPlayingTV + !String.IsEmpty(Window(Home).Property(live.sc.on)) + String.IsEmpty(Window(Home).Property(live.sc.race))')} on={HOME.getProperty('live.sc.on')!r}")
    shot("s-board")
    xbmc.executebuiltin("ActivateWindow(videoosd)")
    mon.waitForAbort(3)
    put("live.sc.", base)
    log(f"sosd: osd focus={lab('System.CurrentControlId')} vis480={cond('Control.IsVisible(480)')} vis460={cond('Control.IsVisible(460)')}")
    xbmc.Player().showSubtitles(False)
    mon.waitForAbort(1)
    shot("s-osd-soccer")
    xbmc.executebuiltin("SetFocus(482)")
    mon.waitForAbort(0.5)
    xbmc.executebuiltin("Action(Select)")          # Statistics -> the panel
    mon.waitForAbort(4)
    log(f"sosd: panel dialog={lab('System.CurrentWindow')!r} focus={lab('System.CurrentControlId')} tab={HOME.getProperty('live.p.tab')!r}")
    shot("s-panel-stats")
    xbmc.executebuiltin("Action(Right)")
    mon.waitForAbort(1.5)
    shot("s-panel-timeline")
    xbmc.executebuiltin("Action(Right)")
    mon.waitForAbort(1.5)
    log(f"sosd: tab={HOME.getProperty('live.p.tab')!r} focus={lab('System.CurrentControlId')}")
    shot("s-panel-table")
    xbmc.executebuiltin("Action(Back)")
    mon.waitForAbort(2)
    # Also live
    xbmc.executebuiltin("RunScript(special://skin/scripts/sportlive.py,also)")
    mon.waitForAbort(3)
    for n, (lg, cl, hn, an, hs, as_, ch, hc, ac) in enumerate((("NBA", "Q4 7:49", "Magic", "Celtics", "83", "87", "ESPN 1", "0077C0", "007A33"),
                                                                ("Serie A", "58'", "Milan", "Inter", "3", "1", "Ziggo Sport 2", "FB090B", "010E80"),
                                                                ("Premier League", "72'", "Arsenal", "Chelsea", "1", "1", "ESPN 2", "EF0107", "034694")), 1):
        put(f"live.a.{n}.", {"hname": hn, "aname": an, "hs": hs, "as": as_, "league": lg, "clock": cl, "chan": ch, "cid": "1", "hcol": hc, "acol": ac,
                             "chicon": art + f"c{n}.png"})
    mon.waitForAbort(2)
    xbmc.executebuiltin("SetFocus(300)")
    mon.waitForAbort(1)
    log(f"sosd: also items={lab('Container(300).NumItems')} focus={lab('System.CurrentControlId')}")
    shot("s-also")
    xbmc.executebuiltin("Action(Back)")
    mon.waitForAbort(2)
    # basketball
    put("live.sc.", {"sport": "basketball", "h": "ORL", "a": "BOS", "hs": "83", "as": "87", "clock": "Q4 · 7:49", "title": "Magic – Celtics", "league": "NBA",
                     "hcol": "FF0077C0", "acol": "FF007A33"})
    put("live.d.", {"qn": "4", "qh1": "24", "qh2": "22", "qh3": "25", "qh4": "12", "qa1": "20", "qa2": "27", "qa3": "22", "qa4": "18",
                    "tp1n": "Banchero", "tp1v": "28 · 9 · 4", "tp2n": "Tatum", "tp2v": "31 · 8 · 5", "tp3n": "Wagner", "tp3v": "19 · 3 · 6"})
    xbmc.executebuiltin("ActivateWindow(videoosd)")
    mon.waitForAbort(3)
    log(f"sosd: basket focus={lab('System.CurrentControlId')}")
    shot("s-osd-basket")
    xbmc.executebuiltin("Dialog.Close(all,true)")
    xbmc.executebuiltin("PlayerControl(Stop)")
    mon.waitForAbort(2)


def serentheme_test():
    """README screenshots of the Lucent theme for Seren: the real theme XML in this Kodi, filled the way Seren fills it."""
    PATH = "/tmp/ci/serentheme"
    ART = "special://home/addons/plugin.video.fakeseren/art/"
    ep = {"item.info.tvshowtitle": "Northbound", "item.info.title": "The Long Crossing", "item.info.season": "2", "item.info.episode": "7",
          "item.info.year": "2025", "item.info.rating": "8.4", "item.info.mpaa": "TV-14", "item.info.aired": "12 March 2025",
          "item.info.duration.hours": "0", "item.info.duration.minutes": "52", "item.info.rottentomatoes_rating": "94%", "item.info.metacritic_rating": "81",
          "item.info.plot": "A storm closes the northern pass, and the crew must choose between waiting it out and a dangerous shortcut over the ice. "
                            "Placeholder text for this screenshot: in Kodi you see the real plot from TMDB.",
          "item.art.fanart": ART + "f3.jpg", "item.art.thumb": ART + "f5.jpg", "seren.fanart": ART + "f3.jpg"}

    class W(xbmcgui.WindowXMLDialog):
        def __init__(self, *a, **k):
            super().__init__(*a)
            self.fill = k.get("fill")
            self.focus = k.get("focus")

        def onInit(self):
            if self.fill:
                self.fill(self)
            if self.focus:
                self.setFocusId(self.focus)

    def show(xml, name, props, fill=None, focus=None, wait=4):
        w = W(xml, PATH, "Default", "1080i", fill=fill, focus=focus)
        for k, v in props.items():
            w.setProperty(k, v)
        w.show()
        mon.waitForAbort(wait)
        log(f"theme {name}: dialog={lab('System.CurrentWindow')} focus={lab('System.CurrentControlId')}")
        shot(f"theme-{name}")
        w.close()
        mon.waitForAbort(1)
        del w

    # 1 source select (episode, the first stream = Recommended)
    streams = [
        ("4K", "Northbound.S02E07.2160p.WEB-DL.DV.HDR.DDP5.1.Atmos.H265", "TORRENTIO", "REAL-DEBRID", "TORRENT", "18.4 GB", "CACHED", "DUAL-AUDIO", ("DV", "HDR", "HEVC", "WEB", "ATMOS", "DD+", "5.1")),
        ("4K", "Northbound.S02E07.2160p.UHD.BluRay.REMUX.HDR.TrueHD.7.1", "COMET", "REAL-DEBRID", "TORRENT", "41.2 GB", "CACHED", "", ("", "HDR", "HEVC", "REMUX", "TRUEHD", "", "7.1")),
        ("1080p", "Northbound.S02E07.1080p.WEB-DL.DDP5.1.H264", "MEDIAFUSION", "PREMIUMIZE", "CLOUD", "3.1 GB", "", "MULTI-SUB", ("", "", "AVC", "WEB", "DD+", "", "5.1")),
        ("1080p", "Northbound.S02E07.1080p.BluRay.x264.DTS", "TORRENTIO", "REAL-DEBRID", "TORRENT", "6.8 GB", "CACHED", "", ("", "", "AVC", "BLURAY", "DTS", "", "5.1")),
        ("720p", "Northbound.S02E07.720p.HDTV.x264.AAC", "TORRENTIO", "REAL-DEBRID", "TORRENT", "1.2 GB", "", "", ("", "", "AVC", "HDTV", "AAC", "", "2.0")),
        ("SD", "Northbound.S02E07.HDTV.x264", "TORRENTIO", "REAL-DEBRID", "TORRENT", "380 MB", "", "", ("", "", "AVC", "HDTV", "AAC", "", "2.0"))]

    def fill_sources(w):
        lst = w.getControl(1000)
        for q, title, prov, deb, typ, size, cached, lang, (hdr1, hdr2, vc, misc, ac1, ac2, ch) in streams:
            li = xbmcgui.ListItem(label=title)
            d = {"quality": q, "release_title": title, "provider": prov, "debrid_provider": deb, "type": typ, "size": size,
                 "info.sourcetype_text": cached, "aio_lang": lang, "info.hdrcodec_1": hdr1 or hdr2, "info.hdrcodec_2": hdr2 if hdr1 else "",
                 "info.videocodec_1": vc, "info.misc_1": misc, "info.audiocodec_1": ac1, "info.audiocodec_2": ac2, "info.audiochannels_1": ch}
            for k, v in d.items():
                if v:
                    li.setProperty(k, v)
            lst.addItem(li)
        w.setFocusId(1000)
    show("source_select.xml", "source-select", dict(ep, instant_close="false", resolving="false", **{"filter.label": "Filter results"}), fill_sources)

    # 2 scraping
    def fill_scrape(w):
        lst = w.getControl(2000)
        for p in ("Comet", "MediaFusion", "Jackettio"):
            lst.addItem(xbmcgui.ListItem(label=p))
    show("get_sources.xml", "scraping", dict(ep, process_started="true", progress="62", remaining_providers_count="3", notification_text="",
                                              totals_4K="7", totals_1080p="23", totals_720p="11", totals_SD="4", totals_total="45",
                                              torrents_total="38", torrentsCached_total="21", hosters_total="0", cloudFiles_total="2",
                                              directSources_total="0", adaptiveSources_total="0", has_torrent_providers="true",
                                              has_cloud_scrapers="true", has_hoster_providers="false", has_direct_providers="false",
                                              has_adaptive_providers="false"), fill_scrape, wait=5)

    # 3 filters
    groups = {1000: ["AV1", "AVC", "DIVX", "HEVC", "MP4", "MPEG", "VP9", "WMV", "XVID"], 2000: ["DV", "HDR", "HYBRID"],
              3000: ["AAC", "ATMOS", "DD", "DD+", "DTS", "DTS-HD", "DTS-HDHR", "DTS-HDMA", "DTS-X", "MP3", "OPUS", "TRUEHD", "WMA"],
              4000: ["2.0", "5.1", "7.1"], 5000: ["3D", "BLURAY", "CAM", "DVDRIP", "HC", "HD-RIP", "HDTV", "PDTV", "REMUX", "SCR", "WEB"]}
    on = {"XVID", "DIVX", "WMV", "CAM", "SCR", "HC", "3D", "MP3"}

    def fill_filters(w):
        for cid, names in groups.items():
            lst = w.getControl(cid)
            for n in names:
                li = xbmcgui.ListItem(label=n)
                li.setProperty("label", n)
                li.setProperty("value", str(n in on))
                lst.addItem(li)
        w.setFocusId(5000)
    show("filter_select.xml", "filters", {"seren.fanart": ART + "f1.jpg"}, fill_filters)

    # 4 sorting
    sp = {"seren.fanart": ART + "f2.jpg", "max_level": "5"}
    rows = [("Resolution",), ("Source Type", "Cloud", "Torrents", "Hosters"), ("Debrid Provider", "Real-Debrid", "Premiumize"),
            ("DV/HDR", "DV", "HDR"), ("Size",), ("None",)]
    for lvl, row in enumerate(rows, 1):
        for i, t in enumerate(row):
            sp[f"general.sortmethod.{lvl}.label.{i}"] = t
        sp[f"general.sortmethod.{lvl}.label.{len(row) - 1}.last"] = "True"
        sp[f"general.sortmethod.{lvl}.reverse"] = "True" if lvl == 5 else "False"
    show("sort_select.xml", "sorting", sp, focus=2002)

    # 5 provider packages
    def fill_packs(w):
        lst = w.getControl(1000)
        for n, (name, ver, author, services) in enumerate([("aiostreams", "1.1.0", "djdirty60", "torrent · cloud"),
                                                           ("torrentio", "2.4.1", "community", "torrent"),
                                                           ("mediafusion", "1.3.0", "community", "torrent · hosters")]):
            li = xbmcgui.ListItem(label=name)
            for k, v in {"pack_name": name, "version": ver, "author": author, "services": services, "package.icon": f"{ART}c{n}.png"}.items():
                li.setProperty(k, v)
            lst.addItem(li)
        w.setFocusId(1000)
    show("provider_packages.xml", "provider-packages", {"seren.fanart": ART + "f4.jpg"}, fill_packs)

    # 6 provider settings
    def fill_pack(w):
        st = w.getControl(1000)
        for label, typ, value, action in [("Manifest URL", "string", "*******", False), ("Timeout (seconds)", "int", "20", False),
                                          ("Only cached results", "bool", "True", False), ("Show IMAX / FEL tags", "bool", "True", False),
                                          ("Include adult", "bool", "False", False), ("Test connection", "action", "", True)]:
            li = xbmcgui.ListItem(label=label)
            for k, v in {"label": label, "type": typ, "value": value, "has_action": str(action), "hide_value": "False"}.items():
                li.setProperty(k, v)
            st.addItem(li)
        pr = w.getControl(2000)
        for n, (name, typ, status) in enumerate([("Torrentio", "torrent", "enabled"), ("Comet", "torrent", "enabled"), ("MediaFusion", "torrent", "enabled"),
                                                 ("Jackettio", "torrent", "disabled"), ("Easynews", "hosters", "enabled"), ("Debrid cloud", "hosters", "disabled")]):
            li = xbmcgui.ListItem(label=name)
            for k, v in {"provider_name": name, "provider_type": typ, "status": status, "package": "aiostreams", "provider.icon": f"{ART}c{n % 6}.png"}.items():
                li.setProperty(k, v)
            pr.addItem(li)
        w.setFocusId(2000)
    show("configure_provider_package.xml", "provider-settings", {"seren.fanart": ART + "f4.jpg", "package.name": "aiostreams", "hassettings": "true"}, fill_pack)

    # 7 + 8 over a playing video: Playing next, Skip intro
    xbmc.executebuiltin("Skin.Reset(nuvio.autosubs)")      # no subtitle list popping up
    xbmc.Player().play("/tmp/ci/test.mkv")
    for _ in range(20):
        if cond("Player.HasVideo"):
            break
        mon.waitForAbort(1)
    mon.waitForAbort(6)
    for _ in range(6):
        if not cond("System.HasVisibleModalDialog"):
            break
        xbmc.executebuiltin("Dialog.Close(all,true)")
        xbmc.executebuiltin("Action(Back)")
        mon.waitForAbort(1.5)
    log(f"theme video: dialog={cond('System.HasVisibleModalDialog')} window={lab('System.CurrentWindow')}")
    nxt = dict(ep, **{"item.info.title": "Thin Ice", "item.info.episode": "8", "item.info.duration.minutes": "49", "item.art.thumb": ART + "f7.jpg",
                      "item.info.plot": "With the pass behind them, the crew reaches the old weather station and finds it is not as empty as it looked."})
    show("playing_next.xml", "playing-next", nxt, focus=3001, wait=5)
    show("skip_intro.xml", "skip-intro", {}, focus=3001, wait=3)
    xbmc.Player().stop()
    mon.waitForAbort(2)


def pinfo_test():
    """Speler-info (example 3) over a playing video."""
    xbmc.executebuiltin("Skin.Reset(nuvio.autosubs)")
    rpcs = json.loads(xbmc.executeJSONRPC(json.dumps({"jsonrpc": "2.0", "id": 1, "method": "Settings.GetSettingValue", "params": {"setting": "videolibrary.flattentvshows"}})))
    log(f"pinfo: flattentvshows={rpcs.get('result')} mark={lab('Skin.String(lucent.flattenset)')}")
    xbmc.Player().play("/tmp/ci/audio.mkv")
    for _ in range(20):
        if cond("Player.HasVideo"):
            break
        mon.waitForAbort(1)
    mon.waitForAbort(5)
    for _ in range(6):
        if not cond("System.HasVisibleModalDialog"):
            break
        xbmc.executebuiltin("Dialog.Close(all,true)")
        mon.waitForAbort(1.5)
    xbmc.executebuiltin("Skin.SetBool(nuvio.osdstats)")
    xbmc.executebuiltin("ActivateWindow(videoosd)")
    mon.waitForAbort(6)
    keys = ["title", "time", "b.res", "b.vc", "b.ac", "b.ch", "b.sub", "t1.big", "t1.sub", "t3.big", "t4.big", "t4.sub", "spark", "t5.big", "t5.bar",
            "t6.big", "t6.sub", "r.file", "r.loc", "r.cont", "r.rate", "r.res", "r.hdr", "r.fmt", "r.vdec", "r.disp", "r.vq", "r.atrack",
            "r.afmt", "r.aq", "r.adec", "r.sub", "r.buf", "r.type", "cores", "cores.label", "core0", "m.ct", "m.mem", "m.clk", "m.fps", "m.vq"]
    log("pinfo: " + json.dumps({k: HOME.getProperty("lucent.pi." + k) for k in keys}, ensure_ascii=False))
    shot("pinfo-1")
    mon.waitForAbort(3)
    shot("pinfo-2")
    xbmc.executebuiltin("Dialog.Close(videoosd,true)")
    xbmc.executebuiltin("Skin.Reset(nuvio.osdstats)")
    xbmc.Player().stop()
    mon.waitForAbort(3)


def svc_test():
    """Streaming service pop-up (example A)."""
    xbmc.executebuiltin("RunScript(special://skin/scripts/service.py,8,Netflix,)")
    mon.waitForAbort(8)
    log(f"svc: window={lab('System.CurrentWindow')} focus={lab('System.CurrentControlId')} items={lab('Container(801).NumItems')} "
        f"label={lab('Container(801).ListItem.Label')!r} row={lab('Window.Property(svc.rowlabel)')!r}")
    shot("svc-1")
    xbmc.executebuiltin("Action(Right)")
    mon.waitForAbort(1)
    xbmc.executebuiltin("Action(Right)")
    mon.waitForAbort(2)
    shot("svc-2")
    steps = []
    xbmc.executebuiltin("Action(Up)")
    mon.waitForAbort(1.2)
    shot("svc-btn")
    xbmc.executebuiltin("Action(Down)")
    mon.waitForAbort(1)
    for key in ("Up", "Up", "Right", "Right", "Right", "Select", "Left", "Left", "Right"):
        xbmc.executebuiltin(f"Action({key})")
        mon.waitForAbort(1.2)
        steps.append(f"{key}:{lab('System.CurrentControlId')}")
    mon.waitForAbort(5)
    steps.append(f"cat={lab('Window.Property(svc.cat)')} kind={lab('Window.Property(svc.kind)')} row={lab('Window.Property(svc.rowlabel)')} items={lab('Container(801).NumItems')}")
    log(f"svc: nav {steps}")
    shot("svc-3")
    xbmc.executebuiltin("SetFocus(713)")
    mon.waitForAbort(1)
    xbmc.executebuiltin("Action(Select)")
    mon.waitForAbort(5)
    log(f"svc: top cat={lab('Window.Property(svc.cat)')} items={lab('Container(801).NumItems')}")
    xbmc.executebuiltin("SetFocus(801)")
    mon.waitForAbort(1.5)
    shot("svc-top")
    for key in ("Down", "Down"):
        xbmc.executebuiltin(f"Action({key})")
        mon.waitForAbort(1)
    log(f"svc: back down focus={lab('System.CurrentControlId')}")
    xbmc.executebuiltin("Action(Back)")
    mon.waitForAbort(2)


def sportnav_test():
    """All games: from the list to the scrollbar, the channels and back; stadium photos for awkward names."""
    import sys as _sys
    _sys.path.insert(0, xbmcvfs.translatePath("special://skin/scripts"))
    import sport_core as sc
    for name, sport, venue, short in [("Bodø/Glimt", "soccer", "Aspmyra Stadion", "Bodø/Glimt"), ("Shakhtar Donetsk", "soccer", "Arena Lviv", "Shakhtar"),
                                      ("Galatasaray", "soccer", "", ""), ("Atlético Madrid", "soccer", "", "Atlético"), ("FC Twente", "soccer", "", "Twente"),
                                      ("Union St.-Gilloise", "soccer", "Stade Joseph Marien", "Union SG")]:
        try:
            img, st = sc.stadium_photo(name, sport, venue, short)
        except Exception as error:  # noqa: BLE001
            img, st = repr(error), ""
        log(f"stadium: {name!r} -> {st!r} {img[:90]!r}")
        mon.waitForAbort(4)
    xbmc.executebuiltin("RunScript(special://skin/scripts/sport.py)")
    for _ in range(40):
        mon.waitForAbort(1)
        if lab("Window.Property(sport.loading)") == "" and int(lab("Container(200).NumItems") or 0) > 0:
            break
    mon.waitForAbort(3)
    win = xbmcgui.Window(xbmcgui.getCurrentWindowDialogId() if cond("System.HasVisibleModalDialog") else xbmcgui.getCurrentWindowId())
    try:
        item = win.getControl(200).getSelectedItem()
        if item is not None and not item.getProperty("ch1name"):
            for n, (name, sub) in enumerate([("ZIGGO SPORT", "NL · Live"), ("ESPN 1", "NL"), ("VIAPLAY 1", "NL")], 1):
                item.setProperty(f"ch{n}name", name)
                item.setProperty(f"ch{n}sub", sub)
        log(f"sportnav: faked channels on {item.getLabel() if item else None!r}")
    except Exception as error:  # noqa: BLE001
        log(f"sportnav: cannot fake channels {error!r}")
    xbmc.executebuiltin("SetFocus(200)")
    mon.waitForAbort(1.5)
    steps = [lab("System.CurrentControlId")]
    for key in ("Right", "Right", "Down", "Down", "Down", "Up", "Up", "Up", "Left", "Left"):
        xbmc.executebuiltin(f"Action({key})")
        mon.waitForAbort(0.8)
        steps.append(f"{key}:{lab('System.CurrentControlId')}")
        if key == "Down" and len(steps) == 4:
            shot("sportnav-ch")
    log(f"sportnav: nav {steps} ch1={lab('Container(200).ListItem.Property(ch1name)')!r}")
    shot("sportnav-end")
    xbmc.executebuiltin("Dialog.Close(all,true)")
    xbmc.executebuiltin("ActivateWindow(home)")
    mon.waitForAbort(2)


def libfix_test():
    """Library: series hidden until their first episode aired; TMDb pictures helper."""
    import sys as _sys
    _sys.path.insert(0, xbmcvfs.translatePath("special://home/addons/script.lucent.library"))
    import tmdbwidgets as tw
    xbmc.executebuiltin("Skin.SetBool(lucent.hide.undigital)")
    mon.waitForAbort(1)
    rows = [{"type": "tvshow", "file": "plugin://plugin.video.seren/?action=showSeasons", "premiered": "2026-12-25", "label": "future"},
            {"type": "tvshow", "file": "plugin://plugin.video.seren/?action=showSeasons", "premiered": "2020-01-01", "label": "aired"},
            {"type": "tvshow", "file": "videodb://tvshows/titles/5/", "premiered": "2030-01-01", "label": "library"},
            {"type": "tvshow", "file": "plugin://plugin.video.seren/?x", "premiered": "", "label": "nodate"}]
    kept = [r["label"] for r in tw.filter_undigital(rows)]
    log(f"libfix: kept={kept}")
    xbmc.executebuiltin("Skin.Reset(lucent.hide.undigital)")
    try:
        import tmdbart
        res = tmdbart.show(1001)
        log(f"libfix: tmdbart keys={sorted(res)} art={sorted((res.get('art') or {}))}")
        sh = {"tmdb_id": 1002, "art": {}, "cast": [], "season_art": {}}
        log(f"libfix: fill_show={tmdbart.fill_show(sh)} poster={(sh.get('art') or {}).get('poster','')[:60]!r}")
        import lib
        log(f"libfix: refresh_artless tv={lib.refresh_artless('tv')} movies={lib.refresh_artless('movies')}")
    except Exception as error:  # noqa: BLE001
        import traceback
        log(f"libfix: error {error!r} {traceback.format_exc()[-500:]}")


def stats_test():
    xbmc.Player().play("/tmp/ci/test.mkv")
    for _ in range(20):
        if cond("Player.HasVideo"):
            break
        mon.waitForAbort(1)
    mon.waitForAbort(4)
    xbmc.executebuiltin("Skin.SetBool(nuvio.osdstats)")
    mon.waitForAbort(1)
    before = cond("Skin.HasSetting(nuvio.osdstats)")
    xbmc.executebuiltin("ActivateWindow(home)")
    mon.waitForAbort(3)
    log(f"stats: before={before} after_leaving={cond('Skin.HasSetting(nuvio.osdstats)')} window={lab('System.CurrentWindow')}")
    xbmc.Player().stop()
    mon.waitForAbort(2)

def pinfo2_test():
    """Speler-info as its own window with three tabs."""
    xbmc.executebuiltin("Skin.Reset(nuvio.autosubs)")
    xbmc.Player().play("/tmp/ci/audio.mkv")
    for _ in range(20):
        if cond("Player.HasVideo"):
            break
        mon.waitForAbort(1)
    mon.waitForAbort(5)
    for _ in range(6):
        if not cond("System.HasVisibleModalDialog"):
            break
        xbmc.executebuiltin("Dialog.Close(all,true)")
        mon.waitForAbort(1.5)
    xbmc.executebuiltin("ActivateWindow(videoosd)")
    mon.waitForAbort(2)
    xbmc.executebuiltin("RunScript(special://skin/scripts/playerinfo.py,open)")
    mon.waitForAbort(6)
    log(f"pinfo2: open={HOME.getProperty('lucent.pi.open')} tab={HOME.getProperty('lucent.pi.tab')} focus={lab('System.CurrentControlId')} "
        f"dialog={lab('System.CurrentWindow')} osd={cond('Window.IsVisible(videoosd)')}")
    shot("pi2-1")
    keys = ["a.c1", "a.c2", "a.c3", "a.c4", "a.c5", "a.h1", "a.hs", "a.dev", "a.cfg", "a.vol", "a.chlabel", "a.t1.lang", "a.t1.codec", "a.t1.on",
            "a.t2.lang", "sp.c", "sp.l", "v.resbox", "v.reslabel", "v.dar", "v.hdrbar", "v.c1", "v.p1", "v.p2", "v.p3", "v.p4", "v.p4s", "v.br"]
    log("pinfo2: " + json.dumps({k: HOME.getProperty("lucent.pi." + k) for k in keys}, ensure_ascii=False))
    xbmc.executebuiltin("Action(Right)")
    mon.waitForAbort(2.5)
    log(f"pinfo2: after right tab={HOME.getProperty('lucent.pi.tab')} focus={lab('System.CurrentControlId')} time={lab('Player.Time')}")
    shot("pi2-2")
    try:
        xbmc.Player().setAudioStream(2)                 # the 5.1 track: more meters on the audio tab
    except Exception as error:  # noqa: BLE001
        log(f"pinfo2: audio stream {error}")
    mon.waitForAbort(2)
    xbmc.executebuiltin("Action(Right)")
    mon.waitForAbort(2.5)
    log(f"pinfo2: after right tab={HOME.getProperty('lucent.pi.tab')} focus={lab('System.CurrentControlId')}")
    shot("pi2-3")
    mon.waitForAbort(1.2)
    shot("pi2-3b")
    xbmc.executebuiltin("Action(Back)")
    mon.waitForAbort(2)
    log(f"pinfo2: after back open={HOME.getProperty('lucent.pi.open')!r} dialog={cond('System.HasVisibleModalDialog')} playing={cond('Player.HasVideo')}")
    xbmc.Player().stop()
    mon.waitForAbort(2)

def settiles_test():
    """Settings tab: four columns with 'Wat is er nieuw' and 'Op updates zoeken'."""
    import sys as _sys
    _sys.path.insert(0, xbmcvfs.translatePath("special://skin/scripts"))
    import menu
    import tabpanels
    m = menu.Menu()
    action = "ActivateWindow(Settings)"
    if not any(t["action"] == action for t in m.tabs) and len(m.tabs) < menu.NTABS:
        m.tabs.append({"label": "Settings", "icon": "icons/tv.png", "action": action, "widgets": [], "actionlabel": ""})
    m.save()
    tabpanels.update()
    xbmc.executebuiltin("ActivateWindow(home)")
    mon.waitForAbort(3)
    count = int(lab("Container(9000).NumItems") or 0)
    idx = None
    for i in range(count):
        xbmc.executebuiltin(f"Control.SetFocus(9000,{i})")
        mon.waitForAbort(0.4)
        if "ActivateWindow(Settings)" in lab("Container(9000).ListItem.Property(act)"):
            idx = i
            break
    log(f"settiles: tab index={idx}")
    if idx is None:
        return
    mon.waitForAbort(2)
    n = int(lab("Container(9350).NumItems") or 0)
    labels = [lab(f"Container(9350).ListItemAbsolute({i}).Label") for i in range(n)]
    log(f"settiles: items={n} labels={labels} visible={cond('Control.IsVisible(9350)')}")
    shot("settiles-1")
    xbmc.executebuiltin("Action(Right)")
    mon.waitForAbort(1.5)
    moves = []
    for key in ("Right", "Right", "Right", "Down", "Left"):
        xbmc.executebuiltin(f"Action({key})")
        mon.waitForAbort(1)
        moves.append(f"{key}:{lab('Container(9350).CurrentItem')}:{lab('Container(9350).ListItem.Label')}")
    log(f"settiles: moves {moves}")
    shot("settiles-2")
    xbmc.executebuiltin("Action(Left)")
    xbmc.executebuiltin("Action(Left)")
    xbmc.executebuiltin("Action(Left)")
    mon.waitForAbort(1)
    xbmc.executebuiltin("Control.SetFocus(9000,0)")
    mon.waitForAbort(2)


def svcreset_test():
    """Switching a list in the streaming pop-up starts it at the first title again."""
    xbmc.executebuiltin("RunScript(special://skin/scripts/service.py,8,Netflix,)")
    mon.waitForAbort(8)
    xbmc.executebuiltin("SetFocus(801)")
    mon.waitForAbort(1)
    for _ in range(4):
        xbmc.executebuiltin("Action(Right)")
        mon.waitForAbort(0.8)
    log(f"svcreset: before cat={lab('Window.Property(svc.cat)')} item={lab('Container(801).CurrentItem')} items={lab('Container(801).NumItems')}")
    for pill in ("702", "713", "701"):
        xbmc.executebuiltin(f"SetFocus({pill})")
        mon.waitForAbort(1)
        xbmc.executebuiltin("Action(Select)")
        mon.waitForAbort(5)
        log(f"svcreset: pill {pill} cat={lab('Window.Property(svc.cat)')} item={lab('Container(801).CurrentItem')} items={lab('Container(801).NumItems')}")
        xbmc.executebuiltin("SetFocus(801)")
        mon.waitForAbort(1)
        for _ in range(3):
            xbmc.executebuiltin("Action(Right)")
            mon.waitForAbort(0.8)
        log(f"svcreset: scrolled item={lab('Container(801).CurrentItem')}")
    shot("svcreset")
    xbmc.executebuiltin("Action(Back)")
    mon.waitForAbort(2)


def liblists_test():
    """Skin settings > Integrations > Lucent Library: the new 'Use my lists as library' row."""
    xbmc.executebuiltin("Skin.SetBool(lucent.ss.open.2505)")
    xbmc.executebuiltin("ActivateWindow(SkinSettings)")
    mon.waitForAbort(2)
    n = int(lab("Container(9000).NumItems") or 0)
    labels = [lab(f"Container(9000).ListItemAbsolute({i}).Label") for i in range(n)]
    log(f"liblists: cats {labels}")
    if "Integrations" not in labels:
        return
    xbmc.executebuiltin(f"SetFocus(9000,{labels.index('Integrations')},absolute)")
    mon.waitForAbort(1)
    xbmc.executebuiltin("Action(Right)")
    mon.waitForAbort(0.5)
    xbmc.executebuiltin("SetFocus(1523)")
    mon.waitForAbort(0.5)
    xbmc.executebuiltin("Action(Down)")
    mon.waitForAbort(0.8)
    log(f"liblists: down from surprise focus={lab('System.CurrentControlId')} vis={cond('Control.IsVisible(21524)')} sub={lab('$VAR[LucentLibLists]')!r}")
    shot("liblists-row")
    xbmc.executebuiltin("Skin.SetString(lucent.lib.lists,Movie collection · Serie collectie)")
    mon.waitForAbort(0.8)
    log(f"liblists: set sub={lab('$VAR[LucentLibLists]')!r}")
    xbmc.executebuiltin("Action(Down)")
    mon.waitForAbort(0.8)
    down = lab("System.CurrentControlId")
    xbmc.executebuiltin("Action(Up)")
    mon.waitForAbort(0.8)
    log(f"liblists: down={down} up again={lab('System.CurrentControlId')}")
    shot("liblists-set")
    xbmc.executebuiltin("Action(Select)")
    mon.waitForAbort(6)
    log(f"liblists: click dialog={lab('System.CurrentWindow')!r} ok={cond('Window.IsVisible(okdialog)')} text={lab('Control.GetLabel(9)')!r}")
    shot("liblists-click")
    xbmc.executebuiltin("Dialog.Close(all,true)")
    mon.waitForAbort(1)
    xbmc.executebuiltin("Skin.Reset(lucent.lib.lists)")
    xbmc.executebuiltin("ActivateWindow(home)")
    mon.waitForAbort(2)


def tvfav_test():
    """The TV tab row shows the favourite guide group."""
    import sys as _sys
    _sys.path.insert(0, xbmcvfs.translatePath("special://skin/scripts"))
    import tabpanels
    for _ in range(90):
        if cond("Pvr.HasTVChannels"):
            break
        mon.waitForAbort(1)
    mon.waitForAbort(3)
    reply = json.loads(xbmc.executeJSONRPC(json.dumps({"jsonrpc": "2.0", "id": 1, "method": "Files.GetDirectory",
                                                        "params": {"directory": "pvr://channels/tv/", "media": "files"}})))
    files = (reply.get("result") or {}).get("files") or []
    log(f"tvfav: groups {[(f.get('label'), f.get('file')) for f in files][:10]} raw={str(reply)[:300]}")
    def rpc(method, params):
        return json.loads(xbmc.executeJSONRPC(json.dumps({"jsonrpc": "2.0", "id": 1, "method": method, "params": params})))
    log(f"tvfav: GetChannelGroups {str(rpc('PVR.GetChannelGroups', {'channeltype': 'tv'}))[:400]}")
    for d in ("pvr://channels/tv/", "pvr://channels/tv/Favorieten/", "pvr://channels/tv/*/"):
        r = rpc("Files.GetDirectory", {"directory": d, "media": "video"})
        log(f"tvfav: dir {d} -> {[(f.get('label'), f.get('file')) for f in (r.get('result') or {}).get('files') or []][:6]} err={r.get('error')}")
    xbmc.executebuiltin("ActivateWindow(TVGuide)")
    mon.waitForAbort(6)
    n = int(lab("Container(11).NumItems") or 0)
    log(f"tvfav: guide groups {[(lab(f'Container(11).ListItemAbsolute({i}).Label'), lab(f'Container(11).ListItemAbsolute({i}).FolderPath'), lab(f'Container(11).ListItemAbsolute({i}).FileNameAndPath')) for i in range(n)]}")
    xbmc.executebuiltin("ActivateWindow(TVChannels)")
    mon.waitForAbort(4)
    log(f"tvfav: channels window path={lab('Container.FolderPath')!r} group={lab('Control.GetLabel(28)')!r}")
    xbmc.executebuiltin("ActivateWindow(home)")
    mon.waitForAbort(2)
    files = files or [{"label": "Favorieten", "file": "x"}]
    for want in ([f.get("label") for f in files if f.get("label")][-1:] or ["x"]) + ["Bestaat niet"]:
        xbmc.executebuiltin(f'Skin.SetString(lucent.guide.group,"{want}")')
        mon.waitForAbort(0.5)
        tabpanels.tv_path()
        log(f"tvfav: want={want!r} path={HOME.getProperty('lucent.ptv.path')!r} title={HOME.getProperty('lucent.ptv.title')!r}")
    xbmc.executebuiltin("Skin.Reset(lucent.guide.group)")
    tabpanels.tv_path()


def misc133_test():
    """Program add-ons in the menu editor's add-on list; What's new reads the news lines."""
    import sys as _sys
    _sys.path.insert(0, xbmcvfs.translatePath("special://skin/scripts"))
    import menu
    vids = [a[1] for a in menu.video_addons()]
    alls = [a[1] for a in menu.video_addons(menu.ALL_ADDONS)]
    log(f"misc: video={len(vids)} all={len(alls)} extra={[a for a in alls if a not in vids][:12]}")
    xbmc.executebuiltin("RunScript(special://skin/scripts/whatsnew.py)")
    mon.waitForAbort(4)
    log(f"misc: whatsnew dialog={lab('System.CurrentWindow')!r} text={lab('Control.GetLabel(5)')[:300]!r}")
    shot("whatsnew")
    xbmc.executebuiltin("Dialog.Close(all,true)")
    mon.waitForAbort(1)


def wn_test():
    """What's new, example A: versions left, headings right."""
    xbmc.executebuiltin("RunScript(special://skin/scripts/whatsnew.py)")
    mon.waitForAbort(4)
    log(f"wn: win={lab('System.CurrentWindow')!r} focus={lab('System.CurrentControlId')} versions={lab('Container(100).NumItems')} "
        f"title={lab('Window.Property(wn.title)')!r} sub={lab('Window.Property(wn.sub)')!r} items={lab('Container(200).NumItems')} first={lab('Container(200).ListItem.Label')!r}")
    shot("wn-1")
    for _ in range(2):
        xbmc.executebuiltin("Action(Down)")
        mon.waitForAbort(0.8)
    log(f"wn: down2 title={lab('Window.Property(wn.title)')!r} tag={lab('Window.Property(wn.tag)')!r} items={lab('Container(200).NumItems')}")
    shot("wn-2")
    xbmc.executebuiltin("Action(Right)")
    mon.waitForAbort(0.8)
    xbmc.executebuiltin("Action(Down)")
    mon.waitForAbort(0.8)
    log(f"wn: right focus={lab('System.CurrentControlId')} item={lab('Container(200).CurrentItem')}")
    shot("wn-3")
    xbmc.executebuiltin("Action(Left)")
    mon.waitForAbort(0.8)
    steps = [f"left:{lab('System.CurrentControlId')}:{lab('Container(100).CurrentItem')}"]
    for n in range(1, 21):
        xbmc.executebuiltin("Action(Down)")
        mon.waitForAbort(0.4)
        if n in (1, 5, 10, 13, 15, 20):
            steps.append(f"{n}:{lab('Container(100).CurrentItem')}")
    log(f"wn: steps {steps}")
    mon.waitForAbort(1)
    log(f"wn: far title={lab('Window.Property(wn.title)')!r} items={lab('Container(200).NumItems')} first={lab('Container(200).ListItem(0).Label')!r}")
    shot("wn-4")
    xbmc.executebuiltin("Action(Back)")
    mon.waitForAbort(1.5)
    log(f"wn: back win={lab('System.CurrentWindow')!r}")


def tvfav2_test():
    """TV tab on Home lists the guide's favourite group (its own folder, kept when chosen in the guide)."""
    import sys as _sys
    _sys.path.insert(0, xbmcvfs.translatePath("special://skin/scripts"))
    import menu
    import tabpanels
    import guidefav
    for _ in range(90):
        if cond("Pvr.HasTVChannels"):
            break
        mon.waitForAbort(1)
    mon.waitForAbort(3)
    xbmc.executebuiltin("ActivateWindow(TVGuide)")
    mon.waitForAbort(6)
    xbmc.executebuiltin('Skin.SetString(lucent.guide.group,"Favorieten")')
    guidefav.remember_path("Favorieten")
    mon.waitForAbort(1)
    log(f"tvfav2: saved={lab('Skin.String(lucent.guide.grouppath)')!r}")
    xbmc.executebuiltin("ActivateWindow(home)")
    mon.waitForAbort(2)
    m = menu.Menu()
    if not any("tv.py" in t["action"] for t in m.tabs):
        m.tabs.append({"label": "TV", "icon": "icons/tv.png", "action": "RunScript(special://skin/scripts/tv.py)",
                       "widgets": [{"label": "TV channels", "path": "pvr://channels/tv/", "style": "land"}], "actionlabel": ""})
        m.save()
    tabpanels.update()
    m = menu.Menu()
    idx = next(i for i, t in enumerate(m.tabs) if "tv.py" in t["action"])
    xbmc.executebuiltin(f"Control.SetFocus(9000,{idx})")
    mon.waitForAbort(5)
    log(f"tvfav2: path={HOME.getProperty('lucent.ptv.path')!r} title={HOME.getProperty('lucent.ptv.title')!r} items={lab('Container(9320).NumItems')} "
        f"first={lab('Container(9320).ListItemAbsolute(0).Label')!r}")
    shot("tvfav2")


def solis_test():
    """Solis Dashboard tab on Home (example C): numbers from the stand-in Homey."""
    xbmc.executebuiltin('Skin.SetString(lucent.logoask,"1")')
    xbmc.executebuiltin("Dialog.Close(all,true)")
    mon.waitForAbort(1)
    import sys as _sys
    _sys.path.insert(0, xbmcvfs.translatePath("special://skin/scripts"))
    import menu
    m = menu.Menu()
    if not any("script.solis.dashboard" in t["action"] for t in m.tabs):
        m.tabs.append({"label": "Solis Dashboard", "icon": "icons/sparkle.png", "action": "RunAddon(script.solis.dashboard)", "widgets": [], "actionlabel": ""})
        m.save()
    xbmc.executeJSONRPC(json.dumps({"jsonrpc": "2.0", "id": 1, "method": "Addons.SetAddonEnabled", "params": {"addonid": "script.solis.dashboard", "enabled": True}}))
    mon.waitForAbort(3)
    log(f"solis: addon={cond('System.HasAddon(script.solis.dashboard)')} enabled={cond('System.AddonIsEnabled(script.solis.dashboard)')}")
    xbmc.executebuiltin("ActivateWindow(home)")
    mon.waitForAbort(3)
    m = menu.Menu()
    idx = next(i for i, t in enumerate(m.tabs) if "script.solis.dashboard" in t["action"])
    xbmc.executebuiltin(f"Control.SetFocus(9000,{idx})")
    for _ in range(20):
        if HOME.getProperty("lucent.sol.1.t"):
            break
        mon.waitForAbort(1)
    mon.waitForAbort(3)
    keys = ["big", "p1", "p2", "p3", "advice", "img", "hint", "err", "pr.on", "pr.label", "pr.12.h", "pr.13.c", "pr.19.c"] + [f"{n}.{k}" for n in range(1, 7) for k in ("t", "v", "s")]
    log("solis: " + json.dumps({k: HOME.getProperty("lucent.sol." + k) for k in keys}, ensure_ascii=False))
    log(f"solis: panel={cond('Control.IsVisible(9370)')} rows9100={cond('Control.IsVisible(9100)')} items={lab('Container(9370).NumItems')}")
    shot("solis-1")
    xbmc.executebuiltin("Action(Right)")
    mon.waitForAbort(1.5)
    log(f"solis: right focus={lab('System.CurrentControlId')} label={lab('Container(9370).ListItem.Label')!r}")
    shot("solis-2")
    xbmc.executebuiltin("Action(Select)")
    mon.waitForAbort(5)
    log(f"solis: ok window={lab('System.CurrentWindow')!r}")
    shot("solis-3")
    xbmc.executebuiltin("Action(Back)")
    mon.waitForAbort(2)
    xbmc.executebuiltin("ActivateWindow(home)")
    mon.waitForAbort(1)


def settings2_test():
    """Lucent settings in eight categories; setup assistant with the new buttons and the Solis tab step."""
    xbmc.executeJSONRPC(json.dumps({"jsonrpc": "2.0", "id": 1, "method": "Addons.SetAddonEnabled", "params": {"addonid": "script.solis.dashboard", "enabled": True}}))
    mon.waitForAbort(2)
    xbmc.executebuiltin("ActivateWindow(Settings)")
    mon.waitForAbort(3)
    n = int(lab("Container(9000).NumItems") or 0)
    cats = []
    for i in range(n):
        xbmc.executebuiltin(f"SetFocus(9000,{i},absolute)")
        mon.waitForAbort(0.8)
        cid = 9101 if lab("Container(9000).ListItem.Property(cat)") == "about" else 9100
        k = int(lab(f"Container({cid}).NumItems") or 0)
        cats.append(f"{lab('Container(9000).ListItem.Label')}={k}:" + "|".join(lab(f"Container({cid}).ListItemAbsolute({j}).Label") for j in range(k)))
        if i in (1, 3, 4, 7):
            shot(f"set2-{i}")
    for c in cats:
        log(f"set2: {c[:400]}")
    xbmc.executebuiltin("SetFocus(9000,4,absolute)")
    mon.waitForAbort(0.8)
    xbmc.executebuiltin("SetFocus(9100,13,absolute)")
    mon.waitForAbort(1)
    log(f"set2: system last={lab('Container(9100).ListItem.Label')!r}")
    xbmc.executebuiltin("Action(Select)")
    mon.waitForAbort(2)
    log(f"set2: more kodi dialog={lab('System.CurrentWindow')!r} heading={lab('Control.GetLabel(1)')!r} items={lab('Container(3).NumItems')}")
    shot("set2-more")
    xbmc.executebuiltin("Dialog.Close(all,true)")
    xbmc.executebuiltin("ActivateWindow(home)")
    mon.waitForAbort(2)
    # setup assistant
    xbmc.executebuiltin("RunScript(special://skin/scripts/setup.py)")
    mon.waitForAbort(4)
    k = int(lab("Container(100).NumItems") or 0)
    log(f"set2: setup steps {k}: {[lab(f'Container(100).ListItemAbsolute({j}).Label') for j in range(k)]}")
    for j in range(k):
        name = lab(f"Container(100).ListItemAbsolute({j}).Label")
        if name in ("Live TV (IPTV)", "Lucent Library", "Tabs"):
            xbmc.executebuiltin(f"SetFocus(100,{j},absolute)")
            mon.waitForAbort(0.5)
            xbmc.executebuiltin("Action(Select)")
            mon.waitForAbort(2)
            log(f"set2: setup {name}: status={lab('Window.Property(status)')!r} buttons {[lab(f'Window.Property(act{n})') for n in range(1, 5)]}")
            shot(f"set2-setup-{j}")
    xbmc.executebuiltin("Dialog.Close(all,true)")
    mon.waitForAbort(1)
    import sys as _sys
    _sys.path.insert(0, xbmcvfs.translatePath("special://skin/scripts"))
    import setup as _setup
    _setup.add_solis_tab()
    import menu
    log(f"set2: tabs after add {[t['label'] for t in menu.Menu().tabs]}")
    xbmc.executebuiltin("ActivateWindow(home)")
    mon.waitForAbort(2)


def bell56_test():
    """Library series page: the calendar bell for series that still get new seasons."""
    res = json.loads(xbmc.executeJSONRPC(json.dumps({"jsonrpc": "2.0", "id": 1, "method": "VideoLibrary.GetTVShows",
                                                    "params": {"properties": ["title", "uniqueid"]}})))
    shows = (res.get("result") or {}).get("tvshows") or []
    log(f"bell56: library shows {[(s_.get('tvshowid'), s_.get('title'), s_.get('uniqueid')) for s_ in shows][:5]}")
    if not shows:
        return
    sid = shows[0]["tvshowid"]
    xbmc.executeJSONRPC(json.dumps({"jsonrpc": "2.0", "id": 1, "method": "VideoLibrary.SetTVShowDetails",
                                    "params": {"tvshowid": sid, "uniqueid": {"tmdb": "1002"}}}))
    xbmc.executebuiltin("Skin.SetString(lucent.flattenset,1)")
    xbmc.executeJSONRPC(json.dumps({"jsonrpc": "2.0", "id": 1, "method": "Settings.SetSettingValue", "params": {"setting": "videolibrary.flattentvshows", "value": 0}}))
    xbmc.executebuiltin(f"ActivateWindow(Videos,videodb://tvshows/titles/{sid}/,return)")
    for _ in range(15):
        mon.waitForAbort(1)
        if cond("Control.IsVisible(56)"):
            break
    mon.waitForAbort(3)
    log(f"bell56: view56={cond('Control.IsVisible(56)')} dbid={lab('Container(56).ListItem.TvShowDBID')!r} status5698={lab('Container(5698).ListItem.Status')!r} "
        f"status56={lab('Container(56).ListItem.Status')!r} show={lab('Container.ShowTitle')!r} dbid1={lab('Container(56).ListItemAbsolute(1).TvShowDBID')!r} bell={cond('Control.IsVisible(5614)')} label={lab('Control.GetLabel(5614)')!r}")
    xbmc.executebuiltin("SetFocus(5614)")
    mon.waitForAbort(2)
    log(f"bell56: focus={lab('System.CurrentControlId')} label={lab('Control.GetLabel(5614)')!r}")
    shot("bell56-1")
    xbmc.executebuiltin("Action(Select)")
    mon.waitForAbort(6)
    log(f"bell56: after click prop={HOME.getProperty('lucent.s56.bell')!r} label={lab('Control.GetLabel(5614)')!r} focus={lab('System.CurrentControlId')}")
    steps = []
    for key in ("Right", "Left", "Left", "Right"):
        xbmc.executebuiltin(f"Action({key})")
        mon.waitForAbort(0.8)
        steps.append(f"{key}:{lab('System.CurrentControlId')}")
    log(f"bell56: nav after click {steps}")
    xbmc.executebuiltin("SetFocus(5614)")
    mon.waitForAbort(0.8)
    shot("bell56-2")
    xbmc.executebuiltin("Action(Select)")
    mon.waitForAbort(4)
    log(f"bell56: after 2nd click prop={HOME.getProperty('lucent.s56.bell')!r} label={lab('Control.GetLabel(5614)')!r}")
    # the real way: the list of series, open one, bell, Back
    xbmc.executebuiltin('Skin.SetString(lucent.logoask,"1")')
    for start in ("5614", "5601", "none"):
        xbmc.executebuiltin("ActivateWindow(home)")
        mon.waitForAbort(2)
        xbmc.executebuiltin("ActivateWindow(Videos,videodb://tvshows/titles/,return)")
        for _ in range(10):
            mon.waitForAbort(1)
            if lab("Container.Content") == "tvshows":
                break
        for _ in range(4):
            if lab("ListItem.Label") == "Lib Show":
                break
            xbmc.executebuiltin("Action(Down)")
            mon.waitForAbort(0.6)
        view = lab("System.CurrentControlId")
        log(f"bell56: series list content={lab('Container.Content')} view={view} item={lab('ListItem.Label')!r}")
        xbmc.executebuiltin("Action(Select)")
        for _ in range(8):
            mon.waitForAbort(1)
            if lab("Container.Content") == "seasons":
                break
        mon.waitForAbort(1)
        if start != "none":
            xbmc.executebuiltin(f"SetFocus({start})")
        mon.waitForAbort(1)
        if start == "5614":
            xbmc.executebuiltin("Action(Select)")
            mon.waitForAbort(3)
        log(f"bell56: on the season page content={lab('Container.Content')} focus={lab('System.CurrentControlId')}")
        xbmc.executebuiltin("Action(Back)")
        mon.waitForAbort(3)
        after = [f"back:{lab('System.CurrentControlId')}:{lab('Container.Content')}"]
        for key in ("Down", "Up", "Right"):
            xbmc.executebuiltin(f"Action({key})")
            mon.waitForAbort(0.8)
            after.append(f"{key}:{lab('System.CurrentControlId')}:{lab('ListItem.Label')}")
        log(f"bell56: back from {start} {after}")
        shot(f"bell56-back-{start}")
    xbmc.executebuiltin("ActivateWindow(home)")
    mon.waitForAbort(2)


def misc134_test():
    """Volume pill, Solis prices, New seasons row, Home clock."""
    log(f"misc134: newseasons {json.dumps(json.loads(xbmc.executeJSONRPC(json.dumps({'jsonrpc': '2.0', 'id': 1, 'method': 'Files.GetDirectory', 'params': {'directory': 'plugin://script.lucent.library/?action=lib&kind=newseasons', 'media': 'files'}}))))[:300]}")
    xbmc.Player().play("/tmp/ci/audio.mkv")
    for _ in range(20):
        if cond("Player.HasVideo"):
            break
        mon.waitForAbort(1)
    mon.waitForAbort(4)
    xbmc.executebuiltin("Dialog.Close(all,true)")
    mon.waitForAbort(1)
    for key in ("VolumeDown", "VolumeDown", "VolumeDown"):
        xbmc.executebuiltin(f"Action({key})")
        mon.waitForAbort(0.4)
    mon.waitForAbort(0.6)
    log(f"misc134: volumebar={cond('Window.IsVisible(volumebar)')} pct={HOME.getProperty('lucent.vol.pct')!r} seg={HOME.getProperty('lucent.vol.seg')!r}")
    shot("vol-1")
    xbmc.executebuiltin("Action(Mute)")
    mon.waitForAbort(0.8)
    log(f"misc134: muted={cond('Player.Muted')} volumebar={cond('Window.IsVisible(volumebar)')}")
    shot("vol-2")
    xbmc.executebuiltin("Action(Mute)")
    mon.waitForAbort(3)
    log(f"misc134: after 3s volumebar={cond('Window.IsVisible(volumebar)')} busy={HOME.getProperty('lucent.vol.busy')!r}")
    xbmc.Player().stop()
    mon.waitForAbort(2)


def diaglog_test():
    """Safe log: quick, YouTube lines in it (this run and the previous one), logins blanked out, a short text on screen."""
    import xbmcvfs as _v
    xbmc.log("[plugin.video.youtube] CI trailer line: playback stopped at 65s", xbmc.LOGWARNING)
    xbmc.log("CI secret line http://example.invalid/get.php?username=ciuser&password=cipass", xbmc.LOGWARNING)
    oldp = _v.translatePath("special://logpath/kodi.old.log")
    try:
        with open(oldp, "a", encoding="utf-8") as fh:
            fh.write("2026-11-05 10:00:00.000 T:1 warning <general>: CI old run: InputStream Adaptive stopped\n")
    except OSError as e:
        log(f"diaglog: old log not writable {e}")
    t0 = time.time()
    xbmc.executebuiltin("RunScript(special://skin/scripts/diag.py,log)")
    for _ in range(80):
        if cond("Window.IsActive(okdialog)"):
            break
        mon.waitForAbort(0.25)
    log(f"diaglog: ok dialog after {time.time() - t0:.1f}s visible={cond('Window.IsActive(okdialog)')}")
    shot("diaglog-ok")
    xbmc.executebuiltin("Action(Select)")
    t1 = time.time()
    for _ in range(80):
        if cond("Window.IsActive(textviewer)"):
            break
        mon.waitForAbort(0.25)
    mon.waitForAbort(1)
    log(f"diaglog: textviewer after {time.time() - t1:.1f}s visible={cond('Window.IsActive(textviewer)')}")
    shot("diaglog-text")
    xbmc.executebuiltin("Dialog.Close(textviewer,true)")
    mon.waitForAbort(1)
    try:
        body = open(_v.translatePath("special://home/lucent-log.txt"), encoding="utf-8").read()
    except OSError as e:
        body = ""
        log(f"diaglog: no file {e}")
    log(f"diaglog: size={len(body)} yt={'CI trailer line' in body} old={'CI old run' in body} "
        f"pass_hidden={'cipass' not in body and 'ciuser' not in body} header={body.splitlines()[1][:120] if body.count(chr(10)) > 1 else ''}")
    log(f"diaglog: back on home={cond('Window.IsActive(home)')} dialogs={cond('System.HasVisibleModalDialog')}")


def waitfor(c, secs=10):
    for _ in range(int(secs * 4)):
        if cond(c):
            return True
        mon.waitForAbort(0.25)
    return False


CTX_VIS = ("ListItem.IsFolder + !ListItem.IsParentFolder + !String.IsEmpty(Skin.String(nuvio.tab1.label)) + !Window.IsVisible(home) + "
           "[String.StartsWith(ListItem.FileNameAndPath,plugin://) | String.StartsWith(ListItem.FileNameAndPath,videodb://)]")


def noseren_test():
    """1.34: 'Add to Home as widget' in the context menu, the menu without Seren, the setup question."""
    import sys as _s
    _s.path.insert(0, xbmcvfs.translatePath("special://skin/scripts"))
    # 1. the context item on a library folder
    xbmc.executebuiltin("ActivateWindow(Videos,videodb://movies/,return)")
    waitfor("Window.IsActive(videos)")
    mon.waitForAbort(3)
    for _ in range(3):
        if not cond("ListItem.IsParentFolder"):
            break
        key("Down")
        mon.waitForAbort(1)
    import re as _re
    vis = _re.search(r'args="addwidget">.*?<visible>(.*?)</visible>',
                     open(xbmcvfs.translatePath("special://home/addons/script.lucent.library/addon.xml"), encoding="utf-8").read(), _re.S).group(1)
    log(f"ctx: item={lab('ListItem.Label')} folderpath={lab('ListItem.FolderPath')} path={lab('ListItem.Path')} "
        f"folder={cond('ListItem.IsFolder')} vis={cond(vis)}")
    xbmc.executebuiltin("Action(ContextMenu)")
    log(f"ctx: menu open={waitfor('Window.IsActive(contextmenu)', 6)}")
    mon.waitForAbort(1)
    shot("ctx-menu")
    xbmc.executebuiltin("Dialog.Close(contextmenu,true)")
    xbmc.executebuiltin("ActivateWindow(home)")
    waitfor("Window.IsActive(home)")
    mon.waitForAbort(2)
    # 2. add a widget (what the context item does)
    HOME.setProperty("lucent.addw.path", "videodb://movies/genres/")
    HOME.setProperty("lucent.addw.label", "CI Genres")
    xbmc.executebuiltin("RunScript(special://skin/scripts/menu.py,addwidget)")
    log(f"addw: tab list={waitfor('Window.IsActive(selectdialog)')}")
    mon.waitForAbort(1)
    shot("addw-tabs")
    xbmc.executebuiltin("Action(Select)")
    log(f"addw: keyboard={waitfor('Window.IsActive(virtualkeyboard)')}")
    mon.waitForAbort(1)
    xbmc.executebuiltin("SendClick(10103,300)")
    log(f"addw: style={waitfor('Window.IsActive(selectdialog)')}")
    mon.waitForAbort(1)
    xbmc.executebuiltin("Action(Select)")
    mon.waitForAbort(3)
    found = [(t_, w_) for t_ in range(1, 13) for w_ in range(1, 11)
             if lab(f"Skin.String(nuvio.tab{t_}.w{w_}.path)") == "videodb://movies/genres/" and lab(f"Skin.String(nuvio.tab{t_}.w{w_}.label)") == "CI Genres"]
    log(f"addw: saved at {found} tab1={lab('Skin.String(nuvio.tab1.label)')} style={lab(f'Skin.String(nuvio.tab{found[0][0]}.w{found[0][1]}.style)') if found else ''}")
    # 3. without Seren
    xbmc.executebuiltin("Skin.SetBool(lucent.noseren)")
    mon.waitForAbort(1)
    import menu as _menu
    import importlib
    importlib.reload(_menu)
    log(f"noseren: uses_seren={_menu.uses_seren()}")
    m = _menu.Menu()
    m.set_defaults()
    m.save()
    xbmc.executebuiltin("ReloadSkin()")
    mon.waitForAbort(6)
    waitfor("Window.IsActive(home)")
    mon.waitForAbort(6)
    tabs = [lab(f"Skin.String(nuvio.tab{i}.label)") for i in range(1, 13)]
    log(f"noseren: tabs={[x for x in tabs if x]} search={lab('Skin.String(nuvio.tab1.action)')} seren_in_menu={any('plugin.video.seren' in lab(f'Skin.String(nuvio.tab{i}.action)') for i in range(1, 13))}")
    log(f"noseren: home rows={[lab(f'Skin.String(nuvio.home.w{w}.label)') for w in range(1, 6)]}")
    shot("noseren-home")
    import setup as _setup
    log(f"noseren: setup status={_setup.st_seren()} actions={[a[0] for a in _setup.ac_seren()]} steps={[x[0] for x in _setup.STEPS]}")
    xbmc.executebuiltin("Skin.Reset(lucent.noseren)")
    mon.waitForAbort(1)
    importlib.reload(_setup)
    log(f"seren: setup status={_setup.st_seren()} actions={[a[0] for a in _setup.ac_seren()]}")


def dv2_test():
    """1.34.1: Dolby Vision 2 from the release name, the DV line on the Video tab of the player info, the DV2 flag."""
    import sys as _s
    import re as _re
    _s.path.insert(0, xbmcvfs.translatePath("special://skin/scripts"))
    import playerinfo as _pi
    for n in ("Movie.2026.2160p.PCOK.WEB-DL.DV2.HDR10.Atmos-GRP.mkv", "Film.2024.2160p.BluRay.REMUX.DV.P7.FEL.TrueHD-X.mkv", "x.DV.2160p.mkv"):
        log(f"dv2: name {n} -> {_pi.dv_from_name(n)}")
    dvn = _pi.dv_from_name("Movie.2026.2160p.PCOK.WEB-DL.DV2.HDR10.Atmos-GRP.mkv")
    _pi.dv_line("dolbyvision", _re.search(r"(\d+)", "8"), "FEL", dvn)
    log("dv2: props " + json.dumps({k: HOME.getProperty("lucent.pi." + k) for k in ("v.dv.on", "v.dv.line", "v.dv.note")}, ensure_ascii=False))
    log(f"dv2: flag file={os.path.exists(xbmcvfs.translatePath('special://skin/media/flags/DV2.png'))}")
    for k, v in (("title", "Movie.2026.2160p.PCOK.WEB-DL.DV2.HDR10.Atmos-GRP.mkv"), ("b.res", "4K"), ("b.dv", "DOLBY VISION 2 P8 FEL"),
                 ("v.hdrbar", "dv"), ("v.hb.dv", "DOLBY VISION 2"), ("v.hb2", "PROFIEL 8 FEL"), ("v.p1k", "Bestand"), ("v.p1", "HEVC 10-bit")):
        HOME.setProperty("lucent.pi." + k, v)
    w = xbmcgui.WindowXMLDialog("Lucent_PlayerInfo.xml", xbmcvfs.translatePath("special://skin/"), "Default", "1080i")
    w.show()
    mon.waitForAbort(1.5)
    w.setFocusId(102)
    HOME.setProperty("lucent.pi.tab", "2")
    mon.waitForAbort(2)
    log(f"dv2: window={cond('Window.IsVisible(Lucent_PlayerInfo.xml)')} tab={HOME.getProperty('lucent.pi.tab')}")
    shot("dv2-video")
    w.close()
    mon.waitForAbort(1)


def videotab_test():
    """1.34.9: the Video tab of the player info is filled all the way (1.34.1 stopped halfway: name 'dvn' unknown)."""
    import sys as _s
    import re as _re
    _s.path.insert(0, xbmcvfs.translatePath("special://skin/scripts"))
    import playerinfo as _pi
    for k in ("v.p1", "v.p2", "v.p3", "v.p4k", "v.br", "v.dv.line", "v.gamut"):
        HOME.clearProperty("lucent.pi." + k)
    v = {"w": "3840", "h": "2160", "fps": "23.976", "hdr": "dolbyvision", "res_badge": "4K", "prof": _re.search(r"(\d+)", "7"),
         "layer": "FEL", "pix": "yuv420p10", "ten": True, "vname": "HEVC", "scan_word": "progressief", "vbr": 61.2,
         "dvn": _pi.dv_from_name("The.Movie.2026.2160p.BluRay.REMUX.DV.P7.FEL.TrueHD.Atmos.7.1-X.mkv")}
    try:
        _pi.video_tab(v)
        err = None
    except Exception as e:  # noqa: BLE001
        err = repr(e)
    log("videotab: err=%s props=%s" % (err, json.dumps({k: HOME.getProperty("lucent.pi." + k) for k in ("v.p1", "v.p2", "v.p3", "v.p4k", "v.br", "v.dv.line", "v.gamut")}, ensure_ascii=False)))


def skipdup_test():
    """1.34.9: Seren and TheIntroDB both show Skip intro: the choice switches the other one off (fake add-on settings)."""
    import sys as _s
    import types as _t
    if not xbmcvfs.exists("special://skin/scripts/skipdup.py"):        # moved out of the skin in 1.37.0
        log("skipdup: not in this skin")
        return
    _s.path.insert(0, xbmcvfs.translatePath("special://skin/scripts"))
    import skipdup as _d

    class Fake:
        def __init__(self, vals):
            self.vals = dict(vals)

        def getSetting(self, k):
            return self.vals.get(k, "")

        def setSetting(self, k, v):
            self.vals[k] = v

        def getAddonInfo(self, k):
            return "3.9.90"

    out = {}
    for choice in ("tidb", "seren"):
        seren = Fake({"skip.intro": "true", "skip.recap": "true", "skip.credits": "false", "skip.autoIntro": "true"})
        tidb = Fake({"introdb_enabled": "true", "enable_intro": "true", "enable_recap": "true", "enable_credits": "true"})
        addons = {_d.SEREN: seren, _d.TIDB: tidb}
        _d._addon = lambda i: addons[i]
        _d.xbmcaddon = _t.SimpleNamespace(Addon=lambda i: addons[i])
        before = _d.both_on()
        xbmc.executebuiltin(f"Skin.SetString(lucent.skipby,{choice})")
        mon.waitForAbort(0.5)
        result = _d.check()
        out[choice] = {"before": before, "result": result, "after": _d.both_on(), "label": _d.label(),
                       "seren": {k: seren.vals.get(k) for k in ("skip.intro", "skip.recap", "skip.autoIntro")},
                       "tidb": {k: tidb.vals.get(k) for k in ("enable_intro", "enable_recap", "enable_credits")}}
    xbmc.executebuiltin("Skin.Reset(lucent.skipby)")
    log("skipdup: " + json.dumps(out))


def scrub_open_test():
    """1.34.10: the safe log hides playback links; the player info opens although 'open' stayed behind."""
    import sys as _s
    _s.path.insert(0, xbmcvfs.translatePath("special://skin/scripts"))
    import diag as _dg
    samples = ["VideoPlayer::OpenFile: https://abc12-aiostreams.elfhosted.wine/api/v1/debrid/playback/eyJpZCI6IjEyMyJ9",
               "Error resolving item. Item 'plugin://plugin.video.seren/?action=getSources&action_args=%257B'",
               "CCurlFile::Open - <http://picon.example.net:25461/picon/NL/HGTV 8K+ UHD.png> Failed"]
    log("scrub: " + json.dumps([_dg.scrub(x, set()) for x in samples], ensure_ascii=False))
    pl = xbmc.Player()
    xbmc.executebuiltin("PlayMedia(/tmp/ci/test.mkv)")
    for _ in range(40):
        if pl.isPlayingVideo():
            break
        mon.waitForAbort(0.5)
    mon.waitForAbort(3)
    for case, flag in (("clean", ""), ("left-behind", "1")):
        if flag:
            HOME.setProperty("lucent.pi.open", flag)                 # left behind, the screen is not on
        else:
            HOME.clearProperty("lucent.pi.open")
        xbmc.executebuiltin("RunScript(special://skin/scripts/playerinfo.py,open)")
        seen = False
        for _ in range(16):
            mon.waitForAbort(0.5)
            if cond("Window.IsVisible(Lucent_PlayerInfo.xml)"):
                seen = True
                break
        log(f"pinfo-open: {case} playing={pl.isPlayingVideo()} shown={seen}")
        if seen:
            shot(f"pinfo-open-{case}")
        xbmc.executebuiltin("Action(Back)")
        mon.waitForAbort(1.5)
        xbmc.executebuiltin("Dialog.Close(all,true)")
        mon.waitForAbort(1)
    pl.stop()
    mon.waitForAbort(2)
    HOME.clearProperty("lucent.pi.open")


def readable_test():
    """1.34.11: readable text on light pictures (dark edge on the hero texts, darker fade with the fullscreen backdrop)."""
    res = json.loads(xbmc.executeJSONRPC(json.dumps({"jsonrpc": "2.0", "id": 1, "method": "VideoLibrary.GetMovies", "params": {}})))
    movies = (res.get("result") or {}).get("movies") or []
    if not movies:
        log("readable: no movie")
        return
    mid = movies[0]["movieid"]
    xbmc.executeJSONRPC(json.dumps({"jsonrpc": "2.0", "id": 1, "method": "VideoLibrary.SetMovieDetails",
                                    "params": {"movieid": mid, "art": {"fanart": "/tmp/ci/bright.jpg"},
                                               "plot": "A long plot line to see how readable the text is over a very light picture, all the way to the right side of the screen.",
                                               "genre": ["Horror", "Thriller", "Science Fiction"]}}))
    xbmc.executebuiltin("Skin.SetBool(nuvio.fullbackdrop)")
    xbmc.executebuiltin("ActivateWindow(Videos,videodb://movies/titles/,return)")
    mon.waitForAbort(3)
    xbmc.executebuiltin("Container.SetViewMode(51)")
    mon.waitForAbort(1.5)
    xbmc.executebuiltin("SetFocus(51)")
    for _ in range(4):
        if lab("ListItem.DBType") == "movie":
            break
        key("Right")
        mon.waitForAbort(1)
    for case in ("on", "off"):
        if case == "off":
            xbmc.executebuiltin("Skin.SetBool(lucent.readable.off)")
        else:
            xbmc.executebuiltin("Skin.Reset(lucent.readable.off)")
        mon.waitForAbort(2.5)
        log(f"readable: {case} item={lab('ListItem.Label')} fanart={lab('ListItem.Art(fanart)')} var={lab('$VAR[LucentTextShadow]')}")
        shot(f"readable-{case}")
    xbmc.executebuiltin("Skin.Reset(lucent.readable.off)")
    xbmc.executebuiltin("Skin.Reset(nuvio.fullbackdrop)")
    xbmc.executebuiltin("ActivateWindow(home)")
    mon.waitForAbort(2)


def landseries_test():
    """1.34.12: episodes in landscape rows: still of the episode (default) or the series' landscape art."""
    xbmc.executeJSONRPC(json.dumps({"jsonrpc": "2.0", "id": 1, "method": "VideoLibrary.SetTVShowDetails",
                                    "params": {"tvshowid": 901, "art": {"landscape": "/tmp/ci/bright.jpg", "fanart": "/tmp/ci/bright.jpg"}}}))
    xbmc.executeJSONRPC(json.dumps({"jsonrpc": "2.0", "id": 1, "method": "VideoLibrary.SetEpisodeDetails",
                                    "params": {"episodeid": 901, "art": {"thumb": "/tmp/ci/test_still.jpg"}}}))
    xbmc.executebuiltin("ActivateWindow(Videos,videodb://tvshows/titles/901/1/,return)")
    mon.waitForAbort(3)
    xbmc.executebuiltin("Container.SetViewMode(50)")
    mon.waitForAbort(1.5)
    xbmc.executebuiltin("SetFocus(50)")
    mon.waitForAbort(1)
    log(f"landseries: folder={lab('Container.FolderPath')} items={lab('Container.NumItems')}")
    for _ in range(4):
        if lab("ListItem.DBType") == "episode":
            break
        key("Down")
        mon.waitForAbort(1)
    out = {}
    for case in ("episode", "series"):
        if case == "series":
            xbmc.executebuiltin("Skin.SetBool(lucent.land.series)")
        else:
            xbmc.executebuiltin("Skin.Reset(lucent.land.series)")
        mon.waitForAbort(1)
        out[case] = lab("$VAR[ItemLandscape]")
    xbmc.executebuiltin("Skin.Reset(lucent.land.series)")
    log(f"landseries: item={lab('ListItem.Label')} type={lab('ListItem.DBType')} tvland={lab('ListItem.Art(tvshow.landscape)')} {json.dumps(out)}")
    xbmc.executebuiltin("ActivateWindow(home)")
    mon.waitForAbort(2)


def fenlight_test():
    """1.34.13 + Library 1.15.5: Browse series / episodes and Mark as watched for a Fen Light clone (CI stand-in)."""
    log(f"fenlight: addon={cond('System.HasAddon(plugin.video.fakefen)')}")
    out = {}
    for what in ("browseshow", "browseeps"):
        xbmc.executebuiltin("Dialog.Close(all,true)")
        xbmc.executebuiltin("ActivateWindow(home)")
        mon.waitForAbort(2.5)
        xbmc.executebuiltin("ActivateWindow(Videos,plugin://plugin.video.fakefen/?mode=list,return)")
        mon.waitForAbort(2)
        xbmc.executebuiltin("Container.Update(plugin://plugin.video.fakefen/?mode=list,replace)")
        mon.waitForAbort(3)
        xbmc.executebuiltin("Container.SetViewMode(50)")
        mon.waitForAbort(1)
        xbmc.executebuiltin("SetFocus(50)")
        for _ in range(4):
            if lab("ListItem.DBType") == "episode":
                break
            key("Down")
            mon.waitForAbort(1)
        before = f"{lab('ListItem.Label')} tmdb={lab('ListItem.UniqueID(tmdb)')} s={lab('ListItem.Season')}"
        xbmc.executebuiltin(f"RunScript(special://home/addons/script.lucent.library/context.py,{what})")
        mon.waitForAbort(4)
        out[what] = {"on": before, "now": lab("Container.FolderPath"), "first": lab("Container(50).ListItem(0).Label")}
    log("fenlight: browse " + json.dumps(out))
    xbmc.executebuiltin("Container.Update(plugin://plugin.video.fakefen/?mode=list,replace)")
    mon.waitForAbort(3)
    xbmc.executebuiltin("SetFocus(9050)")
    mon.waitForAbort(1.5)
    log(f"addonsettings: plugin={lab('Container.PluginName')!r} visible9069={cond('Control.IsVisible(9069)')} label={lab('Control.GetLabel(9069)')!r}")
    shot("addonsettings-side")
    key("Down")
    mon.waitForAbort(0.8)
    shot("addonsettings-side-down")
    xbmc.executebuiltin("Dialog.Close(all,true)")
    xbmc.executebuiltin("ActivateWindow(Videos,videodb://movies/titles/,return)")
    mon.waitForAbort(3)
    xbmc.executebuiltin("SetFocus(9050)")
    mon.waitForAbort(1.5)
    log(f"sidemenu: library focus={lab('System.CurrentControlId')} v9069={cond('Control.IsVisible(9069)')} v9062={cond('Control.IsVisible(9062)')}")
    shot("sidemenu-library")
    xbmc.executebuiltin("Action(Back)")
    mon.waitForAbort(1)
    log(f"sidemenu: after back focus={lab('System.CurrentControlId')} window={lab('System.CurrentWindow')}")
    xbmc.executebuiltin("ActivateWindow(home)")
    mon.waitForAbort(2.5)
    xbmc.executebuiltin("ActivateWindow(Videos,plugin://plugin.video.fakefen/?mode=list,return)")
    mon.waitForAbort(2)
    xbmc.executebuiltin("Container.Update(plugin://plugin.video.fakefen/?mode=list,replace)")
    mon.waitForAbort(3)
    xbmc.executebuiltin("SetFocus(50)")
    for _ in range(4):
        if lab("ListItem.DBType") == "episode":
            break
        key("Down")
        mon.waitForAbort(1)
    xbmc.executebuiltin("Action(Info)")
    for _ in range(20):
        if cond("Window.IsActive(movieinformation)"):
            break
        mon.waitForAbort(0.5)
    mon.waitForAbort(2)
    log(f"fenlight: info={cond('Window.IsActive(movieinformation)')} button22={cond('Control.IsVisible(22)')}")
    try:
        import sys as _s
        _s.path.insert(0, xbmcvfs.translatePath("special://skin/scripts"))
        import info as _inf
        it = _inf.Item()
        log(f"fenlight: diag fen={_inf.fen_light_id()!r} path={lab('ListItem.FileNameAndPath')!r} ids={bool(it.ids())} tmdb={it.tmdb!r} type={it.dbtype} "
            f"s={lab('ListItem.Season')} e={lab('ListItem.Episode')}")
    except Exception as _e:  # noqa: BLE001
        log(f"fenlight: diag error {_e!r}")
    xbmc.executebuiltin("RunScript(special://skin/scripts/info.py,watched)")
    mon.waitForAbort(4)
    log(f"fenlight: after dialog={lab('System.CurrentWindow')} prop={HOME.getProperty('nuvio.info.watched')!r}")
    try:
        calls = open("/tmp/ci/fakefen.log").read().splitlines()
    except OSError:
        calls = []
    log("fenlight: calls " + json.dumps(calls))
    xbmc.executebuiltin("Dialog.Close(all,true)")
    xbmc.executebuiltin("ActivateWindow(home)")
    mon.waitForAbort(2)



def sideclick_test():
    """The side menu in an add-on folder: does every button do something when pressed?"""
    out = {}
    def fresh():
        xbmc.executebuiltin("Dialog.Close(all,true)")
        xbmc.executebuiltin("ActivateWindow(Videos,plugin://plugin.video.fakefen/?mode=list,return)")
        mon.waitForAbort(2)
        xbmc.executebuiltin("Container.Update(plugin://plugin.video.fakefen/?mode=list,replace)")
        mon.waitForAbort(2.5)
    fresh()
    key("Left")
    mon.waitForAbort(1.2)
    out["open_by_left"] = {"focus": lab("System.CurrentControlId"), "menu": cond("ControlGroup(9050).HasFocus")}
    path = [lab("System.CurrentControlId")]
    for _ in range(9):
        key("Down")
        mon.waitForAbort(0.4)
        path.append(lab("System.CurrentControlId"))
    for _ in range(3):
        key("Up")
        mon.waitForAbort(0.4)
        path.append(lab("System.CurrentControlId"))
    out["nav_path"] = path
    shot("sideclick-nav")
    for cid in ("2", "3", "4", "19", "10", "9061", "20", "9069"):
        fresh()
        xbmc.executebuiltin("SetFocus(9050)")
        mon.waitForAbort(1)
        xbmc.executebuiltin(f"SetFocus({cid})")
        mon.waitForAbort(0.8)
        before = {"focus": lab("System.CurrentControlId"), "visible": cond(f"Control.IsVisible({cid})"), "enabled": cond(f"Control.IsEnabled({cid})"),
                  "view": lab("Container.Viewmode"), "sort": lab("Container.SortMethod"), "order": cond("Container.SortDirection(ascending)"),
                  "label": lab(f"Control.GetLabel({cid})")}
        key("Return")
        mon.waitForAbort(2)
        after = {"focus": lab("System.CurrentControlId"), "window": lab("System.CurrentWindow"), "dialog": cond("System.HasModalDialog"),
                 "view": lab("Container.Viewmode"), "sort": lab("Container.SortMethod"), "order": cond("Container.SortDirection(ascending)")}
        shot(f"sideclick-{cid}")
        out[cid] = {"before": before, "after": after}
        xbmc.executebuiltin("Dialog.Close(all,true)")
        mon.waitForAbort(0.8)
    log("sideclick: " + json.dumps(out))
    xbmc.executebuiltin("ActivateWindow(home)")
    mon.waitForAbort(2)


def views_pause_test():
    """1.34.14: the view per kind (issue #5) and the clean picture when paused (issue #4)."""
    xbmc.executebuiltin("Skin.Reset(lucent.view.remember.off)")
    xbmc.executebuiltin("Skin.Reset(lucent.view.videos.episodes)")
    xbmc.executebuiltin("ActivateWindow(home)")
    mon.waitForAbort(2)
    xbmc.executebuiltin("ActivateWindow(Videos,videodb://tvshows/titles/901/1/,return)")
    mon.waitForAbort(3)
    xbmc.executebuiltin("Container.SetViewMode(50)")
    mon.waitForAbort(3)
    xbmc.executebuiltin("Container.SetViewMode(55)")
    mon.waitForAbort(3)
    saved = lab("Skin.String(lucent.view.videos.episodes)")
    xbmc.executebuiltin("ActivateWindow(home)")
    mon.waitForAbort(2)
    xbmc.executebuiltin("ActivateWindow(Videos,videodb://recentlyaddedepisodes/,return)")
    mon.waitForAbort(4)
    log(f"views: saved={saved!r} other folder content={lab('Container.Content')} items={lab('Container.NumItems')} "
        f"view55={cond('Control.IsVisible(55)')} view50={cond('Control.IsVisible(50)')} mode={lab('Container.Viewmode')}")
    xbmc.executebuiltin("Container.SetViewMode(50)")
    mon.waitForAbort(2)
    xbmc.executebuiltin("Skin.Reset(lucent.view.videos.episodes)")
    xbmc.executebuiltin("ActivateWindow(home)")
    mon.waitForAbort(2)
    pl = xbmc.Player()
    out = {}
    autosubs = cond("Skin.HasSetting(nuvio.autosubs)")
    xbmc.executebuiltin("Skin.Reset(nuvio.autosubs)")
    for setting in ("clean3", ""):
        xbmc.executebuiltin(f"Skin.SetString(nuvio.pauseinfo,{setting})" if setting else "Skin.Reset(nuvio.pauseinfo)")
        xbmc.executebuiltin("PlayMedia(/tmp/ci/test.mkv)")
        for _ in range(40):
            if pl.isPlayingVideo():
                break
            mon.waitForAbort(0.5)
        mon.waitForAbort(10)                          # on CI the video really starts ~9 s after PlayMedia
        for _ in range(3):                            # the automatic subtitle search may have opened its window
            xbmc.executebuiltin("Dialog.Close(all,true)")
            mon.waitForAbort(1)
        xbmc.executebuiltin("PlayerControl(Play)")    # pause
        mon.waitForAbort(1)
        early = cond("Window.IsVisible(seekbar)")
        mon.waitForAbort(5)
        out[setting or "default"] = {"paused": cond("Player.Paused"), "bar_at_1s": early, "bar_at_6s": cond("Window.IsVisible(seekbar)")}
        xbmc.executebuiltin("ActivateWindow(videoosd)")             # the player menu, as OK opens it on a Shield
        mon.waitForAbort(1)
        out[setting or "default"]["osd_opened"] = cond("Window.IsActive(videoosd)")
        out[setting or "default"]["diag"] = {c: cond(c) for c in ("Player.Paused", "Window.IsActive(videoosd)", "System.HasActiveModalDialog",
                                                              "Window.IsActive(sliderdialog)", "System.IdleTime(3)", "Window.IsVisible(videoosd)")}
        out[setting or "default"]["diag"]["pauseinfo"] = lab("Skin.String(nuvio.pauseinfo)")
        out[setting or "default"]["diag"]["helper"] = HOME.getProperty("lucent.helper")
        mon.waitForAbort(5)
        out[setting or "default"]["osd_after_6s"] = cond("Window.IsActive(videoosd)")
        xbmc.executebuiltin("Dialog.Close(videoosd)")
        mon.waitForAbort(1)
        shot(f"pause-{setting or 'default'}")
        pl.stop()
        mon.waitForAbort(3)
    xbmc.executebuiltin("Skin.Reset(nuvio.pauseinfo)")
    if autosubs:
        xbmc.executebuiltin("Skin.SetBool(nuvio.autosubs)")
    log("pauseclean: " + json.dumps(out))


def pct_test():
    """1.34.16: percentage watched above the progress bar (issue #7)."""
    xbmc.executebuiltin("ActivateWindow(home)")
    mon.waitForAbort(2)
    xbmc.executebuiltin("ActivateWindow(Videos,videodb://movies/titles/,return)")
    mon.waitForAbort(3)
    xbmc.executebuiltin("Container.SetViewMode(51)")
    mon.waitForAbort(1.5)
    xbmc.executebuiltin("SetFocus(51)")
    for _ in range(4):
        if lab("ListItem.DBType") == "movie":
            break
        key("Right")
        mon.waitForAbort(1)
    for case in ("on", "off"):
        xbmc.executebuiltin("Skin.SetBool(lucent.pct.off)" if case == "off" else "Skin.Reset(lucent.pct.off)")
        mon.waitForAbort(1.5)
        log(f"pct: {case} item={lab('ListItem.Label')} percent={lab('ListItem.PercentPlayed')}")
        shot(f"pct-{case}")
    xbmc.executebuiltin("Skin.Reset(lucent.pct.off)")
    xbmc.executebuiltin("ActivateWindow(home)")
    mon.waitForAbort(2)


def mdblist_test():
    """1.34.17 (issue #8): MDBList scores (Letterboxd, RT audience, Metacritic users) on the info page and in the lists,
    with only an MDBList key (no OMDb key): MDBList also fills RT / Metacritic / IMDb."""
    import sys as _s
    _s.path.insert(0, xbmcvfs.translatePath("special://skin/scripts"))
    import omdb as _o
    d = xbmcvfs.translatePath("special://profile/addon_data/skin.lucent/")
    os.makedirs(d, exist_ok=True)
    for f in ("omdb.key", "omdb_cache.json", "mdblist_cache.json"):
        try:
            os.remove(os.path.join(d, f))
        except OSError:
            pass
    with open(os.path.join(d, "mdblist.key"), "w") as fh:
        fh.write("cimdbkey")
    log(f"mdblist: parse={_o.mdb_fetch('tt0185937', 'movie')} text={_o.list_text(_o.all_scores('tt0185937', 'movie'))!r}")
    mon.waitForAbort(31)                                  # the helper reads the keys again after 30 s
    xbmc.executebuiltin("ActivateWindow(home)")
    mon.waitForAbort(2)
    xbmc.executebuiltin("ActivateWindow(Videos,videodb://movies/titles/,return)")
    mon.waitForAbort(3)
    xbmc.executebuiltin("Container.SetViewMode(51)")
    mon.waitForAbort(1.5)
    xbmc.executebuiltin("SetFocus(51)")
    for _ in range(4):
        if lab("ListItem.DBType") == "movie":
            break
        key("Right")
        mon.waitForAbort(1)
    mon.waitForAbort(4)
    p = {k: HOME.getProperty("lucent.omdbl." + k) for k in ("rt", "rta", "mc", "mcu", "lb", "text", "for")}
    log(f"mdblist: list item={lab('ListItem.Label')} props={json.dumps(p, ensure_ascii=False)}")
    shot("mdblist-list")
    xbmc.executebuiltin("Action(Info)")
    for _ in range(20):
        if cond("Window.IsActive(movieinformation)"):
            break
        mon.waitForAbort(0.5)
    mon.waitForAbort(4)
    p = {k: HOME.getProperty("lucent.omdb." + k) for k in ("imdb", "rt", "rta", "mc", "mcu", "lb", "lb.c", "for")}
    log(f"mdblist: page props={json.dumps(p, ensure_ascii=False)}")
    shot("mdblist-page")
    xbmc.executebuiltin("Dialog.Close(all,true)")
    os.remove(os.path.join(d, "mdblist.key"))
    xbmc.executebuiltin("ActivateWindow(home)")
    mon.waitForAbort(2)


def mediaflags_test():
    """1.34.18 (issue #9): media flags in the list with the big picture, for a film, a series and an episode."""
    out = {}
    for name, path in (("movie", "videodb://movies/titles/"), ("tvshow", "videodb://tvshows/titles/"), ("episode", "videodb://tvshows/titles/901/1/")):
        xbmc.executebuiltin("ActivateWindow(home)")
        mon.waitForAbort(2)
        xbmc.executebuiltin(f"ActivateWindow(Videos,{path},return)")
        mon.waitForAbort(3)
        xbmc.executebuiltin("Container.SetViewMode(51)")
        mon.waitForAbort(1.5)
        xbmc.executebuiltin("SetFocus(51)")
        for _ in range(4):
            if lab("ListItem.DBType") == name:
                break
            key("Right")
            mon.waitForAbort(1)
        mon.waitForAbort(2.5)
        out[name] = {"item": lab("ListItem.Label"), "res": lab("ListItem.VideoResolution"), "hdr": lab("ListItem.HdrType"),
                     **{k: HOME.getProperty("lucent.mf." + k) for k in ("img1", "img2", "img3", "img4", "img5", "img6", "alang", "slang", "most", "for")}}
        shot(f"mediaflags-{name}")
        if name in ("movie", "episode"):                 # 1.35.2: shown at once, and the row keeps its place
            xbmc.executebuiltin("Action(Left)")
            mon.waitForAbort(1.5)
            shot(f"mediaflags-{name}-noflags")
            xbmc.executebuiltin("Action(Right)")
            t0 = time.time()
            while not HOME.getProperty("lucent.mf.img1") and time.time() - t0 < 3:
                mon.waitForAbort(0.05)
            out[name]["fast_s"] = round(time.time() - t0, 2)
            out[name]["fast"] = {"item": lab("ListItem.Label"), "for": HOME.getProperty("lucent.mf.for")[:40],
                                 "img1": HOME.getProperty("lucent.mf.img1"),
                                 "row": cond("!Skin.HasSetting(lucent.mf.off) + String.StartsWith(Container.FolderPath,videodb://)")}
    log("mediaflags: " + json.dumps(out))
    xbmc.executebuiltin("ActivateWindow(home)")
    mon.waitForAbort(2)


def ytfix_test():
    """1.34.2: the YouTube trailer fix on a copy of player_client.py of YouTube 7.4.4 (the add-on is not in CI)."""
    import sys as _s
    import shutil as _sh
    import types as _t
    _s.path.insert(0, xbmcvfs.translatePath("special://skin/scripts"))
    import ytfix as _y
    src = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "ci", "data", "yt744_player_client.py")
    if not os.path.exists(src):
        src = "/tmp/ci/yt744_player_client.py"
    work = xbmcvfs.translatePath("special://temp/ytfix/player_client.py")
    os.makedirs(os.path.dirname(work), exist_ok=True)
    _sh.copyfile(src, work)
    real = _y.xbmc
    fake = _t.SimpleNamespace(**{k: getattr(real, k) for k in dir(real) if not k.startswith("__")})
    fake.getCondVisibility = lambda c: True if "HasAddon(plugin.video.youtube)" in c else real.getCondVisibility(c)
    _y.xbmc = fake
    _y.FILE = "special://temp/ytfix/player_client.py"
    xbmc.executebuiltin("Skin.Reset(lucent.ytfix.off)")
    mon.waitForAbort(0.5)
    r1 = _y.check()
    txt = open(work, encoding="utf-8").read()
    import py_compile
    try:
        py_compile.compile(work, doraise=True)
        ok = True
    except Exception as e:  # noqa: BLE001
        ok = repr(e)
    backups = os.listdir(xbmcvfs.translatePath(_y.BACKUP_DIR)) if os.path.isdir(xbmcvfs.translatePath(_y.BACKUP_DIR)) else []
    log(f"ytfix: on -> {r1} marker={'lucent-ytfix' in txt} vr_active={chr(39) + 'android_vr' + chr(39) + ',' in txt.replace('# ' + chr(39) + 'android_vr', '')} compiles={ok} backups={backups} label={_y.label()}")
    log(f"ytfix: again -> {_y.check()}")
    xbmc.executebuiltin("Skin.SetBool(lucent.ytfix.off)")
    mon.waitForAbort(0.5)
    r2 = _y.check()
    log(f"ytfix: off -> {r2} identical={open(work, encoding='utf-8').read() == open(src, encoding='utf-8').read()} label={_y.label()}")
    xbmc.executebuiltin("Skin.Reset(lucent.ytfix.off)")
    _y.xbmc = real


def fsback_test():
    """1.34.3: Back while skipping (a seek just done, fast forward) must not stop the film; Back later does."""
    pl = xbmc.Player()
    xbmc.executebuiltin("PlayMedia(/tmp/ci/test.mkv)")
    for _ in range(30):
        if pl.isPlayingVideo():
            break
        mon.waitForAbort(0.5)
    xbmc.executebuiltin("ActivateWindow(fullscreenvideo)")
    mon.waitForAbort(4)
    xbmc.executebuiltin("Seek(20)")
    mon.waitForAbort(0.8)
    log(f"fsback: after seek seeking={cond('Player.Seeking')} recent={cond('Player.HasPerformedSeek(3)')} seekbar={cond('Window.IsVisible(seekbar)')}")
    shot("fsback-seek")
    xbmc.executebuiltin("RunScript(special://skin/scripts/fsback.py)")
    mon.waitForAbort(1.5)
    log(f"fsback: back after a seek -> playing={pl.isPlayingVideo()}")
    xbmc.executebuiltin("PlayerControl(Forward)")
    mon.waitForAbort(1.5)
    log(f"fsback: forwarding={cond('Player.Forwarding')} speed={lab('Player.PlaySpeed')}")
    xbmc.executebuiltin("RunScript(special://skin/scripts/fsback.py)")
    mon.waitForAbort(1.5)
    log(f"fsback: back while fast forward -> playing={pl.isPlayingVideo()} forwarding={cond('Player.Forwarding')} speed={lab('Player.PlaySpeed')}")
    mon.waitForAbort(4)
    xbmc.executebuiltin("RunScript(special://skin/scripts/fsback.py)")
    mon.waitForAbort(2.5)
    log(f"fsback: back while just watching -> playing={pl.isPlayingVideo()}")
    if pl.isPlaying():
        pl.stop()
    # the name and count above lists
    xbmc.executebuiltin("ActivateWindow(Videos,videodb://movies/titles/,return)")
    mon.waitForAbort(3)
    shot("topbar-on")
    xbmc.executebuiltin("Skin.SetBool(lucent.hidetopbar)")
    mon.waitForAbort(1.5)
    shot("topbar-off")
    log(f"topbar: hidden={cond('Skin.HasSetting(lucent.hidetopbar)')} folder={lab('Container.FolderName')}")
    xbmc.executebuiltin("Skin.Reset(lucent.hidetopbar)")
    xbmc.executebuiltin("ActivateWindow(home)")
    mon.waitForAbort(2)


def omdb_test():
    """1.34.4: OMDb scores on the info page (fake OMDb on 127.0.0.1:8765/omdb)."""
    import sys as _s
    _s.path.insert(0, xbmcvfs.translatePath("special://skin/scripts"))
    d = xbmcvfs.translatePath("special://profile/addon_data/skin.lucent/")
    os.makedirs(d, exist_ok=True)
    with open(os.path.join(d, "omdb.key"), "w") as fh:
        fh.write("cikey1234")
    res = json.loads(xbmc.executeJSONRPC(json.dumps({"jsonrpc": "2.0", "id": 1, "method": "VideoLibrary.GetMovies", "params": {"properties": ["title"]}})))
    movies = (res.get("result") or {}).get("movies") or []
    log(f"omdb: movies {[(m['movieid'], m['title']) for m in movies][:3]}")
    if not movies:
        return
    mid = movies[0]["movieid"]
    xbmc.executeJSONRPC(json.dumps({"jsonrpc": "2.0", "id": 1, "method": "VideoLibrary.SetMovieDetails",
                                    "params": {"movieid": mid, "uniqueid": {"imdb": "tt0185937"}}}))
    xbmc.executebuiltin("ActivateWindow(Videos,videodb://movies/titles/,return)")
    mon.waitForAbort(3)
    for _ in range(4):
        if lab("ListItem.DBType") == "movie":
            break
        key("Down")
        mon.waitForAbort(1)
    xbmc.executebuiltin("Action(Info)")
    for _ in range(20):
        if cond("Window.IsActive(movieinformation)"):
            break
        mon.waitForAbort(0.5)
    mon.waitForAbort(4)
    p = {k: HOME.getProperty("lucent.omdb." + k) for k in ("imdb", "votes", "rt", "rtc", "mc", "mcc", "for")}
    log(f"omdb: page={cond('Window.IsActive(movieinformation)')} item={lab('ListItem.Title')} imdb={lab('ListItem.UniqueID(imdb)')} props={p}")
    shot("omdb-page")
    xbmc.executebuiltin("Skin.SetBool(lucent.rate.hide.rt)")
    xbmc.executebuiltin("Skin.SetBool(lucent.rate.votes)")
    mon.waitForAbort(1.5)
    shot("omdb-page-choice")
    xbmc.executebuiltin("Skin.Reset(lucent.rate.hide.rt)")
    xbmc.executebuiltin("Skin.Reset(lucent.rate.votes)")
    xbmc.executebuiltin("Dialog.Close(all,true)")
    mon.waitForAbort(1)
    import omdb as _o
    cache = os.path.exists(xbmcvfs.translatePath(_o.CACHE))
    with open(os.path.join(d, "omdb.key"), "w") as fh:
        fh.write("badkey")
    try:
        bad = _o.ask("tt0185937", "badkey").get("Error")
    except Exception as e:  # noqa: BLE001
        bad = repr(e)
    log(f"omdb: cache={cache} badkey={bad} votes_short={_o.short_votes('282345')},{_o.short_votes('1234567')}")
    os.remove(os.path.join(d, "omdb.key"))
    xbmc.executebuiltin("ActivateWindow(home)")
    mon.waitForAbort(2)


def _dir_guarded(path, wait=20):
    """Files.GetDirectory in a thread; a modal dialog that pops up meanwhile is noted and closed (it would block Kodi)."""
    import threading
    box = {}
    def run():
        box["res"] = json.loads(xbmc.executeJSONRPC(json.dumps({"jsonrpc": "2.0", "id": 1, "method": "Files.GetDirectory",
                                "params": {"directory": path, "media": "files"}})))
    th = threading.Thread(target=run, daemon=True)
    th.start()
    dialog = ""
    t0 = time.time()
    while th.is_alive() and time.time() - t0 < wait:
        mon.waitForAbort(0.5)
        if cond("System.HasModalDialog | Window.IsActive(okdialog) | Window.IsActive(yesnodialog) | Window.IsActive(selectdialog)"):
            dialog = dialog or (lab("Control.GetLabel(9)") or lab("System.CurrentWindow"))
            xbmc.executebuiltin("Dialog.Close(all,true)")
    res = box.get("res") or {}
    files = (res.get("result") or {}).get("files")
    return {"n": len(files) if files is not None else None, "labels": [f.get("label") for f in files or []][:12],
            "paths": [f.get("file", "") for f in files or []][:20], "dialog": dialog, "error": str(res.get("error"))[:80] if res.get("error") else ""}


def letters_test():
    """The alphabet bar under the poster row (view 51): each letter jumps to the first title with it."""
    out = {}
    try:
        xbmc.executebuiltin("ActivateWindow(Videos,plugin://plugin.video.fakefen/?mode=letters,return)")
        for _ in range(40):
            if cond("Window.IsActive(videos) + Integer.IsGreater(Container.NumItems,20)"):
                break
            time.sleep(0.5)
        xbmc.executebuiltin("Container.SetSortMethod(7)")
        time.sleep(1)
        xbmc.executebuiltin("Container.SetViewMode(51)")
        time.sleep(2)
        out["view"] = lab("Container.ViewMode")
        out["n"] = lab("Container(51).NumItems")
        out["abs_sortletter_5"] = lab("Container(51).ListItemAbsolute(5).SortLetter")
        for letter in ("C", "M", "T", "B", "W", "#"):
            xbmc.executebuiltin(f"RunScript(special://skin/scripts/letters.py,51,{letter})")
            time.sleep(2.5)
            out[letter] = lab("Container(51).ListItem.Label")
        shot("letters-T")
    except Exception as error:  # noqa: BLE001
        out["error"] = repr(error)
    log("letters: " + json.dumps(out))
    xbmc.executebuiltin("ActivateWindow(home)")
    time.sleep(1)


def lucentvideo_test():
    """the video add-on 0.21.0 (plugin.video.lucent): installs, its menus answer (without a TMDB key: a dialog, closed here)."""
    log(f"lucentvideo: addon={cond('System.HasAddon(plugin.video.lucent)')} version={lab('System.AddonVersion(plugin.video.lucent)')}")
    out = {"root": _dir_guarded("plugin://plugin.video.lucent/")}
    out["tools"] = _dir_guarded("plugin://plugin.video.lucent/?action=tools")
    out["service_row"] = _dir_guarded("plugin://plugin.video.lucent/?action=list&name=service_row&widget=1", 15)
    for nm in ("calendar", "foryou", "person&id=287", "trending_movie", "upcoming_movie", "upcoming_tv", "new_tv", "alerts"):
        out["row_" + nm] = _dir_guarded("plugin://plugin.video.lucent/?action=list&widget=1&name=" + nm, 15)
    try:
        import sys as _s
        _s.path.insert(0, xbmcvfs.translatePath("special://skin/scripts"))
        import menu as _menu
        out["menu"] = {"has_lv": _menu.has_lv(), "rows": len(_menu.WIDGETS_LV), "names": [r[1].split("name=")[1] for r in _menu.WIDGETS_LV]}
        out["lvmap"] = {p: _menu.lv_path(p) for p in ("plugin://plugin.video.seren/?action=showsNextUp",
                         "plugin://plugin.video.seren/?action=genericEndpoint&mediatype=shows&endpoint=anticipated",
                         "plugin://plugin.video.seren/?action=moviesUpdated", "plugin://script.lucent.library/?action=providers",
                         "plugin://script.lucent.library/?action=tmdb&list=prov_8_newtv", "videodb://movies/titles/")}
        out["libmap"] = {p: _menu.lv_path(p, True, True) for p in ("plugin://script.lucent.library/?action=lib&kind=continue&only=movie",
                         "plugin://script.lucent.library/?action=lib&kind=nextup", "plugin://script.lucent.library/?action=tmdb&list=trakt_watchlist_tv",
                         "plugin://script.lucent.library/?action=tmdb&list=toprated_tv", "plugin://script.lucent.library/?action=providers")}
        _tabs = _menu.lv_tabs()[0]
        out["lvtabs"] = [[tb["action"], [w["path"].split("name=")[-1] for w in tb["widgets"]]] for tb in _tabs[:5]]
        out["use_lv"] = _menu.use_lv()
    except Exception as _e:  # noqa: BLE001
        out["menu"] = repr(_e)
    log("lucentvideo: " + json.dumps(out))
    xbmc.executebuiltin("Addon.OpenSettings(plugin.video.lucent)")
    mon.waitForAbort(3)
    shot("lucentvideo-settings")
    xbmc.executebuiltin("Dialog.Close(all,true)")
    xbmc.executebuiltin("ActivateWindow(home)")
    mon.waitForAbort(2)
    try:
        with open(xbmcvfs.translatePath("special://logpath/kodi.log"), encoding="utf-8", errors="replace") as fh:
            lines = [ln for ln in fh if "plugin.video.lucent" in ln or "lucent-video" in ln.lower()]
        errs = [ln.strip()[24:200] for ln in lines if " error " in ln.lower() or "Traceback" in ln]
        secrets = [ln.strip()[24:120] for ln in lines if "api_key=" in ln or "Authorization" in ln]
        log(f"lucentvideo: log lines={len(lines)} errors={len(errs)} secrets={len(secrets)} {json.dumps(errs[:6])}")
    except OSError as e:
        log(f"lucentvideo: log {e}")


def nolib_test():
    """1.36.0: the skin without Lucent Library (switched off here, only in the 'new' run): menus, setup step, diag."""
    if not TAG.startswith("new"):
        return
    xbmc.executeJSONRPC(json.dumps({"jsonrpc": "2.0", "id": 1, "method": "Addons.SetAddonEnabled",
                                    "params": {"addonid": "script.lucent.library", "enabled": False}}))
    mon.waitForAbort(3)
    out = {"has_lib": cond("System.HasAddon(script.lucent.library)"), "skin": lab("System.AddonVersion(skin.lucent)")}
    try:
        import sys as _s
        import importlib
        _s.path.insert(0, xbmcvfs.translatePath("special://skin/scripts"))
        import menu as _menu
        importlib.reload(_menu)
        out["menu_has_lib"] = _menu.has_lib()
        out["lib_rows"] = [r[1] for r in _menu.WIDGETS_LIBRARY if _menu.has_lib() or not r[1].startswith("plugin://script.lucent.library/")][:4]
        out["lv_new_rows"] = [r[1].split("name=")[1] for r in _menu.WIDGETS_LV][-7:]
        import setup as _setup
        importlib.reload(_setup)
        out["setup"] = [_setup.st_library(), [a[0] for a in _setup.ac_library()]]
        import diag as _diag
        out["diag_optional"] = [_diag.addon_state(a) for a in ("plugin.video.lucent", "script.lucent.library")]
        import libtools as _lt
        out["libtools"] = [callable(_lt.surprise), callable(_lt.next_in_set)]
    except SystemExit:
        pass
    except Exception as _e:  # noqa: BLE001
        out["error"] = repr(_e)
    xbmc.executebuiltin("Dialog.Close(all,true)")
    xbmc.executebuiltin("ActivateWindow(Videos,videodb://movies/titles/,return)")
    mon.waitForAbort(4)
    out["side_visible"] = cond("String.StartsWith(Container.FolderPath,videodb://)")
    shot("nolib-movies")
    xbmc.executebuiltin("ActivateWindow(home)")
    mon.waitForAbort(3)
    shot("nolib-home")
    log("nolib: " + json.dumps(out))


def infobuttons_test():
    """1.37.0: Library and lists / Mark as watched work with the video add-on, also for titles of other video add-ons."""
    out = {}
    try:
        import sys as _s
        import importlib
        _s.path.insert(0, xbmcvfs.translatePath("special://skin/scripts"))
        import info as _i
        importlib.reload(_i)
        xbmc.executebuiltin("ActivateWindow(Videos,plugin://plugin.video.fakefen/?mode=list,return)")
        for _ in range(30):
            if cond("Window.IsActive(videos) + Integer.IsGreater(Container.NumItems,0) + String.IsEqual(ListItem.DBType,episode)"):
                break
            mon.waitForAbort(0.5)
        out["item"] = [lab("ListItem.Label"), lab("ListItem.DBType"), lab("ListItem.UniqueID(tmdb)")]
        out["seren_login"] = _i.seren_login()
        out["use_lv"] = _i.use_lv()
        out["target"] = _i.lv_target()
        out["lv_version"] = list(_i.lv_version())
        out["lists_by_lv"] = _i.lv_version() >= _i.LV_LISTS      # False until the video add-on has action=lists
        out["play_movie"] = _i.lv_play_url("movie", 603)
        out["play_tv"] = _i.lv_play_url("tv", 1399)
        HOME_ = xbmcgui.Window(10000)
        HOME_.clearProperty("nuvio.info.watched")
        out["fen_light"] = _i.fen_light_id()                 # the stand-in is a Fen Light clone: toggle_watched lets Fen mark it
        _i.lv_watched()                                      # so call the the video add-on route itself
        mon.waitForAbort(10)
        out["prop_after"] = HOME_.getProperty("nuvio.info.watched")
        try:
            with open(xbmcvfs.translatePath("special://logpath/kodi.log"), encoding="utf-8", errors="replace") as fh:
                out["lv_log_marked"] = any("marked episode 1399 watched" in ln for ln in fh)
        except OSError:
            out["lv_log_marked"] = None
        _i.lv_menu()                                         # 'More': the video add-on's menu with all options
        for _ in range(20):
            if cond("Window.IsActive(contextmenu)"):
                break
            mon.waitForAbort(0.5)
        out["more_menu"] = cond("Window.IsActive(contextmenu)")
        shot("info-more-menu")
        xbmc.executebuiltin("Dialog.Close(contextmenu,true)")
        mon.waitForAbort(1)
        seen = ""
        base = xbmcvfs.translatePath("special://profile/addon_data/plugin.video.lucent/")
        for root, _d, files in os.walk(base):
            if "watched.json" in files:
                with open(os.path.join(root, "watched.json"), encoding="utf-8") as fh:
                    seen += fh.read()
        out["lv_seen_1399_2_3"] = '"1399"' in seen and '"2:3"' in seen
        xbmc.executebuiltin("Dialog.Close(all,true)")
    except Exception as _e:  # noqa: BLE001
        out["error"] = repr(_e)
    log("infobuttons: " + json.dumps(out))
    xbmc.executebuiltin("ActivateWindow(home)")
    mon.waitForAbort(2)


def progress_colour_test():
    """1.38.1: percentage from WatchedProgress (Fen Light / Red Light, issue #7) and the colour of the watched check (#10)."""
    out = {}
    try:
        xbmc.executebuiltin("ActivateWindow(Videos,plugin://plugin.video.fakefen/?mode=progress,return)")
        for _ in range(30):
            if cond("Window.IsActive(videos) + Integer.IsGreater(Container.NumItems,0) + String.IsEqual(ListItem.Label,Half Film)"):
                break
            mon.waitForAbort(0.5)
        xbmc.executebuiltin("Container.SetViewMode(51)")
        mon.waitForAbort(2)
        out["kodi_pct"] = lab("ListItem.PercentPlayed")
        out["prop"] = lab("ListItem.Property(WatchedProgress)")
        out["pct_var"] = lab("$VAR[LucentPct]")
        out["show"] = cond("[Integer.IsGreater(ListItem.PercentPlayed,0) | Integer.IsGreater(ListItem.Property(WatchedProgress),0)]")
        shot("progress-redlight")
        xbmc.executebuiltin("Skin.SetString(lucent.watched.colour,graphite)")
        mon.waitForAbort(1)
        out["colour_graphite"] = lab("$VAR[LucentWatchedColour]")
        xbmc.executebuiltin("Skin.SetString(lucent.watched.colour,)")
        mon.waitForAbort(1)
        out["colour_default"] = lab("$VAR[LucentWatchedColour]")
    except Exception as _e:  # noqa: BLE001
        out["error"] = repr(_e)
    log("progress: " + json.dumps(out))
    xbmc.executebuiltin("ActivateWindow(home)")
    mon.waitForAbort(2)


def formatclips_test():
    """the video add-on's format check: do its clips start in Kodi (windowed, like the check does)?"""
    out = {}
    base = xbmcvfs.translatePath("special://home/addons/plugin.video.lucent/resources/formattest/")
    player = xbmc.Player()
    for name in ("hevc4k.mp4", "ddplus.mkv", "vp9.webm", "dv81.mp4"):
        path = os.path.join(base, name)
        res = {"exists": os.path.exists(path)}
        try:
            player.play(path, xbmcgui.ListItem(name, path=path), windowed=True)
            started = False
            for _ in range(100):
                if mon.waitForAbort(0.1):
                    break
                if player.isPlayingVideo() and player.getTime() > 0.2:
                    started = True
                    break
            res.update(started=started, hdr=lab("VideoPlayer.HdrType"), codec=lab("VideoPlayer.VideoCodec"))
        except Exception as _e:  # noqa: BLE001
            res["error"] = repr(_e)
        player.stop()
        mon.waitForAbort(1.5)
        out[name] = res
    try:
        with open(xbmcvfs.translatePath("special://logpath/kodi.log"), encoding="utf-8", errors="replace") as fh:
            out["errors"] = [ln.strip()[24:200] for ln in fh if "formattest" in ln and (" error " in ln.lower() or "warning" in ln.lower())][:8]
    except OSError:
        pass
    log("formatclips: " + json.dumps(out))


def trailerlayer_test():
    """1.38.3: poster trailers on Home: trailer window, hero media and the expanded card (an overlay over the row)."""
    out = {}
    base = xbmcvfs.translatePath("special://home/addons/plugin.video.lucent/resources/formattest/")
    path = os.path.join(base, "hevc4k.mp4")
    player = xbmc.Player()
    xbmc.executebuiltin("Dialog.Close(all,true)")
    mon.waitForAbort(1)
    xbmc.executebuiltin("Skin.SetBool(nuvio.trailers.menu)")
    full = cond("Skin.HasSetting(nuvio.fullbackdrop)")
    xbmc.executebuiltin("Skin.Reset(nuvio.fullbackdrop)")         # 1.38.6: the soft edge of the picture at the top right
    xbmc.executebuiltin("ActivateWindow(home)")
    mon.waitForAbort(2)
    xbmc.executebuiltin("SetFocus(8101)")
    mon.waitForAbort(2)
    shot("home-picture-edge")
    if full:
        xbmc.executebuiltin("Skin.SetBool(nuvio.fullbackdrop)")
    for mode in ("expand", "window", "hero"):
        xbmc.executebuiltin(f"Skin.SetString(nuvio.posterfocus,{mode})")
        xbmc.executebuiltin("ActivateWindow(home)")
        mon.waitForAbort(2)
        xbmc.executebuiltin("SetFocus(8101)")
        mon.waitForAbort(1)
        if mode == "expand":
            shot("home-expand-card")
        player.play(path, xbmcgui.ListItem("trailer", path=path), windowed=True)
        for _ in range(60):
            if mon.waitForAbort(0.1) or player.isPlayingVideo():
                break
        xbmc.executebuiltin("SetProperty(nuvio.trailer.playing,1,home)")
        mon.waitForAbort(0.8)
        out[mode] = {"home": cond("Window.IsActive(home)"), "playing": cond("Player.HasVideo"),
                     "focus8101": cond("Control.HasFocus(8101)"), "fullscreen": cond("Window.IsActive(fullscreenvideo)")}
        shot(f"home-trailer-{mode}")
        player.stop()
        xbmc.executebuiltin("ClearProperty(nuvio.trailer.playing,home)")
        mon.waitForAbort(1.5)
    xbmc.executebuiltin("Skin.Reset(nuvio.posterfocus)")
    log("trailerlayer: " + json.dumps(out))
    # Go to playlist in the side menu of a list (issue #11)
    r = json.loads(xbmc.executeJSONRPC(json.dumps({"jsonrpc": "2.0", "id": 1, "method": "VideoLibrary.GetMovies"})))
    mv = ((r.get("result") or {}).get("movies") or [{}])[0].get("movieid")
    if mv:
        xbmc.executeJSONRPC(json.dumps({"jsonrpc": "2.0", "id": 1, "method": "Playlist.Add", "params": {"playlistid": 1, "item": {"movieid": mv}}}))
    xbmc.executebuiltin("Dialog.Close(all,true)")
    xbmc.executebuiltin("ActivateWindow(Videos,videodb://movies/titles/,return)")
    mon.waitForAbort(3)
    xbmc.executebuiltin("SetFocus(9070)")
    mon.waitForAbort(1)
    log(f"playlist: len={lab('Playlist.Length(video)')} visible={cond('Control.IsVisible(9070)')} focus={cond('Control.HasFocus(9070)')}")
    shot("playlist-sidemenu")
    xbmc.executebuiltin("Action(Select)")
    mon.waitForAbort(3)
    log(f"playlist: after click window={xbmcgui.getCurrentWindowId()} playlistwin={cond('Window.IsActive(videoplaylist)')} 10028={cond('Window.IsActive(10028)')}")
    shot("playlist-after-click")
    xbmc.executeJSONRPC(json.dumps({"jsonrpc": "2.0", "id": 1, "method": "Playlist.Clear", "params": {"playlistid": 1}}))
    xbmc.executebuiltin("ActivateWindow(home)")
    mon.waitForAbort(2)


def addonsettings_test():
    """1.40.0: add-on settings in three columns, with the group tiles and picture for the video add-on."""
    xbmc.executebuiltin("Dialog.Close(all,true)")
    xbmc.executebuiltin("ActivateWindow(home)")
    mon.waitForAbort(1)
    for addon in ("plugin.video.lucent", "service.subtitles.lucent"):
        xbmc.executebuiltin(f"Addon.OpenSettings({addon})")
        for _ in range(40):
            if mon.waitForAbort(0.1) or xbmcgui.getCurrentWindowDialogId() == 10140:
                break
        mon.waitForAbort(2)
        tag = "lv" if "lucent" in addon and "video" in addon else "other"
        log(f"addonsettings {tag}: open={xbmcgui.getCurrentWindowDialogId() == 10140} heading={lab('Control.GetLabel(2)')!r} "
            f"count={HOME.getProperty('lucent.as.count')!r} "
            f"cat={HOME.getProperty('lucent.as.cat')!r} lvexp={cond('$EXP[LucentAddonSettingsLV]')} asl={HOME.getProperty('lucent.as.lv')!r}")
        shot(f"addonsettings-{tag}")
        if tag == "lv":
            xbmc.executebuiltin("SetFocus(3)")
            mon.waitForAbort(1)
            ids = []
            for _ in range(4):
                fid = xbmcgui.Window(10140).getFocusId()
                ids.append((fid, lab(f"Control.GetLabel({fid})"), cond(f"Control.IsVisible({fid})"), cond(f"Control.HasFocus({fid})")))
                xbmc.executebuiltin("Action(Down)")
                mon.waitForAbort(1.5)
            log(f"addonsettings lv category ids: {ids} cat={HOME.getProperty('lucent.as.cat')!r} current={lab('System.CurrentControl')!r}")
            shot("addonsettings-lv-play")
            xbmc.executebuiltin("SetFocus(5)")
            mon.waitForAbort(2)
            shot("addonsettings-lv-setting")
        xbmc.executebuiltin("Action(Back)")
        mon.waitForAbort(2)
        if xbmcgui.getCurrentWindowDialogId() == 10140:
            xbmc.executebuiltin("Dialog.Close(addonsettings,true)")
            mon.waitForAbort(1)


def osdclose_test():
    """1.40.2: the player menu closes by itself while a video plays (issue #4)."""
    out = {}
    xbmc.executebuiltin("Dialog.Close(all,true)")
    xbmc.executebuiltin("Skin.SetString(lucent.osdclose,3)")
    xbmc.Player().play("/tmp/ci/test.mkv")
    for _ in range(60):
        if mon.waitForAbort(0.2) or cond("Player.HasVideo"):
            break
    mon.waitForAbort(2)
    xbmc.executebuiltin("ActivateWindow(videoosd)")
    mon.waitForAbort(1)
    out["open"] = cond("Window.IsActive(videoosd)")
    mon.waitForAbort(6)
    out["closed_after_6s"] = not cond("Window.IsActive(videoosd)")
    xbmc.executebuiltin("Skin.Reset(lucent.osdclose)")
    xbmc.executebuiltin("ActivateWindow(videoosd)")
    mon.waitForAbort(6)
    out["stays_when_off"] = cond("Window.IsActive(videoosd)")
    xbmc.executebuiltin("Dialog.Close(all,true)")
    xbmc.Player().stop()
    mon.waitForAbort(2)
    xbmc.executebuiltin("ActivateWindow(home)")
    mon.waitForAbort(1)
    log("osdclose: " + json.dumps(out))


def osdintro_test():
    """2.0.1: 'Mark intro' in the player menu when the video add-on knows action=intro_mark."""
    out = {}
    xbmc.executebuiltin("Dialog.Close(all,true)")
    HOME.setProperty("lucent.lv.intromark", "1")
    HOME.setProperty("lucent.lv.replay", "1")
    xbmc.Player().play("/tmp/ci/test.mkv")
    for _ in range(60):
        if mon.waitForAbort(0.2) or cond("Player.HasVideo"):
            break
    mon.waitForAbort(2)
    xbmc.executebuiltin("ActivateWindow(videoosd)")
    mon.waitForAbort(1.5)
    out["button"] = cond("Control.IsVisible(121)")
    xbmc.executebuiltin("SetFocus(121)")
    mon.waitForAbort(1)
    out["focus"] = cond("Control.HasFocus(121)")
    shot("osd-intromark")
    xbmc.executebuiltin("Dialog.Close(all,true)")
    xbmc.Player().stop()
    mon.waitForAbort(2)
    xbmc.executebuiltin("ActivateWindow(home)")
    mon.waitForAbort(1)
    log("osdintro: " + json.dumps(out))


def _alive(seconds=20):
    """Does Kodi still answer? Asked from another thread, so a stuck Kodi does not stop this driver."""
    import threading
    box = {}
    def probe():
        box["v"] = xbmc.getInfoLabel("System.Time")
    th = threading.Thread(target=probe, daemon=True)
    th.start()
    th.join(seconds)
    return "v" in box


def _setup_look():
    xbmc.executebuiltin("RunScript(special://skin/scripts/setup.py)")
    for _ in range(40):
        if mon.waitForAbort(0.3) or cond("Window.IsVisible(Lucent_Setup.xml)"):
            break
    mon.waitForAbort(1.5)
    n = int(lab("Container(100).NumItems") or 0)
    for i in range(n):
        if lab(f"Container(100).ListItemAbsolute({i}).Label") in ("Look", "Weergave"):
            xbmc.executebuiltin(f"SetFocus(100,{i},absolute)")
            mon.waitForAbort(0.5)
            xbmc.executebuiltin("Action(Select)")
            mon.waitForAbort(1.5)
            return True
    return False


def litesetup_test():
    """Reddit: light mode switched on in the setup assistant hung Kodi. Now the skin reloads after the assistant closes."""
    out = {}
    xbmc.executebuiltin("Dialog.Close(all,true)")
    xbmc.executebuiltin("ActivateWindow(home)")
    mon.waitForAbort(1)
    out["look_step"] = _setup_look()
    out["button"] = lab("Control.GetLabel(301)")
    shot("lite-setup-before")
    xbmc.executebuiltin("SetFocus(301)")
    mon.waitForAbort(0.5)
    xbmc.executebuiltin("Action(Select)")
    mon.waitForAbort(3)
    out["alive_in_setup"] = _alive()
    out["setup_open"] = cond("Window.IsVisible(Lucent_Setup.xml)")
    out["button_after"] = lab("Control.GetLabel(301)")
    shot("lite-setup-after")
    log("litesetup step1: " + json.dumps(out))
    xbmc.executebuiltin("Action(Back)")
    mon.waitForAbort(12)
    out["alive_after_close"] = _alive()
    out["lite"] = cond("Skin.HasSetting(lucent.lite)")
    out["built"] = lab("Skin.String(lucent.lite.built)")
    xbmc.executebuiltin("ActivateWindow(home)")
    mon.waitForAbort(6)
    out["home"] = cond("Window.IsActive(home)")
    out["row1_items"] = lab("Container(8101).NumItems")
    out["visible_rows"] = [i for i in range(8101, 8111) if cond(f"Control.IsVisible({i})")]
    shot("lite-home")
    log("litesetup: " + json.dumps(out))
    xbmc.executebuiltin("Skin.Reset(lucent.lite)")             # back to normal for the old-path test
    xbmc.executebuiltin("RunScript(special://skin/scripts/settings.py,litebuild)")
    mon.waitForAbort(10)


def liteold_test():
    """The old way (reload while the assistant is open), to see whether that is what hung Kodi. Runs last."""
    out = {}
    xbmc.executebuiltin("Dialog.Close(all,true)")
    out["look_step"] = _setup_look()
    xbmc.executebuiltin("Skin.ToggleSetting(lucent.lite)")
    xbmc.sleep(400)
    xbmc.executebuiltin("RunScript(special://skin/scripts/settings.py,litebuild)")
    mon.waitForAbort(15)
    out["alive"] = _alive(30)
    log("liteold: " + json.dumps(out))
    if out["alive"]:
        shot("lite-old")


def cwrow_test():
    """2.0.1: one 'Continue watching' row from the library: in progress (film, episode) + next episode of a series."""
    out = {}
    xbmc.executebuiltin("Dialog.Close(all,true)")
    xbmc.executebuiltin("Skin.SetBool(lucent.cw.on)")
    xbmc.executebuiltin("RunScript(special://skin/scripts/continuerow.py)")
    for _ in range(30):
        if mon.waitForAbort(0.5) or HOME.getProperty("lucent.cw.count"):
            break
    out["count"] = HOME.getProperty("lucent.cw.count")
    out["items"] = [(HOME.getProperty(f"lucent.cw.{n}.type"), HOME.getProperty(f"lucent.cw.{n}.title"),
                     HOME.getProperty(f"lucent.cw.{n}.sub"), HOME.getProperty(f"lucent.cw.{n}.percent"))
                    for n in range(1, int(out["count"] or 0) + 1)]
    xbmc.executebuiltin("ActivateWindow(home)")
    mon.waitForAbort(2)
    xbmc.executebuiltin("Dialog.Close(all,true)")          # the video add-on can ask something at start (skip intro)
    mon.waitForAbort(1)
    xbmc.executebuiltin("SetFocus(8092)")
    mon.waitForAbort(2)
    out["row_visible"] = cond("Control.IsVisible(8092)")
    out["focus"] = cond("Control.HasFocus(8092)")
    out["list_items"] = lab("Container(8092).NumItems")
    shot("cw-row")
    for tab, name, rename in ((1, "films", ""), (2, "streaming", ""), (2, "series", "Series"), (0, "home", "")):
        if rename:
            xbmc.executebuiltin("Control.SetFocus(9000,0)")
            xbmc.executebuiltin(f"Skin.SetString(nuvio.tab3.label,{rename})")
            mon.waitForAbort(2.5)
        xbmc.executebuiltin(f"Control.SetFocus(9000,{tab})")
        mon.waitForAbort(3.5)
        out[f"tab_{name}"] = [lab("Container(9000).ListItem.Label"), HOME.getProperty("lucent.cw.kind"),
                              cond("Control.IsVisible(8092)"), HOME.getProperty("lucent.cw.show"),
                              HOME.getProperty("lucent.cw.count"), HOME.getProperty("lucent.cw.1.title")]
        shot(f"cw-tab-{name}")
    xbmc.executebuiltin("Skin.SetString(nuvio.tab3.label,Streaming)")
    xbmc.executebuiltin("Control.SetFocus(9000,1)")
    mon.waitForAbort(3.5)
    xbmc.executebuiltin("SetFocus(8092)")
    mon.waitForAbort(1)
    xbmc.executebuiltin("Action(Right)")
    mon.waitForAbort(1.5)
    shot("cw-row-2")
    # the calendar button is not on the info page of a film in the library
    xbmc.executebuiltin("ActivateWindow(Videos,videodb://movies/titles/,return)")
    for _ in range(20):
        if mon.waitForAbort(0.5) or int(lab("Container.NumItems") or 0) > 0:
            break
    n = int(lab("Container.NumItems") or 0)
    for i in range(n + 1):
        if lab(f"Container.ListItemAbsolute({i}).Label") == "Lib Film":
            xbmc.executebuiltin(f"SetFocus(50,{i},absolute)")
            xbmc.executebuiltin(f"SetFocus(51,{i},absolute)")
    mon.waitForAbort(1)
    xbmc.executebuiltin("Action(Info)")
    for _ in range(20):
        if mon.waitForAbort(0.5) or cond("Window.IsVisible(movieinformation)"):
            break
    mon.waitForAbort(2)
    out["info_title"] = lab("ListItem.Title")
    out["info_dbid"] = lab("ListItem.DBID")
    out["bell_button"] = cond("Control.IsVisible(23)")
    out["more_button"] = cond("Control.IsVisible(25)")
    out["lv_version"] = lab("System.AddonVersion(plugin.video.lucent)")
    try:
        import sys as _s
        _s.path.insert(0, xbmcvfs.translatePath("special://skin/scripts/"))
        import importlib
        import info as _i
        importlib.reload(_i)
        out["lv_version_parsed"] = list(_i.lv_version())
    except Exception as error:  # noqa: BLE001
        out["lv_version_parsed"] = str(error)
    shot("cw-info-libfilm")
    xbmc.executebuiltin("Dialog.Close(all,true)")
    xbmc.executebuiltin("ActivateWindow(home)")
    mon.waitForAbort(1)
    log("cwrow: " + json.dumps(out))


def perf_test():
    """Speed and memory (lucent-performance): Kodi's memory on Home, after opening windows and after 2 minutes idle;
    how long Kodi ran before Home was ready; how many scripts were started and how many log errors there are."""
    import re as _re
    out = {}
    def rss():
        try:
            for ln in open("/proc/self/status"):
                if ln.startswith("VmRSS:"):
                    return int(ln.split()[1]) // 1024
        except OSError:
            return -1
    def uptime():
        try:
            ticks = os.sysconf(os.sysconf_names["SC_CLK_TCK"])
            start = int(open("/proc/self/stat").read().rsplit(")", 1)[1].split()[19]) / ticks
            return round(float(open("/proc/uptime").read().split()[0]) - start, 1)
        except Exception:  # noqa: BLE001
            return -1
    out["kodi_seconds_at_home_ready"] = HOME_READY.get("uptime")
    xbmc.executebuiltin("Dialog.Close(all,true)")
    xbmc.executebuiltin("ActivateWindow(home)")
    mon.waitForAbort(5)
    out["mb_home"] = rss()
    for win in ("Videos,videodb://movies/titles/,return", "Settings", "SkinSettings", "home"):
        xbmc.executebuiltin(f"ActivateWindow({win})")
        mon.waitForAbort(4)
    out["mb_after_windows"] = rss()
    xbmc.executebuiltin("ActivateWindow(home)")
    mon.waitForAbort(120)
    out["mb_after_2min_idle"] = rss()
    out["kodi_seconds_total"] = uptime()
    try:
        with open(xbmcvfs.translatePath("special://logpath/kodi.log"), encoding="utf-8", errors="replace") as fh:
            text = fh.read()
        starts = [ln for ln in text.splitlines() if "CPythonInvoker" in ln and "the source file to load is" in ln]
        out["scripts_started"] = len(starts)
        out["skin_scripts_started"] = len([ln for ln in starts if "special://skin/" in ln or "skin.lucent" in ln])
        names = {}
        for ln in starts:
            m = _re.search(r"scripts/(\w+)\.py", ln)
            if m:
                names[m.group(1)] = names.get(m.group(1), 0) + 1
        out["per_script"] = dict(sorted(names.items(), key=lambda kv: -kv[1])[:12])
        out["unknown_addon_id"] = text.count("Unknown addon id")
        out["parse_errors"] = text.count("Error parsing boolean expression")
        out["log_errors"] = len([ln for ln in text.splitlines() if " error <" in ln])
    except OSError as error:
        out["log"] = str(error)
    log("perf: " + json.dumps(out))


def firststart_test():
    """Speed point 1: a new installation runs its one-time jobs one after the other in startup.py (not 6 scripts from Home)."""
    import importlib
    import sys as _s
    _s.path.insert(0, xbmcvfs.translatePath("special://skin/scripts/"))
    out = {}
    try:
        text = open(xbmcvfs.translatePath("special://logpath/kodi.log"), encoding="utf-8", errors="replace").read()
        starts = [ln for ln in text.splitlines() if "the source file to load is" in ln and "skin/scripts/" in ln]
        out["home_scripts_at_start"] = sorted({ln.split("skin/scripts/")[1].split(".py")[0] for ln in starts})
    except OSError as error:
        out["log"] = str(error)
    for key in ("lucent.lite.checked", "lucent.addonw4"):
        xbmc.executebuiltin(f"Skin.Reset({key})")
    mon.waitForAbort(1)
    t = time.time()
    try:
        import startup
        importlib.reload(startup)
        out["reload"] = startup.first_start()
    except Exception as error:  # noqa: BLE001
        out["error"] = f"{type(error).__name__}: {error}"
    out["seconds"] = round(time.time() - t, 1)
    out["lite_checked"] = lab("Skin.String(lucent.lite.checked)")
    out["addonw4"] = lab("Skin.String(lucent.addonw4)")
    out["alive"] = bool(lab("System.Time"))
    log("firststart: " + json.dumps(out))


def remember_test():
    """Issue #9: going back into a folder (Films ...) starts on the title you were on."""
    out = {}
    path = "plugin://plugin.video.fakefen/?mode=showcase"
    for rnd in (1, 2):
        xbmc.executebuiltin("Dialog.Close(all,true)")
        xbmc.executebuiltin(f"ActivateWindow(Videos,{path},return)")
        for _ in range(40):
            if mon.waitForAbort(0.3) or int(lab("Container.NumItems") or 0) > 0:
                break
        mon.waitForAbort(2.5)
        out[f"label_{rnd}"] = lab("ListItem.Label")
        if rnd == 1:
            view = xbmcgui.Window(xbmcgui.getCurrentWindowId()).getFocusId()
            for _ in range(5):
                xbmc.executebuiltin("Action(Right)" if cond("Container.Content(movies)") and view in (51, 52, 70, 72) else "Action(Down)")
                mon.waitForAbort(0.4)
            mon.waitForAbort(2)
            out["picked"] = lab("ListItem.Label")
            xbmc.executebuiltin("ActivateWindow(home)")
            mon.waitForAbort(3)
    out["back_on_it"] = out.get("label_2") == out.get("picked")
    shot("remember")
    xbmc.executebuiltin("ActivateWindow(home)")
    mon.waitForAbort(1)
    log("remember: " + json.dumps(out))


def nolv_test():
    """2.1.1: not tied to one video add-on - who plays titles Lucent opens itself, For you only on Home."""
    import importlib
    import sys as _s
    _s.path.insert(0, xbmcvfs.translatePath("special://skin/scripts/"))
    out = {}
    try:
        import info
        importlib.reload(info)
        out["player_with_lv"] = info.title_player()
        out["film_lv"] = info.lv_play_url("movie", 603)
        real = info.lv_on
        info.lv_on = lambda: False
        out["player_without"] = info.title_player()
        out["can_open_without"] = info.lv_open_with()
        info.title_player = lambda: "th"
        out["film_th"] = info.lv_play_url("movie", 603)
        out["show_th"] = info.lv_play_url("tv", 1399)
        out["ep_th"] = info.episode_play_url(1399, 2, 3)
        info.lv_on = real
        importlib.reload(info)
    except Exception as error:  # noqa: BLE001
        out["error"] = f"{type(error).__name__}: {error}"
    for _ in range(40):                                    # the video add-on asks something at start: answer No
        if mon.waitForAbort(0.5):
            break
        if cond("Window.IsVisible(yesnodialog)"):
            xbmc.executebuiltin("Dialog.Close(all,true)")
            mon.waitForAbort(1)
            break
    xbmc.executebuiltin("Dialog.Close(all,true)")
    xbmc.executebuiltin("Skin.SetString(nuvio.tab1.icon,icons/home.png)")
    xbmc.executebuiltin("Skin.Reset(lucent.fy.off)")
    try:
        import foryou
        importlib.reload(foryou)
        out["home_tab"] = foryou.home_tab()
        HOME.setProperty("lucent.fy.tab", foryou.home_tab())
    except Exception as error:  # noqa: BLE001
        out["home_tab"] = str(error)
    HOME.setProperty("lucent.fy.count", "3")
    HOME.setProperty("lucent.fy.label", "Tonight for you")
    for n in (1, 2, 3):
        HOME.setProperty(f"lucent.fy.{n}.title", f"Title {n}")
    xbmc.executebuiltin("ActivateWindow(home)")
    mon.waitForAbort(2)
    for tab in (0, 1):
        xbmc.executebuiltin(f"Control.SetFocus(9000,{tab})")
        mon.waitForAbort(2)
        xbmc.executebuiltin("Dialog.Close(all,true)")
        mon.waitForAbort(0.5)
        out[f"foryou_tab{tab + 1}"] = cond("Control.IsVisible(9989)")
        out[f"icon_tab{tab + 1}"] = lab("Container(9000).ListItem.Icon")
        shot(f"nolv-tab{tab + 1}")
    xbmc.executebuiltin("Skin.SetBool(lucent.fy.off)")
    HOME.clearProperty("lucent.fy.count")
    xbmc.executebuiltin("Skin.SetString(nuvio.tab1.icon,icons/movies.png)")
    xbmc.executebuiltin("ActivateWindow(InterfaceSettings)")
    mon.waitForAbort(3)
    shot("nolv-level")
    xbmc.executebuiltin("ActivateWindow(home)")
    mon.waitForAbort(1)
    log("nolv: " + json.dumps(out))


def mousehome_test():
    """Issue #13: with a mouse, the first posters of a Home row must not open the side menu."""
    import subprocess
    out = {}
    def move(x, y):
        try:
            subprocess.run(["xdotool", "mousemove", str(x), str(y)], timeout=5)
        except Exception as error:  # noqa: BLE001
            log(f"xdotool error {error!r}")
        mon.waitForAbort(1.2)
    xbmc.executeJSONRPC(json.dumps({"jsonrpc": "2.0", "id": 1, "method": "Settings.SetSettingValue",
                                     "params": {"setting": "input.enablemouse", "value": True}}))
    try:
        subprocess.run(["xdotool", "search", "--name", "Kodi", "windowactivate", "--sync"], timeout=5)
    except Exception as error:  # noqa: BLE001
        log(f"xdotool error {error!r}")
    move(900, 300)
    move(910, 310)
    xbmc.executebuiltin("Dialog.Close(all,true)")
    xbmc.executebuiltin("ActivateWindow(home)")
    mon.waitForAbort(2)
    xbmc.executebuiltin("SetFocus(9100)")
    mon.waitForAbort(1.5)
    out["rows_focus"] = not cond("Control.HasFocus(9000)")
    for name, x, y in (("poster1", 250, 820), ("poster2", 380, 820), ("rowtitle", 300, 600),
                       ("band_sport", 300, 640), ("band_cal", 220, 470), ("band_cal_icon", 90, 470)):
        out[name + "_before"] = lab("System.CurrentControlID")
        move(x, y)
        out[name + "_menu"] = cond("Control.HasFocus(9000)")
        out[name + "_after"] = lab("System.CurrentControlID")
        shot(f"mouse-{name}")
        xbmc.executebuiltin("SetFocus(9100)")
        move(1700, 100)
        xbmc.executebuiltin("SetFocus(9100)")
        mon.waitForAbort(0.8)
    move(60, 300)
    out["icon_menu"] = cond("Control.HasFocus(9000)")
    shot("mouse-icon")
    move(260, 300)
    out["label_menu"] = cond("Control.HasFocus(9000)")
    out["label_item"] = lab("Container(9000).ListItem.Label")
    shot("mouse-label")
    move(1700, 100)
    xbmc.executebuiltin("SetFocus(9100)")
    mon.waitForAbort(1)
    log("mousehome: " + json.dumps(out))


def owntrakt_test():
    """2.0.1: Lucent's own Trakt login (traktlogin.py) comes before the login of a video add-on; Skin settings > Follow."""
    import importlib
    import sys as _s
    _s.path.insert(0, xbmcvfs.translatePath("special://skin/scripts/"))
    out = {}
    own = xbmcvfs.translatePath("special://profile/addon_data/skin.lucent/trakt.json")
    lv = xbmcvfs.translatePath("special://profile/addon_data/plugin.video.lucent/")
    os.makedirs(os.path.dirname(own), exist_ok=True)
    os.makedirs(lv, exist_ok=True)
    try:
        json.dump({"access_token": "lv-token", "refresh_token": "r", "expires_at": time.time() + 86400 * 30},
                  open(os.path.join(lv, "trakt.json"), "w"))
        json.dump({"trakt_client_id": "lv-client"}, open(os.path.join(lv, "keys.json"), "w"))
        json.dump({"client_id": "own-client", "client_secret": "own-secret", "access_token": "own-token",
                   "refresh_token": "r", "expires_at": time.time() + 86400 * 30, "user": "ci-user"}, open(own, "w"))
        import info
        import traktlogin
        importlib.reload(traktlogin)
        importlib.reload(info)
        tr = info.Trakt()
        out["own_first"] = tr.own and tr.client_id == "own-client" and tr.token == "own-token"
        os.remove(own)
        tr = info.Trakt()
        out["lv_fallback"] = (not tr.own) and tr.token == "lv-token"
        out["available"] = info.trakt_available()
    except Exception as error:  # noqa: BLE001
        out["error"] = f"{type(error).__name__}: {error}"
    for name in ("trakt.json", "keys.json"):
        if os.path.exists(os.path.join(lv, name)):
            os.remove(os.path.join(lv, name))
    xbmc.executebuiltin("Dialog.Close(all,true)")
    xbmc.executebuiltin("Skin.Reset(lucent.trakt.user)")
    xbmc.executebuiltin("ActivateWindow(SkinSettings)")
    mon.waitForAbort(2.5)
    n = int(lab("Container(9000).NumItems") or 0)
    for i in range(n):
        if lab(f"Container(9000).ListItemAbsolute({i}).Property(cat)") == "6":
            xbmc.executebuiltin(f"SetFocus(9000,{i},absolute)")
    mon.waitForAbort(1.3)
    out["button"] = cond("Control.IsVisible(1601)")
    xbmc.executebuiltin("SetFocus(1601)")
    mon.waitForAbort(1)
    shot("trakt-follow-out")
    xbmc.executebuiltin("Skin.SetString(lucent.trakt.user,ci-user)")
    mon.waitForAbort(1)
    shot("trakt-follow-in")
    xbmc.executebuiltin("Skin.Reset(lucent.trakt.user)")
    xbmc.executebuiltin("Action(Select)")
    for _ in range(20):
        if mon.waitForAbort(0.3) or cond("Window.IsVisible(yesnodialog)"):
            break
    mon.waitForAbort(1)
    out["keys_dialog"] = cond("Window.IsVisible(yesnodialog)")
    shot("trakt-keys")
    xbmc.executebuiltin("Dialog.Close(all,true)")
    mon.waitForAbort(1)
    xbmc.executebuiltin("Action(Back)")
    xbmc.executebuiltin("RunScript(special://skin/scripts/setup.py)")
    for _ in range(30):
        if mon.waitForAbort(0.3) or cond("Window.IsVisible(Lucent_Setup.xml)"):
            break
    mon.waitForAbort(1.5)
    for _ in range(3):
        xbmc.executebuiltin("SetFocus(100)")
        xbmc.executebuiltin("Action(Down)")
        mon.waitForAbort(0.3)
    xbmc.executebuiltin("Action(Select)")
    mon.waitForAbort(2.5)
    shot("trakt-setup")
    xbmc.executebuiltin("Dialog.Close(all,true)")
    xbmc.executebuiltin("ActivateWindow(home)")
    mon.waitForAbort(1)
    log("owntrakt: " + json.dumps(out))


def menus_test():
    """2.0 RC: every category of Settings and Skin settings, for a look at all menus."""
    out = {}
    for window, prefix in (("Settings", "set"), ("SkinSettings", "skin")):
        xbmc.executebuiltin("Dialog.Close(all,true)")
        xbmc.executebuiltin(f"ActivateWindow({window})")
        mon.waitForAbort(2.5)
        n = int(lab("Container(9000).NumItems") or 0)
        out[prefix] = [lab(f"Container(9000).ListItemAbsolute({i}).Label") for i in range(n)]
        for i in range(n):
            xbmc.executebuiltin(f"SetFocus(9000,{i},absolute)")
            mon.waitForAbort(1.3)
            shot(f"menus-{prefix}-{i}")
        xbmc.executebuiltin("Action(Back)")
        mon.waitForAbort(1)
    xbmc.executebuiltin("ActivateWindow(home)")
    mon.waitForAbort(1.5)
    xbmc.executebuiltin("SetFocus(9000)")
    mon.waitForAbort(1)
    shot("menus-home")
    log("menus: " + json.dumps(out))


def s56eps_test():
    """1.43.0: the season page shows its episodes as a row, a timeline, cards or a list with flags (side menu)."""
    out = {}
    xbmc.executebuiltin("Dialog.Close(all,true)")
    xbmc.executebuiltin("ActivateWindow(Videos,plugin://plugin.video.fakefen/?mode=showcase_seasons,return)")
    for _ in range(40):
        if mon.waitForAbort(0.3) or (cond("Control.IsVisible(56)") and int(lab("Container(5601).NumItems") or 0) > 0):
            break
    xbmc.executebuiltin("SetFocus(56,1,absolute)")         # the first season, not '..'
    mon.waitForAbort(2.5)
    out["page"] = cond("Control.IsVisible(56)")
    out["episodes"] = lab("Container(5601).NumItems")
    for style in ("timeline", "cards", "flags", ""):
        xbmc.executebuiltin(f"Skin.SetString(lucent.s56.eps,{style})" if style else "Skin.Reset(lucent.s56.eps)")
        xbmc.executebuiltin("SetFocus(5601)")
        xbmc.executebuiltin("Action(Right)")
        mon.waitForAbort(2)
        shot(f"s56-{style or 'row'}")
    xbmc.executebuiltin("SetFocus(56)")
    xbmc.executebuiltin("Action(Left)")
    mon.waitForAbort(1)
    out["menu"] = cond("ControlGroup(9050).HasFocus")
    out["button"] = cond("Control.IsVisible(9072)")
    xbmc.executebuiltin("SetFocus(9072)")
    mon.waitForAbort(0.8)
    shot("s56-menu")
    xbmc.executebuiltin("Action(Back)")
    xbmc.executebuiltin("ActivateWindow(home)")
    mon.waitForAbort(1)
    log("s56eps: " + json.dumps(out))


def wnitem_test():
    """1.43.0: What's new - OK on a change opens it on its own with a picture, the explanation and steps."""
    out = {}
    xbmc.executebuiltin("Dialog.Close(all,true)")
    xbmc.executebuiltin("RunScript(special://skin/scripts/whatsnew.py)")
    for _ in range(30):
        if mon.waitForAbort(0.3) or cond("Control.IsVisible(200)"):
            break
    mon.waitForAbort(1)
    xbmc.executebuiltin("SetFocus(200)")
    mon.waitForAbort(0.8)
    shot("wn-list")
    xbmc.executebuiltin("Action(Select)")
    for _ in range(20):
        if mon.waitForAbort(0.3) or cond("Window.IsVisible(Lucent_WhatsNewItem.xml)"):
            break
    mon.waitForAbort(1)
    out["open"] = cond("Window.IsVisible(Lucent_WhatsNewItem.xml)")
    shot("wn-item")
    xbmc.executebuiltin("SetFocus(12)")
    xbmc.executebuiltin("Action(Select)")
    mon.waitForAbort(1)
    shot("wn-item-next")
    xbmc.executebuiltin("Action(Back)")
    mon.waitForAbort(0.5)
    out["back_to_list"] = cond("Control.IsVisible(200)")
    xbmc.executebuiltin("Action(Back)")
    xbmc.executebuiltin("Action(Back)")
    xbmc.executebuiltin("ActivateWindow(home)")
    mon.waitForAbort(1)
    log("wnitem: " + json.dumps(out))


def newviews_test():
    """1.41.0 / 1.42.0: the newer views (films, series, episodes, music, sets, recently added) and the side menu in each."""
    out = {}
    if int(xbmc.executeJSONRPC('{"jsonrpc":"2.0","id":1,"method":"AudioLibrary.GetAlbums","params":{"limits":{"end":1}}}').count('"albumid"')) == 0:
        xbmc.executebuiltin("UpdateLibrary(music,/tmp/ci/music/)")
        for _ in range(60):
            if mon.waitForAbort(1) or not cond("Library.IsScanningMusic"):
                break
    runs = (("Videos", "plugin://plugin.video.fakefen/?mode=showcase", (70, 71, 72, 73, 87)),
            ("Videos", "plugin://plugin.video.fakefen/?mode=showcase_tv", (74, 75, 78)),
            ("Videos", "plugin://plugin.video.fakefen/?mode=showcase_ep", (76, 77, 79, 80)),
            ("Videos", "plugin://plugin.video.fakefen/?mode=showcase_sets", (86,)),
            ("Music", "musicdb://albums/", (81, 84, 85)),
            ("Music", "musicdb://artists/", (82,)),
            ("Music", "musicdb://songs/", (83,)))
    for window, path, views in runs:
        xbmc.executebuiltin("Dialog.Close(all,true)")
        xbmc.executebuiltin(f"ActivateWindow({window},{path},return)")
        for _ in range(30):
            if mon.waitForAbort(0.3) or (cond(f"Window.IsActive({window.lower()})") and int(lab("Container.NumItems") or 0) > 0):
                break
        mon.waitForAbort(1)
        for view in views:
            xbmc.executebuiltin(f"Container.SetViewMode({view})")
            mon.waitForAbort(2)
            xbmc.executebuiltin(f"SetFocus({view})")
            xbmc.executebuiltin("Action(Down)" if view in (73, 74, 77, 79, 80, 83, 87) else "Action(Right)")
            mon.waitForAbort(2.5)
            row = {"visible": cond(f"Control.IsVisible({view})"), "focus": cond(f"Control.HasFocus({view})"),
                   "mode": lab("Container.Viewmode"), "item": lab("ListItem.Label"), "content": lab("Container.Content")}
            shot(f"view-{view}")
            # the side menu: Left on the first item opens it, Right brings you back to the view
            xbmc.executebuiltin(f"SetFocus({view},0,absolute)")
            mon.waitForAbort(0.8)
            xbmc.executebuiltin("Action(Left)")
            mon.waitForAbort(1.2)
            row["menu_open"] = cond("ControlGroup(9050).HasFocus")
            if view in (72, 81):
                shot(f"view-{view}-menu")
            xbmc.executebuiltin("Action(Right)")
            mon.waitForAbort(1)
            row["menu_back"] = cond(f"Control.HasFocus({view})")
            out[view] = row
        xbmc.executebuiltin("Container.SetViewMode(50)" if window == "Music" else "Container.SetViewMode(51)")
        mon.waitForAbort(1)
    xbmc.executebuiltin("ActivateWindow(home)")
    mon.waitForAbort(1)
    log("newviews: " + json.dumps(out))

def lvtrakt_test():
    """1.39.0: the Trakt login of the video add-on is used (calendar, lists, watched) before Seren's."""
    import importlib
    import sys as _s
    _s.path.insert(0, xbmcvfs.translatePath("special://skin/scripts/"))
    data = xbmcvfs.translatePath("special://profile/addon_data/plugin.video.lucent/")
    os.makedirs(data, exist_ok=True)
    keep = {}
    for name in ("trakt.json", "keys.json"):
        p = os.path.join(data, name)
        keep[name] = open(p).read() if os.path.exists(p) else None
    try:
        json.dump({"access_token": "ci-token", "refresh_token": "ci-refresh", "expires_at": time.time() + 86400}, open(os.path.join(data, "trakt.json"), "w"))
        json.dump({"trakt_client_id": "ci-client"}, open(os.path.join(data, "keys.json"), "w"))
        import info
        importlib.reload(info)
        tr = info.Trakt()
        log(f"lvtrakt: lv client={tr.client_id == 'ci-client'} token={tr.token == 'ci-token'} seren={tr.seren} available={info.trakt_available()}")
        json.dump({"access_token": "ci-token", "expires_at": time.time() - 10}, open(os.path.join(data, "trakt.json"), "w"))
        log(f"lvtrakt: expired -> lv={info.lv_trakt() != ('', '')}")
    except Exception as error:  # noqa: BLE001
        log(f"lvtrakt: error {type(error).__name__}: {error}")
    finally:
        for name, text in keep.items():
            p = os.path.join(data, name)
            if text is None:
                if os.path.exists(p):
                    os.remove(p)
            else:
                open(p, "w").write(text)


def music_fav_test():
    """1.34.5: sort on last watched, one favourite as widget, the Covers view and the bigger cover for albums."""
    import sys as _s
    import threading
    _s.path.insert(0, xbmcvfs.translatePath("special://skin/scripts"))
    import menu as _m
    log(f"sorts: {[k for k, _n in _m.SORTS()]}")
    xbmc.executeJSONRPC(json.dumps({"jsonrpc": "2.0", "id": 1, "method": "Favourites.AddFavourite",
                                    "params": {"title": "CI In progress", "type": "window", "window": "videos", "windowparameter": "videodb://inprogresstvshows/"}}))
    res = []
    th = threading.Thread(target=lambda: res.append(_m.pick_favourite()))
    th.start()
    for _ in range(20):
        if cond("Window.IsActive(selectdialog)"):
            break
        mon.waitForAbort(0.5)
    mon.waitForAbort(1)
    shot("fav-pick")
    xbmc.executebuiltin("Action(Select)")
    th.join(10)
    log(f"fav: picked {res}")
    # music
    xbmc.executebuiltin("UpdateLibrary(music,/tmp/ci/music/)")
    for _ in range(40):
        mon.waitForAbort(1)
        r = json.loads(xbmc.executeJSONRPC(json.dumps({"jsonrpc": "2.0", "id": 1, "method": "AudioLibrary.GetAlbums", "params": {"properties": ["artist", "title"]}})))
        albums = (r.get("result") or {}).get("albums") or []
        if len(albums) >= 3 and not cond("Library.IsScanningMusic"):
            break
    log(f"music: albums {[(a.get('title'), a.get('artist')) for a in albums]}")
    xbmc.executebuiltin("ActivateWindow(Music,musicdb://albums/,return)")
    mon.waitForAbort(3)
    xbmc.executebuiltin("Container.SetViewMode(54)")
    mon.waitForAbort(2)
    log(f"music: view={lab('Container.Viewmode')} 54={cond('Control.IsVisible(54)')} item={lab('ListItem.Label')} artist={lab('ListItem.Artist')}")
    shot("music-covers")
    xbmc.executebuiltin("Container.SetViewMode(50)")
    mon.waitForAbort(2)
    for _ in range(3):
        if not cond("ListItem.IsParentFolder"):
            break
        key("Down")
        mon.waitForAbort(1)
    log(f"music: view={lab('Container.Viewmode')} 50={cond('Control.IsVisible(50)')} item={lab('ListItem.Label')} icon={lab('ListItem.Icon')[:60]}")
    shot("music-list")
    xbmc.executebuiltin("ActivateWindow(home)")
    mon.waitForAbort(2)


def smallposter_test():
    """1.34.6: small posters with names: the focused poster grows up and sideways, not over its name."""
    res = json.loads(xbmc.executeJSONRPC(json.dumps({"jsonrpc": "2.0", "id": 1, "method": "Files.GetDirectory",
        "params": {"directory": "plugin://script.lucent.library/?action=lib&kind=newin&only=movie", "media": "video"}})))
    log(f"librow: only=movie items={len((res.get('result') or {}).get('files') or [])} error={res.get('error')}")
    xbmc.executebuiltin("Skin.SetBool(lucent.posters.small)")
    xbmc.executebuiltin("Skin.Reset(nuvio.posterlabels.hide)")
    xbmc.executebuiltin("ReloadSkin()")
    mon.waitForAbort(8)
    xbmc.executebuiltin("ActivateWindow(home)")
    mon.waitForAbort(3)
    xbmc.executebuiltin("Control.SetFocus(9000,1)")
    mon.waitForAbort(2)
    xbmc.executebuiltin("SetFocus(9100)")
    mon.waitForAbort(3)
    log(f"smallposter: focus={lab('System.CurrentControlId')} item={lab('Container(' + lab('System.CurrentControlId') + ').ListItem.Label')}")
    shot("smallposter-focus")
    xbmc.executebuiltin("Skin.Reset(lucent.posters.small)")
    xbmc.executebuiltin("Skin.SetBool(nuvio.posterlabels.hide)")
    xbmc.executebuiltin("ReloadSkin()")
    mon.waitForAbort(6)


def alwayson_test():
    """1.34.7: Subtitles always on: a new video starts with a subtitle, also when the sound is in your language.
    (On CI a video only really starts after ~9 s: there is no sound card, Kodi waits for it first.)"""
    pl = xbmc.Player()
    out = {}
    for setting in (True, False):
        xbmc.executebuiltin("Skin.SetBool(lucent.subs.alwayson)" if setting else "Skin.Reset(lucent.subs.alwayson)")
        mon.waitForAbort(1)
        for f in ("nodef-eng", "same-eng"):
            started = HOME.getProperty("lucent.play.start")
            xbmc.executebuiltin(f"PlayMedia(/tmp/ci/{f}.mkv)")
            for _ in range(60):                         # until Lucent's watcher saw the start (onAVStarted)
                if HOME.getProperty("lucent.play.start") != started:
                    break
                mon.waitForAbort(0.5)
            mon.waitForAbort(9)                          # the watcher waits 4 s, then checks
            out[f"{'on' if setting else 'off'}:{f}"] = (cond("VideoPlayer.SubtitlesEnabled"), lab("VideoPlayer.SubtitlesLanguage"))
            if f == "nodef-eng" and setting:
                shot("alwayson-play")
            pl.stop()
            mon.waitForAbort(3)
    log(f"alwayson: {out}")
    xbmc.executebuiltin("Skin.Reset(lucent.subs.alwayson)")


def omdblist_test():
    """1.34.8: Rotten Tomatoes / Metacritic of the title under the cursor in the lists (no info page)."""
    d = xbmcvfs.translatePath("special://profile/addon_data/skin.lucent/")
    with open(os.path.join(d, "omdb.key"), "w") as fh:
        fh.write("cikey1234")
    mon.waitForAbort(31)                                  # the helper reads the key again after 30 s
    xbmc.executebuiltin("ActivateWindow(Videos,videodb://movies/titles/,return)")
    mon.waitForAbort(3)
    for view in (51, 50):
        xbmc.executebuiltin(f"Container.SetViewMode({view})")
        mon.waitForAbort(2)
        xbmc.executebuiltin(f"SetFocus({view})")
        mon.waitForAbort(1)
        for _ in range(4):
            if lab("ListItem.DBType") == "movie":
                break
            key("Down")
            mon.waitForAbort(1)
        mon.waitForAbort(4)
        log(f"omdblist: diag helper={HOME.getProperty('lucent.helper')} now={time.time():.1f} videos={cond('Window.IsActive(videos)')} "
            f"content={lab('Container.Content')} c_movies={cond('Container.Content(movies)')} imdb={lab('ListItem.UniqueID(imdb)')!r} "
            f"imdbnr={lab('ListItem.IMDBNumber')!r} dbtype={lab('ListItem.DBType')} dbid={lab('ListItem.DBID')} off={cond('Skin.HasSetting(lucent.omdb.lists.off)')}")
        p = {k: HOME.getProperty("lucent.omdbl." + k) for k in ("rt", "rtc", "mc", "mcc", "imdb", "for")}
        log(f"omdblist: view={lab('Container.Viewmode')} item={lab('ListItem.Label')} props={p}")
        shot(f"omdblist-{view}")
        key("Up")
        mon.waitForAbort(2)
        log(f"omdblist: on '..' for={HOME.getProperty('lucent.omdbl.for')!r}")
        key("Down")
        mon.waitForAbort(3)
        log(f"omdblist: back on {lab('ListItem.Label')!r} rt={HOME.getProperty('lucent.omdbl.rt')!r} mc={HOME.getProperty('lucent.omdbl.mc')!r}")
        key("Up")
        mon.waitForAbort(1)
    os.remove(os.path.join(d, "omdb.key"))
    xbmc.executebuiltin("ActivateWindow(home)")
    mon.waitForAbort(2)


def flicker_test():
    """the video add-on marks many titles watched: does the focus jump to the side menu while the library changes?"""
    import threading
    r = json.loads(xbmc.executeJSONRPC(json.dumps({"jsonrpc": "2.0", "id": 1, "method": "VideoLibrary.GetMovies", "params": {"properties": ["playcount"]}})))
    movies = (r.get("result") or {}).get("movies") or []
    out = {"movies": len(movies)}
    if not movies:
        log("flicker: " + json.dumps(out))
        return
    mid = movies[0]["movieid"]

    def run(name, focus):
        xbmc.executebuiltin(focus)
        mon.waitForAbort(2.5)
        start_id = lab("System.CurrentControlId")
        seen = []
        stop = []

        def sample():
            while not stop and not mon.abortRequested():
                cid = lab("System.CurrentControlId") + ("/menu" if cond("Control.HasFocus(9000)") else "")
                if not seen or seen[-1] != cid:
                    seen.append(cid)
                time.sleep(0.03)
        th = threading.Thread(target=sample)
        th.start()
        for n in range(30):
            xbmc.executeJSONRPC(json.dumps({"jsonrpc": "2.0", "id": 1, "method": "VideoLibrary.SetMovieDetails",
                                            "params": {"movieid": mid, "playcount": n % 2}}))
            mon.waitForAbort(0.2)
        mon.waitForAbort(1.5)
        stop.append(1)
        th.join(5)
        out[name] = {"start": start_id, "changes": len(seen) - 1, "seen": seen[:12], "end": lab("System.CurrentControlId")}
        shot(f"flicker-{name}")

    tab = None
    for i in range(16):
        xbmc.executebuiltin(f"Control.SetFocus(9000,{i})")
        mon.waitForAbort(0.4)
        if cond("String.Contains(Container(9000).ListItem.Property(act),AddonBrowser)"):
            tab = i
            break
    out["addontab"] = tab
    if tab is not None:
        run("addons", "SetFocus(9340)")
    xbmc.executebuiltin("Control.SetFocus(9000,0)")
    mon.waitForAbort(2)
    run("homerow", "SetFocus(9100)")
    xbmc.executeJSONRPC(json.dumps({"jsonrpc": "2.0", "id": 1, "method": "VideoLibrary.SetMovieDetails", "params": {"movieid": mid, "playcount": movies[0].get("playcount", 0)}}))
    xbmc.executebuiltin("Control.SetFocus(9000,0)")
    log("flicker: " + json.dumps(out))


def intro_test():
    """2.1.3: the intro shows nothing on a real box (the sound plays). Three copies as normal windows: full, without the
    fade-out at the end, and without any animation - a picture of each after 3 s."""
    xbmc.executebuiltin("Dialog.Close(all,true)")
    xbmc.executebuiltin("Skin.Reset(lucent.intro.off)")
    out = {"off": cond("Skin.HasSetting(lucent.intro.off)")}
    for wid in (1195, 1196, 1197):
        xbmc.executebuiltin(f"ActivateWindow({wid})")
        mon.waitForAbort(3)
        out[wid] = [cond(f"Window.IsVisible({wid})"), lab("System.CurrentWindow"), lab("Window.Property(xmlfile)")]
        xbmc.executebuiltin(f"TakeScreenshot({OUT}/{TAG}-intro-{wid}.png,sync)")
        mon.waitForAbort(2)
        xbmc.executebuiltin("ActivateWindow(home)")
        mon.waitForAbort(2)
    log("intro: " + json.dumps(out))


def introsound_test():
    """2.1.3: the switch 'Sound with the intro' (1225) sits between Intro at start (1110) and the next row (1111)."""
    fid = lambda: lab("System.CurrentControlID")  # noqa: E731
    xbmc.executebuiltin("ActivateWindow(SkinSettings)")
    mon.waitForAbort(3)
    found = None
    for pos in range(16):
        xbmc.executebuiltin(f"SetFocus(9000,{pos},absolute)")
        mon.waitForAbort(1.0)
        xbmc.executebuiltin("SetFocus(1225)")
        mon.waitForAbort(0.6)
        if cond("Control.HasFocus(1225)"):
            found = pos
            break
    log(f"introsound: found at 9000 pos {found} cat={lab('Container(9000).ListItem.Label')!r}")
    if found is not None:
        shot("introsound-1")
        xbmc.executebuiltin("Action(Up)")
        mon.waitForAbort(0.6)
        up = fid()
        xbmc.executebuiltin("Action(Down)")
        mon.waitForAbort(0.6)
        xbmc.executebuiltin("Action(Down)")
        mon.waitForAbort(0.6)
        down = fid()
        xbmc.executebuiltin("SetFocus(1225)")
        mon.waitForAbort(0.5)
        xbmc.executebuiltin("Action(Select)")
        mon.waitForAbort(1)
        log(f"introsound: up={up} down={down} off after select={cond('Skin.HasSetting(lucent.introsound.off)')}")
        shot("introsound-2")
        xbmc.executebuiltin("Action(Select)")
        mon.waitForAbort(0.5)
    xbmc.executebuiltin("ActivateWindow(home)")
    mon.waitForAbort(2)


def rowshift_test():
    """Rows shift by one (Binnenkort where Nieuw was) - what is visible above Nieuw, every 0.25 s, from the moment the
    Series tab opens, without trailers and then with trailers."""
    W = "plugin://plugin.video.fakeseren/?list="
    for trailers in (False, True):
        tag = "tr" if trailers else "no"
        if trailers:
            xbmc.executebuiltin("Skin.SetBool(nuvio.trailers.menu)")
            xbmc.executebuiltin("Skin.SetString(nuvio.posterfocus,window)")
            xbmc.executebuiltin("RunScript(special://skin/scripts/trailers.py)")
        xbmc.executebuiltin("Dialog.Close(all,true)")
        xbmc.executebuiltin("ActivateWindow(home)")
        mon.waitForAbort(1.5)
        for k, v in (("label", "Series"), ("w1.label", "Nieuw"), ("w1.path", W + "ss"), ("w1.style", "poster"),
                     ("w2.label", "Binnenkort"), ("w2.path", W + "sm"), ("w2.style", "poster"),
                     ("w3.label", "Afleveringen"), ("w3.path", W + "se"), ("w3.style", "land")):
            xbmc.executebuiltin(f"Skin.SetString(nuvio.tab3.{k},{v})")
        mon.waitForAbort(2)
        xbmc.executebuiltin("Control.SetFocus(9000,0)")
        mon.waitForAbort(3)
        xbmc.executebuiltin("Control.SetFocus(9000,2)")
        mon.waitForAbort(1)
        xbmc.executebuiltin("Action(Right)")
        rows, t0, last = [], time.time(), None
        while time.time() - t0 < 30 and not mon.abortRequested():
            try:
                fid = xbmcgui.Window(10000).getFocusId()
            except RuntimeError:
                fid = -1
            now = [fid, HOME.getProperty("nuvio.row"), HOME.getProperty("lucent.cw.show"), HOME.getProperty("lucent.cw.tab"),
                   HOME.getProperty("lucent.cw.count"), cond("Window.IsVisible(busydialog) | Window.IsVisible(busydialognocancel)"),
                   cond("Player.HasVideo"), lab("Window(home).Property(lucent.toprow)"),
                   cond("Control.IsVisible(9987)"), cond("Control.IsVisible(9901)"), cond("Control.IsVisible(9902)"),
                   lab("Container(8101).NumItems"), lab("Container(8102).NumItems"), lab("Container(8092).NumItems"),
                   cond("$EXP[LucentForYouRow]"), cond("$EXP[LucentSportRow]")]
            if now != last:
                rows.append([round(time.time() - t0, 2)] + now)
                last = now
                if len(rows) < 12:
                    shot(f"rowshift-{tag}-{len(rows)}")
            mon.waitForAbort(0.25)
        log(f"rowshift {tag}: " + json.dumps(rows))
        shot(f"rowshift-{tag}-end")
        xbmc.executebuiltin("PlayerControl(Stop)")
        mon.waitForAbort(2)
    xbmc.executebuiltin("Skin.Reset(nuvio.trailers.menu)")
    xbmc.executebuiltin("Skin.Reset(nuvio.posterfocus)")
    xbmc.executebuiltin("Skin.SetString(nuvio.tab3.label,Streaming)")


def cwmenu_test():
    """2.1.3: Continue watching from the library holds REAL library items (multipath of smart playlists), so Kodi's own
    context menu works on it, with the items of context add-ons."""
    W = "plugin://plugin.video.fakeseren/?list="
    xbmc.executebuiltin("Dialog.Close(all,true)")
    xbmc.executebuiltin("ActivateWindow(home)")
    mon.waitForAbort(1.5)
    for k, v in (("label", "Series"), ("w1.label", "Nieuw"), ("w1.path", W + "ss"), ("w1.style", "poster")):
        xbmc.executebuiltin(f"Skin.SetString(nuvio.tab3.{k},{v})")
    mon.waitForAbort(2)
    xbmc.executebuiltin("Control.SetFocus(9000,0)")
    mon.waitForAbort(3)
    xbmc.executebuiltin("Control.SetFocus(9000,2)")
    mon.waitForAbort(3)
    xbmc.executebuiltin("RunScript(special://skin/scripts/continuerow.py)")
    mon.waitForAbort(4)
    xbmc.executebuiltin("SetFocus(8092)")
    mon.waitForAbort(3)
    out = {"path": HOME.getProperty("lucent.cw.path")[:300], "count": HOME.getProperty("lucent.cw.count"),
           "show": HOME.getProperty("lucent.cw.show"), "focus": lab("System.CurrentControlID"),
           "num": lab("Container(8092).NumItems"), "items": []}
    for i in range(int(out["num"]) if out["num"].isdigit() else 0):
        b = f"Container(8092).ListItemAbsolute({i})."
        out["items"].append([lab(b + "DBType"), lab(b + "DBID"), lab(b + "TVShowTitle"), lab(b + "Title"), lab(b + "Season"),
                             lab(b + "Episode"), lab(b + "PercentPlayed"), lab(b + "FileNameAndPath")[-40:]])
    shot("cwmenu-row")
    xbmc.executebuiltin("Action(ContextMenu)")
    mon.waitForAbort(2)
    out["menu_open"] = cond("Window.IsVisible(contextmenu)")
    out["show_during_menu"] = HOME.getProperty("lucent.cw.show")
    out["menu"] = [lab(f"Control.GetLabel({i})") for i in range(1000, 1030) if cond(f"Control.IsVisible({i})")]
    shot("cwmenu-menu")
    xbmc.executebuiltin("Dialog.Close(all,true)")
    mon.waitForAbort(1)
    log("cwmenu: " + json.dumps(out))
    xbmc.executebuiltin("Skin.SetString(nuvio.tab3.label,Streaming)")


def badges_test():
    """2.1.3: premiere / finale top right (left of the watched tick when watched), episodes left bottom left (next to
    the percentage when that shows) - on poster cards and on landscape cards."""
    W = "plugin://plugin.video.fakeseren/?list="
    xbmc.executebuiltin("Dialog.Close(all,true)")
    xbmc.executebuiltin("ActivateWindow(home)")
    mon.waitForAbort(1.5)
    for k, v in (("label", "Afleveringen"), ("w1.label", "Poster"), ("w1.path", W + "se"), ("w1.style", "poster"),
                 ("w2.label", "Landschap"), ("w2.path", W + "se"), ("w2.style", "land")):
        xbmc.executebuiltin(f"Skin.SetString(nuvio.tab3.{k},{v})")
    mon.waitForAbort(2)
    xbmc.executebuiltin("Control.SetFocus(9000,0)")
    mon.waitForAbort(3)
    xbmc.executebuiltin("Control.SetFocus(9000,2)")
    mon.waitForAbort(6)
    xbmc.executebuiltin("Action(Right)")
    mon.waitForAbort(4)
    shot("badges-poster")
    xbmc.executebuiltin("Action(Down)")
    mon.waitForAbort(4)
    shot("badges-land")
    log(f"badges: focus={lab('System.CurrentControlID')} n1={lab('Container(8101).NumItems')} n2={lab('Container(8202).NumItems')}")
    xbmc.executebuiltin("Skin.SetString(nuvio.tab3.label,Streaming)")
    xbmc.executebuiltin("Skin.Reset(nuvio.tab3.w2.path)")


def okpage_test():
    """2.1.3: 'OK on a film opens its page' also in the video lists (an add-on folder and the library), not only on Home."""
    out = {}
    xbmc.executebuiltin("Skin.SetBool(nuvio.ok.movie.page)")
    xbmc.executebuiltin("Skin.SetBool(nuvio.ok.episode.page)")
    xbmc.executebuiltin("RunScript(special://skin/scripts/keymap.py)")
    mon.waitForAbort(3)
    out["keymap_file"] = xbmcvfs.exists("special://profile/keymaps/lucent-ok-page.xml")
    for name, path in (("addon", "plugin://plugin.video.fakeseren/?list=sm"), ("addon-ep", "plugin://plugin.video.fakeseren/?list=se"),
                       ("library", "videodb://movies/titles/")):
        xbmc.executebuiltin("Dialog.Close(all,true)")
        xbmc.executebuiltin(f"ActivateWindow(Videos,{path},return)")
        mon.waitForAbort(5)
        for _ in range(3):
            if lab("ListItem.Label") == "..":
                xbmc.executebuiltin("Action(Down)")
                mon.waitForAbort(0.8)
        item = lab("ListItem.Label")
        dbtype = lab("ListItem.DBType")
        # the real OK key (keyboard Return) through Kodi's keymaps, like a remote does
        xbmc.executeJSONRPC(json.dumps({"jsonrpc": "2.0", "id": 1, "method": "Input.ButtonEvent",
                                        "params": {"button": "return", "keymap": "KB", "holdtime": 0}}))
        mon.waitForAbort(3)
        out[name] = {"item": item, "dbtype": dbtype, "view": lab("Container.ViewMode"), "focus": lab("System.CurrentControlID"),
                     "info_open": cond("Window.IsVisible(movieinformation)"), "playing": cond("Player.HasVideo")}
        shot(f"okpage-{name}")
        xbmc.executebuiltin("PlayerControl(Stop)")
        xbmc.executebuiltin("Dialog.Close(all,true)")
        mon.waitForAbort(1.5)
    xbmc.executebuiltin("Skin.Reset(nuvio.ok.movie.page)")
    xbmc.executebuiltin("Skin.Reset(nuvio.ok.episode.page)")
    xbmc.executebuiltin("ActivateWindow(home)")
    mon.waitForAbort(2)
    log("okpage: " + json.dumps(out))


def levels_test():
    """Issue #18: the settings level button in Kodi's settings stays on Standard. Press it a few times and read it."""
    out = []
    xbmc.executebuiltin("Dialog.Close(all,true)")
    xbmc.executebuiltin("ActivateWindow(systemsettings)")
    mon.waitForAbort(3)
    xbmc.executebuiltin("SetFocus(20)")
    mon.waitForAbort(1)
    out.append(["start", lab("System.CurrentControlID"), lab("Control.GetLabel(20)"), lab("System.CurrentWindow")])
    shot("levels-0")
    for i in range(4):
        xbmc.executebuiltin("Action(Select)")
        mon.waitForAbort(2)
        out.append([i, lab("System.CurrentControlID"), lab("Control.GetLabel(20)"), lab("System.CurrentWindow"),
                    cond("Window.IsVisible(selectdialog)"), cond("System.HasModalDialog")])
        if i == 0:
            shot("levels-1")
        if cond("System.HasModalDialog"):
            xbmc.executebuiltin("Action(Down)")
            mon.waitForAbort(0.6)
            xbmc.executebuiltin("Action(Select)")
            mon.waitForAbort(1.5)
            out.append(["after dialog", lab("Control.GetLabel(20)")])
    log("levels: " + json.dumps(out))
    # the same in the settings of an add-on
    xbmc.executebuiltin("Addon.OpenSettings(plugin.video.fakeseren)")
    mon.waitForAbort(3)
    xbmc.executebuiltin("SetFocus(20)")
    mon.waitForAbort(1)
    a = [lab("Control.GetLabel(20)")]
    xbmc.executebuiltin("Action(Select)")
    mon.waitForAbort(2)
    a.append(lab("Control.GetLabel(20)"))
    log("levels addon: " + json.dumps(a))
    shot("levels-addon")
    xbmc.executebuiltin("Dialog.Close(all,true)")
    xbmc.executebuiltin("ActivateWindow(home)")
    mon.waitForAbort(2)


def epinprog_test():
    """2.1.4: the new library widget 'Episodes in progress' (smart playlist) fills a row with real episodes."""
    import urllib.parse as _u
    xsp = _u.quote(json.dumps({"type": "episodes", "order": {"direction": "descending", "method": "lastplayed"},
                               "rules": {"and": [{"field": "inprogress", "operator": "true", "value": []}]}}, separators=(",", ":")))
    path = "videodb://tvshows/titles/-1/-1/-1/?xsp=" + xsp
    xbmc.executebuiltin("Dialog.Close(all,true)")
    xbmc.executebuiltin("ActivateWindow(home)")
    mon.waitForAbort(1.5)
    for k, v in (("label", "Series"), ("w1.label", "Afleveringen die je kijkt"), ("w1.path", path), ("w1.style", "land")):
        xbmc.executebuiltin(f"Skin.SetString(nuvio.tab3.{k},{v})")
    mon.waitForAbort(2)
    xbmc.executebuiltin("Control.SetFocus(9000,0)")
    mon.waitForAbort(3)
    xbmc.executebuiltin("Control.SetFocus(9000,2)")
    mon.waitForAbort(6)
    xbmc.executebuiltin("Action(Right)")
    mon.waitForAbort(3)
    out = {"focus": lab("System.CurrentControlID"), "n": lab("Container(8201).NumItems"),
           "first": [lab("Container(8201).ListItem.DBType"), lab("Container(8201).ListItem.TVShowTitle"), lab("Container(8201).ListItem.Label")]}
    shot("epinprog")
    log("epinprog: " + json.dumps(out))
    xbmc.executebuiltin("Skin.SetString(nuvio.tab3.label,Streaming)")


def cwnotice_test():
    """2.1.4: the one-time message about Continue watching, for someone who used Lucent before."""
    xbmc.executebuiltin("Skin.SetString(lucent.setup.done,1)")
    xbmc.executebuiltin("Skin.Reset(lucent.notice.cw214)")
    xbmc.executebuiltin("ActivateWindow(home)")
    mon.waitForAbort(1)
    import importlib, sys as _s
    _s.path.insert(0, xbmcvfs.translatePath("special://skin/scripts/"))
    import startup as _st
    _st.cw_notice()
    mon.waitForAbort(8)
    out = {"dialog": cond("Window.IsVisible(okdialog)"), "head": lab("Control.GetLabel(1)"), "flag": lab("Skin.String(lucent.notice.cw214)")}
    shot("cwnotice")
    xbmc.executebuiltin("Dialog.Close(all,true)")
    mon.waitForAbort(1)
    _st.cw_notice()
    mon.waitForAbort(8)
    out["second_time"] = cond("Window.IsVisible(okdialog)")
    xbmc.executebuiltin("Dialog.Close(all,true)")
    log("cwnotice: " + json.dumps(out))


def agendalist_test():
    """2.1.4: calendar List in the new look (day headings, backdrop in view, logo on the picture) and Back: first up to
    Week / List / Month, then out."""
    out = {}
    xbmc.executebuiltin("Dialog.Close(all,true)")
    xbmc.executebuiltin("ActivateWindow(home)")
    mon.waitForAbort(1)
    xbmc.executebuiltin("RunScript(special://skin/scripts/agenda.py)")
    mon.waitForAbort(8)
    xbmc.executebuiltin("SetFocus(102)")
    mon.waitForAbort(1)
    xbmc.executebuiltin("Action(Select)")
    mon.waitForAbort(3)
    out["start"] = [lab("System.CurrentControlID"), lab("Container(200).ListItem.Label"), lab("Container(200).ListItem.Property(isheader)"), lab("Container(200).NumItems")]
    shot("agenda-list-1")
    seen = []
    for _ in range(4):
        xbmc.executebuiltin("Action(Down)")
        mon.waitForAbort(1)
        seen.append([lab("Container(200).CurrentItem"), lab("Container(200).ListItem.Label"), lab("Container(200).ListItem.Property(isheader)")])
    out["down"] = seen
    shot("agenda-list-2")
    xbmc.executebuiltin("Action(Back)")
    mon.waitForAbort(1.5)
    out["back1"] = [lab("System.CurrentControlID"), cond("Window.IsVisible(Lucent_Agenda.xml)")]
    xbmc.executebuiltin("Action(Back)")
    mon.waitForAbort(1.5)
    out["back2"] = [lab("System.CurrentControlID"), cond("Window.IsVisible(Lucent_Agenda.xml)"), lab("System.CurrentWindow")]
    log("agendalist: " + json.dumps(out))
    xbmc.executebuiltin("ActivateWindow(home)")
    mon.waitForAbort(2)


def intro2_test():
    """2.1.4: the intro after the fix (no delayed fade-out on the group): pictures at 1, 2.5, 4 and 5.5 s."""
    xbmc.executebuiltin("Dialog.Close(all,true)")
    xbmc.executebuiltin("ActivateWindow(1195)")
    t0 = time.time()
    for s in (1.0, 2.5, 4.0, 5.5):
        while time.time() - t0 < s:
            mon.waitForAbort(0.05)
        xbmc.executebuiltin(f"TakeScreenshot({OUT}/{TAG}-intro2-{int(s*10):02d}.png,sync)")
    mon.waitForAbort(2)
    xbmc.executebuiltin("ActivateWindow(home)")
    mon.waitForAbort(2)


def cwjumplog_test():
    """Rows shift by one when a poster trailer starts. Same as cwjump, but a picture every 2 s during the first 26 s and
    the skin's own log lines of that minute, to see what moves the rows."""
    import re as _re
    t0 = time.strftime("%H:%M:%S")
    xbmc.executebuiltin("Skin.SetBool(nuvio.trailers.menu)")
    xbmc.executebuiltin("Skin.SetString(nuvio.posterfocus,window)")
    xbmc.executebuiltin("RunScript(special://skin/scripts/trailers.py)")
    _idle_on_series("cwlog", 1, 26)
    xbmc.executebuiltin("Skin.Reset(nuvio.trailers.menu)")
    xbmc.executebuiltin("Skin.Reset(nuvio.posterfocus)")
    try:
        with open(xbmcvfs.translatePath("special://logpath/kodi.log"), encoding="utf-8", errors="replace") as fh:
            lines = fh.read().splitlines()
        keep = [ln[11:] for ln in lines if ln[11:19] >= t0 and _re.search(r"skin.lucent|trailer|youtube|Activate|busy|focus|Window|CPythonInvoker", ln)]
        log("cwlog lines: " + json.dumps(keep[-120:]))
    except Exception as error:  # noqa: BLE001
        log(f"cwlog lines: {error}")


ONLY = None
try:
    ONLY = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "only.txt")).read().split()
except OSError:
    pass


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


def series_test():
    """Streaming: the service row has only the wanted services; a series page's Play opens its seasons in Seren."""
    res = json.loads(xbmc.executeJSONRPC(json.dumps({"jsonrpc": "2.0", "id": 1, "method": "Files.GetDirectory",
                                                    "params": {"directory": "plugin://script.lucent.library/?action=providers", "media": "files"}})))
    names = [f.get("label") for f in (res.get("result") or {}).get("files") or []]
    log(f"series: providers ({len(names)}) {names}")
    for kind, tmdb_id in (("movie", "1001"), ("tv", "1002")):
        HOME.setProperty("nuvio.open.tmdb", tmdb_id)
        HOME.setProperty("nuvio.open.type", kind)
        HOME.setProperty("nuvio.open.trakt", "4242")
        xbmc.executebuiltin("RunScript(special://skin/scripts/info.py,open,path)")
        for _ in range(20):
            mon.waitForAbort(1)
            if cond("Window.IsVisible(movieinformation)"):
                break
        mon.waitForAbort(2)
        log(f"series: {kind} page={cond('Window.IsVisible(movieinformation)')} dbtype={lab('ListItem.DBType')} "
            f"folder={cond('ListItem.IsFolder')} path={lab('ListItem.FileNameAndPath')[:90]!r}")
        if kind == "tv":
            shot("15-series-page")
            xbmc.executebuiltin("SetFocus(8)")
            mon.waitForAbort(1)
            xbmc.executebuiltin("Action(Select)")
            for _ in range(15):
                mon.waitForAbort(1)
                if cond("Window.IsActive(videos)") and int(lab("Container.NumItems") or 0) > 0:
                    break
            mon.waitForAbort(2)
            log(f"series: after Play window={lab('System.CurrentWindow')} page={cond('Window.IsVisible(movieinformation)')} "
                f"path={lab('Container.FolderPath')[:90]!r} items={lab('Container.NumItems')}")
            shot("15-series-after-play")
        xbmc.executebuiltin("Dialog.Close(all,true)")
        xbmc.executebuiltin("ActivateWindow(home)")
        mon.waitForAbort(3)


def art_of(directory):
    res = json.loads(xbmc.executeJSONRPC(json.dumps({"jsonrpc": "2.0", "id": 1, "method": "Files.GetDirectory",
                                                    "params": {"directory": directory, "media": "files", "properties": ["art"]}})))
    return [(f.get("label"), (f.get("art") or {}).get("thumb", "")[-28:]) for f in (res.get("result") or {}).get("files") or []]


def custom_test():
    """Own title picture / background / hidden title per widget, own tab icon, own streaming services list."""
    star = "special://skin/media/icons/star.png"
    bgimg = "special://home/addons/plugin.video.fakeseren/icon.png"
    xbmc.executebuiltin("Control.SetFocus(9000,0)")
    mon.waitForAbort(2)
    xbmc.executebuiltin("SetFocus(9100)")
    mon.waitForAbort(2)
    log(f"custom: before fanart={lab('$VAR[LucentHomeFanart]')[-30:]!r} w1label={lab('$VAR[NuvioW1Label]')!r}")
    shot("16-before")
    sys.path.insert(0, xbmcvfs_translate("special://skin/scripts"))
    try:
        import menu
        m = menu.Menu()
        wd = m.tabs[0]["widgets"][0]
        wd["timg"], wd["bg"] = star, "special://skin/media/icons/tv.png"
        wd2 = m.tabs[0]["widgets"][1]
        wd2["notitle"] = "1"
        m.tabs[0]["icon"] = bgimg
        m.save()
        mon.waitForAbort(4)
        log(f"custom: saved timg={lab('Skin.String(nuvio.home.w1.timg)')[-20:]!r} tab={lab('Skin.String(nuvio.tab1.w1.timg)')[-20:]!r} "
            f"bg={lab('Skin.String(nuvio.home.w1.bg)')[-20:]!r} notitle2={lab('Skin.String(nuvio.home.w2.notitle)')!r} icon={lab('Skin.String(nuvio.tab1.icon)')[-20:]!r}")
        log(f"custom: vars timg={lab('$VAR[NuvioW1TitleImg]')[-20:]!r} bg={lab('$VAR[NuvioW1Bg]')[-20:]!r} "
            f"fanart={lab('$VAR[LucentHomeFanart]')[-30:]!r} row={HOME.getProperty('nuvio.row')}")
        shot("16-after")
        m = menu.Menu()
        log(f"custom: reloaded {m.tabs[0]['widgets'][0].get('timg', '')[-20:]!r} {m.tabs[0]['widgets'][1].get('notitle')!r}")
    except Exception as error:  # noqa: BLE001
        log(f"custom: menu error {error!r}")
    # streaming services: the standard list, then your own list with your own picture
    lib = "plugin://script.lucent.library/?action=providers"
    log(f"custom: services standard {[a for a, _b in art_of(lib)]}")
    cat = art_of("plugin://script.lucent.library/?action=provcatalog")
    log(f"custom: catalog ({len(cat)}) {[a for a, _b in cat][:20]}")
    d = xbmcvfs_translate("special://profile/addon_data/script.lucent.library/tmdb/")
    os.makedirs(d, exist_ok=True)
    json.dump({"items": [{"id": 1899, "name": "HBO Max", "logo": "/h.png", "region": "US"},
                         {"id": 8, "name": "Netflix", "logo": "/n.png", "region": "US", "image": bgimg},
                         {"id": 900, "name": "Fubo", "logo": "/f.png", "region": "US"}]}, open(d + "services.json", "w"))
    log(f"custom: services own {art_of(lib)}")
    xbmc.executebuiltin("RunScript(special://skin/scripts/streamedit.py,reset)")
    mon.waitForAbort(3)
    log(f"custom: services after reset {[a for a, _b in art_of(lib)]} file={os.path.exists(d + 'services.json')}")
    xbmc.executebuiltin("RunScript(special://skin/scripts/streamedit.py)")
    mon.waitForAbort(4)
    cid = 6 if int(lab("Container(6).NumItems") or 0) else 3
    labels = [lab(f"Container({cid}).ListItemAbsolute({i}).Label") for i in range(int(lab(f"Container({cid}).NumItems") or 0))]
    log(f"custom: editor open={cond('Window.IsVisible(selectdialog)')} items={labels}")
    shot("16-editor")
    xbmc.executebuiltin("Dialog.Close(all,true)")
    mon.waitForAbort(2)


def popup_test():
    """Streaming pop-up: OK on a series opens its page; Play there opens the seasons and the pop-up goes away."""
    xbmc.executebuiltin("RunScript(special://skin/scripts/service.py,8,Netflix,)")
    for _ in range(20):
        mon.waitForAbort(1)
        if cond("Window.IsVisible(Lucent_Service.xml)") and int(lab("Container(802).NumItems") or 0) > 0:
            break
    mon.waitForAbort(2)
    xbmc.executebuiltin("SetFocus(802)")
    mon.waitForAbort(1.5)
    log(f"popup: open={cond('Window.IsVisible(Lucent_Service.xml)')} focus={lab('System.CurrentControlID')} "
        f"item={lab('Container(802).ListItem.Label')!r} dbtype={lab('Container(802).ListItem.DBType')}")
    xbmc.executebuiltin("Action(Select)")
    for _ in range(20):
        mon.waitForAbort(1)
        if cond("Window.IsVisible(movieinformation)"):
            break
    mon.waitForAbort(2)
    log(f"popup: page={cond('Window.IsVisible(movieinformation)')} dbtype={lab('ListItem.DBType')} path={lab('ListItem.FileNameAndPath')[:70]!r}")
    xbmc.executebuiltin("SetFocus(8)")
    mon.waitForAbort(1)
    xbmc.executebuiltin("Action(Select)")
    for _ in range(15):
        mon.waitForAbort(1)
        if not cond("Window.IsVisible(Lucent_Service.xml)") and cond("Window.IsActive(videos)"):
            break
    mon.waitForAbort(2)
    log(f"popup: after Play popup={cond('Window.IsVisible(Lucent_Service.xml)')} window={lab('System.CurrentWindow')} "
        f"videos={cond('Window.IsActive(videos)')} path={lab('Container.FolderPath')[:70]!r} items={lab('Container.NumItems')}")
    shot("17-popup-play")
    xbmc.executebuiltin("Dialog.Close(all,true)")
    xbmc.executebuiltin("ActivateWindow(home)")
    mon.waitForAbort(3)
    # Back from a page keeps the pop-up (only Play closes it)
    xbmc.executebuiltin("RunScript(special://skin/scripts/service.py,8,Netflix,)")
    mon.waitForAbort(6)
    xbmc.executebuiltin("SetFocus(802)")
    mon.waitForAbort(1.5)
    xbmc.executebuiltin("Action(Select)")
    for _ in range(20):
        mon.waitForAbort(1)
        if cond("Window.IsVisible(movieinformation)"):
            break
    mon.waitForAbort(2)
    xbmc.executebuiltin("Action(Back)")
    mon.waitForAbort(4)
    log(f"popup: after Back page={cond('Window.IsVisible(movieinformation)')} popup={cond('Window.IsVisible(Lucent_Service.xml)')}")
    xbmc.executebuiltin("Dialog.Close(all,true)")
    xbmc.executebuiltin("ActivateWindow(home)")
    mon.waitForAbort(2)


def direct_test():
    """A series in the streaming pop-up (and in a TMDb row on Home) opens straight on its seasons; a film on its page."""
    for row, label in ((802, "series"), (801, "film")):
        xbmc.executebuiltin("RunScript(special://skin/scripts/service.py,8,Netflix,)")
        for _ in range(20):
            mon.waitForAbort(1)
            if cond("Window.IsVisible(Lucent_Service.xml)") and int(lab(f"Container({row}).NumItems") or 0) > 0:
                break
        mon.waitForAbort(2)
        xbmc.executebuiltin(f"SetFocus({row})")
        mon.waitForAbort(1.5)
        item = lab(f"Container({row}).ListItem.Label")
        xbmc.executebuiltin("Action(Select)")
        for _ in range(15):
            mon.waitForAbort(1)
            if cond("Window.IsActive(videos) | Window.IsVisible(movieinformation)") and not cond("Window.IsVisible(Lucent_Service.xml)"):
                break
            if cond("Window.IsVisible(movieinformation)"):
                break
        mon.waitForAbort(2)
        log(f"direct: {label} {item!r}: popup={cond('Window.IsVisible(Lucent_Service.xml)')} page={cond('Window.IsVisible(movieinformation)')} "
            f"videos={cond('Window.IsActive(videos)')} path={lab('Container.FolderPath')[:60]!r} items={lab('Container.NumItems')}")
        shot(f"18-direct-{label}")
        xbmc.executebuiltin("Dialog.Close(all,true)")
        xbmc.executebuiltin("ActivateWindow(home)")
        mon.waitForAbort(3)


def logo_test():
    """The streaming services row: each tile shows the service's transparent logo (from the logo packs)."""
    res = json.loads(xbmc.executeJSONRPC(json.dumps({"jsonrpc": "2.0", "id": 1, "method": "Files.GetDirectory",
                     "params": {"directory": "plugin://script.lucent.library/?action=providers", "media": "files", "properties": ["art"]}})))
    log(f"logos: {[(f.get('label'), (f.get('art') or {}).get('clearlogo', '')[-28:]) for f in (res.get('result') or {}).get('files') or []]}")
    xbmc.executebuiltin("Control.SetFocus(9000,2)")
    for _ in range(40):
        mon.waitForAbort(1)
        if int(lab("Container(8201).NumItems") or 0) > 0:
            break
    mon.waitForAbort(8)
    xbmc.executebuiltin("SetFocus(9100)")
    mon.waitForAbort(3)
    log(f"logos: tab={lab('Container(9000).ListItem.Label')} focus={lab('System.CurrentControlID')} n={lab('Container(8201).NumItems')} "
        f"svclogo={lab('Container(8201).ListItem.Property(svclogo)')[-28:]!r} hover={lab('Container(8201).ListItem.Property(svchover)')[-28:]!r} "
        f"labels.hide={cond('Skin.HasSetting(nuvio.posterlabels.hide)')} last={lab('Container(8201).ListItemAbsolute(11).Label')!r}")
    shot("19-logos")
    xbmc.executebuiltin("Action(Right)")
    mon.waitForAbort(1)
    xbmc.executebuiltin("Action(Right)")
    mon.waitForAbort(2)
    shot("19-logos-right")
    mon.waitForAbort(1)
    shot("19-logos-right2")
    xbmc.executebuiltin("Control.SetFocus(9000,0)")
    mon.waitForAbort(2)


def poster_test():
    """Poster rows: a picture with and without the names under the posters (preview)."""
    xbmc.executebuiltin("Control.SetFocus(9000,1)")
    mon.waitForAbort(25)
    xbmc.executebuiltin("SetFocus(9100)")
    mon.waitForAbort(3)
    log(f"poster: focus={lab('System.CurrentControlID')} n={lab('Container(8101).NumItems')} {lab('Container(8102).NumItems')}")
    shot("20-posters-labels")
    xbmc.executebuiltin("Skin.SetBool(nuvio.posterlabels.hide)")
    mon.waitForAbort(3)
    shot("20-posters-nolabels")
    xbmc.executebuiltin("Action(Down)")
    mon.waitForAbort(3)
    shot("20-posters-nolabels-down")
    xbmc.executebuiltin("Skin.Reset(nuvio.posterlabels.hide)")


def sel_items():
    for cid in (6, 3):
        n = int(lab(f"Container({cid}).NumItems") or 0)
        if n and cond(f"Control.IsVisible({cid})"):
            return cid, [lab(f"Container({cid}).ListItemAbsolute({i}).Label") + "|" + lab(f"Container({cid}).ListItemAbsolute({i}).Label2") for i in range(n)]
    return 0, []


def pick(index):
    cid, _items = sel_items()
    xbmc.executebuiltin(f"SetFocus({cid},{index},absolute)")
    mon.waitForAbort(1)
    xbmc.executebuiltin("Action(Select)")
    mon.waitForAbort(2)


def edit_test():
    """Streaming services editor: switch a service off, move one to another place (run as menu.py runs it)."""
    import threading
    sys.path.insert(0, xbmcvfs_translate("special://skin/scripts"))
    lib = "plugin://script.lucent.library/?action=providers"
    import streamedit
    th = threading.Thread(target=streamedit.editor)
    th.start()
    mon.waitForAbort(4)
    cid, items = sel_items()
    log(f"edit: open={cond('Window.IsVisible(selectdialog)')} {items[:4]} ... {len(items)}")
    pick(1)                                            # Disney
    cid, opts = sel_items()
    log(f"edit: options {opts}")
    pick(0)                                            # hide / switch off
    xbmc.executebuiltin("Action(Back)")
    mon.waitForAbort(2)
    cid, items = sel_items()
    log(f"edit: after off {items[:3]}")
    pick(0)                                            # Netflix
    pick(1)                                            # place
    cid, places = sel_items()
    log(f"edit: places {places[:4]}")
    pick(3)                                            # to place 4
    xbmc.executebuiltin("Action(Back)")
    mon.waitForAbort(2)
    cid, items = sel_items()
    log(f"edit: after move {items[:5]}")
    shot("21-editor")
    xbmc.executebuiltin("Action(Back)")
    mon.waitForAbort(2)
    th.join(5)
    log(f"edit: row now {[a for a, _b in art_of(lib)]}")


def same_test():
    """A widget that is on two tabs: changing it on one tab changes it on the other too."""
    sys.path.insert(0, xbmcvfs_translate("special://skin/scripts"))
    import menu
    m = menu.Menu()
    wd = m.tabs[0]["widgets"][0]
    copy = dict(wd)
    m.tabs[1]["widgets"].append(copy)
    m.save()
    mon.waitForAbort(2)
    m = menu.Menu()
    wd = m.tabs[0]["widgets"][0]
    wd["style"], wd["sort"], wd["label"] = "land", "title", "Renamed"
    try:
        n = menu.copy_to_same(m, m.tabs[0], wd)
    except AttributeError:
        n = "no copy_to_same"
    m.save()
    mon.waitForAbort(3)
    t2 = len(m.tabs[1]["widgets"])
    log(f"same: copied={n} tab2.w{t2}: label={lab(f'Skin.String(nuvio.tab2.w{t2}.label)')!r} style={lab(f'Skin.String(nuvio.tab2.w{t2}.style)')!r} "
        f"sort={lab(f'Skin.String(nuvio.tab2.w{t2}.sort)')!r} tab1.w1={lab('Skin.String(nuvio.tab1.w1.label)')!r}")
    res = json.loads(xbmc.executeJSONRPC(json.dumps({"jsonrpc": "2.0", "id": 1, "method": "Addons.GetAddonDetails",
                                                    "params": {"addonid": "script.lucent.library", "properties": ["extrainfo", "enabled", "version"]}})))
    log(f"same: library addon {str(res.get('result') or res.get('error'))[:200]}")


def settings_test():
    """Skin settings: the Menu and widgets pane, and the order in Kodi's settings (Lucent category)."""
    fid = lambda: lab("System.CurrentControlID")  # noqa: E731
    xbmc.executebuiltin("ActivateWindow(SkinSettings)")
    mon.waitForAbort(3)
    xbmc.executebuiltin("SetFocus(9000,2,absolute)")
    mon.waitForAbort(1.5)
    log(f"settings: cat={lab('Container(9000).ListItem.Label')!r} sub={lab('Container(9000).ListItem.Property(sub)')!r}")
    xbmc.executebuiltin("Action(Right)")
    mon.waitForAbort(1.5)
    seen = []
    for _ in range(6):
        seen.append(fid())
        xbmc.executebuiltin("Action(Down)")
        mon.waitForAbort(0.8)
    log(f"settings: pane 3 focus path {seen}")
    shot("22-skinsettings-menu")
    xbmc.executebuiltin("SetFocus(9000,1,absolute)")
    mon.waitForAbort(1.5)
    xbmc.executebuiltin("Action(Right)")
    mon.waitForAbort(1)
    xbmc.executebuiltin("SetFocus(2201)")
    mon.waitForAbort(1)
    xbmc.executebuiltin("Action(Select)")
    mon.waitForAbort(1)
    seen = []
    for _ in range(4):
        xbmc.executebuiltin("Action(Down)")
        mon.waitForAbort(0.8)
        seen.append(fid())
    log(f"settings: pane 2 after opening Startscherm {seen}")
    xbmc.executebuiltin("Action(Select)")
    xbmc.executebuiltin("SetFocus(2201)")
    xbmc.executebuiltin("Action(Select)")
    mon.waitForAbort(1)
    xbmc.executebuiltin("ActivateWindow(home)")
    mon.waitForAbort(2)
    xbmc.executebuiltin("ActivateWindow(Settings)")
    mon.waitForAbort(3)
    n = int(lab("Container(9000).NumItems") or 0)
    cats = [lab(f"Container(9000).ListItemAbsolute({i}).Property(cat)") for i in range(n)]
    if "lucent" in cats:
        xbmc.executebuiltin(f"SetFocus(9000,{cats.index('lucent')},absolute)")
        mon.waitForAbort(2)
    items = [lab(f"Container(9100).ListItemAbsolute({i}).Label") for i in range(int(lab("Container(9100).NumItems") or 0))]
    log(f"settings: kodi menu lucent items {items}")
    shot("22-settings-lucent")
    xbmc.executebuiltin("ActivateWindow(home)")
    mon.waitForAbort(2)


def ctxmenu_test():
    """A Lucent Library film: its context menu has Seren's options."""
    xbmc.executebuiltin('ActivateWindow(Videos,"special://profile/addon_data/script.lucent.library/movies/Test Film (2020)/",return)')
    mon.waitForAbort(4)
    for _ in range(4):
        if lab("ListItem.Label").endswith(".strm") or "Test Film" in lab("ListItem.Label"):
            break
        xbmc.executebuiltin("Action(Down)")
        mon.waitForAbort(1)
    log(f"ctxmenu: item={lab('ListItem.Label')!r} path={lab('ListItem.FileNameAndPath')[-50:]!r} dbtype={lab('ListItem.DBType')!r}")
    xbmc.executebuiltin("Action(ContextMenu)")
    mon.waitForAbort(2)
    labels = []
    for i in range(1000, 1030):
        if cond(f"Control.IsVisible({i})"):
            labels.append(lab(f"Control.GetLabel({i})"))
    log(f"ctxmenu: open={cond('Window.IsVisible(contextmenu)')} items={labels}")
    shot("23-ctxmenu")
    xbmc.executebuiltin("Dialog.Close(all,true)")
    xbmc.executebuiltin("ActivateWindow(home)")
    mon.waitForAbort(2)

def resume_test():
    """Stop a film / episode half way: saved locally, and starting it again jumps back there."""
    import xbmcvfs
    rfile = xbmcvfs.translatePath("special://profile/addon_data/script.lucent.library/resume.json")
    player = xbmc.Player()
    for kind, uid in (("movie", {"tmdb": "123", "imdb": "tt0000123"}), ("episode", {"tmdb": "999"})):
        def item():
            li = xbmcgui.ListItem("Resume " + kind)
            tag = li.getVideoInfoTag()
            tag.setMediaType(kind)
            tag.setTitle("Resume " + kind)
            if kind == "episode":
                tag.setTvShowTitle("Resume Show")
                tag.setSeason(1)
                tag.setEpisode(2)
            tag.setUniqueIDs(uid)
            return li
        player.play("/tmp/ci/test.mkv", item())
        for _ in range(20):
            if player.isPlayingVideo() and player.getTotalTime() > 0:
                break
            mon.waitForAbort(0.5)
        mon.waitForAbort(6)
        player.seekTime(70)
        mon.waitForAbort(4)
        at = player.getTime()
        player.stop()
        mon.waitForAbort(3)
        try:
            saved = json.load(open(rfile))
        except Exception as error:  # noqa: BLE001
            saved = {"error": repr(error)}
        log(f"resume {kind}: stopped at {int(at)} saved={ {k: v.get('pos') for k, v in saved.items() if isinstance(v, dict)} }")
        player.play("/tmp/ci/test.mkv", item())
        for _ in range(20):
            if player.isPlayingVideo() and player.getTotalTime() > 0:
                break
            mon.waitForAbort(0.5)
        mon.waitForAbort(8)
        log(f"resume {kind}: started again, now at {int(player.getTime())}")
        shot(f"24-resume-{kind}")
        player.seekTime(115)
        mon.waitForAbort(3)
        player.stop()
        mon.waitForAbort(3)
        try:
            saved = json.load(open(rfile))
        except Exception:  # noqa: BLE001
            saved = {}
        log(f"resume {kind}: after watching to the end keys={list(saved)}")
    xbmc.executebuiltin("ActivateWindow(home)")
    mon.waitForAbort(2)

def widgetctx_test():
    """A film in a Lucent row on Home: its context menu has Seren's options too."""
    xbmc.executebuiltin("ActivateWindow(home)")
    mon.waitForAbort(2)
    found = None
    for _try in range(30):
        for cid in [8100 + n for n in range(1, 11)] + [8200 + n for n in range(1, 11)]:
            num = lab(f"Container({cid}).NumItems")
            for pos in range(int(num) if num.isdigit() else 0):
                path = lab(f"Container({cid}).ListItemAbsolute({pos}).FileNameAndPath")
                if "tmdbopen" in path and "type=movie" in path:
                    found = (cid, pos)
                    break
            if found:
                break
        if found:
            break
        mon.waitForAbort(3)
    log(f"widgetctx: film found at {found}")
    if not found:
        return
    xbmc.executebuiltin(f"Control.SetFocus({found[0]},{found[1]},absolute)")
    mon.waitForAbort(2)
    log(f"widgetctx: focus={lab('System.CurrentControlId')} item={lab('ListItem.Label')!r} path={lab('ListItem.FileNameAndPath')[:60]!r}")
    xbmc.executebuiltin("Action(ContextMenu)")
    mon.waitForAbort(2)
    labels = [lab(f"Control.GetLabel({i})") for i in range(1000, 1030) if cond(f"Control.IsVisible({i})")]
    log(f"widgetctx: open={cond('Window.IsVisible(contextmenu)')} items={labels}")
    shot("25-widgetctx")
    xbmc.executebuiltin("Dialog.Close(all,true)")
    mon.waitForAbort(1)

def limit_test():
    """Number of titles per row: 25 by default, 50, or all."""
    xbmc.executebuiltin("ActivateWindow(home)")
    xbmc.executebuiltin("Control.SetFocus(9000,0)")
    for _ in range(60):
        if lab("Container(8104).NumItems") not in ("", "0"):
            break
        mon.waitForAbort(2)
    for value in ("", "50", "0", "100", ""):
        for name in ("nuvio.tab1.w4", "nuvio.home.w4"):
            xbmc.executebuiltin(f"Skin.SetString({name}.limit,{value})" if value else f"Skin.Reset({name}.limit)")
        mon.waitForAbort(12)
        log(f"limit {value or 'standard'}: row 8104 has {lab('Container(8104).NumItems')} titles "
            f"(var={lab('$VAR[NuvioW4Limit]')!r})")
    shot("26-limit")

def digital_test():
    """Hide films until their digital release: half of the TMDb films come out digitally in 2027."""
    xbmc.executebuiltin("ActivateWindow(home)")
    xbmc.executebuiltin("Control.SetFocus(8101,0)")
    for _ in range(5):
        mon.waitForAbort(1)
        xbmc.executebuiltin("Action(Down)")
    for _ in range(150):
        if lab("Container(8106).NumItems") not in ("", "0"):
            break
        mon.waitForAbort(2)
    for on in (False, True, False):
        xbmc.executebuiltin("Skin.SetBool(lucent.hide.undigital)" if on else "Skin.Reset(lucent.hide.undigital)")
        HOME.setProperty("lucent.wr.6", str(time.time()))
        mon.waitForAbort(8)
        log(f"digital {'on' if on else 'off'}: row 8106 has {lab('Container(8106).NumItems')} films")

def watched_test():
    """No pop-up for an episode you already saw: Seren's Trakt copy says watched."""
    import sqlite3
    import sys
    import xbmcvfs
    sys.path.append(xbmcvfs.translatePath("special://skin/scripts"))
    path = xbmcvfs.translatePath("special://profile/addon_data/plugin.video.seren/traktSync.db")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    con = sqlite3.connect(path)
    con.execute("CREATE TABLE IF NOT EXISTS shows (trakt_id INTEGER, tmdb_id INTEGER)")
    con.execute("CREATE TABLE IF NOT EXISTS episodes (trakt_show_id INTEGER, season INTEGER, number INTEGER, watched INTEGER)")
    con.execute("CREATE TABLE IF NOT EXISTS movies (tmdb_id INTEGER, watched INTEGER)")
    con.execute("INSERT INTO shows VALUES (77, 5555)")
    con.execute("INSERT INTO episodes VALUES (77, 2, 3, 1)")
    con.execute("INSERT INTO episodes VALUES (77, 2, 4, 0)")
    con.execute("INSERT INTO movies VALUES (6666, 1)")
    con.commit()
    con.close()
    import agenda_core
    for ev in ({"kind": "tv", "tmdb": 5555, "season": 2, "episode": 3}, {"kind": "tv", "tmdb": 5555, "season": 2, "episode": 4},
               {"kind": "tv", "tmdb": 9, "season": 1, "episode": 1}, {"kind": "movie", "tmdb": 6666, "season": 0, "episode": 0}):
        log(f"watchedcheck {ev['kind']} {ev['tmdb']} S{ev['season']}E{ev['episode']}: {agenda_core.already_watched(ev)}")

def postersize_test():
    """Big posters (default) and small posters: the row title stays under the hero, small rows peek."""
    for small in (False, True, False):
        xbmc.executebuiltin("Skin.SetBool(lucent.posters.small)" if small else "Skin.Reset(lucent.posters.small)")
        xbmc.executebuiltin("ReloadSkin()")
        mon.waitForAbort(8)
        xbmc.executebuiltin("ActivateWindow(home)")
        xbmc.executebuiltin("Control.SetFocus(8101,0)")
        mon.waitForAbort(6)
        tag = "small" if small else "big"
        shot(f"27-posters-{tag}-row1")
        xbmc.executebuiltin("Action(Down)")
        mon.waitForAbort(3)
        log(f"postersize {tag}: focus={lab('System.CurrentControlId')} labelshidden={cond('Skin.HasSetting(nuvio.posterlabels.hide)')}")
        shot(f"27-posters-{tag}-row2")

def libsplit_test():
    """Library rows with only films / only series: Kodi opens them without errors."""
    base = "plugin://script.lucent.library/?action=lib&kind="
    for kind in ("continue", "continue&only=movie", "continue&only=tv", "newin&only=movie", "newin&only=tv"):
        res = json.loads(xbmc.executeJSONRPC(json.dumps({"jsonrpc": "2.0", "id": 1, "method": "Files.GetDirectory",
                                                         "params": {"directory": base + kind, "media": "video"}})))
        files = (res.get('result') or {}).get('files') or []
        log(f"libsplit {kind}: {'error ' + str(res['error']) if 'error' in res else [f.get('label') for f in files]}")
    import sys
    import xbmcvfs
    sys.path.append(xbmcvfs.translatePath("special://skin/scripts"))
    import menu
    log(f"libsplit menu: {[menu.tr(k) for k, p, _s in menu.WIDGETS_LIBRARY if 'only=' in p]}")

def trailer_test():
    """A trailer from the page: full screen at once (not behind the page), and the page comes back afterwards."""
    xbmc.executebuiltin('ActivateWindow(Videos,"videodb://movies/titles/",return)')
    mon.waitForAbort(4)
    for _ in range(4):
        if lab("ListItem.Label") == "Lib Film":
            break
        xbmc.executebuiltin("Action(Down)")
        mon.waitForAbort(1)
    xbmc.executebuiltin("Action(Info)")
    mon.waitForAbort(4)
    log(f"trailer: page open={cond('Window.IsActive(movieinformation)')} item={lab('ListItem.Label')!r}")
    t0 = time.time()
    xbmc.executebuiltin("PlayMedia(/tmp/ci/test.mkv)")
    xbmc.executebuiltin("SetProperty(nuvio.open.leave,1,home)")
    xbmc.executebuiltin("RunScript(special://skin/scripts/trailerback.py)")
    seen = []
    while time.time() - t0 < 8:
        state = (xbmc.Player().isPlayingVideo(), cond("Window.IsActive(fullscreenvideo)"), cond("Window.IsActive(movieinformation)"))
        if not seen or seen[-1][1:] != state:
            seen.append((round(time.time() - t0, 1),) + state)
        mon.waitForAbort(0.1)
    log(f"trailer: (time, playing, fullscreen, page) {seen}")
    shot("28-trailer-playing")
    xbmc.Player().stop()
    mon.waitForAbort(5)
    log(f"trailer: after stop page open={cond('Window.IsActive(movieinformation)')} window={lab('System.CurrentWindow')!r}")
    shot("28-trailer-after")
    xbmc.executebuiltin("Dialog.Close(all,true)")
    xbmc.executebuiltin("ActivateWindow(home)")
    mon.waitForAbort(2)

def audio_test():
    """Spoken language: first choice Dutch (not in the film), second English: the English 5.1, not the commentary."""
    xbmc.executebuiltin("Skin.SetString(lucent.audio.lang1,nl)")
    xbmc.executebuiltin("Skin.SetString(lucent.audio.lang2,en)")
    mon.waitForAbort(8)                              # the helper starts its watcher
    for run in (1, 2):
        xbmc.executebuiltin("PlayMedia(/tmp/ci/audio.mkv)")
        mon.waitForAbort(25)
        res = json.loads(xbmc.executeJSONRPC(json.dumps({"jsonrpc": "2.0", "id": 1, "method": "Player.GetProperties",
                                                         "params": {"playerid": 1, "properties": ["currentaudiostream", "audiostreams"]}})))
        r = res.get("result") or {}
        cur = r.get("currentaudiostream") or {}
        if run == 3 and xbmcvfs.exists("special://skin/scripts/subtitles.py"):   # gone from the skin in 1.37.0
            import sys
            sys.path.append(xbmcvfs.translatePath("special://skin/scripts"))
            import subtitles as subs
            log(f"audio direct: lang2(eng)={subs.lang2('eng')!r} lang1={lab('Skin.String(lucent.audio.lang1)')!r}")
            try:
                subs.fix_audio()
            except Exception as error:  # noqa: BLE001
                log(f"audio direct error {error!r}")
            mon.waitForAbort(2)
            res = json.loads(xbmc.executeJSONRPC(json.dumps({"jsonrpc": "2.0", "id": 1, "method": "Player.GetProperties",
                                                             "params": {"playerid": 1, "properties": ["currentaudiostream", "audiostreams"]}})))
            r = res.get("result") or {}
            cur = r.get("currentaudiostream") or {}
        log(f"audio state: play.start={HOME.getProperty('lucent.play.start')!r} now={time.time():.1f} trailer={HOME.getProperty('nuvio.trailer.playing')!r} title={lab('VideoPlayer.Title')!r} inet={cond('Player.IsInternetStream')}")
        log(f"audio run {run}: now {cur.get('language')} {cur.get('name')!r} ch={cur.get('channels')} of {[(a.get('language'), a.get('name')) for a in r.get('audiostreams') or []]}")
        xbmc.Player().stop()
        mon.waitForAbort(3)
    xbmc.executebuiltin("Skin.Reset(lucent.audio.lang1)")
    xbmc.executebuiltin("Skin.Reset(lucent.audio.lang2)")

def menumove_test():
    """1.35.1: the list options moved from Settings > Lucent to Skin settings (Layout > Lists and posters, Look, Integrations)."""
    for f in ("2206", "2501"):
        xbmc.executebuiltin(f"Skin.SetBool(lucent.ss.open.{f})")
    xbmc.executebuiltin("ActivateWindow(SkinSettings)")
    mon.waitForAbort(2.5)
    n = int(lab("Container(9000).NumItems") or 0)
    labels = [lab(f"Container(9000).ListItemAbsolute({i}).Label") for i in range(n)]
    log(f"menumove: cats {labels}")
    for cat, first, ids, name in ((1, 1230, (2206, 1230, 1231, 1232, 1233, 1234), "layout"), (0, 1112, (1111, 1112), "look"),
                                  (4, 1525, (1509, 1525), "integrations")):
        xbmc.executebuiltin(f"SetFocus(9000,{cat},absolute)")
        mon.waitForAbort(1.2)
        xbmc.executebuiltin("Action(Right)")
        mon.waitForAbort(0.6)
        xbmc.executebuiltin(f"SetFocus({first})")
        mon.waitForAbort(0.8)
        vis = {i: cond(f"Control.IsVisible({i})") for i in ids}
        log(f"menumove {name}: focus={lab('System.CurrentControlId')} visible={vis}")
        shot(f"menumove-{name}")
        path = [lab("System.CurrentControlId")]
        for _ in range(7):
            xbmc.executebuiltin("Action(Down)")
            mon.waitForAbort(0.35)
            path.append(lab("System.CurrentControlId"))
        log(f"menumove {name}: down path {path}")
    xbmc.executebuiltin("SetFocus(1230)")
    mon.waitForAbort(0.5)
    before = cond("Skin.HasSetting(lucent.mf.off)")
    xbmc.executebuiltin("SetFocus(9000,1,absolute)")
    mon.waitForAbort(1)
    xbmc.executebuiltin("Action(Right)")
    mon.waitForAbort(0.5)
    xbmc.executebuiltin("SetFocus(1230)")
    mon.waitForAbort(0.5)
    xbmc.executebuiltin("Action(Select)")
    mon.waitForAbort(0.8)
    log(f"menumove toggle: mf.off {before} -> {cond('Skin.HasSetting(lucent.mf.off)')}")
    xbmc.executebuiltin("Skin.Reset(lucent.mf.off)")
    for f in ("2206", "2501"):
        xbmc.executebuiltin(f"Skin.Reset(lucent.ss.open.{f})")
    xbmc.executebuiltin("ActivateWindow(home)")
    mon.waitForAbort(2)


def navwalk_test():
    """Every pane of the skin settings, all folds open: Down and Up through every row; report where focus sticks."""
    import re
    import xbmcvfs
    xml = open(xbmcvfs.translatePath("special://skin/xml/SkinSettings.xml"), encoding="utf-8").read()
    folds = sorted(set(re.findall(r"lucent\.ss\.open\.(\d+)", xml)))
    for f in folds:
        xbmc.executebuiltin(f"Skin.SetBool(lucent.ss.open.{f})")
    fid = lambda: lab("System.CurrentControlID")  # noqa: E731
    xbmc.executebuiltin("ActivateWindow(SkinSettings)")
    mon.waitForAbort(3)
    n = int(lab("Container(9000).NumItems") or 0)
    for c in range(n):
        xbmc.executebuiltin(f"SetFocus(9000,{c},absolute)")
        mon.waitForAbort(1.2)
        name = lab("Container(9000).ListItem.Label")
        xbmc.executebuiltin("Action(Right)")
        mon.waitForAbort(0.8)
        for direction in ("Down", "Up"):
            path = [fid()]
            for _ in range(45):
                xbmc.executebuiltin(f"Action({direction})")
                mon.waitForAbort(0.35)
                path.append(fid())
                if path[-1] == path[0] and len(path) > 2:
                    break
            stuck = [path[i] for i in range(1, len(path)) if path[i] == path[i - 1]]
            log(f"navwalk {c} {name!r} {direction}: {len(set(path))} rows, stuck at {sorted(set(stuck))}, path {path}")
        xbmc.executebuiltin("SetFocus(9000)")
        mon.waitForAbort(0.5)
    for f in folds:
        xbmc.executebuiltin(f"Skin.Reset(lucent.ss.open.{f})")
    xbmc.executebuiltin("ActivateWindow(home)")
    mon.waitForAbort(2)

def setup_test():
    """Setup assistant: the steps Subtitles and Look show their buttons."""
    xbmc.executebuiltin("RunScript(special://skin/scripts/setup.py)")
    mon.waitForAbort(4)
    for step in (5, 7):
        xbmc.executebuiltin(f"SetFocus(100,{step},absolute)")
        mon.waitForAbort(0.5)
        xbmc.executebuiltin("Action(Select)")
        mon.waitForAbort(2)
        acts = [lab(f"Window.Property(act{n})") for n in range(1, 5)]
        log(f"setup step {step}: {lab('Window.Property(stepno)')!r} buttons {acts}")
        shot(f"29-setup-{step}")
    xbmc.executebuiltin("Dialog.Close(all,true)")
    xbmc.executebuiltin("ActivateWindow(home)")
    mon.waitForAbort(2)

def maint_test():
    """Maintenance: zip files, old temp files and the old log go; two cached pictures are removed the proper way."""
    import sys
    import xbmcvfs
    sys.path.append(xbmcvfs.translatePath("special://skin/scripts"))
    import maintenance as m
    pk = xbmcvfs.translatePath("special://home/addons/packages/")
    os.makedirs(pk, exist_ok=True)
    open(os.path.join(pk, "old.addon-1.0.zip"), "wb").write(b"x" * 300000)
    tmp = os.path.join(xbmcvfs.translatePath("special://temp/"), "lucent-ci-old.tmp")
    open(tmp, "wb").write(b"y" * 1000)
    os.utime(tmp, (time.time() - 5 * 86400, time.time() - 5 * 86400))
    fresh = os.path.join(xbmcvfs.translatePath("special://temp/"), "lucent-ci-new.tmp")
    open(fresh, "wb").write(b"z")
    pics = m.old_pictures(-1)                       # every picture counts as old
    log(f"maint: found pkgs={len(m.packages())} temp={[os.path.basename(f) for f in m.temp_files()]} pictures={len(pics)}")
    two = [p for p in pics if p[1] and os.path.exists(p[1])][:2]
    freed = m.delete(m.packages()) + m.delete(m.temp_files()) + m.remove_pictures(two)
    left = [os.path.exists(p[1]) for p in two]
    still = {p[0] for p in m.old_pictures(-1)}
    log(f"maint: freed {m.size_text(freed)}; packages left {len(m.packages())}; old tmp gone {not os.path.exists(tmp)}; "
        f"new tmp kept {os.path.exists(fresh)}; picture files left {left}; picture ids left {[p[0] in still for p in two]}")
    xbmc.executebuiltin("Skin.SetBool(lucent.maint.auto)")
    xbmc.executebuiltin("Skin.Reset(lucent.maint.last)")
    mon.waitForAbort(1)
    m.auto()
    log(f"maint: auto ran, last={lab('Skin.String(lucent.maint.last)')!r}")
    xbmc.executebuiltin("Skin.Reset(lucent.maint.auto)")
    xbmc.executebuiltin("ActivateWindow(SkinSettings)")
    mon.waitForAbort(2)
    n = int(lab("Container(9000).NumItems") or 0)
    labels = [lab(f"Container(9000).ListItemAbsolute({i}).Label") for i in range(n)]
    if "Advanced" in labels:
        xbmc.executebuiltin(f"SetFocus(9000,{labels.index('Advanced')},absolute)")
        mon.waitForAbort(1)
        xbmc.executebuiltin("Action(Right)")
        mon.waitForAbort(0.5)
        path = [lab("System.CurrentControlID")]
        for _ in range(10):
            xbmc.executebuiltin("Action(Down)")
            mon.waitForAbort(0.35)
            path.append(lab("System.CurrentControlID"))
        log(f"maint: advanced pane path {path}")
        xbmc.executebuiltin("SetFocus(1809)")
        mon.waitForAbort(0.5)
        xbmc.executebuiltin("Action(Select)")
        mon.waitForAbort(3)
        log(f"maint: menu open={cond('Window.IsVisible(selectdialog)')} heading={lab('Control.GetLabel(1)')!r}")
        shot("30-maintenance")
        xbmc.executebuiltin("Dialog.Close(all,true)")
    xbmc.executebuiltin("ActivateWindow(home)")
    mon.waitForAbort(2)

def sameaudio_test():
    """Sound in your language (English here): the English subtitle goes off. Russian sound: it stays on."""
    log(f"same: kodi language={xbmc.getLanguage(xbmc.ISO_639_1)!r}")
    for a in ("eng", "rus"):
        xbmc.executebuiltin(f"PlayMedia(/tmp/ci/same-{a}.mkv)")
        mon.waitForAbort(25)
        log(f"same {a} sound: subtitle on={cond('VideoPlayer.SubtitlesEnabled')} lang={lab('VideoPlayer.SubtitlesLanguage')!r}")
        xbmc.Player().stop()
        mon.waitForAbort(3)

def skip_test():
    """TheIntroDB's skip window in the Lucent look: Kodi takes the skin's overlay.xml; the add-on sets the text."""
    import threading
    import xbmcaddon
    path = xbmcaddon.Addon("plugin.video.tidb").getAddonInfo("path")
    win = xbmcgui.WindowXMLDialog("overlay.xml", path, "default", "1080i")

    def later():
        mon.waitForAbort(2)
        try:
            win.getControl(3001).setLabel("Skip intro")
        except Exception as error:  # noqa: BLE001
            log(f"skip: label error {error!r}")
        mon.waitForAbort(1.5)
        log(f"skip: window={lab('System.CurrentWindow')!r} focus={lab('System.CurrentControlID')} label={lab('Control.GetLabel(3001)')!r}")
        shot("31-skip")
        win.close()
    threading.Thread(target=later).start()
    win.doModal()
    del win
    xbmc.executebuiltin("RunScript(special://skin/scripts/setup.py)")
    mon.waitForAbort(4)
    xbmc.executebuiltin("SetFocus(100,5,absolute)")
    mon.waitForAbort(0.5)
    xbmc.executebuiltin("Action(Select)")
    mon.waitForAbort(2)
    log(f"skip: setup {lab('Window.Property(stepno)')!r} buttons {[lab(f'Window.Property(act{n})') for n in range(1, 5)]}")
    xbmc.executebuiltin("Dialog.Close(all,true)")
    xbmc.executebuiltin("ActivateWindow(home)")
    mon.waitForAbort(2)

def skipkey_test():
    """Setup > Skip intro: a filled-in TheIntroDB API key gives an orange warning and a first button that removes it."""
    import xbmcaddon
    tidb = xbmcaddon.Addon("plugin.video.tidb")
    tidb.setSetting("introdb_api_key", "wrongkey123")
    log(f"skipkey: before key={tidb.getSetting('introdb_api_key')!r}")
    xbmc.executebuiltin("RunScript(special://skin/scripts/setup.py)")
    mon.waitForAbort(4)
    xbmc.executebuiltin("SetFocus(100,5,absolute)")
    mon.waitForAbort(0.5)
    xbmc.executebuiltin("Action(Select)")
    mon.waitForAbort(3)
    log(f"skipkey: step {lab('Window.Property(stepno)')!r} status={lab('Window.Property(status)')!r} color={lab('Window.Property(statecolor)')!r} "
        f"buttons {[lab(f'Window.Property(act{n})') for n in range(1, 5)]}")
    shot("33-skipkey-before")
    xbmc.executebuiltin("SetFocus(301)")
    mon.waitForAbort(0.5)
    xbmc.executebuiltin("Action(Select)")
    mon.waitForAbort(3)
    log(f"skipkey: after key={xbmcaddon.Addon('plugin.video.tidb').getSetting('introdb_api_key')!r} test={xbmcaddon.Addon('plugin.video.tidb').getSetting('test_api_key_now')!r} "
        f"status={lab('Window.Property(status)')!r} buttons {[lab(f'Window.Property(act{n})') for n in range(1, 5)]}")
    shot("33-skipkey-after")
    xbmc.executebuiltin("Dialog.Close(all,true)")
    xbmc.executebuiltin("ActivateWindow(home)")
    mon.waitForAbort(2)


def sportA_test():
    """Sport > All games: live games as cards (list 205) on top, then the games per competition (list 200)."""
    xbmc.executebuiltin("RunScript(special://skin/scripts/sport.py)")
    for _ in range(60):
        mon.waitForAbort(1)
        if cond("Window.IsVisible(Lucent_Sport.xml)"):
            break
    mon.waitForAbort(3)
    xbmc.executebuiltin("SetFocus(102)")
    mon.waitForAbort(1)
    xbmc.executebuiltin("Action(Select)")
    for _ in range(60):
        mon.waitForAbort(1)
        if int(lab("Container(200).NumItems") or 0) > 0:
            break
    mon.waitForAbort(4)
    P = lambda k: lab(f"Container(200).ListItem.Property({k})")  # noqa: E731
    C = lambda k: lab(f"Container(205).ListItem.Property({k})")  # noqa: E731
    n = int(lab("Container(200).NumItems") or 0)
    heads = [lab(f"Container(200).ListItemAbsolute({i}).Property(header)") + "/" + lab(f"Container(200).ListItemAbsolute({i}).Property(headersub)") for i in range(n)]
    ncards = int(lab("Container(205).NumItems") or 0)
    log(f"sportA: items={n} cards={ncards} live={lab('Window(Lucent_Sport.xml).Property(sport.live)') or lab('Window.Property(sport.live)')!r} strip visible={cond('Control.IsVisible(205)')}")
    log(f"sportA: competitions in order {[h for h in heads if h != '/']}")
    xbmc.executebuiltin("SetFocus(114)")
    mon.waitForAbort(1)
    xbmc.executebuiltin("Action(Down)")
    mon.waitForAbort(1.5)
    log(f"sportA: day strip Down -> focus={lab('System.CurrentControlID')}")
    shot("32-sportA-top")
    if ncards:
        for step in range(min(3, ncards)):
            log(f"sportA: card {step}: {C('hname')}-{C('aname')} {C('score')!r} min={C('min')!r} chan={C('chan')!r} prog={C('prog')!r} "
                f"panel={P('hname')}-{P('aname')} same={C('evid') == P('evid')} focus={lab('System.CurrentControlID')}")
            xbmc.executebuiltin("Action(Right)")
            mon.waitForAbort(1.5)
        shot("32-sportA-right")
        xbmc.executebuiltin("Action(Down)")
        mon.waitForAbort(1.5)
        log(f"sportA: cards Down -> focus={lab('System.CurrentControlID')}")
        xbmc.executebuiltin("SetFocus(200,0,absolute)")
        mon.waitForAbort(1.5)
        xbmc.executebuiltin("Action(Up)")
        mon.waitForAbort(1.5)
        log(f"sportA: list top Up -> focus={lab('System.CurrentControlID')}")
    xbmc.executebuiltin("SetFocus(200,0,absolute)")
    mon.waitForAbort(1.5)
    for _ in range(4):
        xbmc.executebuiltin("Action(Down)")
        mon.waitForAbort(1.2)
    log(f"sportA: after 4x down: {P('hname')!r} header={P('header')!r} focus={lab('System.CurrentControlID')}")
    shot("32-sportA-list")
    xbmc.executebuiltin("SetFocus(101)")
    mon.waitForAbort(1)
    xbmc.executebuiltin("Action(Select)")
    mon.waitForAbort(5)
    log(f"sportA: mine view strip visible={cond('Control.IsVisible(205)')} view={lab('Window.Property(sport.view)')!r}")
    shot("32-sportA-mine")
    xbmc.executebuiltin("Dialog.Close(all,true)")
    xbmc.executebuiltin("ActivateWindow(home)")
    mon.waitForAbort(2)


def tables_test():
    """Sport > Tables (T1+T2): competitions as tabs, table with W/D/L, club panel that follows the selected row."""
    xbmc.executebuiltin("RunScript(special://skin/scripts/sport.py)")
    for _ in range(60):
        mon.waitForAbort(1)
        if cond("Window.IsVisible(Lucent_Sport.xml)"):
            break
    mon.waitForAbort(3)
    xbmc.executebuiltin("SetFocus(103)")
    mon.waitForAbort(1)
    xbmc.executebuiltin("Action(Select)")
    for _ in range(40):
        mon.waitForAbort(1)
        if int(lab("Container(410).NumItems") or 0) > 0:
            break
    mon.waitForAbort(4)
    W = lambda k: lab(f"Window(Lucent_Sport.xml).Property(sport.tc.{k})") or lab(f"Window.Property(sport.tc.{k})")  # noqa: E731
    R = lambda k: lab(f"Container(410).ListItem.Property({k})")  # noqa: E731
    log(f"tables: league={lab('Container(400).ListItem.Label')!r} n={lab('Container(410).NumItems')} focus={lab('System.CurrentControlID')} "
        f"row={lab('Container(410).ListItem.Label')!r} gp/w/d/l/gd/pts={[R(k) for k in ('gp', 'w', 'd', 'l', 'gd', 'pts')]} "
        f"legend={[lab(f'Window.Property(sport.leg{n}.text)') for n in range(1, 5)]}")
    log(f"tables: panel on={W('on')!r} name={W('name')!r} sub={W('sub')!r} form={[W(f'f{n}') for n in range(1, 6)]} "
        f"r1={W('r1')!r} {W('r1s')!r} home={W('home')!r} away={W('away')!r} next={W('next')!r} chan={W('nextchan')!r}")
    shot("34-tables-top")
    for _ in range(3):
        xbmc.executebuiltin("Action(Down)")
        mon.waitForAbort(1.5)
    log(f"tables: after 3x down row={lab('Container(410).ListItem.Label')!r} panel={W('name')!r} sub={W('sub')!r} r1={W('r1')!r}")
    shot("34-tables-down")
    xbmc.executebuiltin("Action(Up)")
    mon.waitForAbort(0.5)
    xbmc.executebuiltin("SetFocus(400)")
    mon.waitForAbort(1)
    xbmc.executebuiltin("Action(Right)")
    mon.waitForAbort(4)
    log(f"tables: league right -> {lab('Container(400).ListItem.Label')!r} n={lab('Container(410).NumItems')} row={lab('Container(410).ListItem.Label')!r} panel={W('name')!r}")
    shot("34-tables-league2")
    xbmc.executebuiltin("Dialog.Close(all,true)")
    xbmc.executebuiltin("ActivateWindow(home)")
    mon.waitForAbort(2)


def mine_test():
    """My sport M3: follow the home team of a live football game, then My sport shows it as a live scoreboard."""
    import sys as _sys
    _sys.path.insert(0, xbmcvfs.translatePath("special://skin/scripts"))
    import sport_core as sc
    live = [e for e in sc.all_cached() if e["state"] == "in" and e["kind"] == "teams"]
    soccer = [e for e in live if sc.LEAGUES.get(e["league"], {}).get("sport") == "soccer"] or live
    log(f"mine: live games={len(live)} football={len(soccer)}")
    if not soccer:
        soccer = sorted((e for e in sc.all_cached() if e["state"] == "pre" and e["kind"] == "teams"
                         and sc.LEAGUES.get(e["league"], {}).get("sport") == "soccer"), key=lambda e: e["start"])[:1]
    if not soccer:
        return
    ev = soccer[0]
    sc.toggle_team(ev["league"], ev["home"])
    log(f"mine: following {ev['home'].get('name')!r} ({ev['league']}) {ev.get('status')!r}")
    xbmc.executebuiltin("RunScript(special://skin/scripts/sport.py)")
    for _ in range(60):
        mon.waitForAbort(1)
        if cond("Window.IsVisible(Lucent_Sport.xml)"):
            break
    mon.waitForAbort(4)
    xbmc.executebuiltin("SetFocus(101)")
    mon.waitForAbort(0.5)
    xbmc.executebuiltin("Action(Select)")
    mon.waitForAbort(12)
    H = lambda k: lab(f"Container(150).ListItem.Property({k})")  # noqa: E731
    WP = lambda k: lab(f"Window.Property({k})")  # noqa: E731
    log(f"mine: hero n={lab('Container(150).NumItems')} {H('hname')}-{H('aname')} mid={H('mid')!r} when={H('when')!r} prog={H('prog')!r} "
        f"hgoals={H('hgoals')!r} agoals={H('agoals')!r}")
    log(f"mine: sections {[(WP(f'sport.sec{n}.title'), WP(f'sport.sec{n}.sub'), WP(f'sport.sec{n}.count')) for n in range(1, 4)]}")
    log(f"mine: top={H('topline')!r} watch={H('watchlabel')!r} cols={H('hfull')!r}/{H('afull')!r} week={lab('Container(209).NumItems')} also={lab('Container(160).NumItems')}")
    shot("35-mine-live")
    xbmc.executebuiltin("SetFocus(209)")
    mon.waitForAbort(1.5)
    shot("35-mine-week")
    sc.toggle_team(ev["league"], ev["home"])
    xbmc.executebuiltin("Dialog.Close(all,true)")
    xbmc.executebuiltin("ActivateWindow(home)")
    mon.waitForAbort(2)


def follow_test():
    """Follow page F3: cards of what you follow, + Add opens Search / Browse / Countries / Drivers & players."""
    xbmc.executebuiltin("RunScript(special://skin/scripts/sport.py)")
    for _ in range(60):
        mon.waitForAbort(1)
        if cond("Window.IsVisible(Lucent_Sport.xml)"):
            break
    mon.waitForAbort(3)
    xbmc.executebuiltin("SetFocus(104)")
    mon.waitForAbort(0.5)
    xbmc.executebuiltin("Action(Select)")
    mon.waitForAbort(4)
    C = lambda k: lab(f"Container(570).ListItem.Property({k})")  # noqa: E731
    log(f"follow: cards={lab('Container(570).NumItems')} first={lab('Container(570).ListItem.Label')!r} sub={C('sub')!r} next={C('next')!r} "
        f"goals={C('goals')!r} remind={C('remind')!r} count={lab('Window.Property(sport.f.count)')!r}")
    shot("36-follow-cards")
    xbmc.executebuiltin("SetFocus(571)")
    mon.waitForAbort(0.5)
    xbmc.executebuiltin("Action(Select)")
    mon.waitForAbort(3)
    log(f"follow: add={lab('Window.Property(sport.f.add)')!r} tab={lab('Window.Property(sport.f.tab)')!r} focus={lab('System.CurrentControlID')} "
        f"tabs={[lab(f'Container(575).ListItemAbsolute({i}).Label') for i in range(4)]}")
    xbmc.executebuiltin("Action(Select)")
    mon.waitForAbort(2)
    xbmc.executeJSONRPC(json.dumps({"jsonrpc": "2.0", "id": 1, "method": "Input.SendText", "params": {"text": "Ajax", "done": True}}))
    mon.waitForAbort(3)
    R = lambda k: lab(f"Container(582).ListItem.Property({k})")  # noqa: E731
    log(f"follow: search q={lab('Window.Property(sport.f.query)')!r} results={lab('Container(582).NumItems')} focus={lab('System.CurrentControlID')} "
        f"first={lab('Container(582).ListItem.Label')!r}/{lab('Container(582).ListItem.Label2')!r} btn={R('btn')!r}")
    shot("36-follow-search")
    xbmc.executebuiltin("Action(Select)")
    mon.waitForAbort(1.5)
    log(f"follow: after OK btn={R('btn')!r} mine={R('mine')!r}")
    xbmc.executebuiltin("SetFocus(575)")
    mon.waitForAbort(0.5)
    xbmc.executebuiltin("Action(Right)")
    mon.waitForAbort(2)
    log(f"follow: tab -> {lab('Window.Property(sport.f.tab)')!r} sports={lab('Container(530).NumItems')} comps={lab('Container(540).NumItems')}")
    shot("36-follow-browse")
    xbmc.executebuiltin("Action(Right)")
    mon.waitForAbort(1.5)
    xbmc.executebuiltin("Action(Down)")
    mon.waitForAbort(1.5)
    log(f"follow: tab -> {lab('Window.Property(sport.f.tab)')!r} countries={lab('Container(590).NumItems')} focus={lab('System.CurrentControlID')} first={lab('Container(590).ListItem.Label')!r}")
    xbmc.executebuiltin("Action(Select)")
    mon.waitForAbort(1)
    log(f"follow: country mine={lab('Container(590).ListItem.Property(mine)')!r}")
    shot("36-follow-countries")
    xbmc.executebuiltin("SetFocus(575)")
    mon.waitForAbort(0.5)
    xbmc.executebuiltin("Action(Right)")
    mon.waitForAbort(1.5)
    log(f"follow: tab -> {lab('Window.Property(sport.f.tab)')!r} names={lab('Container(596).NumItems')} first={lab('Container(596).ListItem.Label')!r}")
    shot("36-follow-names")
    xbmc.executebuiltin("Action(Back)")
    mon.waitForAbort(4)
    log(f"follow: back add={lab('Window.Property(sport.f.add)')!r} cards={lab('Container(570).NumItems')} labels={[lab(f'Container(570).ListItemAbsolute({i}).Label') for i in range(4)]} focus={lab('System.CurrentControlID')}")
    shot("36-follow-after")
    xbmc.executebuiltin("SetFocus(570,0,absolute)")
    mon.waitForAbort(1)
    xbmc.executebuiltin("Action(Select)")
    mon.waitForAbort(2)
    log(f"follow: card menu window={lab('System.CurrentWindow')!r} dialog={cond('Window.IsActive(contextmenu)')}")
    shot("36-follow-menu")
    xbmc.executebuiltin("Action(Back)")
    mon.waitForAbort(1)
    tk = xbmcvfs.translatePath("special://profile/keymaps/lucent-touch.xml")
    log(f"touch keymap exists={os.path.exists(tk)}")
    xbmc.executebuiltin("Dialog.Close(all,true)")
    xbmc.executebuiltin("ActivateWindow(home)")
    mon.waitForAbort(2)


def f1_test():
    """F1 game page: the track drawing turns white and lies on a dark glass panel."""
    import sys as _sys
    _sys.path.insert(0, xbmcvfs.translatePath("special://skin/scripts"))
    import sport_core as sc
    races = [e for e in sc.all_cached() if e["league"] == "f1" and e["state"] != "post"]
    races.sort(key=lambda e: ("race" not in (e.get("sub") or "").lower(), e["start"]))
    log(f"f1: events={len(races)} first={(races[0].get('title'), races[0].get('sub'), races[0]['id']) if races else None}")
    try:
        c = sc.circuit_info("617", "f1")
        log(f"f1: circuit 617 dark={c.get('dark')!r} png={c.get('png')!r} photo={c.get('photo')!r}")
    except Exception as error:  # noqa: BLE001
        log(f"f1: circuit_info error {error!r}")
    if not races:
        return
    xbmc.executebuiltin(f"RunScript(special://skin/scripts/sport.py,game,{races[0]['id']})")
    for _ in range(40):
        mon.waitForAbort(1)
        if lab("Window.Property(g.circname)") and lab("Window.Property(g.circimg)"):
            break
    mon.waitForAbort(4)
    img = lab("Window.Property(g.circimg)")
    log(f"f1: photo={lab('Window.Property(g.circphoto)')[-40:]!r} page layout={lab('Window.Property(g.layout)')!r} circ={lab('Window.Property(g.circname)')!r} img={img.rsplit('/', 1)[-1]!r} "
        f"white={lab('Window.Property(g.circpng)')!r} tiles={[lab(f'Window.Property(g.circt{n}v)') for n in range(1, 5)]}")
    local = xbmcvfs.translatePath(img) if img.startswith("special://") else ""
    if local and os.path.exists(local):
        import struct
        raw = open(local, "rb").read()
        log(f"f1: white png size={len(raw)} type={raw[25]} wh={struct.unpack('>II', raw[16:24])}")
    shot("37-f1-page")
    xbmc.executebuiltin("Dialog.Close(all,true)")
    mon.waitForAbort(1)
    xbmc.executebuiltin("Dialog.Close(all,true)")
    xbmc.executebuiltin("ActivateWindow(home)")
    mon.waitForAbort(2)


def probe_test():
    """Where can a stadium photo come from? ESPN game summary, ESPN team page, TheSportsDB."""
    import sys as _sys
    import urllib.request
    _sys.path.insert(0, xbmcvfs.translatePath("special://skin/scripts"))
    import sport_core as sc

    def get(url):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            return json.loads(urllib.request.urlopen(req, timeout=20).read().decode("utf-8", "replace"))
        except Exception as error:  # noqa: BLE001
            return {"error": repr(error)}
    games = [e for e in sc.all_cached() if e["league"] in ("ned.1", "eng.1", "nba", "nfl") and e["kind"] == "teams"][:4]
    for ev in games:
        eid = ev["id"].split(":", 1)[-1]
        d = get(f"{sc.ESPN}{sc.LEAGUES[ev['league']]['path']}/summary?event={eid}")
        venue = (d.get("gameInfo") or {}).get("venue") or {}
        log(f"probe summary {ev['league']} {ev['home'].get('name')}: venue={venue.get('fullName')!r} images={[i.get('href') for i in venue.get('images') or []][:3]} err={d.get('error')}")
        t = get(f"{sc.ESPN}{sc.LEAGUES[ev['league']]['path']}/teams/{ev['home'].get('id')}")
        team = t.get("team") or {}
        fv = (team.get("franchise") or {}).get("venue") or team.get("venue") or {}
        log(f"probe team {ev['home'].get('name')}: keys={sorted(team)[:25]} venue={fv.get('fullName')!r} images={[i.get('href') for i in fv.get('images') or []][:3]}")
    for key in ("3", "123"):
        d = get(f"https://www.thesportsdb.com/api/v1/json/{key}/searchteams.php?t=Ajax")
        teams = d.get("teams") or []
        log(f"probe tsdb key {key}: n={len(teams)} err={d.get('error')} stadium={(teams[0].get('strStadium'), teams[0].get('strStadiumThumb') or teams[0].get('strVenueThumb'), teams[0].get('strFanart1')) if teams else None}")


def club_test():
    """Club page: logo behind the games, club colours, stadium photo in the TV window; All games: stadium of the home team."""
    import sys as _sys
    _sys.path.insert(0, xbmcvfs.translatePath("special://skin/scripts"))
    import sport_core as sc
    row = next((r for r in sc.standings("ned.1") if "Ajax" in (r.get("team") or "")), None)
    log(f"club: ajax row={(row or {}).get('id')!r}")
    if not row:
        return
    xbmc.executebuiltin(f"RunScript(special://skin/scripts/sport.py,team,ned.1,{row['id']},{row['team']})")
    for _ in range(30):
        mon.waitForAbort(1)
        if lab("Window.Property(sport.view)") == "team" and lab("Window.Property(sport.stadium)"):
            break
    mon.waitForAbort(3)
    W = lambda k: lab(f"Window.Property({k})")  # noqa: E731
    log(f"club: view={W('sport.view')!r} games={lab('Container(200).NumItems')} logo={W('sport.teamlogo')[-40:]!r} bg={W('sport.bgA')!r} "
        f"stadium={W('sport.stadium')[-60:]!r} name={W('sport.stadium.name')!r}")
    shot("38-club")
    xbmc.executebuiltin("SetFocus(102)")
    mon.waitForAbort(0.5)
    xbmc.executebuiltin("Action(Select)")
    mon.waitForAbort(4)
    xbmc.executebuiltin("SetFocus(200,1,absolute)")
    mon.waitForAbort(1)
    xbmc.executebuiltin("Action(Down)")
    for _ in range(15):
        mon.waitForAbort(1)
        if W("sport.stadium"):
            break
    log(f"club: all games on {lab('Container(200).ListItem.Property(hname)')!r} stadium={W('sport.stadium')[-60:]!r} name={W('sport.stadium.name')!r}")
    shot("38-allgames-stadium")
    xbmc.executebuiltin("Dialog.Close(all,true)")
    xbmc.executebuiltin("ActivateWindow(home)")
    mon.waitForAbort(2)


def guide_test():
    """TV guide G1 (no channels in CI: only the frame, the header and the buttons)."""
    xbmc.executebuiltin("ActivateWindow(TVGuide)")
    mon.waitForAbort(6)
    log(f"guide: window={lab('System.CurrentWindow')!r} focus={lab('System.CurrentControlID')} groups={lab('Container(11).NumItems')}")
    shot("39-guide")
    xbmc.executebuiltin("ActivateWindow(home)")
    mon.waitForAbort(2)


def browse_test():
    """Issue #3: the file browser that add-ons open (Dialog().browse) must list the files, not only '..'."""
    import threading
    for typ, mask, start in ((1, "", "special://skin/xml/"), (1, ".xml", "special://skin/xml/"), (2, "", "special://skin/media/"),
                             (1, "", "special://skin/")):
        def later(typ=typ, mask=mask):
            mon.waitForAbort(4)
            n = lab("Container(450).NumItems")
            log(f"browse: type={typ} mask={mask!r} window={lab('System.CurrentWindow')!r} focus={lab('System.CurrentControlID')} "
                f"items450={n} items451={lab('Container(451).NumItems')} first={[lab(f'Container(450).ListItemAbsolute({i}).Label') for i in range(4)]} "
                f"vis450={cond('Control.IsVisible(450)')} vis451={cond('Control.IsVisible(451)')}")
            shot(f"40-browse-{typ}-{mask.strip('.') or 'all'}")
            xbmc.executebuiltin("Action(Back)")
        t = threading.Thread(target=later)
        t.start()
        xbmcgui.Dialog().browse(typ, "Test", "files", mask, False, False, start)
        t.join()
        mon.waitForAbort(1)


def w1_test():
    """Game page W1: a football game (a finished one has statistics and a timeline)."""
    import sys as _sys
    _sys.path.insert(0, xbmcvfs.translatePath("special://skin/scripts"))
    import sport_core as sc
    games = [e for e in sc.all_cached() if e["kind"] == "teams" and sc.LEAGUES.get(e["league"], {}).get("sport") == "soccer"]
    games.sort(key=lambda e: ({"in": 0, "post": 1, "pre": 2}[e["state"]], -e["start"] if e["state"] == "post" else e["start"]))
    log(f"w1: games={len(games)} first={(games[0]['home'].get('name'), games[0]['away'].get('name'), games[0]['state']) if games else None}")
    if not games:
        return
    xbmc.executebuiltin(f"RunScript(special://skin/scripts/sport.py,game,{games[0]['id']})")
    for _ in range(30):
        mon.waitForAbort(1)
        if lab("Window.Property(g.layout)") == "teams" and lab("Window.Property(g.st1l)"):
            break
    mon.waitForAbort(4)
    W = lambda k: lab(f"Window.Property(g.{k})")  # noqa: E731
    log(f"w1: top={W('topline')!r} mid={W('bigmid')!r} sub={W('bigsub')!r} lines={W('hline')!r}/{W('aline')!r} goals={W('hgoals')!r}/{W('agoals')!r} "
        f"stats={[W(f'st{n}l') + ':' + W(f'st{n}h') + '-' + W(f'st{n}a') + '/' + W(f'st{n}k') for n in range(1, 5)]} "
        f"timeline={[W(f'tl{n}m') + ' ' + W(f'tl{n}k') + ' ' + W(f'tl{n}x') for n in range(1, 4)]} table={W('tabletitle')!r} focus={lab('System.CurrentControlID')}")
    log(f"w1: remind={W('remindtext')!r} rec={W('rectext')!r} vis1330={cond('Control.IsVisible(1330)')} vis1332={cond('Control.IsVisible(1332)')} table={W('table')!r}")
    shot("41-w1")
    xbmc.executebuiltin("Dialog.Close(all,true)")
    mon.waitForAbort(1)
    xbmc.executebuiltin("Dialog.Close(all,true)")
    xbmc.executebuiltin("ActivateWindow(home)")
    mon.waitForAbort(2)


def w3_test():
    """Game page for basketball (W3): points per quarter, top players, team stats."""
    import sys as _sys
    _sys.path.insert(0, xbmcvfs.translatePath("special://skin/scripts"))
    import sport_core as sc
    games = [e for e in sc.all_cached() if e["kind"] == "teams" and e["league"] == "nba"]
    games.sort(key=lambda e: ({"in": 0, "post": 1, "pre": 2}[e["state"]], -e["start"] if e["state"] == "post" else e["start"]))
    log(f"w3: games={len(games)} first={(games[0]['home'].get('name'), games[0]['state']) if games else None}")
    if not games:
        return
    xbmc.executebuiltin(f"RunScript(special://skin/scripts/sport.py,game,{games[0]['id']})")
    for _ in range(30):
        mon.waitForAbort(1)
        if lab("Window.Property(g.layout)") == "teams" and lab("Window.Property(g.tp1n)"):
            break
    mon.waitForAbort(3)
    W = lambda k: lab(f"Window.Property(g.{k})")  # noqa: E731
    log(f"w3: mid={W('bigmid')!r} qn={W('qn')!r} q={[W(f'qh{i}') + '/' + W(f'qa{i}') for i in range(1, 5)]} "
        f"stats={[W(f'st{n}l') + ':' + W(f'st{n}h') + '-' + W(f'st{n}a') for n in range(1, 5)]} top={[W(f'tp{n}n') + ' ' + W(f'tp{n}v') for n in range(1, 5)]}")
    shot("42-w3")
    xbmc.executebuiltin("Dialog.Close(all,true)")
    mon.waitForAbort(1)
    xbmc.executebuiltin("Dialog.Close(all,true)")
    xbmc.executebuiltin("ActivateWindow(home)")
    mon.waitForAbort(2)


def pagelimit_test():
    """Number of titles: choosing 100 for a Seren row offers to raise Seren's page limit (20) and does it."""
    import sys as _sys
    import threading
    import xbmcaddon
    _sys.path.insert(0, xbmcvfs.translatePath("special://skin/scripts"))
    import menu
    ser = xbmcaddon.Addon("plugin.video.seren")
    log(f"limit: before={ser.getSetting('item.limit')!r}")
    t = threading.Thread(target=menu.source_page, args=({"limit": "100", "path": "plugin://plugin.video.seren/?action=x"},), daemon=True)
    t.start()
    for _ in range(15):
        mon.waitForAbort(1)
        if cond("Window.IsActive(yesnodialog)"):
            break
    log(f"limit: dialog={cond('Window.IsActive(yesnodialog)')} text={lab('Control.GetLabel(9)')!r}")
    shot("50-limit-ask")
    xbmc.executebuiltin("SendClick(11)")
    t.join(10)
    mon.waitForAbort(1)
    log(f"limit: after={xbmcaddon.Addon('plugin.video.seren').getSetting('item.limit')!r}")
    shot("51-limit-done")
    # a non-Seren add-on: only a notification, no question
    menu.source_page({"limit": "50", "path": "plugin://plugin.video.youtube/"})
    mon.waitForAbort(1)
    log(f"limit: other dialog={cond('Window.IsActive(yesnodialog)')}")
    xbmc.executebuiltin("Dialog.Close(all,true)")
    mon.waitForAbort(1)


def panels_test():
    """Tabs without rows of their own (Calendar, TV, Sport, Add-ons, Settings, Power) show their own screen."""
    import sys as _sys
    import datetime as _dt
    _sys.path.insert(0, xbmcvfs.translatePath("special://skin/scripts"))
    import menu
    import tabpanels
    m = menu.Menu()
    for label, action in (("TV", "RunScript(special://skin/scripts/tv.py)"), ("Sport", "RunScript(special://skin/scripts/sport.py)"),
                          ("Add-ons", "ActivateWindow(AddonBrowser)"), ("Settings", "ActivateWindow(Settings)"), ("Power", "ActivateWindow(ShutdownMenu)")):
        if not any(t["action"] == action for t in m.tabs) and len(m.tabs) < menu.NTABS:
            m.tabs.append({"label": label, "icon": "icons/tv.png", "action": action, "widgets": [], "actionlabel": ""})
    m.save()
    # a week of calendar items
    data = xbmcvfs.translatePath("special://profile/addon_data/skin.lucent/")
    os.makedirs(data, exist_ok=True)
    art = "special://home/addons/plugin.video.fakeseren/icon.png"
    today = _dt.date.today()
    evs = []
    for n, (name, days, at) in enumerate((("The Northern Line", 20, "21:00"), ("Harbor Lights", 21, "20:00"), ("Kitchen Wars", 30, ""), ("Silent Peak", 40, ""))):
        evs.append({"kind": "tv" if n < 3 else "movie", "key": f"k{n}", "name": name, "title": "De laatste halte" if n == 0 else "",
                    "season": 3, "episode": 5 + n, "date": (today + _dt.timedelta(days=days)).isoformat(), "time": at,
                    "still": art, "backdrop": art, "network": "HBO Max" if n == 0 else "", "plot": "Mara ontdekt wie er achter de verdwenen trein zit.",
                    "tmdb": 100 + n, "logo": "", "digital": True})
    json.dump({"shows": {"tv:1": {"name": "x", "kind": "tv", "tmdb": 1, "notify": True}}, "synced": time.time()}, open(data + "agenda_follow.json", "w"))
    import agenda_core
    json.dump({"v": agenda_core.CACHE_VERSION, "shows": {"tv:1": {"events": evs, "fetched": time.time()}}}, open(data + "agenda_cache.json", "w"))
    tabpanels.update()
    rows = [("1", "Ajax", "PSV", "2", "1", "LIVE 67'", "1", "D2122E", "ED1C24"), ("2", "Feyenoord", "AZ", "", "", "18:45", "", "E30613", "C8102E"),
            ("3", "Real Madrid", "Barcelona", "", "", "21:00", "", "1C3C8C", "A50044")]
    def set_sport():
      for n, (i, hn, an, hs, as_, when, live, hc, ac) in enumerate(rows, 1):
        for k, v in {"id": i, "hname": hn, "aname": an, "hs": hs, "as": as_, "when": when, "live": live, "hcol": hc, "acol": ac,
                     "hlogo": art, "alogo": art, "league": "Eredivisie", "kick": ("LIVE · EREDIVISIE · 67'" if live else f"{when} · EREDIVISIE"),
                     "big": f"{hs} – {as_}" if hs else when}.items():
            HOME.setProperty(f"lucent.ps.{n}.{k}", v)
    set_sport()
    log(f"panels: cal1={HOME.getProperty('lucent.pc.1.title')!r} day={HOME.getProperty('lucent.pc.1.day')!r} cal4={HOME.getProperty('lucent.pc.4.title')!r} sub4={HOME.getProperty('lucent.pc.4.sub')!r}")
    xbmc.executebuiltin("ActivateWindow(home)")
    mon.waitForAbort(3)
    wanted = [("cal", "agenda.py", 9310), ("tv", "scripts/tv.py", 9320), ("sport", "scripts/sport.py", 9330),
              ("addons", "AddonBrowser", 9340), ("settings", "ActivateWindow(Settings)", 9350), ("power", "ShutdownMenu", 9360)]
    count = int(lab("Container(9000).NumItems") or 0)
    acts = []
    for i in range(count):
        xbmc.executebuiltin(f"Control.SetFocus(9000,{i})")
        mon.waitForAbort(0.4)
        acts.append(lab("Container(9000).ListItem.Property(act)"))
    log(f"panels: tabs={[a[-30:] for a in acts]}")
    for name, needle, cid in wanted:
        idx = next((i for i, a in enumerate(acts) if needle in a), None)
        if idx is None:
            log(f"panels: {name} tab missing")
            continue
        xbmc.executebuiltin(f"Control.SetFocus(9000,{idx})")
        tabpanels.update()                  # the helper may have cleared the test values
        set_sport()
        mon.waitForAbort(2)
        set_sport()
        mon.waitForAbort(1)
        log(f"panels: {name} ps1={HOME.getProperty('lucent.ps.1.id')!r} pc1={HOME.getProperty('lucent.pc.1.title')!r} panel={cond('Control.IsVisible(' + str(cid) + ')')} rows9100={cond('Control.IsVisible(9100)')} items={lab(f'Container({cid}).NumItems')}")
        shot(f"6{wanted.index((name, needle, cid))}-{name}-menu")
        xbmc.executebuiltin("Action(Right)")
        mon.waitForAbort(2)
        log(f"panels: {name} right focus={xbmc.getInfoLabel('System.CurrentControlId')} has={cond(f'Control.HasFocus({cid})')} label={lab(f'Container({cid}).ListItem.Label')!r}")
        shot(f"6{wanted.index((name, needle, cid))}-{name}-in")
        xbmc.executebuiltin("Action(Left)")
        mon.waitForAbort(1)
    # back to the start tab: its rows again
    xbmc.executebuiltin("Control.SetFocus(9000,0)")
    mon.waitForAbort(3)
    log(f"panels: back start rows9100={cond('Control.IsVisible(9100)')} panel={cond('Control.IsVisible(9310)')}")


def updater_test():
    """The update check reads the newest list (cache-busting address) and the new zip can be downloaded."""
    import sys as _sys
    _sys.path.insert(0, xbmcvfs.translatePath("special://skin/scripts"))
    import updater
    try:
        found = updater.fetch_available()
        log(f"upd: skin={found.get('skin.lucent', ('?',))[0]} library={found.get('script.lucent.library', ('?',))[0]}")
        ups = updater.available_updates()
        log(f"upd: updates={[(u['id'], u['have'], u['version']) for u in ups]}")
        skin = next((u for u in ups if u["id"] == "skin.lucent"), None)
        if skin:
            path = updater.download_zip(skin)
            log(f"upd: zip {os.path.getsize(path)} bytes")
    except Exception as error:  # noqa: BLE001
        log(f"upd: error {error!r}")


def readme_test():
    """Screenshots for the README: Home, side menu, the tab screens, the views, calendar, settings, keyboard."""
    import sys as _sys
    import datetime as _dt
    _sys.path.insert(0, xbmcvfs.translatePath("special://skin/scripts"))
    import menu
    import tabpanels
    import agenda_core
    FS = "plugin://plugin.video.fakeseren/?list="
    ART = "special://home/addons/plugin.video.fakeseren/art/"

    def w(label, kind, style):
        return {"label": label, "path": FS + kind, "style": style}
    home = [w("Continue watching · Shows", "se", "land"), w("Trending movies", "sm", "poster"), w("Popular shows", "ss", "poster")]
    tab = lambda label, icon, action, widgets=None: {"label": label, "icon": f"icons/{icon}.png", "action": action,  # noqa: E731
                                                     "widgets": widgets or [], "actionlabel": ""}
    m = menu.Menu()
    m.tabs = [tab("Search", "search", "ActivateWindow(Videos,plugin://plugin.video.fakeseren/?list=sm,return)"),
              tab("Home", "home", menu.SHOW_WIDGETS, home),
              tab("Movies", "movies", "ActivateWindow(Videos,plugin://plugin.video.fakeseren/?list=sm,return)", [w("Trending movies", "sm", "poster"), w("Continue watching · Shows", "se", "land")]),
              tab("Shows", "tv", "ActivateWindow(Videos,plugin://plugin.video.fakeseren/?list=ss,return)", [w("Popular shows", "ss", "poster")]),
              tab("Calendar", "calendar", "RunScript(special://skin/scripts/agenda.py)"),
              tab("TV", "tv", "RunScript(special://skin/scripts/tv.py)"),
              tab("Sport", "sport", "RunScript(special://skin/scripts/sport.py)"),
              tab("Add-ons", "addons", "ActivateWindow(AddonBrowser)"),
              tab("Settings", "settings", "ActivateWindow(Settings)"),
              tab("Power", "power", "ActivateWindow(ShutdownMenu)")]
    m.start = m.tabs[1]
    m.save()
    # calendar data
    data = xbmcvfs.translatePath("special://profile/addon_data/skin.lucent/")
    os.makedirs(data, exist_ok=True)
    today = _dt.date.today()
    names = [("Glasswork", 0, "21:00"), ("Red Harbour", 1, "20:00"), ("Lumen", 2, "22:00"), ("Night Ferry", 3, ""), ("Northbound", 5, ""), ("Copper Sky", 6, "")]
    evs = []
    for n, (name, days, at) in enumerate(names):
        evs.append({"kind": "tv" if n != 4 else "movie", "key": f"k{n}", "show": f"tv:{n}", "name": name, "title": f"Chapter {5 + n}" if n != 4 else "",
                    "season": 2, "episode": 7 + n, "date": (today + _dt.timedelta(days=days)).isoformat(), "time": at,
                    "still": f"{ART}f{n}.jpg", "backdrop": f"{ART}f{n}.jpg", "poster": f"{ART}p{n}.jpg", "network": ["HBO Max", "Netflix", "Apple TV+", "Disney+", "", "Prime Video"][n],
                    "plot": "A fictional placeholder synopsis used for this screenshot. The real text comes from TMDB.",
                    "tmdb": 100 + n, "logo": "", "digital": True, "rating": 8.1, "genre": "Drama", "runtime": 52})
    json.dump({"shows": {"tv:1": {"name": "x", "kind": "tv", "tmdb": 1, "notify": True}}, "synced": time.time()}, open(data + "agenda_follow.json", "w"))
    json.dump({"v": agenda_core.CACHE_VERSION, "shows": {"tv:1": {"events": evs, "fetched": time.time()}}}, open(data + "agenda_cache.json", "w"))
    rows = [("1", "Ajax", "PSV", "2", "1", "LIVE 67'", "1", "D2122E", "ED1C24", 0, 1), ("2", "Feyenoord", "AZ", "", "", "18:45", "", "E30613", "C8102E", 2, 3),
            ("3", "Real Madrid", "Barcelona", "", "", "21:00", "", "1C3C8C", "A50044", 4, 5)]

    def set_sport():
        for n, (i, hn, an, hs, as_, when, live, hc, ac, hl, al) in enumerate(rows, 1):
            for k, v in {"id": i, "hname": hn, "aname": an, "hs": hs, "as": as_, "when": when, "live": live, "hcol": hc, "acol": ac,
                         "hlogo": f"{ART}c{hl}.png", "alogo": f"{ART}c{al}.png", "league": "Eredivisie" if n < 3 else "LaLiga",
                         "kick": ("LIVE · EREDIVISIE · 67'" if live else f"{when} · {'EREDIVISIE' if n < 3 else 'LALIGA'}"),
                         "big": f"{hs} – {as_}" if hs else when}.items():
                HOME.setProperty(f"lucent.ps.{n}.{k}", v)
    xbmc.executebuiltin("ReloadSkin()")
    mon.waitForAbort(6)
    xbmc.executebuiltin("Dialog.Close(all,true)")
    xbmc.executebuiltin("ActivateWindow(home)")
    mon.waitForAbort(3)
    # Home
    xbmc.executebuiltin("Control.SetFocus(9000,1)")
    mon.waitForAbort(2)
    xbmc.executebuiltin("SetFocus(9100)")
    mon.waitForAbort(14)
    log(f"readme: home rows {lab('Container(8101).NumItems')} {lab('Container(8201).NumItems')} focus={lab('System.CurrentControlId')}")
    shot("r-home")
    xbmc.executebuiltin("Control.SetFocus(9000,2)")
    mon.waitForAbort(8)
    shot("r-sidebar")
    # the tab screens
    for idx, name, cid in ((4, "calendar", 9310), (6, "sport", 9330), (8, "settings", 9350), (9, "power", 9360), (7, "addons", 9340)):
        tabpanels.update()
        set_sport()
        xbmc.executebuiltin(f"Control.SetFocus(9000,{idx})")
        mon.waitForAbort(3)
        set_sport()
        xbmc.executebuiltin(f"SetFocus({cid})")
        mon.waitForAbort(3)
        log(f"readme: {name} focus={lab('System.CurrentControlId')} items={lab(f'Container({cid}).NumItems')}")
        shot(f"r-tab-{name}")
    # views (without the '..' item, focus on the second title)
    xbmc.executeJSONRPC(json.dumps({"jsonrpc": "2.0", "id": 1, "method": "Settings.SetSettingValue",
                                    "params": {"setting": "filelists.showparentdiritems", "value": False}}))
    xbmc.executebuiltin("ActivateWindow(Videos,plugin://plugin.video.fakeseren/?list=sm,return)")
    mon.waitForAbort(6)
    for view, name in ((51, "posters"), (52, "poster-wall"), (50, "list"), (57, "showcase")):
        xbmc.executebuiltin(f"Container.SetViewMode({view})")
        mon.waitForAbort(2)
        xbmc.executebuiltin(f"SetFocus({view},1)")
        mon.waitForAbort(4)
        log(f"readme: view {name} visible={cond(f'Control.IsVisible({view})')} items={lab('Container.NumItems')}")
        shot(f"r-view-{name}")
    xbmc.executebuiltin("Container.Update(plugin://plugin.video.fakeseren/?list=se,replace)")
    mon.waitForAbort(6)
    xbmc.executebuiltin("Container.SetViewMode(55)")
    mon.waitForAbort(2)
    xbmc.executebuiltin("SetFocus(55,0)")
    mon.waitForAbort(4)
    log(f"readme: episodes visible={cond('Control.IsVisible(55)')}")
    shot("r-view-episodes")
    xbmc.executebuiltin("ActivateWindow(home)")
    mon.waitForAbort(3)
    # calendar window
    xbmc.executebuiltin("RunScript(special://skin/scripts/agenda.py)")
    mon.waitForAbort(8)
    shot("r-calendar")
    xbmc.executebuiltin("Action(Back)")
    mon.waitForAbort(3)
    # settings, skin settings, keyboard
    xbmc.executebuiltin("ActivateWindow(Settings)")
    mon.waitForAbort(4)
    shot("r-settings")
    xbmc.executebuiltin("ActivateWindow(SkinSettings)")
    mon.waitForAbort(5)
    shot("r-skin-settings")
    xbmc.executebuiltin("ActivateWindow(home)")
    mon.waitForAbort(3)
    xbmc.executebuiltin("Skin.SetString(ci.keyboard)")
    mon.waitForAbort(4)
    shot("r-keyboard")
    xbmc.executebuiltin("Dialog.Close(all,true)")
    mon.waitForAbort(2)


def filebrowser_test():
    """Issue #3: an add-on asks for pictures (thumbnails view 451) or zip files: the files must be visible."""
    import threading
    folder = "special://home/addons/plugin.video.fakeseren/art/"
    for name, args in (("images", (2, "Choose a picture", "files", ".jpg|.png", True, False, folder)),
                       ("zips", (1, "Choose a backup", "files", ".zip", True, False, "special://temp/zips/"))):
        if name == "zips":
            os.makedirs(xbmcvfs.translatePath("special://temp/zips/"), exist_ok=True)
            for i in range(6):
                open(xbmcvfs.translatePath(f"special://temp/zips/build{i}.zip"), "wb").write(b"PK\x05\x06" + b"\x00" * 18)
        t = threading.Thread(target=lambda: xbmcgui.Dialog().browse(*args), daemon=True)
        t.start()
        for _ in range(15):
            mon.waitForAbort(1)
            if cond("Window.IsActive(filebrowser)"):
                break
        mon.waitForAbort(3)
        log(f"fb: {name} active={cond('Window.IsActive(filebrowser)')} list450={cond('Control.IsVisible(450)')} n450={lab('Container(450).NumItems')} "
            f"thumbs451={cond('Control.IsVisible(451)')} n451={lab('Container(451).NumItems')} focus={lab('System.CurrentControlId')}")
        shot(f"r-fb-{name}")
        xbmc.executebuiltin("Dialog.Close(filebrowser,true)")
        mon.waitForAbort(2)


def pvr_test():
    """Live TV with IPTV Simple: TV tab, TV guide, a channel playing with its OSD."""
    def rpc(method, params=None):
        return json.loads(xbmc.executeJSONRPC(json.dumps({"jsonrpc": "2.0", "id": 1, "method": method, "params": params or {}}))).get("result") or {}
    for _ in range(90):
        if cond("Pvr.HasTVChannels"):
            break
        mon.waitForAbort(1)
    chans = (rpc("PVR.GetChannels", {"channelgroupid": "alltv"}) or {}).get("channels") or []
    log(f"pvr: has={cond('Pvr.HasTVChannels')} channels={[c.get('label') for c in chans]}")
    if not chans:
        return
    mon.waitForAbort(8)                     # the guide is read a bit later
    bc = rpc("PVR.GetBroadcasts", {"channelid": chans[0]["channelid"], "properties": ["title", "starttime", "endtime"]}).get("broadcasts") or []
    log(f"pvr: broadcasts ch1={len(bc)} first={[b.get('title') for b in bc[:3]]}")
    # TV tab on Home
    import sys as _sys
    _sys.path.insert(0, xbmcvfs.translatePath("special://skin/scripts"))
    import menu
    import tabpanels
    m = menu.Menu()
    if not any("tv.py" in t["action"] for t in m.tabs):
        m.tabs.append({"label": "TV", "icon": "icons/tv.png", "action": "RunScript(special://skin/scripts/tv.py)",
                       "widgets": [{"label": "TV channels", "path": "pvr://channels/tv/", "style": "land"}], "actionlabel": ""})
        m.save()
    tabpanels.update()
    xbmc.executebuiltin("ActivateWindow(home)")
    mon.waitForAbort(3)
    m = menu.Menu()
    idx = next(i for i, t in enumerate(m.tabs) if "tv.py" in t["action"])
    xbmc.executebuiltin(f"Control.SetFocus(9000,{idx})")
    mon.waitForAbort(4)
    xbmc.executebuiltin("SetFocus(9320)")
    mon.waitForAbort(4)
    log(f"pvr: tvtab rows9100={cond('Control.IsVisible(9100)')} w1={lab('Container(9000).ListItem.Property(w1.path)')!r} path={HOME.getProperty('lucent.ptv.path')!r} items={lab('Container(9320).NumItems')} focus={lab('System.CurrentControlId')} "
        f"now={lab('Container(9320).ListItem.EpgEventTitle')!r}")
    shot("p-tvtab")
    # TV guide
    xbmc.executebuiltin("ActivateWindow(TVGuide)")
    mon.waitForAbort(8)
    shot("p-guide")
    xbmc.executebuiltin("ActivateWindow(home)")
    mon.waitForAbort(2)
    # play a channel and open the OSD
    rpc("Player.Open", {"item": {"channelid": chans[2]["channelid"]}})
    for _ in range(20):
        mon.waitForAbort(1)
        if cond("Pvr.IsPlayingTv"):
            break
    mon.waitForAbort(4)
    log(f"pvr: playing={cond('Pvr.IsPlayingTv')} title={lab('VideoPlayer.Title')!r} channel={lab('VideoPlayer.ChannelName')!r}")
    xbmc.executebuiltin("ActivateWindow(videoosd)")
    mon.waitForAbort(4)
    for _ in range(10):
        mon.waitForAbort(1)
        if HOME.getProperty("live.g.1.title"):
            break
    mon.waitForAbort(1)
    log(f"pvr: osd={cond('Window.IsActive(videoosd)')} focus={lab('System.CurrentControlId')} guide={[HOME.getProperty(f'live.g.{n}.title') for n in range(1, 7)]} "
        f"now1={HOME.getProperty('live.g.1.now')!r} up={HOME.getProperty('live.g.up')!r} down={HOME.getProperty('live.g.down')!r} items={lab('Container(460).NumItems')}")
    shot("p-osd")
    xbmc.executebuiltin("Action(Right)")
    mon.waitForAbort(1.5)
    log(f"pvr: right focus={lab('System.CurrentControlId')} item={lab('Container(460).ListItem.Label')!r} n={lab('Container(460).ListItem.Property(n)')!r}")
    shot("p-osd-next")
    xbmc.executebuiltin("Action(Select)")                  # remind me for the next programme
    mon.waitForAbort(2)
    try:
        rem = json.load(open(xbmcvfs.translatePath("special://profile/addon_data/skin.lucent/live_reminders.json")))
    except Exception as error:  # noqa: BLE001
        rem = repr(error)
    log(f"pvr: reminders={rem}")
    xbmc.executebuiltin("Action(Down)")
    mon.waitForAbort(1.5)
    log(f"pvr: down focus={lab('System.CurrentControlId')}")
    shot("p-osd-buttons")
    xbmc.executebuiltin("SetFocus(477)")
    mon.waitForAbort(1)
    xbmc.executebuiltin("Action(Select)")
    mon.waitForAbort(1.5)
    log(f"pvr: more focus={lab('System.CurrentControlId')} settings={cond('Skin.HasSetting(lucent.livesettings)')}")
    shot("p-osd-more")
    xbmc.executebuiltin("SetFocus(401)")
    xbmc.executebuiltin("Action(Select)")
    mon.waitForAbort(1.5)
    log(f"pvr: back focus={lab('System.CurrentControlId')} settings={cond('Skin.HasSetting(lucent.livesettings)')}")
    # clean channel logos (tv-logos) in the list Lucent writes for IPTV Simple
    xbmc.executebuiltin("Dialog.Close(all,true)")
    xbmc.executebuiltin("PlayerControl(Stop)")
    mon.waitForAbort(3)
    import channels
    import xtream
    cfg = channels.load()
    path = channels.pick_instance(cfg)
    ok = bool(path) and channels.remember_original(cfg, path)
    cfg["logos"] = True
    res = channels.build_file(cfg) if ok else None
    if res:
        channels.point_to_file(cfg)
        channels.save(cfg)

        class Busy:
            def update(self, *a):
                pass

            def iscanceled(self):
                return False
        state = xtream.restart_addon(Busy())
    else:
        state = "-"
    mon.waitForAbort(5)
    chans = (rpc("PVR.GetChannels", {"channelgroupid": "alltv", "properties": ["icon", "thumbnail"]}) or {}).get("channels") or []
    log(f"pvr: logos instance={bool(path)} built={res} restart={state} icons={[(c.get('label'), (c.get('icon') or c.get('thumbnail') or '')[-30:]) for c in chans]}")
    xbmc.executebuiltin("ActivateWindow(TVGuide)")
    mon.waitForAbort(8)
    shot("p-guide-logos")
    xbmc.executebuiltin("ActivateWindow(home)")
    mon.waitForAbort(2)
    xbmc.executebuiltin("Dialog.Close(all,true)")
    xbmc.executebuiltin("PlayerControl(Stop)")
    mon.waitForAbort(3)


def chanrows_test():
    """Game page channel rows: the first row readable when not focused, names without the provider's marks."""
    import sys as _sys
    _sys.path.insert(0, xbmcvfs.translatePath("special://skin/scripts"))
    import sport_core as sc
    names = ["┃NL┃ ZIGGO SPORT 2 ┃", "|NL| ZIGGO SPORT", "┃PT┃ SPORT TV 1", "[RO] DIGI SPORT 1", "NL: Ziggo Sport 2 FHD"]
    log(f"chan: clean={[(sc.display_channel(n), sc.channel_country(n)) for n in names]}")
    xbmc.executebuiltin("RunScript(special://skin/scripts/sport.py)")
    for _ in range(40):
        mon.waitForAbort(1)
        if [e for e in sc.all_cached() if e["kind"] == "teams"]:
            break
    xbmc.executebuiltin("Dialog.Close(all,true)")
    xbmc.executebuiltin("Action(Back)")
    mon.waitForAbort(2)
    try:
        pass
    except Exception as error:  # noqa: BLE001
        import traceback
        log(f"chan: refresh {error!r} {traceback.format_exc()[-600:]}")
    games = [e for e in sc.all_cached() if e["kind"] == "teams" and sc.LEAGUES.get(e["league"], {}).get("sport") == "soccer"]
    games.sort(key=lambda e: ({"in": 0, "post": 1, "pre": 2}[e["state"]], -e["start"] if e["state"] == "post" else e["start"]))
    if not games:
        # no games in the test: the game page on its own, with made-up properties
        import xbmcaddon
        win = xbmcgui.WindowXMLDialog("Lucent_SportGame.xml", xbmcaddon.Addon("skin.lucent").getAddonInfo("path"), "Default", "1080i")
        for k, v in {"layout": "teams", "hname": "Ajax", "aname": "AZ", "bigmid": "2 – 1", "topline": "Eredivisie", "remindtext": "Remind me",
                     "rectext": "Record", "t.watchcap": "WATCH ON YOUR CHANNELS"}.items():
            win.setProperty(f"g.{k}", v)
        rows = [("ZIGGO SPORT 2", "NL  ·  Live now  ·  Broadcasting  ·  4K"), ("ZIGGO SPORT", "NL  ·  Live now  ·  Broadcasting"),
                ("SPORT TV 1", "PT  ·  Broadcasting  ·  4K"), ("DIGI SPORT 1", "RO  ·  Live now  ·  Broadcasting")]
        for n, (name, sub) in enumerate(rows, 1):
            win.setProperty(f"g.ch{n}name", name)
            win.setProperty(f"g.ch{n}sub", sub)
        win.show()
        mon.waitForAbort(3)
        xbmc.executebuiltin("SetFocus(1311)")
        mon.waitForAbort(1.5)
        shot("c-rows-1")
        xbmc.executebuiltin("SetFocus(1313)")
        mon.waitForAbort(1.5)
        log(f"chan: page focus={lab('System.CurrentControlId')} vis1311={cond('Control.IsVisible(1311)')}")
        shot("c-rows-3")
        steps = []
        xbmc.executebuiltin("SetFocus(1332)")
        mon.waitForAbort(1)
        steps.append(lab("System.CurrentControlId"))
        for key in ("Up", "Up", "Up", "Up", "Down", "Down", "Down", "Down"):
            xbmc.executebuiltin(f"Action({key})")
            mon.waitForAbort(0.8)
            steps.append(f"{key}:{lab('System.CurrentControlId')}")
        log(f"chan: nav {steps}")
        win.close()
        del win
        return
    xbmc.executebuiltin(f"RunScript(special://skin/scripts/sport.py,game,{games[0]['id']})")
    for _ in range(30):
        mon.waitForAbort(1)
        if lab("Window.Property(g.layout)") == "teams":
            break
    mon.waitForAbort(3)
    win = xbmcgui.Window(xbmcgui.getCurrentWindowId())
    rows = [("ZIGGO SPORT 2", "NL  ·  Live now  ·  Broadcasting  ·  4K"), ("ZIGGO SPORT", "NL  ·  Live now  ·  Broadcasting"),
            ("SPORT TV 1", "PT  ·  Broadcasting  ·  4K"), ("DIGI SPORT 1", "RO  ·  Live now  ·  Broadcasting")]
    for n, (name, sub) in enumerate(rows, 1):
        win.setProperty(f"g.ch{n}name", name)
        win.setProperty(f"g.ch{n}sub", sub)
    if not win.getProperty("g.remindtext"):
        win.setProperty("g.remindtext", "Remind me")
    mon.waitForAbort(1)
    xbmc.executebuiltin("SetFocus(1311)")
    mon.waitForAbort(1.5)
    shot("c-rows-1")
    xbmc.executebuiltin("SetFocus(1313)")
    mon.waitForAbort(1.5)
    log(f"chan: focus={lab('System.CurrentControlId')} vis1311={cond('Control.IsVisible(1311)')} name1={lab('Window.Property(g.ch1name)')!r}")
    shot("c-rows-3")
    steps = []
    xbmc.executebuiltin("SetFocus(1332)")
    mon.waitForAbort(1)
    steps.append(lab("System.CurrentControlId"))
    for key in ("Up", "Up", "Up", "Up", "Down", "Down", "Down", "Down"):
        xbmc.executebuiltin(f"Action({key})")
        mon.waitForAbort(0.8)
        steps.append(f"{key}:{lab('System.CurrentControlId')}")
    log(f"chan: nav {steps}")
    xbmc.executebuiltin("Dialog.Close(all,true)")
    mon.waitForAbort(1)
    xbmc.executebuiltin("ActivateWindow(home)")
    mon.waitForAbort(2)


def sportosd_test():
    """The sport layer of the TV player (P1-P5) with a game made up in the window properties."""
    def rpc(method, params=None):
        return json.loads(xbmc.executeJSONRPC(json.dumps({"jsonrpc": "2.0", "id": 1, "method": method, "params": params or {}}))).get("result") or {}
    for _ in range(90):
        if cond("Pvr.HasTVChannels"):
            break
        mon.waitForAbort(1)
    chans = (rpc("PVR.GetChannels", {"channelgroupid": "alltv"}) or {}).get("channels") or []
    if not chans:
        log("sosd: no channels")
        return
    rpc("Player.Open", {"item": {"channelid": chans[2]["channelid"]}})
    for _ in range(20):
        mon.waitForAbort(1)
        if cond("Pvr.IsPlayingTv"):
            break
    mon.waitForAbort(26)                      # the helper's first round for this channel has run
    art = "special://home/addons/plugin.video.fakeseren/art/"
    base = {"on": "1", "h": "AJA", "a": "AZ", "hs": "2", "as": "1", "clock": "67'", "hname": "Ajax", "aname": "AZ", "hlogo": art + "c0.png", "alogo": art + "c4.png",
            "hcol": "FFD2122E", "acol": "FF1C3C8C", "sport": "soccer", "league": "Eredivisie", "id": "x", "title": "Ajax – AZ", "race": ""}
    det = {"hgoals": "12' Brobbey  ·  58' Taylor", "agoals": "44' Pavlidis"}
    for n, (l, h, a, k) in enumerate((("Possession", "58%", "42%", 6), ("Shots", "14", "7", 7), ("On target", "6", "3", 7), ("Corners", "5", "2", 7),
                                      ("Fouls", "9", "12", 4), ("Yellow cards", "1", "2", 3)), 1):
        det.update({f"st{n}l": l, f"st{n}h": h, f"st{n}a": a, f"st{n}k": str(k)})
    for n, (m, t, x) in enumerate((("58'", "AJA", "Taylor"), ("44'", "AZ", "Pavlidis"), ("12'", "AJA", "Brobbey")), 1):
        det.update({f"sc{n}m": m, f"sc{n}t": t, f"sc{n}x": x})
    for n, (m, k, x) in enumerate((("58'", "goal", "Goal Taylor (Ajax)"), ("51'", "yellow", "Yellow card Mijnans (AZ)"), ("44'", "goal", "Goal Pavlidis (AZ)"),
                                   ("12'", "goal", "Goal Brobbey (Ajax)")), 1):
        det.update({f"tl{n}m": m, f"tl{n}k": k, f"tl{n}x": x})
    tab = {}
    for n, (r, t, gp, gd, pts, mine) in enumerate(((1, "PSV", 12, "+24", 31, ""), (2, "Ajax", 12, "+15", 27, "1"), (3, "AZ", 12, "+10", 24, "1"), (4, "Feyenoord", 12, "+9", 22, "")), 1):
        tab.update({f"{n}rank": str(r), f"{n}team": t, f"{n}gp": str(gp), f"{n}gd": gd, f"{n}pts": str(pts), f"{n}mine": mine})

    def put(prefix, d):
        for k, v in d.items():
            HOME.setProperty(prefix + k, v)
    put("live.sc.", base)
    put("live.d.", det)
    put("live.t.", tab)
    mon.waitForAbort(2)
    log(f"sosd: vis9700={cond('Control.IsVisible(9700)')} ")
    log(f"sosd: board win={lab('System.CurrentWindow')!r} full={cond('Window.IsActive(fullscreenvideo)')} cond={cond('Pvr.IsPlayingTV + !String.IsEmpty(Window(Home).Property(live.sc.on)) + String.IsEmpty(Window(Home).Property(live.sc.race))')} on={HOME.getProperty('live.sc.on')!r}")
    shot("s-board")
    xbmc.executebuiltin("ActivateWindow(videoosd)")
    mon.waitForAbort(3)
    put("live.sc.", base)
    log(f"sosd: osd focus={lab('System.CurrentControlId')} vis480={cond('Control.IsVisible(480)')} vis460={cond('Control.IsVisible(460)')}")
    xbmc.Player().showSubtitles(False)
    mon.waitForAbort(1)
    shot("s-osd-soccer")
    xbmc.executebuiltin("SetFocus(482)")
    mon.waitForAbort(0.5)
    xbmc.executebuiltin("Action(Select)")          # Statistics -> the panel
    mon.waitForAbort(4)
    log(f"sosd: panel dialog={lab('System.CurrentWindow')!r} focus={lab('System.CurrentControlId')} tab={HOME.getProperty('live.p.tab')!r}")
    shot("s-panel-stats")
    xbmc.executebuiltin("Action(Right)")
    mon.waitForAbort(1.5)
    shot("s-panel-timeline")
    xbmc.executebuiltin("Action(Right)")
    mon.waitForAbort(1.5)
    log(f"sosd: tab={HOME.getProperty('live.p.tab')!r} focus={lab('System.CurrentControlId')}")
    shot("s-panel-table")
    xbmc.executebuiltin("Action(Back)")
    mon.waitForAbort(2)
    # Also live
    xbmc.executebuiltin("RunScript(special://skin/scripts/sportlive.py,also)")
    mon.waitForAbort(3)
    for n, (lg, cl, hn, an, hs, as_, ch, hc, ac) in enumerate((("NBA", "Q4 7:49", "Magic", "Celtics", "83", "87", "ESPN 1", "0077C0", "007A33"),
                                                                ("Serie A", "58'", "Milan", "Inter", "3", "1", "Ziggo Sport 2", "FB090B", "010E80"),
                                                                ("Premier League", "72'", "Arsenal", "Chelsea", "1", "1", "ESPN 2", "EF0107", "034694")), 1):
        put(f"live.a.{n}.", {"hname": hn, "aname": an, "hs": hs, "as": as_, "league": lg, "clock": cl, "chan": ch, "cid": "1", "hcol": hc, "acol": ac,
                             "chicon": art + f"c{n}.png"})
    mon.waitForAbort(2)
    xbmc.executebuiltin("SetFocus(300)")
    mon.waitForAbort(1)
    log(f"sosd: also items={lab('Container(300).NumItems')} focus={lab('System.CurrentControlId')}")
    shot("s-also")
    xbmc.executebuiltin("Action(Back)")
    mon.waitForAbort(2)
    # basketball
    put("live.sc.", {"sport": "basketball", "h": "ORL", "a": "BOS", "hs": "83", "as": "87", "clock": "Q4 · 7:49", "title": "Magic – Celtics", "league": "NBA",
                     "hcol": "FF0077C0", "acol": "FF007A33"})
    put("live.d.", {"qn": "4", "qh1": "24", "qh2": "22", "qh3": "25", "qh4": "12", "qa1": "20", "qa2": "27", "qa3": "22", "qa4": "18",
                    "tp1n": "Banchero", "tp1v": "28 · 9 · 4", "tp2n": "Tatum", "tp2v": "31 · 8 · 5", "tp3n": "Wagner", "tp3v": "19 · 3 · 6"})
    xbmc.executebuiltin("ActivateWindow(videoosd)")
    mon.waitForAbort(3)
    log(f"sosd: basket focus={lab('System.CurrentControlId')}")
    shot("s-osd-basket")
    xbmc.executebuiltin("Dialog.Close(all,true)")
    xbmc.executebuiltin("PlayerControl(Stop)")
    mon.waitForAbort(2)


def serentheme_test():
    """README screenshots of the Lucent theme for Seren: the real theme XML in this Kodi, filled the way Seren fills it."""
    PATH = "/tmp/ci/serentheme"
    ART = "special://home/addons/plugin.video.fakeseren/art/"
    ep = {"item.info.tvshowtitle": "Northbound", "item.info.title": "The Long Crossing", "item.info.season": "2", "item.info.episode": "7",
          "item.info.year": "2025", "item.info.rating": "8.4", "item.info.mpaa": "TV-14", "item.info.aired": "12 March 2025",
          "item.info.duration.hours": "0", "item.info.duration.minutes": "52", "item.info.rottentomatoes_rating": "94%", "item.info.metacritic_rating": "81",
          "item.info.plot": "A storm closes the northern pass, and the crew must choose between waiting it out and a dangerous shortcut over the ice. "
                            "Placeholder text for this screenshot: in Kodi you see the real plot from TMDB.",
          "item.art.fanart": ART + "f3.jpg", "item.art.thumb": ART + "f5.jpg", "seren.fanart": ART + "f3.jpg"}

    class W(xbmcgui.WindowXMLDialog):
        def __init__(self, *a, **k):
            super().__init__(*a)
            self.fill = k.get("fill")
            self.focus = k.get("focus")

        def onInit(self):
            if self.fill:
                self.fill(self)
            if self.focus:
                self.setFocusId(self.focus)

    def show(xml, name, props, fill=None, focus=None, wait=4):
        w = W(xml, PATH, "Default", "1080i", fill=fill, focus=focus)
        for k, v in props.items():
            w.setProperty(k, v)
        w.show()
        mon.waitForAbort(wait)
        log(f"theme {name}: dialog={lab('System.CurrentWindow')} focus={lab('System.CurrentControlId')}")
        shot(f"theme-{name}")
        w.close()
        mon.waitForAbort(1)
        del w

    # 1 source select (episode, the first stream = Recommended)
    streams = [
        ("4K", "Northbound.S02E07.2160p.WEB-DL.DV.HDR.DDP5.1.Atmos.H265", "TORRENTIO", "REAL-DEBRID", "TORRENT", "18.4 GB", "CACHED", "DUAL-AUDIO", ("DV", "HDR", "HEVC", "WEB", "ATMOS", "DD+", "5.1")),
        ("4K", "Northbound.S02E07.2160p.UHD.BluRay.REMUX.HDR.TrueHD.7.1", "COMET", "REAL-DEBRID", "TORRENT", "41.2 GB", "CACHED", "", ("", "HDR", "HEVC", "REMUX", "TRUEHD", "", "7.1")),
        ("1080p", "Northbound.S02E07.1080p.WEB-DL.DDP5.1.H264", "MEDIAFUSION", "PREMIUMIZE", "CLOUD", "3.1 GB", "", "MULTI-SUB", ("", "", "AVC", "WEB", "DD+", "", "5.1")),
        ("1080p", "Northbound.S02E07.1080p.BluRay.x264.DTS", "TORRENTIO", "REAL-DEBRID", "TORRENT", "6.8 GB", "CACHED", "", ("", "", "AVC", "BLURAY", "DTS", "", "5.1")),
        ("720p", "Northbound.S02E07.720p.HDTV.x264.AAC", "TORRENTIO", "REAL-DEBRID", "TORRENT", "1.2 GB", "", "", ("", "", "AVC", "HDTV", "AAC", "", "2.0")),
        ("SD", "Northbound.S02E07.HDTV.x264", "TORRENTIO", "REAL-DEBRID", "TORRENT", "380 MB", "", "", ("", "", "AVC", "HDTV", "AAC", "", "2.0"))]

    def fill_sources(w):
        lst = w.getControl(1000)
        for q, title, prov, deb, typ, size, cached, lang, (hdr1, hdr2, vc, misc, ac1, ac2, ch) in streams:
            li = xbmcgui.ListItem(label=title)
            d = {"quality": q, "release_title": title, "provider": prov, "debrid_provider": deb, "type": typ, "size": size,
                 "info.sourcetype_text": cached, "aio_lang": lang, "info.hdrcodec_1": hdr1 or hdr2, "info.hdrcodec_2": hdr2 if hdr1 else "",
                 "info.videocodec_1": vc, "info.misc_1": misc, "info.audiocodec_1": ac1, "info.audiocodec_2": ac2, "info.audiochannels_1": ch}
            for k, v in d.items():
                if v:
                    li.setProperty(k, v)
            lst.addItem(li)
        w.setFocusId(1000)
    show("source_select.xml", "source-select", dict(ep, instant_close="false", resolving="false", **{"filter.label": "Filter results"}), fill_sources)

    # 2 scraping
    def fill_scrape(w):
        lst = w.getControl(2000)
        for p in ("Comet", "MediaFusion", "Jackettio"):
            lst.addItem(xbmcgui.ListItem(label=p))
    show("get_sources.xml", "scraping", dict(ep, process_started="true", progress="62", remaining_providers_count="3", notification_text="",
                                              totals_4K="7", totals_1080p="23", totals_720p="11", totals_SD="4", totals_total="45",
                                              torrents_total="38", torrentsCached_total="21", hosters_total="0", cloudFiles_total="2",
                                              directSources_total="0", adaptiveSources_total="0", has_torrent_providers="true",
                                              has_cloud_scrapers="true", has_hoster_providers="false", has_direct_providers="false",
                                              has_adaptive_providers="false"), fill_scrape, wait=5)

    # 3 filters
    groups = {1000: ["AV1", "AVC", "DIVX", "HEVC", "MP4", "MPEG", "VP9", "WMV", "XVID"], 2000: ["DV", "HDR", "HYBRID"],
              3000: ["AAC", "ATMOS", "DD", "DD+", "DTS", "DTS-HD", "DTS-HDHR", "DTS-HDMA", "DTS-X", "MP3", "OPUS", "TRUEHD", "WMA"],
              4000: ["2.0", "5.1", "7.1"], 5000: ["3D", "BLURAY", "CAM", "DVDRIP", "HC", "HD-RIP", "HDTV", "PDTV", "REMUX", "SCR", "WEB"]}
    on = {"XVID", "DIVX", "WMV", "CAM", "SCR", "HC", "3D", "MP3"}

    def fill_filters(w):
        for cid, names in groups.items():
            lst = w.getControl(cid)
            for n in names:
                li = xbmcgui.ListItem(label=n)
                li.setProperty("label", n)
                li.setProperty("value", str(n in on))
                lst.addItem(li)
        w.setFocusId(5000)
    show("filter_select.xml", "filters", {"seren.fanart": ART + "f1.jpg"}, fill_filters)

    # 4 sorting
    sp = {"seren.fanart": ART + "f2.jpg", "max_level": "5"}
    rows = [("Resolution",), ("Source Type", "Cloud", "Torrents", "Hosters"), ("Debrid Provider", "Real-Debrid", "Premiumize"),
            ("DV/HDR", "DV", "HDR"), ("Size",), ("None",)]
    for lvl, row in enumerate(rows, 1):
        for i, t in enumerate(row):
            sp[f"general.sortmethod.{lvl}.label.{i}"] = t
        sp[f"general.sortmethod.{lvl}.label.{len(row) - 1}.last"] = "True"
        sp[f"general.sortmethod.{lvl}.reverse"] = "True" if lvl == 5 else "False"
    show("sort_select.xml", "sorting", sp, focus=2002)

    # 5 provider packages
    def fill_packs(w):
        lst = w.getControl(1000)
        for n, (name, ver, author, services) in enumerate([("aiostreams", "1.1.0", "djdirty60", "torrent · cloud"),
                                                           ("torrentio", "2.4.1", "community", "torrent"),
                                                           ("mediafusion", "1.3.0", "community", "torrent · hosters")]):
            li = xbmcgui.ListItem(label=name)
            for k, v in {"pack_name": name, "version": ver, "author": author, "services": services, "package.icon": f"{ART}c{n}.png"}.items():
                li.setProperty(k, v)
            lst.addItem(li)
        w.setFocusId(1000)
    show("provider_packages.xml", "provider-packages", {"seren.fanart": ART + "f4.jpg"}, fill_packs)

    # 6 provider settings
    def fill_pack(w):
        st = w.getControl(1000)
        for label, typ, value, action in [("Manifest URL", "string", "*******", False), ("Timeout (seconds)", "int", "20", False),
                                          ("Only cached results", "bool", "True", False), ("Show IMAX / FEL tags", "bool", "True", False),
                                          ("Include adult", "bool", "False", False), ("Test connection", "action", "", True)]:
            li = xbmcgui.ListItem(label=label)
            for k, v in {"label": label, "type": typ, "value": value, "has_action": str(action), "hide_value": "False"}.items():
                li.setProperty(k, v)
            st.addItem(li)
        pr = w.getControl(2000)
        for n, (name, typ, status) in enumerate([("Torrentio", "torrent", "enabled"), ("Comet", "torrent", "enabled"), ("MediaFusion", "torrent", "enabled"),
                                                 ("Jackettio", "torrent", "disabled"), ("Easynews", "hosters", "enabled"), ("Debrid cloud", "hosters", "disabled")]):
            li = xbmcgui.ListItem(label=name)
            for k, v in {"provider_name": name, "provider_type": typ, "status": status, "package": "aiostreams", "provider.icon": f"{ART}c{n % 6}.png"}.items():
                li.setProperty(k, v)
            pr.addItem(li)
        w.setFocusId(2000)
    show("configure_provider_package.xml", "provider-settings", {"seren.fanart": ART + "f4.jpg", "package.name": "aiostreams", "hassettings": "true"}, fill_pack)

    # 7 + 8 over a playing video: Playing next, Skip intro
    xbmc.executebuiltin("Skin.Reset(nuvio.autosubs)")      # no subtitle list popping up
    xbmc.Player().play("/tmp/ci/test.mkv")
    for _ in range(20):
        if cond("Player.HasVideo"):
            break
        mon.waitForAbort(1)
    mon.waitForAbort(6)
    for _ in range(6):
        if not cond("System.HasVisibleModalDialog"):
            break
        xbmc.executebuiltin("Dialog.Close(all,true)")
        xbmc.executebuiltin("Action(Back)")
        mon.waitForAbort(1.5)
    log(f"theme video: dialog={cond('System.HasVisibleModalDialog')} window={lab('System.CurrentWindow')}")
    nxt = dict(ep, **{"item.info.title": "Thin Ice", "item.info.episode": "8", "item.info.duration.minutes": "49", "item.art.thumb": ART + "f7.jpg",
                      "item.info.plot": "With the pass behind them, the crew reaches the old weather station and finds it is not as empty as it looked."})
    show("playing_next.xml", "playing-next", nxt, focus=3001, wait=5)
    show("skip_intro.xml", "skip-intro", {}, focus=3001, wait=3)
    xbmc.Player().stop()
    mon.waitForAbort(2)


def pinfo_test():
    """Speler-info (example 3) over a playing video."""
    xbmc.executebuiltin("Skin.Reset(nuvio.autosubs)")
    rpcs = json.loads(xbmc.executeJSONRPC(json.dumps({"jsonrpc": "2.0", "id": 1, "method": "Settings.GetSettingValue", "params": {"setting": "videolibrary.flattentvshows"}})))
    log(f"pinfo: flattentvshows={rpcs.get('result')} mark={lab('Skin.String(lucent.flattenset)')}")
    xbmc.Player().play("/tmp/ci/audio.mkv")
    for _ in range(20):
        if cond("Player.HasVideo"):
            break
        mon.waitForAbort(1)
    mon.waitForAbort(5)
    for _ in range(6):
        if not cond("System.HasVisibleModalDialog"):
            break
        xbmc.executebuiltin("Dialog.Close(all,true)")
        mon.waitForAbort(1.5)
    xbmc.executebuiltin("Skin.SetBool(nuvio.osdstats)")
    xbmc.executebuiltin("ActivateWindow(videoosd)")
    mon.waitForAbort(6)
    keys = ["title", "time", "b.res", "b.vc", "b.ac", "b.ch", "b.sub", "t1.big", "t1.sub", "t3.big", "t4.big", "t4.sub", "spark", "t5.big", "t5.bar",
            "t6.big", "t6.sub", "r.file", "r.loc", "r.cont", "r.rate", "r.res", "r.hdr", "r.fmt", "r.vdec", "r.disp", "r.vq", "r.atrack",
            "r.afmt", "r.aq", "r.adec", "r.sub", "r.buf", "r.type", "cores", "cores.label", "core0", "m.ct", "m.mem", "m.clk", "m.fps", "m.vq"]
    log("pinfo: " + json.dumps({k: HOME.getProperty("lucent.pi." + k) for k in keys}, ensure_ascii=False))
    shot("pinfo-1")
    mon.waitForAbort(3)
    shot("pinfo-2")
    xbmc.executebuiltin("Dialog.Close(videoosd,true)")
    xbmc.executebuiltin("Skin.Reset(nuvio.osdstats)")
    xbmc.Player().stop()
    mon.waitForAbort(3)


def svc_test():
    """Streaming service pop-up (example A)."""
    xbmc.executebuiltin("RunScript(special://skin/scripts/service.py,8,Netflix,)")
    mon.waitForAbort(8)
    log(f"svc: window={lab('System.CurrentWindow')} focus={lab('System.CurrentControlId')} items={lab('Container(801).NumItems')} "
        f"label={lab('Container(801).ListItem.Label')!r} row={lab('Window.Property(svc.rowlabel)')!r}")
    shot("svc-1")
    xbmc.executebuiltin("Action(Right)")
    mon.waitForAbort(1)
    xbmc.executebuiltin("Action(Right)")
    mon.waitForAbort(2)
    shot("svc-2")
    steps = []
    xbmc.executebuiltin("Action(Up)")
    mon.waitForAbort(1.2)
    shot("svc-btn")
    xbmc.executebuiltin("Action(Down)")
    mon.waitForAbort(1)
    for key in ("Up", "Up", "Right", "Right", "Right", "Select", "Left", "Left", "Right"):
        xbmc.executebuiltin(f"Action({key})")
        mon.waitForAbort(1.2)
        steps.append(f"{key}:{lab('System.CurrentControlId')}")
    mon.waitForAbort(5)
    steps.append(f"cat={lab('Window.Property(svc.cat)')} kind={lab('Window.Property(svc.kind)')} row={lab('Window.Property(svc.rowlabel)')} items={lab('Container(801).NumItems')}")
    log(f"svc: nav {steps}")
    shot("svc-3")
    xbmc.executebuiltin("SetFocus(713)")
    mon.waitForAbort(1)
    xbmc.executebuiltin("Action(Select)")
    mon.waitForAbort(5)
    log(f"svc: top cat={lab('Window.Property(svc.cat)')} items={lab('Container(801).NumItems')}")
    xbmc.executebuiltin("SetFocus(801)")
    mon.waitForAbort(1.5)
    shot("svc-top")
    for key in ("Down", "Down"):
        xbmc.executebuiltin(f"Action({key})")
        mon.waitForAbort(1)
    log(f"svc: back down focus={lab('System.CurrentControlId')}")
    xbmc.executebuiltin("Action(Back)")
    mon.waitForAbort(2)


def sportnav_test():
    """All games: from the list to the scrollbar, the channels and back; stadium photos for awkward names."""
    import sys as _sys
    _sys.path.insert(0, xbmcvfs.translatePath("special://skin/scripts"))
    import sport_core as sc
    for name, sport, venue, short in [("Bodø/Glimt", "soccer", "Aspmyra Stadion", "Bodø/Glimt"), ("Shakhtar Donetsk", "soccer", "Arena Lviv", "Shakhtar"),
                                      ("Galatasaray", "soccer", "", ""), ("Atlético Madrid", "soccer", "", "Atlético"), ("FC Twente", "soccer", "", "Twente"),
                                      ("Union St.-Gilloise", "soccer", "Stade Joseph Marien", "Union SG")]:
        try:
            img, st = sc.stadium_photo(name, sport, venue, short)
        except Exception as error:  # noqa: BLE001
            img, st = repr(error), ""
        log(f"stadium: {name!r} -> {st!r} {img[:90]!r}")
        mon.waitForAbort(4)
    xbmc.executebuiltin("RunScript(special://skin/scripts/sport.py)")
    for _ in range(40):
        mon.waitForAbort(1)
        if lab("Window.Property(sport.loading)") == "" and int(lab("Container(200).NumItems") or 0) > 0:
            break
    mon.waitForAbort(3)
    win = xbmcgui.Window(xbmcgui.getCurrentWindowDialogId() if cond("System.HasVisibleModalDialog") else xbmcgui.getCurrentWindowId())
    try:
        item = win.getControl(200).getSelectedItem()
        if item is not None and not item.getProperty("ch1name"):
            for n, (name, sub) in enumerate([("ZIGGO SPORT", "NL · Live"), ("ESPN 1", "NL"), ("VIAPLAY 1", "NL")], 1):
                item.setProperty(f"ch{n}name", name)
                item.setProperty(f"ch{n}sub", sub)
        log(f"sportnav: faked channels on {item.getLabel() if item else None!r}")
    except Exception as error:  # noqa: BLE001
        log(f"sportnav: cannot fake channels {error!r}")
    xbmc.executebuiltin("SetFocus(200)")
    mon.waitForAbort(1.5)
    steps = [lab("System.CurrentControlId")]
    for key in ("Right", "Right", "Down", "Down", "Down", "Up", "Up", "Up", "Left", "Left"):
        xbmc.executebuiltin(f"Action({key})")
        mon.waitForAbort(0.8)
        steps.append(f"{key}:{lab('System.CurrentControlId')}")
        if key == "Down" and len(steps) == 4:
            shot("sportnav-ch")
    log(f"sportnav: nav {steps} ch1={lab('Container(200).ListItem.Property(ch1name)')!r}")
    shot("sportnav-end")
    xbmc.executebuiltin("Dialog.Close(all,true)")
    xbmc.executebuiltin("ActivateWindow(home)")
    mon.waitForAbort(2)


def libfix_test():
    """Library: series hidden until their first episode aired; TMDb pictures helper."""
    import sys as _sys
    _sys.path.insert(0, xbmcvfs.translatePath("special://home/addons/script.lucent.library"))
    import tmdbwidgets as tw
    xbmc.executebuiltin("Skin.SetBool(lucent.hide.undigital)")
    mon.waitForAbort(1)
    rows = [{"type": "tvshow", "file": "plugin://plugin.video.seren/?action=showSeasons", "premiered": "2026-12-25", "label": "future"},
            {"type": "tvshow", "file": "plugin://plugin.video.seren/?action=showSeasons", "premiered": "2020-01-01", "label": "aired"},
            {"type": "tvshow", "file": "videodb://tvshows/titles/5/", "premiered": "2030-01-01", "label": "library"},
            {"type": "tvshow", "file": "plugin://plugin.video.seren/?x", "premiered": "", "label": "nodate"}]
    kept = [r["label"] for r in tw.filter_undigital(rows)]
    log(f"libfix: kept={kept}")
    xbmc.executebuiltin("Skin.Reset(lucent.hide.undigital)")
    try:
        import tmdbart
        res = tmdbart.show(1001)
        log(f"libfix: tmdbart keys={sorted(res)} art={sorted((res.get('art') or {}))}")
        sh = {"tmdb_id": 1002, "art": {}, "cast": [], "season_art": {}}
        log(f"libfix: fill_show={tmdbart.fill_show(sh)} poster={(sh.get('art') or {}).get('poster','')[:60]!r}")
        import lib
        log(f"libfix: refresh_artless tv={lib.refresh_artless('tv')} movies={lib.refresh_artless('movies')}")
    except Exception as error:  # noqa: BLE001
        import traceback
        log(f"libfix: error {error!r} {traceback.format_exc()[-500:]}")


def stats_test():
    xbmc.Player().play("/tmp/ci/test.mkv")
    for _ in range(20):
        if cond("Player.HasVideo"):
            break
        mon.waitForAbort(1)
    mon.waitForAbort(4)
    xbmc.executebuiltin("Skin.SetBool(nuvio.osdstats)")
    mon.waitForAbort(1)
    before = cond("Skin.HasSetting(nuvio.osdstats)")
    xbmc.executebuiltin("ActivateWindow(home)")
    mon.waitForAbort(3)
    log(f"stats: before={before} after_leaving={cond('Skin.HasSetting(nuvio.osdstats)')} window={lab('System.CurrentWindow')}")
    xbmc.Player().stop()
    mon.waitForAbort(2)

def pinfo2_test():
    """Speler-info as its own window with three tabs."""
    xbmc.executebuiltin("Skin.Reset(nuvio.autosubs)")
    xbmc.Player().play("/tmp/ci/audio.mkv")
    for _ in range(20):
        if cond("Player.HasVideo"):
            break
        mon.waitForAbort(1)
    mon.waitForAbort(5)
    for _ in range(6):
        if not cond("System.HasVisibleModalDialog"):
            break
        xbmc.executebuiltin("Dialog.Close(all,true)")
        mon.waitForAbort(1.5)
    xbmc.executebuiltin("ActivateWindow(videoosd)")
    mon.waitForAbort(2)
    xbmc.executebuiltin("RunScript(special://skin/scripts/playerinfo.py,open)")
    mon.waitForAbort(6)
    log(f"pinfo2: open={HOME.getProperty('lucent.pi.open')} tab={HOME.getProperty('lucent.pi.tab')} focus={lab('System.CurrentControlId')} "
        f"dialog={lab('System.CurrentWindow')} osd={cond('Window.IsVisible(videoosd)')}")
    shot("pi2-1")
    keys = ["a.c1", "a.c2", "a.c3", "a.c4", "a.c5", "a.h1", "a.hs", "a.dev", "a.cfg", "a.vol", "a.chlabel", "a.t1.lang", "a.t1.codec", "a.t1.on",
            "a.t2.lang", "sp.c", "sp.l", "v.resbox", "v.reslabel", "v.dar", "v.hdrbar", "v.c1", "v.p1", "v.p2", "v.p3", "v.p4", "v.p4s", "v.br"]
    log("pinfo2: " + json.dumps({k: HOME.getProperty("lucent.pi." + k) for k in keys}, ensure_ascii=False))
    xbmc.executebuiltin("Action(Right)")
    mon.waitForAbort(2.5)
    log(f"pinfo2: after right tab={HOME.getProperty('lucent.pi.tab')} focus={lab('System.CurrentControlId')} time={lab('Player.Time')}")
    shot("pi2-2")
    try:
        xbmc.Player().setAudioStream(2)                 # the 5.1 track: more meters on the audio tab
    except Exception as error:  # noqa: BLE001
        log(f"pinfo2: audio stream {error}")
    mon.waitForAbort(2)
    xbmc.executebuiltin("Action(Right)")
    mon.waitForAbort(2.5)
    log(f"pinfo2: after right tab={HOME.getProperty('lucent.pi.tab')} focus={lab('System.CurrentControlId')}")
    shot("pi2-3")
    mon.waitForAbort(1.2)
    shot("pi2-3b")
    xbmc.executebuiltin("Action(Back)")
    mon.waitForAbort(2)
    log(f"pinfo2: after back open={HOME.getProperty('lucent.pi.open')!r} dialog={cond('System.HasVisibleModalDialog')} playing={cond('Player.HasVideo')}")
    xbmc.Player().stop()
    mon.waitForAbort(2)

def settiles_test():
    """Settings tab: four columns with 'Wat is er nieuw' and 'Op updates zoeken'."""
    import sys as _sys
    _sys.path.insert(0, xbmcvfs.translatePath("special://skin/scripts"))
    import menu
    import tabpanels
    m = menu.Menu()
    action = "ActivateWindow(Settings)"
    if not any(t["action"] == action for t in m.tabs) and len(m.tabs) < menu.NTABS:
        m.tabs.append({"label": "Settings", "icon": "icons/tv.png", "action": action, "widgets": [], "actionlabel": ""})
    m.save()
    tabpanels.update()
    xbmc.executebuiltin("ActivateWindow(home)")
    mon.waitForAbort(3)
    count = int(lab("Container(9000).NumItems") or 0)
    idx = None
    for i in range(count):
        xbmc.executebuiltin(f"Control.SetFocus(9000,{i})")
        mon.waitForAbort(0.4)
        if "ActivateWindow(Settings)" in lab("Container(9000).ListItem.Property(act)"):
            idx = i
            break
    log(f"settiles: tab index={idx}")
    if idx is None:
        return
    mon.waitForAbort(2)
    n = int(lab("Container(9350).NumItems") or 0)
    labels = [lab(f"Container(9350).ListItemAbsolute({i}).Label") for i in range(n)]
    log(f"settiles: items={n} labels={labels} visible={cond('Control.IsVisible(9350)')}")
    shot("settiles-1")
    xbmc.executebuiltin("Action(Right)")
    mon.waitForAbort(1.5)
    moves = []
    for key in ("Right", "Right", "Right", "Down", "Left"):
        xbmc.executebuiltin(f"Action({key})")
        mon.waitForAbort(1)
        moves.append(f"{key}:{lab('Container(9350).CurrentItem')}:{lab('Container(9350).ListItem.Label')}")
    log(f"settiles: moves {moves}")
    shot("settiles-2")
    xbmc.executebuiltin("Action(Left)")
    xbmc.executebuiltin("Action(Left)")
    xbmc.executebuiltin("Action(Left)")
    mon.waitForAbort(1)
    xbmc.executebuiltin("Control.SetFocus(9000,0)")
    mon.waitForAbort(2)


def svcreset_test():
    """Switching a list in the streaming pop-up starts it at the first title again."""
    xbmc.executebuiltin("RunScript(special://skin/scripts/service.py,8,Netflix,)")
    mon.waitForAbort(8)
    xbmc.executebuiltin("SetFocus(801)")
    mon.waitForAbort(1)
    for _ in range(4):
        xbmc.executebuiltin("Action(Right)")
        mon.waitForAbort(0.8)
    log(f"svcreset: before cat={lab('Window.Property(svc.cat)')} item={lab('Container(801).CurrentItem')} items={lab('Container(801).NumItems')}")
    for pill in ("702", "713", "701"):
        xbmc.executebuiltin(f"SetFocus({pill})")
        mon.waitForAbort(1)
        xbmc.executebuiltin("Action(Select)")
        mon.waitForAbort(5)
        log(f"svcreset: pill {pill} cat={lab('Window.Property(svc.cat)')} item={lab('Container(801).CurrentItem')} items={lab('Container(801).NumItems')}")
        xbmc.executebuiltin("SetFocus(801)")
        mon.waitForAbort(1)
        for _ in range(3):
            xbmc.executebuiltin("Action(Right)")
            mon.waitForAbort(0.8)
        log(f"svcreset: scrolled item={lab('Container(801).CurrentItem')}")
    shot("svcreset")
    xbmc.executebuiltin("Action(Back)")
    mon.waitForAbort(2)


def liblists_test():
    """Skin settings > Integrations > Lucent Library: the new 'Use my lists as library' row."""
    xbmc.executebuiltin("Skin.SetBool(lucent.ss.open.2505)")
    xbmc.executebuiltin("ActivateWindow(SkinSettings)")
    mon.waitForAbort(2)
    n = int(lab("Container(9000).NumItems") or 0)
    labels = [lab(f"Container(9000).ListItemAbsolute({i}).Label") for i in range(n)]
    log(f"liblists: cats {labels}")
    if "Integrations" not in labels:
        return
    xbmc.executebuiltin(f"SetFocus(9000,{labels.index('Integrations')},absolute)")
    mon.waitForAbort(1)
    xbmc.executebuiltin("Action(Right)")
    mon.waitForAbort(0.5)
    xbmc.executebuiltin("SetFocus(1523)")
    mon.waitForAbort(0.5)
    xbmc.executebuiltin("Action(Down)")
    mon.waitForAbort(0.8)
    log(f"liblists: down from surprise focus={lab('System.CurrentControlId')} vis={cond('Control.IsVisible(21524)')} sub={lab('$VAR[LucentLibLists]')!r}")
    shot("liblists-row")
    xbmc.executebuiltin("Skin.SetString(lucent.lib.lists,Movie collection · Serie collectie)")
    mon.waitForAbort(0.8)
    log(f"liblists: set sub={lab('$VAR[LucentLibLists]')!r}")
    xbmc.executebuiltin("Action(Down)")
    mon.waitForAbort(0.8)
    down = lab("System.CurrentControlId")
    xbmc.executebuiltin("Action(Up)")
    mon.waitForAbort(0.8)
    log(f"liblists: down={down} up again={lab('System.CurrentControlId')}")
    shot("liblists-set")
    xbmc.executebuiltin("Action(Select)")
    mon.waitForAbort(6)
    log(f"liblists: click dialog={lab('System.CurrentWindow')!r} ok={cond('Window.IsVisible(okdialog)')} text={lab('Control.GetLabel(9)')!r}")
    shot("liblists-click")
    xbmc.executebuiltin("Dialog.Close(all,true)")
    mon.waitForAbort(1)
    xbmc.executebuiltin("Skin.Reset(lucent.lib.lists)")
    xbmc.executebuiltin("ActivateWindow(home)")
    mon.waitForAbort(2)


def tvfav_test():
    """The TV tab row shows the favourite guide group."""
    import sys as _sys
    _sys.path.insert(0, xbmcvfs.translatePath("special://skin/scripts"))
    import tabpanels
    for _ in range(90):
        if cond("Pvr.HasTVChannels"):
            break
        mon.waitForAbort(1)
    mon.waitForAbort(3)
    reply = json.loads(xbmc.executeJSONRPC(json.dumps({"jsonrpc": "2.0", "id": 1, "method": "Files.GetDirectory",
                                                        "params": {"directory": "pvr://channels/tv/", "media": "files"}})))
    files = (reply.get("result") or {}).get("files") or []
    log(f"tvfav: groups {[(f.get('label'), f.get('file')) for f in files][:10]} raw={str(reply)[:300]}")
    def rpc(method, params):
        return json.loads(xbmc.executeJSONRPC(json.dumps({"jsonrpc": "2.0", "id": 1, "method": method, "params": params})))
    log(f"tvfav: GetChannelGroups {str(rpc('PVR.GetChannelGroups', {'channeltype': 'tv'}))[:400]}")
    for d in ("pvr://channels/tv/", "pvr://channels/tv/Favorieten/", "pvr://channels/tv/*/"):
        r = rpc("Files.GetDirectory", {"directory": d, "media": "video"})
        log(f"tvfav: dir {d} -> {[(f.get('label'), f.get('file')) for f in (r.get('result') or {}).get('files') or []][:6]} err={r.get('error')}")
    xbmc.executebuiltin("ActivateWindow(TVGuide)")
    mon.waitForAbort(6)
    n = int(lab("Container(11).NumItems") or 0)
    log(f"tvfav: guide groups {[(lab(f'Container(11).ListItemAbsolute({i}).Label'), lab(f'Container(11).ListItemAbsolute({i}).FolderPath'), lab(f'Container(11).ListItemAbsolute({i}).FileNameAndPath')) for i in range(n)]}")
    xbmc.executebuiltin("ActivateWindow(TVChannels)")
    mon.waitForAbort(4)
    log(f"tvfav: channels window path={lab('Container.FolderPath')!r} group={lab('Control.GetLabel(28)')!r}")
    xbmc.executebuiltin("ActivateWindow(home)")
    mon.waitForAbort(2)
    files = files or [{"label": "Favorieten", "file": "x"}]
    for want in ([f.get("label") for f in files if f.get("label")][-1:] or ["x"]) + ["Bestaat niet"]:
        xbmc.executebuiltin(f'Skin.SetString(lucent.guide.group,"{want}")')
        mon.waitForAbort(0.5)
        tabpanels.tv_path()
        log(f"tvfav: want={want!r} path={HOME.getProperty('lucent.ptv.path')!r} title={HOME.getProperty('lucent.ptv.title')!r}")
    xbmc.executebuiltin("Skin.Reset(lucent.guide.group)")
    tabpanels.tv_path()


def misc133_test():
    """Program add-ons in the menu editor's add-on list; What's new reads the news lines."""
    import sys as _sys
    _sys.path.insert(0, xbmcvfs.translatePath("special://skin/scripts"))
    import menu
    vids = [a[1] for a in menu.video_addons()]
    alls = [a[1] for a in menu.video_addons(menu.ALL_ADDONS)]
    log(f"misc: video={len(vids)} all={len(alls)} extra={[a for a in alls if a not in vids][:12]}")
    xbmc.executebuiltin("RunScript(special://skin/scripts/whatsnew.py)")
    mon.waitForAbort(4)
    log(f"misc: whatsnew dialog={lab('System.CurrentWindow')!r} text={lab('Control.GetLabel(5)')[:300]!r}")
    shot("whatsnew")
    xbmc.executebuiltin("Dialog.Close(all,true)")
    mon.waitForAbort(1)


def wn_test():
    """What's new, example A: versions left, headings right."""
    xbmc.executebuiltin("RunScript(special://skin/scripts/whatsnew.py)")
    mon.waitForAbort(4)
    log(f"wn: win={lab('System.CurrentWindow')!r} focus={lab('System.CurrentControlId')} versions={lab('Container(100).NumItems')} "
        f"title={lab('Window.Property(wn.title)')!r} sub={lab('Window.Property(wn.sub)')!r} items={lab('Container(200).NumItems')} first={lab('Container(200).ListItem.Label')!r}")
    shot("wn-1")
    for _ in range(2):
        xbmc.executebuiltin("Action(Down)")
        mon.waitForAbort(0.8)
    log(f"wn: down2 title={lab('Window.Property(wn.title)')!r} tag={lab('Window.Property(wn.tag)')!r} items={lab('Container(200).NumItems')}")
    shot("wn-2")
    xbmc.executebuiltin("Action(Right)")
    mon.waitForAbort(0.8)
    xbmc.executebuiltin("Action(Down)")
    mon.waitForAbort(0.8)
    log(f"wn: right focus={lab('System.CurrentControlId')} item={lab('Container(200).CurrentItem')}")
    shot("wn-3")
    xbmc.executebuiltin("Action(Left)")
    mon.waitForAbort(0.8)
    steps = [f"left:{lab('System.CurrentControlId')}:{lab('Container(100).CurrentItem')}"]
    for n in range(1, 21):
        xbmc.executebuiltin("Action(Down)")
        mon.waitForAbort(0.4)
        if n in (1, 5, 10, 13, 15, 20):
            steps.append(f"{n}:{lab('Container(100).CurrentItem')}")
    log(f"wn: steps {steps}")
    mon.waitForAbort(1)
    log(f"wn: far title={lab('Window.Property(wn.title)')!r} items={lab('Container(200).NumItems')} first={lab('Container(200).ListItem(0).Label')!r}")
    shot("wn-4")
    xbmc.executebuiltin("Action(Back)")
    mon.waitForAbort(1.5)
    log(f"wn: back win={lab('System.CurrentWindow')!r}")


def tvfav2_test():
    """TV tab on Home lists the guide's favourite group (its own folder, kept when chosen in the guide)."""
    import sys as _sys
    _sys.path.insert(0, xbmcvfs.translatePath("special://skin/scripts"))
    import menu
    import tabpanels
    import guidefav
    for _ in range(90):
        if cond("Pvr.HasTVChannels"):
            break
        mon.waitForAbort(1)
    mon.waitForAbort(3)
    xbmc.executebuiltin("ActivateWindow(TVGuide)")
    mon.waitForAbort(6)
    xbmc.executebuiltin('Skin.SetString(lucent.guide.group,"Favorieten")')
    guidefav.remember_path("Favorieten")
    mon.waitForAbort(1)
    log(f"tvfav2: saved={lab('Skin.String(lucent.guide.grouppath)')!r}")
    xbmc.executebuiltin("ActivateWindow(home)")
    mon.waitForAbort(2)
    m = menu.Menu()
    if not any("tv.py" in t["action"] for t in m.tabs):
        m.tabs.append({"label": "TV", "icon": "icons/tv.png", "action": "RunScript(special://skin/scripts/tv.py)",
                       "widgets": [{"label": "TV channels", "path": "pvr://channels/tv/", "style": "land"}], "actionlabel": ""})
        m.save()
    tabpanels.update()
    m = menu.Menu()
    idx = next(i for i, t in enumerate(m.tabs) if "tv.py" in t["action"])
    xbmc.executebuiltin(f"Control.SetFocus(9000,{idx})")
    mon.waitForAbort(5)
    log(f"tvfav2: path={HOME.getProperty('lucent.ptv.path')!r} title={HOME.getProperty('lucent.ptv.title')!r} items={lab('Container(9320).NumItems')} "
        f"first={lab('Container(9320).ListItemAbsolute(0).Label')!r}")
    shot("tvfav2")


def solis_test():
    """Solis Dashboard tab on Home (example C): numbers from the stand-in Homey."""
    xbmc.executebuiltin('Skin.SetString(lucent.logoask,"1")')
    xbmc.executebuiltin("Dialog.Close(all,true)")
    mon.waitForAbort(1)
    import sys as _sys
    _sys.path.insert(0, xbmcvfs.translatePath("special://skin/scripts"))
    import menu
    m = menu.Menu()
    if not any("script.solis.dashboard" in t["action"] for t in m.tabs):
        m.tabs.append({"label": "Solis Dashboard", "icon": "icons/sparkle.png", "action": "RunAddon(script.solis.dashboard)", "widgets": [], "actionlabel": ""})
        m.save()
    xbmc.executeJSONRPC(json.dumps({"jsonrpc": "2.0", "id": 1, "method": "Addons.SetAddonEnabled", "params": {"addonid": "script.solis.dashboard", "enabled": True}}))
    mon.waitForAbort(3)
    log(f"solis: addon={cond('System.HasAddon(script.solis.dashboard)')} enabled={cond('System.AddonIsEnabled(script.solis.dashboard)')}")
    xbmc.executebuiltin("ActivateWindow(home)")
    mon.waitForAbort(3)
    m = menu.Menu()
    idx = next(i for i, t in enumerate(m.tabs) if "script.solis.dashboard" in t["action"])
    xbmc.executebuiltin(f"Control.SetFocus(9000,{idx})")
    for _ in range(20):
        if HOME.getProperty("lucent.sol.1.t"):
            break
        mon.waitForAbort(1)
    mon.waitForAbort(3)
    keys = ["big", "p1", "p2", "p3", "advice", "img", "hint", "err", "pr.on", "pr.label", "pr.12.h", "pr.13.c", "pr.19.c"] + [f"{n}.{k}" for n in range(1, 7) for k in ("t", "v", "s")]
    log("solis: " + json.dumps({k: HOME.getProperty("lucent.sol." + k) for k in keys}, ensure_ascii=False))
    log(f"solis: panel={cond('Control.IsVisible(9370)')} rows9100={cond('Control.IsVisible(9100)')} items={lab('Container(9370).NumItems')}")
    shot("solis-1")
    xbmc.executebuiltin("Action(Right)")
    mon.waitForAbort(1.5)
    log(f"solis: right focus={lab('System.CurrentControlId')} label={lab('Container(9370).ListItem.Label')!r}")
    shot("solis-2")
    xbmc.executebuiltin("Action(Select)")
    mon.waitForAbort(5)
    log(f"solis: ok window={lab('System.CurrentWindow')!r}")
    shot("solis-3")
    xbmc.executebuiltin("Action(Back)")
    mon.waitForAbort(2)
    xbmc.executebuiltin("ActivateWindow(home)")
    mon.waitForAbort(1)


def settings2_test():
    """Lucent settings in eight categories; setup assistant with the new buttons and the Solis tab step."""
    xbmc.executeJSONRPC(json.dumps({"jsonrpc": "2.0", "id": 1, "method": "Addons.SetAddonEnabled", "params": {"addonid": "script.solis.dashboard", "enabled": True}}))
    mon.waitForAbort(2)
    xbmc.executebuiltin("ActivateWindow(Settings)")
    mon.waitForAbort(3)
    n = int(lab("Container(9000).NumItems") or 0)
    cats = []
    for i in range(n):
        xbmc.executebuiltin(f"SetFocus(9000,{i},absolute)")
        mon.waitForAbort(0.8)
        cid = 9101 if lab("Container(9000).ListItem.Property(cat)") == "about" else 9100
        k = int(lab(f"Container({cid}).NumItems") or 0)
        cats.append(f"{lab('Container(9000).ListItem.Label')}={k}:" + "|".join(lab(f"Container({cid}).ListItemAbsolute({j}).Label") for j in range(k)))
        if i in (1, 3, 4, 7):
            shot(f"set2-{i}")
    for c in cats:
        log(f"set2: {c[:400]}")
    xbmc.executebuiltin("SetFocus(9000,4,absolute)")
    mon.waitForAbort(0.8)
    xbmc.executebuiltin("SetFocus(9100,13,absolute)")
    mon.waitForAbort(1)
    log(f"set2: system last={lab('Container(9100).ListItem.Label')!r}")
    xbmc.executebuiltin("Action(Select)")
    mon.waitForAbort(2)
    log(f"set2: more kodi dialog={lab('System.CurrentWindow')!r} heading={lab('Control.GetLabel(1)')!r} items={lab('Container(3).NumItems')}")
    shot("set2-more")
    xbmc.executebuiltin("Dialog.Close(all,true)")
    xbmc.executebuiltin("ActivateWindow(home)")
    mon.waitForAbort(2)
    # setup assistant
    xbmc.executebuiltin("RunScript(special://skin/scripts/setup.py)")
    mon.waitForAbort(4)
    k = int(lab("Container(100).NumItems") or 0)
    log(f"set2: setup steps {k}: {[lab(f'Container(100).ListItemAbsolute({j}).Label') for j in range(k)]}")
    for j in range(k):
        name = lab(f"Container(100).ListItemAbsolute({j}).Label")
        if name in ("Live TV (IPTV)", "Lucent Library", "Tabs"):
            xbmc.executebuiltin(f"SetFocus(100,{j},absolute)")
            mon.waitForAbort(0.5)
            xbmc.executebuiltin("Action(Select)")
            mon.waitForAbort(2)
            log(f"set2: setup {name}: status={lab('Window.Property(status)')!r} buttons {[lab(f'Window.Property(act{n})') for n in range(1, 5)]}")
            shot(f"set2-setup-{j}")
    xbmc.executebuiltin("Dialog.Close(all,true)")
    mon.waitForAbort(1)
    import sys as _sys
    _sys.path.insert(0, xbmcvfs.translatePath("special://skin/scripts"))
    import setup as _setup
    _setup.add_solis_tab()
    import menu
    log(f"set2: tabs after add {[t['label'] for t in menu.Menu().tabs]}")
    xbmc.executebuiltin("ActivateWindow(home)")
    mon.waitForAbort(2)


def bell56_test():
    """Library series page: the calendar bell for series that still get new seasons."""
    res = json.loads(xbmc.executeJSONRPC(json.dumps({"jsonrpc": "2.0", "id": 1, "method": "VideoLibrary.GetTVShows",
                                                    "params": {"properties": ["title", "uniqueid"]}})))
    shows = (res.get("result") or {}).get("tvshows") or []
    log(f"bell56: library shows {[(s_.get('tvshowid'), s_.get('title'), s_.get('uniqueid')) for s_ in shows][:5]}")
    if not shows:
        return
    sid = shows[0]["tvshowid"]
    xbmc.executeJSONRPC(json.dumps({"jsonrpc": "2.0", "id": 1, "method": "VideoLibrary.SetTVShowDetails",
                                    "params": {"tvshowid": sid, "uniqueid": {"tmdb": "1002"}}}))
    xbmc.executebuiltin("Skin.SetString(lucent.flattenset,1)")
    xbmc.executeJSONRPC(json.dumps({"jsonrpc": "2.0", "id": 1, "method": "Settings.SetSettingValue", "params": {"setting": "videolibrary.flattentvshows", "value": 0}}))
    xbmc.executebuiltin(f"ActivateWindow(Videos,videodb://tvshows/titles/{sid}/,return)")
    for _ in range(15):
        mon.waitForAbort(1)
        if cond("Control.IsVisible(56)"):
            break
    mon.waitForAbort(3)
    log(f"bell56: view56={cond('Control.IsVisible(56)')} dbid={lab('Container(56).ListItem.TvShowDBID')!r} status5698={lab('Container(5698).ListItem.Status')!r} "
        f"status56={lab('Container(56).ListItem.Status')!r} show={lab('Container.ShowTitle')!r} dbid1={lab('Container(56).ListItemAbsolute(1).TvShowDBID')!r} bell={cond('Control.IsVisible(5614)')} label={lab('Control.GetLabel(5614)')!r}")
    xbmc.executebuiltin("SetFocus(5614)")
    mon.waitForAbort(2)
    log(f"bell56: focus={lab('System.CurrentControlId')} label={lab('Control.GetLabel(5614)')!r}")
    shot("bell56-1")
    xbmc.executebuiltin("Action(Select)")
    mon.waitForAbort(6)
    log(f"bell56: after click prop={HOME.getProperty('lucent.s56.bell')!r} label={lab('Control.GetLabel(5614)')!r} focus={lab('System.CurrentControlId')}")
    steps = []
    for key in ("Right", "Left", "Left", "Right"):
        xbmc.executebuiltin(f"Action({key})")
        mon.waitForAbort(0.8)
        steps.append(f"{key}:{lab('System.CurrentControlId')}")
    log(f"bell56: nav after click {steps}")
    xbmc.executebuiltin("SetFocus(5614)")
    mon.waitForAbort(0.8)
    shot("bell56-2")
    xbmc.executebuiltin("Action(Select)")
    mon.waitForAbort(4)
    log(f"bell56: after 2nd click prop={HOME.getProperty('lucent.s56.bell')!r} label={lab('Control.GetLabel(5614)')!r}")
    # the real way: the list of series, open one, bell, Back
    xbmc.executebuiltin('Skin.SetString(lucent.logoask,"1")')
    for start in ("5614", "5601", "none"):
        xbmc.executebuiltin("ActivateWindow(home)")
        mon.waitForAbort(2)
        xbmc.executebuiltin("ActivateWindow(Videos,videodb://tvshows/titles/,return)")
        for _ in range(10):
            mon.waitForAbort(1)
            if lab("Container.Content") == "tvshows":
                break
        for _ in range(4):
            if lab("ListItem.Label") == "Lib Show":
                break
            xbmc.executebuiltin("Action(Down)")
            mon.waitForAbort(0.6)
        view = lab("System.CurrentControlId")
        log(f"bell56: series list content={lab('Container.Content')} view={view} item={lab('ListItem.Label')!r}")
        xbmc.executebuiltin("Action(Select)")
        for _ in range(8):
            mon.waitForAbort(1)
            if lab("Container.Content") == "seasons":
                break
        mon.waitForAbort(1)
        if start != "none":
            xbmc.executebuiltin(f"SetFocus({start})")
        mon.waitForAbort(1)
        if start == "5614":
            xbmc.executebuiltin("Action(Select)")
            mon.waitForAbort(3)
        log(f"bell56: on the season page content={lab('Container.Content')} focus={lab('System.CurrentControlId')}")
        xbmc.executebuiltin("Action(Back)")
        mon.waitForAbort(3)
        after = [f"back:{lab('System.CurrentControlId')}:{lab('Container.Content')}"]
        for key in ("Down", "Up", "Right"):
            xbmc.executebuiltin(f"Action({key})")
            mon.waitForAbort(0.8)
            after.append(f"{key}:{lab('System.CurrentControlId')}:{lab('ListItem.Label')}")
        log(f"bell56: back from {start} {after}")
        shot(f"bell56-back-{start}")
    xbmc.executebuiltin("ActivateWindow(home)")
    mon.waitForAbort(2)


def misc134_test():
    """Volume pill, Solis prices, New seasons row, Home clock."""
    log(f"misc134: newseasons {json.dumps(json.loads(xbmc.executeJSONRPC(json.dumps({'jsonrpc': '2.0', 'id': 1, 'method': 'Files.GetDirectory', 'params': {'directory': 'plugin://script.lucent.library/?action=lib&kind=newseasons', 'media': 'files'}}))))[:300]}")
    xbmc.Player().play("/tmp/ci/audio.mkv")
    for _ in range(20):
        if cond("Player.HasVideo"):
            break
        mon.waitForAbort(1)
    mon.waitForAbort(4)
    xbmc.executebuiltin("Dialog.Close(all,true)")
    mon.waitForAbort(1)
    for key in ("VolumeDown", "VolumeDown", "VolumeDown"):
        xbmc.executebuiltin(f"Action({key})")
        mon.waitForAbort(0.4)
    mon.waitForAbort(0.6)
    log(f"misc134: volumebar={cond('Window.IsVisible(volumebar)')} pct={HOME.getProperty('lucent.vol.pct')!r} seg={HOME.getProperty('lucent.vol.seg')!r}")
    shot("vol-1")
    xbmc.executebuiltin("Action(Mute)")
    mon.waitForAbort(0.8)
    log(f"misc134: muted={cond('Player.Muted')} volumebar={cond('Window.IsVisible(volumebar)')}")
    shot("vol-2")
    xbmc.executebuiltin("Action(Mute)")
    mon.waitForAbort(3)
    log(f"misc134: after 3s volumebar={cond('Window.IsVisible(volumebar)')} busy={HOME.getProperty('lucent.vol.busy')!r}")
    xbmc.Player().stop()
    mon.waitForAbort(2)


def diaglog_test():
    """Safe log: quick, YouTube lines in it (this run and the previous one), logins blanked out, a short text on screen."""
    import xbmcvfs as _v
    xbmc.log("[plugin.video.youtube] CI trailer line: playback stopped at 65s", xbmc.LOGWARNING)
    xbmc.log("CI secret line http://example.invalid/get.php?username=ciuser&password=cipass", xbmc.LOGWARNING)
    oldp = _v.translatePath("special://logpath/kodi.old.log")
    try:
        with open(oldp, "a", encoding="utf-8") as fh:
            fh.write("2026-11-05 10:00:00.000 T:1 warning <general>: CI old run: InputStream Adaptive stopped\n")
    except OSError as e:
        log(f"diaglog: old log not writable {e}")
    t0 = time.time()
    xbmc.executebuiltin("RunScript(special://skin/scripts/diag.py,log)")
    for _ in range(80):
        if cond("Window.IsActive(okdialog)"):
            break
        mon.waitForAbort(0.25)
    log(f"diaglog: ok dialog after {time.time() - t0:.1f}s visible={cond('Window.IsActive(okdialog)')}")
    shot("diaglog-ok")
    xbmc.executebuiltin("Action(Select)")
    t1 = time.time()
    for _ in range(80):
        if cond("Window.IsActive(textviewer)"):
            break
        mon.waitForAbort(0.25)
    mon.waitForAbort(1)
    log(f"diaglog: textviewer after {time.time() - t1:.1f}s visible={cond('Window.IsActive(textviewer)')}")
    shot("diaglog-text")
    xbmc.executebuiltin("Dialog.Close(textviewer,true)")
    mon.waitForAbort(1)
    try:
        body = open(_v.translatePath("special://home/lucent-log.txt"), encoding="utf-8").read()
    except OSError as e:
        body = ""
        log(f"diaglog: no file {e}")
    log(f"diaglog: size={len(body)} yt={'CI trailer line' in body} old={'CI old run' in body} "
        f"pass_hidden={'cipass' not in body and 'ciuser' not in body} header={body.splitlines()[1][:120] if body.count(chr(10)) > 1 else ''}")
    log(f"diaglog: back on home={cond('Window.IsActive(home)')} dialogs={cond('System.HasVisibleModalDialog')}")


def waitfor(c, secs=10):
    for _ in range(int(secs * 4)):
        if cond(c):
            return True
        mon.waitForAbort(0.25)
    return False


CTX_VIS = ("ListItem.IsFolder + !ListItem.IsParentFolder + !String.IsEmpty(Skin.String(nuvio.tab1.label)) + !Window.IsVisible(home) + "
           "[String.StartsWith(ListItem.FileNameAndPath,plugin://) | String.StartsWith(ListItem.FileNameAndPath,videodb://)]")


def noseren_test():
    """1.34: 'Add to Home as widget' in the context menu, the menu without Seren, the setup question."""
    import sys as _s
    _s.path.insert(0, xbmcvfs.translatePath("special://skin/scripts"))
    # 1. the context item on a library folder
    xbmc.executebuiltin("ActivateWindow(Videos,videodb://movies/,return)")
    waitfor("Window.IsActive(videos)")
    mon.waitForAbort(3)
    for _ in range(3):
        if not cond("ListItem.IsParentFolder"):
            break
        key("Down")
        mon.waitForAbort(1)
    import re as _re
    vis = _re.search(r'args="addwidget">.*?<visible>(.*?)</visible>',
                     open(xbmcvfs.translatePath("special://home/addons/script.lucent.library/addon.xml"), encoding="utf-8").read(), _re.S).group(1)
    log(f"ctx: item={lab('ListItem.Label')} folderpath={lab('ListItem.FolderPath')} path={lab('ListItem.Path')} "
        f"folder={cond('ListItem.IsFolder')} vis={cond(vis)}")
    xbmc.executebuiltin("Action(ContextMenu)")
    log(f"ctx: menu open={waitfor('Window.IsActive(contextmenu)', 6)}")
    mon.waitForAbort(1)
    shot("ctx-menu")
    xbmc.executebuiltin("Dialog.Close(contextmenu,true)")
    xbmc.executebuiltin("ActivateWindow(home)")
    waitfor("Window.IsActive(home)")
    mon.waitForAbort(2)
    # 2. add a widget (what the context item does)
    HOME.setProperty("lucent.addw.path", "videodb://movies/genres/")
    HOME.setProperty("lucent.addw.label", "CI Genres")
    xbmc.executebuiltin("RunScript(special://skin/scripts/menu.py,addwidget)")
    log(f"addw: tab list={waitfor('Window.IsActive(selectdialog)')}")
    mon.waitForAbort(1)
    shot("addw-tabs")
    xbmc.executebuiltin("Action(Select)")
    log(f"addw: keyboard={waitfor('Window.IsActive(virtualkeyboard)')}")
    mon.waitForAbort(1)
    xbmc.executebuiltin("SendClick(10103,300)")
    log(f"addw: style={waitfor('Window.IsActive(selectdialog)')}")
    mon.waitForAbort(1)
    xbmc.executebuiltin("Action(Select)")
    mon.waitForAbort(3)
    found = [(t_, w_) for t_ in range(1, 13) for w_ in range(1, 11)
             if lab(f"Skin.String(nuvio.tab{t_}.w{w_}.path)") == "videodb://movies/genres/" and lab(f"Skin.String(nuvio.tab{t_}.w{w_}.label)") == "CI Genres"]
    log(f"addw: saved at {found} tab1={lab('Skin.String(nuvio.tab1.label)')} style={lab(f'Skin.String(nuvio.tab{found[0][0]}.w{found[0][1]}.style)') if found else ''}")
    # 3. without Seren
    xbmc.executebuiltin("Skin.SetBool(lucent.noseren)")
    mon.waitForAbort(1)
    import menu as _menu
    import importlib
    importlib.reload(_menu)
    log(f"noseren: uses_seren={_menu.uses_seren()}")
    m = _menu.Menu()
    m.set_defaults()
    m.save()
    xbmc.executebuiltin("ReloadSkin()")
    mon.waitForAbort(6)
    waitfor("Window.IsActive(home)")
    mon.waitForAbort(6)
    tabs = [lab(f"Skin.String(nuvio.tab{i}.label)") for i in range(1, 13)]
    log(f"noseren: tabs={[x for x in tabs if x]} search={lab('Skin.String(nuvio.tab1.action)')} seren_in_menu={any('plugin.video.seren' in lab(f'Skin.String(nuvio.tab{i}.action)') for i in range(1, 13))}")
    log(f"noseren: home rows={[lab(f'Skin.String(nuvio.home.w{w}.label)') for w in range(1, 6)]}")
    shot("noseren-home")
    import setup as _setup
    log(f"noseren: setup status={_setup.st_seren()} actions={[a[0] for a in _setup.ac_seren()]} steps={[x[0] for x in _setup.STEPS]}")
    xbmc.executebuiltin("Skin.Reset(lucent.noseren)")
    mon.waitForAbort(1)
    importlib.reload(_setup)
    log(f"seren: setup status={_setup.st_seren()} actions={[a[0] for a in _setup.ac_seren()]}")


def dv2_test():
    """1.34.1: Dolby Vision 2 from the release name, the DV line on the Video tab of the player info, the DV2 flag."""
    import sys as _s
    import re as _re
    _s.path.insert(0, xbmcvfs.translatePath("special://skin/scripts"))
    import playerinfo as _pi
    for n in ("Movie.2026.2160p.PCOK.WEB-DL.DV2.HDR10.Atmos-GRP.mkv", "Film.2024.2160p.BluRay.REMUX.DV.P7.FEL.TrueHD-X.mkv", "x.DV.2160p.mkv"):
        log(f"dv2: name {n} -> {_pi.dv_from_name(n)}")
    dvn = _pi.dv_from_name("Movie.2026.2160p.PCOK.WEB-DL.DV2.HDR10.Atmos-GRP.mkv")
    _pi.dv_line("dolbyvision", _re.search(r"(\d+)", "8"), "FEL", dvn)
    log("dv2: props " + json.dumps({k: HOME.getProperty("lucent.pi." + k) for k in ("v.dv.on", "v.dv.line", "v.dv.note")}, ensure_ascii=False))
    log(f"dv2: flag file={os.path.exists(xbmcvfs.translatePath('special://skin/media/flags/DV2.png'))}")
    for k, v in (("title", "Movie.2026.2160p.PCOK.WEB-DL.DV2.HDR10.Atmos-GRP.mkv"), ("b.res", "4K"), ("b.dv", "DOLBY VISION 2 P8 FEL"),
                 ("v.hdrbar", "dv"), ("v.hb.dv", "DOLBY VISION 2"), ("v.hb2", "PROFIEL 8 FEL"), ("v.p1k", "Bestand"), ("v.p1", "HEVC 10-bit")):
        HOME.setProperty("lucent.pi." + k, v)
    w = xbmcgui.WindowXMLDialog("Lucent_PlayerInfo.xml", xbmcvfs.translatePath("special://skin/"), "Default", "1080i")
    w.show()
    mon.waitForAbort(1.5)
    w.setFocusId(102)
    HOME.setProperty("lucent.pi.tab", "2")
    mon.waitForAbort(2)
    log(f"dv2: window={cond('Window.IsVisible(Lucent_PlayerInfo.xml)')} tab={HOME.getProperty('lucent.pi.tab')}")
    shot("dv2-video")
    w.close()
    mon.waitForAbort(1)


def videotab_test():
    """1.34.9: the Video tab of the player info is filled all the way (1.34.1 stopped halfway: name 'dvn' unknown)."""
    import sys as _s
    import re as _re
    _s.path.insert(0, xbmcvfs.translatePath("special://skin/scripts"))
    import playerinfo as _pi
    for k in ("v.p1", "v.p2", "v.p3", "v.p4k", "v.br", "v.dv.line", "v.gamut"):
        HOME.clearProperty("lucent.pi." + k)
    v = {"w": "3840", "h": "2160", "fps": "23.976", "hdr": "dolbyvision", "res_badge": "4K", "prof": _re.search(r"(\d+)", "7"),
         "layer": "FEL", "pix": "yuv420p10", "ten": True, "vname": "HEVC", "scan_word": "progressief", "vbr": 61.2,
         "dvn": _pi.dv_from_name("The.Movie.2026.2160p.BluRay.REMUX.DV.P7.FEL.TrueHD.Atmos.7.1-X.mkv")}
    try:
        _pi.video_tab(v)
        err = None
    except Exception as e:  # noqa: BLE001
        err = repr(e)
    log("videotab: err=%s props=%s" % (err, json.dumps({k: HOME.getProperty("lucent.pi." + k) for k in ("v.p1", "v.p2", "v.p3", "v.p4k", "v.br", "v.dv.line", "v.gamut")}, ensure_ascii=False)))


def skipdup_test():
    """1.34.9: Seren and TheIntroDB both show Skip intro: the choice switches the other one off (fake add-on settings)."""
    import sys as _s
    import types as _t
    if not xbmcvfs.exists("special://skin/scripts/skipdup.py"):        # moved out of the skin in 1.37.0
        log("skipdup: not in this skin")
        return
    _s.path.insert(0, xbmcvfs.translatePath("special://skin/scripts"))
    import skipdup as _d

    class Fake:
        def __init__(self, vals):
            self.vals = dict(vals)

        def getSetting(self, k):
            return self.vals.get(k, "")

        def setSetting(self, k, v):
            self.vals[k] = v

        def getAddonInfo(self, k):
            return "3.9.90"

    out = {}
    for choice in ("tidb", "seren"):
        seren = Fake({"skip.intro": "true", "skip.recap": "true", "skip.credits": "false", "skip.autoIntro": "true"})
        tidb = Fake({"introdb_enabled": "true", "enable_intro": "true", "enable_recap": "true", "enable_credits": "true"})
        addons = {_d.SEREN: seren, _d.TIDB: tidb}
        _d._addon = lambda i: addons[i]
        _d.xbmcaddon = _t.SimpleNamespace(Addon=lambda i: addons[i])
        before = _d.both_on()
        xbmc.executebuiltin(f"Skin.SetString(lucent.skipby,{choice})")
        mon.waitForAbort(0.5)
        result = _d.check()
        out[choice] = {"before": before, "result": result, "after": _d.both_on(), "label": _d.label(),
                       "seren": {k: seren.vals.get(k) for k in ("skip.intro", "skip.recap", "skip.autoIntro")},
                       "tidb": {k: tidb.vals.get(k) for k in ("enable_intro", "enable_recap", "enable_credits")}}
    xbmc.executebuiltin("Skin.Reset(lucent.skipby)")
    log("skipdup: " + json.dumps(out))


def scrub_open_test():
    """1.34.10: the safe log hides playback links; the player info opens although 'open' stayed behind."""
    import sys as _s
    _s.path.insert(0, xbmcvfs.translatePath("special://skin/scripts"))
    import diag as _dg
    samples = ["VideoPlayer::OpenFile: https://abc12-aiostreams.elfhosted.wine/api/v1/debrid/playback/eyJpZCI6IjEyMyJ9",
               "Error resolving item. Item 'plugin://plugin.video.seren/?action=getSources&action_args=%257B'",
               "CCurlFile::Open - <http://picon.example.net:25461/picon/NL/HGTV 8K+ UHD.png> Failed"]
    log("scrub: " + json.dumps([_dg.scrub(x, set()) for x in samples], ensure_ascii=False))
    pl = xbmc.Player()
    xbmc.executebuiltin("PlayMedia(/tmp/ci/test.mkv)")
    for _ in range(40):
        if pl.isPlayingVideo():
            break
        mon.waitForAbort(0.5)
    mon.waitForAbort(3)
    for case, flag in (("clean", ""), ("left-behind", "1")):
        if flag:
            HOME.setProperty("lucent.pi.open", flag)                 # left behind, the screen is not on
        else:
            HOME.clearProperty("lucent.pi.open")
        xbmc.executebuiltin("RunScript(special://skin/scripts/playerinfo.py,open)")
        seen = False
        for _ in range(16):
            mon.waitForAbort(0.5)
            if cond("Window.IsVisible(Lucent_PlayerInfo.xml)"):
                seen = True
                break
        log(f"pinfo-open: {case} playing={pl.isPlayingVideo()} shown={seen}")
        if seen:
            shot(f"pinfo-open-{case}")
        xbmc.executebuiltin("Action(Back)")
        mon.waitForAbort(1.5)
        xbmc.executebuiltin("Dialog.Close(all,true)")
        mon.waitForAbort(1)
    pl.stop()
    mon.waitForAbort(2)
    HOME.clearProperty("lucent.pi.open")


def readable_test():
    """1.34.11: readable text on light pictures (dark edge on the hero texts, darker fade with the fullscreen backdrop)."""
    res = json.loads(xbmc.executeJSONRPC(json.dumps({"jsonrpc": "2.0", "id": 1, "method": "VideoLibrary.GetMovies", "params": {}})))
    movies = (res.get("result") or {}).get("movies") or []
    if not movies:
        log("readable: no movie")
        return
    mid = movies[0]["movieid"]
    xbmc.executeJSONRPC(json.dumps({"jsonrpc": "2.0", "id": 1, "method": "VideoLibrary.SetMovieDetails",
                                    "params": {"movieid": mid, "art": {"fanart": "/tmp/ci/bright.jpg"},
                                               "plot": "A long plot line to see how readable the text is over a very light picture, all the way to the right side of the screen.",
                                               "genre": ["Horror", "Thriller", "Science Fiction"]}}))
    xbmc.executebuiltin("Skin.SetBool(nuvio.fullbackdrop)")
    xbmc.executebuiltin("ActivateWindow(Videos,videodb://movies/titles/,return)")
    mon.waitForAbort(3)
    xbmc.executebuiltin("Container.SetViewMode(51)")
    mon.waitForAbort(1.5)
    xbmc.executebuiltin("SetFocus(51)")
    for _ in range(4):
        if lab("ListItem.DBType") == "movie":
            break
        key("Right")
        mon.waitForAbort(1)
    for case in ("on", "off"):
        if case == "off":
            xbmc.executebuiltin("Skin.SetBool(lucent.readable.off)")
        else:
            xbmc.executebuiltin("Skin.Reset(lucent.readable.off)")
        mon.waitForAbort(2.5)
        log(f"readable: {case} item={lab('ListItem.Label')} fanart={lab('ListItem.Art(fanart)')} var={lab('$VAR[LucentTextShadow]')}")
        shot(f"readable-{case}")
    xbmc.executebuiltin("Skin.Reset(lucent.readable.off)")
    xbmc.executebuiltin("Skin.Reset(nuvio.fullbackdrop)")
    xbmc.executebuiltin("ActivateWindow(home)")
    mon.waitForAbort(2)


def landseries_test():
    """1.34.12: episodes in landscape rows: still of the episode (default) or the series' landscape art."""
    xbmc.executeJSONRPC(json.dumps({"jsonrpc": "2.0", "id": 1, "method": "VideoLibrary.SetTVShowDetails",
                                    "params": {"tvshowid": 901, "art": {"landscape": "/tmp/ci/bright.jpg", "fanart": "/tmp/ci/bright.jpg"}}}))
    xbmc.executeJSONRPC(json.dumps({"jsonrpc": "2.0", "id": 1, "method": "VideoLibrary.SetEpisodeDetails",
                                    "params": {"episodeid": 901, "art": {"thumb": "/tmp/ci/test_still.jpg"}}}))
    xbmc.executebuiltin("ActivateWindow(Videos,videodb://tvshows/titles/901/1/,return)")
    mon.waitForAbort(3)
    xbmc.executebuiltin("Container.SetViewMode(50)")
    mon.waitForAbort(1.5)
    xbmc.executebuiltin("SetFocus(50)")
    mon.waitForAbort(1)
    log(f"landseries: folder={lab('Container.FolderPath')} items={lab('Container.NumItems')}")
    for _ in range(4):
        if lab("ListItem.DBType") == "episode":
            break
        key("Down")
        mon.waitForAbort(1)
    out = {}
    for case in ("episode", "series"):
        if case == "series":
            xbmc.executebuiltin("Skin.SetBool(lucent.land.series)")
        else:
            xbmc.executebuiltin("Skin.Reset(lucent.land.series)")
        mon.waitForAbort(1)
        out[case] = lab("$VAR[ItemLandscape]")
    xbmc.executebuiltin("Skin.Reset(lucent.land.series)")
    log(f"landseries: item={lab('ListItem.Label')} type={lab('ListItem.DBType')} tvland={lab('ListItem.Art(tvshow.landscape)')} {json.dumps(out)}")
    xbmc.executebuiltin("ActivateWindow(home)")
    mon.waitForAbort(2)


def fenlight_test():
    """1.34.13 + Library 1.15.5: Browse series / episodes and Mark as watched for a Fen Light clone (CI stand-in)."""
    log(f"fenlight: addon={cond('System.HasAddon(plugin.video.fakefen)')}")
    out = {}
    for what in ("browseshow", "browseeps"):
        xbmc.executebuiltin("Dialog.Close(all,true)")
        xbmc.executebuiltin("ActivateWindow(home)")
        mon.waitForAbort(2.5)
        xbmc.executebuiltin("ActivateWindow(Videos,plugin://plugin.video.fakefen/?mode=list,return)")
        mon.waitForAbort(2)
        xbmc.executebuiltin("Container.Update(plugin://plugin.video.fakefen/?mode=list,replace)")
        mon.waitForAbort(3)
        xbmc.executebuiltin("Container.SetViewMode(50)")
        mon.waitForAbort(1)
        xbmc.executebuiltin("SetFocus(50)")
        for _ in range(4):
            if lab("ListItem.DBType") == "episode":
                break
            key("Down")
            mon.waitForAbort(1)
        before = f"{lab('ListItem.Label')} tmdb={lab('ListItem.UniqueID(tmdb)')} s={lab('ListItem.Season')}"
        xbmc.executebuiltin(f"RunScript(special://home/addons/script.lucent.library/context.py,{what})")
        mon.waitForAbort(4)
        out[what] = {"on": before, "now": lab("Container.FolderPath"), "first": lab("Container(50).ListItem(0).Label")}
    log("fenlight: browse " + json.dumps(out))
    xbmc.executebuiltin("Container.Update(plugin://plugin.video.fakefen/?mode=list,replace)")
    mon.waitForAbort(3)
    xbmc.executebuiltin("SetFocus(9050)")
    mon.waitForAbort(1.5)
    log(f"addonsettings: plugin={lab('Container.PluginName')!r} visible9069={cond('Control.IsVisible(9069)')} label={lab('Control.GetLabel(9069)')!r}")
    shot("addonsettings-side")
    key("Down")
    mon.waitForAbort(0.8)
    shot("addonsettings-side-down")
    xbmc.executebuiltin("Dialog.Close(all,true)")
    xbmc.executebuiltin("ActivateWindow(Videos,videodb://movies/titles/,return)")
    mon.waitForAbort(3)
    xbmc.executebuiltin("SetFocus(9050)")
    mon.waitForAbort(1.5)
    log(f"sidemenu: library focus={lab('System.CurrentControlId')} v9069={cond('Control.IsVisible(9069)')} v9062={cond('Control.IsVisible(9062)')}")
    shot("sidemenu-library")
    xbmc.executebuiltin("Action(Back)")
    mon.waitForAbort(1)
    log(f"sidemenu: after back focus={lab('System.CurrentControlId')} window={lab('System.CurrentWindow')}")
    xbmc.executebuiltin("ActivateWindow(home)")
    mon.waitForAbort(2.5)
    xbmc.executebuiltin("ActivateWindow(Videos,plugin://plugin.video.fakefen/?mode=list,return)")
    mon.waitForAbort(2)
    xbmc.executebuiltin("Container.Update(plugin://plugin.video.fakefen/?mode=list,replace)")
    mon.waitForAbort(3)
    xbmc.executebuiltin("SetFocus(50)")
    for _ in range(4):
        if lab("ListItem.DBType") == "episode":
            break
        key("Down")
        mon.waitForAbort(1)
    xbmc.executebuiltin("Action(Info)")
    for _ in range(20):
        if cond("Window.IsActive(movieinformation)"):
            break
        mon.waitForAbort(0.5)
    mon.waitForAbort(2)
    log(f"fenlight: info={cond('Window.IsActive(movieinformation)')} button22={cond('Control.IsVisible(22)')}")
    try:
        import sys as _s
        _s.path.insert(0, xbmcvfs.translatePath("special://skin/scripts"))
        import info as _inf
        it = _inf.Item()
        log(f"fenlight: diag fen={_inf.fen_light_id()!r} path={lab('ListItem.FileNameAndPath')!r} ids={bool(it.ids())} tmdb={it.tmdb!r} type={it.dbtype} "
            f"s={lab('ListItem.Season')} e={lab('ListItem.Episode')}")
    except Exception as _e:  # noqa: BLE001
        log(f"fenlight: diag error {_e!r}")
    xbmc.executebuiltin("RunScript(special://skin/scripts/info.py,watched)")
    mon.waitForAbort(4)
    log(f"fenlight: after dialog={lab('System.CurrentWindow')} prop={HOME.getProperty('nuvio.info.watched')!r}")
    try:
        calls = open("/tmp/ci/fakefen.log").read().splitlines()
    except OSError:
        calls = []
    log("fenlight: calls " + json.dumps(calls))
    xbmc.executebuiltin("Dialog.Close(all,true)")
    xbmc.executebuiltin("ActivateWindow(home)")
    mon.waitForAbort(2)



def sideclick_test():
    """The side menu in an add-on folder: does every button do something when pressed?"""
    out = {}
    def fresh():
        xbmc.executebuiltin("Dialog.Close(all,true)")
        xbmc.executebuiltin("ActivateWindow(Videos,plugin://plugin.video.fakefen/?mode=list,return)")
        mon.waitForAbort(2)
        xbmc.executebuiltin("Container.Update(plugin://plugin.video.fakefen/?mode=list,replace)")
        mon.waitForAbort(2.5)
    fresh()
    key("Left")
    mon.waitForAbort(1.2)
    out["open_by_left"] = {"focus": lab("System.CurrentControlId"), "menu": cond("ControlGroup(9050).HasFocus")}
    path = [lab("System.CurrentControlId")]
    for _ in range(9):
        key("Down")
        mon.waitForAbort(0.4)
        path.append(lab("System.CurrentControlId"))
    for _ in range(3):
        key("Up")
        mon.waitForAbort(0.4)
        path.append(lab("System.CurrentControlId"))
    out["nav_path"] = path
    shot("sideclick-nav")
    for cid in ("2", "3", "4", "19", "10", "9061", "20", "9069"):
        fresh()
        xbmc.executebuiltin("SetFocus(9050)")
        mon.waitForAbort(1)
        xbmc.executebuiltin(f"SetFocus({cid})")
        mon.waitForAbort(0.8)
        before = {"focus": lab("System.CurrentControlId"), "visible": cond(f"Control.IsVisible({cid})"), "enabled": cond(f"Control.IsEnabled({cid})"),
                  "view": lab("Container.Viewmode"), "sort": lab("Container.SortMethod"), "order": cond("Container.SortDirection(ascending)"),
                  "label": lab(f"Control.GetLabel({cid})")}
        key("Return")
        mon.waitForAbort(2)
        after = {"focus": lab("System.CurrentControlId"), "window": lab("System.CurrentWindow"), "dialog": cond("System.HasModalDialog"),
                 "view": lab("Container.Viewmode"), "sort": lab("Container.SortMethod"), "order": cond("Container.SortDirection(ascending)")}
        shot(f"sideclick-{cid}")
        out[cid] = {"before": before, "after": after}
        xbmc.executebuiltin("Dialog.Close(all,true)")
        mon.waitForAbort(0.8)
    log("sideclick: " + json.dumps(out))
    xbmc.executebuiltin("ActivateWindow(home)")
    mon.waitForAbort(2)


def views_pause_test():
    """1.34.14: the view per kind (issue #5) and the clean picture when paused (issue #4)."""
    xbmc.executebuiltin("Skin.Reset(lucent.view.remember.off)")
    xbmc.executebuiltin("Skin.Reset(lucent.view.videos.episodes)")
    xbmc.executebuiltin("ActivateWindow(home)")
    mon.waitForAbort(2)
    xbmc.executebuiltin("ActivateWindow(Videos,videodb://tvshows/titles/901/1/,return)")
    mon.waitForAbort(3)
    xbmc.executebuiltin("Container.SetViewMode(50)")
    mon.waitForAbort(3)
    xbmc.executebuiltin("Container.SetViewMode(55)")
    mon.waitForAbort(3)
    saved = lab("Skin.String(lucent.view.videos.episodes)")
    xbmc.executebuiltin("ActivateWindow(home)")
    mon.waitForAbort(2)
    xbmc.executebuiltin("ActivateWindow(Videos,videodb://recentlyaddedepisodes/,return)")
    mon.waitForAbort(4)
    log(f"views: saved={saved!r} other folder content={lab('Container.Content')} items={lab('Container.NumItems')} "
        f"view55={cond('Control.IsVisible(55)')} view50={cond('Control.IsVisible(50)')} mode={lab('Container.Viewmode')}")
    xbmc.executebuiltin("Container.SetViewMode(50)")
    mon.waitForAbort(2)
    xbmc.executebuiltin("Skin.Reset(lucent.view.videos.episodes)")
    xbmc.executebuiltin("ActivateWindow(home)")
    mon.waitForAbort(2)
    pl = xbmc.Player()
    out = {}
    autosubs = cond("Skin.HasSetting(nuvio.autosubs)")
    xbmc.executebuiltin("Skin.Reset(nuvio.autosubs)")
    for setting in ("clean3", ""):
        xbmc.executebuiltin(f"Skin.SetString(nuvio.pauseinfo,{setting})" if setting else "Skin.Reset(nuvio.pauseinfo)")
        xbmc.executebuiltin("PlayMedia(/tmp/ci/test.mkv)")
        for _ in range(40):
            if pl.isPlayingVideo():
                break
            mon.waitForAbort(0.5)
        mon.waitForAbort(10)                          # on CI the video really starts ~9 s after PlayMedia
        for _ in range(3):                            # the automatic subtitle search may have opened its window
            xbmc.executebuiltin("Dialog.Close(all,true)")
            mon.waitForAbort(1)
        xbmc.executebuiltin("PlayerControl(Play)")    # pause
        mon.waitForAbort(1)
        early = cond("Window.IsVisible(seekbar)")
        mon.waitForAbort(5)
        out[setting or "default"] = {"paused": cond("Player.Paused"), "bar_at_1s": early, "bar_at_6s": cond("Window.IsVisible(seekbar)")}
        xbmc.executebuiltin("ActivateWindow(videoosd)")             # the player menu, as OK opens it on a Shield
        mon.waitForAbort(1)
        out[setting or "default"]["osd_opened"] = cond("Window.IsActive(videoosd)")
        out[setting or "default"]["diag"] = {c: cond(c) for c in ("Player.Paused", "Window.IsActive(videoosd)", "System.HasActiveModalDialog",
                                                              "Window.IsActive(sliderdialog)", "System.IdleTime(3)", "Window.IsVisible(videoosd)")}
        out[setting or "default"]["diag"]["pauseinfo"] = lab("Skin.String(nuvio.pauseinfo)")
        out[setting or "default"]["diag"]["helper"] = HOME.getProperty("lucent.helper")
        mon.waitForAbort(5)
        out[setting or "default"]["osd_after_6s"] = cond("Window.IsActive(videoosd)")
        xbmc.executebuiltin("Dialog.Close(videoosd)")
        mon.waitForAbort(1)
        shot(f"pause-{setting or 'default'}")
        pl.stop()
        mon.waitForAbort(3)
    xbmc.executebuiltin("Skin.Reset(nuvio.pauseinfo)")
    if autosubs:
        xbmc.executebuiltin("Skin.SetBool(nuvio.autosubs)")
    log("pauseclean: " + json.dumps(out))


def pct_test():
    """1.34.16: percentage watched above the progress bar (issue #7)."""
    xbmc.executebuiltin("ActivateWindow(home)")
    mon.waitForAbort(2)
    xbmc.executebuiltin("ActivateWindow(Videos,videodb://movies/titles/,return)")
    mon.waitForAbort(3)
    xbmc.executebuiltin("Container.SetViewMode(51)")
    mon.waitForAbort(1.5)
    xbmc.executebuiltin("SetFocus(51)")
    for _ in range(4):
        if lab("ListItem.DBType") == "movie":
            break
        key("Right")
        mon.waitForAbort(1)
    for case in ("on", "off"):
        xbmc.executebuiltin("Skin.SetBool(lucent.pct.off)" if case == "off" else "Skin.Reset(lucent.pct.off)")
        mon.waitForAbort(1.5)
        log(f"pct: {case} item={lab('ListItem.Label')} percent={lab('ListItem.PercentPlayed')}")
        shot(f"pct-{case}")
    xbmc.executebuiltin("Skin.Reset(lucent.pct.off)")
    xbmc.executebuiltin("ActivateWindow(home)")
    mon.waitForAbort(2)


def mdblist_test():
    """1.34.17 (issue #8): MDBList scores (Letterboxd, RT audience, Metacritic users) on the info page and in the lists,
    with only an MDBList key (no OMDb key): MDBList also fills RT / Metacritic / IMDb."""
    import sys as _s
    _s.path.insert(0, xbmcvfs.translatePath("special://skin/scripts"))
    import omdb as _o
    d = xbmcvfs.translatePath("special://profile/addon_data/skin.lucent/")
    os.makedirs(d, exist_ok=True)
    for f in ("omdb.key", "omdb_cache.json", "mdblist_cache.json"):
        try:
            os.remove(os.path.join(d, f))
        except OSError:
            pass
    with open(os.path.join(d, "mdblist.key"), "w") as fh:
        fh.write("cimdbkey")
    log(f"mdblist: parse={_o.mdb_fetch('tt0185937', 'movie')} text={_o.list_text(_o.all_scores('tt0185937', 'movie'))!r}")
    mon.waitForAbort(31)                                  # the helper reads the keys again after 30 s
    xbmc.executebuiltin("ActivateWindow(home)")
    mon.waitForAbort(2)
    xbmc.executebuiltin("ActivateWindow(Videos,videodb://movies/titles/,return)")
    mon.waitForAbort(3)
    xbmc.executebuiltin("Container.SetViewMode(51)")
    mon.waitForAbort(1.5)
    xbmc.executebuiltin("SetFocus(51)")
    for _ in range(4):
        if lab("ListItem.DBType") == "movie":
            break
        key("Right")
        mon.waitForAbort(1)
    mon.waitForAbort(4)
    p = {k: HOME.getProperty("lucent.omdbl." + k) for k in ("rt", "rta", "mc", "mcu", "lb", "text", "for")}
    log(f"mdblist: list item={lab('ListItem.Label')} props={json.dumps(p, ensure_ascii=False)}")
    shot("mdblist-list")
    xbmc.executebuiltin("Action(Info)")
    for _ in range(20):
        if cond("Window.IsActive(movieinformation)"):
            break
        mon.waitForAbort(0.5)
    mon.waitForAbort(4)
    p = {k: HOME.getProperty("lucent.omdb." + k) for k in ("imdb", "rt", "rta", "mc", "mcu", "lb", "lb.c", "for")}
    log(f"mdblist: page props={json.dumps(p, ensure_ascii=False)}")
    shot("mdblist-page")
    xbmc.executebuiltin("Dialog.Close(all,true)")
    os.remove(os.path.join(d, "mdblist.key"))
    xbmc.executebuiltin("ActivateWindow(home)")
    mon.waitForAbort(2)


def mediaflags_test():
    """1.34.18 (issue #9): media flags in the list with the big picture, for a film, a series and an episode."""
    out = {}
    for name, path in (("movie", "videodb://movies/titles/"), ("tvshow", "videodb://tvshows/titles/"), ("episode", "videodb://tvshows/titles/901/1/")):
        xbmc.executebuiltin("Dialog.Close(all,true)")
        xbmc.executebuiltin("ActivateWindow(home)")
        mon.waitForAbort(2)
        xbmc.executebuiltin("Dialog.Close(all,true)")
        mon.waitForAbort(1)
        xbmc.executebuiltin(f"ActivateWindow(Videos,{path},return)")
        mon.waitForAbort(3)
        xbmc.executebuiltin("Container.SetViewMode(51)")
        mon.waitForAbort(1.5)
        xbmc.executebuiltin("SetFocus(51)")
        for _ in range(4):
            if lab("ListItem.DBType") == name:
                break
            key("Right")
            mon.waitForAbort(1)
        mon.waitForAbort(2.5)
        out[name] = {"item": lab("ListItem.Label"), "res": lab("ListItem.VideoResolution"), "hdr": lab("ListItem.HdrType"),
                     **{k: HOME.getProperty("lucent.mf." + k) for k in ("img1", "img2", "img3", "img4", "img5", "img6", "alang", "slang", "most", "for")},
                     "logos": [HOME.getProperty(f"lucent.mf.l{i}") + "/" + HOME.getProperty(f"lucent.mf.w{i}") for i in range(1, 8)]}
        shot(f"mediaflags-{name}")
        if name in ("movie", "episode"):                 # 1.35.2: shown at once, and the row keeps its place
            xbmc.executebuiltin("Action(Left)")
            mon.waitForAbort(1.5)
            shot(f"mediaflags-{name}-noflags")
            xbmc.executebuiltin("Action(Right)")
            t0 = time.time()
            while not HOME.getProperty("lucent.mf.img1") and time.time() - t0 < 3:
                mon.waitForAbort(0.05)
            out[name]["fast_s"] = round(time.time() - t0, 2)
            out[name]["fast"] = {"item": lab("ListItem.Label"), "for": HOME.getProperty("lucent.mf.for")[:40],
                                 "img1": HOME.getProperty("lucent.mf.img1"),
                                 "row": cond("!Skin.HasSetting(lucent.mf.off) + String.StartsWith(Container.FolderPath,videodb://)")}
    log("mediaflags: " + json.dumps(out))
    xbmc.executebuiltin("ActivateWindow(home)")
    mon.waitForAbort(2)


def ytfix_test():
    """1.34.2: the YouTube trailer fix on a copy of player_client.py of YouTube 7.4.4 (the add-on is not in CI)."""
    import sys as _s
    import shutil as _sh
    import types as _t
    _s.path.insert(0, xbmcvfs.translatePath("special://skin/scripts"))
    import ytfix as _y
    src = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "ci", "data", "yt744_player_client.py")
    if not os.path.exists(src):
        src = "/tmp/ci/yt744_player_client.py"
    work = xbmcvfs.translatePath("special://temp/ytfix/player_client.py")
    os.makedirs(os.path.dirname(work), exist_ok=True)
    _sh.copyfile(src, work)
    real = _y.xbmc
    fake = _t.SimpleNamespace(**{k: getattr(real, k) for k in dir(real) if not k.startswith("__")})
    fake.getCondVisibility = lambda c: True if "HasAddon(plugin.video.youtube)" in c else real.getCondVisibility(c)
    _y.xbmc = fake
    _y.FILE = "special://temp/ytfix/player_client.py"
    xbmc.executebuiltin("Skin.Reset(lucent.ytfix.off)")
    mon.waitForAbort(0.5)
    r1 = _y.check()
    txt = open(work, encoding="utf-8").read()
    import py_compile
    try:
        py_compile.compile(work, doraise=True)
        ok = True
    except Exception as e:  # noqa: BLE001
        ok = repr(e)
    backups = os.listdir(xbmcvfs.translatePath(_y.BACKUP_DIR)) if os.path.isdir(xbmcvfs.translatePath(_y.BACKUP_DIR)) else []
    log(f"ytfix: on -> {r1} marker={'lucent-ytfix' in txt} vr_active={chr(39) + 'android_vr' + chr(39) + ',' in txt.replace('# ' + chr(39) + 'android_vr', '')} compiles={ok} backups={backups} label={_y.label()}")
    log(f"ytfix: again -> {_y.check()}")
    xbmc.executebuiltin("Skin.SetBool(lucent.ytfix.off)")
    mon.waitForAbort(0.5)
    r2 = _y.check()
    log(f"ytfix: off -> {r2} identical={open(work, encoding='utf-8').read() == open(src, encoding='utf-8').read()} label={_y.label()}")
    xbmc.executebuiltin("Skin.Reset(lucent.ytfix.off)")
    _y.xbmc = real


def fsback_test():
    """1.34.3: Back while skipping (a seek just done, fast forward) must not stop the film; Back later does."""
    pl = xbmc.Player()
    xbmc.executebuiltin("PlayMedia(/tmp/ci/test.mkv)")
    for _ in range(30):
        if pl.isPlayingVideo():
            break
        mon.waitForAbort(0.5)
    xbmc.executebuiltin("ActivateWindow(fullscreenvideo)")
    mon.waitForAbort(4)
    xbmc.executebuiltin("Seek(20)")
    mon.waitForAbort(0.8)
    log(f"fsback: after seek seeking={cond('Player.Seeking')} recent={cond('Player.HasPerformedSeek(3)')} seekbar={cond('Window.IsVisible(seekbar)')}")
    shot("fsback-seek")
    xbmc.executebuiltin("RunScript(special://skin/scripts/fsback.py)")
    mon.waitForAbort(1.5)
    log(f"fsback: back after a seek -> playing={pl.isPlayingVideo()}")
    xbmc.executebuiltin("PlayerControl(Forward)")
    mon.waitForAbort(1.5)
    log(f"fsback: forwarding={cond('Player.Forwarding')} speed={lab('Player.PlaySpeed')}")
    xbmc.executebuiltin("RunScript(special://skin/scripts/fsback.py)")
    mon.waitForAbort(1.5)
    log(f"fsback: back while fast forward -> playing={pl.isPlayingVideo()} forwarding={cond('Player.Forwarding')} speed={lab('Player.PlaySpeed')}")
    mon.waitForAbort(4)
    xbmc.executebuiltin("RunScript(special://skin/scripts/fsback.py)")
    mon.waitForAbort(2.5)
    log(f"fsback: back while just watching -> playing={pl.isPlayingVideo()}")
    if pl.isPlaying():
        pl.stop()
    # the name and count above lists
    xbmc.executebuiltin("ActivateWindow(Videos,videodb://movies/titles/,return)")
    mon.waitForAbort(3)
    shot("topbar-on")
    xbmc.executebuiltin("Skin.SetBool(lucent.hidetopbar)")
    mon.waitForAbort(1.5)
    shot("topbar-off")
    log(f"topbar: hidden={cond('Skin.HasSetting(lucent.hidetopbar)')} folder={lab('Container.FolderName')}")
    xbmc.executebuiltin("Skin.Reset(lucent.hidetopbar)")
    xbmc.executebuiltin("ActivateWindow(home)")
    mon.waitForAbort(2)


def omdb_test():
    """1.34.4: OMDb scores on the info page (fake OMDb on 127.0.0.1:8765/omdb)."""
    import sys as _s
    _s.path.insert(0, xbmcvfs.translatePath("special://skin/scripts"))
    d = xbmcvfs.translatePath("special://profile/addon_data/skin.lucent/")
    os.makedirs(d, exist_ok=True)
    with open(os.path.join(d, "omdb.key"), "w") as fh:
        fh.write("cikey1234")
    res = json.loads(xbmc.executeJSONRPC(json.dumps({"jsonrpc": "2.0", "id": 1, "method": "VideoLibrary.GetMovies", "params": {"properties": ["title"]}})))
    movies = (res.get("result") or {}).get("movies") or []
    log(f"omdb: movies {[(m['movieid'], m['title']) for m in movies][:3]}")
    if not movies:
        return
    mid = movies[0]["movieid"]
    xbmc.executeJSONRPC(json.dumps({"jsonrpc": "2.0", "id": 1, "method": "VideoLibrary.SetMovieDetails",
                                    "params": {"movieid": mid, "uniqueid": {"imdb": "tt0185937"}}}))
    xbmc.executebuiltin("ActivateWindow(Videos,videodb://movies/titles/,return)")
    mon.waitForAbort(3)
    for _ in range(4):
        if lab("ListItem.DBType") == "movie":
            break
        key("Down")
        mon.waitForAbort(1)
    xbmc.executebuiltin("Action(Info)")
    for _ in range(20):
        if cond("Window.IsActive(movieinformation)"):
            break
        mon.waitForAbort(0.5)
    mon.waitForAbort(4)
    p = {k: HOME.getProperty("lucent.omdb." + k) for k in ("imdb", "votes", "rt", "rtc", "mc", "mcc", "for")}
    log(f"omdb: page={cond('Window.IsActive(movieinformation)')} item={lab('ListItem.Title')} imdb={lab('ListItem.UniqueID(imdb)')} props={p}")
    shot("omdb-page")
    xbmc.executebuiltin("Skin.SetBool(lucent.rate.hide.rt)")
    xbmc.executebuiltin("Skin.SetBool(lucent.rate.votes)")
    mon.waitForAbort(1.5)
    shot("omdb-page-choice")
    xbmc.executebuiltin("Skin.Reset(lucent.rate.hide.rt)")
    xbmc.executebuiltin("Skin.Reset(lucent.rate.votes)")
    xbmc.executebuiltin("Dialog.Close(all,true)")
    mon.waitForAbort(1)
    import omdb as _o
    cache = os.path.exists(xbmcvfs.translatePath(_o.CACHE))
    with open(os.path.join(d, "omdb.key"), "w") as fh:
        fh.write("badkey")
    try:
        bad = _o.ask("tt0185937", "badkey").get("Error")
    except Exception as e:  # noqa: BLE001
        bad = repr(e)
    log(f"omdb: cache={cache} badkey={bad} votes_short={_o.short_votes('282345')},{_o.short_votes('1234567')}")
    os.remove(os.path.join(d, "omdb.key"))
    xbmc.executebuiltin("ActivateWindow(home)")
    mon.waitForAbort(2)


def _dir_guarded(path, wait=20):
    """Files.GetDirectory in a thread; a modal dialog that pops up meanwhile is noted and closed (it would block Kodi)."""
    import threading
    box = {}
    def run():
        box["res"] = json.loads(xbmc.executeJSONRPC(json.dumps({"jsonrpc": "2.0", "id": 1, "method": "Files.GetDirectory",
                                "params": {"directory": path, "media": "files"}})))
    th = threading.Thread(target=run, daemon=True)
    th.start()
    dialog = ""
    t0 = time.time()
    while th.is_alive() and time.time() - t0 < wait:
        mon.waitForAbort(0.5)
        if cond("System.HasModalDialog | Window.IsActive(okdialog) | Window.IsActive(yesnodialog) | Window.IsActive(selectdialog)"):
            dialog = dialog or (lab("Control.GetLabel(9)") or lab("System.CurrentWindow"))
            xbmc.executebuiltin("Dialog.Close(all,true)")
    res = box.get("res") or {}
    files = (res.get("result") or {}).get("files")
    return {"n": len(files) if files is not None else None, "labels": [f.get("label") for f in files or []][:12],
            "paths": [f.get("file", "") for f in files or []][:20], "dialog": dialog, "error": str(res.get("error"))[:80] if res.get("error") else ""}


def letters_test():
    """The alphabet bar under the poster row (view 51): each letter jumps to the first title with it."""
    out = {}
    try:
        xbmc.executebuiltin("ActivateWindow(Videos,plugin://plugin.video.fakefen/?mode=letters,return)")
        for _ in range(40):
            if cond("Window.IsActive(videos) + Integer.IsGreater(Container.NumItems,20)"):
                break
            time.sleep(0.5)
        xbmc.executebuiltin("Container.SetSortMethod(7)")
        time.sleep(1)
        xbmc.executebuiltin("Container.SetViewMode(51)")
        time.sleep(2)
        out["view"] = lab("Container.ViewMode")
        out["n"] = lab("Container(51).NumItems")
        out["abs_sortletter_5"] = lab("Container(51).ListItemAbsolute(5).SortLetter")
        for letter in ("C", "M", "T", "B", "W", "#"):
            xbmc.executebuiltin(f"RunScript(special://skin/scripts/letters.py,51,{letter})")
            time.sleep(2.5)
            out[letter] = lab("Container(51).ListItem.Label")
        shot("letters-T")
    except Exception as error:  # noqa: BLE001
        out["error"] = repr(error)
    log("letters: " + json.dumps(out))
    xbmc.executebuiltin("ActivateWindow(home)")
    time.sleep(1)


def lucentvideo_test():
    """the video add-on 0.21.0 (plugin.video.lucent): installs, its menus answer (without a TMDB key: a dialog, closed here)."""
    log(f"lucentvideo: addon={cond('System.HasAddon(plugin.video.lucent)')} version={lab('System.AddonVersion(plugin.video.lucent)')}")
    out = {"root": _dir_guarded("plugin://plugin.video.lucent/")}
    out["tools"] = _dir_guarded("plugin://plugin.video.lucent/?action=tools")
    out["service_row"] = _dir_guarded("plugin://plugin.video.lucent/?action=list&name=service_row&widget=1", 15)
    for nm in ("calendar", "foryou", "person&id=287", "trending_movie", "upcoming_movie", "upcoming_tv", "new_tv", "alerts"):
        out["row_" + nm] = _dir_guarded("plugin://plugin.video.lucent/?action=list&widget=1&name=" + nm, 15)
    try:
        import sys as _s
        _s.path.insert(0, xbmcvfs.translatePath("special://skin/scripts"))
        import menu as _menu
        out["menu"] = {"has_lv": _menu.has_lv(), "rows": len(_menu.WIDGETS_LV), "names": [r[1].split("name=")[1] for r in _menu.WIDGETS_LV]}
        out["lvmap"] = {p: _menu.lv_path(p) for p in ("plugin://plugin.video.seren/?action=showsNextUp",
                         "plugin://plugin.video.seren/?action=genericEndpoint&mediatype=shows&endpoint=anticipated",
                         "plugin://plugin.video.seren/?action=moviesUpdated", "plugin://script.lucent.library/?action=providers",
                         "plugin://script.lucent.library/?action=tmdb&list=prov_8_newtv", "videodb://movies/titles/")}
        out["libmap"] = {p: _menu.lv_path(p, True, True) for p in ("plugin://script.lucent.library/?action=lib&kind=continue&only=movie",
                         "plugin://script.lucent.library/?action=lib&kind=nextup", "plugin://script.lucent.library/?action=tmdb&list=trakt_watchlist_tv",
                         "plugin://script.lucent.library/?action=tmdb&list=toprated_tv", "plugin://script.lucent.library/?action=providers")}
        _tabs = _menu.lv_tabs()[0]
        out["lvtabs"] = [[tb["action"], [w["path"].split("name=")[-1] for w in tb["widgets"]]] for tb in _tabs[:5]]
        out["use_lv"] = _menu.use_lv()
    except Exception as _e:  # noqa: BLE001
        out["menu"] = repr(_e)
    log("lucentvideo: " + json.dumps(out))
    xbmc.executebuiltin("Addon.OpenSettings(plugin.video.lucent)")
    mon.waitForAbort(3)
    shot("lucentvideo-settings")
    xbmc.executebuiltin("Dialog.Close(all,true)")
    xbmc.executebuiltin("ActivateWindow(home)")
    mon.waitForAbort(2)
    try:
        with open(xbmcvfs.translatePath("special://logpath/kodi.log"), encoding="utf-8", errors="replace") as fh:
            lines = [ln for ln in fh if "plugin.video.lucent" in ln or "lucent-video" in ln.lower()]
        errs = [ln.strip()[24:200] for ln in lines if " error " in ln.lower() or "Traceback" in ln]
        secrets = [ln.strip()[24:120] for ln in lines if "api_key=" in ln or "Authorization" in ln]
        log(f"lucentvideo: log lines={len(lines)} errors={len(errs)} secrets={len(secrets)} {json.dumps(errs[:6])}")
    except OSError as e:
        log(f"lucentvideo: log {e}")


def nolib_test():
    """1.36.0: the skin without Lucent Library (switched off here, only in the 'new' run): menus, setup step, diag."""
    if not TAG.startswith("new"):
        return
    xbmc.executeJSONRPC(json.dumps({"jsonrpc": "2.0", "id": 1, "method": "Addons.SetAddonEnabled",
                                    "params": {"addonid": "script.lucent.library", "enabled": False}}))
    mon.waitForAbort(3)
    out = {"has_lib": cond("System.HasAddon(script.lucent.library)"), "skin": lab("System.AddonVersion(skin.lucent)")}
    try:
        import sys as _s
        import importlib
        _s.path.insert(0, xbmcvfs.translatePath("special://skin/scripts"))
        import menu as _menu
        importlib.reload(_menu)
        out["menu_has_lib"] = _menu.has_lib()
        out["lib_rows"] = [r[1] for r in _menu.WIDGETS_LIBRARY if _menu.has_lib() or not r[1].startswith("plugin://script.lucent.library/")][:4]
        out["lv_new_rows"] = [r[1].split("name=")[1] for r in _menu.WIDGETS_LV][-7:]
        import setup as _setup
        importlib.reload(_setup)
        out["setup"] = [_setup.st_library(), [a[0] for a in _setup.ac_library()]]
        import diag as _diag
        out["diag_optional"] = [_diag.addon_state(a) for a in ("plugin.video.lucent", "script.lucent.library")]
        import libtools as _lt
        out["libtools"] = [callable(_lt.surprise), callable(_lt.next_in_set)]
    except SystemExit:
        pass
    except Exception as _e:  # noqa: BLE001
        out["error"] = repr(_e)
    xbmc.executebuiltin("Dialog.Close(all,true)")
    xbmc.executebuiltin("ActivateWindow(Videos,videodb://movies/titles/,return)")
    mon.waitForAbort(4)
    out["side_visible"] = cond("String.StartsWith(Container.FolderPath,videodb://)")
    shot("nolib-movies")
    xbmc.executebuiltin("ActivateWindow(home)")
    mon.waitForAbort(3)
    shot("nolib-home")
    log("nolib: " + json.dumps(out))


def infobuttons_test():
    """1.37.0: Library and lists / Mark as watched work with the video add-on, also for titles of other video add-ons."""
    out = {}
    try:
        import sys as _s
        import importlib
        _s.path.insert(0, xbmcvfs.translatePath("special://skin/scripts"))
        import info as _i
        importlib.reload(_i)
        xbmc.executebuiltin("ActivateWindow(Videos,plugin://plugin.video.fakefen/?mode=list,return)")
        for _ in range(30):
            if cond("Window.IsActive(videos) + Integer.IsGreater(Container.NumItems,0) + String.IsEqual(ListItem.DBType,episode)"):
                break
            mon.waitForAbort(0.5)
        out["item"] = [lab("ListItem.Label"), lab("ListItem.DBType"), lab("ListItem.UniqueID(tmdb)")]
        out["seren_login"] = _i.seren_login()
        out["use_lv"] = _i.use_lv()
        out["target"] = _i.lv_target()
        out["lv_version"] = list(_i.lv_version())
        out["lists_by_lv"] = _i.lv_version() >= _i.LV_LISTS      # False until the video add-on has action=lists
        out["play_movie"] = _i.lv_play_url("movie", 603)
        out["play_tv"] = _i.lv_play_url("tv", 1399)
        HOME_ = xbmcgui.Window(10000)
        HOME_.clearProperty("nuvio.info.watched")
        out["fen_light"] = _i.fen_light_id()                 # the stand-in is a Fen Light clone: toggle_watched lets Fen mark it
        _i.lv_watched()                                      # so call the the video add-on route itself
        mon.waitForAbort(10)
        out["prop_after"] = HOME_.getProperty("nuvio.info.watched")
        try:
            with open(xbmcvfs.translatePath("special://logpath/kodi.log"), encoding="utf-8", errors="replace") as fh:
                out["lv_log_marked"] = any("marked episode 1399 watched" in ln for ln in fh)
        except OSError:
            out["lv_log_marked"] = None
        _i.lv_menu()                                         # 'More': the video add-on's menu with all options
        for _ in range(20):
            if cond("Window.IsActive(contextmenu)"):
                break
            mon.waitForAbort(0.5)
        out["more_menu"] = cond("Window.IsActive(contextmenu)")
        shot("info-more-menu")
        xbmc.executebuiltin("Dialog.Close(contextmenu,true)")
        mon.waitForAbort(1)
        seen = ""
        base = xbmcvfs.translatePath("special://profile/addon_data/plugin.video.lucent/")
        for root, _d, files in os.walk(base):
            if "watched.json" in files:
                with open(os.path.join(root, "watched.json"), encoding="utf-8") as fh:
                    seen += fh.read()
        out["lv_seen_1399_2_3"] = '"1399"' in seen and '"2:3"' in seen
        xbmc.executebuiltin("Dialog.Close(all,true)")
    except Exception as _e:  # noqa: BLE001
        out["error"] = repr(_e)
    log("infobuttons: " + json.dumps(out))
    xbmc.executebuiltin("ActivateWindow(home)")
    mon.waitForAbort(2)


def progress_colour_test():
    """1.38.1: percentage from WatchedProgress (Fen Light / Red Light, issue #7) and the colour of the watched check (#10)."""
    out = {}
    try:
        xbmc.executebuiltin("ActivateWindow(Videos,plugin://plugin.video.fakefen/?mode=progress,return)")
        for _ in range(30):
            if cond("Window.IsActive(videos) + Integer.IsGreater(Container.NumItems,0) + String.IsEqual(ListItem.Label,Half Film)"):
                break
            mon.waitForAbort(0.5)
        xbmc.executebuiltin("Container.SetViewMode(51)")
        mon.waitForAbort(2)
        out["kodi_pct"] = lab("ListItem.PercentPlayed")
        out["prop"] = lab("ListItem.Property(WatchedProgress)")
        out["pct_var"] = lab("$VAR[LucentPct]")
        out["show"] = cond("[Integer.IsGreater(ListItem.PercentPlayed,0) | Integer.IsGreater(ListItem.Property(WatchedProgress),0)]")
        shot("progress-redlight")
        xbmc.executebuiltin("Skin.SetString(lucent.watched.colour,graphite)")
        mon.waitForAbort(1)
        out["colour_graphite"] = lab("$VAR[LucentWatchedColour]")
        xbmc.executebuiltin("Skin.SetString(lucent.watched.colour,)")
        mon.waitForAbort(1)
        out["colour_default"] = lab("$VAR[LucentWatchedColour]")
    except Exception as _e:  # noqa: BLE001
        out["error"] = repr(_e)
    log("progress: " + json.dumps(out))
    xbmc.executebuiltin("ActivateWindow(home)")
    mon.waitForAbort(2)


def formatclips_test():
    """the video add-on's format check: do its clips start in Kodi (windowed, like the check does)?"""
    out = {}
    base = xbmcvfs.translatePath("special://home/addons/plugin.video.lucent/resources/formattest/")
    player = xbmc.Player()
    for name in ("hevc4k.mp4", "ddplus.mkv", "vp9.webm", "dv81.mp4"):
        path = os.path.join(base, name)
        res = {"exists": os.path.exists(path)}
        try:
            player.play(path, xbmcgui.ListItem(name, path=path), windowed=True)
            started = False
            for _ in range(100):
                if mon.waitForAbort(0.1):
                    break
                if player.isPlayingVideo() and player.getTime() > 0.2:
                    started = True
                    break
            res.update(started=started, hdr=lab("VideoPlayer.HdrType"), codec=lab("VideoPlayer.VideoCodec"))
        except Exception as _e:  # noqa: BLE001
            res["error"] = repr(_e)
        player.stop()
        mon.waitForAbort(1.5)
        out[name] = res
    try:
        with open(xbmcvfs.translatePath("special://logpath/kodi.log"), encoding="utf-8", errors="replace") as fh:
            out["errors"] = [ln.strip()[24:200] for ln in fh if "formattest" in ln and (" error " in ln.lower() or "warning" in ln.lower())][:8]
    except OSError:
        pass
    log("formatclips: " + json.dumps(out))


def trailerlayer_test():
    """1.38.3: poster trailers on Home: trailer window, hero media and the expanded card (an overlay over the row)."""
    out = {}
    base = xbmcvfs.translatePath("special://home/addons/plugin.video.lucent/resources/formattest/")
    path = os.path.join(base, "hevc4k.mp4")
    player = xbmc.Player()
    xbmc.executebuiltin("Dialog.Close(all,true)")
    mon.waitForAbort(1)
    xbmc.executebuiltin("Skin.SetBool(nuvio.trailers.menu)")
    full = cond("Skin.HasSetting(nuvio.fullbackdrop)")
    xbmc.executebuiltin("Skin.Reset(nuvio.fullbackdrop)")         # 1.38.6: the soft edge of the picture at the top right
    xbmc.executebuiltin("ActivateWindow(home)")
    mon.waitForAbort(2)
    xbmc.executebuiltin("SetFocus(8101)")
    mon.waitForAbort(2)
    shot("home-picture-edge")
    if full:
        xbmc.executebuiltin("Skin.SetBool(nuvio.fullbackdrop)")
    for mode in ("expand", "window", "hero"):
        xbmc.executebuiltin(f"Skin.SetString(nuvio.posterfocus,{mode})")
        xbmc.executebuiltin("ActivateWindow(home)")
        mon.waitForAbort(2)
        xbmc.executebuiltin("SetFocus(8101)")
        mon.waitForAbort(1)
        if mode == "expand":
            shot("home-expand-card")
        player.play(path, xbmcgui.ListItem("trailer", path=path), windowed=True)
        for _ in range(60):
            if mon.waitForAbort(0.1) or player.isPlayingVideo():
                break
        xbmc.executebuiltin("SetProperty(nuvio.trailer.playing,1,home)")
        mon.waitForAbort(0.8)
        out[mode] = {"home": cond("Window.IsActive(home)"), "playing": cond("Player.HasVideo"),
                     "focus8101": cond("Control.HasFocus(8101)"), "fullscreen": cond("Window.IsActive(fullscreenvideo)")}
        shot(f"home-trailer-{mode}")
        player.stop()
        xbmc.executebuiltin("ClearProperty(nuvio.trailer.playing,home)")
        mon.waitForAbort(1.5)
    xbmc.executebuiltin("Skin.Reset(nuvio.posterfocus)")
    log("trailerlayer: " + json.dumps(out))
    # Go to playlist in the side menu of a list (issue #11)
    r = json.loads(xbmc.executeJSONRPC(json.dumps({"jsonrpc": "2.0", "id": 1, "method": "VideoLibrary.GetMovies"})))
    mv = ((r.get("result") or {}).get("movies") or [{}])[0].get("movieid")
    if mv:
        xbmc.executeJSONRPC(json.dumps({"jsonrpc": "2.0", "id": 1, "method": "Playlist.Add", "params": {"playlistid": 1, "item": {"movieid": mv}}}))
    xbmc.executebuiltin("Dialog.Close(all,true)")
    xbmc.executebuiltin("ActivateWindow(Videos,videodb://movies/titles/,return)")
    mon.waitForAbort(3)
    xbmc.executebuiltin("SetFocus(9070)")
    mon.waitForAbort(1)
    log(f"playlist: len={lab('Playlist.Length(video)')} visible={cond('Control.IsVisible(9070)')} focus={cond('Control.HasFocus(9070)')}")
    shot("playlist-sidemenu")
    xbmc.executebuiltin("Action(Select)")
    mon.waitForAbort(3)
    log(f"playlist: after click window={xbmcgui.getCurrentWindowId()} playlistwin={cond('Window.IsActive(videoplaylist)')} 10028={cond('Window.IsActive(10028)')}")
    shot("playlist-after-click")
    xbmc.executeJSONRPC(json.dumps({"jsonrpc": "2.0", "id": 1, "method": "Playlist.Clear", "params": {"playlistid": 1}}))
    xbmc.executebuiltin("ActivateWindow(home)")
    mon.waitForAbort(2)


def addonsettings_test():
    """1.40.0: add-on settings in three columns, with the group tiles and picture for the video add-on."""
    xbmc.executebuiltin("Dialog.Close(all,true)")
    xbmc.executebuiltin("ActivateWindow(home)")
    mon.waitForAbort(1)
    for addon in ("plugin.video.lucent", "service.subtitles.lucent"):
        xbmc.executebuiltin(f"Addon.OpenSettings({addon})")
        for _ in range(40):
            if mon.waitForAbort(0.1) or xbmcgui.getCurrentWindowDialogId() == 10140:
                break
        mon.waitForAbort(2)
        tag = "lv" if "lucent" in addon and "video" in addon else "other"
        log(f"addonsettings {tag}: open={xbmcgui.getCurrentWindowDialogId() == 10140} heading={lab('Control.GetLabel(2)')!r} "
            f"count={HOME.getProperty('lucent.as.count')!r} "
            f"cat={HOME.getProperty('lucent.as.cat')!r} lvexp={cond('$EXP[LucentAddonSettingsLV]')} asl={HOME.getProperty('lucent.as.lv')!r}")
        shot(f"addonsettings-{tag}")
        if tag == "lv":
            xbmc.executebuiltin("SetFocus(3)")
            mon.waitForAbort(1)
            ids = []
            for _ in range(4):
                fid = xbmcgui.Window(10140).getFocusId()
                ids.append((fid, lab(f"Control.GetLabel({fid})"), cond(f"Control.IsVisible({fid})"), cond(f"Control.HasFocus({fid})")))
                xbmc.executebuiltin("Action(Down)")
                mon.waitForAbort(1.5)
            log(f"addonsettings lv category ids: {ids} cat={HOME.getProperty('lucent.as.cat')!r} current={lab('System.CurrentControl')!r}")
            shot("addonsettings-lv-play")
            xbmc.executebuiltin("SetFocus(5)")
            mon.waitForAbort(2)
            shot("addonsettings-lv-setting")
        xbmc.executebuiltin("Action(Back)")
        mon.waitForAbort(2)
        if xbmcgui.getCurrentWindowDialogId() == 10140:
            xbmc.executebuiltin("Dialog.Close(addonsettings,true)")
            mon.waitForAbort(1)


def osdclose_test():
    """1.40.2: the player menu closes by itself while a video plays (issue #4)."""
    out = {}
    xbmc.executebuiltin("Dialog.Close(all,true)")
    xbmc.executebuiltin("Skin.SetString(lucent.osdclose,3)")
    xbmc.Player().play("/tmp/ci/test.mkv")
    for _ in range(60):
        if mon.waitForAbort(0.2) or cond("Player.HasVideo"):
            break
    mon.waitForAbort(2)
    xbmc.executebuiltin("ActivateWindow(videoosd)")
    mon.waitForAbort(1)
    out["open"] = cond("Window.IsActive(videoosd)")
    mon.waitForAbort(6)
    out["closed_after_6s"] = not cond("Window.IsActive(videoosd)")
    xbmc.executebuiltin("Skin.Reset(lucent.osdclose)")
    xbmc.executebuiltin("ActivateWindow(videoosd)")
    mon.waitForAbort(6)
    out["stays_when_off"] = cond("Window.IsActive(videoosd)")
    xbmc.executebuiltin("Dialog.Close(all,true)")
    xbmc.Player().stop()
    mon.waitForAbort(2)
    xbmc.executebuiltin("ActivateWindow(home)")
    mon.waitForAbort(1)
    log("osdclose: " + json.dumps(out))


def osdintro_test():
    """2.0.1: 'Mark intro' in the player menu when the video add-on knows action=intro_mark."""
    out = {}
    xbmc.executebuiltin("Dialog.Close(all,true)")
    HOME.setProperty("lucent.lv.intromark", "1")
    HOME.setProperty("lucent.lv.replay", "1")
    xbmc.Player().play("/tmp/ci/test.mkv")
    for _ in range(60):
        if mon.waitForAbort(0.2) or cond("Player.HasVideo"):
            break
    mon.waitForAbort(2)
    xbmc.executebuiltin("ActivateWindow(videoosd)")
    mon.waitForAbort(1.5)
    out["button"] = cond("Control.IsVisible(121)")
    xbmc.executebuiltin("SetFocus(121)")
    mon.waitForAbort(1)
    out["focus"] = cond("Control.HasFocus(121)")
    shot("osd-intromark")
    xbmc.executebuiltin("Dialog.Close(all,true)")
    xbmc.Player().stop()
    mon.waitForAbort(2)
    xbmc.executebuiltin("ActivateWindow(home)")
    mon.waitForAbort(1)
    log("osdintro: " + json.dumps(out))


def _alive(seconds=20):
    """Does Kodi still answer? Asked from another thread, so a stuck Kodi does not stop this driver."""
    import threading
    box = {}
    def probe():
        box["v"] = xbmc.getInfoLabel("System.Time")
    th = threading.Thread(target=probe, daemon=True)
    th.start()
    th.join(seconds)
    return "v" in box


def _setup_look():
    xbmc.executebuiltin("RunScript(special://skin/scripts/setup.py)")
    for _ in range(40):
        if mon.waitForAbort(0.3) or cond("Window.IsVisible(Lucent_Setup.xml)"):
            break
    mon.waitForAbort(1.5)
    n = int(lab("Container(100).NumItems") or 0)
    for i in range(n):
        if lab(f"Container(100).ListItemAbsolute({i}).Label") in ("Look", "Weergave"):
            xbmc.executebuiltin(f"SetFocus(100,{i},absolute)")
            mon.waitForAbort(0.5)
            xbmc.executebuiltin("Action(Select)")
            mon.waitForAbort(1.5)
            return True
    return False


def litesetup_test():
    """Reddit: light mode switched on in the setup assistant hung Kodi. Now the skin reloads after the assistant closes."""
    out = {}
    xbmc.executebuiltin("Dialog.Close(all,true)")
    xbmc.executebuiltin("ActivateWindow(home)")
    mon.waitForAbort(1)
    out["look_step"] = _setup_look()
    out["button"] = lab("Control.GetLabel(301)")
    shot("lite-setup-before")
    xbmc.executebuiltin("SetFocus(301)")
    mon.waitForAbort(0.5)
    xbmc.executebuiltin("Action(Select)")
    mon.waitForAbort(3)
    out["alive_in_setup"] = _alive()
    out["setup_open"] = cond("Window.IsVisible(Lucent_Setup.xml)")
    out["button_after"] = lab("Control.GetLabel(301)")
    shot("lite-setup-after")
    log("litesetup step1: " + json.dumps(out))
    xbmc.executebuiltin("Action(Back)")
    mon.waitForAbort(12)
    out["alive_after_close"] = _alive()
    out["lite"] = cond("Skin.HasSetting(lucent.lite)")
    out["built"] = lab("Skin.String(lucent.lite.built)")
    xbmc.executebuiltin("ActivateWindow(home)")
    mon.waitForAbort(6)
    out["home"] = cond("Window.IsActive(home)")
    out["row1_items"] = lab("Container(8101).NumItems")
    out["visible_rows"] = [i for i in range(8101, 8111) if cond(f"Control.IsVisible({i})")]
    shot("lite-home")
    log("litesetup: " + json.dumps(out))
    xbmc.executebuiltin("Skin.Reset(lucent.lite)")             # back to normal for the old-path test
    xbmc.executebuiltin("RunScript(special://skin/scripts/settings.py,litebuild)")
    mon.waitForAbort(10)


def liteold_test():
    """The old way (reload while the assistant is open), to see whether that is what hung Kodi. Runs last."""
    out = {}
    xbmc.executebuiltin("Dialog.Close(all,true)")
    out["look_step"] = _setup_look()
    xbmc.executebuiltin("Skin.ToggleSetting(lucent.lite)")
    xbmc.sleep(400)
    xbmc.executebuiltin("RunScript(special://skin/scripts/settings.py,litebuild)")
    mon.waitForAbort(15)
    out["alive"] = _alive(30)
    log("liteold: " + json.dumps(out))
    if out["alive"]:
        shot("lite-old")


def cwrow_test():
    """2.0.1: one 'Continue watching' row from the library: in progress (film, episode) + next episode of a series."""
    out = {}
    xbmc.executebuiltin("Dialog.Close(all,true)")
    xbmc.executebuiltin("Skin.SetBool(lucent.cw.on)")
    xbmc.executebuiltin("RunScript(special://skin/scripts/continuerow.py)")
    for _ in range(30):
        if mon.waitForAbort(0.5) or HOME.getProperty("lucent.cw.count"):
            break
    out["count"] = HOME.getProperty("lucent.cw.count")
    out["items"] = [(HOME.getProperty(f"lucent.cw.{n}.type"), HOME.getProperty(f"lucent.cw.{n}.title"),
                     HOME.getProperty(f"lucent.cw.{n}.sub"), HOME.getProperty(f"lucent.cw.{n}.percent"))
                    for n in range(1, int(out["count"] or 0) + 1)]
    xbmc.executebuiltin("ActivateWindow(home)")
    mon.waitForAbort(2)
    xbmc.executebuiltin("Dialog.Close(all,true)")          # the video add-on can ask something at start (skip intro)
    mon.waitForAbort(1)
    xbmc.executebuiltin("SetFocus(8092)")
    mon.waitForAbort(2)
    out["row_visible"] = cond("Control.IsVisible(8092)")
    out["focus"] = cond("Control.HasFocus(8092)")
    out["list_items"] = lab("Container(8092).NumItems")
    shot("cw-row")
    for tab, name, rename in ((1, "films", ""), (2, "streaming", ""), (2, "series", "Series"), (0, "home", "")):
        if rename:
            xbmc.executebuiltin("Control.SetFocus(9000,0)")
            xbmc.executebuiltin(f"Skin.SetString(nuvio.tab3.label,{rename})")
            mon.waitForAbort(2.5)
        xbmc.executebuiltin(f"Control.SetFocus(9000,{tab})")
        mon.waitForAbort(3.5)
        out[f"tab_{name}"] = [lab("Container(9000).ListItem.Label"), HOME.getProperty("lucent.cw.kind"),
                              cond("Control.IsVisible(8092)"), HOME.getProperty("lucent.cw.show"),
                              HOME.getProperty("lucent.cw.count"), HOME.getProperty("lucent.cw.1.title")]
        shot(f"cw-tab-{name}")
    xbmc.executebuiltin("Skin.SetString(nuvio.tab3.label,Streaming)")
    xbmc.executebuiltin("Control.SetFocus(9000,1)")
    mon.waitForAbort(3.5)
    xbmc.executebuiltin("SetFocus(8092)")
    mon.waitForAbort(1)
    xbmc.executebuiltin("Action(Right)")
    mon.waitForAbort(1.5)
    shot("cw-row-2")
    # the calendar button is not on the info page of a film in the library
    xbmc.executebuiltin("ActivateWindow(Videos,videodb://movies/titles/,return)")
    for _ in range(20):
        if mon.waitForAbort(0.5) or int(lab("Container.NumItems") or 0) > 0:
            break
    n = int(lab("Container.NumItems") or 0)
    for i in range(n + 1):
        if lab(f"Container.ListItemAbsolute({i}).Label") == "Lib Film":
            xbmc.executebuiltin(f"SetFocus(50,{i},absolute)")
            xbmc.executebuiltin(f"SetFocus(51,{i},absolute)")
    mon.waitForAbort(1)
    xbmc.executebuiltin("Action(Info)")
    for _ in range(20):
        if mon.waitForAbort(0.5) or cond("Window.IsVisible(movieinformation)"):
            break
    mon.waitForAbort(2)
    out["info_title"] = lab("ListItem.Title")
    out["info_dbid"] = lab("ListItem.DBID")
    out["bell_button"] = cond("Control.IsVisible(23)")
    out["more_button"] = cond("Control.IsVisible(25)")
    out["lv_version"] = lab("System.AddonVersion(plugin.video.lucent)")
    try:
        import sys as _s
        _s.path.insert(0, xbmcvfs.translatePath("special://skin/scripts/"))
        import importlib
        import info as _i
        importlib.reload(_i)
        out["lv_version_parsed"] = list(_i.lv_version())
    except Exception as error:  # noqa: BLE001
        out["lv_version_parsed"] = str(error)
    shot("cw-info-libfilm")
    xbmc.executebuiltin("Dialog.Close(all,true)")
    xbmc.executebuiltin("ActivateWindow(home)")
    mon.waitForAbort(1)
    log("cwrow: " + json.dumps(out))


def perf_test():
    """Speed and memory (lucent-performance): Kodi's memory on Home, after opening windows and after 2 minutes idle;
    how long Kodi ran before Home was ready; how many scripts were started and how many log errors there are."""
    import re as _re
    out = {}
    def rss():
        try:
            for ln in open("/proc/self/status"):
                if ln.startswith("VmRSS:"):
                    return int(ln.split()[1]) // 1024
        except OSError:
            return -1
    def uptime():
        try:
            ticks = os.sysconf(os.sysconf_names["SC_CLK_TCK"])
            start = int(open("/proc/self/stat").read().rsplit(")", 1)[1].split()[19]) / ticks
            return round(float(open("/proc/uptime").read().split()[0]) - start, 1)
        except Exception:  # noqa: BLE001
            return -1
    out["kodi_seconds_at_home_ready"] = HOME_READY.get("uptime")
    xbmc.executebuiltin("Dialog.Close(all,true)")
    xbmc.executebuiltin("ActivateWindow(home)")
    mon.waitForAbort(5)
    out["mb_home"] = rss()
    for win in ("Videos,videodb://movies/titles/,return", "Settings", "SkinSettings", "home"):
        xbmc.executebuiltin(f"ActivateWindow({win})")
        mon.waitForAbort(4)
    out["mb_after_windows"] = rss()
    xbmc.executebuiltin("ActivateWindow(home)")
    mon.waitForAbort(120)
    out["mb_after_2min_idle"] = rss()
    out["kodi_seconds_total"] = uptime()
    try:
        with open(xbmcvfs.translatePath("special://logpath/kodi.log"), encoding="utf-8", errors="replace") as fh:
            text = fh.read()
        starts = [ln for ln in text.splitlines() if "CPythonInvoker" in ln and "the source file to load is" in ln]
        out["scripts_started"] = len(starts)
        out["skin_scripts_started"] = len([ln for ln in starts if "special://skin/" in ln or "skin.lucent" in ln])
        names = {}
        for ln in starts:
            m = _re.search(r"scripts/(\w+)\.py", ln)
            if m:
                names[m.group(1)] = names.get(m.group(1), 0) + 1
        out["per_script"] = dict(sorted(names.items(), key=lambda kv: -kv[1])[:12])
        out["unknown_addon_id"] = text.count("Unknown addon id")
        out["parse_errors"] = text.count("Error parsing boolean expression")
        out["log_errors"] = len([ln for ln in text.splitlines() if " error <" in ln])
    except OSError as error:
        out["log"] = str(error)
    log("perf: " + json.dumps(out))


def firststart_test():
    """Speed point 1: a new installation runs its one-time jobs one after the other in startup.py (not 6 scripts from Home)."""
    import importlib
    import sys as _s
    _s.path.insert(0, xbmcvfs.translatePath("special://skin/scripts/"))
    out = {}
    try:
        text = open(xbmcvfs.translatePath("special://logpath/kodi.log"), encoding="utf-8", errors="replace").read()
        starts = [ln for ln in text.splitlines() if "the source file to load is" in ln and "skin/scripts/" in ln]
        out["home_scripts_at_start"] = sorted({ln.split("skin/scripts/")[1].split(".py")[0] for ln in starts})
    except OSError as error:
        out["log"] = str(error)
    for key in ("lucent.lite.checked", "lucent.addonw4"):
        xbmc.executebuiltin(f"Skin.Reset({key})")
    mon.waitForAbort(1)
    t = time.time()
    try:
        import startup
        importlib.reload(startup)
        out["reload"] = startup.first_start()
    except Exception as error:  # noqa: BLE001
        out["error"] = f"{type(error).__name__}: {error}"
    out["seconds"] = round(time.time() - t, 1)
    out["lite_checked"] = lab("Skin.String(lucent.lite.checked)")
    out["addonw4"] = lab("Skin.String(lucent.addonw4)")
    out["alive"] = bool(lab("System.Time"))
    log("firststart: " + json.dumps(out))


def remember_test():
    """Issue #9: going back into a folder (Films ...) starts on the title you were on."""
    out = {}
    path = "plugin://plugin.video.fakefen/?mode=showcase"
    for rnd in (1, 2):
        xbmc.executebuiltin("Dialog.Close(all,true)")
        xbmc.executebuiltin(f"ActivateWindow(Videos,{path},return)")
        for _ in range(40):
            if mon.waitForAbort(0.3) or int(lab("Container.NumItems") or 0) > 0:
                break
        mon.waitForAbort(2.5)
        out[f"label_{rnd}"] = lab("ListItem.Label")
        if rnd == 1:
            view = xbmcgui.Window(xbmcgui.getCurrentWindowId()).getFocusId()
            for _ in range(5):
                xbmc.executebuiltin("Action(Right)" if cond("Container.Content(movies)") and view in (51, 52, 70, 72) else "Action(Down)")
                mon.waitForAbort(0.4)
            mon.waitForAbort(2)
            out["picked"] = lab("ListItem.Label")
            xbmc.executebuiltin("ActivateWindow(home)")
            mon.waitForAbort(3)
    out["back_on_it"] = out.get("label_2") == out.get("picked")
    shot("remember")
    xbmc.executebuiltin("ActivateWindow(home)")
    mon.waitForAbort(1)
    log("remember: " + json.dumps(out))


def nolv_test():
    """2.1.1: not tied to one video add-on - who plays titles Lucent opens itself, For you only on Home."""
    import importlib
    import sys as _s
    _s.path.insert(0, xbmcvfs.translatePath("special://skin/scripts/"))
    out = {}
    try:
        import info
        importlib.reload(info)
        out["player_with_lv"] = info.title_player()
        out["film_lv"] = info.lv_play_url("movie", 603)
        real = info.lv_on
        info.lv_on = lambda: False
        out["player_without"] = info.title_player()
        out["can_open_without"] = info.lv_open_with()
        info.title_player = lambda: "th"
        out["film_th"] = info.lv_play_url("movie", 603)
        out["show_th"] = info.lv_play_url("tv", 1399)
        out["ep_th"] = info.episode_play_url(1399, 2, 3)
        info.lv_on = real
        importlib.reload(info)
    except Exception as error:  # noqa: BLE001
        out["error"] = f"{type(error).__name__}: {error}"
    for _ in range(40):                                    # the video add-on asks something at start: answer No
        if mon.waitForAbort(0.5):
            break
        if cond("Window.IsVisible(yesnodialog)"):
            xbmc.executebuiltin("Dialog.Close(all,true)")
            mon.waitForAbort(1)
            break
    xbmc.executebuiltin("Dialog.Close(all,true)")
    xbmc.executebuiltin("Skin.SetString(nuvio.tab1.icon,icons/home.png)")
    xbmc.executebuiltin("Skin.Reset(lucent.fy.off)")
    try:
        import foryou
        importlib.reload(foryou)
        out["home_tab"] = foryou.home_tab()
        HOME.setProperty("lucent.fy.tab", foryou.home_tab())
    except Exception as error:  # noqa: BLE001
        out["home_tab"] = str(error)
    HOME.setProperty("lucent.fy.count", "3")
    HOME.setProperty("lucent.fy.label", "Tonight for you")
    for n in (1, 2, 3):
        HOME.setProperty(f"lucent.fy.{n}.title", f"Title {n}")
    xbmc.executebuiltin("ActivateWindow(home)")
    mon.waitForAbort(2)
    for tab in (0, 1):
        xbmc.executebuiltin(f"Control.SetFocus(9000,{tab})")
        mon.waitForAbort(2)
        xbmc.executebuiltin("Dialog.Close(all,true)")
        mon.waitForAbort(0.5)
        out[f"foryou_tab{tab + 1}"] = cond("Control.IsVisible(9989)")
        out[f"icon_tab{tab + 1}"] = lab("Container(9000).ListItem.Icon")
        shot(f"nolv-tab{tab + 1}")
    xbmc.executebuiltin("Skin.SetBool(lucent.fy.off)")
    HOME.clearProperty("lucent.fy.count")
    xbmc.executebuiltin("Skin.SetString(nuvio.tab1.icon,icons/movies.png)")
    xbmc.executebuiltin("ActivateWindow(InterfaceSettings)")
    mon.waitForAbort(3)
    shot("nolv-level")
    xbmc.executebuiltin("ActivateWindow(home)")
    mon.waitForAbort(1)
    log("nolv: " + json.dumps(out))


def mousehome_test():
    """Issue #13: with a mouse, the first posters of a Home row must not open the side menu."""
    import subprocess
    out = {}
    def move(x, y):
        try:
            subprocess.run(["xdotool", "mousemove", str(x), str(y)], timeout=5)
        except Exception as error:  # noqa: BLE001
            log(f"xdotool error {error!r}")
        mon.waitForAbort(1.2)
    xbmc.executeJSONRPC(json.dumps({"jsonrpc": "2.0", "id": 1, "method": "Settings.SetSettingValue",
                                     "params": {"setting": "input.enablemouse", "value": True}}))
    try:
        subprocess.run(["xdotool", "search", "--name", "Kodi", "windowactivate", "--sync"], timeout=5)
    except Exception as error:  # noqa: BLE001
        log(f"xdotool error {error!r}")
    move(900, 300)
    move(910, 310)
    xbmc.executebuiltin("Dialog.Close(all,true)")
    xbmc.executebuiltin("ActivateWindow(home)")
    mon.waitForAbort(2)
    xbmc.executebuiltin("SetFocus(9100)")
    mon.waitForAbort(1.5)
    out["rows_focus"] = not cond("Control.HasFocus(9000)")
    for name, x, y in (("poster1", 250, 820), ("poster2", 380, 820), ("rowtitle", 300, 600),
                       ("band_sport", 300, 640), ("band_cal", 220, 470), ("band_cal_icon", 90, 470)):
        out[name + "_before"] = lab("System.CurrentControlID")
        move(x, y)
        out[name + "_menu"] = cond("Control.HasFocus(9000)")
        out[name + "_after"] = lab("System.CurrentControlID")
        shot(f"mouse-{name}")
        xbmc.executebuiltin("SetFocus(9100)")
        move(1700, 100)
        xbmc.executebuiltin("SetFocus(9100)")
        mon.waitForAbort(0.8)
    move(60, 300)
    out["icon_menu"] = cond("Control.HasFocus(9000)")
    shot("mouse-icon")
    move(260, 300)
    out["label_menu"] = cond("Control.HasFocus(9000)")
    out["label_item"] = lab("Container(9000).ListItem.Label")
    shot("mouse-label")
    move(1700, 100)
    xbmc.executebuiltin("SetFocus(9100)")
    mon.waitForAbort(1)
    log("mousehome: " + json.dumps(out))


def owntrakt_test():
    """2.0.1: Lucent's own Trakt login (traktlogin.py) comes before the login of a video add-on; Skin settings > Follow."""
    import importlib
    import sys as _s
    _s.path.insert(0, xbmcvfs.translatePath("special://skin/scripts/"))
    out = {}
    own = xbmcvfs.translatePath("special://profile/addon_data/skin.lucent/trakt.json")
    lv = xbmcvfs.translatePath("special://profile/addon_data/plugin.video.lucent/")
    os.makedirs(os.path.dirname(own), exist_ok=True)
    os.makedirs(lv, exist_ok=True)
    try:
        json.dump({"access_token": "lv-token", "refresh_token": "r", "expires_at": time.time() + 86400 * 30},
                  open(os.path.join(lv, "trakt.json"), "w"))
        json.dump({"trakt_client_id": "lv-client"}, open(os.path.join(lv, "keys.json"), "w"))
        json.dump({"client_id": "own-client", "client_secret": "own-secret", "access_token": "own-token",
                   "refresh_token": "r", "expires_at": time.time() + 86400 * 30, "user": "ci-user"}, open(own, "w"))
        import info
        import traktlogin
        importlib.reload(traktlogin)
        importlib.reload(info)
        tr = info.Trakt()
        out["own_first"] = tr.own and tr.client_id == "own-client" and tr.token == "own-token"
        os.remove(own)
        tr = info.Trakt()
        out["lv_fallback"] = (not tr.own) and tr.token == "lv-token"
        out["available"] = info.trakt_available()
    except Exception as error:  # noqa: BLE001
        out["error"] = f"{type(error).__name__}: {error}"
    for name in ("trakt.json", "keys.json"):
        if os.path.exists(os.path.join(lv, name)):
            os.remove(os.path.join(lv, name))
    xbmc.executebuiltin("Dialog.Close(all,true)")
    xbmc.executebuiltin("Skin.Reset(lucent.trakt.user)")
    xbmc.executebuiltin("ActivateWindow(SkinSettings)")
    mon.waitForAbort(2.5)
    n = int(lab("Container(9000).NumItems") or 0)
    for i in range(n):
        if lab(f"Container(9000).ListItemAbsolute({i}).Property(cat)") == "6":
            xbmc.executebuiltin(f"SetFocus(9000,{i},absolute)")
    mon.waitForAbort(1.3)
    out["button"] = cond("Control.IsVisible(1601)")
    xbmc.executebuiltin("SetFocus(1601)")
    mon.waitForAbort(1)
    shot("trakt-follow-out")
    xbmc.executebuiltin("Skin.SetString(lucent.trakt.user,ci-user)")
    mon.waitForAbort(1)
    shot("trakt-follow-in")
    xbmc.executebuiltin("Skin.Reset(lucent.trakt.user)")
    xbmc.executebuiltin("Action(Select)")
    for _ in range(20):
        if mon.waitForAbort(0.3) or cond("Window.IsVisible(yesnodialog)"):
            break
    mon.waitForAbort(1)
    out["keys_dialog"] = cond("Window.IsVisible(yesnodialog)")
    shot("trakt-keys")
    xbmc.executebuiltin("Dialog.Close(all,true)")
    mon.waitForAbort(1)
    xbmc.executebuiltin("Action(Back)")
    xbmc.executebuiltin("RunScript(special://skin/scripts/setup.py)")
    for _ in range(30):
        if mon.waitForAbort(0.3) or cond("Window.IsVisible(Lucent_Setup.xml)"):
            break
    mon.waitForAbort(1.5)
    for _ in range(3):
        xbmc.executebuiltin("SetFocus(100)")
        xbmc.executebuiltin("Action(Down)")
        mon.waitForAbort(0.3)
    xbmc.executebuiltin("Action(Select)")
    mon.waitForAbort(2.5)
    shot("trakt-setup")
    xbmc.executebuiltin("Dialog.Close(all,true)")
    xbmc.executebuiltin("ActivateWindow(home)")
    mon.waitForAbort(1)
    log("owntrakt: " + json.dumps(out))


def menus_test():
    """2.0 RC: every category of Settings and Skin settings, for a look at all menus."""
    out = {}
    for window, prefix in (("Settings", "set"), ("SkinSettings", "skin")):
        xbmc.executebuiltin("Dialog.Close(all,true)")
        xbmc.executebuiltin(f"ActivateWindow({window})")
        mon.waitForAbort(2.5)
        n = int(lab("Container(9000).NumItems") or 0)
        out[prefix] = [lab(f"Container(9000).ListItemAbsolute({i}).Label") for i in range(n)]
        for i in range(n):
            xbmc.executebuiltin(f"SetFocus(9000,{i},absolute)")
            mon.waitForAbort(1.3)
            shot(f"menus-{prefix}-{i}")
        xbmc.executebuiltin("Action(Back)")
        mon.waitForAbort(1)
    xbmc.executebuiltin("ActivateWindow(home)")
    mon.waitForAbort(1.5)
    xbmc.executebuiltin("SetFocus(9000)")
    mon.waitForAbort(1)
    shot("menus-home")
    log("menus: " + json.dumps(out))


def s56eps_test():
    """1.43.0: the season page shows its episodes as a row, a timeline, cards or a list with flags (side menu)."""
    out = {}
    xbmc.executebuiltin("Dialog.Close(all,true)")
    xbmc.executebuiltin("ActivateWindow(Videos,plugin://plugin.video.fakefen/?mode=showcase_seasons,return)")
    for _ in range(40):
        if mon.waitForAbort(0.3) or (cond("Control.IsVisible(56)") and int(lab("Container(5601).NumItems") or 0) > 0):
            break
    xbmc.executebuiltin("SetFocus(56,1,absolute)")         # the first season, not '..'
    mon.waitForAbort(2.5)
    out["page"] = cond("Control.IsVisible(56)")
    out["episodes"] = lab("Container(5601).NumItems")
    for style in ("timeline", "cards", "flags", ""):
        xbmc.executebuiltin(f"Skin.SetString(lucent.s56.eps,{style})" if style else "Skin.Reset(lucent.s56.eps)")
        xbmc.executebuiltin("SetFocus(5601)")
        xbmc.executebuiltin("Action(Right)")
        mon.waitForAbort(2)
        shot(f"s56-{style or 'row'}")
    xbmc.executebuiltin("SetFocus(56)")
    xbmc.executebuiltin("Action(Left)")
    mon.waitForAbort(1)
    out["menu"] = cond("ControlGroup(9050).HasFocus")
    out["button"] = cond("Control.IsVisible(9072)")
    xbmc.executebuiltin("SetFocus(9072)")
    mon.waitForAbort(0.8)
    shot("s56-menu")
    xbmc.executebuiltin("Action(Back)")
    xbmc.executebuiltin("ActivateWindow(home)")
    mon.waitForAbort(1)
    log("s56eps: " + json.dumps(out))


def wnitem_test():
    """1.43.0: What's new - OK on a change opens it on its own with a picture, the explanation and steps."""
    out = {}
    xbmc.executebuiltin("Dialog.Close(all,true)")
    xbmc.executebuiltin("RunScript(special://skin/scripts/whatsnew.py)")
    for _ in range(30):
        if mon.waitForAbort(0.3) or cond("Control.IsVisible(200)"):
            break
    mon.waitForAbort(1)
    xbmc.executebuiltin("SetFocus(200)")
    mon.waitForAbort(0.8)
    shot("wn-list")
    xbmc.executebuiltin("Action(Select)")
    for _ in range(20):
        if mon.waitForAbort(0.3) or cond("Window.IsVisible(Lucent_WhatsNewItem.xml)"):
            break
    mon.waitForAbort(1)
    out["open"] = cond("Window.IsVisible(Lucent_WhatsNewItem.xml)")
    shot("wn-item")
    xbmc.executebuiltin("SetFocus(12)")
    xbmc.executebuiltin("Action(Select)")
    mon.waitForAbort(1)
    shot("wn-item-next")
    xbmc.executebuiltin("Action(Back)")
    mon.waitForAbort(0.5)
    out["back_to_list"] = cond("Control.IsVisible(200)")
    xbmc.executebuiltin("Action(Back)")
    xbmc.executebuiltin("Action(Back)")
    xbmc.executebuiltin("ActivateWindow(home)")
    mon.waitForAbort(1)
    log("wnitem: " + json.dumps(out))


def newviews_test():
    """1.41.0 / 1.42.0: the newer views (films, series, episodes, music, sets, recently added) and the side menu in each."""
    out = {}
    if int(xbmc.executeJSONRPC('{"jsonrpc":"2.0","id":1,"method":"AudioLibrary.GetAlbums","params":{"limits":{"end":1}}}').count('"albumid"')) == 0:
        xbmc.executebuiltin("UpdateLibrary(music,/tmp/ci/music/)")
        for _ in range(60):
            if mon.waitForAbort(1) or not cond("Library.IsScanningMusic"):
                break
    runs = (("Videos", "plugin://plugin.video.fakefen/?mode=showcase", (70, 71, 72, 73, 87)),
            ("Videos", "plugin://plugin.video.fakefen/?mode=showcase_tv", (74, 75, 78)),
            ("Videos", "plugin://plugin.video.fakefen/?mode=showcase_ep", (76, 77, 79, 80)),
            ("Videos", "plugin://plugin.video.fakefen/?mode=showcase_sets", (86,)),
            ("Music", "musicdb://albums/", (81, 84, 85)),
            ("Music", "musicdb://artists/", (82,)),
            ("Music", "musicdb://songs/", (83,)))
    for window, path, views in runs:
        xbmc.executebuiltin("Dialog.Close(all,true)")
        xbmc.executebuiltin(f"ActivateWindow({window},{path},return)")
        for _ in range(30):
            if mon.waitForAbort(0.3) or (cond(f"Window.IsActive({window.lower()})") and int(lab("Container.NumItems") or 0) > 0):
                break
        mon.waitForAbort(1)
        for view in views:
            xbmc.executebuiltin(f"Container.SetViewMode({view})")
            mon.waitForAbort(2)
            xbmc.executebuiltin(f"SetFocus({view})")
            xbmc.executebuiltin("Action(Down)" if view in (73, 74, 77, 79, 80, 83, 87) else "Action(Right)")
            mon.waitForAbort(2.5)
            row = {"visible": cond(f"Control.IsVisible({view})"), "focus": cond(f"Control.HasFocus({view})"),
                   "mode": lab("Container.Viewmode"), "item": lab("ListItem.Label"), "content": lab("Container.Content")}
            shot(f"view-{view}")
            # the side menu: Left on the first item opens it, Right brings you back to the view
            xbmc.executebuiltin(f"SetFocus({view},0,absolute)")
            mon.waitForAbort(0.8)
            xbmc.executebuiltin("Action(Left)")
            mon.waitForAbort(1.2)
            row["menu_open"] = cond("ControlGroup(9050).HasFocus")
            if view in (72, 81):
                shot(f"view-{view}-menu")
            xbmc.executebuiltin("Action(Right)")
            mon.waitForAbort(1)
            row["menu_back"] = cond(f"Control.HasFocus({view})")
            out[view] = row
        xbmc.executebuiltin("Container.SetViewMode(50)" if window == "Music" else "Container.SetViewMode(51)")
        mon.waitForAbort(1)
    xbmc.executebuiltin("ActivateWindow(home)")
    mon.waitForAbort(1)
    log("newviews: " + json.dumps(out))

def lvtrakt_test():
    """1.39.0: the Trakt login of the video add-on is used (calendar, lists, watched) before Seren's."""
    import importlib
    import sys as _s
    _s.path.insert(0, xbmcvfs.translatePath("special://skin/scripts/"))
    data = xbmcvfs.translatePath("special://profile/addon_data/plugin.video.lucent/")
    os.makedirs(data, exist_ok=True)
    keep = {}
    for name in ("trakt.json", "keys.json"):
        p = os.path.join(data, name)
        keep[name] = open(p).read() if os.path.exists(p) else None
    try:
        json.dump({"access_token": "ci-token", "refresh_token": "ci-refresh", "expires_at": time.time() + 86400}, open(os.path.join(data, "trakt.json"), "w"))
        json.dump({"trakt_client_id": "ci-client"}, open(os.path.join(data, "keys.json"), "w"))
        import info
        importlib.reload(info)
        tr = info.Trakt()
        log(f"lvtrakt: lv client={tr.client_id == 'ci-client'} token={tr.token == 'ci-token'} seren={tr.seren} available={info.trakt_available()}")
        json.dump({"access_token": "ci-token", "expires_at": time.time() - 10}, open(os.path.join(data, "trakt.json"), "w"))
        log(f"lvtrakt: expired -> lv={info.lv_trakt() != ('', '')}")
    except Exception as error:  # noqa: BLE001
        log(f"lvtrakt: error {type(error).__name__}: {error}")
    finally:
        for name, text in keep.items():
            p = os.path.join(data, name)
            if text is None:
                if os.path.exists(p):
                    os.remove(p)
            else:
                open(p, "w").write(text)


def music_fav_test():
    """1.34.5: sort on last watched, one favourite as widget, the Covers view and the bigger cover for albums."""
    import sys as _s
    import threading
    _s.path.insert(0, xbmcvfs.translatePath("special://skin/scripts"))
    import menu as _m
    log(f"sorts: {[k for k, _n in _m.SORTS()]}")
    xbmc.executeJSONRPC(json.dumps({"jsonrpc": "2.0", "id": 1, "method": "Favourites.AddFavourite",
                                    "params": {"title": "CI In progress", "type": "window", "window": "videos", "windowparameter": "videodb://inprogresstvshows/"}}))
    res = []
    th = threading.Thread(target=lambda: res.append(_m.pick_favourite()))
    th.start()
    for _ in range(20):
        if cond("Window.IsActive(selectdialog)"):
            break
        mon.waitForAbort(0.5)
    mon.waitForAbort(1)
    shot("fav-pick")
    xbmc.executebuiltin("Action(Select)")
    th.join(10)
    log(f"fav: picked {res}")
    # music
    xbmc.executebuiltin("UpdateLibrary(music,/tmp/ci/music/)")
    for _ in range(40):
        mon.waitForAbort(1)
        r = json.loads(xbmc.executeJSONRPC(json.dumps({"jsonrpc": "2.0", "id": 1, "method": "AudioLibrary.GetAlbums", "params": {"properties": ["artist", "title"]}})))
        albums = (r.get("result") or {}).get("albums") or []
        if len(albums) >= 3 and not cond("Library.IsScanningMusic"):
            break
    log(f"music: albums {[(a.get('title'), a.get('artist')) for a in albums]}")
    xbmc.executebuiltin("ActivateWindow(Music,musicdb://albums/,return)")
    mon.waitForAbort(3)
    xbmc.executebuiltin("Container.SetViewMode(54)")
    mon.waitForAbort(2)
    log(f"music: view={lab('Container.Viewmode')} 54={cond('Control.IsVisible(54)')} item={lab('ListItem.Label')} artist={lab('ListItem.Artist')}")
    shot("music-covers")
    xbmc.executebuiltin("Container.SetViewMode(50)")
    mon.waitForAbort(2)
    for _ in range(3):
        if not cond("ListItem.IsParentFolder"):
            break
        key("Down")
        mon.waitForAbort(1)
    log(f"music: view={lab('Container.Viewmode')} 50={cond('Control.IsVisible(50)')} item={lab('ListItem.Label')} icon={lab('ListItem.Icon')[:60]}")
    shot("music-list")
    xbmc.executebuiltin("ActivateWindow(home)")
    mon.waitForAbort(2)


def smallposter_test():
    """1.34.6: small posters with names: the focused poster grows up and sideways, not over its name."""
    res = json.loads(xbmc.executeJSONRPC(json.dumps({"jsonrpc": "2.0", "id": 1, "method": "Files.GetDirectory",
        "params": {"directory": "plugin://script.lucent.library/?action=lib&kind=newin&only=movie", "media": "video"}})))
    log(f"librow: only=movie items={len((res.get('result') or {}).get('files') or [])} error={res.get('error')}")
    xbmc.executebuiltin("Skin.SetBool(lucent.posters.small)")
    xbmc.executebuiltin("Skin.Reset(nuvio.posterlabels.hide)")
    xbmc.executebuiltin("ReloadSkin()")
    mon.waitForAbort(8)
    xbmc.executebuiltin("ActivateWindow(home)")
    mon.waitForAbort(3)
    xbmc.executebuiltin("Control.SetFocus(9000,1)")
    mon.waitForAbort(2)
    xbmc.executebuiltin("SetFocus(9100)")
    mon.waitForAbort(3)
    log(f"smallposter: focus={lab('System.CurrentControlId')} item={lab('Container(' + lab('System.CurrentControlId') + ').ListItem.Label')}")
    shot("smallposter-focus")
    xbmc.executebuiltin("Skin.Reset(lucent.posters.small)")
    xbmc.executebuiltin("Skin.SetBool(nuvio.posterlabels.hide)")
    xbmc.executebuiltin("ReloadSkin()")
    mon.waitForAbort(6)


def alwayson_test():
    """1.34.7: Subtitles always on: a new video starts with a subtitle, also when the sound is in your language.
    (On CI a video only really starts after ~9 s: there is no sound card, Kodi waits for it first.)"""
    pl = xbmc.Player()
    out = {}
    for setting in (True, False):
        xbmc.executebuiltin("Skin.SetBool(lucent.subs.alwayson)" if setting else "Skin.Reset(lucent.subs.alwayson)")
        mon.waitForAbort(1)
        for f in ("nodef-eng", "same-eng"):
            started = HOME.getProperty("lucent.play.start")
            xbmc.executebuiltin(f"PlayMedia(/tmp/ci/{f}.mkv)")
            for _ in range(60):                         # until Lucent's watcher saw the start (onAVStarted)
                if HOME.getProperty("lucent.play.start") != started:
                    break
                mon.waitForAbort(0.5)
            mon.waitForAbort(9)                          # the watcher waits 4 s, then checks
            out[f"{'on' if setting else 'off'}:{f}"] = (cond("VideoPlayer.SubtitlesEnabled"), lab("VideoPlayer.SubtitlesLanguage"))
            if f == "nodef-eng" and setting:
                shot("alwayson-play")
            pl.stop()
            mon.waitForAbort(3)
    log(f"alwayson: {out}")
    xbmc.executebuiltin("Skin.Reset(lucent.subs.alwayson)")


def omdblist_test():
    """1.34.8: Rotten Tomatoes / Metacritic of the title under the cursor in the lists (no info page)."""
    d = xbmcvfs.translatePath("special://profile/addon_data/skin.lucent/")
    with open(os.path.join(d, "omdb.key"), "w") as fh:
        fh.write("cikey1234")
    mon.waitForAbort(31)                                  # the helper reads the key again after 30 s
    xbmc.executebuiltin("ActivateWindow(Videos,videodb://movies/titles/,return)")
    mon.waitForAbort(3)
    for view in (51, 50):
        xbmc.executebuiltin(f"Container.SetViewMode({view})")
        mon.waitForAbort(2)
        xbmc.executebuiltin(f"SetFocus({view})")
        mon.waitForAbort(1)
        for _ in range(4):
            if lab("ListItem.DBType") == "movie":
                break
            key("Down")
            mon.waitForAbort(1)
        mon.waitForAbort(4)
        log(f"omdblist: diag helper={HOME.getProperty('lucent.helper')} now={time.time():.1f} videos={cond('Window.IsActive(videos)')} "
            f"content={lab('Container.Content')} c_movies={cond('Container.Content(movies)')} imdb={lab('ListItem.UniqueID(imdb)')!r} "
            f"imdbnr={lab('ListItem.IMDBNumber')!r} dbtype={lab('ListItem.DBType')} dbid={lab('ListItem.DBID')} off={cond('Skin.HasSetting(lucent.omdb.lists.off)')}")
        p = {k: HOME.getProperty("lucent.omdbl." + k) for k in ("rt", "rtc", "mc", "mcc", "imdb", "for")}
        log(f"omdblist: view={lab('Container.Viewmode')} item={lab('ListItem.Label')} props={p}")
        shot(f"omdblist-{view}")
        key("Up")
        mon.waitForAbort(2)
        log(f"omdblist: on '..' for={HOME.getProperty('lucent.omdbl.for')!r}")
        key("Down")
        mon.waitForAbort(3)
        log(f"omdblist: back on {lab('ListItem.Label')!r} rt={HOME.getProperty('lucent.omdbl.rt')!r} mc={HOME.getProperty('lucent.omdbl.mc')!r}")
        key("Up")
        mon.waitForAbort(1)
    os.remove(os.path.join(d, "omdb.key"))
    xbmc.executebuiltin("ActivateWindow(home)")
    mon.waitForAbort(2)


def flicker_test():
    """the video add-on marks many titles watched: does the focus jump to the side menu while the library changes?"""
    import threading
    r = json.loads(xbmc.executeJSONRPC(json.dumps({"jsonrpc": "2.0", "id": 1, "method": "VideoLibrary.GetMovies", "params": {"properties": ["playcount"]}})))
    movies = (r.get("result") or {}).get("movies") or []
    out = {"movies": len(movies)}
    if not movies:
        log("flicker: " + json.dumps(out))
        return
    mid = movies[0]["movieid"]

    def run(name, focus):
        xbmc.executebuiltin(focus)
        mon.waitForAbort(2.5)
        start_id = lab("System.CurrentControlId")
        seen = []
        stop = []

        def sample():
            while not stop and not mon.abortRequested():
                cid = lab("System.CurrentControlId") + ("/menu" if cond("Control.HasFocus(9000)") else "")
                if not seen or seen[-1] != cid:
                    seen.append(cid)
                time.sleep(0.03)
        th = threading.Thread(target=sample)
        th.start()
        for n in range(30):
            xbmc.executeJSONRPC(json.dumps({"jsonrpc": "2.0", "id": 1, "method": "VideoLibrary.SetMovieDetails",
                                            "params": {"movieid": mid, "playcount": n % 2}}))
            mon.waitForAbort(0.2)
        mon.waitForAbort(1.5)
        stop.append(1)
        th.join(5)
        out[name] = {"start": start_id, "changes": len(seen) - 1, "seen": seen[:12], "end": lab("System.CurrentControlId")}
        shot(f"flicker-{name}")

    tab = None
    for i in range(16):
        xbmc.executebuiltin(f"Control.SetFocus(9000,{i})")
        mon.waitForAbort(0.4)
        if cond("String.Contains(Container(9000).ListItem.Property(act),AddonBrowser)"):
            tab = i
            break
    out["addontab"] = tab
    if tab is not None:
        run("addons", "SetFocus(9340)")
    xbmc.executebuiltin("Control.SetFocus(9000,0)")
    mon.waitForAbort(2)
    run("homerow", "SetFocus(9100)")
    xbmc.executeJSONRPC(json.dumps({"jsonrpc": "2.0", "id": 1, "method": "VideoLibrary.SetMovieDetails", "params": {"movieid": mid, "playcount": movies[0].get("playcount", 0)}}))
    xbmc.executebuiltin("Control.SetFocus(9000,0)")
    log("flicker: " + json.dumps(out))


ONLY = None
try:
    ONLY = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "only.txt")).read().split()
except OSError:
    pass


def svctiles_test():
    """2.1.2: the streaming services row (Home tab, row 2, landscape): every logo on a solid dark card."""
    out = {}
    xbmc.executebuiltin("Dialog.Close(all,true)")
    xbmc.executebuiltin("ActivateWindow(home)")
    mon.waitForAbort(1.5)
    xbmc.executebuiltin("Dialog.Close(all,true)")
    xbmc.executebuiltin("Control.SetFocus(9000,5)")
    mon.waitForAbort(6)
    for _ in range(10):
        xbmc.executebuiltin("SetFocus(8201)")
        mon.waitForAbort(1.5)
        if lab("Container(8201).ListItem.Label"):
            break
    out["first"] = lab("Container(8201).ListItem.Label")
    out["svclogo"] = lab("Container(8201).ListItem.Property(svclogo)")
    out["num"] = lab("Container(8201).NumItems")
    shot("svc-1")
    xbmc.executebuiltin("Action(Right)")
    mon.waitForAbort(1.5)
    out["second"] = lab("Container(8201).ListItem.Label")
    shot("svc-2")
    xbmc.executebuiltin("Control.SetFocus(9000,0)")
    mon.waitForAbort(1)
    log("svctiles: " + json.dumps(out))


def sort_test():
    """Issue #9 (13 Nov): rows from an add-on and genre rows ignore the sort chosen in Menu and widgets."""
    out = {}
    r = json.loads(xbmc.executeJSONRPC(json.dumps({"jsonrpc": "2.0", "id": 1, "method": "VideoLibrary.GetMovies"})))
    genres = [["Western"], ["Action", "Drama"], ["Comedy"], ["Thriller"], ["Animation"], ["Horror"]]
    for n, m in enumerate((r.get("result") or {}).get("movies") or []):
        xbmc.executeJSONRPC(json.dumps({"jsonrpc": "2.0", "id": 1, "method": "VideoLibrary.SetMovieDetails",
                                        "params": {"movieid": m["movieid"], "genre": genres[n % len(genres)]}}))
    xbmc.executebuiltin("Dialog.Close(all,true)")
    xbmc.executebuiltin("ActivateWindow(home)")
    mon.waitForAbort(1.5)
    xbmc.executebuiltin("Dialog.Close(all,true)")
    for tab in (3, 4):
        xbmc.executebuiltin(f"Control.SetFocus(9000,{tab})")
        mon.waitForAbort(8)
        name = lab("Container(9000).ListItem.Label")
        for w in (1, 2):
            rows = {}
            for cid in (8100 + w, 8200 + w):
                n = int(lab(f"Container({cid}).NumItems") or 0)
                if n:
                    rows[cid] = [lab(f"Container({cid}).ListItemAbsolute({i}).Label") for i in range(min(n, 8))]
            out[f"{name} w{w}"] = [lab(f"Skin.String(nuvio.tab{tab + 1}.w{w}.label)"), lab(f"Skin.String(nuvio.tab{tab + 1}.w{w}.sort)"), rows]
        shot(f"sort-tab{tab}")
    shot("sort-tab")
    log("sort: " + json.dumps(out))


def homeextra_test():
    """2.1.3 (Reddit): on Home the OMDb / MDBList scores of the title under the cursor, episodes left in the season and a
    season premiere / finale badge. Lib Show season 1 has two episodes: E1 = premiere, 1 left; E2 = finale, last one."""
    out = {}
    d = xbmcvfs.translatePath("special://profile/addon_data/skin.lucent/")
    os.makedirs(d, exist_ok=True)
    with open(os.path.join(d, "mdblist.key"), "w") as fh:
        fh.write("cimdbkey")
    xbmc.executebuiltin("Dialog.Close(all,true)")
    xbmc.executebuiltin("ActivateWindow(home)")
    mon.waitForAbort(1.5)
    xbmc.executebuiltin("Dialog.Close(all,true)")
    for k, v in (("label", "Series"), ("w1.label", "Afleveringen"), ("w1.path", "videodb://tvshows/titles/901/1/"), ("w1.style", "poster"),
                 ("w2.label", "Films"), ("w2.path", "videodb://movies/titles/"), ("w2.style", "poster")):
        xbmc.executebuiltin(f"Skin.SetString(nuvio.tab3.{k},{v})")
    xbmc.executebuiltin("Skin.Reset(nuvio.tab3.w3.path)")
    mon.waitForAbort(31)                                   # the helper reads the keys again after 30 s
    xbmc.executebuiltin("Control.SetFocus(9000,2)")
    mon.waitForAbort(3)
    xbmc.executebuiltin("ReplaceWindow(home)")
    mon.waitForAbort(3)
    xbmc.executebuiltin("Control.SetFocus(9000,2)")
    mon.waitForAbort(5)
    props = lambda: {"item": lab("Container(8101).ListItem.Label") if HOME.getProperty("nuvio.row") == "8101" else lab("Container(8102).ListItem.Label"),  # noqa: E731
                     "row": HOME.getProperty("nuvio.row"),
                     "ep": [HOME.getProperty("lucent.ep.left"), HOME.getProperty("lucent.ep.badge")],
                     "scores": {k: HOME.getProperty("lucent.omdbh." + k) for k in ("rt", "rta", "mc", "lb", "for")}}
    xbmc.executebuiltin("SetFocus(8101,0,absolute)")
    mon.waitForAbort(4)
    out["ep1"] = props()
    shot("homeextra-ep1")
    xbmc.executebuiltin("SetFocus(8101,1,absolute)")
    mon.waitForAbort(4)
    out["ep2"] = props()
    shot("homeextra-ep2")
    xbmc.executebuiltin("SetFocus(8102,0,absolute)")
    mon.waitForAbort(4)
    out["movie"] = props()
    shot("homeextra-movie")
    log("homeextra: " + json.dumps(out, ensure_ascii=False))
    os.remove(os.path.join(d, "mdblist.key"))
    xbmc.executebuiltin("Skin.SetString(nuvio.tab3.label,Streaming)")


def sideicons_test():
    """Issue #17: Skin settings > Hide side icons: no icons in the side bar while the rows have the focus."""
    out = {}
    xbmc.executebuiltin("Dialog.Close(all,true)")
    xbmc.executebuiltin("Skin.SetBool(nuvio.sideicons.hide)")
    xbmc.executebuiltin("ActivateWindow(home)")
    mon.waitForAbort(2)
    xbmc.executebuiltin("Dialog.Close(all,true)")
    xbmc.executebuiltin("Control.SetFocus(9000,0)")
    mon.waitForAbort(2)
    shot("sideicons-menu")
    xbmc.executebuiltin("SetFocus(9100)")
    mon.waitForAbort(3)
    out["focus"] = xbmcgui.Window(10000).getFocusId()
    out["hide"] = cond("Skin.HasSetting(nuvio.sideicons.hide)")
    shot("sideicons-rows")
    xbmc.executebuiltin("ActivateWindow(Videos,videodb://movies/titles/,return)")
    mon.waitForAbort(4)
    shot("sideicons-videos")
    xbmc.executebuiltin("Skin.Reset(nuvio.sideicons.hide)")
    xbmc.executebuiltin("ActivateWindow(home)")
    mon.waitForAbort(2)
    log("sideicons: " + json.dumps(out))


def cwjump_test():
    """Wilfried 13 Nov: on his Series tab (with the Continue watching row of the library above it) the rows shift by
    themselves. Fill the Continue watching row first, then sit on Nieuw with poster trailers on."""
    xbmc.executebuiltin("Skin.SetBool(lucent.cw.on)")
    xbmc.executebuiltin("RunScript(special://skin/scripts/continuerow.py)")
    mon.waitForAbort(4)
    xbmc.executebuiltin("Skin.SetBool(nuvio.trailers.menu)")
    xbmc.executebuiltin("Skin.SetString(nuvio.posterfocus,window)")
    xbmc.executebuiltin("RunScript(special://skin/scripts/trailers.py)")
    _idle_on_series("cwjump", 1, 60)
    xbmc.executebuiltin("Skin.Reset(nuvio.trailers.menu)")
    xbmc.executebuiltin("Skin.Reset(nuvio.posterfocus)")


def trailerjump_test():
    """Wilfried's video (13 Nov): a trailer on a poster of a Series tab - does the focus jump to the next row?"""
    for mode in ("window", "hero", "expand"):
        xbmc.executebuiltin("Skin.SetBool(nuvio.trailers.menu)")
        xbmc.executebuiltin(f"Skin.SetString(nuvio.posterfocus,{mode})")
        xbmc.executebuiltin("RunScript(special://skin/scripts/trailers.py)")
        _idle_on_series(f"trailer-{mode}", 0.5, 60)
    xbmc.executebuiltin("Skin.Reset(nuvio.trailers.menu)")
    xbmc.executebuiltin("Skin.Reset(nuvio.posterfocus)")


def idlejump_test():
    """Wilfried's video (13 Nov): on a Series tab the focus jumps between two rows by itself, with a spinner. Sit still
    on the first row of a tab named Series for 60 s and log every 2 s where the focus is."""
    _idle_on_series("idle", 2, 30)


def _idle_on_series(name, step, rounds):
    out = {"t": []}
    W = "plugin://plugin.video.fakeseren/?list="
    xbmc.executebuiltin("Dialog.Close(all,true)")
    xbmc.executebuiltin("ActivateWindow(home)")
    mon.waitForAbort(1.5)
    xbmc.executebuiltin("Dialog.Close(all,true)")
    for k, v in (("label", "Series"), ("w1.label", "Nieuw"), ("w1.path", W + "ss"), ("w1.style", "poster"),
                 ("w2.label", "Binnenkort"), ("w2.path", W + "sm"), ("w2.style", "poster"),
                 ("w3.label", "Afleveringen"), ("w3.path", W + "se"), ("w3.style", "land")):
        xbmc.executebuiltin(f"Skin.SetString(nuvio.tab3.{k},{v})")
    mon.waitForAbort(2)
    xbmc.executebuiltin("Control.SetFocus(9000,2)")
    mon.waitForAbort(6)
    xbmc.executebuiltin("Action(Right)")
    mon.waitForAbort(3)
    xbmc.executebuiltin("ReplaceWindow(home)")
    mon.waitForAbort(3)
    xbmc.executebuiltin("Control.SetFocus(9000,2)")
    mon.waitForAbort(4)
    xbmc.executebuiltin("SetFocus(8101)")
    mon.waitForAbort(0.5)
    shot(f"{name}-0")
    for i in range(rounds):
        mon.waitForAbort(step)
        try:
            fid = xbmcgui.Window(10000).getFocusId()
        except RuntimeError:
            fid = -1
        out["t"].append([i * 2, fid, lab("Window(home).Property(nuvio.row)"), lab("ListItem.Label"),
                         HOME.getProperty("lucent.cw.show"), HOME.getProperty("lucent.cw.count"),
                         cond("Window.IsVisible(busydialognocancel) | Window.IsVisible(busydialog)"),
                         cond("Player.HasVideo"), HOME.getProperty("nuvio.trailer.playing"),
                         cond("Control.IsVisible(8092)"), cond("Control.IsVisible(8101)"), cond("Control.IsVisible(8102)"),
                         lab("Container(8101).NumItems"), lab("Container(8102).NumItems")])
        if (name == "cwlog" and i % 2 == 0) or i in (rounds // 6, rounds // 3, rounds // 2, rounds - 1) or (out["t"][-1][1] not in (8101,) and i % 3 == 0) or \
                (len(out["t"]) > 1 and out["t"][-1][9:12] != out["t"][-2][9:12]):
            shot(f"{name}-{i}")
    log(f"idlejump {name}: " + json.dumps(out))
    xbmc.executebuiltin("PlayerControl(Stop)")
    mon.waitForAbort(2)
    xbmc.executebuiltin("Skin.SetString(nuvio.tab3.label,Streaming)")


def safe(test):
    if ONLY is not None and test.__name__ not in ONLY:
        return
    """One test that fails (for example because Lucent Library is no longer there) does not stop the others."""
    try:
        test()
    except Exception as error:  # noqa: BLE001
        log(f"test error {test.__name__}: {error!r}")
        xbmc.executebuiltin("Dialog.Close(all,true)")


def main():
    for _ in range(180):
        if cond("Window.IsActive(home)") and HOME.getProperty("nuvio.started"):
            break
        mon.waitForAbort(1)
    log(f"deps: tidb repo={cond('System.HasAddon(repository.tidb.repo)')} tidb={cond('System.HasAddon(plugin.video.tidb)')}")
    log(f"deps: seren-nixgate={cond('System.HasAddon(repository.seren-nixgate)')} enabled={cond('System.AddonIsEnabled(repository.seren-nixgate)')}")
    try:
        _ticks = os.sysconf(os.sysconf_names["SC_CLK_TCK"])
        _start = int(open("/proc/self/stat").read().rsplit(")", 1)[1].split()[19]) / _ticks
        HOME_READY["uptime"] = round(float(open("/proc/uptime").read().split()[0]) - _start, 1)
    except Exception:  # noqa: BLE001
        pass
    log(f"home ready skin={lab('Skin.CurrentTheme')} {lab('System.AddonVersion(skin.lucent)')} "
        f"lib={lab('System.AddonVersion(script.lucent.library)')} helper={HOME.getProperty('lucent.helper.running')}")
    xbmc.executebuiltin("Dialog.Close(all,true)")
    xbmc.executebuiltin("Control.SetFocus(9000,0)")
    watch("home1", 40)
    shot("1-home")
    safe(svctiles_test)
    safe(sideicons_test)
    safe(cwjump_test)
    safe(intro_test)
    safe(introsound_test)
    safe(cwjumplog_test)
    safe(rowshift_test)
    safe(cwmenu_test)
    safe(badges_test)
    safe(okpage_test)
    safe(levels_test)
    safe(epinprog_test)
    safe(cwnotice_test)
    safe(agendalist_test)
    safe(intro2_test)
    safe(homeextra_test)
    safe(sort_test)
    safe(idlejump_test)
    safe(trailerjump_test)
    safe(mousehome_test)
    safe(nolv_test)
    safe(remember_test)
    safe(firststart_test)
    safe(perf_test)
    safe(cwrow_test)
    safe(litesetup_test)
    safe(owntrakt_test)
    safe(osdintro_test)
    safe(flicker_test)
    safe(diaglog_test)
    safe(dv2_test)
    safe(videotab_test)
    safe(skipdup_test)
    safe(scrub_open_test)
    safe(readable_test)
    safe(landseries_test)
    safe(fenlight_test)
    safe(sideclick_test)
    safe(views_pause_test)
    safe(pct_test)
    safe(ytfix_test)
    safe(fsback_test)
    safe(omdb_test)
    safe(omdblist_test)
    safe(mdblist_test)
    safe(mediaflags_test)
    safe(menumove_test)
    safe(letters_test)
    safe(lucentvideo_test)
    safe(music_fav_test)
    safe(smallposter_test)
    safe(alwayson_test)
    safe(nolib_test)
    safe(infobuttons_test)
    safe(progress_colour_test)
    safe(formatclips_test)
    safe(trailerlayer_test)
    safe(lvtrakt_test)
    safe(addonsettings_test)
    safe(menus_test)
    safe(s56eps_test)
    safe(wnitem_test)
    safe(osdclose_test)
    safe(newviews_test)
    safe(liteold_test)

    try:                                                   # conditions Kodi could not read (like '[dv2]' in 1.34.1-1.34.14)
        with open(xbmcvfs.translatePath("special://logpath/kodi.log"), encoding="utf-8", errors="replace") as fh:
            bad = [ln.strip()[24:220] for ln in fh if "Error parsing boolean expression" in ln or "Misplaced" in ln]
        log(f"parse errors: {len(bad)} {json.dumps(bad[:5])}")
    except OSError as error:
        log(f"parse errors: log not readable {error}")
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
