# -*- coding: utf-8 -*-
"""Solis Dashboard voor Kodi: startpunt van de add-on."""
import xbmcaddon


def run():
    addon = xbmcaddon.Addon()
    path = addon.getAddonInfo('path')
    if (addon.getSetting('mode') or '2') == '1':
        from resources.lib.window import SolisWindow
        win = SolisWindow('script-solis-dashboard.xml', path, 'default', '1080i')
    else:
        from resources.lib.imagewindow import SolisImageWindow
        win = SolisImageWindow('script-solis-image.xml', path, 'default', '1080i')
    win.addon = addon
    win.doModal()
    del win


if __name__ == '__main__':
    run()
