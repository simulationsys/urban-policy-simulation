# Data Engineering Pipelines — Delhi Build

## Overview

These pipelines fetch, clean, and validate data for the Urban Intelligence Platform simulation. All pipelines are **idempotent** — running them multiple times produces identical outputs.

## Pipeline Stages

| # | Script | Input | Output | Purpose |
|---|--------|-------|--------|---------|
| 1 | `01_download_osm_delhi.py` | OSM Overpass API | `raw/osm/delhi.pbf` | Download road network |
| 2 | `02_parse_gtfs_delhi.py` | GTFS CSV files (manual) | `processed/transit_network_delhi.json` | Parse metro + bus routes |
| 3 | `03_clean_road_network.py` | `raw/osm/delhi.pbf` | `processed/road_network_delhi.parquet` | Extract, clean, validate roads |
| 4 | `04_generate_population_delhi.py` | Census ward data | `processed/synthetic_population_delhi.parquet` | Generate households + agents |
| 5 | `05_validate_outputs.py` | Processed datasets | `validation/report.txt` | Validate all outputs |

## Running Pipelines

**Run all pipelines end-to-end:**
```bash
python run_all_pipelines.py
```

**Run a single pipeline:**
```bash
python 01_download_osm_delhi.py
```

## Configuration

Edit `config.json` to override defaults:
```json
{
  "city": "delhi",
  "bbox": [77.04, 28.40, 77.42, 28.88],
  "population_size": 50000,
  "random_seed": 42
}
```

## Data Versioning

Each processed file includes a hash in its name:
```
road_network_delhi_v0_abc123def.parquet
synthetic_population_delhi_v0_abc123def.parquet
```

This ensures reproducibility: same input + same code = same versioned output.

## Important Notes

- **OSM data is large (~30 MB)**; download only once and cache locally
- **GTFS files must be manually placed** in `raw/gtfs_dmrc/` and `raw/gtfs_dtc/` (not auto-downloaded yet)
- **Census data** is small and committed to the repo
- **Outputs are gitignored** to avoid bloating the repo
