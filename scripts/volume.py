"""Lucent: keeps Window(home).Property(lucent.vol.pct / lucent.vol.step) up to date while the volume bar is open
(DialogVolumeBar.xml runs this on load). Kodi's own Player.Volume is in dB; the card shows percent and 24 blocks."""
import json
import time

import xbmc
import xbmcgui

HOME = xbmcgui.Window(10000)


def read():
    try:
        res = json.loads(xbmc.executeJSONRPC(json.dumps({"jsonrpc": "2.0", "id": 1, "method": "Application.GetProperties",
                                                         "params": {"properties": ["volume"]}})))
        return int((res.get("result") or {}).get("volume") or 0)
    except Exception:  # noqa: BLE001
        return 0


def run():
    if HOME.getProperty("lucent.vol.busy"):
        return                                  # one copy is already following the bar
    HOME.setProperty("lucent.vol.busy", "1")
    mon = xbmc.Monitor()
    gone = 0
    muted_since = 0.0
    try:
        while not mon.abortRequested() and gone < 8:
            vol = read()
            HOME.setProperty("lucent.vol.pct", str(vol))
            HOME.setProperty("lucent.vol.seg", str(max(1, round(vol * 24 / 100))) if vol > 0 else "0")   # 24 blocks
            gone = 0 if xbmc.getCondVisibility("Window.IsVisible(volumebar)") else gone + 1
            # 2.1.7 (#20): Kodi keeps the bar open while muted; the card fades away after 1.2 s (lucent.vol.hide)
            if xbmc.getCondVisibility("Player.Muted"):
                muted_since = muted_since or time.time()
                if time.time() - muted_since > 1.2 and not HOME.getProperty("lucent.vol.hide"):
                    HOME.setProperty("lucent.vol.hide", "1")
            else:
                muted_since = 0.0
                if HOME.getProperty("lucent.vol.hide"):
                    HOME.clearProperty("lucent.vol.hide")
            if mon.waitForAbort(0.08 if not HOME.getProperty("lucent.vol.hide") else 0.3):
                break
    finally:
        HOME.clearProperty("lucent.vol.busy")
        HOME.clearProperty("lucent.vol.hide")


if __name__ == "__main__":
    run()
