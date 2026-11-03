# -*- coding: utf-8 -*-
"""Het Kodi-scherm: tekent de pagina's van het Solis-dashboard."""
import threading
import time

import xbmc
import xbmcgui

from . import client, layout

ACTION_MOVE_LEFT = 1
ACTION_MOVE_RIGHT = 2
ACTION_PREVIOUS_MENU = 10
ACTION_NAV_BACK = 92

CARD_BASE = 100   # kaart i: groep 100+10i, titel +1, groot +2, eenheid +3, tekst +4
BAR_ROWS = (500, 600)  # rij: groep, titel +1, info +2, uurlabels +10.., balken +20..


class SolisWindow(xbmcgui.WindowXML):
    addon = None
    data = None
    page = 0
    error = ''
    _stop = False
    _lock = None

    def onInit(self):
        self._lock = threading.RLock()
        self._stop = False
        s = self.addon
        self.host = s.getSetting('host') or 'homey.local'
        self.port = int(s.getSetting('port') or 8765)
        self.refresh = max(3, int(s.getSetting('refresh') or 10))
        self.rotate = max(0, int(s.getSetting('rotate') or 0))
        self.page = max(0, int(s.getSetting('startpage') or 0))
        self.getControl(13).setLabel(s.getLocalizedString(30011))
        self._hide_all()
        threading.Thread(target=self._loop, daemon=True).start()

    # ---------- invoer ----------
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
            n = len((self.data or {}).get('pages') or [1])
            self.page = (self.page + step) % max(n, 1)
            self._last_rotate = time.time()
        self.render()

    # ---------- achtergrondlus ----------
    def _loop(self):
        monitor = xbmc.Monitor()
        last_fetch = 0.0
        self._last_rotate = time.time()
        while not self._stop and not monitor.abortRequested():
            now = time.time()
            if now - last_fetch >= self.refresh or self.data is None and now - last_fetch >= 3:
                last_fetch = now
                try:
                    data = client.fetch(self.host, self.port)
                    with self._lock:
                        self.data = data
                        self.error = ''
                except Exception as exc:  # noqa: BLE001
                    xbmc.log('Solis dashboard: ophalen mislukt: %s' % exc, xbmc.LOGWARNING)
                    with self._lock:
                        self.error = self.addon.getLocalizedString(30010)
                self.render()
            if self.rotate and self.data and now - self._last_rotate >= self.rotate:
                self._last_rotate = now
                self._go(1)
            if monitor.waitForAbort(1):
                break

    # ---------- tekenen ----------
    def _set(self, cid, text):
        try:
            self.getControl(cid).setLabel(text)
        except Exception:  # noqa: BLE001
            pass

    def _hide_all(self):
        for i in range(12):
            self.getControl(CARD_BASE + i * 10).setVisible(False)
        for base in BAR_ROWS:
            self.getControl(base).setVisible(False)

    def render(self):
        with self._lock:
            data, page, error = self.data, self.page, self.error
        self._set(14, error)
        if not data:
            self._set(10, 'Solis')
            return
        pages = data['pages']
        page = page % len(pages)
        pg = pages[page]
        self._set(10, pg['title'])
        self._set(11, layout.summary_line(data))
        self._set(12, layout.tab_strip([p['title'] for p in pages], page))
        bars = pg.get('bars') or []
        cards = pg.get('cards') or []
        positions = layout.card_positions(len(cards), len(bars))
        for i in range(12):
            group = self.getControl(CARD_BASE + i * 10)
            if i >= len(positions):
                group.setVisible(False)
                continue
            c = cards[i]
            gid = CARD_BASE + i * 10
            group.setPosition(*positions[i])
            self._set(gid + 1, c.get('t', ''))
            big = self.getControl(gid + 2)
            big.setLabel(c.get('big', ''), textColor=layout.big_color(c.get('color')))
            self._set(gid + 3, c.get('u', ''))
            tb = self.getControl(gid + 4)
            if c.get('small'):
                tb.setPosition(24, 58)   # lijstkaart: de hele kaart voor tekst
                tb.setHeight(200)
            else:
                tb.setPosition(24, 182)
                tb.setHeight(80)
            tb.setText(c.get('sub', ''))
            group.setVisible(True)
        tops = layout.bar_row_tops(len(bars))
        for r, base in enumerate(BAR_ROWS):
            group = self.getControl(base)
            if r >= len(bars):
                group.setVisible(False)
                continue
            b = bars[r]
            group.setPosition(0, tops[r])
            self._set(base + 1, b.get('title', ''))
            self._set(base + 2, layout.bar_info([v for v in b['v']], b.get('unit', '')))
            labels = layout.MONTH_LABELS if b.get('labels') == 'maanden' else layout.HOUR_LABELS
            for j, text in enumerate(labels):
                self._set(base + 10 + j, text)
            geo = layout.bar_geometry(b['v'], b.get('c') or [])
            for i, g in enumerate(geo):
                img = self.getControl(base + 20 + i)
                if g is None:
                    img.setVisible(False)
                    continue
                x, y, h, color = g
                img.setPosition(x, y)
                img.setHeight(h)
                img.setColorDiffuse(color)
                img.setVisible(True)
            group.setVisible(True)
