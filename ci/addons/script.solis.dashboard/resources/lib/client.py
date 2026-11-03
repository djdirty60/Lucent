# -*- coding: utf-8 -*-
"""Haalt de pagina's op bij het dashboard van Solis voor Homey."""
import json

try:
    from urllib.request import urlopen
except ImportError:  # pragma: no cover
    from urllib2 import urlopen


def url_for(host, port):
    host = (host or '').strip().replace('http://', '').replace('https://', '').strip('/')
    if ':' in host:
        return 'http://%s/kodi.json' % host
    return 'http://%s:%s/kodi.json' % (host, int(port or 8765))


def fetch(host, port, timeout=6):
    with urlopen(url_for(host, port), timeout=timeout) as resp:
        data = json.loads(resp.read().decode('utf-8'))
    if not isinstance(data, dict) or not data.get('pages'):
        raise ValueError('onverwacht antwoord')
    return data


def base_url(host, port):
    host = (host or '').strip().replace('http://', '').replace('https://', '').strip('/')
    if ':' in host:
        return 'http://%s' % host
    return 'http://%s:%s' % (host, int(port or 8780))


def fetch_pages(host, port, timeout=5, prefix=''):
    """Lijst met pagina's van de beeldserver (of van de Homey-app met prefix /beeld)."""
    with urlopen(base_url(host, port) + prefix + '/pages.json', timeout=timeout) as resp:
        data = json.loads(resp.read().decode('utf-8'))
    pages = [p for p in data.get('pages', []) if isinstance(p, str)]
    if not pages:
        raise ValueError('geen pagina\'s')
    return pages


def download_page(host, port, page, path, timeout=20, prefix='', ext='jpg'):
    """Haalt de afbeelding van een pagina op en schrijft die naar path."""
    with urlopen('%s%s/page/%s.%s' % (base_url(host, port), prefix, page, ext), timeout=timeout) as resp:
        body = resp.read()
    if len(body) < 1000 or not (body[:2] == b'\xff\xd8' or body[:4] == b'\x89PNG'):
        raise ValueError('geen geldige afbeelding')
    with open(path, 'wb') as fh:
        fh.write(body)
    return path


def fetch_notifications(host, port, since=None, timeout=5):
    """Nieuwe meldingen uit de Solis-app op de Homey (/meldingen.json)."""
    url = base_url(host, port) + '/meldingen.json'
    if since is not None:
        url += '?since=%d' % int(since)
    with urlopen(url, timeout=timeout) as resp:
        return json.loads(resp.read().decode('utf-8'))
