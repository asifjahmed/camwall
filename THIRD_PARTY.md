# Third-party code, data and models

camwall itself is licensed under the GNU Affero General Public License v3 (see `LICENSE`). It includes, or fetches,
the following, each under its own terms.

## Code included with camwall

- **Leaflet 1.9.4** (`web/vendor/leaflet.js`, `leaflet.css`): BSD 2-Clause licence. © 2010–2023 Vladimir Agafonkin,
  © 2010–2011 CloudMade. https://github.com/Leaflet/Leaflet/blob/main/LICENSE
- **hls.js 1.6.13** (`web/vendor/hls.min.js`): Apache License 2.0. © the hls.js authors (Dailymotion).
  https://github.com/video-dev/hls.js/blob/master/LICENSE

The Mac, Windows and Linux downloads also include a Python built by python-build-standalone
(https://github.com/astral-sh/python-build-standalone), under the Python Software Foundation licence and the
licences of the libraries it bundles.

## Data included with camwall

- **Town and ZIP code locations** (`data/places.json`): the US Census Bureau's gazetteer files, public domain.
- **Camera lists** (`data/catalogue/`): the lists each source publishes, fetched when camwall was built. Only
  sources whose terms allow this are included. Sources whose terms restrict apps are never shipped (see
  `CONTRIBUTING.md`). Some ask for credit:
  - **Iowa DOT** (`ia_iowadot`): from its open-data "Traffic Cameras" layer, licensed CC BY 4.0.
    https://iowadot.gov/policies_and_statements/terms-of-use
  - **Illinois DOT** (`il_idot`): from the Illinois Gateway traffic cameras dataset, licensed CC BY-SA 2.0. That list
    stays under CC BY-SA. Travel Midwest's reuse policy: https://travelmidwest.com/About/InfoReusePolicy
  - **Oregon DOT** (`or_odot`): "Oregon DOT (TripCheck) and partner agencies", with its disclaimer.
  - **Rhode Island DOT** (`ri_ridot`), **the City of Lawrence, Kansas** (`ks_lawrence`), **MaineDOT** (`me_mainedot`)
    and **Tri-State: MaineDOT, NHDOT and VTrans** (`nh_newengland511`) ask to be credited.
  - camwall shows each of these credits with that source's cameras.
  - The City of Austin and the National Park Service publish theirs in the public domain.
  - These lists are the agencies' data, not camwall's: camwall's licence doesn't cover them, and each stays under its
    source's terms.
- **Camera pictures and video** aren't included. Each install fetches them from the agency that publishes them,
  and they belong to that agency. The only exceptions are the screenshots in `docs/`, which show Iowa DOT's
  pictures (CC BY 4.0) and OpenStreetMap's map. Settings › Camera sources links each source's site and terms.

## Map

The map shows OpenStreetMap's tiles (map data © OpenStreetMap contributors, ODbL), unless another provider is set in
Settings › Map. camwall fetches them itself, as its tile usage policy asks: with a User-Agent naming camwall, only the
tiles being looked at, each kept for a week (https://operations.osmfoundation.org/policies/tiles/).

## Fetched when the detector is set up (not included)

Setting up the alerts detector installs these from the Python Package Index into camwall's data folder:
PyTorch, torchvision, OpenCLIP, Transformers, Pillow and Ultralytics. It also downloads these models:

- **YOLO11s** (Ultralytics): AGPL-3.0.
- **OpenCLIP ViT-B-32**, trained on LAION-2B: MIT.
- **SigLIP ViT-B-16** (Google, WebLI): Apache License 2.0.
