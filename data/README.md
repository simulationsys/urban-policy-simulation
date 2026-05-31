# SUB-04 — Data Engineering

**Urban Intelligence Platform (UIP)**
*Study Area: Rajiv Chowk, New Delhi, India*

---

## Overview

This module handles all data acquisition, cleaning, and transformation pipelines
for the Urban Intelligence Platform. The primary focus area is a **2 km radius
around Rajiv Chowk Metro Station** (28.6328° N, 77.2197° E) in central New Delhi.

## Folder Structure

```
SUB-04_Data_Engineering/
├── README.md                 ← You are here
├── requirements.txt          ← Python dependencies
├── venv/                     ← Python virtual environment (not committed)
│
├── raw_data/                 ← Unmodified source data downloads
│   └── (populated by pipeline scripts)
│
├── processed_data/           ← Cleaned, analysis-ready outputs
│   ├── network.graphml       ← OSM street network (GraphML)
│   └── edges.parquet         ← OSM edge list (GeoParquet)
│
└── pipelines/                ← Data acquisition & processing scripts
    ├── 1_download_osm_network.py
    └── 2_fetch_census_demographics.py  (placeholder)
```

## Data Provenance

| Dataset | Source | License | Status |
|---------|--------|---------|--------|
| Street Network | [OpenStreetMap](https://www.openstreetmap.org/) via `osmnx` | ODbL 1.0 | ✅ Implemented |
| Census Demographics | [Census of India 2011](https://censusindia.gov.in/) | Government Open Data | ⏳ Placeholder |

### OpenStreetMap Network

- **Query**: Point-based, 2 km radius around (28.6328, 77.2197)
- **Network type**: `drive` (drivable roads only)
- **Cleaning**: Largest strongly-connected component retained
- **Formats**: GraphML (for NetworkX), Parquet edge list (for pandas/geopandas)

### Census Demographics (Planned)

- **Tables**: C-13 (age), HH-1/HH-2 (household size), B-4 (worker categories)
- **Income proxy**: Worker categories mapped to PLFS wage brackets
- **Geographic filter**: NCT of Delhi

## How to Run

### 1. Environment Setup

```bash
# Navigate to this directory
cd SUB-04_Data_Engineering

# Create and activate the virtual environment
python -m venv venv

# Windows
venv\Scripts\activate

# Linux / macOS
# source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### 2. Run the OSM Network Pipeline

```bash
python pipelines/1_download_osm_network.py
```

**Expected output:**
- `processed_data/network.graphml` — Full graph in GraphML format
- `processed_data/edges.parquet` — Edge list as GeoParquet

### 3. Census Demographics (Not Yet Implemented)

```bash
# python pipelines/2_fetch_census_demographics.py
# See the script for detailed implementation notes
```

## Dependencies

| Package | Purpose |
|---------|---------|
| `osmnx` | OpenStreetMap network download & analysis |
| `geopandas` | Geospatial DataFrames & Parquet export |
| `pandas` | Tabular data processing |
| `shapely` | Geometric operations |
| `networkx` | Graph data structures (bundled with osmnx) |
| `pyarrow` | Parquet file I/O engine |

## Notes

- The virtual environment (`venv/`) should **not** be committed to version control.
- Raw data files in `raw_data/` should be treated as immutable once downloaded.
- All processed outputs are reproducible by re-running the pipeline scripts.
