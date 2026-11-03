# -*- coding: utf-8 -*-
"""Logica voor meldingen op de tv. Geen Kodi nodig, dus te testen."""
import time

KINDS = ('info', 'warn', 'good')
LOG_EVERY = 600  # maximaal een logregel per 10 minuten bij fouten


class Notifier(object):
    """Haalt nieuwe meldingen op en geeft ze door aan show().

    fetch(since)  -> dict {"now", "last", "items": [...]}  (since is None bij de eerste keer)
    show(title, text, kind, seconds)
    settings()    -> dict met enabled, seconds, quiet, warn_only
    playing()     -> True als er video speelt
    log(text)
    """

    def __init__(self, fetch, show, settings, playing=lambda: False, log=lambda t: None, clock=time.time):
        self.fetch, self.show, self.settings = fetch, show, settings
        self.playing, self.log, self.clock = playing, log, clock
        self.last = None          # hoogste melding-id dat we al kennen
        self._last_log = 0.0

    def _warn(self, text):
        now = self.clock()
        if now - self._last_log >= LOG_EVERY:
            self._last_log = now
            self.log(text)

    def poll(self):
        """Een ronde. Geeft het aantal getoonde meldingen terug."""
        cfg = self.settings()
        if not cfg.get('enabled', True):
            self.last = None      # bij weer aanzetten opnieuw beginnen zonder oude meldingen
            return 0
        try:
            data = self.fetch(self.last)
            if not isinstance(data, dict):
                raise ValueError('onverwacht antwoord')
            items = [i for i in (data.get('items') or []) if isinstance(i, dict) and isinstance(i.get('id'), int)]
            top = data.get('last')
            if not isinstance(top, int):
                top = max([i['id'] for i in items] or [0])
        except Exception as exc:  # noqa: BLE001
            self._warn('Solis meldingen: ophalen mislukt: %s' % exc)
            return 0
        if self.last is None or top < self.last:
            # eerste keer, of de server is opnieuw begonnen: alleen onthouden, niets tonen
            self.last = top
            return 0
        shown = 0
        for item in sorted(items, key=lambda i: i['id']):
            if item['id'] <= self.last:
                continue
            self.last = item['id']
            kind = item.get('kind')
            title = str(item.get('title') or '').strip()
            if kind not in KINDS or not title:
                continue
            if cfg.get('warn_only') and kind == 'info':
                continue
            if cfg.get('quiet') and self.playing():
                continue
            try:
                self.show(title, str(item.get('text') or ''), kind, cfg.get('seconds', 8))
                shown += 1
            except Exception as exc:  # noqa: BLE001
                self._warn('Solis meldingen: tonen mislukt: %s' % exc)
        self.last = max(self.last, top)
        return shown


def as_bool(value, default=False):
    if value is None or value == '':
        return default
    return str(value).strip().lower() in ('true', '1', 'yes', 'on')


def as_int(value, default, low=1, high=60):
    try:
        return max(low, min(high, int(value)))
    except (TypeError, ValueError):
        return default
