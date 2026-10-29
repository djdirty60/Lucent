# -*- coding: utf-8 -*-
"""Lucent: the background takes on the colour of the poster you are on.

Run by the Lucent helper (helper.py, TintJob). When a poster has had the focus for a
moment it fetches a small version of it (TMDB w92 / fanart.tv preview), works out its main colour and sets
Window(home).Property(lucent.tint.a / .b) as AARRGGBB. The skin draws a soft glow in that colour and fades
between the two slots, so the colour flows from one poster to the next.

Kodi's Python has no image library, so the colour is read straight from the JPEG: only the DC value (the
average) of every 8x8 block is decoded, which is enough for a colour and fast on any box.
"""
import colorsys
import json
import re
import struct
import time
import urllib.parse
import urllib.request

import xbmc
import xbmcgui
import xbmcvfs

HOME = xbmcgui.Window(10000)
CACHE_FILE = "special://profile/addon_data/skin.lucent/tint_cache.json"
CACHE_MAX = 600
ALPHA = "A0"


def log(text):
    xbmc.log(f"[skin.lucent] tint: {text}", xbmc.LOGINFO)


# ----------------------------------------------------------------------------- JPEG: block averages only
class _Bits:
    def __init__(self, data, pos):
        self.d, self.p, self.acc, self.n = data, pos, 0, 0
        self.marker = None

    def _byte(self):
        if self.marker is not None:
            return 0
        b = self.d[self.p] if self.p < len(self.d) else 0xFF
        self.p += 1
        if b == 0xFF:
            nxt = self.d[self.p] if self.p < len(self.d) else 0xD9
            if nxt == 0:
                self.p += 1
            else:
                self.marker = nxt
                self.p -= 1
                return 0
        return b

    def bit(self):
        if self.n == 0:
            self.acc, self.n = self._byte(), 8
        self.n -= 1
        return (self.acc >> self.n) & 1

    def bits(self, k):
        v = 0
        for _ in range(k):
            v = (v << 1) | self.bit()
        return v

    def restart(self):
        """Skip to after the next RSTn marker."""
        self.n = 0
        self.marker = None
        while self.p < len(self.d) - 1:
            if self.d[self.p] == 0xFF and 0xD0 <= self.d[self.p + 1] <= 0xD7:
                self.p += 2
                return
            self.p += 1


def _huff(lengths, symbols):
    table, code, k = {}, 0, 0
    for size in range(1, 17):
        for _ in range(lengths[size - 1]):
            table[(size, code)] = symbols[k]
            k += 1
            code += 1
        code <<= 1
    return table


def _decode(bits, table):
    code = 0
    for size in range(1, 17):
        code = (code << 1) | bits.bit()
        sym = table.get((size, code))
        if sym is not None:
            return sym
    raise ValueError("bad huffman code")


def _extend(v, s):
    return v - (1 << s) + 1 if s and v < (1 << (s - 1)) else v


def block_colours(data):
    """List of (r, g, b) per 8x8 luma block (chroma taken from its MCU)."""
    if data[:2] != b"\xff\xd8":
        raise ValueError("not a JPEG")
    pos, qt, dc_t, ac_t, comps, frame = 2, {}, {}, {}, [], None
    restart = 0
    dc_vals = {}            # comp id -> {(bx, by): value}
    while pos < len(data) - 4:
        if data[pos] != 0xFF:
            pos += 1
            continue
        marker = data[pos + 1]
        pos += 2
        if marker in (0xD8, 0x01) or 0xD0 <= marker <= 0xD7:
            continue
        if marker == 0xD9:
            break
        length = struct.unpack(">H", data[pos:pos + 2])[0]
        seg = data[pos + 2:pos + length]
        if marker == 0xDB:
            i = 0
            while i < len(seg):
                pq, tq = seg[i] >> 4, seg[i] & 15
                qt[tq] = seg[i + 1] if pq == 0 else struct.unpack(">H", seg[i + 1:i + 3])[0]
                i += 1 + (64 if pq == 0 else 128)
        elif marker == 0xC4:
            i = 0
            while i < len(seg):
                tc, th = seg[i] >> 4, seg[i] & 15
                lengths = list(seg[i + 1:i + 17])
                n = sum(lengths)
                table = _huff(lengths, list(seg[i + 17:i + 17 + n]))
                (dc_t if tc == 0 else ac_t)[th] = table
                i += 17 + n
        elif marker == 0xDD:
            restart = struct.unpack(">H", seg[:2])[0]
        elif marker in (0xC0, 0xC1, 0xC2):
            frame = "progressive" if marker == 0xC2 else "baseline"
            height, width = struct.unpack(">HH", seg[1:5])
            comps = []
            for c in range(seg[5]):
                cid, hv, tq = seg[6 + 3 * c], seg[7 + 3 * c], seg[8 + 3 * c]
                comps.append({"id": cid, "h": hv >> 4, "v": hv & 15, "tq": tq})
            hmax = max(c["h"] for c in comps)
            vmax = max(c["v"] for c in comps)
            mcux = (width + 8 * hmax - 1) // (8 * hmax)
            mcuy = (height + 8 * vmax - 1) // (8 * vmax)
            for c in comps:
                c["bw"] = (width * c["h"] // hmax + 7) // 8
                c["bh"] = (height * c["v"] // vmax + 7) // 8
                dc_vals[c["id"]] = {}
        elif marker in (0xC3, 0xC5, 0xC6, 0xC7, 0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF):
            raise ValueError("unsupported JPEG")
        elif marker == 0xDA:
            ns = seg[0]
            scomps = []
            for k in range(ns):
                cid, t = seg[1 + 2 * k], seg[2 + 2 * k]
                comp = next(c for c in comps if c["id"] == cid)
                scomps.append((comp, t >> 4, t & 15))
            ss, se, ah_al = seg[1 + 2 * ns], seg[2 + 2 * ns], seg[3 + 2 * ns]
            ah, al = ah_al >> 4, ah_al & 15
            bits = _Bits(data, pos + length)
            if frame == "progressive" and not (ss == 0 and ah == 0):
                # refinement / AC scans: not needed; skip the entropy data
                pos = _skip_entropy(data, pos + length)
                continue
            pred = {c["id"]: 0 for c, _, _ in scomps}
            count = 0

            def unit(comp, dct, act, bx, by):
                s = _decode(bits, dc_t[dct])
                diff = _extend(bits.bits(s), s)
                pred[comp["id"]] += diff
                dc_vals[comp["id"]][(bx, by)] = pred[comp["id"]] << al if frame == "progressive" else pred[comp["id"]]
                if frame == "baseline":
                    k = 1
                    table = ac_t[act]
                    while k < 64:
                        rs = _decode(bits, table)
                        r, s2 = rs >> 4, rs & 15
                        if s2 == 0:
                            if r != 15:
                                break
                            k += 16
                            continue
                        k += r
                        bits.bits(s2)
                        k += 1

            def maybe_restart():
                nonlocal count
                if restart:
                    count += 1
                    if count % restart == 0:
                        bits.restart()
                        for key in pred:
                            pred[key] = 0

            if ns == 1:
                comp, dct, act = scomps[0]
                for by in range(comp["bh"]):
                    for bx in range(comp["bw"]):
                        unit(comp, dct, act, bx, by)
                        maybe_restart()
            else:
                for my in range(mcuy):
                    for mx in range(mcux):
                        for comp, dct, act in scomps:
                            for v in range(comp["v"]):
                                for h in range(comp["h"]):
                                    unit(comp, dct, act, mx * comp["h"] + h, my * comp["v"] + v)
                        maybe_restart()
            pos = _skip_entropy(data, bits.p)
            if all(dc_vals[c["id"]] for c in comps):
                break
            continue
        pos += length
    if not comps or not dc_vals[comps[0]["id"]]:
        raise ValueError("no image data")
    y = comps[0]
    hmax = max(c["h"] for c in comps)
    vmax = max(c["v"] for c in comps)
    out = []
    for (bx, by), dcy in dc_vals[y["id"]].items():
        Y = dcy * qt.get(y["tq"], 1) / 8 + 128
        if len(comps) >= 3:
            vals = []
            for c in comps[1:3]:
                cx = bx * c["h"] // hmax if y["h"] == hmax else bx
                cy = by * c["v"] // vmax if y["v"] == vmax else by
                vals.append(dc_vals[c["id"]].get((cx, cy), 0) * qt.get(c["tq"], 1) / 8)
            cb, cr = vals
        else:
            cb = cr = 0
        r = Y + 1.402 * cr
        g = Y - 0.344136 * cb - 0.714136 * cr
        b = Y + 1.772 * cb
        out.append(tuple(max(0, min(255, int(x))) for x in (r, g, b)))
    return out


def _skip_entropy(data, pos):
    """Position of the next real marker after entropy coded data."""
    while pos < len(data) - 1:
        if data[pos] == 0xFF and data[pos + 1] != 0 and not (0xD0 <= data[pos + 1] <= 0xD7):
            return pos
        pos += 1
    return pos


def main_colour(pixels):
    """The most striking colour: a hue histogram weighted by saturation, then made calm enough for a glow."""
    bins = {}
    for r, g, b in pixels:
        h, s, v = colorsys.rgb_to_hsv(r / 255, g / 255, b / 255)
        if v < 0.12 or (s < 0.15 and v > 0.9):
            continue
        w = (s ** 1.5) * (0.4 + v)
        k = int(h * 18) % 18
        acc = bins.setdefault(k, [0.0, 0.0, 0.0, 0.0])
        acc[0] += r * w
        acc[1] += g * w
        acc[2] += b * w
        acc[3] += w
    if not bins:
        return None
    best = max(bins.values(), key=lambda a: a[3])
    if best[3] <= 0:
        return None
    r, g, b = (best[i] / best[3] / 255 for i in range(3))
    h, s, v = colorsys.rgb_to_hsv(r, g, b)
    s = min(max(s, 0.35), 0.85)
    v = min(max(v, 0.55), 0.85)
    r, g, b = colorsys.hsv_to_rgb(h, s, v)
    return "%02X%02X%02X" % (int(r * 255), int(g * 255), int(b * 255))


# ----------------------------------------------------------------------------- where to get a small picture
def small_url(art):
    if not art:
        return ""
    if art.startswith("image://"):
        art = urllib.parse.unquote(art[8:].rstrip("/"))
    m = re.match(r"(https?://image\.tmdb\.org/t/p/)[^/]+(/.+)$", art)
    if m:
        return f"{m.group(1)}w92{m.group(2)}"
    if "assets.fanart.tv/fanart/" in art:
        return art.replace("/fanart/", "/preview/")
    return ""


def fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": "Kodi skin.lucent"})
    with urllib.request.urlopen(req, timeout=6) as resp:
        return resp.read(400000)


class Cache:
    def __init__(self):
        self.data = {}
        try:
            with xbmcvfs.File(CACHE_FILE) as fh:
                self.data = json.loads(fh.read() or "{}")
        except Exception:  # noqa: BLE001
            self.data = {}
        self.dirty = 0

    def get(self, key):
        return self.data.get(key)

    def put(self, key, value):
        self.data[key] = value
        self.dirty += 1
        if len(self.data) > CACHE_MAX:
            for k in list(self.data)[: len(self.data) - CACHE_MAX]:
                del self.data[k]
        if self.dirty >= 10:
            self.save()

    def save(self):
        if not self.dirty:
            return
        try:
            xbmcvfs.mkdirs("special://profile/addon_data/skin.lucent/")
            with xbmcvfs.File(CACHE_FILE, "w") as fh:
                fh.write(json.dumps(self.data))
            self.dirty = 0
        except Exception:  # noqa: BLE001
            pass


def colour_for(art, cache):
    url = small_url(art)
    if not url:
        return None
    hit = cache.get(url)
    if hit is not None:
        return hit or None
    try:
        raw = fetch(url)
    except Exception as error:  # noqa: BLE001 - offline or slow: not remembered, tried again next time
        log(f"{url}: {error}")
        return None
    try:
        colour = main_colour(block_colours(raw))
    except Exception:  # noqa: BLE001 - a picture that cannot be read: remembered as "no colour"
        colour = None
    cache.put(url, colour or "")
    return colour


# ----------------------------------------------------------------------------- the service
ACTIVE = "Window.IsActive(home) | Window.IsActive(videos) | Window.IsActive(movieinformation)"


_SKIPPED = {"last": ""}


def focused_art():
    first = ""
    for name in ("ListItem.Art(poster)", "ListItem.Art(tvshow.poster)", "ListItem.Art(season.poster)",
                 "ListItem.Art(fanart)", "ListItem.Art(thumb)"):
        art = xbmc.getInfoLabel(name)
        first = first or art
        if small_url(art):
            return art
    if first and first != _SKIPPED["last"]:
        _SKIPPED["last"] = first
        log(f"no small picture for {first[:120]}")
    return ""


def set_colour(colour, state):
    if colour == state["shown"]:
        return
    state["shown"] = colour
    log(f"colour {colour or '-'}")
    if not colour:
        HOME.clearProperty("lucent.tint.slot")
        return
    slot = "b" if HOME.getProperty("lucent.tint.slot") == "a" else "a"
    HOME.setProperty(f"lucent.tint.{slot}", ALPHA + colour)
    HOME.setProperty("lucent.tint.slot", slot)


class TintJob:
    """The poster colour, one small step at a time (the Lucent helper calls tick() about 4 times a second)."""

    def __init__(self):
        self.cache = Cache()
        self.state = {"art": "", "since": 0.0, "done": "", "shown": None}

    def wanted(self):
        return not xbmc.getCondVisibility("Skin.HasSetting(lucent.tint.off) | Skin.HasSetting(lucent.lite)")

    def active(self):
        return xbmc.getCondVisibility(f"[{ACTIVE}] + ![Player.HasVideo + Window.IsActive(fullscreenvideo)] + !Container.Scrolling")

    def tick(self):
        """One step; returns True while the colour is being followed (then the helper looks again soon)."""
        if not self.wanted():
            set_colour("", self.state)
            return False
        if not self.active():
            return False
        try:
            art = focused_art()
            now = time.time()
            state = self.state
            if art != state["art"]:
                state["art"], state["since"] = art, now
            elif art and art != state["done"] and now - state["since"] > 0.35:
                state["done"] = art
                colour = colour_for(art, self.cache)
                if colour:
                    set_colour(colour, state)
        except Exception as error:  # noqa: BLE001 - never let the helper die
            log(f"error: {error}")
        return True

    def save(self):
        self.cache.save()
