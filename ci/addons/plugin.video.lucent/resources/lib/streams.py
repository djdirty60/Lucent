# -*- coding: utf-8 -*-
"""Fetches playable links from the user's AIOStreams address. AIOStreams does the searching and sorting."""
import re
import urllib.parse

import util

def size_text(size):
    return "%.1f GB" % (size / 1073741824.0) if size else ""


SKIP = {"error", "statistic", "info", "external", "youtube", "p2p", "live"}
FEL = re.compile(r"(?:^|[ ._\-\[(])FEL(?=$|[ ._\-\])])", re.I)
USER_AGENT = "AIOStreams-Lucent/0.1"     # starting with 'AIO' makes AIOStreams send streamData


def base_url(address):
    url = (address or "").strip()
    if not url:
        return ""
    if url.startswith("stremio://"):
        url = "https://" + url[len("stremio://"):]
    if not re.match(r"^https?://", url, re.I):
        url = "https://" + url
    url = url.split("?")[0].rstrip("/")
    for tail in ("/manifest.json", "/configure"):
        if url.endswith(tail):
            url = url[:-len(tail)]
    return url.rstrip("/")


def resolution(parsed, name):
    value = parsed.get("resolution") or ""
    if value:
        return "4K" if value == "2160p" else value
    lower = name.lower()
    for mark, label in (("2160", "4K"), ("4k", "4K"), ("1080", "1080p"), ("720", "720p")):
        if mark in lower:
            return label
    return "SD"


def with_headers(url, hints):
    headers = ((hints or {}).get("proxyHeaders") or {}).get("request") or {}
    return url + "|" + urllib.parse.urlencode(headers) if headers else url


VISUAL = {"DV": ["DV"], "DV ONLY": ["DV"], "HDR+DV": ["DV", "HDR"], "HDR": ["HDR"], "HDR10": ["HDR"], "HDR10+": ["HDR"], "HDR ONLY": ["HDR"],
          "HLG": ["HDR"], "SDR": ["SDR"], "3D": ["3D"]}
AUDIO = {"ATMOS": "ATMOS", "TRUEHD": "TRUEHD", "DTS:X": "DTS-X", "DTS-HD MA": "DTS-HDMA", "DTS-HD": "DTS-HD", "DTS-ES": "DTS", "DTS": "DTS",
         "DD+": "DD+", "DD": "DD", "AAC": "AAC", "OPUS": "OPUS"}
QUALITY = {"BLURAY REMUX": "REMUX", "BLURAY": "BLURAY", "WEB-DL": "WEB", "WEBRIP": "WEB", "HDTV": "HDTV", "CAM": "CAM", "TS": "CAM", "TC": "CAM",
           "SCR": "SCR", "DVDRIP": "DVDRIP", "HDRIP": "HD-RIP"}
ENCODE = {"HEVC": "HEVC", "AVC": "AVC", "AV1": "AV1", "XVID": "XVID", "DIVX": "DIVX"}


def flags_of(parsed, name):
    """Names of the badge pictures for this source, in the order they are shown."""
    out = []
    for tag in parsed.get("visualTags") or []:
        out += VISUAL.get(tag.upper(), [])
    if "DV" in out and re.search(r"(?:^|[ ._\-\[(])DV2(?=$|[ ._\-\])])", name, re.I):
        out = ["DV2" if f == "DV" else f for f in out]
    if FEL.search(name):
        out.append("aio_FEL")
    elif re.search(r"(?:^|[ ._\-\[(])(?:DV[ ._-]?)?P7(?=$|[ ._\-\])])", name, re.I):
        out.append("aio_P7")
    if "IMAX" in [t.upper() for t in parsed.get("visualTags") or []] or re.search(r"(?:^|[ ._\-\[(])IMAX(?=$|[ ._\-\])])", name, re.I):
        out.append("aio_IMAX")
    encode = ENCODE.get((parsed.get("encode") or "").upper())
    if encode:
        out.append(encode)
    quality = QUALITY.get((parsed.get("quality") or "").upper())
    if quality:
        out.append(quality)
    for tag in parsed.get("audioTags") or []:
        if AUDIO.get(tag.upper()):
            out.append(AUDIO[tag.upper()])
    out += [c for c in parsed.get("audioChannels") or [] if c in ("2.0", "5.1", "7.1")]
    languages = [l.lower() for l in parsed.get("languages") or []]
    if "dutch" in languages:
        out.append("aio_NL")
    elif "multi" in languages:
        out.append("aio_MULTI")
    if "dutch" in [l.lower() for l in parsed.get("subtitles") or []]:
        out.append("aio_NL-SUBS")
    seen = []
    return [f for f in out if not (f in seen or seen.append(f))]


def convert(raw, include_uncached=True):
    """AIOStreams' answer, in AIOStreams' own order, as simple source dicts."""
    out = []
    for stream in raw or []:
        data = stream.get("streamData") or {}
        kind = (data.get("type") or "").lower()
        service = data.get("service") or {}
        if not stream.get("url") or kind in SKIP:
            continue
        if not include_uncached and service and service.get("cached") is False:
            continue
        hints = stream.get("behaviorHints") or {}
        parsed = data.get("parsedFile") or {}
        name = (data.get("filename") or hints.get("filename") or data.get("folderName")
                or (stream.get("description") or "").split("\n")[0] or stream.get("name") or "AIOStreams").strip()
        tags = [t.upper() for t in parsed.get("visualTags") or []]
        badges = []
        if FEL.search(name):
            badges.append("FEL")
        elif any("DV" in t for t in tags):
            badges.append("DV")
        elif any("HDR" in t for t in tags):
            badges.append("HDR")
        if "IMAX" in tags or re.search(r"\bIMAX\b", name, re.I):
            badges.append("IMAX")
        if "REMUX" in (parsed.get("quality") or "").upper():
            badges.append("REMUX")
        badges += [a for a in (parsed.get("audioTags") or [])[:2]]
        size = data.get("size") or hints.get("videoSize") or 0
        service_name = str(service.get("id") or data.get("addon") or "").upper()
        size_label = size_text(size if isinstance(size, (int, float)) else 0)
        out.append({
            "flags": flags_of(parsed, name),
            "meta": " · ".join(p for p in (service_name, size_label) if p),
            "url": with_headers(stream["url"], hints),
            "name": name,
            "resolution": resolution(parsed, name),
            "badges": badges,
            "size": size if isinstance(size, (int, float)) else 0,
            "service": str(service.get("id") or data.get("addon") or "").upper(),
            "cached": service.get("cached") is True or kind in ("usenet", "http"),
        })
    return out


def stream_id(meta):
    show_part = meta.get("imdb") or "tmdb:%s" % meta["tmdb"]
    if meta["kind"] == "movie":
        return "movie", show_part
    return "series", "%s:%s:%s" % (show_part, meta["season"], meta["episode"])


def fetch(meta):
    """Returns the sources, or raises util.HttpError. Short-lived cache: links stay valid for a while."""
    base = base_url(util.setting("manifest_url"))
    if not base:
        return None
    media, sid = stream_id(meta)
    url = "%s/stream/%s/%s.json" % (base, media, urllib.parse.quote(sid, safe=":"))
    key = "streams" + url
    raw = util.cache_get(key, 600)
    if raw is None:
        answer, _ = util.http(url, headers={"User-Agent": USER_AGENT}, timeout=max(5, util.number("timeout", 30)))
        raw = (answer or {}).get("streams") or []
        if raw:
            util.cache_set(key, raw)
    return convert(raw)


def describe(source):
    parts = [source["resolution"]] + source["badges"] + [size_text(source["size"]), source["service"]]
    return " · ".join(p for p in parts if p)


def check():
    """For the Test button: (ok, text). Never shows the address."""
    base = base_url(util.setting("manifest_url"))
    if not base:
        return False, util.T("Vul eerst je AIOStreams-adres in.", "Enter your AIOStreams address first.")
    try:
        answer, _ = util.http(base + "/stream/movie/tt0111161.json", headers={"User-Agent": USER_AGENT}, timeout=30)
    except util.HttpError as error:
        return False, util.T("Geen verbinding: %s", "No connection: %s") % error
    count = len(convert((answer or {}).get("streams"), True))
    return count > 0, util.T("Verbonden. Testfilm: %d bronnen.", "Connected. Test film: %d sources.") % count
