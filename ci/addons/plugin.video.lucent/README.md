# Lucent Video

Films and series for Kodi, made for the Lucent skin but working in any skin:
- browse with TMDB;
- play through your own AIOStreams address, Easynews, TorBox, debrid services or CocoScrapers;
- keep your progress on Trakt, Simkl or only this device.

## For other add-ons and skins

These actions are public: any add-on or skin may call them with `RunPlugin(plugin://plugin.video.lucent/?...)`.

- `tmdb` is always the TMDB id of the film or series. For an episode or season it is the series' id.
- They work for any title, also when it does not come from Lucent Video.
- Without an account they use this device.

### The info page of a title

| Button | Call |
|---|---|
| All options in one menu | `action=title_menu&type=movie\|tvshow\|season\|episode&tmdb=<id>[&season=<n>][&episode=<n>]` |
| Play (choose the best source) | `action=play&type=movie&tmdb=<id>` or `action=play&type=episode&tmdb=<id>&season=<n>&episode=<n>` |
| Choose a source yourself | the same, with `&select=1` |
| Seasons of a series (a folder) | `ActivateWindow(Videos,plugin://plugin.video.lucent/?action=seasons&tmdb=<id>,return)` |
| Mark as watched or unwatched | `action=watched&type=movie\|tvshow\|season\|episode&tmdb=<id>[&season=<n>][&episode=<n>]&value=1\|0` |
| Library and lists (ticks: watchlist, collection, Kodi library, own Trakt lists, Simkl status, own static MDBList lists) | `action=lists&type=movie\|tvshow&tmdb=<id>` |
| Add to or remove from the watchlist | `action=watchlist&type=movie\|tvshow&tmdb=<id>&value=1\|0` |
| Add to or remove from the Kodi library at once | `action=library_add&type=movie\|tvshow&tmdb=<id>` and `action=library_remove&...` |
| Keep an episode or season out of the library | `action=library_skip&tmdb=<id>&season=<n>[&episode=<n>]` |
| Trailer | `action=trailer&type=movie\|tvshow&tmdb=<id>` |
| Cast (pop-up) | `action=cast_popup&type=movie\|tvshow&tmdb=<id>` |
| Similar titles (a folder) | `ActivateWindow(Videos,plugin://plugin.video.lucent/?action=list&name=similar&type=movie\|tvshow&tmdb=<id>,return)` |
| Rate (Great, Nice, Not for me; Kompas learns from it) | `action=kompas_rate&type=movie\|tvshow&tmdb=<id>` |
| Get ready for tonight (sources looked up beforehand) | `action=tonight_add&type=movie\|episode&tmdb=<id>[&season=<n>&episode=<n>]` |
| Skip the intro by itself for this series: on or off | `action=introskip&tmdb=<id>` |

### While watching

| Button | Call |
|---|---|
| Subtitles: the live list of all subtitle add-ons | `action=subtitles` |
| Spoken language: first and second choice | `action=subs_audio` |

### Windows and settings

| What | Call |
|---|---|
| Kompas page, Your taste | `action=kompas_page`, `action=kompas_taste` |
| What shall we watch? / Your year of watching | `action=pick`, `action=year` |
| Type with your phone | `action=remote` |
| Format check | `action=formatcheck` |
| Settings on a category | `action=settings&section=general\|account\|sources\|play\|subs\|skip\|library\|services` |
| Subtitles or skip intro, step by step | `action=subs_setup`, `action=skip_setup` |

Rows for Home and their properties: see the docstrings of `router.py`, `widgets.py`, `kompas.py`, `services.py` and `librows.py`.

## Privacy

Lucent Video runs on your own device and has no server. Keys and sign-in tokens stay in Kodi's add-on data folder and are never written to the log.

Lucent uses Trakt but is not endorsed or certified by Trakt.
