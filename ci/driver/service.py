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
    club_test()
    mine_test()

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
