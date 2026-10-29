# -*- coding: utf-8 -*-
"""Lucent: Sport - "Fix channel", reminders, automatic switching and recording.

  sport_fix.json    channels you chose yourself: per game, per competition or per team
  sport_plan.json   reminders (remind | switch), recordings, and the 'automatic reminders for my teams' switch

The Lucent helper (helper.py) calls tick() -> check() every 30 seconds:
  remind   a notification 5 minutes before kick-off
  switch   1 minute before kick-off a question with 10 seconds to cancel, then the channel opens
  record   an instant recording on the channel from 2 minutes before kick-off for the chosen number of hours
           (Kodi has to be running; a PVR timer cannot be longer than the programme, so the helper starts/stops it)
"""
import time

import xbmc
import xbmcgui

import agenda_core as ac
import sport_core as sc
import sport_epg as epg

FIX_PATH = ac.DATA + "sport_fix.json"
PLAN_PATH = ac.DATA + "sport_plan.json"
REMIND_LEAD = 5 * 60
SWITCH_LEAD = 60
RECORD_LEAD = 2 * 60
GRACE = 10 * 60               # a reminder that is more than this late is dropped
HOME = xbmcgui.Window(10000)

TX = {
    "fix_game": ("Only this game", "Alleen deze wedstrijd"),
    "fix_league": ("Every game of {0}", "Alle wedstrijden van {0}"),
    "fix_team": ("Every game of {0}", "Alle wedstrijden van {0}"),
    "fix_pick": ("Choose the right channel", "Kies de juiste zender"),
    "fix_scope": ("Remember this for…", "Onthouden voor…"),
    "fix_clear": ("Forget my choices for this game", "Mijn keuzes voor deze wedstrijd vergeten"),
    "yours": ("Your choice", "Jouw keuze"),
    "r_off": ("Off", "Uit"), "r_remind": ("Remind me (5 minutes before)", "Herinner me (5 minuten van tevoren)"),
    "r_switch": ("Switch automatically (1 minute before)", "Automatisch omschakelen (1 minuut van tevoren)"),
    "r_title": ("Reminder", "Herinnering"),
    "btn_fix": ("Fix channel", "Zender kiezen"), "btn_remind": ("Remind me", "Herinner me"),
    "btn_remind_on": ("Reminder on", "Herinnering aan"), "btn_switch_on": ("Switching on", "Omschakelen aan"),
    "btn_rec": ("Record", "Opnemen"), "btn_rec_on": ("Recording set", "Opname staat klaar"),
    "badge_rec": ("REC", "REC"), "badge_remind": ("Reminder", "Herinnering"), "badge_switch": ("Switch", "Omschakelen"),
    "rec_hours": ("How long to record?", "Hoe lang opnemen?"), "rec_hours_n": ("{0} hours", "{0} uur"),
    "rec_hour": ("1 hour", "1 uur"), "rec_cancel": ("Cancel the recording", "Opname annuleren"),
    "rec_nochan": ("Pick a channel first (Fix channel)", "Kies eerst een zender (Zender kiezen)"),
    "soon": ("{0} starts in {1} minutes on {2}", "{0} begint over {1} minuten op {2}"),
    "soon_nochan": ("{0} starts in {1} minutes", "{0} begint over {1} minuten"),
    "switch_q": ("{0} is about to start. Switch to {1}?", "{0} begint zo. Omschakelen naar {1}?"),
    "switch_now": ("Switch", "Omschakelen"), "switch_cancel": ("Cancel", "Annuleren"),
    "auto_on": ("Automatic reminders for my teams: on", "Automatische herinneringen voor mijn teams: aan"),
    "auto_off": ("Automatic reminders for my teams: off", "Automatische herinneringen voor mijn teams: uit"),
    "rec_started": ("Recording started: {0}", "Opname gestart: {0}"),
    "rec_stopped": ("Recording stopped: {0}", "Opname gestopt: {0}"),
}


def t(key, *args):
    text = TX[key][1 if sc.NL else 0]
    return text.format(*args) if args else text


# ----------------------------------------------------------------------------- fix channel
def load_fix():
    data = ac.read_json(FIX_PATH, {})
    for key in ("game", "league", "team"):
        data.setdefault(key, {})
    return data


def set_fix(ev, scope, cid, team_ident=""):
    data = load_fix()
    key = {"game": ev["id"], "league": ev["league"], "team": team_ident}[scope]
    if not key:
        return
    cids = [c for c in data[scope].get(key, []) if c != int(cid)]
    data[scope][key] = [int(cid)] + cids
    ac.write_json(FIX_PATH, data)


def clear_fix_game(ev):
    data = load_fix()
    data["game"].pop(ev["id"], None)
    ac.write_json(FIX_PATH, data)


def fixed_cids(ev):
    """Channels you chose for this game, most specific first (game, team, competition)."""
    data = load_fix()
    out = list(data["game"].get(ev["id"], []))
    if ev["kind"] == "teams":
        for side in (ev["home"], ev["away"]):
            out += data["team"].get(side.get("id") or side.get("name"), [])
    out += data["league"].get(ev["league"], [])
    seen, ordered = set(), []
    for cid in out:
        if cid not in seen:
            seen.add(cid)
            ordered.append(cid)
    return ordered


def with_fixes(ev, found, guide):
    """Your own choices first (tagged 'Jouw keuze'), then what the guide found."""
    names, icons = guide.get("names", {}), guide.get("icons", {})
    mine = []
    for cid in fixed_cids(ev):
        raw = names.get(str(cid))
        if raw is None:
            continue
        mine.append({"cid": cid, "name": epg.clean_name(raw) or raw, "country": epg.country_of(raw), "q": epg.quality_of(raw),
                     "score": 4, "tag": t("yours"), "title": "", "start": ev["start"], "icon": icons.get(str(cid), ""),
                     "live": False})
    ids = {c["cid"] for c in mine}
    return (mine + [c for c in found if c["cid"] not in ids])[:epg.MAX_CHANNELS]


def all_channels(guide=None):
    """[(cid, 'Ziggo Sport 1 · FHD')] of every channel the PVR knows, Dutch/Belgian first."""
    guide = guide or epg.load()
    rows = []
    for cid, raw in (guide.get("names") or {}).items():
        quality = epg.quality_of(raw)
        label = epg.clean_name(raw) or raw
        rows.append((0 if epg.country_of(raw) in ("NL", "BE") else 1, label.lower(), int(cid),
                     f"{label}  ·  {quality}" if quality else label))
    rows.sort()
    return [(r[2], r[3]) for r in rows]


# ----------------------------------------------------------------------------- plan
def load_plan():
    data = ac.read_json(PLAN_PATH, {})
    data.setdefault("remind", {})
    data.setdefault("record", {})
    data.setdefault("auto", False)
    data.setdefault("dismissed", [])
    return data


def save_plan(plan):
    ac.write_json(PLAN_PATH, plan)


def set_reminder(ev, mode, cid=0):
    plan = load_plan()
    if mode in ("remind", "switch"):
        plan["remind"][ev["id"]] = {"start": ev["start"], "title": game_title(ev), "mode": mode, "cid": int(cid or 0),
                                    "league": ev["league"], "done": False}
        if ev["id"] in plan["dismissed"]:
            plan["dismissed"].remove(ev["id"])
    else:
        plan["remind"].pop(ev["id"], None)
        if ev["id"] not in plan["dismissed"]:
            plan["dismissed"].append(ev["id"])         # an automatic reminder must not come back
    save_plan(plan)


def reminder_mode(ev_id):
    return load_plan()["remind"].get(ev_id, {}).get("mode", "")


def set_recording(ev, cid, hours):
    plan = load_plan()
    plan["record"][ev["id"]] = {"start": ev["start"], "title": game_title(ev), "cid": int(cid), "hours": int(hours), "state": "wait"}
    save_plan(plan)


def cancel_recording(ev_id):
    plan = load_plan()
    rec = plan["record"].pop(ev_id, None)
    save_plan(plan)
    if rec and rec.get("state") == "on":
        epg.rpc("PVR.Record", {"record": False, "channel": rec["cid"]})


def recording(ev_id):
    return load_plan()["record"].get(ev_id)


def toggle_auto():
    plan = load_plan()
    plan["auto"] = not plan["auto"]
    save_plan(plan)
    return plan["auto"]


def game_title(ev):
    if ev["kind"] == "teams":
        return f"{ev['home'].get('name', '')} – {ev['away'].get('name', '')}"
    return ev.get("title") or ""


# ----------------------------------------------------------------------------- the helper
def best_channel(ev, plan_entry=None):
    """The channel to use: the one saved with the reminder, else the best match."""
    if plan_entry and plan_entry.get("cid"):
        return plan_entry["cid"]
    guide = epg.load()
    found = with_fixes(ev, epg.channels_for(ev, guide) if guide else [], guide or {})
    return found[0]["cid"] if found else 0


def channel_name(cid):
    raw = (epg.load().get("names") or {}).get(str(cid), "")
    return epg.clean_name(raw) or raw


def event_by_id(ev_id):
    return next((e for e in sc.all_cached() if e["id"] == ev_id), None)


def add_auto_reminders(plan, now):
    """'Automatic reminders for my teams': games of followed teams in the next 24 hours get a reminder."""
    if not plan["auto"]:
        return False
    follow = sc.load_follow()
    changed = False
    for ev in sc.all_cached():
        if ev["state"] != "pre" or not now < ev["start"] < now + 24 * 3600 or ev["kind"] != "teams":
            continue
        if ev["id"] in plan["remind"] or ev["id"] in plan["dismissed"]:
            continue
        if sc.is_following_team(follow, ev["home"]) or sc.is_following_team(follow, ev["away"]):
            plan["remind"][ev["id"]] = {"start": ev["start"], "title": game_title(ev), "mode": "remind", "cid": 0,
                                        "league": ev["league"], "done": False, "auto": True}
            changed = True
    return changed


def check(now=None, ask=None, notify=None, play=None):
    """One pass of the helper. ask(text, yes, no) -> True when the user cancels; notify(text); play(cid). Returns what it did."""
    now = now or time.time()
    ask = ask or ask_dialog
    notify = notify or send_notice
    play = play or epg.play
    plan = load_plan()
    did = []
    changed = add_auto_reminders(plan, now)
    for ev_id, rem in list(plan["remind"].items()):
        if rem["done"] and now > rem["start"] + GRACE:
            del plan["remind"][ev_id]
            changed = True
            continue
        if rem["done"]:
            continue
        lead = SWITCH_LEAD if rem["mode"] == "switch" else REMIND_LEAD
        if now < rem["start"] - lead:
            continue
        rem["done"] = True
        changed = True
        if now > rem["start"] + GRACE:
            continue                                    # too late to be useful
        ev = event_by_id(ev_id) or {"id": ev_id, "league": rem.get("league", ""), "kind": "event", "start": rem["start"],
                                    "home": {}, "away": {}, "title": rem["title"]}
        cid = best_channel(ev, rem)
        minutes = max(int(round((rem["start"] - now) / 60)), 0)
        name = channel_name(cid)
        if rem["mode"] == "switch" and cid:
            save_plan(plan)                              # the question blocks for 10 seconds
            if not ask(t("switch_q", rem["title"], name), t("switch_cancel"), t("switch_now")):
                play(cid)
                did.append(("switch", ev_id, cid))
        else:
            notify(t("soon", rem["title"], minutes, name) if name else t("soon_nochan", rem["title"], minutes))
            did.append(("remind", ev_id, cid))
    for ev_id, rec in list(plan["record"].items()):
        stop = rec["start"] + rec["hours"] * 3600
        if rec["state"] == "wait" and rec["start"] - RECORD_LEAD <= now < stop:
            epg.rpc("PVR.Record", {"record": True, "channel": rec["cid"]})
            rec["state"] = "on"
            changed = True
            notify(t("rec_started", rec["title"]))
            did.append(("rec_start", ev_id, rec["cid"]))
        elif rec["state"] == "on" and now >= stop:
            epg.rpc("PVR.Record", {"record": False, "channel": rec["cid"]})
            del plan["record"][ev_id]
            changed = True
            notify(t("rec_stopped", rec["title"]))
            did.append(("rec_stop", ev_id, rec["cid"]))
        elif rec["state"] == "wait" and now >= stop:
            del plan["record"][ev_id]                    # never started (Kodi was off): forget it
            changed = True
    if changed:
        save_plan(plan)
    return did


def ask_dialog(text, cancel_label, go_label):
    """10 seconds to cancel: no answer = go (Kodi answers 'no' when the dialog times out)."""
    return xbmcgui.Dialog().yesno(t("r_title"), text, nolabel=go_label, yeslabel=cancel_label, autoclose=10000)


def send_notice(text):
    xbmcgui.Dialog().notification(sc.t("title"), text, xbmcgui.NOTIFICATION_INFO, 8000, True)


# ----------------------------------------------------------------------------- the sport card on Home
HS = "lucent.hs."
HS_KEYS = ("show", "id", "title", "hname", "aname", "hlogo", "alogo", "hcol", "acol", "when", "live", "score", "league",
           "lglogo", "channel", "cid")
_HS_CHAN = {}          # event id -> (time asked, channel id)
_HS_REFRESH = [0.0]
HS_BEFORE = 6 * 3600   # show a game from 6 hours before kick-off


def _side_colour(side):
    value = (side.get("color") or "").strip("#")
    return value.upper() if len(value) == 6 else "2A3441"


def home_game(now=None):
    """The game of a team you follow to show on Home: live first, else the next one today (within 6 hours)."""
    now = now or time.time()
    follow = sc.load_follow()
    if not follow["teams"]:
        return None
    today = ac.today()
    live, coming = [], []
    for ev in sc.all_cached():
        if ev["kind"] != "teams":
            continue
        if not (sc.is_following_team(follow, ev["home"]) or sc.is_following_team(follow, ev["away"])):
            continue
        if ev["state"] == "in":
            live.append(ev)
        elif ev["state"] == "pre" and sc.local_day(ev["start"]) == today and ev["start"] - now < HS_BEFORE \
                and ev["start"] > now - 3 * 3600:
            coming.append(ev)
    live.sort(key=lambda e: e["start"])
    coming.sort(key=lambda e: e["start"])
    return (live or coming or [None])[0]


def _channel_for(ev, now):
    asked, cid = _HS_CHAN.get(ev["id"], (0, 0))
    if now - asked > 10 * 60:
        try:
            cid = best_channel(ev, load_plan()["remind"].get(ev["id"]))
        except Exception as error:  # noqa: BLE001
            sc.log(f"home card channel: {error}")
            cid = 0
        _HS_CHAN[ev["id"]] = (now, cid)
    return cid


def home_card(now=None):
    """Fill Window(home).Property(lucent.hs.*) for the sport card on Home (cleared when there is nothing)."""
    now = now or time.time()
    ev = None
    if not xbmc.getCondVisibility("Skin.HasSetting(lucent.hs.off)"):
        try:
            ev = home_game(now)
        except Exception as error:  # noqa: BLE001
            sc.log(f"home card: {error}")
    if ev and (ev["state"] == "in" or ev["start"] - now < 15 * 60) and now - _HS_REFRESH[0] > 120:
        _HS_REFRESH[0] = now
        try:
            sc.refresh(keys=[ev["league"]])          # fresh score / status while the game is (about to be) on
            ev = home_game(now) or ev
        except Exception as error:  # noqa: BLE001
            sc.log(f"home card refresh: {error}")
    if not ev:
        for key in HS_KEYS:
            HOME.clearProperty(HS + key)
        return
    cid = _channel_for(ev, now)
    live = ev["state"] == "in"
    if live:
        when = ev.get("status") or "LIVE"
    else:
        when = f"{sc.t('today')}  {sc.local_time(ev['start'])}"
    values = {
        "id": ev["id"], "title": game_title(ev),
        "hname": ev["home"].get("short") or ev["home"].get("name", ""), "aname": ev["away"].get("short") or ev["away"].get("name", ""),
        "hlogo": ev["home"].get("logo", ""), "alogo": ev["away"].get("logo", ""),
        "hcol": _side_colour(ev["home"]), "acol": _side_colour(ev["away"]),
        "when": when, "live": "1" if live else "",
        "score": f"{ev['home'].get('score', '')} – {ev['away'].get('score', '')}" if live else "",
        "league": sc.league_name_of(ev["league"]),
        "lglogo": sc.league_logo(ev["league"]),
        "channel": channel_name(cid) if cid else "", "cid": str(cid or ""),
    }
    for key, value in values.items():
        if HOME.getProperty(HS + key) != value:
            HOME.setProperty(HS + key, value)
    HOME.setProperty(HS + "show", "1")


def open_home_card():
    """OK on the sport card: watch the channel, or open the game in Sport when no channel is known."""
    cid = HOME.getProperty(HS + "cid")
    if cid.isdigit() and int(cid):
        epg.play(int(cid))
        return
    xbmc.executebuiltin("RunScript(special://skin/scripts/sport.py)")


# ----------------------------------------------------------------------------- goal notifications
def _num(value):
    try:
        return int(str(value).strip())
    except ValueError:
        return None


def _followed_game(follow, ev):
    if ev.get("kind") != "teams":
        return False
    return bool(sc.is_following_team(follow, ev["home"]) or sc.is_following_team(follow, ev["away"]))


def _watching(ev):
    """The score bar of the channel you are watching already shows this game: no extra pop-up then."""
    if not xbmc.getCondVisibility("Player.HasVideo") or not HOME.getProperty("live.sc.on"):
        return False
    return HOME.getProperty("live.sc.hname") in (ev["home"].get("short") or ev["home"]["name"], ev["away"].get("short") or ev["away"]["name"])


def goals(state):
    """A followed team scores: a notification with the score and the minute. Looks every 30 s, and only while a followed
    team is playing (the scores of that competition are asked again at most every 2 minutes)."""
    if xbmc.getCondVisibility("Skin.HasSetting(lucent.goals.off)"):
        return
    follow = sc.load_follow()
    if not follow["teams"]:
        return
    live = [e for e in sc.all_cached() if e.get("state") == "in" and _followed_game(follow, e)]
    if live:
        try:
            sc.refresh(keys=sorted({e["league"] for e in live}))
        except Exception as error:  # noqa: BLE001
            sc.log(f"goals refresh: {error}")
        live = [e for e in sc.all_cached() if e.get("state") == "in" and _followed_game(follow, e)]
    seen = state.setdefault("goals", {})
    for gone in [k for k in seen if k not in {e["id"] for e in live}]:
        del seen[gone]
    for ev in live:
        h, a = _num(ev["home"].get("score")), _num(ev["away"].get("score"))
        if h is None or a is None:
            continue
        before = seen.get(ev["id"])
        seen[ev["id"]] = (h, a)
        if before is None or (h <= before[0] and a <= before[1]) or _watching(ev):
            continue
        scorer = ev["home"] if h > before[0] else ev["away"]
        name = scorer.get("short") or scorer["name"]
        minute = ev.get("status") or ""
        xbmcgui.Dialog().notification(
            sc.t("goal") + (f"  ·  {minute}" if minute else ""),
            f"{ev['home'].get('short') or ev['home']['name']} {h} - {a} {ev['away'].get('short') or ev['away']['name']}   ({name})",
            scorer.get("logo") or xbmcgui.NOTIFICATION_INFO, 9000, True)


def tick(state, monitor):
    """One round of the sport helper (every 30 seconds): refresh, reminders / switching / recording, the Home card."""
    try:
        epg.restore_fullscreen(min_age=60)          # safety net: a preview script that ended before it could put it back
        plan = load_plan()
        if sc.has_follow() or plan["remind"] or plan["record"]:
            if plan["auto"] and time.time() - state.get("refresh", 0) > 15 * 60:
                state["refresh"] = time.time()
                sc.refresh()
                if time.time() - epg.load().get("fetched", 0) > 6 * 3600 and not xbmc.Player().isPlaying():
                    epg.scan(abort=monitor.abortRequested)
            check()
        goals(state)
        home_card()
    except Exception as error:  # noqa: BLE001
        sc.log(f"plan helper: {error}")
    finally:
        epg.forget()                                # do not keep the whole TV guide in the helper's memory

