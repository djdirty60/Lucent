# -*- coding: utf-8 -*-
"""Debrid services for torrent sources (from CocoScrapers): TorBox, Premiumize, Real-Debrid and AllDebrid.

Each service is set with an API key in the settings. Keys are never logged.
- TorBox and Premiumize can say beforehand which torrents they already have ("cached"); only those are shown for them.
- Real-Debrid and AllDebrid stopped offering that check in 2024. Lucent tries their torrents when you press play and
  only plays when the service has the file at once; otherwise the torrent is removed again and the next source is tried.
"""
import re
import time
import urllib.parse

import xbmc

import util

T = util.T
VIDEO = (".mkv", ".mp4", ".avi", ".ts", ".m2ts", ".mov", ".wmv", ".webm")
AGENT = "Lucent-Video"
WAIT = 12
RD = "https://api.real-debrid.com/rest/1.0/"
AD = "https://api.alldebrid.com/"
PM = "https://www.premiumize.me/api/"
TB = "https://api.torbox.app/v1/api/"
SERVICES = [("torbox", "TorBox", "torbox_key"), ("premiumize", "Premiumize", "premiumize_key"),
            ("realdebrid", "Real-Debrid", "realdebrid_key"), ("alldebrid", "AllDebrid", "alldebrid_key")]
CHECKED = ("torbox", "premiumize")


def key(service):
    return util.setting(dict((s, k) for s, _n, k in SERVICES)[service]).strip()


def label(service):
    return dict((s, n) for s, n, _k in SERVICES)[service].upper()


def active():
    return [s for s, _n, _k in SERVICES if key(s)]


def _head(service):
    return {"Authorization": "Bearer %s" % key(service), "User-Agent": AGENT}


def _chunks(items, size=80):
    for start in range(0, len(items), size):
        yield items[start:start + size]


# ------------------------------------------------------------------ what is cached
def _tb_cached(hashes):
    found = set()
    for part in _chunks(hashes):
        answer, _ = util.http(TB + "torrents/checkcached?" + urllib.parse.urlencode({"hash": ",".join(part), "format": "list"}),
                              headers=_head("torbox"), timeout=20)
        for row in (answer or {}).get("data") or []:
            if row.get("hash"):
                found.add(row["hash"].lower())
    return found


def _pm_cached(hashes):
    found = set()
    for part in _chunks(hashes):
        query = urllib.parse.urlencode([("items[]", h) for h in part])
        answer, _ = util.http(PM + "cache/check?" + query, headers=_head("premiumize"), timeout=20)
        for value, flag in zip(part, (answer or {}).get("response") or []):
            if flag:
                found.add(value)
    return found


def assign(hashes):
    """{hash: service} for every torrent that one of your services can play. Checked services come first."""
    hashes = [h.lower() for h in dict.fromkeys(hashes) if h]
    out = {}
    for service in active():
        rest = [h for h in hashes if h not in out]
        if not rest:
            break
        if service in CHECKED:
            try:
                cached = (_tb_cached if service == "torbox" else _pm_cached)(rest)
            except util.HttpError as error:
                util.log("%s cache check: %s" % (service, error))
                continue
            out.update((h, service) for h in rest if h in cached)
        else:
            out.update((h, service) for h in rest)          # tried when you press play
    return out


# ------------------------------------------------------------------ choosing the file
def _pick(files, season, episode, name_of, size_of):
    files = [f for f in files if str(name_of(f)).lower().endswith(VIDEO)]
    if season and episode:
        pattern = re.compile(r"s0*%d[ ._-]?e0*%d(?!\d)|\b0*%dx0*%d\b" % (int(season), int(episode), int(season), int(episode)), re.I)
        exact = [f for f in files if pattern.search(str(name_of(f)))]
        if not exact:
            return None
        files = exact
    return max(files, key=lambda f: size_of(f) or 0) if files else None


def _magnet(job):
    return "magnet:?xt=urn:btih:%s&dn=%s" % (job["hash"], urllib.parse.quote(job.get("name") or ""))


# ------------------------------------------------------------------ links
def _tb_link(job):
    import usenet
    return usenet.torbox_link({"kind": "torrents", "link": _magnet(job), "name": job.get("name") or "",
                               "season": job.get("season"), "episode": job.get("episode")})


def _pm_link(job):
    answer, _ = util.http(PM + "transfer/directdl", form={"src": _magnet(job)}, headers=_head("premiumize"), timeout=30)
    files = (answer or {}).get("content") or []
    chosen = _pick(files, job.get("season"), job.get("episode"), lambda f: f.get("path") or "", lambda f: f.get("size"))
    return (chosen or {}).get("stream_link") or (chosen or {}).get("link")


def _rd_link(job):
    head = _head("realdebrid")
    added, _ = util.http(RD + "torrents/addMagnet", form={"magnet": _magnet(job)}, headers=head, timeout=25)
    torrent = (added or {}).get("id")
    if not torrent:
        return None
    try:
        info, _ = util.http(RD + "torrents/info/" + torrent, headers=head, timeout=20)
        files = (info or {}).get("files") or []
        chosen = _pick(files, job.get("season"), job.get("episode"), lambda f: f.get("path") or "", lambda f: f.get("bytes"))
        if not chosen:
            raise util.HttpError("no matching file")
        util.http(RD + "torrents/selectFiles/" + torrent, form={"files": str(chosen["id"])}, headers=head, timeout=20, raw=None)
        monitor, end = xbmc.Monitor(), time.time() + WAIT
        while time.time() < end:
            info, _ = util.http(RD + "torrents/info/" + torrent, headers=head, timeout=20)
            if (info or {}).get("status") == "downloaded" and info.get("links"):
                answer, _ = util.http(RD + "unrestrict/link", form={"link": info["links"][0]}, headers=head, timeout=20)
                return (answer or {}).get("download")
            if (info or {}).get("status") in ("magnet_error", "error", "virus", "dead") or monitor.waitForAbort(1.5):
                break
    except util.HttpError as error:
        util.log("Real-Debrid: %s" % error)
    try:                                                   # not ready at once: leave the account as it was
        util.http(RD + "torrents/delete/" + torrent, headers=head, method="DELETE", timeout=15)
    except util.HttpError:
        pass
    return None


def _ad_call(path, params=None, form=None):
    query = urllib.parse.urlencode(dict(params or {}, agent=AGENT), doseq=True)
    answer, _ = util.http(AD + path + "?" + query, form=form, headers=_head("alldebrid"), timeout=25)
    if (answer or {}).get("status") != "success":
        raise util.HttpError(((answer or {}).get("error") or {}).get("code") or "AllDebrid")
    return answer.get("data") or {}


def _ad_files(nodes, path=""):
    for node in nodes or []:
        name = "%s/%s" % (path, node.get("n") or "")
        if node.get("e"):
            yield from _ad_files(node["e"], name)
        elif node.get("l"):
            yield {"name": name, "size": node.get("s") or 0, "link": node["l"]}


def _ad_link(job):
    magnet_id = None
    try:
        data = _ad_call("v4/magnet/upload", form={"magnets[]": _magnet(job)})
        magnet_id = ((data.get("magnets") or [{}])[0]).get("id")
        if not magnet_id:
            return None
        monitor, end = xbmc.Monitor(), time.time() + WAIT
        while time.time() < end:
            status = (_ad_call("v4.1/magnet/status", {"id": magnet_id}).get("magnets") or {})
            if isinstance(status, list):
                status = status[0] if status else {}
            if status.get("statusCode") == 4:                # ready
                files = _ad_call("v4/magnet/files", {"id[]": magnet_id}).get("magnets") or [{}]
                chosen = _pick(list(_ad_files(files[0].get("files"))), job.get("season"), job.get("episode"),
                               lambda f: f["name"], lambda f: f["size"])
                if not chosen:
                    break
                return _ad_call("v4/link/unlock", {"link": chosen["link"]}).get("link")
            if (status.get("statusCode") or 0) > 4 or monitor.waitForAbort(1.5):
                break
    except util.HttpError as error:
        util.log("AllDebrid: %s" % error)
    if magnet_id:
        try:
            _ad_call("v4/magnet/delete", {"id": magnet_id})
        except util.HttpError:
            pass
    return None


LINKS = {"torbox": _tb_link, "premiumize": _pm_link, "realdebrid": _rd_link, "alldebrid": _ad_link}


def link(job):
    try:
        return LINKS[job["service"]](job)
    except util.HttpError as error:
        util.log("%s: %s" % (job["service"], error))
        return None


# ------------------------------------------------------------------ settings test
CHECK = {"premiumize": (PM + "account/info", lambda a: a.get("status") == "success"),
         "realdebrid": (RD + "user", lambda a: bool(a.get("username"))),
         "alldebrid": (AD + "v4/user?agent=" + AGENT, lambda a: a.get("status") == "success"),
         "torbox": (TB + "user/me", lambda a: bool(a.get("data")))}


def check(service):
    name = dict((s, n) for s, n, _k in SERVICES)[service]
    if not key(service):
        return False, T("Vul eerst je API-sleutel in.", "Enter your API key first.")
    url, ok = CHECK[service]
    try:
        answer, _ = util.http(url, headers=_head(service), timeout=20)
    except util.HttpError as error:
        return False, T("Geen verbinding: %s", "No connection: %s") % error
    if not ok(answer or {}):
        return False, T("%s accepteert deze sleutel niet.", "%s does not accept this key.") % name
    return True, T("Verbonden met %s.", "Connected to %s.") % name
