# -*- coding: utf-8 -*-
"""All sources of streams. A new scraper = one entry here, with a fetch(meta) that returns a list of source dicts.

Required in each source: url, name, resolution, flags (may be []), size, cached, service, meta. See streams.convert.
"""
from concurrent.futures import ThreadPoolExecutor, wait

import coco
import ranking
import streams
import usenet
import util

REGISTRY = {"AIOStreams": streams.fetch, "Easynews": usenet.easynews, "TorBox": usenet.torbox, "CocoScrapers": coco.fetch}
LINKS = {"TorBox": usenet.torbox_link, "CocoScrapers": coco.link}


def names(profile):
    """Scraper names in the order of the profile; new ones at the end."""
    order = [n for n in profile["scrapers"].get("order") or [] if n in REGISTRY]
    return order + [n for n in REGISTRY if n not in order]


def _run(selection, profile, meta):
    """Returns (sources in scraper order, did anything answer?, was an address missing everywhere?)."""
    per = profile["scrapers"].get("per") or {}
    pool = ThreadPoolExecutor(max_workers=max(1, len(selection)))
    jobs = {name: pool.submit(REGISTRY[name], meta) for name in selection}
    wait(list(jobs.values()), timeout=max(5, int(profile["scrapers"].get("wait") or 30)))
    pool.shutdown(wait=False)
    collected, answered, unset = [], False, 0
    for name in selection:
        job = jobs[name]
        if not job.done():
            util.log("%s: took too long" % name)
            continue
        try:
            found = job.result()
        except util.HttpError as error:
            util.log("%s: %s" % (name, error))
            continue
        if found is None:
            unset += 1
            continue
        answered = True
        limit = int(per.get(name, {}).get("max") or 0)
        for source in found[:limit] if limit else found:
            collected.append(dict(source, scraper=name))
    return collected, answered, unset == len(selection)


def ready(source):
    """Some scrapers only make their link when you press play. True when the source has a link."""
    job = source.get("resolve")
    if source.get("url") or not job:
        return bool(source.get("url"))
    source["url"] = LINKS[job["scraper"]](job) or ""
    return bool(source["url"])


def search(meta):
    """Returns (ranked sources, None) or (None, 'address' or 'failed')."""
    import subcheck
    subtitles = subcheck.start(meta) if not meta.get("no_subcheck") else None
    profile = ranking.active()
    per = profile["scrapers"].get("per") or {}
    order = [n for n in names(profile) if not per.get(n, {}).get("off")]
    main = [n for n in order if not per.get(n, {}).get("fallback")]
    spare = [n for n in order if per.get(n, {}).get("fallback")]
    found, answered, unset = _run(main, profile, meta) if main else ([], False, False)
    if not found and spare:
        extra, answered_spare, _ = _run(spare, profile, meta)
        found, answered = extra, answered or answered_spare
    if not answered and not found:
        return None, "address" if unset else "failed"
    import learn
    fitting = subcheck.mark(subtitles, found)          # before ranking, so the order of sources can use NL-SUBS
    ranked = learn.adjust(ranking.apply(found, profile, meta["kind"], order))
    return subcheck.first(ranked, fitting), None
