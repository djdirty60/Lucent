# -*- coding: utf-8 -*-
"""Lucent: AI subtitles - Google Gemini translates an English subtitle into your language.

Started from the live subtitle list (subs_live.py). It works from where you are watching: the next few minutes are
translated first and shown at once, the rest follows in the background and the subtitle is reloaded when it is done.
The finished translation is kept (addon_data/skin.lucent/subs_ai/), so the next time it opens at once.

Needs your own free Gemini key (Skin settings > Integrations > Subtitles > AI translation). The subtitle text is sent to
Google for the translation.
"""
import hashlib
import json
import os
import re
import time
import urllib.error
import urllib.request

import xbmc
import xbmcgui
import xbmcvfs

NL = xbmc.getLanguage(xbmc.ISO_639_1) == "nl"
KEY_SETTING = "lucent.gemini.key"
MODELS = ("gemini-flash-latest", "gemini-3.8-flash", "gemini-3.6-flash", "gemini-2.5-flash")
CHUNK = 60                   # subtitle lines per request
FIRST = 2                    # chunks translated before the subtitle is shown
DIR = xbmcvfs.translatePath("special://profile/addon_data/skin.lucent/subs_ai/")
LANG_NAMES = {"nl": "Dutch", "de": "German", "fr": "French", "es": "Spanish", "it": "Italian", "pt": "Portuguese",
              "da": "Danish", "sv": "Swedish", "no": "Norwegian", "fi": "Finnish", "pl": "Polish", "tr": "Turkish"}


def t(en, nl):
    return nl if NL else en


def log(text):
    xbmc.log(f"[skin.lucent] subs_ai: {text}", xbmc.LOGINFO)


def notify(text, ms=4000, icon=xbmcgui.NOTIFICATION_INFO):
    xbmcgui.Dialog().notification(t("AI subtitles", "AI-ondertitels"), text, icon, ms)


# ----------------------------------------------------------------------------- SRT
TIME = re.compile(r"(\d+):(\d+):(\d+)[,.](\d+)\s*-->\s*(\d+):(\d+):(\d+)[,.](\d+)")


def read_text(path):
    with xbmcvfs.File(path) as fh:
        raw = fh.readBytes()
    raw = bytes(raw)
    for enc in ("utf-8-sig", "cp1252", "latin-1"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", "replace")


def to_seconds(h, m, s, ms):
    return int(h) * 3600 + int(m) * 60 + int(s) + int(ms[:3].ljust(3, "0")) / 1000


def parse_srt(text):
    cues = []
    for block in re.split(r"\r?\n\s*\r?\n", text.strip()):
        lines = [x for x in block.splitlines() if x.strip() != ""]
        idx = next((i for i, x in enumerate(lines) if TIME.search(x)), None)
        if idx is None:
            continue
        m = TIME.search(lines[idx])
        start, end = to_seconds(*m.groups()[:4]), to_seconds(*m.groups()[4:])
        body = "\n".join(lines[idx + 1:]).strip()
        if body:
            cues.append({"start": start, "end": end, "time": lines[idx].strip(), "text": body})
    return cues


def write_srt(path, cues):
    out = []
    for n, c in enumerate(cues, start=1):
        out.append(f"{n}\n{c['time']}\n{c.get('tr') or c['text']}\n")
    with open(path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(out))


# ----------------------------------------------------------------------------- Gemini
def gemini(key, lines, target):
    """Translate a list of subtitle lines; returns a list of the same length."""
    prompt = (f"Translate these film/TV subtitle lines from English into natural, spoken {target}. "
              "Keep it short like real subtitles, keep line breaks (\\n) inside a line, keep names, do not add notes. "
              f"Return a JSON array with exactly {len(lines)} strings, in the same order.\n\n"
              + json.dumps(lines, ensure_ascii=False))
    body = {"contents": [{"role": "user", "parts": [{"text": prompt}]}],
            "generationConfig": {"temperature": 0.2, "responseMimeType": "application/json",
                                 "responseSchema": {"type": "ARRAY", "items": {"type": "STRING"}}}}
    last = None
    for model in MODELS:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
        req = urllib.request.Request(url, data=json.dumps(body).encode("utf-8"), method="POST",
                                     headers={"Content-Type": "application/json", "x-goog-api-key": key})
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                data = json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as error:
            last = error
            if error.code in (400, 401, 403, 429):
                raise                              # wrong key / no quota: another model will not help
            continue                               # 404 (model gone) / 5xx: try the next model
        except Exception as error:  # noqa: BLE001
            last = error
            continue
        text = "".join(p.get("text", "") for p in ((data.get("candidates") or [{}])[0].get("content") or {}).get("parts", []))
        out = json.loads(text)
        if isinstance(out, list) and len(out) == len(lines):
            return [str(x) for x in out]
        last = ValueError(f"got {len(out) if isinstance(out, list) else '?'} lines for {len(lines)}")
    raise last or RuntimeError("no model answered")


# ----------------------------------------------------------------------------- cache
def media_key():
    show = xbmc.getInfoLabel("VideoPlayer.TVShowTitle")
    if show:
        name = f"{show} S{xbmc.getInfoLabel('VideoPlayer.Season')}E{xbmc.getInfoLabel('VideoPlayer.Episode')}"
    else:
        name = f"{xbmc.getInfoLabel('VideoPlayer.Title')} {xbmc.getInfoLabel('VideoPlayer.Year')}"
    imdb = xbmc.getInfoLabel("VideoPlayer.IMDBNumber")
    return hashlib.md5(f"{imdb}|{name}".lower().encode("utf-8")).hexdigest()[:16]


def cached_for_current(code):
    path = os.path.join(DIR, f"{media_key()}.{code}.srt")
    return path if os.path.exists(path) else ""


# ----------------------------------------------------------------------------- work
def translate_and_load(source_path, code):
    key = xbmc.getInfoLabel(f"Skin.String({KEY_SETTING})")
    if not key:
        notify(t("No Gemini key - Skin settings > Integrations", "Geen Gemini-sleutel - Skin-instellingen > Integraties"))
        return
    target = LANG_NAMES.get(code, xbmc.getLanguage(xbmc.ENGLISH_NAME))
    try:
        cues = parse_srt(read_text(source_path))
    except Exception as error:  # noqa: BLE001
        log(f"read {source_path}: {error}")
        cues = []
    if not cues:
        notify(t("This subtitle cannot be read (not SRT)", "Deze ondertitel is niet te lezen (geen SRT)"), icon=xbmcgui.NOTIFICATION_WARNING)
        return
    os.makedirs(DIR, exist_ok=True)
    player = xbmc.Player()
    now = player.getTime() if player.isPlayingVideo() else 0
    first = next((i for i, c in enumerate(cues) if c["end"] >= now - 5), 0)
    order = list(range(first, len(cues))) + list(range(0, first))      # from where you are, then the beginning
    chunks = [order[i:i + CHUNK] for i in range(0, len(order), CHUNK)]
    final = os.path.join(DIR, f"{media_key()}.{code}.srt")
    notify(t("Translating… the subtitle appears in a moment", "Vertalen… de ondertitel verschijnt zo"), 5000)
    log(f"{len(cues)} lines, starting at line {first} ({int(now)} s), {len(chunks)} parts")
    shown = False
    monitor = xbmc.Monitor()
    for n, chunk in enumerate(chunks, start=1):
        if monitor.abortRequested() or not player.isPlayingVideo():
            log("stopped: playback ended")
            break
        try:
            out = gemini(key, [cues[i]["text"] for i in chunk], target)
        except urllib.error.HTTPError as error:
            log(f"Gemini HTTP {error.code}: {error.read()[:200]!r}")
            reason = {400: t("the key is not valid", "de sleutel klopt niet"), 403: t("the key is not allowed", "de sleutel mag dit niet"),
                      429: t("daily limit reached, try again later", "daglimiet bereikt, probeer het later")}.get(error.code, f"HTTP {error.code}")
            notify(t("Gemini: ", "Gemini: ") + reason, 6000, xbmcgui.NOTIFICATION_WARNING)
            break
        except Exception as error:  # noqa: BLE001
            log(f"part {n}: {error}")
            continue
        for i, text in zip(chunk, out):
            cues[i]["tr"] = text
        if not shown and (n >= FIRST or n == len(chunks)):
            part = os.path.join(DIR, f"{media_key()}.{code}.part{int(time.time())}.srt")
            write_srt(part, cues)                           # translated from here on, the rest still English
            player.setSubtitles(part)
            player.showSubtitles(True)
            shown = True
            notify(t("AI subtitle on - the rest follows in the background", "AI-ondertitel staat aan - de rest volgt op de achtergrond"))
    done = sum(1 for c in cues if c.get("tr"))
    if done == len(cues):
        write_srt(final, cues)
        for name in os.listdir(DIR):
            if ".part" in name:
                try:
                    os.remove(os.path.join(DIR, name))
                except OSError:
                    pass
        if player.isPlayingVideo():
            player.setSubtitles(final)
            player.showSubtitles(True)
        log(f"finished, kept as {final}")
    elif done and player.isPlayingVideo() and not shown:
        part = os.path.join(DIR, f"{media_key()}.{code}.part{int(time.time())}.srt")
        write_srt(part, cues)
        player.setSubtitles(part)
