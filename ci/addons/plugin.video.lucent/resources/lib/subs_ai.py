# -*- coding: utf-8 -*-
"""Lucent: AI subtitles - an AI service translates an English subtitle into your language.

Started from the live subtitle list (subs_live.py). It works from where you are watching: the next few minutes are
translated first and shown at once, the rest follows in the background and the subtitle is reloaded when it is done.
The finished translation is kept (addon_data/plugin.video.lucent/subs_ai/), so the next time it opens at once.

Needs your own key for one of the services (Lucent Video settings > Subtitles and sound > AI translation):
Google Gemini (free key), OpenRouter (one key for many models) or Anthropic Claude. The subtitle text is sent to that
service for the translation.
"""
import hashlib
import json
import os
import re
import time
import urllib.error
import urllib.request

import subconf
import xbmc
import xbmcgui
import xbmcvfs

NL = xbmc.getLanguage(xbmc.ISO_639_1) == "nl"
KEY_SETTING = "lucent.gemini.key"
PROVIDER_SETTING = "lucent.ai.provider"
# service -> (name shown, key setting, model setting, default model)
PROVIDERS = {
    "gemini": ("Google Gemini", "lucent.gemini.key", "", ""),
    "openrouter": ("OpenRouter", "lucent.openrouter.key", "lucent.openrouter.model", "openrouter/auto"),
    "claude": ("Claude", "lucent.claude.key", "lucent.claude.model", "claude-haiku-5-5"),
}
MODELS = ("gemini-flash-latest", "gemini-3.8-flash", "gemini-3.6-flash", "gemini-2.5-flash")
CHUNK = 60                   # subtitle lines per request
FIRST = 2                    # chunks translated before the subtitle is shown
DIR = subconf.data_dir("subs_ai")
LANG_NAMES = {"nl": "Dutch", "de": "German", "fr": "French", "es": "Spanish", "it": "Italian", "pt": "Portuguese",
              "da": "Danish", "sv": "Swedish", "no": "Norwegian", "fi": "Finnish", "pl": "Polish", "tr": "Turkish"}


def t(en, nl):
    return nl if NL else en


def log(text):
    xbmc.log(f"[lucent.video] subs_ai: {text}", xbmc.LOGINFO)


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


# hearing-impaired notes: (he sighs), [wind howling], ♪ music ♪, and speaker names like "JOHN:" or "- MAN:"
SDH_BRACKETS = re.compile(r"\([^)]*\)|\[[^\]]*\]|\{\*?[^}]*\}|<i>\s*\([^)]*\)\s*</i>")
SDH_SPEAKER = re.compile(r"^(\s*-?\s*)(?:<i>)?[A-Z][A-Z0-9 .'#-]{1,30}:\s*(?:</i>)?")
SDH_MUSIC = re.compile(r"^[\s\-]*[♪♫#*]+.*$|^.*[♪♫]+[\s\-]*$")


def clean_sdh(text):
    """Remove what is meant for the hard of hearing; keep the spoken words. '' when nothing spoken is left."""
    out = []
    for line in text.split("\n"):
        line = SDH_BRACKETS.sub("", line)
        line = SDH_SPEAKER.sub(r"\1", line)
        if SDH_MUSIC.match(line):
            continue
        line = re.sub(r"<(i|b|u)>\s*</\1>", "", line)
        line = re.sub(r"\s{2,}", " ", line).strip()
        if line in ("", "-", "...", "- ...") or not re.search(r"\w", line):
            continue
        out.append(line)
    if len(out) == 1 and out[0].startswith("- "):
        out[0] = out[0][2:]                               # a dialogue dash with only one speaker left
    return "\n".join(out)


def keep_sdh():
    return subconf.on("lucent.subs.ai.keephi")


def write_srt(path, cues):
    out = []
    for n, c in enumerate(cues, start=1):
        out.append(f"{n}\n{c['time']}\n{c.get('tr') or c['text']}\n")
    with open(path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(out))


# ----------------------------------------------------------------------------- services
def skin_string(name):
    return subconf.text(name) if name else ""


def provider():
    """The chosen AI service; when it has no key but another one has, that one is used."""
    chosen = skin_string(PROVIDER_SETTING) or "gemini"
    if chosen not in PROVIDERS:
        chosen = "gemini"
    if skin_string(PROVIDERS[chosen][1]):
        return chosen
    return next((p for p, v in PROVIDERS.items() if skin_string(v[1])), chosen)


def provider_name(p=None):
    return PROVIDERS[p or provider()][0]


def has_key():
    return bool(skin_string(PROVIDERS[provider()][1]))


def make_prompt(lines, target):
    return (f"Translate these film/TV subtitle lines from English into natural, spoken {target}. "
            "Keep it short like real subtitles, keep line breaks (\\n) inside a line, keep names, do not add notes. "
            "Do not translate or add descriptions of sounds or actions such as (sighs) or [music]; give an empty string for a line "
            "that is only such a description. "
            f"Return only a JSON array with exactly {len(lines)} strings, in the same order.\n\n"
            + json.dumps(lines, ensure_ascii=False))


def json_list(text, count):
    """The JSON array in an answer (models sometimes wrap it in ``` or add a sentence)."""
    text = (text or "").strip()
    start, end = text.find("["), text.rfind("]")
    if start < 0 or end < start:
        raise ValueError("no JSON array in the answer")
    out = json.loads(text[start:end + 1])
    if not isinstance(out, list) or len(out) != count:
        raise ValueError(f"got {len(out) if isinstance(out, list) else '?'} lines for {count}")
    return [str(x) for x in out]


def post(url, body, headers):
    req = urllib.request.Request(url, data=json.dumps(body).encode("utf-8"), method="POST",
                                 headers={"Content-Type": "application/json", **headers})
    with urllib.request.urlopen(req, timeout=90) as resp:
        return json.loads(resp.read().decode("utf-8"))


def openrouter(key, lines, target):
    model = skin_string(PROVIDERS["openrouter"][2]) or PROVIDERS["openrouter"][3]
    data = post("https://openrouter.ai/api/v1/chat/completions",
                {"model": model, "temperature": 0.2, "messages": [{"role": "user", "content": make_prompt(lines, target)}]},
                {"Authorization": f"Bearer {key}", "HTTP-Referer": "https://github.com/djdirty60/Lucent", "X-Title": "Lucent"})
    text = (((data.get("choices") or [{}])[0].get("message") or {}).get("content")) or ""
    return json_list(text, len(lines))


def claude(key, lines, target):
    model = skin_string(PROVIDERS["claude"][2]) or PROVIDERS["claude"][3]
    data = post("https://api.anthropic.com/v1/messages",
                {"model": model, "max_tokens": 8000, "messages": [{"role": "user", "content": make_prompt(lines, target)}]},
                {"x-api-key": key, "anthropic-version": "2023-06-01"})
    text = "".join(b.get("text", "") for b in data.get("content") or [] if b.get("type") == "text")
    return json_list(text, len(lines))


def translate(lines, target):
    p = provider()
    key = skin_string(PROVIDERS[p][1])
    if p == "openrouter":
        return openrouter(key, lines, target)
    if p == "claude":
        return claude(key, lines, target)
    return gemini(key, lines, target)


# ----------------------------------------------------------------------------- Gemini
def gemini(key, lines, target):
    """Translate a list of subtitle lines; returns a list of the same length."""
    prompt = make_prompt(lines, target)
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
    path = os.path.join(DIR, f"{media_key()}.{code}.v2.srt")
    return path if os.path.exists(path) else ""


# ----------------------------------------------------------------------------- work
def show(path, code):
    """Switch the translation on, also when the film's own subtitle (for example a 'forced' one) is selected."""
    try:
        from subs_live import activate
        activate(path, code, 8)
    except Exception as error:  # noqa: BLE001
        log(f"show: {error}")
        xbmc.Player().setSubtitles(path)
        xbmc.Player().showSubtitles(True)


def translate_and_load(source_path, code):
    if not has_key():
        notify(t("No AI key - Lucent Video settings > Subtitles and sound", "Geen AI-sleutel - instellingen van Lucent Video > Ondertitels en geluid"))
        return
    name = provider_name()
    target = LANG_NAMES.get(code) or xbmc.convertLanguage(code, xbmc.ENGLISH_NAME) or xbmc.getLanguage(xbmc.ENGLISH_NAME)
    try:
        cues = parse_srt(read_text(source_path))
    except Exception as error:  # noqa: BLE001
        log(f"read {source_path}: {error}")
        cues = []
    if cues and not keep_sdh():
        before = len(cues)
        for c in cues:
            c["text"] = clean_sdh(c["text"])
        cues = [c for c in cues if c["text"]]
        log(f"hearing-impaired notes removed: {before - len(cues)} lines were only sounds")
    if not cues:
        notify(t("This subtitle cannot be read (not SRT)", "Deze ondertitel is niet te lezen (geen SRT)"), icon=xbmcgui.NOTIFICATION_WARNING)
        return
    os.makedirs(DIR, exist_ok=True)
    player = xbmc.Player()
    now = player.getTime() if player.isPlayingVideo() else 0
    first = next((i for i, c in enumerate(cues) if c["end"] >= now - 5), 0)
    order = list(range(first, len(cues))) + list(range(0, first))      # from where you are, then the beginning
    chunks = [order[i:i + CHUNK] for i in range(0, len(order), CHUNK)]
    final = os.path.join(DIR, f"{media_key()}.{code}.v2.srt")
    notify(t("Translating… the subtitle appears in a moment", "Vertalen… de ondertitel verschijnt zo"), 5000)
    log(f"{len(cues)} lines, starting at line {first} ({int(now)} s), {len(chunks)} parts")
    shown = False
    monitor = xbmc.Monitor()
    for n, chunk in enumerate(chunks, start=1):
        if monitor.abortRequested() or not player.isPlayingVideo():
            log("stopped: playback ended")
            break
        try:
            out = translate([cues[i]["text"] for i in chunk], target)
        except urllib.error.HTTPError as error:
            log(f"{name} HTTP {error.code}: {error.read()[:200]!r}")
            if error.code >= 500:
                continue                                    # the service is busy: try the next part
            reason = {400: t("the request or model is not accepted", "het verzoek of model wordt niet geaccepteerd"),
                      401: t("the key is not valid", "de sleutel klopt niet"), 402: t("no credit left", "geen tegoed meer"),
                      403: t("the key is not allowed", "de sleutel mag dit niet"), 404: t("model not found", "model niet gevonden"),
                      429: t("limit reached, try again later", "limiet bereikt, probeer het later")}.get(error.code, f"HTTP {error.code}")
            notify(f"{name}: {reason}", 6000, xbmcgui.NOTIFICATION_WARNING)
            break
        except Exception as error:  # noqa: BLE001
            log(f"part {n}: {error}")
            continue
        for i, text in zip(chunk, out):
            cues[i]["tr"] = text
        if not shown and (n >= FIRST or n == len(chunks)):
            part = os.path.join(DIR, f"{media_key()}.{code}.part{int(time.time())}.srt")
            write_srt(part, cues)                           # translated from here on, the rest still English
            show(part, code)
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
            show(final, code)
        log(f"finished, kept as {final}")
    elif done and player.isPlayingVideo() and not shown:
        part = os.path.join(DIR, f"{media_key()}.{code}.part{int(time.time())}.srt")
        write_srt(part, cues)
        show(part, code)
