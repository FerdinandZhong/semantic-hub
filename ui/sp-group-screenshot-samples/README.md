# SP Group power-sector screenshot samples

Open [Sources](index.html), [semantic context](context.html), [NiFi](nifi.html), [observability](observability.html) and [data understanding](data.html).
These five pages reuse the original static layouts from `Handson_labs/uob_screenshot_samples`.
They now show a fictional SP Group power-sector prototype.
The original UOB pages and running application remain unchanged.

Sources and semantic context describe meter readings, imported energy and a proposed feeder-demand view.
NiFi shows meter-reading ingestion. Observability shows ingestion errors, exact log evidence and CPU metrics.
Data understanding shows measured energy by Singapore date and service region.
The seven-day total is 8,547.28 kWh across 3,960 valid, non-estimated readings.
Missing and estimated readings are excluded. These are fictional values, not SP Group operational data.

The power CSV pack is staged under `apps/helios-ds-generation/fixtures/sectors/v1/power`.
`sample-data.json` records its checksum and derived daily totals.
`context-models.json` defines the three model previews.
The feeder-demand view is proposed; the fixture does not yet materialize that view.
Sample review badges illustrate the workflow. They do not establish live approval or acceptance.
These pages do not query services, execute SQL or publish releases.
The live application's banking planner has not been converted into a power planner.

## Rebuild and verify

Run these commands from the project root:

```sh
python ui/sp-group-screenshot-samples/build_power_pages.py
python ui/sp-group-screenshot-samples/check_static.py
python ui/sp-group-screenshot-samples/check_pages.py
```

The builder updates the existing page shells from the staged power fixture.
It preserves the styles and navigation. The rebuild is deterministic.
Static content and JavaScript syntax checks passed on 10 October 2026.
The browser script requires Playwright and Chromium. It exports 18 desktop/context/mobile PNGs.
Set `SCREENSHOT_CHROMIUM_PATH` to select an installed Chromium executable.
The browser attempt failed during startup with MachPortRendezvous permission denied.
No new screenshot PNGs or responsive-layout acceptance are claimed.

## Logo and offline use

The logo uses the PNG on the [Singapore government SP Group profile](https://www.poweringlives.gov.sg/about/industry-partners/sp-group/).
The pages currently load that PNG online. Download access was blocked in this environment.
Run this command with network access to embed the same logo:

```sh
python ui/sp-group-screenshot-samples/cache_logo.py
```

After embedding, the pages require no external requests.
`source-manifest.json` preserves original page hashes and records the new power-page hashes.
A later narrative should follow preparation, meter ingestion, operational evidence and energy understanding.
