# -*- coding: utf-8 -*-
"""Lucent: Sport - the list of competitions ESPN has (slugs checked against ESPN's own league lists).

Each block: sport, kind (teams = two sides, event = race / tournament / fight card), then rows
  key | Dutch name | English name | shown in "All games" without following (1/0) | extra words a TV guide may use (; separated)
The key is the ESPN slug (the part after the sport in .../sports/<sport>/<slug>/scoreboard).
"""

_SOCCER = """
ned.1|Eredivisie|Eredivisie|1|eredivisie
ned.2|Keuken Kampioen Divisie|Dutch Eerste Divisie|1|keuken kampioen;eerste divisie
ned.cup|KNVB Beker|KNVB Cup|1|knvb beker;knvb cup
ned.supercup|Johan Cruijff Schaal|Johan Cruyff Shield|0|johan cruijff schaal;johan cruyff
ned.w.1|Eredivisie Vrouwen|Dutch Eredivisie Women|0|eredivisie vrouwen
ned.w.knvb_cup|KNVB Beker Vrouwen|KNVB Cup Women|0|knvb beker vrouwen
bel.1|Jupiler Pro League|Belgian Pro League|1|jupiler;pro league
eng.1|Premier League|Premier League|1|premier league
eng.2|Championship|EFL Championship|0|championship
eng.3|League One|EFL League One|0|league one
eng.4|League Two|EFL League Two|0|league two
eng.5|National League|National League|0|national league
eng.fa|FA Cup|FA Cup|1|fa cup
eng.league_cup|League Cup|League Cup|0|league cup;carabao
eng.trophy|EFL Trophy|EFL Trophy|0|efl trophy
eng.charity|Community Shield|Community Shield|0|community shield
eng.w.1|WSL|Women's Super League|0|wsl;women's super league
eng.w.fa|FA Cup Vrouwen|Women's FA Cup|0|women's fa cup
eng.w.league_cup|WSL Cup|Women's League Cup|0|wsl cup
sco.1|Scottish Premiership|Scottish Premiership|0|scottish premiership
sco.2|Scottish Championship|Scottish Championship|0|scottish championship
sco.tennents|Scottish Cup|Scottish Cup|0|scottish cup
sco.cis|Scottish League Cup|Scottish League Cup|0|scottish league cup;viaplay cup
sco.challenge|Scottish Challenge Cup|Scottish Challenge Cup|0|challenge cup
esp.1|La Liga|La Liga|1|la liga;laliga
esp.2|Segunda División|Segunda División|0|segunda division
esp.copa_del_rey|Copa del Rey|Copa del Rey|0|copa del rey
esp.super_cup|Supercopa de España|Spanish Super Cup|0|supercopa
esp.joan_gamper|Trofeu Joan Gamper|Joan Gamper Trophy|0|joan gamper
esp.w.1|Liga F|Liga F|0|liga f
esp.copa_de_la_reina|Copa de la Reina|Copa de la Reina|0|copa de la reina
ger.1|Bundesliga|Bundesliga|1|bundesliga
ger.2|2. Bundesliga|2. Bundesliga|0|2 bundesliga
ger.dfb_pokal|DFB-Pokal|DFB-Pokal|0|dfb pokal;dfb-pokal
ger.super_cup|Duitse Supercup|German Super Cup|0|supercup
ita.1|Serie A|Serie A|1|serie a
ita.2|Serie B|Serie B|0|serie b
ita.coppa_italia|Coppa Italia|Coppa Italia|0|coppa italia
ita.super_cup|Supercoppa Italiana|Italian Super Cup|0|supercoppa
fra.1|Ligue 1|Ligue 1|1|ligue 1
fra.2|Ligue 2|Ligue 2|0|ligue 2
fra.coupe_de_france|Coupe de France|Coupe de France|0|coupe de france
fra.super_cup|Trophée des Champions|Trophée des Champions|0|trophee des champions
fra.w.1|Première Ligue|Première Ligue (women)|0|premiere ligue
por.1|Liga Portugal|Portuguese Liga|1|liga portugal;primeira liga
por.taca.portugal|Taça de Portugal|Taça de Portugal|0|taca de portugal
aut.1|Oostenrijkse Bundesliga|Austrian Bundesliga|0|oostenrijkse bundesliga;austrian bundesliga
gre.1|Griekse Super League|Greek Super League|0|super league
tur.1|Süper Lig|Turkish Super Lig|0|super lig;süper lig
rus.1|Russische Premier League|Russian Premier League|0|russian premier league
swe.1|Allsvenskan|Allsvenskan|0|allsvenskan
den.1|Deense Superliga|Danish Superliga|0|superliga
nor.1|Eliteserien|Eliteserien|0|eliteserien
usa.1|MLS|MLS|0|mls;major league soccer
usa.nwsl|NWSL|NWSL|0|nwsl
usa.nwsl.cup|NWSL Challenge Cup|NWSL Challenge Cup|0|nwsl challenge cup
usa.open|US Open Cup|US Open Cup|0|us open cup
usa.usl.1|USL Championship|USL Championship|0|usl
mex.1|Liga MX|Liga MX|0|liga mx
mex.2|Liga de Expansión MX|Liga de Expansión MX|0|liga de expansion
can.w.nsl|Northern Super League|Northern Super League|0|northern super league
concacaf.leagues.cup|Leagues Cup|Leagues Cup|0|leagues cup
concacaf.champions|Concacaf Champions Cup|Concacaf Champions Cup|0|concacaf champions
arg.1|Argentijnse Liga Profesional|Argentine Liga Profesional|0|liga profesional
arg.copa|Copa Argentina|Copa Argentina|0|copa argentina
arg.2|Primera Nacional|Primera Nacional|0|primera nacional
bra.1|Braziliaanse Série A|Brazilian Série A|0|brasileirao;serie a brazilie
bra.2|Braziliaanse Série B|Brazilian Série B|0|serie b brazilie
bra.copa_do_brazil|Copa do Brasil|Copa do Brasil|0|copa do brasil
chi.1|Chileense Primera División|Chilean Primera División|0|primera division chili
uru.1|Uruguayaanse Primera División|Uruguayan Primera División|0|primera division uruguay
col.1|Colombiaanse Liga|Colombian Liga|0|liga colombia
per.1|Peruaanse Liga 1|Peruvian Liga 1|0|liga 1 peru
par.1|Paraguayaanse Primera División|Paraguayan Primera División|0|primera division paraguay
ecu.1|Ecuadoriaanse LigaPro|Ecuadorian LigaPro|0|ligapro
ven.1|Venezolaanse Primera División|Venezuelan Primera División|0|primera division venezuela
bol.1|Boliviaanse Liga|Bolivian Liga|0|liga boliviana
conmebol.libertadores|Copa Libertadores|Copa Libertadores|0|libertadores
conmebol.sudamericana|Copa Sudamericana|Copa Sudamericana|0|sudamericana
conmebol.recopa|Recopa Sudamericana|Recopa Sudamericana|0|recopa
campeones.cup|Campeones Cup|Campeones Cup|0|campeones cup
ksa.1|Saudi Pro League|Saudi Pro League|0|saudi pro league
ksa.kings.cup|King's Cup (Saoedi-Arabië)|Saudi King's Cup|0|king's cup
jpn.1|J1 League|J1 League|0|j1 league
chn.1|Chinese Super League|Chinese Super League|0|chinese super league
aus.1|A-League Men|A-League Men|0|a-league
aus.w.1|A-League Women|A-League Women|0|a-league women
ind.1|Indian Super League|Indian Super League|0|indian super league
rsa.1|Zuid-Afrikaanse Premiership|South African Premiership|0|premiership zuid afrika
caf.champions|CAF Champions League|CAF Champions League|0|caf champions league
caf.confed|CAF Confederation Cup|CAF Confederation Cup|0|caf confederation cup
afc.champions|AFC Champions League|AFC Champions League|0|afc champions league
afc.cup|AFC Cup|AFC Cup|0|afc cup
uefa.champions|Champions League|Champions League|1|champions league
uefa.champions_qual|Champions League kwalificatie|Champions League qualifying|0|champions league kwalificatie;champions league qualifying
uefa.europa|Europa League|Europa League|1|europa league
uefa.europa_qual|Europa League kwalificatie|Europa League qualifying|0|europa league kwalificatie
uefa.europa.conf|Conference League|Conference League|1|conference league
uefa.europa.conf_qual|Conference League kwalificatie|Conference League qualifying|0|conference league kwalificatie
uefa.super_cup|UEFA Super Cup|UEFA Super Cup|0|super cup;uefa supercup
uefa.wchampions|Champions League Vrouwen|Women's Champions League|0|champions league vrouwen;women's champions league
uefa.nations|Nations League|Nations League|1|nations league
uefa.w.nations|Nations League Vrouwen|Women's Nations League|0|nations league vrouwen
uefa.euro|EK voetbal|European Championship|1|ek voetbal;european championship;euro 20
uefa.euroq|EK-kwalificatie|European Championship qualifying|0|ek kwalificatie;ek-kwalificatie;euro qualifying
uefa.weuro|EK voetbal vrouwen|Women's European Championship|0|ek vrouwen;women's euro
uefa.euro_u21|EK onder 21|European U21 Championship|0|ek onder 21;ek -21
uefa.euro_u21_qual|EK onder 21 kwalificatie|European U21 qualifying|0|ek onder 21 kwalificatie
uefa.euro.u19|EK onder 19|European U19 Championship|0|ek onder 19
fifa.world|WK voetbal|World Cup|1|wk voetbal;world cup;wereldkampioenschap
fifa.wwc|WK voetbal vrouwen|Women's World Cup|0|wk vrouwen;women's world cup
fifa.worldq.uefa|WK-kwalificatie Europa|World Cup qualifying (Europe)|1|wk kwalificatie;wk-kwalificatie;world cup qualifying;wk kwal
fifa.worldq.concacaf|WK-kwalificatie Noord-Amerika|World Cup qualifying (CONCACAF)|0|wk kwalificatie
fifa.worldq.conmebol|WK-kwalificatie Zuid-Amerika|World Cup qualifying (South America)|0|wk kwalificatie
fifa.worldq.afc|WK-kwalificatie Azië|World Cup qualifying (Asia)|0|wk kwalificatie
fifa.worldq.caf|WK-kwalificatie Afrika|World Cup qualifying (Africa)|0|wk kwalificatie
fifa.worldq.ofc|WK-kwalificatie Oceanië|World Cup qualifying (Oceania)|0|wk kwalificatie
fifa.wcq.ply|WK-play-offs (intercontinentaal)|World Cup play-offs (intercontinental)|0|wk play-offs
fifa.wworldq.uefa|WK-kwalificatie vrouwen Europa|Women's World Cup qualifying (Europe)|0|wk kwalificatie vrouwen
fifa.friendly|Oefeninterlands|International friendlies|0|oefeninterland;vriendschappelijk;friendly
fifa.friendly.w|Oefeninterlands vrouwen|Women's friendlies|0|oefeninterland vrouwen
club.friendly|Oefenwedstrijden clubs|Club friendlies|0|oefenwedstrijd;club friendly
fifa.cwc|WK voor clubs|Club World Cup|0|wk voor clubs;club world cup
fifa.intercontinental_cup|Intercontinental Cup|Intercontinental Cup|0|intercontinental cup
fifa.world.u20|WK onder 20|U20 World Cup|0|wk onder 20
fifa.world.u17|WK onder 17|U17 World Cup|0|wk onder 17
fifa.olympics|Olympisch voetbal (mannen)|Olympic football (men)|0|olympisch voetbal
fifa.w.olympics|Olympisch voetbal (vrouwen)|Olympic football (women)|0|olympisch voetbal vrouwen
fifa.shebelieves|SheBelieves Cup|SheBelieves Cup|0|shebelieves
global.finalissima|Finalissima|Finalissima|0|finalissima
conmebol.america|Copa América|Copa América|0|copa america
concacaf.gold|Gold Cup|Gold Cup|0|gold cup
concacaf.nations.league|Concacaf Nations League|Concacaf Nations League|0|concacaf nations league
afc.asian.cup|Asian Cup|Asian Cup|0|asian cup
caf.nations|Afrika Cup|Africa Cup of Nations|0|afrika cup;africa cup of nations;afcon
"""

_BASKETBALL = """
nba|NBA|NBA|1|nba
wnba|WNBA|WNBA|0|wnba
nba-development|NBA G League|NBA G League|0|g league
nba-summer-las-vegas|NBA Summer League|NBA Summer League|0|summer league
mens-college-basketball|Collegebasketbal (mannen)|Men's college basketball|0|college basketball;ncaa basketball
womens-college-basketball|Collegebasketbal (vrouwen)|Women's college basketball|0|college basketball vrouwen
fiba|FIBA|FIBA|0|fiba
nbl|NBL (Australië)|Australian NBL|0|nbl
mens-olympics-basketball|Olympisch basketbal (mannen)|Olympic basketball (men)|0|olympisch basketbal
womens-olympics-basketball|Olympisch basketbal (vrouwen)|Olympic basketball (women)|0|olympisch basketbal vrouwen
"""
_FOOTBALL = """
nfl|NFL|NFL|1|nfl
college-football|College football|College football|0|college football;ncaa football
cfl|CFL|CFL|0|cfl
ufl|UFL|UFL|0|ufl
"""
_HOCKEY = """
nhl|NHL|NHL|0|nhl
mens-college-hockey|College hockey (mannen)|Men's college hockey|0|college hockey
womens-college-hockey|College hockey (vrouwen)|Women's college hockey|0|college hockey vrouwen
olympics-mens-ice-hockey|Olympisch ijshockey (mannen)|Olympic ice hockey (men)|0|olympisch ijshockey
olympics-womens-ice-hockey|Olympisch ijshockey (vrouwen)|Olympic ice hockey (women)|0|olympisch ijshockey vrouwen
hockey-world-cup|World Cup of Hockey|World Cup of Hockey|0|world cup of hockey
"""
_BASEBALL = """
mlb|MLB|MLB|0|mlb
college-baseball|College baseball|College baseball|0|college baseball
college-softball|College softball|College softball|0|college softball
world-baseball-classic|World Baseball Classic|World Baseball Classic|0|world baseball classic
olympics-baseball|Olympisch honkbal|Olympic baseball|0|olympisch honkbal
caribbean-series|Caribbean Series|Caribbean Series|0|caribbean series
"""
_AUSSIE = """
afl|AFL|AFL|0|afl;australian football
"""
_RACING = """
f1|Formule 1|Formula 1|1|formule 1;formula 1;f1
irl|IndyCar|IndyCar|0|indycar
nascar-premier|NASCAR Cup Series|NASCAR Cup Series|0|nascar
nascar-secondary|NASCAR Xfinity Series|NASCAR Xfinity Series|0|nascar xfinity
nascar-truck|NASCAR Truck Series|NASCAR Truck Series|0|nascar truck
"""
_GOLF = """
pga|PGA Tour|PGA Tour|0|pga
lpga|LPGA Tour|LPGA Tour|0|lpga
eur|DP World Tour|DP World Tour|0|dp world tour;european tour
liv|LIV Golf|LIV Golf|0|liv golf
champions-tour|PGA Tour Champions|PGA Tour Champions|0|champions tour
tgl|TGL|TGL|0|tgl
mens-olympics-golf|Olympisch golf (mannen)|Olympic golf (men)|0|olympisch golf
womens-olympics-golf|Olympisch golf (vrouwen)|Olympic golf (women)|0|olympisch golf vrouwen
"""
_TENNIS = """
atp|ATP-tennis|ATP tennis|0|atp
wta|WTA-tennis|WTA tennis|0|wta
"""
_MMA = """
ufc|UFC|UFC|1|ufc
pfl|PFL|PFL|0|pfl
bellator|Bellator|Bellator|0|bellator
rizin|Rizin|Rizin|0|rizin
ksw|KSW|KSW|0|ksw
cage-warriors|Cage Warriors|Cage Warriors|0|cage warriors
"""

# rugby: ESPN uses numeric league ids (filled in from ESPN's league list)
_RUGBY = """
180659|Six Nations|Six Nations|0|six nations
164205|WK rugby|Rugby World Cup|0|wk rugby;rugby world cup
244293|Rugby Championship|Rugby Championship|0|rugby championship
267979|Premiership Rugby|Premiership Rugby|0|premiership rugby;gallagher premiership
270557|United Rugby Championship|United Rugby Championship|0|united rugby championship;urc
270559|Top 14|Top 14|0|top 14
271937|Champions Cup (rugby)|Rugby Champions Cup|0|champions cup
242041|Super Rugby Pacific|Super Rugby Pacific|0|super rugby
272073|Challenge Cup (rugby)|European Rugby Challenge Cup|0|challenge cup
270555|Currie Cup|Currie Cup|0|currie cup
17567|Nations Championship|Nations Championship|0|nations championship
289237|WK rugby vrouwen|Women's Rugby World Cup|0|wk rugby vrouwen
289262|Major League Rugby|Major League Rugby|0|major league rugby
289234|Rugby-interlands|International Test Matches|0|rugby interland;test match
268565|British & Irish Lions|British and Irish Lions Tour|0|lions tour;british irish lions
236461|Anglo-Welsh Cup|Anglo-Welsh Cup|0|anglo-welsh cup
"""

BLOCKS = (("soccer", "teams", _SOCCER), ("basketball", "teams", _BASKETBALL), ("football", "teams", _FOOTBALL),
          ("hockey", "teams", _HOCKEY), ("baseball", "teams", _BASEBALL), ("australian-football", "teams", _AUSSIE),
          ("rugby", "teams", _RUGBY), ("racing", "event", _RACING), ("golf", "event", _GOLF),
          ("tennis", "event", _TENNIS), ("mma", "event", _MMA))
SPORT_OF_PATH = {"australian-football": "aussie"}


def build():
    """[(key, path, nameNL, nameEN, sport, kind, default, [words])] for sport_core."""
    out = []
    for sport, kind, block in BLOCKS:
        for line in block.strip().splitlines():
            key, nl, en, default, words = line.split("|")
            short = sport if sport != "australian-football" else "aussie"
            out.append((key, f"{sport}/{key}", nl, en, short, kind, default == "1", [w for w in words.split(";") if w]))
    return out
