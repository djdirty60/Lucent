# -*- coding: utf-8 -*-
"""Toont het echte dashboard als beeld, geleverd door de Solis beeldserver."""
import os
import threading
import time

import xbmc
import xbmcgui
import xbmcvfs

from . import client

ACTION_MOVE_LEFT = 1
ACTION_MOVE_RIGHT = 2
ACTION_PREVIOUS_MENU = 10
ACTION_NAV_BACK = 92

DEFAULT_PAGES = ['zon', 'stroom', 'meer', 'inzicht', 'overzicht', 'dynamisch', 'verbruik', 'slim', 'instel']
NAMES = {'zon': 'Zon', 'stroom': 'Stroom', 'meer': 'Details', 'inzicht': 'Inzicht', 'overzicht': 'Overzicht',
         'dynamisch': 'Dynamisch', 'verbruik': 'Verbruik', 'slim': 'Slim', 'instel': 'Opties'}


class SolisImageWindow(xbmcgui.WindowXML):
    addon = None
    pages = None
    index = 0
    _stop = False

    def onInit(self):
        s = self.addon
        self._lock = threading.RLock()
        self._stop = False
        self._flip = 0
        self._want = True        # er moet een nieuwe afbeelding komen
        self._hint_until = 0.0
        self.homey = (s.getSetting('mode') or '2') == '2'
        if self.homey:   # beeld rechtstreeks uit de Homey-app
            self.host = s.getSetting('host') or 'homey.local'
            self.port = int(s.getSetting('port') or 8765)
            self.prefix, self.ext = '/beeld', 'png'
        else:            # beeld van de beeldserver op een computer
            self.host = s.getSetting('render_host')
            self.port = int(s.getSetting('render_port') or 8780)
            self.prefix, self.ext = '', 'jpg'
        self.refresh = max(3, int(s.getSetting('refresh') or 10))
        self.rotate = max(0, int(s.getSetting('rotate') or 0))
        self.pages = list(DEFAULT_PAGES)
        self.index = min(max(0, int(s.getSetting('startpage') or 0)), len(self.pages) - 1)
        self._tmp = xbmcvfs.translatePath('special://temp/')
        self._set(14, '' if self.host else s.getLocalizedString(30012))
        threading.Thread(target=self._loop, daemon=True).start()

    def onAction(self, action):
        aid = action.getId()
        if aid in (ACTION_PREVIOUS_MENU, ACTION_NAV_BACK):
            self._stop = True
            self.close()
        elif aid == ACTION_MOVE_RIGHT:
            self._go(1)
        elif aid == ACTION_MOVE_LEFT:
            self._go(-1)

    def _go(self, step):
        with self._lock:
            self.index = (self.index + step) % len(self.pages)
            self._want = True
            self._last_rotate = time.time()

    def _set(self, cid, text):
        try:
            self.getControl(cid).setLabel(text)
        except Exception:  # noqa: BLE001
            pass

    def _opruimen(self, nr):
        """Verwijdert oude tijdelijke afbeeldingen."""
        for n in range(max(0, nr - 2), nr + 1):
            try:
                os.remove(os.path.join(self._tmp, 'solis_beeld_%d.%s' % (n, self.ext)))
            except OSError:
                pass

    def _page_title(self):
        p = self.pages[self.index]
        return '%s  (%d/%d)' % (NAMES.get(p, p), self.index + 1, len(self.pages))

    def _loop(self):
        monitor = xbmc.Monitor()
        last = 0.0
        self._last_rotate = time.time()
        listed = False
        while not self._stop and not monitor.abortRequested():
            now = time.time()
            if self.host and not listed:
                try:
                    pages = client.fetch_pages(self.host, self.port, prefix=self.prefix)
                    with self._lock:
                        self.pages = pages
                        self.index = min(self.index, len(pages) - 1)
                    listed = True
                except Exception as exc:  # noqa: BLE001
                    xbmc.log('Solis dashboard: paginalijst mislukt: %s' % exc, xbmc.LOGWARNING)
            if self.rotate and now - self._last_rotate >= self.rotate:
                self._go(1)
            if self.host and (self._want or now - last >= self.refresh):
                with self._lock:
                    page = self.pages[self.index]
                    self._want = False
                last = now
                self._flip += 1   # elke afbeelding een eigen bestandsnaam: Kodi onthoudt anders de oude
                path = os.path.join(self._tmp, 'solis_beeld_%d.%s' % (self._flip, self.ext))
                try:
                    client.download_page(self.host, self.port, page, path, prefix=self.prefix, ext=self.ext)
                    with self._lock:
                        still = page == self.pages[self.index]
                    if still:
                        self.getControl(20).setImage(path, False)
                        self._opruimen(self._flip - 3)
                    self._set(14, '')
                except Exception as exc:  # noqa: BLE001
                    xbmc.log('Solis dashboard: beeld ophalen mislukt: %s' % exc, xbmc.LOGWARNING)
                    self._set(14, self.addon.getLocalizedString(30012))
                self._hint_until = max(self._hint_until, now + 3) if self._hint_until == 0 else now + 3
                self._set(13, self._page_title())
            if self._hint_until and now > self._hint_until:
                self._hint_until = 0
                self._set(13, '')
            if monitor.waitForAbort(0.5):
                break
