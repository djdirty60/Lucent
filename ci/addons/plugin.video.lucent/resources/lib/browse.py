# -*- coding: utf-8 -*-
"""Browsing by studio, TV network, decade and award.

Studios and networks are TMDB companies and networks; their names and logos come from TMDB itself. The award lists
are fixed lists of winners (up to 2025), looked up on TMDB by title and year."""
import datetime

import tmdb
import util

T = util.T

STUDIOS = [420, 3, 2, 174, 33, 4, 5, 25, 1632, 41077, 3172, 521, 923, 10342, 1, 12, 7505, 2251]
NETWORKS = [213, 49, 1024, 2739, 2552, 3186, 453, 4330, 3353, 67, 318, 88, 174, 4, 1063, 6, 16, 2, 19, 71]
DECADES = [2020, 2010, 2000, 1990, 1980, 1970, 1960, 1950]

AWARDS = {
    "oscar_picture": (T("Oscar: beste film", "Oscar: Best Picture"), "movie", [
        ("Anora", 2024), ("Oppenheimer", 2023), ("Everything Everywhere All at Once", 2022), ("CODA", 2021), ("Nomadland", 2020),
        ("Parasite", 2019), ("Green Book", 2018), ("The Shape of Water", 2017), ("Moonlight", 2016), ("Spotlight", 2015),
        ("Birdman", 2014), ("12 Years a Slave", 2013), ("Argo", 2012), ("The Artist", 2011), ("The King's Speech", 2010),
        ("The Hurt Locker", 2009), ("Slumdog Millionaire", 2008), ("No Country for Old Men", 2007), ("The Departed", 2006),
        ("Crash", 2005), ("Million Dollar Baby", 2004), ("The Lord of the Rings: The Return of the King", 2003), ("Chicago", 2002),
        ("A Beautiful Mind", 2001), ("Gladiator", 2000), ("American Beauty", 1999), ("Shakespeare in Love", 1998), ("Titanic", 1997),
        ("The English Patient", 1996), ("Braveheart", 1995), ("Forrest Gump", 1994), ("Schindler's List", 1993), ("Unforgiven", 1992),
        ("The Silence of the Lambs", 1991), ("Dances with Wolves", 1990), ("Driving Miss Daisy", 1989), ("Rain Man", 1988),
        ("The Last Emperor", 1987), ("Platoon", 1986), ("Out of Africa", 1985), ("Amadeus", 1984), ("Terms of Endearment", 1983),
        ("Gandhi", 1982), ("Chariots of Fire", 1981), ("Ordinary People", 1980), ("Kramer vs. Kramer", 1979), ("The Deer Hunter", 1978),
        ("Annie Hall", 1977), ("Rocky", 1976), ("One Flew Over the Cuckoo's Nest", 1975), ("The Godfather Part II", 1974),
        ("The Sting", 1973), ("The Godfather", 1972), ("The French Connection", 1971)]),
    "oscar_animated": (T("Oscar: beste animatiefilm", "Oscar: Best Animated Feature"), "movie", [
        ("Flow", 2024), ("The Boy and the Heron", 2023), ("Guillermo del Toro's Pinocchio", 2022), ("Encanto", 2021), ("Soul", 2020),
        ("Toy Story 4", 2019), ("Spider-Man: Into the Spider-Verse", 2018), ("Coco", 2017), ("Zootopia", 2016), ("Inside Out", 2015),
        ("Big Hero 6", 2014), ("Frozen", 2013), ("Brave", 2012), ("Rango", 2011), ("Toy Story 3", 2010), ("Up", 2009), ("WALL·E", 2008),
        ("Ratatouille", 2007), ("Happy Feet", 2006), ("Wallace & Gromit: The Curse of the Were-Rabbit", 2005), ("The Incredibles", 2004),
        ("Finding Nemo", 2003), ("Spirited Away", 2001), ("Shrek", 2001)]),
    "palme": (T("Gouden Palm (Cannes)", "Palme d'Or (Cannes)"), "movie", [
        ("It Was Just an Accident", 2025), ("Anora", 2024), ("Anatomy of a Fall", 2023), ("Triangle of Sadness", 2022), ("Titane", 2021),
        ("Parasite", 2019), ("Shoplifters", 2018), ("The Square", 2017), ("I, Daniel Blake", 2016), ("Dheepan", 2015), ("Winter Sleep", 2014),
        ("Blue Is the Warmest Color", 2013), ("Amour", 2012), ("The Tree of Life", 2011), ("Uncle Boonmee Who Can Recall His Past Lives", 2010),
        ("The White Ribbon", 2009), ("The Class", 2008), ("4 Months, 3 Weeks and 2 Days", 2007), ("The Wind That Shakes the Barley", 2006),
        ("The Child", 2005), ("Fahrenheit 9/11", 2004), ("Elephant", 2003), ("The Pianist", 2002), ("The Son's Room", 2001),
        ("Dancer in the Dark", 2000)]),
    "emmy_drama": (T("Emmy: beste dramaserie", "Emmy: Outstanding Drama Series"), "tvshow", [
        ("The Pitt", 2025), ("Shōgun", 2024), ("Succession", 2018), ("The Crown", 2016), ("Game of Thrones", 2011),
        ("The Handmaid's Tale", 2017), ("Breaking Bad", 2008), ("Homeland", 2011), ("Mad Men", 2007), ("The Sopranos", 1999),
        ("24", 2001), ("Lost", 2004), ("The West Wing", 1999)]),
    "emmy_comedy": (T("Emmy: beste comedyserie", "Emmy: Outstanding Comedy Series"), "tvshow", [
        ("The Studio", 2025), ("Hacks", 2021), ("The Bear", 2022), ("Ted Lasso", 2020), ("Schitt's Creek", 2015), ("Fleabag", 2016),
        ("The Marvelous Mrs. Maisel", 2017), ("Veep", 2012), ("Modern Family", 2009), ("30 Rock", 2006), ("The Office", 2005),
        ("Arrested Development", 2003), ("Everybody Loves Raymond", 1996), ("Friends", 1994)]),
}


def companies(kind):
    """[(id, name, logo)] of the studios (kind movie) or networks (kind tvshow), names and logos from TMDB."""
    api, ids = ("company", STUDIOS) if kind == "movie" else ("network", NETWORKS)
    out = []
    for number in ids:
        try:
            data = tmdb.get("%s/%s" % (api, number), ttl=30 * tmdb.DAY)
        except util.HttpError:
            continue
        if data.get("name"):
            out.append((number, data["name"], tmdb.image(data.get("logo_path"), "w500")))
    return out


def company_titles(kind, number, page=1):
    if kind == "movie":
        return tmdb.listing("discover/movie", "movie", page, with_companies=number, sort_by="popularity.desc", include_adult="false")
    return tmdb.listing("discover/tv", "tvshow", page, with_networks=number, sort_by="popularity.desc", include_adult="false")


def decade_titles(kind, start, page=1):
    start = int(start)
    end = min(start + 9, datetime.date.today().year)
    if kind == "movie":
        params = {"primary_release_date.gte": "%d-01-01" % start, "primary_release_date.lte": "%d-12-31" % end, "vote_count.gte": 200}
        return tmdb.listing("discover/movie", "movie", page, sort_by="popularity.desc", include_adult="false", **params)
    params = {"first_air_date.gte": "%d-01-01" % start, "first_air_date.lte": "%d-12-31" % end, "vote_count.gte": 100}
    return tmdb.listing("discover/tv", "tvshow", page, sort_by="popularity.desc", include_adult="false", **params)


def _find(kind, title, year):
    api = "movie" if kind == "movie" else "tv"
    field = "release_date" if kind == "movie" else "first_air_date"
    try:
        rows = tmdb.get("search/" + api, ttl=30 * tmdb.DAY, language="en-US", query=title).get("results") or []
    except util.HttpError:
        return None
    near = [r for r in rows if (r.get(field) or "")[:4].isdigit() and abs(int(r[field][:4]) - year) <= 1]
    return (near or rows or [None])[0]


def award_titles(key, page=1, size=20):
    name, kind, winners = AWARDS[key]
    part = winners[(page - 1) * size:page * size]
    found = [_find(kind, title, year) for title, year in part]
    pairs = list(dict.fromkeys((kind, row["id"]) for row in found if row))
    return tmdb.many(pairs), len(winners) > page * size
