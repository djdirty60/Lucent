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
import urllib.request
from concurrent.futures import ThreadPoolExecutor

import xbmc

import agenda_core as ac
import info

DATA = ac.DATA
FOLLOW_PATH = DATA + "sport_follow.json"
CACHE_PATH = DATA + "sport_cache.json"
ESPN = "https://site.api.espn.com/apis/site/v2/sports/"
ESPN_V2 = "https://site.api.espn.com/apis/v2/sports/"
CACHE_VERSION = 3
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

import sport_catalog

CATALOG = sport_catalog.build()
LEAGUES = {row[0]: {"key": row[0], "path": row[1], "name": row[2] if NL else row[3], "sport": row[4], "kind": row[5],
                    "default": row[6], "words": list(row[7]) + [row[2].lower(), row[3].lower()]} for row in CATALOG}
SPORT_NAMES = {"rugby": ("Rugby", "Rugby"), "aussie": ("Australian football", "Australian football"),
               "soccer": ("Football", "Voetbal"), "basketball": ("Basketball", "Basketbal"),
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
    "c_record": ("Record", "Seizoen"), "c_home": ("Home", "Thuis"), "c_away": ("Away", "Uit"),
    "c_nonext": ("No game planned", "Geen wedstrijd gepland"), "c_watch": ("Watch now", "Kijk nu"),
    "c_now": ("NOW", "NU"), "c_last1": ("LAST", "LAATSTE"), "c_next1": ("NEXT", "VOLGENDE"),
    "c_theirgames": ("All their games", "Al hun wedstrijden"), "c_teaminfo": ("Team info", "Teaminfo"),
    "c_games": ("All games", "Alle wedstrijden"), "c_last": ("LAST RESULTS", "LAATSTE UITSLAGEN"), "c_next": ("NEXT GAME", "VOLGENDE WEDSTRIJD"),
    "q_remove": ("Remove", "Verwijderen"), "q_cancel": ("Keep", "Laten staan"),
    "notable": ("No table for this competition", "Geen stand beschikbaar voor deze competitie"),
    "today": ("Today", "Vandaag"), "tomorrow": ("Tomorrow", "Morgen"), "yesterday": ("Yesterday", "Gisteren"),
    "nogames": ("No games planned right now", "Geen wedstrijden gepland"),
    "previewhint": ("OK on a channel: watch here", "OK op een zender: hier kijken"), "stoptext": ("Stop channel", "Zender stoppen"),
    "c_length": ("Length", "Lengte"), "c_laps": ("laps", "ronden"), "c_turns": ("turns", "bochten"), "c_cw": ("clockwise", "met de klok mee"),
    "c_ccw": ("anti-clockwise", "tegen de klok in"), "circ_record": ("Lap record", "Rondrecord"), "fullhint": ("OK again: full screen", "Nog een keer OK: beeldvullend"),
    "dayerr": ("ESPN did not answer for {} of {} days ({})", "ESPN gaf geen antwoord voor {} van {} dagen ({})"),
    "neterr": ("Could not reach ESPN ({})", "ESPN niet bereikbaar ({})"),
    "list_n": ("{} games", "{} wedstrijden"),
    "f_search": ("Search", "Zoeken"), "f_order": ("Order", "Volgorde"), "f_more": ("More", "Meer"),
    "f_following": ("FOLLOWING · {}", "VOLGEN · {}"), "f_followed": ("Following", "Gevolgd"), "f_teams": ("Teams", "Teams"),
    "f_competition": ("Competition", "Competitie"), "f_follow": ("★  Follow {}", "★  Volg {}"), "f_stop": ("✓  Following {}  (stop)", "✓  Je volgt {}  (stoppen)"),
    "f_hint": ("OK on a team follows it  ·  OK on a name above stops following", "OK op een team volgt het  ·  OK op een naam bovenin stopt met volgen"),
    "f_noteams": ("This competition has no teams. Follow the whole competition with the button above.",
                  "Deze competitie heeft geen teams. Volg de hele competitie met de knop hierboven."),
    "g_form": ("FORM · LAST FIVE", "VORM · LAATSTE 5"), "g_info": ("INFO", "INFO"), "g_matchinfo": ("MATCH INFO", "WEDSTRIJDINFO"),
    "g_fulltable": ("Full table  ›", "Volledige stand  ›"), "g_sessions": ("SCHEDULE", "PROGRAMMA"), "res_pre": ("Not held yet", "Nog niet gereden"), "res_none": ("No results available", "Geen uitslag beschikbaar"),
    "res_loading": ("Loading results…", "Uitslag laden…"), "res_live": ("In progress - provisional", "Bezig - voorlopig"), "res_title": ("Results", "Uitslag"), "g_home": ("Home", "Thuis"), "g_away": ("Away", "Uit"),
    "g_teamstats": ("TEAM STATS", "TEAMSTATISTIEKEN"), "g_top": ("TOP PERFORMERS", "TOPSPELERS"), "g_scoring": ("LATEST SCORING", "LAATSTE DOELPUNTEN"),
    "g_possession": ("Possession", "Balbezit"), "g_shots": ("Shots", "Schoten"), "g_ontarget": ("On goal", "Op doel"), "g_corners": ("Corner kicks", "Hoekschoppen"),
    "g_nodata": ("No match statistics yet", "Nog geen wedstrijdstatistieken"), "g_showing": ("SHOWING IT", "ZENDT HET UIT"),
    "g_standings": ("{} STANDINGS", "{} STAND"), "g_over": ("Finished", "Afgelopen"),
    "g_in_dh": ("in {} days {} h", "over {} dagen {} u"), "g_in_h": ("in {} h {} min", "over {} u {} min"), "g_in_m": ("in {} min", "over {} min"),
    "pvr_off": ("Live TV is switched off in Kodi (Settings > PVR)", "Live TV staat uit in Kodi (Instellingen > PVR)"),
    "pvr_nochan": ("No TV channels yet - IPTV Simple Client is still loading or has no playlist", "Nog geen tv-zenders - IPTV Simple Client laadt nog of heeft geen zenderlijst"),
    "pvr_noepg": ("Channels found, but no programme guide yet", "Zenders gevonden, maar nog geen tv-gids"),
    "loading_title": ("Loading games", "Wedstrijden laden"), "loading_text": ("One moment, the first time takes a little longer…", "Een momentje, de eerste keer duurt iets langer…"),
    "loading_pct": ("{}%", "{}%"), "updating": ("Updating…", "Bijwerken…"),
    "play_on": ("Watch on", "Kijk op"), "n_games": ("{} games", "{} wedstrijden"),
    "hint": ("OK: game info   ◄ ►: browse the row   ▲ ▼: next team", "OK: wedstrijdinfo   ◄ ►: door de rij   ▲ ▼: volgend team"),
    "hint_all": ("OK: game info", "OK: wedstrijdinfo"),
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
COUNTRY_ISO = {
    "Netherlands": "nl", "Belgium": "be", "Germany": "de", "France": "fr", "England": "gb-eng", "Spain": "es", "Italy": "it",
    "Portugal": "pt", "Croatia": "hr", "Denmark": "dk", "Switzerland": "ch", "Austria": "at", "Poland": "pl", "Turkey": "tr",
    "Norway": "no", "Sweden": "se", "Scotland": "gb-sct", "Wales": "gb-wls", "Ireland": "ie", "Northern Ireland": "gb-nir",
    "Ukraine": "ua", "Greece": "gr", "Czechia": "cz", "Serbia": "rs", "Hungary": "hu", "Romania": "ro", "Slovakia": "sk",
    "Slovenia": "si", "Finland": "fi", "Iceland": "is", "Morocco": "ma", "Senegal": "sn", "Nigeria": "ng", "Egypt": "eg",
    "Ghana": "gh", "Brazil": "br", "Argentina": "ar", "Uruguay": "uy", "Colombia": "co", "Chile": "cl", "Ecuador": "ec",
    "Mexico": "mx", "United States": "us", "Canada": "ca", "Japan": "jp", "South Korea": "kr", "Australia": "au",
    "Saudi Arabia": "sa", "Iran": "ir", "Suriname": "sr", "Curaçao": "cw", "Indonesia": "id",
}


def flag_logo(name, logo=""):
    """National teams: a plain flag instead of ESPN's crosshair country badge. Anything else keeps its logo."""
    en = next((e for e, nl in COUNTRIES.items() if name in (e, nl)), "")
    iso = COUNTRY_ISO.get(en)
    if iso and (not logo or "/countries/" in logo):
        return f"https://flagcdn.com/w160/{iso}.png"
    return logo


COUNTRY_COLOURS = {
    "Netherlands": "F36C21", "Belgium": "D0202E", "Germany": "3A3A3A", "France": "1D3F9E", "England": "1B2A5C", "Spain": "C60B1E",
    "Italy": "1F5FBF", "Portugal": "9E1B32", "Croatia": "D1232A", "Denmark": "C8102E", "Switzerland": "D52B1E", "Austria": "ED2939",
    "Poland": "DC143C", "Turkey": "E30A17", "Norway": "BA0C2F", "Sweden": "006AA7", "Scotland": "1B3F8B", "Wales": "C8102E",
    "Ireland": "169B62", "Northern Ireland": "1B8A4A", "Ukraine": "0057B8", "Greece": "0D5EAF", "Czechia": "D7141A", "Serbia": "C6363C",
    "Hungary": "477050", "Romania": "E0B800", "Slovakia": "0B4EA2", "Slovenia": "005DA4", "Finland": "003580", "Iceland": "02529C",
    "Morocco": "C1272D", "Senegal": "00853F", "Nigeria": "008751", "Egypt": "CE1126", "Ghana": "006B3F", "Brazil": "F2C200",
    "Argentina": "6CACE4", "Uruguay": "5AA6DB", "Colombia": "E8B800", "Chile": "D52B1E", "Ecuador": "E0B000", "Mexico": "006847",
    "United States": "B22234", "Canada": "D52B1E", "Japan": "1F3E8E", "South Korea": "C60C30", "Australia": "F2B600",
    "Saudi Arabia": "006C35", "Iran": "239F40", "Suriname": "377E3F", "Curaçao": "002B7F", "Indonesia": "CE1126",
}
COUNTRY_NL = {en: (nl if NL else en) for en, nl in COUNTRIES.items()}
NATIONAL_LEAGUE = "fifa.friendly"


def country_colour(name):
    """Card colour (AARRGGBB) for a national team, '' for anything else. Accepts the English or the Dutch name."""
    for en, nl in COUNTRIES.items():
        if name in (en, nl):
            return "CC" + COUNTRY_COLOURS.get(en, "3A4A5C")
    return ""


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
            "nick": team.get("name") or "", "logo": flag_logo(full, team.get("logo") or (team.get("flag") or {}).get("href") or ""),
            "score": str(competitor.get("score", "") if not isinstance(competitor.get("score"), dict) else competitor["score"].get("displayValue", "")),
            "color": team.get("color") or "", "alt": team.get("alternateColor") or "",
            "rec": next((r.get("summary", "") for r in (competitor.get("records") or []) if r.get("summary")), "")}


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
                         "venue": "", "round": "", "circuit": str((ev.get("circuit") or {}).get("id") or ""),
                         "circname": (ev.get("circuit") or {}).get("fullName") or "",
                         "evid": str(ev.get("id") or ""), "comp": str(comp.get("id") or "")})
        return rows
    start = parse_iso(ev.get("date"))
    if start:
        end = parse_iso(ev.get("endDate"))
        state, label = status_of(ev)
        rows.append({"id": f"{league}:{ev.get('id')}", "league": league, "kind": "event", "start": start, "end": end, "state": state,
                     "status": label, "home": {}, "away": {}, "title": ev.get("name") or "", "sub": "", "venue": "", "round": ""})
    return rows


CIRCUIT_PATH = DATA + "sport_circuits.json"


def _is_transparent_png(raw):
    """True for a PNG that really has see-through parts (alpha channel or tRNS chunk)."""
    if raw[:8] != b"\x89PNG\r\n\x1a\n" or len(raw) < 33:
        return False
    return raw[25] in (4, 6) or b"tRNS" in raw[:2048]


def circuit_png(cid, diagrams):
    """Try to get the track drawing as a PNG with a see-through background; saved locally. Returns the file path or ''."""
    target = DATA + f"circuit_{cid}.png"
    try:
        if _is_transparent_png(open(target, "rb").read()):
            return target
    except OSError:
        pass
    candidates = []
    for d in diagrams:
        rel, href = d.get("rel") or [], (d.get("href") or "").replace("http://", "https://")
        if "circuit" in rel and not any("dark" in r or "info" in r for r in rel) and href:
            base = href.rsplit(".", 1)[0]
            path = base.split("espncdn.com", 1)[-1]
            candidates += [base + ".png", f"https://a.espncdn.com/combiner/i?img={path}.png&w=1000",
                           f"https://a.espncdn.com/combiner/i?img={path}.svg&w=1000&format=png"]
    for url in candidates:
        try:
            request = urllib.request.Request(url, headers=dict(BROWSER))
            with urllib.request.urlopen(request, timeout=20) as response:
                raw = response.read()
            if _is_transparent_png(raw):
                with open(target, "wb") as handle:
                    handle.write(raw)
                return target
        except Exception as error:  # noqa: BLE001 - try the next address
            log(f"circuit png {url}: {error}")
    return ""


RESULTS_PATH = DATA + "sport_results.json"
ATHLETES_PATH = DATA + "sport_athletes.json"


def session_results(league, evid, comp, final=True):
    """Top 10 of one race session: [{pos, name, team}]. Finished sessions are remembered for good."""
    if not (evid and comp):
        return []
    key = f"{league}:{evid}:{comp}"
    store = ac.read_json(RESULTS_PATH, {}) or {}
    if key in store:
        return store[key]
    path = LEAGUES.get(league, {}).get("path", "racing/f1")
    sport, slug = path.split("/", 1)
    data = espn_get(f"{CORE}{sport}/leagues/{slug}/events/{evid}/competitions/{comp}/competitors?limit=30")
    items = [i for i in (data.get("items") or []) if i.get("order")]
    items.sort(key=lambda i: i.get("order") or 99)
    items = items[:10]
    names = ac.read_json(ATHLETES_PATH, {}) or {}

    def one(item):
        m = re.search(r"/athletes/(\d+)", (item.get("athlete") or {}).get("$ref", ""))
        aid = m.group(1) if m else ""
        if not aid:
            return ""
        if aid in names:
            return names[aid]
        try:
            d = espn_get(f"{CORE}{sport}/leagues/{slug}/athletes/{aid}")
            return d.get("displayName") or d.get("fullName") or ""
        except Exception as error:  # noqa: BLE001
            log(f"athlete {aid}: {error}")
            return ""
    with ThreadPoolExecutor(max_workers=5) as pool:
        found = list(pool.map(one, items))
    rows, complete = [], True
    for item, name in zip(items, found):
        m = re.search(r"/athletes/(\d+)", (item.get("athlete") or {}).get("$ref", ""))
        if m and name:
            names[m.group(1)] = name
        complete = complete and bool(name)
        veh = item.get("vehicle") or {}
        rows.append({"pos": str(item.get("order")), "name": name or "?", "team": str(veh.get("manufacturer") or "")})
    if rows:
        try:
            ac.write_json(ATHLETES_PATH, names)
            if final and complete:
                store[key] = rows
                ac.write_json(RESULTS_PATH, store)
        except Exception as error:  # noqa: BLE001
            log(f"cannot save results: {error}")
    return rows


def circuit_of_event(ev):
    """Circuit id and name of a race weekend whose saved data has no circuit (older saved data): ask the scoreboard of that day."""
    try:
        path = LEAGUES.get(ev["league"], {}).get("path", "racing/f1")
        for shift in (0, 1, -1):
            day = (local_day(ev["start"]) + datetime.timedelta(days=shift)).strftime("%Y%m%d")
            data = espn_get(f"{ESPN}{path}/scoreboard?dates={day}&limit=50")
            for e in data.get("events") or []:
                c = e.get("circuit") or {}
                if c.get("id") and str(ev["id"]).split(":")[1:2] == [str(e.get("id"))]:
                    return str(c["id"]), c.get("fullName") or ""
            for e in data.get("events") or []:
                c = e.get("circuit") or {}
                if c.get("id") and (e.get("name") or "") == ev.get("title"):
                    return str(c["id"]), c.get("fullName") or ""
    except Exception as error:  # noqa: BLE001
        log(f"circuit of event: {error}")
    return "", ""


def circuit_info(cid, league="f1"):
    """Facts and drawing of a racing circuit from ESPN, remembered for good: {name, place, length, laps, turns, direction, record, image}."""
    if not cid:
        return {}
    known = ac.read_json(CIRCUIT_PATH, {}) or {}
    if (known.get(cid, {}).get("name") or known.get(cid, {}).get("image")) and "png" in known[cid]:
        return known[cid]
    path = LEAGUES.get(league, {}).get("path", "racing/f1")
    sport, slug = path.split("/", 1)
    data = espn_get(f"{CORE}{sport}/leagues/{slug}/circuits/{cid}")
    address = data.get("address") or {}
    place = ", ".join(x for x in ((address.get("city") if isinstance(address, dict) else str(address)), (address.get("country") if isinstance(address, dict) else "")) if x)
    image = ""
    for rel_wanted in (("circuit",), ("full",)):
        for d in data.get("diagrams") or []:
            rel, href = d.get("rel") or [], d.get("href") or ""
            if all(w in rel for w in rel_wanted) and not any("dark" in r or "info" in r for r in rel) and href.lower().endswith((".jpg", ".png")):
                image = href
                break
        if image:
            break
    png = circuit_png(cid, data.get("diagrams") or [])
    info_ = {"name": data.get("fullName") or "", "place": place, "png": png, "length": str(data.get("length") or ""), "laps": str(data.get("laps") or ""),
             "turns": str(data.get("turns") or ""), "direction": str(data.get("direction") or ""),
             "record": str(data.get("fastestLapTime") or ""), "recyear": str(data.get("fastestLapYear") or ""), "image": image}
    if not (info_["name"] or info_["image"]):
        return info_                      # ESPN gave nothing (busy?): do not remember the emptiness, try again next time
    known[cid] = info_
    try:
        ac.write_json(CIRCUIT_PATH, known)
    except Exception as error:  # noqa: BLE001
        log(f"cannot save circuits: {error}")
    return info_


LOGO_PATH = DATA + "sport_logos.json"
_LOGOS = {}


def logo_map():
    if not _LOGOS:
        _LOGOS.update(ac.read_json(LOGO_PATH, {}) or {})
    return _LOGOS


def league_logo(key):
    """Logo of a competition (from ESPN, remembered), '' while unknown."""
    value = logo_map().get(key, "")
    return "" if value == "-" else value


def remember_logo(key, logo):
    if logo and logo_map().get(key) != logo:
        _LOGOS[key] = logo
        try:
            ac.write_json(LOGO_PATH, _LOGOS)
        except Exception as error:  # noqa: BLE001
            log(f"cannot save logos: {error}")


def fetch_logos(keys, workers=3):
    """Ask ESPN for the logo of competitions we do not know yet (one small request each). True when something new came in."""
    todo = [k for k in keys if k in LEAGUES and k not in logo_map()]
    if not todo:
        return False

    def one(key):
        try:
            data = espn_get(f"{ESPN}{LEAGUES[key]['path']}/scoreboard?limit=1")
            logos = ((data or {}).get("leagues") or [{}])[0].get("logos") or [{}]
            return key, logos[0].get("href", "")
        except Exception as error:  # noqa: BLE001
            log(f"logo {key}: {error}")
            return key, None

    found = False
    with ThreadPoolExecutor(max_workers=workers) as pool:
        for key, logo in pool.map(one, todo):
            if logo is None:
                continue                      # ESPN busy: try again next time
            _LOGOS[key] = logo or "-"
            found = found or bool(logo)
    try:
        ac.write_json(LOGO_PATH, _LOGOS)
    except Exception as error:  # noqa: BLE001
        log(f"cannot save logos: {error}")
    return found


def parse_scoreboard(league, data):
    info_ = LEAGUES[league]
    out = []
    logos = ((data or {}).get("leagues") or [{}])[0].get("logos") or [{}]
    logo = logos[0].get("href", "")
    remember_logo(league, logo)
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
                           "logo": flag_logo(team.get("displayName") or team.get("name") or "", team.get("logo") or (logos[0].get("href") if logos else "")), "gp": gp, "gd": gd, "pts": pts,
                           "w": shown("wins"), "d": shown("ties") or shown("draws"), "l": shown("losses"),
                           "note": ((entry.get("note") or {}).get("color") or ""),
                           "notetext": ((entry.get("note") or {}).get("description") or "")})
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


def days_between(first, last):
    """'20261027', '20261029' -> ['20261027', '20261028', '20261029']"""
    a = datetime.datetime.strptime(first.replace("-", ""), "%Y%m%d").date()
    b = datetime.datetime.strptime(last.replace("-", ""), "%Y%m%d").date()
    return [(a + datetime.timedelta(days=n)).strftime("%Y%m%d") for n in range((b - a).days + 1)]


DAYFAIL = [0, 0, ""]   # days without an answer, days asked, last error (of the latest refresh)
PARTIAL = {}   # competition -> days ESPN did not answer the last time (the old games of those days are kept)


def fetch_range(key, first, last, workers=3):
    """ESPN no longer accepts 'from-to' for dates (HTTP 400), so ask day by day and join the answers.
    Days that fail (ESPN is busy) are asked again one by one; what still fails is remembered in PARTIAL."""
    path = LEAGUES[key]["path"]
    seen, out, got = set(), [], {}
    def one(day):
        try:
            return day, parse_scoreboard(key, espn_get(f"{ESPN}{path}/scoreboard?dates={day}&limit=400"))
        except Exception as error:  # noqa: BLE001
            return day, error

    days = days_between(first, last)
    with ThreadPoolExecutor(max_workers=workers) as pool:
        for day, res in pool.map(one, days):
            got[day] = res
    for _pass in range(1):
        for day in [d for d, r in got.items() if isinstance(r, Exception)]:
            time.sleep(1)
            got[day] = one(day)[1]
    failed = [d for d, r in got.items() if isinstance(r, Exception)]
    DAYFAIL[0] += len(failed)
    DAYFAIL[1] += len(days)
    if failed:
        DAYFAIL[2] = short_error(got[failed[0]])
    if len(failed) == len(days):
        raise got[failed[0]]
    PARTIAL[key] = failed
    for day in days:
        for ev in got[day] if not isinstance(got[day], Exception) else []:
            if ev["id"] not in seen:
                seen.add(ev["id"])
                out.append(ev)
    return out


def fetch_years(key, first_year, last_year):
    """One call per calendar year (a whole season in one answer); [] when ESPN does not answer."""
    path, out, seen = LEAGUES[key]["path"], [], set()
    for year in range(first_year, last_year + 1):
        try:
            events = parse_scoreboard(key, espn_get(f"{ESPN}{path}/scoreboard?dates={year}&limit=1000"))
        except Exception as error:  # noqa: BLE001
            log(f"year {key} {year}: {error}")
            continue
        for ev in events:
            if ev["id"] not in seen:
                seen.add(ev["id"])
                out.append(ev)
    return out


def _num(text):
    m = re.search(r"-?\d+(?:\.\d+)?", str(text or ""))
    return float(m.group()) if m else 0.0


def match_detail(ev):
    """Statistics, top performers and goals of one game from ESPN's summary; {} when ESPN has nothing (every part is optional)."""
    out = {}
    key = ev["league"]
    if key not in LEAGUES:
        return out
    eid = ev["id"].split(":", 1)[-1]
    data = espn_get(f"{ESPN}{LEAGUES[key]['path']}/summary?event={eid}")
    teams = (data.get("boxscore") or {}).get("teams") or []
    by_side = {}
    for tm in teams:
        who = tm.get("homeAway") or ""
        if not who:
            who = "home" if str((tm.get("team") or {}).get("id")) == ev["home"].get("id") else "away"
        by_side[who] = {s.get("name"): s.get("displayValue") for s in (tm.get("statistics") or [])}
    wanted = (("possessionPct", "g_possession"), ("totalShots", "g_shots"), ("shotsOnTarget", "g_ontarget"), ("wonCorners", "g_corners"))
    n = 0
    for name, label in wanted:
        hv, av = by_side.get("home", {}).get(name), by_side.get("away", {}).get(name)
        if hv in (None, "") and av in (None, ""):
            continue
        n += 1
        h, a = _num(hv), _num(av)
        if name == "possessionPct":
            hv, av = f"{round(h)}%", f"{round(a)}%"
        out[f"st{n}l"] = t(label)
        out[f"st{n}h"], out[f"st{n}a"] = str(hv if hv not in (None, "") else 0), str(av if av not in (None, "") else 0)
        out[f"st{n}k"] = str(int(round(10 * h / (h + a)))) if h + a else "5"
    k = 0
    for block in data.get("leaders") or []:
        abbr = (block.get("team") or {}).get("abbreviation", "")
        for cat in (block.get("leaders") or [])[:2]:
            lead = (cat.get("leaders") or [None])[0]
            if not lead:
                continue
            k += 1
            who = (lead.get("athlete") or {})
            out[f"tp{k}t"] = f"{abbr}  {cat.get('displayName') or cat.get('name') or ''}".strip()
            out[f"tp{k}n"] = who.get("shortName") or who.get("displayName") or ""
            out[f"tp{k}v"] = (lead.get("mainStat") or {}).get("value") or ""
            if k >= 4:
                break
        if k >= 4:
            break
    abbr_of = {ev["home"].get("id"): ev["home"].get("abbr") or ev["home"].get("name", ""), ev["away"].get("id"): ev["away"].get("abbr") or ev["away"].get("name", "")}
    plays = [p for p in (data.get("keyEvents") or []) if p.get("scoringPlay")]
    if not plays:
        comp = ((data.get("header") or {}).get("competitions") or [{}])[0]
        plays = [p for p in (comp.get("details") or []) if p.get("scoringPlay")]
    for i, p in enumerate(reversed(plays[-5:]), 1):
        tid = str((p.get("team") or {}).get("id", ""))
        out[f"sc{i}m"] = (p.get("clock") or {}).get("displayValue", "")
        out[f"sc{i}t"] = abbr_of.get(tid, "")
        who = ""
        parts = p.get("participants") or []
        if parts:
            who = (parts[0].get("athlete") or {}).get("displayName", "")
        out[f"sc{i}x"] = (p.get("shortText") or p.get("text") or who or "").split(".")[0][:60]
    return out


def fetch_league(key, first, last):
    return fetch_range(key, first, last)


UEFA_CLUBS = ["uefa.champions", "uefa.europa", "uefa.europa.conf"]
NATIONAL = ["fifa.friendly", "fifa.world", "fifa.worldq.uefa", "uefa.nations", "uefa.euro", "uefa.euroq", "fifa.worldq.concacaf",
            "fifa.worldq.conmebol", "fifa.worldq.afc", "fifa.worldq.caf", "conmebol.america", "concacaf.gold", "afc.asian.cup",
            "caf.nations", "global.finalissima"]


def wider_leagues(league):
    """Where a followed team plays besides its league: the same country's cups, the UEFA club cups; national teams: all their tournaments."""
    if league not in LEAGUES:
        return [league]
    if league in NATIONAL:
        return [k for k in NATIONAL if k in LEAGUES]
    if LEAGUES[league]["sport"] != "soccer":
        return [league]
    country = league.split(".")[0]
    near = [k for k, v in LEAGUES.items() if v["sport"] == "soccer" and k.split(".")[0] == country and ".w." not in k]
    return near + [k for k in UEFA_CLUBS if k in LEAGUES]


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
        for k in wider_leagues(league):
            if k not in keys:
                keys.append(k)
    return keys


BROWSER = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15",
           "Accept": "application/json"}


def espn_get(url):
    """ESPN answers a normal browser; one retry when it is busy (429 / 5xx)."""
    try:
        return info.http(url, headers=dict(BROWSER))
    except Exception as error:  # noqa: BLE001
        code = getattr(error, "code", 0)
        if code == 429 or code >= 500:
            time.sleep(2)
            return info.http(url, headers=dict(BROWSER))
        raise


def short_error(error):
    code = getattr(error, "code", 0)
    return f"HTTP {code}" if code else (str(getattr(error, "reason", "") or error)[:30] or "?")


LAST_FAIL = [0, 0, ""]        # failed, asked, last error text of the latest refresh


NATIONAL_TTL = 12 * 3600
CORE = "https://sports.core.api.espn.com/v2/sports/"


def followed_countries():
    """[(espn id, English name)] of the national teams you follow."""
    english = set(COUNTRIES)
    dutch = {nl: en for en, nl in COUNTRIES.items()}
    out = []
    for team in load_follow()["teams"]:
        name = team.get("name") or ""
        en = name if name in english else dutch.get(name)
        if en and team.get("id"):
            out.append((str(team["id"]), en))
    return out


def refresh_national(force=False):
    """The games of a followed country are often further away than the 13 days we load (a Nations League game in
    three weeks). Ask ESPN for the dates of its games and fetch exactly those days. Once per 12 hours."""
    teams = followed_countries()
    cache = load_cache()
    extra = cache.get("extra") or {}
    ids = sorted(t[0] for t in teams)
    if not teams:
        if extra:
            cache.pop("extra", None)
            save_cache(cache)
        return False
    if not force and extra.get("teams") == ids and time.time() - extra.get("fetched", 0) < NATIONAL_TTL:
        return False
    today = ac.today()
    year = today.year
    jobs = [(tid, key, season) for tid, _name in teams for key in NATIONAL if key in LEAGUES for season in (year, year + 1)]

    def dates_of(job):
        tid, key, season = job
        sport, slug = LEAGUES[key]["path"].split("/", 1)
        try:
            data = espn_get(f"{CORE}{sport}/leagues/{slug}/seasons/{season}/teams/{tid}/events?limit=50")
        except Exception:  # noqa: BLE001 - most competitions have nothing for this team: normal
            return []
        days = []
        for item in (data or {}).get("items") or []:
            ref = (item.get("$ref") or "").replace("http://", "https://")
            try:
                when = (espn_get(ref).get("date") or "")[:16]
                stamp = datetime.datetime.strptime(when, "%Y-%m-%dT%H:%M").replace(tzinfo=datetime.timezone.utc).timestamp()
            except Exception:  # noqa: BLE001
                continue
            day = local_day(stamp)
            if today <= day <= today + datetime.timedelta(days=400):
                days.append((key, espn_day(day)))
        return days

    wanted = set()
    with ThreadPoolExecutor(max_workers=4) as pool:
        for days in pool.map(dates_of, jobs):
            wanted.update(days)
    names = {norm(en) for _tid, en in teams} | {norm(COUNTRIES[en]) for _tid, en in teams}

    def day_events(item):
        key, day = item
        try:
            return parse_scoreboard(key, espn_get(f"{ESPN}{LEAGUES[key]['path']}/scoreboard?dates={day}&limit=400"))
        except Exception as error:  # noqa: BLE001
            log(f"national {key} {day}: {error}")
            return None

    events, failed = [], False
    with ThreadPoolExecutor(max_workers=3) as pool:
        for rows in pool.map(day_events, sorted(wanted)):
            if rows is None:
                failed = True
                continue
            for e in rows:
                if e.get("kind") == "teams" and (norm(e["home"].get("name")) in names or norm(e["away"].get("name")) in names
                                                 or {e["home"].get("id"), e["away"].get("id")} & {t[0] for t in teams}):
                    events.append(e)
    old = extra.get("events", []) if failed else []
    have = {e["id"] for e in events}
    events += [e for e in old if e["id"] not in have]
    cache["extra"] = {"fetched": int(time.time()) - (NATIONAL_TTL - 120 if failed else 0), "teams": ids, "events": events}
    save_cache(cache)
    return True


def refresh(force=False, keys=None, progress=None):
    """Fetch the competitions that are out of date. Returns True when something changed."""
    main = _refresh(force, keys, progress)
    if keys is not None:
        return main
    try:                                   # after the normal games, so they are never held up
        return refresh_national(force) or main
    except Exception as error:  # noqa: BLE001 - the extra games must never stop the normal refresh
        log(f"national: {error}")
        return main


def _refresh(force=False, keys=None, progress=None):
    now = int(time.time())
    first_d, last_d = window()
    first, last = first_d.isoformat().replace("-", ""), last_d.isoformat().replace("-", "")
    cache = load_cache()
    todo = [k for k in (keys or league_keys()) if force or is_stale(cache["leagues"].get(k), now, first, last)]
    if not todo:
        return False
    done = [0]
    LAST_FAIL[:] = [0, len(todo), ""]
    DAYFAIL[:] = [0, 0, ""]

    def work(key):
        try:
            events = fetch_league(key, first, last)
            return key, events
        except Exception as error:  # noqa: BLE001 - one competition failing must not stop the others
            log(f"{key}: {error}")
            LAST_FAIL[0] += 1
            LAST_FAIL[2] = short_error(error)
            return key, None

    changed = False
    with ThreadPoolExecutor(max_workers=4) as pool:
        for key, events in pool.map(work, todo):
            done[0] += 1
            if progress:
                progress(done[0], len(todo))
            if events is None:
                if key in cache["leagues"]:
                    cache["leagues"][key]["fetched"] = now - TTL + 60      # try again in a minute
                continue
            fetched = now
            failed = PARTIAL.pop(key, [])
            if failed:      # keep the games we already had for the days ESPN did not answer, and ask again in a minute
                old = [e for e in (cache["leagues"].get(key) or {}).get("events", []) if espn_day(local_day(e["start"])) in failed]
                have = {e["id"] for e in events}
                events = events + [e for e in old if e["id"] not in have]
                fetched = now - TTL + 60
            cache["leagues"][key] = {"fetched": fetched, "from": first, "to": last, "events": events}
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
        rows = parse_standings(espn_get(f"{ESPN_V2}{LEAGUES[key]['path']}/standings"))
    except Exception as error:  # noqa: BLE001
        log(f"standings {key}: {error}")
        return entry["rows"] if entry else []
    if entry:
        track_places(entry["rows"], rows)
    cache["standings"][key] = {"fetched": time.time(), "rows": rows}
    save_cache(cache)
    return rows


def track_places(old_rows, new_rows):
    """Place changes since the last round: a team's 'prev' rank is the one it had before its games-played changed."""
    old = {r["id"]: r for r in old_rows if r.get("id")}
    for row in new_rows:
        before = old.get(row.get("id"))
        if not before:
            continue
        if before.get("gp") != row.get("gp"):
            row["prev"] = before["rank"]
        elif before.get("prev"):
            row["prev"] = before["prev"]


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
    have = {e["id"] for e in out}
    now = time.time()
    out.extend(e for e in (cache.get("extra") or {}).get("events", []) if e["id"] not in have and e["start"] > now)   # later games of followed countries
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


# ----------------------------------------------------------------------------- results, form, team cards
RESULTS_DAYS = 70
RESULTS_TTL = 60 * 60
FORM_COLOURS = {"W": "FF3FB950", "D": "FF8B949E", "L": "FFE5534B"}
GOLD = "FFD4A83A"


def results(key, force=False):
    """Finished games of a competition of the last ten weeks (one call), newest first. Cached for an hour."""
    cache = load_cache()
    entry = cache.setdefault("results", {}).get(key)
    if entry and not force and time.time() - entry.get("fetched", 0) < RESULTS_TTL:
        return entry["events"]
    today = ac.today()
    first = (today - datetime.timedelta(days=RESULTS_DAYS)).strftime("%Y%m%d")
    events = fetch_years(key, int(first[:4]), today.year)
    if not events:                              # a year answer failed: ask day by day instead
        try:
            events = fetch_range(key, first, espn_day(today), workers=4)
        except Exception as error:  # noqa: BLE001
            log(f"results {key}: {error}")
            return entry["events"] if entry else []
    cut = time.time() - RESULTS_DAYS * 86400
    done = sorted((e for e in events if e["state"] == "post" and e["kind"] == "teams" and e["start"] >= cut), key=lambda e: -e["start"])
    cache["results"][key] = {"fetched": time.time(), "events": done}
    save_cache(cache)
    return done


def result_for(ev, team_id, team_name=""):
    """('W'|'D'|'L', 'own-opp', opponent name, is_home) from a finished game, or None."""
    n = norm(team_name)
    for mine, other, home in ((ev["home"], ev["away"], True), (ev["away"], ev["home"], False)):
        if (team_id and mine.get("id") == team_id) or (n and norm(mine.get("name")) == n):
            try:
                a, b = int(float(mine.get("score"))), int(float(other.get("score")))
            except (TypeError, ValueError):
                return None
            return ("W" if a > b else "L" if a < b else "D", f"{a}–{b}", other.get("name", ""), home)
    return None


def team_results(key, team_id, team_name="", limit=5):
    out = []
    for ev in results(key):
        res = result_for(ev, team_id, team_name)
        if res:
            out.append((ev, res))
            if len(out) >= limit:
                break
    return out


def colour_map():
    """team id -> 'AARRGGBB' from the colours ESPN sends with the games."""
    out = {}
    for ev in all_cached():
        for s in (ev.get("home"), ev.get("away")):
            if s and s.get("id") and s.get("color") and s["id"] not in out:
                out[s["id"]] = "FF" + s["color"].strip("#").upper()
    return out


def table_rows(key, marks=()):
    """The table with everything the screen shows: form, place change, edge colour, team colour, and which rows are yours."""
    rows = [dict(r) for r in standings(key)]
    follow = load_follow()
    colours = colour_map()
    played = results(key)
    if not played:                              # no season answer: use the finished games we already hold
        played = sorted((e for e in all_cached() if e["league"] == key and e["state"] == "post" and e["kind"] == "teams"),
                        key=lambda e: -e["start"])
    for row in rows:
        if "header" in row or not row.get("id"):
            continue
        form = []
        for ev in played:
            res = result_for(ev, row["id"], row["team"])
            if res:
                form.append(res[0])
                if len(form) == 5:
                    break
        row["form"] = form
        row["teamcol"] = colours.get(row["id"], "")
        prev = row.get("prev")
        row["chg"] = (prev - row["rank"]) if prev and isinstance(row.get("rank"), int) else 0
        edge = (row.get("note") or "").strip("#")
        row["edge"] = ("FF" + edge.upper()) if len(edge) == 6 else ""
        row["mine"] = bool(is_following_team(follow, {"id": row["id"], "name": row.get("team", "")})) or row["id"] in marks
    return rows


def legend(rows):
    """[(colour, text)] of the coloured edges (Champions League, relegation, ...)."""
    seen, out = set(), []
    for row in rows:
        if row.get("edge") and row.get("notetext") and row["edge"] not in seen:
            seen.add(row["edge"])
            out.append((row["edge"], row["notetext"]))
    return out[:4]


def team_card(key, team_id, name):
    """Everything on the team card."""
    row = next((r for r in standings(key) if r.get("id") == team_id), {})
    recent = team_results(key, team_id, name, limit=5)
    home = [r for _e, r in team_results(key, team_id, name, limit=30) if r[3]][:5]
    away = [r for _e, r in team_results(key, team_id, name, limit=30) if not r[3]][:5]

    def tally(rs):
        return f"{sum(1 for r in rs if r[0] == 'W')}-{sum(1 for r in rs if r[0] == 'D')}-{sum(1 for r in rs if r[0] == 'L')}"

    upcoming = sorted((e for e in all_cached() if e["state"] in ("pre", "in") and e["kind"] == "teams"
                       and ((team_id and team_id in (e["home"].get("id"), e["away"].get("id")))
                            or norm(name) in (norm(e["home"].get("name")), norm(e["away"].get("name"))))),
                      key=lambda e: e["start"])
    return {"row": row, "recent": recent, "home": tally(home), "away": tally(away),
            "last3": recent[:3], "next": upcoming[0] if upcoming else None, "games": upcoming}
