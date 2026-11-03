# -*- coding: utf-8 -*-
"""Rekenwerk voor de schermindeling. Geen Kodi nodig, dus te testen."""

COLS = 4
X0 = 80
CARD_W, CARD_H = 410, 270
GAP_X, GAP_Y = 450, 300
BAR_X0, BAR_STEP, BAR_W = 110, 70, 48
BAR_BASE, BAR_MAX = 216, 170

COLORS = {
    'g': 'FF1FAE6B',   # goed, goedkoop
    'r': 'FFE5484D',   # duur of let op
    'n': 'FF3B82F6',   # negatief
    'd': 'FF5A6490',   # gewoon
    'o': 'FFFF9F1C',   # zon
    'p': 'FF7A5CFF',   # verbruik
    '': 'FF3A4160',
}
TEXT = 'FFF2F4FB'
GOOD = 'FF3DD68C'
BAD = 'FFFF6B6F'


def card_positions(count, bar_rows):
    """Posities (x, y) van de kaarten. Hoeveel er passen hangt af van het aantal grafieken."""
    if bar_rows == 0:
        top, gap, limit = 160, 290, 12
    elif bar_rows == 1:
        top, gap, limit = 160, 280, 8
    else:
        top, gap, limit = 160, 280, 4
    return [(X0 + (i % COLS) * GAP_X, top + (i // COLS) * gap) for i in range(min(count, limit))]


def bar_row_tops(bar_rows):
    if bar_rows >= 2:
        return [445, 735]
    if bar_rows == 1:
        return [730]
    return []


def big_color(code):
    return {'g': GOOD, 'r': BAD}.get(code or '', TEXT)


def bar_geometry(values, codes):
    """Per balk: (x, y, hoogte, kleur) of None als er geen waarde is."""
    known = [abs(v) for v in values if v is not None]
    top = max(known) if known else 0
    out = []
    for i in range(24):
        v = values[i] if i < len(values) else None
        if v is None or top <= 0:
            out.append(None)
            continue
        h = max(4, int(round(abs(v) / top * BAR_MAX)))
        code = codes[i] if i < len(codes) else ''
        out.append((BAR_X0 + i * BAR_STEP, BAR_BASE - h, h, COLORS.get(code, COLORS[''])))
    return out


def bar_info(values, unit):
    known = [v for v in values if v is not None]
    if not known:
        return ''
    def f(x):
        return ('%.1f' % x).replace('.', ',')
    return 'laagst %s · hoogst %s %s' % (f(min(known)), f(max(known)), unit)


def tab_strip(titles, current):
    parts = []
    for i, t in enumerate(titles):
        if i == current:
            parts.append('[COLOR FFF2F4FB][B]%s[/B][/COLOR]' % t)
        else:
            parts.append('[COLOR FF6F7794]%s[/COLOR]' % t)
    return '   '.join(parts)


def summary_line(data):
    mode = {'normaal': 'Normaal', 'geen-export': 'Geen export', 'uit': 'Uit'}.get(data.get('mode'), data.get('mode') or '')
    watts = int(round(data.get('watts') or 0))
    online = 'online' if data.get('online') else 'omvormer slaapt'
    return '%s W · %s · %s' % (('{:,}'.format(watts)).replace(',', '.'), mode, online)


MONTH_LABELS = ['jan', 'apr', 'jul', 'okt', '', '', '', '']
HOUR_LABELS = ['0', '3', '6', '9', '12', '15', '18', '21']
