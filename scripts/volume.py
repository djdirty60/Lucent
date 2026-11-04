"""Lucent: keeps Window(home).Property(lucent.vol.pct / lucent.vol.step) up to date while the volume bar is open
(DialogVolumeBar.xml runs this on load). Kodi's own Player.Volume is in dB; the pill shows percent."""
import json

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
    try:
        while not mon.abortRequested() and gone < 8:
            vol = read()
            HOME.setProperty("lucent.vol.pct", str(vol))
            HOME.setProperty("lucent.vol.step", str(max(1, round(vol / 2))) if vol > 0 else "0")
            gone = 0 if xbmc.getCondVisibility("Window.IsVisible(volumebar)") else gone + 1
            if mon.waitForAbort(0.08):
                break
    finally:
        HOME.clearProperty("lucent.vol.busy")


if __name__ == "__main__":
    run()
