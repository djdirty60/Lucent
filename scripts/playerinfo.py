# -*- coding: utf-8 -*-
"""Lucent: the player info screen (player menu > statistics button, Includes_Player.xml NuvioStatsPanel).

The helper calls tick() every second while the screen is open. It fills Window(Home).Property(lucent.pi.*):
title, time, the badges (b.*), the six tiles on the left (t1..t6), the rows (r.*), the CPU cores and the meters.
Bars are given as a step 0..40 (cores 0..27): Kodi cannot size a picture from a property.
Only the name of the server is shown as location, never the whole address (it can hold a login or a key).
"""
import json
import os
import re
import time
import urllib.parse
import zlib
import struct

import xbmc
import xbmcgui
import xbmcvfs

HOME = xbmcgui.Window(10000)
NL = xbmc.getLanguage(xbmc.ISO_639_1) == "nl"
P = "lucent.pi."
_STATE = {"hist": [], "path": None, "size": "", "rpc": 0.0, "tracks": {}, "maxclk": 0.0, "spark": 0, "open": False}
SPARK_DIR = "special://temp/lucent_pi/"


def t(en, nl):
    return nl if NL else en


def info(name):
    value = xbmc.getInfoLabel(name)
    return "" if value == name else value              # Kodi gives the name back for a label it does not know


def put(key, value):
    value = "" if value is None else str(value)
    if HOME.getProperty(P + key) != value:
        HOME.setProperty(P + key, value)


def num(text, default=0.0):
    m = re.search(r"-?\d+(?:[.,]\d+)?", text or "")
    return float(m.group(0).replace(",", ".")) if m else default


def step(percent, steps=40):
    try:
        return max(0, min(steps, round(float(percent) * steps / 100.0)))
    except (TypeError, ValueError):
        return 0


# ----------------------------------------------------------------------------- names
ACODEC = {"truehd_atmos": "TrueHD Atmos", "eac3_ddp_atmos": "Dolby Digital+ Atmos", "dtshd_ma_x_imax": "DTS:X IMAX",
          "dtshd_ma_x": "DTS:X", "truehd": "TrueHD", "dtshd_ma": "DTS-HD MA", "dtshd_hra": "DTS-HD HRA", "dts": "DTS",
          "eac3": "Dolby Digital+", "ac3": "Dolby Digital", "aac": "AAC", "flac": "FLAC", "opus": "Opus", "mp3": "MP3",
          "vorbis": "Vorbis", "mp2": "MP2"}
ABADGE = {"truehd_atmos": "TrueHD", "truehd": "TrueHD", "eac3_ddp_atmos": "DD+", "eac3": "DD+", "ac3": "DD",
          "dtshd_ma_x_imax": "DTS-HD MA", "dtshd_ma_x": "DTS-HD MA", "dtshd_ma": "DTS-HD MA", "dtshd_hra": "DTS-HD HRA",
          "dts": "DTS", "aac": "AAC", "flac": "FLAC", "opus": "OPUS", "mp3": "MP3"}
VCODEC = {"hevc": "HEVC", "h264": "H.264", "av1": "AV1", "vp9": "VP9", "mpeg2video": "MPEG-2", "vc1": "VC-1"}
CONTAINER = {"mkv": "Matroska (MKV)", "mp4": "MPEG-4 (MP4)", "m4v": "MPEG-4 (M4V)", "ts": "MPEG-TS", "m2ts": "Blu-ray (M2TS)",
             "avi": "AVI", "webm": "WebM", "mov": "QuickTime (MOV)", "iso": "ISO", "m3u8": "HLS (M3U8)", "mpd": "DASH (MPD)",
             "wmv": "WMV", "flv": "FLV"}
CHANNELS = {1: "1.0", 2: "2.0", 3: "2.1", 6: "5.1", 7: "6.1", 8: "7.1"}
LANG_NL = {"eng": "Engels", "dut": "Nederlands", "nld": "Nederlands", "ger": "Duits", "deu": "Duits", "fre": "Frans",
           "fra": "Frans", "spa": "Spaans", "ita": "Italiaans", "por": "Portugees", "jpn": "Japans", "kor": "Koreaans",
           "chi": "Chinees", "zho": "Chinees", "rus": "Russisch", "ara": "Arabisch", "tur": "Turks", "pol": "Pools",
           "swe": "Zweeds", "nor": "Noors", "dan": "Deens", "fin": "Fins", "ukr": "Oekraïens", "cze": "Tsjechisch",
           "ces": "Tsjechisch", "hin": "Hindi", "gre": "Grieks", "ell": "Grieks", "hun": "Hongaars", "heb": "Hebreeuws"}


def lang_name(code):
    code = (code or "").lower()
    if not code or code in ("und", "unk"):
        return ""
    if NL and code in LANG_NL:
        return LANG_NL[code]
    try:
        return xbmc.convertLanguage(code, xbmc.ENGLISH_NAME) or code.upper()
    except Exception:  # noqa: BLE001
        return code.upper()


def lang_short(code):
    try:
        two = xbmc.convertLanguage(code or "", xbmc.ISO_639_1)
    except Exception:  # noqa: BLE001
        two = ""
    return (two or code or "").upper()[:3]


def middle(text, keep=64):
    """A long file name with the middle left out: 'The.Expanse.S03E07.2160p … TrueHD.Atmos.7.1-FGT.mkv'."""
    if len(text) <= keep:
        return text
    head = keep * 55 // 100
    return f"{text[:head].rstrip('.')} … {text[-(keep - head - 3):].lstrip('.')}"


def location(path):
    """Only the server name (or the add-on, or 'local'), never the whole address."""
    if not path:
        return ""
    if path.startswith("plugin://"):
        addon = urllib.parse.urlparse(path).netloc
        try:
            import xbmcaddon
            return xbmcaddon.Addon(addon).getAddonInfo("name")
        except Exception:  # noqa: BLE001
            return addon
    parts = urllib.parse.urlparse(path)
    if parts.scheme in ("http", "https", "rtmp", "rtsp", "udp", "rtp", "mms"):
        host = (parts.hostname or "").lower()
        return host[4:] if host.startswith("www.") else host
    if parts.scheme in ("smb", "nfs", "ftp", "sftp", "dav", "davs"):
        return f"{parts.hostname or ''} · {parts.scheme.upper()}"
    return t("this device", "dit apparaat")


def local_size(path):
    if not path or "://" in path and not path.startswith(("smb://", "nfs://", "special://")):
        return ""
    try:
        size = xbmcvfs.Stat(path).st_size()
    except Exception:  # noqa: BLE001
        return ""
    if not size:
        return ""
    return f"{size / 1073741824:.1f} GB" if size >= 1073741824 else f"{size / 1048576:.0f} MB"


# ----------------------------------------------------------------------------- tracks (JSON-RPC, every 5 s)
def tracks(now):
    if now - _STATE["rpc"] < 5 and _STATE["tracks"]:
        return _STATE["tracks"]
    _STATE["rpc"] = now
    out = {}
    try:
        req = {"jsonrpc": "2.0", "id": 1, "method": "Player.GetProperties",
               "params": {"playerid": 1, "properties": ["currentaudiostream", "audiostreams", "currentsubtitle", "subtitles",
                                                        "subtitleenabled", "currentvideostream"]}}
        res = json.loads(xbmc.executeJSONRPC(json.dumps(req))).get("result") or {}
        out = res
    except Exception:  # noqa: BLE001
        pass
    _STATE["tracks"] = out
    return out


# ----------------------------------------------------------------------------- the bitrate graph (a small PNG)
def _png(width, height, rows):
    raw = b"".join(b"\x00" + bytes(r) for r in rows)

    def chunk(kind, data):
        c = struct.pack(">I", len(data)) + kind + data
        return c + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(raw, 6)) + chunk(b"IEND", b""))


def spark(values):
    """Area and line of the last values, 760 x 60 (shown at 380 x 30), colour #7CC4FF."""
    W, H = 760, 60
    vals = values[-40:]
    if len(vals) < 2:
        return ""
    lo, hi = min(vals), max(vals)
    span = (hi - lo) or max(hi, 1.0)
    ys = []
    for x in range(W):
        pos = x / (W - 1) * (len(vals) - 1)
        i = int(pos)
        f = pos - i
        v = vals[i] if i + 1 >= len(vals) else vals[i] * (1 - f) + vals[i + 1] * f
        ys.append(H - 4 - (v - lo) / span * (H - 12) - (H * 0.1 if hi == lo else 0))
    rows = []
    for y in range(H):
        row = bytearray(W * 4)
        for x in range(W):
            ly = ys[x]
            prev = ys[x - 1] if x else ly
            top, bot = min(ly, prev) - 2.5, max(ly, prev) + 2.5
            if top <= y <= bot:
                a = 255
            elif y > ly:
                a = 46
            else:
                continue
            row[x * 4:x * 4 + 4] = bytes((0x7C, 0xC4, 0xFF, a))
        rows.append(row)
    folder = xbmcvfs.translatePath(SPARK_DIR)
    os.makedirs(folder, exist_ok=True)
    _STATE["spark"] += 1
    name = f"spark_{int(time.time())}_{_STATE['spark']}.png"
    with open(os.path.join(folder, name), "wb") as handle:
        handle.write(_png(W, H, rows))
    for old in os.listdir(folder):
        if old != name and old.startswith("spark_"):
            try:
                if time.time() - os.path.getmtime(os.path.join(folder, old)) > 4:
                    os.remove(os.path.join(folder, old))
            except OSError:
                pass
    return SPARK_DIR + name


# ----------------------------------------------------------------------------- one update
def visible():
    return xbmc.getCondVisibility("Skin.HasSetting(nuvio.osdstats) + Player.HasVideo")


def tick():
    if not visible():
        if _STATE["open"]:
            _STATE.update(open=False, hist=[])
        return
    _STATE["open"] = True
    now = time.time()
    path = info("Player.Filenameandpath")
    if path != _STATE["path"]:
        _STATE.update(path=path, hist=[], size=local_size(path), rpc=0.0)

    # header
    show = info("VideoPlayer.TVShowTitle")
    title = info("VideoPlayer.Title")
    if show:
        s, e = info("VideoPlayer.Season"), info("VideoPlayer.Episode")
        se = f"S{s} E{e}" if s and e else ""
        put("title", " · ".join(x for x in (show, se, title) if x))
    else:
        year = info("VideoPlayer.Year")
        put("title", f"{title} ({year})" if title and year else title or info("Player.Filename"))
    tm = f"{info('Player.Time')} / {info('Player.Duration')}" if info("Player.Duration") else info("Player.Time")
    try:
        chap, chaps = int(info("Player.Chapter") or 0), int(info("Player.ChapterCount") or 0)
    except ValueError:
        chap = chaps = 0
    if chaps > 1 and chap:
        tm += t(f" · chapter {chap} of {chaps}", f" · hoofdstuk {chap} van {chaps}")
    put("time", tm)

    # video facts
    w, h = info("Player.Process(videowidth)").replace(",", "").replace(".", ""), info("Player.Process(videoheight)").replace(",", "").replace(".", "")
    fps = info("Player.Process(videofps)")
    res = info("VideoPlayer.VideoResolution")
    res_badge = {"8K": "8K", "4K": "4K", "1080": "1080p", "720": "720p", "576": "576p", "540": "540p", "480": "480p"}.get(res, res.upper())
    hdr = info("VideoPlayer.HdrType").lower()
    detail = info("VideoPlayer.HdrDetail")
    prof = re.search(r"(\d+)", detail or "")
    layer = "FEL" if "FEL" in (detail or "").upper() else "MEL" if "MEL" in (detail or "").upper() else ""
    pix = info("Player.Process(pixformat)")
    ten = bool(re.search(r"10|12", pix or ""))
    vcodec = info("VideoPlayer.VideoCodec").lower()
    vname = VCODEC.get(vcodec, vcodec.upper())
    fname = info("Player.Filename")

    # audio facts
    acodec = info("VideoPlayer.AudioCodec").lower()
    try:
        chn = int(info("VideoPlayer.AudioChannels") or 0)
    except ValueError:
        chn = 0
    chs = CHANNELS.get(chn, f"{chn}.0" if chn else "")
    aname_stream = info("VideoPlayer.AudioName") or ""
    atmos = "atmos" in acodec or "atmos" in aname_stream.lower()
    dtsx = acodec.startswith("dtshd_ma_x") or "dts:x" in aname_stream.lower() or "dts-x" in aname_stream.lower()
    along = ACODEC.get(acodec, acodec.upper())
    if atmos and "Atmos" not in along:
        along += " Atmos"
    rate = float(re.sub(r"\D", "", info("Player.Process(audiosamplerate)") or "") or 0)   # '44,100' / '48.000': thousands marks
    bits = info("Player.Process(audiobitspersample)")

    # badges
    put("b.res", res_badge)
    if hdr == "dolbyvision":
        put("b.dv", "DOLBY VISION" + (f" P{prof.group(1)}" if prof else "") + (f" {layer}" if layer else ""))
        put("b.hdr", "")
    else:
        put("b.dv", "")
        put("b.hdr", {"hdr10": "HDR10", "hdr10plus": "HDR10+", "hlg": "HLG"}.get(hdr, ""))
    put("b.vc", f"{vname} 10-bit" if vname and ten else vname)
    put("b.remux", "REMUX" if re.search(r"remux", fname or "", re.I) else "")
    put("b.ac", ABADGE.get(acodec, acodec.upper()))
    put("b.imm", f"ATMOS {chs}".strip() if atmos else f"DTS:X {chs}".strip() if dtsx else "")
    put("b.ch", "" if (atmos or dtsx) else chs)
    subs_on = xbmc.getCondVisibility("VideoPlayer.SubtitlesEnabled")
    sl = info("VideoPlayer.SubtitlesLanguage")
    put("b.sub", t(f"{lang_short(sl)} subtitles", f"{lang_short(sl)} ondertitels") if subs_on and sl else "")

    # tiles
    hdr_word = {"dolbyvision": "Dolby Vision", "hdr10": "HDR10", "hdr10plus": "HDR10+", "hlg": "HLG"}.get(hdr, "")
    put("t1.big", f"{res_badge} HDR" if hdr_word else res_badge)
    put("t1.sub", " · ".join(x for x in (f"{w}×{h}" if w and h else "", fps) if x))
    put("t2.big", hdr_word or "SDR")
    put("t2.sub", t(f"profile {prof.group(1)}", f"profiel {prof.group(1)}") + (f" {layer}" if layer else "") if hdr == "dolbyvision" and prof else "")
    put("t3.big", (f"Atmos {chs}" if atmos else f"DTS:X {chs}" if dtsx else chs or along).strip())
    khz = (f"{rate / 1000:g} kHz" if rate else "")
    put("t3.sub", " · ".join(x for x in (ABADGE.get(acodec, along) if (atmos or dtsx or chs) else "", khz) if x))
    vbr = num(info("Player.Process(videolivebitrate)"))
    abr_k = float(re.sub(r"\D", "", info("Player.Process(audiolivebitrate)") or "") or 0)
    abr = abr_k / 1024.0
    total = vbr + abr
    if total:
        _STATE["hist"] = (_STATE["hist"] + [total])[-40:]
    put("t4.big", f"{total:.1f} Mb/s" if total else "–")
    put("t4.sub", t(f"picture {vbr:.1f} · audio {abr:.1f}", f"beeld {vbr:.1f} · audio {abr:.1f}") if total else "")
    if len(_STATE["hist"]) >= 2:
        try:
            put("spark", spark(_STATE["hist"]))
        except Exception as error:  # noqa: BLE001
            xbmc.log(f"[skin.lucent] playerinfo spark: {error}", xbmc.LOGINFO)
    cache = num(info("Player.CacheLevel"))
    ahead = ""
    try:
        total_s = xbmc.Player().getTotalTime()
        pc, pp = num(info("Player.ProgressCache")), num(info("Player.Progress"))
        if total_s and pc > pp:
            ahead_s = int((pc - pp) / 100.0 * total_s)
            ahead = t(f"{ahead_s} s ahead", f"{ahead_s} s vooruit") if ahead_s < 600 else t(f"{ahead_s // 60} min ahead", f"{ahead_s // 60} min vooruit")
    except Exception:  # noqa: BLE001
        pass
    put("t5.big", f"{cache:.0f}%")
    put("t5.sub", ahead)
    put("t5.bar", step(cache))

    # system
    cpu_text = info("System.CpuUsage")
    cores = [float(x) for x in re.findall(r"#\d+:\s*([\d.,]+)%", cpu_text.replace(",", "."))]
    avg = sum(cores) / len(cores) if cores else num(cpu_text)
    put("cores", min(len(cores), 8))
    for i in range(8):
        put(f"core{i}", max(1, min(27, round(cores[i] * 27 / 100))) if i < len(cores) else "")
    put("cores.label", t(f"CPU per core · avg. {avg:.0f}%", f"CPU per kern · gem. {avg:.0f}%") if cores else t(f"CPU · {avg:.0f}%", f"CPU · {avg:.0f}%"))
    ct, gt = num(info("System.CPUTemperature"), -1), num(info("System.GPUTemperature"), -1)
    mem_p = num(info("System.Memory(used.percent)"))
    mem_u = info("System.Memory(used)").replace("MB", " MB").replace("GB", " GB").replace("  ", " ")
    put("t6.big", f"CPU {avg:.0f}%")
    put("t6.sub", " · ".join(x for x in (f"{ct:.0f} °C" if ct >= 0 else "", t(f"{mem_p:.0f}% memory", f"{mem_p:.0f}% geheugen")) if x))
    put("t6.bar", step(mem_p))
    put("m.ct", f"{ct:.0f} °C" if ct >= 0 else "–")
    put("m.ct.bar", step(ct) if ct >= 0 else 0)
    put("m.gt", f"{gt:.0f} °C" if gt >= 0 else "–")
    put("m.gt.bar", step(gt) if gt >= 0 else 0)
    put("m.mem", f"{mem_p:.0f}% · {mem_u}".strip(" ·"))
    put("m.mem.bar", step(mem_p))
    clk = num(info("System.CpuFrequency"))
    if not _STATE["maxclk"]:
        try:
            with open("/sys/devices/system/cpu/cpu0/cpufreq/cpuinfo_max_freq") as handle:
                _STATE["maxclk"] = int(handle.read().strip()) / 1000.0
        except (OSError, ValueError):
            _STATE["maxclk"] = 0.0
    _STATE["maxclk"] = max(_STATE["maxclk"], clk)
    put("m.clk", f"{clk:.0f} MHz" if clk else "–")
    put("m.clk.bar", step(clk / _STATE["maxclk"] * 100) if clk and _STATE["maxclk"] else 0)
    rfps = num(info("System.FPS"))
    vfps = num(fps)
    put("m.fps", f"{rfps:.2f} fps" if rfps else "–")
    put("m.fps.bar", step(min(100.0, rfps / vfps * 100)) if rfps and vfps else 0)
    vq = num(info("Player.Process(videoqueuelevel)"))
    aq = num(info("Player.Process(audioqueuelevel)"))
    put("m.vq", f"{vq:.0f}%")
    put("m.vq.bar", step(vq))

    # rows: source
    put("r.file", middle(fname or ""))
    stream = xbmc.getCondVisibility("Player.IsInternetStream")
    loc = location(path)
    put("r.loc", f"{loc} · stream" if stream and loc else loc)
    ext = os.path.splitext(urllib.parse.urlparse(fname or "").path)[1].lower().lstrip(".")
    put("r.cont", " · ".join(x for x in (CONTAINER.get(ext, ext.upper()), _STATE["size"]) if x))
    put("r.rate", t(f"{total:.1f} Mb/s · picture {vbr:.1f} · audio {abr:.1f}", f"{total:.1f} Mb/s · beeld {vbr:.1f} · audio {abr:.1f}") if total else "–")
    # video
    scan = info("Player.Process(videoscantype)").lower()
    scan_word = t("progressive", "progressief") if scan.startswith("p") else t("interlaced", "geïnterlaced") if scan.startswith("i") else ""
    put("r.res", " · ".join(x for x in (f"{w}×{h}" if w and h else "", f"{fps} fps" if fps else "", scan_word) if x))
    if hdr == "dolbyvision":
        put("r.hdr", " · ".join(x for x in ("Dolby Vision", (t("profile ", "profiel ") + prof.group(1) + (f" {layer}" if layer else "")) if prof else "", "BT.2020") if x))
    elif hdr_word:
        put("r.hdr", f"{hdr_word} · BT.2020")
    else:
        put("r.hdr", "SDR")
    dar = info("Player.Process(videodar)")
    put("r.fmt", " · ".join(x for x in (pix, f"{dar}:1" if dar else "") if x))
    hw = xbmc.getCondVisibility("Player.Process(videohwdecoder)")
    put("r.vdec", " · ".join(x for x in (info("Player.Process(videodecoder)"), "hardware" if hw else "software") if x))
    disp = info("System.ScreenResolution")
    disp = re.sub(r"(\d)\s*x\s*(\d)", r"\1×\2", disp).replace(" - ", " · ")
    disp = re.sub(r"(\d)Hz", r"\1 Hz", disp)
    put("r.disp", disp)
    put("r.vq", f"{vq:.0f}%")
    put("r.vq.dot", "low" if vq <= 20 else "ok")
    # audio
    tr = tracks(now)
    streams = tr.get("audiostreams") or []
    cur = tr.get("currentaudiostream") or {}
    idx = next((n for n, s in enumerate(streams, 1) if s.get("index") == cur.get("index")), 0)
    bits_track = [t(f"{idx} of {len(streams)}", f"{idx} van {len(streams)}") if idx and len(streams) > 1 else "",
                  lang_name(cur.get("language") or info("VideoPlayer.AudioLanguage")), cur.get("name") or aname_stream]
    put("r.atrack", " · ".join(x for x in bits_track if x))
    ch_word = (t(f"{chn} channel ({chs})", f"{chn} kanaal ({chs})") if chn == 1 else
               t(f"{chn} channels ({chs})", f"{chn} kanalen ({chs})")) if chn else ""
    put("r.afmt", " · ".join(x for x in (along, ch_word) if x))
    put("r.aq", " · ".join(x for x in (khz, f"{bits} bit" if bits and bits != "0" else "") if x))
    adec = info("Player.Process(audiodecoder)")
    adec = "" if adec.lower() in ("unknown", "none") else adec
    if adec.lower().startswith("pt-"):
        adec += t(" · passthrough to receiver", " · passthrough naar receiver")
    put("r.adec", adec)
    put("r.aqueue", f"{aq:.0f}%")
    put("r.aqueue.dot", "low" if aq <= 20 else "ok")
    # subtitles
    subs = tr.get("subtitles") or []
    cs = tr.get("currentsubtitle") or {}
    if tr.get("subtitleenabled") and cs:
        sidx = next((n for n, s in enumerate(subs, 1) if s.get("index") == cs.get("index")), 0)
        codec = (cs.get("codec") or "").upper().replace("SUBRIP", "SRT")
        put("r.sub", " · ".join(x for x in (lang_name(cs.get("language")) or cs.get("name"), codec,
                                             t(f"{sidx} of {len(subs)}", f"{sidx} van {len(subs)}") if sidx else "") if x))
    else:
        put("r.sub", t("Off", "Uit") + (t(f" · {len(subs)} available", f" · {len(subs)} beschikbaar") if subs else ""))
    # network
    put("r.buf", " · ".join(x for x in (f"{cache:.0f}%", ahead) if x))
    put("r.buf.dot", "low" if cache <= 20 else "ok")
    put("r.type", t("Stream · internet", "Stream · internet") if stream else t("Local file", "Lokaal bestand"))
