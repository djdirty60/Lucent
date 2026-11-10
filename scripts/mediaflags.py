"""Lucent: media flags in the lists with the big picture (issue #9; Settings > Lucent > Media flags in the lists).

The title under the cursor gets the same flags as the player (4K, Dolby Vision, HEVC, Atmos, 7.1 ...) under its scores,
plus small labels with the languages of the sound and the subtitles. Films and episodes: what Kodi knows of the file.
A series or season: Lucent asks the library for its episodes and shows the quality most of them have, with "mostly"
when they are not all the same.
The helper calls tick() several times a second. Fills Window(home).Property(lucent.mf.*):
  img1..img6  flag images in player order     alang / slang  languages (EN · NL)
  t1..t6 / c1..c6 / k1..k6  the same flags as coloured text badges (text, badge colour, text colour), always sharp
  most        '1' when it is what most episodes have          for  the title the flags belong to
"""
import json
import time
from collections import Counter

import xbmc
import xbmcgui

HOME = xbmcgui.Window(10000)
OFF = "Skin.HasSetting(lucent.mf.off)"
P = "lucent.mf."
PROPS = tuple(f"{k}{i}" for k in ("img", "t", "c", "k") for i in range(1, 7)) + ("alang", "slang", "most", "for")
STATE = {"id": "", "since": 0.0, "done": ""}
SHOW_CACHE = {}                                   # 'tvshow:12' / 'season:12:3' -> flags, for this session

RES = [("8k", "8K", "8k"), ("4k", "4K", "4k"), ("1080", "1080P", "1080"), ("720", "720P", "720"), ("sd", "SD", "sd")]
HDR = {"dolbyvision": ("DV", "dolbyvision"), "hdr10plus": ("HDR10+", "hdr10plus"), "hdr10": ("HDR10", "hdr10"), "hlg": ("HLG", "hlg")}
VCODEC = {"hevc": ("HEVC", "hevc"), "h265": ("HEVC", "hevc"), "av1": ("AV1", "av1"), "h264": ("AVC", "h264"), "avc1": ("AVC", "h264"),
          "vp9": ("VP9", "vp9")}
CH = {8: ("7.1", "71"), 7: ("6.1", "61"), 6: ("5.1", "51"), 2: ("2.0", "20"), 1: ("1.0", "10")}


# key -> (badge text, badge colour, text colour): the coloured badges in the lists (look C, issue #9)
DARK, GREY, LIGHT, WHITE, BLACK = "FF3A3A3A", "FF555555", "FFD9D9D9", "FFFFFFFF", "FF111111"
BADGE = {"8k": ("8K", LIGHT, BLACK), "4k": ("4K", LIGHT, BLACK), "1080": ("1080P", DARK, WHITE), "720": ("720P", DARK, WHITE),
         "sd": ("SD", DARK, WHITE), "dolbyvision": ("DOLBY VISION", "FF7B35B0", WHITE), "hdr10plus": ("HDR10+", "FFC9A227", BLACK),
         "hdr10": ("HDR10", "FFC9A227", BLACK), "hlg": ("HLG", "FF2E8B57", WHITE), "hevc": ("HEVC", DARK, WHITE), "av1": ("AV1", DARK, WHITE),
         "h264": ("H.264", DARK, WHITE), "vp9": ("VP9", DARK, WHITE), "atmos": ("ATMOS", "FF262A33", WHITE),
         "dtsx": ("DTS:X", "FF2F6FD6", WHITE), "dtshd_ma": ("DTS-HD MA", "FF2F6FD6", WHITE), "dtshd_hra": ("DTS-HD HRA", "FF2F6FD6", WHITE),
         "dts": ("DTS", "FF2F6FD6", WHITE), "truehd": ("TRUEHD", "FF4A4A55", WHITE), "eac3": ("DD+", "FF4A4A55", WHITE),
         "ac3": ("DD", "FF4A4A55", WHITE), "aac": ("AAC", DARK, WHITE), "flac": ("FLAC", DARK, WHITE), "opus": ("OPUS", DARK, WHITE),
         "pcm": ("PCM", DARK, WHITE), "mp3": ("MP3", DARK, WHITE), "71": ("7.1", GREY, WHITE), "61": ("6.1", GREY, WHITE),
         "51": ("5.1", GREY, WHITE), "20": ("2.0", GREY, WHITE), "10": ("1.0", GREY, WHITE)}


def cond(text):
    return xbmc.getCondVisibility(text)


def label(text):
    return xbmc.getInfoLabel(text)


def _img(name, key):
    """(picture, key): flags/<name>.png, or the flag the user chose for it (Settings > Player > flags), like the player does."""
    own = label(f"Skin.String(nuvio.flag.{key})")
    return own or f"flags/{name}.png", key


def res_tier(res, width=0):
    res = str(res or "").lower()
    if res in ("8k", "4320") or width >= 6000:
        return "8k"
    if res in ("4k", "2160") or width >= 3000:
        return "4k"
    if res == "1080" or width >= 1700:
        return "1080"
    if res == "720" or width >= 1100:
        return "720"
    if res in ("480", "540", "576", "sd") or width > 0:
        return "sd"
    return ""


def acodec_flag(codec):
    c = str(codec or "").lower()
    for start, name, key in (("dtshd_ma_x", "DTS-X", "dtsx"), ("truehd", "TRUEHD", "truehd"), ("dtshd_ma", "DTS-HDMA", "dtshd_ma"),
                             ("dtshd_hra", "DTS-HDHR", "dtshd_hra"), ("dts", "DTS", "dts"), ("eac3", "DD+", "eac3"), ("ac3", "DD", "ac3"),
                             ("aac", "AAC", "aac"), ("he_aac", "AAC", "aac"), ("flac", "FLAC", "flac"), ("opus", "OPUS", "opus"),
                             ("pcm", "PCM", "pcm"), ("mp3", "MP3", "mp3")):
        if c.startswith(start):
            return name, key
    return None


def flags(res, hdr, vcodec, acodec, channels):
    """The flag images in the player's order: resolution, HDR, video codec, Atmos, audio codec, channels."""
    out = []
    tier = res_tier(res)
    for t, name, key in RES:
        if t == tier:
            out.append(_img(name, key))
    if str(hdr or "").lower() in HDR:
        name, key = HDR[str(hdr).lower()]
        out.append(_img(name, key))
    if str(vcodec or "").lower() in VCODEC:
        name, key = VCODEC[str(vcodec).lower()]
        out.append(_img(name, key))
    a = str(acodec or "").lower()
    if a in ("truehd_atmos", "eac3_ddp_atmos") or "atmos" in a:
        out.append(_img("ATMOS", "atmos"))
    af = acodec_flag(a)
    if af:
        out.append(_img(*af))
    try:
        ch = int(channels or 0)
    except ValueError:
        ch = 0
    if ch in CH:
        out.append(_img(*CH[ch]))
    return out


def langs(text):
    """'eng / dut / eng' -> 'EN · NL' (each once, at most four)."""
    seen = []
    for part in str(text or "").replace(",", "/").split("/"):
        code = part.strip().lower()
        if not code or code in ("und", "unknown"):
            continue
        short = xbmc.convertLanguage(code, xbmc.ISO_639_1) or code[:2]
        short = short.upper()
        if short not in seen:
            seen.append(short)
    return " · ".join(seen[:4])


def _rpc(method, params):
    res = json.loads(xbmc.executeJSONRPC(json.dumps({"jsonrpc": "2.0", "id": 1, "method": method, "params": params})))
    return res.get("result") or {}


def from_episodes(show_id, season=None):
    """(flags, mostly) for a series or one season: the quality most episodes have."""
    key = f"season:{show_id}:{season}" if season is not None else f"tvshow:{show_id}"
    if key in SHOW_CACHE:
        return SHOW_CACHE[key]
    params = {"tvshowid": int(show_id), "properties": ["streamdetails"]}
    if season is not None:
        params["season"] = int(season)
    episodes = _rpc("VideoLibrary.GetEpisodes", params).get("episodes") or []
    combos = Counter()
    for ep in episodes:
        sd = ep.get("streamdetails") or {}
        v = (sd.get("video") or [{}])[0] if sd.get("video") else {}
        a = (sd.get("audio") or [{}])[0] if sd.get("audio") else {}
        if not v:
            continue
        combos[(res_tier("", int(v.get("width") or 0)), str(v.get("hdrtype") or ""), str(v.get("codec") or ""),
                str(a.get("codec") or ""), int(a.get("channels") or 0))] += 1
    if not combos:
        SHOW_CACHE[key] = ([], False)
        return SHOW_CACHE[key]
    (tier, hdr, vcodec, acodec, ch), n = combos.most_common(1)[0]
    result = (flags(tier, hdr, vcodec, acodec, ch), n < sum(combos.values()))
    SHOW_CACHE[key] = result
    return result


def clear():
    if HOME.getProperty(P + "for"):
        for p in PROPS:
            HOME.clearProperty(P + p)


def fill(ident):
    dbtype = label("ListItem.DBType")
    most = False
    if dbtype in ("tvshow", "season"):
        show_id = label("ListItem.DBID") if dbtype == "tvshow" else (label("ListItem.TvShowDBID") or "")
        season = label("ListItem.Season") if dbtype == "season" else None
        if not show_id.isdigit() or (season is not None and not season.lstrip("-").isdigit()):
            imgs = []
        else:
            season_nr = int(season) if season is not None else None
            imgs, most = from_episodes(show_id, season_nr if season_nr is not None and season_nr >= 0 else None)
        alang = slang = ""
    else:
        imgs = flags(label("ListItem.VideoResolution"), label("ListItem.HdrType"), label("ListItem.VideoCodec"),
                     label("ListItem.AudioCodec"), label("ListItem.AudioChannels"))
        alang, slang = langs(label("ListItem.AudioLanguage")), langs(label("ListItem.SubtitleLanguage"))
    for p in PROPS:
        HOME.clearProperty(P + p)
    if not imgs and not alang and not slang:
        return
    for i, (img, key) in enumerate(imgs[:6], 1):
        HOME.setProperty(f"{P}img{i}", img)
        text, colour, ink = BADGE.get(key, (key.upper(), DARK, WHITE))
        HOME.setProperty(f"{P}t{i}", text)
        HOME.setProperty(f"{P}c{i}", colour)
        HOME.setProperty(f"{P}k{i}", ink)
    if alang:
        HOME.setProperty(P + "alang", alang)
    if slang:
        HOME.setProperty(P + "slang", slang)
    if most:
        HOME.setProperty(P + "most", "1")
    HOME.setProperty(P + "for", ident)


def tick():
    if cond(OFF) or not cond("Window.IsActive(videos) + [Container.Content(movies) | Container.Content(tvshows) | "
                             "Container.Content(seasons) | Container.Content(episodes)]"):
        STATE["id"] = STATE["done"] = ""
        clear()
        return
    ident = f"{label('ListItem.DBType')}:{label('ListItem.DBID')}:{label('ListItem.FileNameAndPath')}:{label('ListItem.Label')}"
    now = time.time()
    series = label("ListItem.DBType") in ("tvshow", "season")
    if ident != STATE["id"]:
        STATE["id"], STATE["since"], STATE["done"] = ident, now, ""
        if series:                                    # series and seasons ask the library: wait until the cursor rests
            clear()
            return
        STATE["done"] = ident                         # films and episodes: Kodi already knows their streams, show them at once
        fill(ident)
        return
    if STATE["done"] == ident or now - STATE["since"] < 0.3:
        return
    STATE["done"] = ident
    fill(ident)
