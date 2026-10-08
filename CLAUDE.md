# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

A GitHub Pages site (https://tristangabl.github.io/all_mensa/) showing today's menus for ETH Polymensa, UZH Untere Mensa, UZH Obere Mensa and UZH Platte 14. No build step, no dependencies beyond the Python stdlib.

## Commands

- Fetch menus locally: `python3 scripts/fetch.py` (writes `data/menu.json`, prints meal count / error per mensa)
- Preview: `python3 scripts/fetch.py && python3 -m http.server`, open http://localhost:8000
- Deploy: push to `main`, or `gh workflow run update.yml`. Check with `gh run list -L1`.

There are no tests or linters.

## Architecture

Pages is static and the source sites block cross-origin requests, so data is scraped server-side at deploy time, not in the browser:

1. `.github/workflows/update.yml` runs on push, manually, and on a UTC cron (`43 6-10 * * *`, `17 13 * * *`; Zurich 8:43–12:43 + 15:17 in summer time). It runs `scripts/fetch.py`, copies `index.html` + `data/menu.json` into `_site/` and deploys via `actions/deploy-pages`. `data/` and `_site/` are gitignored; the JSON only exists in the deployed artifact.
2. `scripts/fetch.py` produces `{date, updated, mensas: [{name, link, meals: [{time, line, name, description, tags, price, image}], error?}]}`. Each source is wrapped in `safe()`, so a broken source yields `meals: []` + `error` instead of failing the deploy.
3. `index.html` is self-contained (inline CSS/JS): renders cards from `data/menu.json`, a photo popup (`<dialog>`) on meal click, and a scripted joke "advisor" chatbot (asks mensa, then meal, then "recommends" exactly that choice).

### Data sources (fragile parts)

- **ETH**: JSON API `idapps.ethz.ch/cookpit-pub-services/v1/weeklyrotas`, filtered by facility id 9 and today's weekday. Image URLs require `?client-id=ethz-wcms` appended, otherwise they return a text error. Student price = customer group `stud.`. Lines named `novalue` are placeholders and skipped.
- **ETH filtering/ordering** (user preference): drop lines starting with "Hot & Cold", "Dessert", "Poly-Bowl"; within each meal time sort VEGAN, GARDEN, HOME first (prefix match, so "GARDEN ABEND" counts).
- **UZH (food2050)**: no API — `fetch.py` regex-parses the Next.js RSC payload embedded in the weekly page `app.food2050.ch/de/zfv/universitat-zurich,<campus>/<outlet>/<menu>/menu/weekly` (Untere: `campus-zentrum/untere-mensa/mittagsverpflegung`, Obere: `campus-zentrum/obere-mensa/lunch`, Platte 14: `platte-14/platte-14/mittagsverpflegung`). The payload is split on `OutletMenuCategoryCalendarRangeDay` / `OutletMenuItemDish` markers. Repeated objects are `$7:...` references, so the line name falls back to the last segment of `detailUrl`.
- Prices and images are not on the weekly page: `dish_details()` fetches each dish's `detailUrl` page and reads the `Studierende` price and `imageUrl`. A price of 0.00 means "not set" and is stored as `null`.
- Obere Mensa lines are renamed: MENU 1→GARDEN, 2→PASTA, 3→BUTCHER, 4→VOLL ANDERS.
- Use the non-`v2`, comma-form URLs; the `v2`/`%2C` URLs return a 308 that urllib doesn't follow.
