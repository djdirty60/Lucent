# -*- coding: utf-8 -*-
"""Per series: the sound track and subtitle you chose are remembered, and set again for the next episode.
(Only for series; a film starts with Kodi's and the skin's own choices.)"""
import json

import xbmc

import util

FILE = "series_streams.json"


def _rpc(method, params):
    answer = json.loads(xbmc.executeJSONRPC(json.dumps({"jsonrpc": "2.0", "id": 1, "method": method, "params": params})))
    return answer.get("result") or {}


def snapshot():
    """What is in use right now, or None."""
    props = _rpc("Player.GetProperties", {"playerid": 1, "properties": ["currentaudiostream", "currentsubtitle", "subtitleenabled"]})
    if not props:
        return None
    audio, sub = props.get("currentaudiostream") or {}, props.get("currentsubtitle") or {}
    return {"audio_lang": audio.get("language") or "", "audio_name": audio.get("name") or "", "audio_channels": audio.get("channels") or 0,
            "sub_on": bool(props.get("subtitleenabled")), "sub_lang": sub.get("language") or "", "sub_name": sub.get("name") or "",
            "sub_forced": bool(sub.get("isforced"))}


def remember(meta, snap):
    if not snap or meta.get("kind") != "episode" or not util.flag("remember_streams"):
        return
    data = util.load_json(FILE, {})
    data[str(meta["tmdb"])] = snap
    util.save_json(FILE, data)


def has_memory(meta):
    return meta.get("kind") == "episode" and util.flag("remember_streams") and bool(util.load_json(FILE, {}).get(str(meta["tmdb"])))


def apply(meta):
    """Sets the remembered sound and subtitle for this series, when they are in this episode."""
    if meta.get("kind") != "episode" or not util.flag("remember_streams"):
        return
    saved = util.load_json(FILE, {}).get(str(meta["tmdb"]))
    if not saved:
        return
    props = _rpc("Player.GetProperties", {"playerid": 1, "properties": ["audiostreams", "subtitles", "currentaudiostream", "currentsubtitle", "subtitleenabled"]})
    audios = props.get("audiostreams") or []
    if saved.get("audio_lang") and len(audios) > 1:
        same = [a for a in audios if a.get("language") == saved["audio_lang"]]
        same.sort(key=lambda a: (a.get("name") != saved.get("audio_name"), a.get("channels") != saved.get("audio_channels")))
        if same and same[0].get("index") != (props.get("currentaudiostream") or {}).get("index"):
            _rpc("Player.SetAudioStream", {"playerid": 1, "stream": same[0]["index"]})
    subs = props.get("subtitles") or []
    if not saved.get("sub_on"):
        if props.get("subtitleenabled"):
            _rpc("Player.SetSubtitle", {"playerid": 1, "subtitle": "off"})
    elif saved.get("sub_lang"):
        same = [s for s in subs if s.get("language") == saved["sub_lang"] and bool(s.get("isforced")) == saved.get("sub_forced", False)]
        same = same or [s for s in subs if s.get("language") == saved["sub_lang"]]
        same.sort(key=lambda s: s.get("name") != saved.get("sub_name"))
        if same:
            _rpc("Player.SetSubtitle", {"playerid": 1, "subtitle": same[0]["index"], "enable": True})
    util.log("series %s: remembered sound and subtitle set" % meta["tmdb"])
