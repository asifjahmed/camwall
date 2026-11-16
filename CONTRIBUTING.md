# Contributing

The most useful help is with camera sources. Agencies change their sites often, so sources break; and there are
still towns, counties and toll roads whose public cameras camwall doesn't have. `research/COVERAGE.md` shows what each
state has.

## Fixing or adding a camera source

Each source is one module in `sources/`, and `sources/__init__.py` describes what it defines: `SOURCE` (who runs the
cameras, where their terms are) and `cameras(get, key=None)`, which yields each camera.

1. Find the list the agency's own public page uses: its map's JSON, an ArcGIS layer, an XML feed. Look at what the
   page fetches in your browser's developer tools.
2. Write or fix the module. Copy a similar one: `ia_iowadot` (ArcGIS), `oh_ohgo` (a JSON API), `or_odot` (credit and
   a disclaimer).
3. Check it: `python3 -m sources.check <module>`. This runs it, validates every camera, tries a few pictures and video
   streams, and saves the list to `sources/out/`.
4. Open a pull request saying where the list comes from and what its terms say.

### The rules for sources

- **Public only.** A source must be something the agency shows anyone, without an account. Don't sign up for
  accounts, and don't get around logins, keys, challenges or other access controls.
- **Never pretend to be the agency's own page.** If its server only answers with the page's Referer or Origin, a
  header the page adds, or a key from the page's own code, it isn't public to apps: leave it out, or use what the
  agency offers developers (a key the user asks for goes in `SOURCE["key"]`).
- **Never use credentials you find.** If a source's data exposes passwords or private stream addresses, don't request
  that field, and report it to the agency rather than in a public issue.
- **Record the terms.** Put the agency's terms of use in `SOURCE["terms"]`, and quote what matters in `notes`:
  - If the terms restrict apps like camwall (no automated access, no republishing, personal use only), set
    `restricted` to the quote. A restricted source is off until a user turns it on, after seeing its terms, and it's
    never shipped in `data/catalogue/`.
  - If the terms forbid saving or capturing pictures, set `no_capture`. Alerts are then off for its cameras, since an
    alert saves a picture.
  - If they ask for credit or a disclaimer, set `credit` and `disclaimer`. camwall shows them with the cameras.
- **Be light on their servers.** One request for the list. `sources.get` already spaces requests to one host.
- **robots.txt:** if the list's path is one the site's robots.txt asks crawlers to leave alone, set
  `NOT_FOR_CRAWLERS = True` in the module. camwall itself fetches a list once a day for someone using it, but the
  weekly source check is a crawler and skips it.
- **Terms that forbid copying the list on** (all rights reserved, a non-transferable licence): set `SHIPPED = False`.
  The list isn't shipped with camwall; each install fetches it, for its user's state or when they turn it on.
- **Links that expire** (signed or tokenized): list them, and set `EXPIRING = ("video",)` or `("image",)` with a
  `resolve()` that gets fresh ones, so that the shipped lists keep none.
- **No YouTube-only cameras.** YouTube's terms forbid this kind of automated access.
- **Withdrawn sources** (`data/withdrawn.json`) are ones whose agencies asked camwall to stop using their cameras.
  Every copy of camwall reads that file daily and turns them off. Don't add them back without the agency's say.

## Code

- The app uses only Python's standard library (3.11 or newer), plus ffmpeg for video. Only the optional detector
  (`detector/`) has other dependencies, installed when a user turns it on.
- Run the tests before a pull request: `python3 -m unittest discover tests`.
- Security problems: see `SECURITY.md`. Please don't open a public issue for them.

By contributing, you agree that your contribution is licensed under the AGPL-3.0, like the rest of camwall.
