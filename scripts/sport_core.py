# -*- coding: utf-8 -*-
"""Lucent: the Sport tab - data (matches, tables), what you follow, and the match -> IPTV channel link.

The screen is scripts/sport.py; the IPTV guide part is scripts/sport_epg.py. This file holds the rest:

  matches / tables   ESPN's public scoreboard + standings (free, no key). One call per competition for a whole
                     period (yesterday ... 13 days ahead), cached on disk (15 minutes, 2 minutes while a game is on).
  follow list        special://profile/addon_data/skin.lucent/sport_follow.json  (competitions, teams, free names)
  cache              special://profile/addon_data/skin.lucent/sport_cache.json

Competitions come from CATALOG below; each has a "kind":
  teams   two sides per game (football, basketball, ...): shown as  Home  v  Away
  event   a race weekend / a tournament / a fight card: shown with its name (Formula 1: every session is a row)
"""
import datetime
import re
import time
import unicodedata
from concurrent.futures import ThreadPoolExecutor

import xbmc

import agenda_core as ac
import info

DATA = ac.DATA
FOLLOW_PATH = DATA + "sport_follow.json"
CACHE_PATH = DATA + "sport_cache.json"
ESPN = "https://site.api.espn.com/apis/site/v2/sports/"
ESPN_V2 = "https://site.api.espn.com/apis/v2/sports/"
CACHE_VERSION = 1
TTL = 15 * 60
TTL_LIVE = 2 * 60
STANDINGS_TTL = 60 * 60
DAYS_BACK = 1
DAYS_AHEAD = 13
NL = ac.LANG == "nl"

TEXT = {
    "FP1": ("Free practice 1", "Vrije training 1"), "FP2": ("Free practice 2", "Vrije training 2"),
    "FP3": ("Free practice 3", "Vrije training 3"), "Qual": ("Qualifying", "Kwalificatie"),
    "Race": ("Race", "Race"), "Sprint": ("Sprint", "Sprint"), "SQ": ("Sprint qualifying", "Sprintkwalificatie"),
    "final": ("Full time", "Afgelopen"), "postponed": ("Postponed", "Uitgesteld"), "cancelled": ("Cancelled", "Afgelast"),
}

# key, ESPN path, name NL, name EN, sport, kind, shown in "All games", extra words that show up in a TV guide
CATALOG = [
    ("ned.1", "soccer/ned.1", "Eredivisie", "Eredivisie", "soccer", "teams", True, ["eredivisie"]),
    ("ned.2", "soccer/ned.2", "Keuken Kampioen Divisie", "Dutch Eerste Divisie", "soccer", "teams", True, ["keuken kampioen", "eerste divisie"]),
    ("ned.cup", "soccer/ned.cup", "KNVB Beker", "KNVB Cup", "soccer", "teams", True, ["knvb beker", "knvb cup"]),
    ("bel.1", "soccer/bel.1", "Jupiler Pro League", "Belgian Pro League", "soccer", "teams", True, ["jupiler", "pro league"]),
    ("eng.1", "soccer/eng.1", "Premier League", "Premier League", "soccer", "teams", True, ["premier league"]),
    ("eng.2", "soccer/eng.2", "Championship", "EFL Championship", "soccer", "teams", False, ["championship"]),
    ("eng.fa", "soccer/eng.fa", "FA Cup", "FA Cup", "soccer", "teams", True, ["fa cup"]),
    ("eng.league_cup", "soccer/eng.league_cup", "League Cup", "League Cup", "soccer", "teams", False, ["league cup", "carabao"]),
    ("esp.1", "soccer/esp.1", "La Liga", "La Liga", "soccer", "teams", True, ["la liga", "laliga"]),
    ("esp.copa_del_rey", "soccer/esp.copa_del_rey", "Copa del Rey", "Copa del Rey", "soccer", "teams", False, ["copa del rey"]),
    ("ger.1", "soccer/ger.1", "Bundesliga", "Bundesliga", "soccer", "teams", True, ["bundesliga"]),
    ("ger.dfb_pokal", "soccer/ger.dfb_pokal", "DFB-Pokal", "DFB-Pokal", "soccer", "teams", False, ["dfb pokal", "dfb-pokal"]),
    ("ita.1", "soccer/ita.1", "Serie A", "Serie A", "soccer", "teams", True, ["serie a"]),
    ("ita.coppa_italia", "soccer/ita.coppa_italia", "Coppa Italia", "Coppa Italia", "soccer", "teams", False, ["coppa italia"]),
    ("fra.1", "soccer/fra.1", "Ligue 1", "Ligue 1", "soccer", "teams", True, ["ligue 1"]),
    ("por.1", "soccer/por.1", "Liga Portugal", "Portuguese Liga", "soccer", "teams", True, ["liga portugal", "primeira liga"]),
    ("tur.1", "soccer/tur.1", "Süper Lig", "Turkish Super Lig", "soccer", "teams", False, ["super lig", "süper lig"]),
    ("sco.1", "soccer/sco.1", "Scottish Premiership", "Scottish Premiership", "soccer", "teams", False, ["scottish premiership"]),
    ("usa.1", "soccer/usa.1", "MLS", "MLS", "soccer", "teams", False, ["mls", "major league soccer"]),
    ("uefa.champions", "soccer/uefa.champions", "Champions League", "Champions League", "soccer", "teams", True, ["champions league"]),
    ("uefa.europa", "soccer/uefa.europa", "Europa League", "Europa League", "soccer", "teams", True, ["europa league"]),
    ("uefa.europa.conf", "soccer/uefa.europa.conf", "Conference League", "Conference League", "soccer", "teams", True, ["conference league"]),
    ("uefa.nations", "soccer/uefa.nations", "Nations League", "Nations League", "soccer", "teams", True, ["nations league"]),
    ("uefa.euro", "soccer/uefa.euro", "EK voetbal", "European Championship", "soccer", "teams", True, ["ek voetbal", "european championship", "euro 20"]),
    ("fifa.world", "soccer/fifa.world", "WK voetbal", "World Cup", "soccer", "teams", True, ["wk voetbal", "world cup", "wereldkampioenschap"]),
    ("fifa.worldq.uefa", "soccer/fifa.worldq.uefa", "WK-kwalificatie Europa", "World Cup qualifying (Europe)", "soccer", "teams", True, ["wk kwalificatie", "wk-kwalificatie", "world cup qualifying", "wk kwal"]),
    ("fifa.friendly", "soccer/fifa.friendly", "Oefeninterlands", "International friendlies", "soccer", "teams", False, ["oefeninterland", "vriendschappelijk", "friendly"]),
    ("ned.w.1", "soccer/ned.w.1", "Eredivisie Vrouwen", "Dutch Eredivisie Women", "soccer", "teams", False, ["eredivisie vrouwen"]),
    ("nba", "basketball/nba", "NBA", "NBA", "basketball", "teams", True, ["nba"]),
    ("nfl", "football/nfl", "NFL", "NFL", "football", "teams", True, ["nfl"]),
    ("nhl", "hockey/nhl", "NHL", "NHL", "hockey", "teams", False, ["nhl"]),
    ("mlb", "baseball/mlb", "MLB", "MLB", "baseball", "teams", False, ["mlb"]),
    ("f1", "racing/f1", "Formule 1", "Formula 1", "racing", "event", True, ["formule 1", "formula 1", "f1"]),
    ("atp", "tennis/atp", "ATP-tennis", "ATP tennis", "tennis", "event", False, ["atp"]),
    ("wta", "tennis/wta", "WTA-tennis", "WTA tennis", "tennis", "event", False, ["wta"]),
    ("pga", "golf/pga", "PGA Tour", "PGA Tour", "golf", "event", False, ["pga"]),
    ("ufc", "mma/ufc", "UFC", "UFC", "mma", "event", True, ["ufc"]),
]
LEAGUES = {row[0]: {"key": row[0], "path": row[1], "name": row[2] if NL else row[3], "sport": row[4], "kind": row[5],
                    "default": row[6], "words": list(row[7]) + [row[2].lower(), row[3].lower()]} for row in CATALOG}
SPORT_NAMES = {"soccer": ("Football", "Voetbal"), "basketball": ("Basketball", "Basketbal"),
               "football": ("American football", "American football"), "hockey": ("Ice hockey", "IJshockey"),
               "baseball": ("Baseball", "Honkbal"), "racing": ("Racing", "Racen"), "tennis": ("Tennis", "Tennis"),
               "golf": ("Golf", "Golf"), "mma": ("Fighting", "Vechtsport")}
STOP_WORDS = {"fc", "afc", "sc", "cf", "fk", "sv", "vv", "ac", "as", "us", "ss", "cd", "ud", "sk", "bk", "if", "ik", "fc.", "the", "de", "la", "le", "of"}


TX = {
    "title": ("Sport", "Sport"), "mine": ("My sport", "Mijn sport"), "all": ("All games", "Alle wedstrijden"),
    "tables": ("Tables", "Standen"), "follow": ("Follow", "Volgen"),
    "watch": ("WATCH ON YOUR CHANNELS", "KIJK OP JE ZENDERS"),
    "nochan": ("No channel found in your guide", "Geen zender gevonden in je gids"),
    "noguide": ("No IPTV guide found - set up IPTV Simple Client", "Geen IPTV-gids gevonden - stel IPTV Simple Client in"),
    "gp": ("P", "G"), "gd": ("+/-", "DV"), "pts": ("Pts", "Pnt"),
    "powered": ("Data from ESPN  ·  channels from your IPTV guide", "Gegevens van ESPN  ·  zenders uit je IPTV-gids"),
    "sure": ("Showing it", "Zendt uit"), "maybe": ("Maybe", "Misschien"), "livenow": ("Live now", "Nu live"),
    "loading": ("Loading games…", "Wedstrijden laden…"), "guide": ("Reading guide… {0}%", "Gids lezen… {0}%"),
    "empty_title": ("Nothing to show yet", "Nog niets om te tonen"),
    "empty_mine": ("Choose what you want to follow with the Follow button: competitions, teams or a name "
                   "(a driver, a club, a fighter). Their games and the channels that show them appear here.",
                   "Kies met de knop Volgen wat je wilt volgen: competities, teams of een naam (een coureur, een club, "
                   "een vechter). Hun wedstrijden en de zenders die ze uitzenden komen hier te staan."),
    "empty_day": ("No games on this day", "Geen wedstrijden op deze dag"),
    "empty_net": ("The games could not be loaded. Check the internet connection and try again.",
                  "De wedstrijden konden niet worden geladen. Controleer de internetverbinding en probeer opnieuw."),
    "follow_team": ("Follow {0}", "Volg {0}"), "unfollow_team": ("Stop following {0}", "Stop met volgen: {0}"),
    "show_table": ("Show table", "Bekijk stand"),
    "m_leagues": ("Choose competitions", "Competities kiezen"), "m_teams": ("Choose teams", "Teams kiezen"),
    "m_name": ("Add a name (team, driver, fighter…)", "Naam toevoegen (team, coureur, vechter…)"),
    "m_manage": ("Remove from my list", "Uit mijn lijst halen"), "m_guide": ("Read the IPTV guide again", "IPTV-gids opnieuw lezen"),
    "q_league": ("Which competition?", "Welke competitie?"), "q_name": ("Name to follow", "Naam om te volgen"),
    "q_remove": ("Remove", "Verwijderen"), "q_cancel": ("Keep", "Laten staan"),
    "notable": ("No table for this competition", "Geen stand beschikbaar voor deze competitie"),
    "today": ("Today", "Vandaag"), "tomorrow": ("Tomorrow", "Morgen"), "yesterday": ("Yesterday", "Gisteren"),
    "tvguide": ("TV guide", "TV-gids"), "liveup": ("Live & upcoming", "Live & binnenkort"),
    "m_countries": ("Choose countries", "Landen kiezen"),
    "m_search": ("Search team, country or competition", "Zoeken: team, land of competitie"),
    "q_search": ("Type a name", "Typ een naam"), "m_order": ("Change the order", "Volgorde aanpassen"),
    "nohit": ("Nothing found for \"{0}\"", "Niets gevonden voor \"{0}\""), "as_name": ("Follow \"{0}\" as a name", "Volg \"{0}\" als naam"),
    "q_move": ("Move where?", "Waarheen verplaatsen?"), "up": ("Up", "Omhoog"), "down": ("Down", "Omlaag"), "first": ("To the top", "Naar boven"), "round": ("Round", "Ronde"),
}


def t(key, *args):
    text = TX[key][1 if NL else 0]
    return text.format(*args) if args else text


# national teams: ESPN name -> Dutch name (shown when the phone / box is Dutch; the TV guide uses the Dutch names)
COUNTRIES = {
    "Netherlands": "Nederland", "Belgium": "België", "Germany": "Duitsland", "France": "Frankrijk", "England": "Engeland",
    "Spain": "Spanje", "Italy": "Italië", "Portugal": "Portugal", "Croatia": "Kroatië", "Denmark": "Denemarken",
    "Switzerland": "Zwitserland", "Austria": "Oostenrijk", "Poland": "Polen", "Turkey": "Turkije", "Norway": "Noorwegen",
    "Sweden": "Zweden", "Scotland": "Schotland", "Wales": "Wales", "Ireland": "Ierland", "Northern Ireland": "Noord-Ierland",
    "Ukraine": "Oekraïne", "Greece": "Griekenland", "Czechia": "Tsjechië", "Serbia": "Servië", "Hungary": "Hongarije",
    "Romania": "Roemenië", "Slovakia": "Slowakije", "Slovenia": "Slovenië", "Finland": "Finland", "Iceland": "IJsland",
    "Morocco": "Marokko", "Senegal": "Senegal", "Nigeria": "Nigeria", "Egypt": "Egypte", "Ghana": "Ghana",
    "Brazil": "Brazilië", "Argentina": "Argentinië", "Uruguay": "Uruguay", "Colombia": "Colombia", "Chile": "Chili",
    "Ecuador": "Ecuador", "Mexico": "Mexico", "United States": "Verenigde Staten", "Canada": "Canada",
    "Japan": "Japan", "South Korea": "Zuid-Korea", "Australia": "Australië", "Saudi Arabia": "Saoedi-Arabië",
    "Iran": "Iran", "Suriname": "Suriname", "Curaçao": "Curaçao", "Indonesia": "Indonesië",
}
COUNTRY_NL = {en: (nl if NL else en) for en, nl in COUNTRIES.items()}
NATIONAL_LEAGUE = "fifa.friendly"


def country_label(name):
    return COUNTRY_NL.get(name, name)


def team_ident(team):
    return team.get("id") or team.get("name")


def sport_name(sport):
    return SPORT_NAMES.get(sport, (sport, sport))[1 if NL else 0]


def log(text):
    xbmc.log(f"[skin.lucent] sport: {text}", xbmc.LOGINFO)


# ----------------------------------------------------------------------------- text and time
def norm(text):
    """Lower case, no accents, no punctuation: 'MAC³PARK Stadion' -> 'mac3park stadion'."""
    text = unicodedata.normalize("NFKD", str(text or "")).encode("ascii", "ignore").decode("ascii").lower()
    return re.sub(r"[^a-z0-9]+", " ", text).strip()


def has_phrase(text, phrase):
    """True when the whole words of phrase (both already normalised) are in text."""
    return bool(phrase) and f" {phrase} " in f" {text} "


def parse_iso(value):
    """'2026-10-30T18:30Z' (UTC) -> timestamp, 0 when it cannot be read."""
    value = (value or "").strip()
    for fmt in ("%Y-%m-%dT%H:%MZ", "%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%dT%H:%M:%S.%fZ", "%Y-%m-%d"):
        try:
            stamp = datetime.datetime.strptime(value, fmt)
        except ValueError:
            continue
        return int(stamp.replace(tzinfo=datetime.timezone.utc).timestamp())
    return 0


def local_day(stamp):
    return datetime.datetime.fromtimestamp(stamp).date()


def local_time(stamp):
    return datetime.datetime.fromtimestamp(stamp).strftime("%H:%M")


def espn_day(day):
    return day.strftime("%Y%m%d")


def window():
    today = ac.today()
    return today - datetime.timedelta(days=DAYS_BACK), today + datetime.timedelta(days=DAYS_AHEAD)


# ----------------------------------------------------------------------------- ESPN -> events
def side(competitor):
    team = competitor.get("team") or competitor.get("athlete") or {}
    full = team.get("displayName") or team.get("name") or ""
    return {"id": str(team.get("id") or ""), "name": country_label(full), "en": full,
            "short": country_label(team.get("shortDisplayName") or team.get("displayName") or ""), "abbr": team.get("abbreviation") or "",
            "nick": team.get("name") or "", "logo": team.get("logo") or (team.get("flag") or {}).get("href") or "",
            "score": str(competitor.get("score", "") if not isinstance(competitor.get("score"), dict) else competitor["score"].get("displayValue", "")),
            "color": team.get("color") or "", "alt": team.get("alternateColor") or ""}


def status_of(ev):
    kind = ((ev.get("status") or {}).get("type") or {})
    state = kind.get("state") or "pre"
    name = (kind.get("name") or "").upper()
    label = ""
    if "POSTPONED" in name:
        label = TEXT["postponed"][1 if NL else 0]
    elif "CANCEL" in name:
        label = TEXT["cancelled"][1 if NL else 0]
    elif state == "in":
        label = kind.get("shortDetail") or (ev.get("status") or {}).get("displayClock") or "LIVE"
    elif state == "post":
        label = TEXT["final"][1 if NL else 0]
    return state, label


def parse_team_event(league, ev):
    comp = (ev.get("competitions") or [{}])[0]
    competitors = comp.get("competitors") or []
    if len(competitors) < 2:
        return None
    home = next((c for c in competitors if c.get("homeAway") == "home"), competitors[0])
    away = next((c for c in competitors if c.get("homeAway") == "away"), competitors[1])
    state, label = status_of(comp if comp.get("status") else ev)
    venue = comp.get("venue") or {}
    city = (venue.get("address") or {}).get("city", "")
    notes = [n.get("headline") for n in (comp.get("notes") or []) if n.get("headline")]
    start = parse_iso(ev.get("date"))
    if not start:
        return None
    return {"id": f"{league}:{ev.get('id')}", "league": league, "kind": "teams", "start": start, "state": state, "status": label,
            "home": side(home), "away": side(away), "title": "", "venue": ", ".join(x for x in (venue.get("fullName"), city) if x),
            "round": notes[0] if notes else ""}


def session_name(code):
    pair = TEXT.get(code)
    return pair[1 if NL else 0] if pair else code


def parse_event_kind(league, ev):
    """Formula 1: one row per session; other sports: one row per event (tournament, fight card)."""
    rows = []
    if league == "f1" and ev.get("competitions"):
        for comp in ev["competitions"]:
            code = (comp.get("type") or {}).get("abbreviation") or ""
            start = parse_iso(comp.get("date") or comp.get("startDate"))
            if not start:
                continue
            state, label = status_of(comp if comp.get("status") else ev)
            rows.append({"id": f"{league}:{ev.get('id')}:{code}", "league": league, "kind": "event", "start": start, "state": state,
                         "status": label, "home": {}, "away": {}, "title": ev.get("name") or "", "sub": session_name(code),
                         "venue": "", "round": ""})
        return rows
    start = parse_iso(ev.get("date"))
    if start:
        end = parse_iso(ev.get("endDate"))
        state, label = status_of(ev)
        rows.append({"id": f"{league}:{ev.get('id')}", "league": league, "kind": "event", "start": start, "end": end, "state": state,
                     "status": label, "home": {}, "away": {}, "title": ev.get("name") or "", "sub": "", "venue": "", "round": ""})
    return rows


def parse_scoreboard(league, data):
    info_ = LEAGUES[league]
    out = []
    logos = ((data or {}).get("leagues") or [{}])[0].get("logos") or [{}]
    logo = logos[0].get("href", "")
    for ev in (data or {}).get("events") or []:
        try:
            if info_["kind"] == "teams":
                row = parse_team_event(league, ev)
                if row:
                    out.append(row)
            else:
                out.extend(parse_event_kind(league, ev))
        except Exception as error:  # noqa: BLE001 - one odd record must not hide the rest
            log(f"{league}: skipped a record: {error}")
    for row in out:
        row["lg"] = logo
    return out


def parse_standings(data):
    """[{header, rank, team, id, logo, gp, gd, pts, note}] - one header row per group (conference) when there are several."""
    sections = []

    def walk(node, title):
        standings = node.get("standings") or {}
        if standings.get("entries"):
            sections.append((title, standings["entries"]))
        for child in node.get("children") or []:
            walk(child, child.get("name") or title)

    walk(data or {}, "")
    rows = []
    for title, entries in sections:
        if len(sections) > 1:
            rows.append({"header": title})
        parsed = []
        for index, entry in enumerate(entries, 1):
            stats = {s.get("name"): s for s in entry.get("stats") or []}

            def shown(name, stats=stats):
                return str((stats.get(name) or {}).get("displayValue", "") or "")

            team = entry.get("team") or {}
            logos = team.get("logos") or []
            try:
                rank = int(float((stats.get("rank") or {}).get("value", index)))
            except (TypeError, ValueError):
                rank = index
            gp = shown("gamesPlayed") or shown("overall")
            pts = shown("points") or shown("winPercent")
            gd = shown("pointDifferential")
            parsed.append({"rank": rank, "team": team.get("displayName") or team.get("name") or "", "id": str(team.get("id") or ""),
                           "logo": team.get("logo") or (logos[0].get("href") if logos else ""), "gp": gp, "gd": gd, "pts": pts,
                           "note": ((entry.get("note") or {}).get("color") or "")})
        parsed.sort(key=lambda row: row["rank"])
        rows.extend(parsed)
    return rows


# ----------------------------------------------------------------------------- cache + refresh
def load_cache():
    data = ac.read_json(CACHE_PATH, {})
    if data.get("v") != CACHE_VERSION:
        data = {"v": CACHE_VERSION}
    data.setdefault("leagues", {})
    data.setdefault("standings", {})
    return data


def save_cache(cache):
    try:
        ac.write_json(CACHE_PATH, cache)
    except Exception as error:  # noqa: BLE001
        log(f"cannot save cache: {error}")


def live_or_close(events, now):
    return any(e["state"] == "in" or abs(e["start"] - now) < 3 * 3600 for e in events)


def is_stale(entry, now, first, last):
    if not entry or entry.get("from", "9") > first or entry.get("to", "") < last:
        return True
    age = now - entry.get("fetched", 0)
    return age > (TTL_LIVE if live_or_close(entry.get("events", []), now) else TTL)


def fetch_league(key, first, last):
    path = LEAGUES[key]["path"]
    data = info.http(f"{ESPN}{path}/scoreboard?dates={first.replace('-', '')}-{last.replace('-', '')}&limit=400")
    return parse_scoreboard(key, data)


def league_keys():
    """Competitions shown in 'All games' plus everything you follow."""
    keys = [k for k, v in LEAGUES.items() if v["default"]]
    for k in load_follow()["leagues"]:
        if k in LEAGUES and k not in keys:
            keys.append(k)
    for team in load_follow()["teams"]:
        league = team.get("league")
        if league not in LEAGUES:
            continue
        wider = [k for k, v in LEAGUES.items() if v["sport"] == "soccer" and v["kind"] == "teams"] \
            if LEAGUES[league]["sport"] == "soccer" else [league]
        for k in wider:
            if k not in keys:
                keys.append(k)
    return keys


def refresh(force=False, keys=None, progress=None):
    """Fetch the competitions that are out of date. Returns True when something changed."""
    now = int(time.time())
    first_d, last_d = window()
    first, last = first_d.isoformat().replace("-", ""), last_d.isoformat().replace("-", "")
    cache = load_cache()
    todo = [k for k in (keys or league_keys()) if force or is_stale(cache["leagues"].get(k), now, first, last)]
    if not todo:
        return False
    done = [0]

    def work(key):
        try:
            events = fetch_league(key, first, last)
            return key, events
        except Exception as error:  # noqa: BLE001 - one competition failing must not stop the others
            log(f"{key}: {error}")
            return key, None

    changed = False
    with ThreadPoolExecutor(max_workers=6) as pool:
        for key, events in pool.map(work, todo):
            done[0] += 1
            if progress:
                progress(done[0], len(todo))
            if events is None:
                if key in cache["leagues"]:
                    cache["leagues"][key]["fetched"] = now - TTL + 60      # try again in a minute
                continue
            cache["leagues"][key] = {"fetched": now, "from": first, "to": last, "events": events}
            changed = True
    save_cache(cache)
    return changed


def standings(key, force=False):
    """Table rows of a competition ([] when ESPN has none)."""
    cache = load_cache()
    entry = cache["standings"].get(key)
    if entry and not force and time.time() - entry.get("fetched", 0) < STANDINGS_TTL:
        return entry["rows"]
    try:
        rows = parse_standings(info.http(f"{ESPN_V2}{LEAGUES[key]['path']}/standings"))
    except Exception as error:  # noqa: BLE001
        log(f"standings {key}: {error}")
        return entry["rows"] if entry else []
    cache["standings"][key] = {"fetched": time.time(), "rows": rows}
    save_cache(cache)
    return rows


def teams_of(key):
    """[(id, name, logo)] of a competition, from its table (falls back to the games)."""
    seen, out = set(), []
    for row in standings(key):
        if row.get("id") and row["id"] not in seen:
            seen.add(row["id"])
            out.append((row["id"], row["team"], row["logo"]))
    if not out:
        for ev in load_cache()["leagues"].get(key, {}).get("events", []):
            for s in (ev.get("home"), ev.get("away")):
                if s and s.get("id") and s["id"] not in seen:
                    seen.add(s["id"])
                    out.append((s["id"], s["name"], s["logo"]))
    return sorted(out, key=lambda t: t[1])


# ----------------------------------------------------------------------------- follow list
def load_follow():
    data = ac.read_json(FOLLOW_PATH, {})
    data.setdefault("leagues", [])
    data.setdefault("teams", [])
    data.setdefault("names", [])
    data.setdefault("order", [])
    return data


def save_follow(data):
    ac.write_json(FOLLOW_PATH, data)


def is_following_team(follow, side_):
    if not side_:
        return False
    ids = {t["id"] for t in follow["teams"] if t.get("id")}
    names = {norm(t["name"]) for t in follow["teams"]}
    return (side_.get("id") in ids and side_.get("id")) or norm(side_.get("name")) in names


def toggle_team(league, side_):
    """Follow / unfollow a team of a game. Returns True when it is followed afterwards."""
    follow = load_follow()
    keep = [t for t in follow["teams"] if not ((t["id"] and t["id"] == side_["id"]) or norm(t["name"]) == norm(side_["name"]))]
    followed = len(keep) == len(follow["teams"])
    if followed:
        keep.append({"league": league, "id": side_["id"], "name": side_["name"], "logo": side_.get("logo", "")})
    follow["teams"] = keep
    save_follow(follow)
    return followed


def has_follow():
    follow = load_follow()
    return bool(follow["leagues"] or follow["teams"] or follow["names"])


# ----------------------------------------------------------------------------- picking events
def all_cached():
    cache = load_cache()
    out = []
    for key, entry in cache["leagues"].items():
        if key in LEAGUES:
            out.extend(entry.get("events", []))
    return out


def order(events):
    """Live games first, then what is coming up, then what is finished (latest first)."""
    live = sorted((e for e in events if e["state"] == "in"), key=lambda e: e["start"])
    coming = sorted((e for e in events if e["state"] == "pre"), key=lambda e: e["start"])
    done = sorted((e for e in events if e["state"] == "post"), key=lambda e: -e["start"])
    return live, coming, done


def events_on(day, keys=None):
    shown = set(keys or [k for k, v in LEAGUES.items() if v["default"]] + load_follow()["leagues"]
                + [t["league"] for t in load_follow()["teams"]])
    return [e for e in all_cached() if e["league"] in shown and local_day(e["start"]) == day]


def mine_events():
    """Games of what you follow (competitions, teams), live first, then by time. Results of yesterday are included."""
    follow = load_follow()
    out = []
    for ev in all_cached():
        if ev["league"] in follow["leagues"]:
            out.append(ev)
        elif ev["kind"] == "teams" and (is_following_team(follow, ev["home"]) or is_following_team(follow, ev["away"])):
            out.append(ev)
    live, coming, done = order(out)
    done = [e for e in done if local_day(e["start"]) >= ac.today() - datetime.timedelta(days=1)]
    return live + coming + list(reversed(done))


def team_terms(side_):
    """Names a TV guide might use for a team: ['pec zwolle', 'zwolle'] (short names and stop words left out)."""
    terms = set()
    for value in (side_.get("name"), side_.get("short"), side_.get("nick"), side_.get("en")):
        n = norm(value)
        if len(n) >= 4 and n not in STOP_WORDS:
            terms.add(n)
        stripped = " ".join(w for w in n.split() if w not in STOP_WORDS)
        if len(stripped) >= 4:
            terms.add(stripped)
    return terms


def league_terms(league):
    return {norm(w) for w in LEAGUES[league]["words"] if len(norm(w)) >= 2}


# ----------------------------------------------------------------------------- sections of "My sport"
def section_key(kind, ident):
    return f"{kind}:{ident}"


def sections(follow=None):
    """Everything you follow, in your own order: [(key, kind, ident, title)]."""
    follow = follow or load_follow()
    items = ([(section_key("team", team_ident(t)), "team", team_ident(t), t["name"]) for t in follow["teams"]]
             + [(section_key("league", k), "league", k, LEAGUES[k]["name"]) for k in follow["leagues"] if k in LEAGUES]
             + [(section_key("name", n), "name", n, n) for n in follow["names"]])
    by_key = {row[0]: row for row in items}
    ordered = [by_key[k] for k in follow["order"] if k in by_key]
    return ordered + [row for row in items if row[0] not in follow["order"]]


def save_order(keys):
    follow = load_follow()
    follow["order"] = keys
    save_follow(follow)


def events_of_team(team_id, name):
    out = []
    n = norm(name)
    for ev in all_cached():
        if ev["kind"] != "teams":
            continue
        for s in (ev["home"], ev["away"]):
            if (team_id and s.get("id") == team_id) or norm(s.get("name")) == n:
                out.append(ev)
                break
    return out


def place_text(team):
    """'2e in Eredivisie' from the stored table (no network); '' when unknown."""
    league = team.get("league")
    cache = load_cache()["standings"].get(league)
    if not cache or league not in LEAGUES:
        return ""
    for row in cache["rows"]:
        if row.get("id") == team["id"] and row.get("rank"):
            rank = row["rank"]
            return (f"{rank}e in {LEAGUES[league]['name']}" if NL else f"{rank}{'st' if rank == 1 else 'nd' if rank == 2 else 'rd' if rank == 3 else 'th'} in {LEAGUES[league]['name']}")
    return ""


def search_catalog(query):
    """Competitions and teams that match a typed word: [(kind, ident, label, extra)]. Teams come from the games we hold."""
    q = norm(query)
    if not q:
        return []
    out = []
    for key, lg in LEAGUES.items():
        hay = norm(f"{lg['name']} {' '.join(lg['words'])}")
        if q in hay:
            out.append(("league", key, f"{sport_name(lg['sport'])}  ·  {lg['name']}", ""))
    for en, nl in sorted(COUNTRIES.items(), key=lambda kv: kv[1]):
        if q in norm(nl) or q in norm(en):
            out.append(("country", en, f"{'Land' if NL else 'Country'}  ·  {COUNTRY_NL[en]}", ""))
    seen = set()
    for ev in all_cached():
        if ev["kind"] != "teams":
            continue
        for s in (ev["home"], ev["away"]):
            if s.get("id") and norm(s["name"]).find(q) >= 0 and (s["id"], s["name"]) not in seen:
                seen.add((s["id"], s["name"]))
                out.append(("team", s["id"], f"{s['name']}  ·  {league_name_of(ev['league'])}", ev["league"] + "|" + s["name"] + "|" + s.get("logo", "")))
    return out


def league_name_of(key):
    return LEAGUES[key]["name"] if key in LEAGUES else key
