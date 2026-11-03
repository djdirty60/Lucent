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
        if run == 3:
            import sys
            import xbmcvfs
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


def main():
    for _ in range(180):
        if cond("Window.IsActive(home)") and HOME.getProperty("nuvio.started"):
            break
        mon.waitForAbort(1)
    log(f"deps: tidb repo={cond('System.HasAddon(repository.tidb.repo)')} tidb={cond('System.HasAddon(plugin.video.tidb)')}")
    log(f"deps: seren-nixgate={cond('System.HasAddon(repository.seren-nixgate)')} enabled={cond('System.AddonIsEnabled(repository.seren-nixgate)')}")
    log(f"home ready skin={lab('Skin.CurrentTheme')} {lab('System.AddonVersion(skin.lucent)')} "
        f"lib={lab('System.AddonVersion(script.lucent.library)')} helper={HOME.getProperty('lucent.helper.running')}")
    xbmc.executebuiltin("Dialog.Close(all,true)")
    xbmc.executebuiltin("Control.SetFocus(9000,0)")
    watch("home1", 40)
    shot("1-home")
    settiles_test()
    sportosd_test()
    pinfo2_test()

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
