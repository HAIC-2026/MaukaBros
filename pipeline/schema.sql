-- Fact store schema

CREATE OR REPLACE TABLE source (
    source_id    TEXT PRIMARY KEY,
    publisher    TEXT NOT NULL,
    dataset      TEXT NOT NULL,
    url          TEXT NOT NULL,
    year         TEXT NOT NULL,
    retrieved_at TIMESTAMP NOT NULL,
    vintage      TEXT                 -- publisher's release note, e.g. BEA "Last updated: ..."
);

CREATE OR REPLACE TABLE geography (
    geo_id          TEXT PRIMARY KEY,   -- 'HD-22', 'SD-11', 'STATE-15', 'COUNTY-003'
    geo_type        TEXT NOT NULL,      -- 'house' | 'senate' | 'state' | 'county'
    name            TEXT NOT NULL,      -- 'House District 22'; state/county names come from the Census
    district_number INTEGER             -- NULL for state and county comparison rows
);

CREATE OR REPLACE TABLE indicator (
    indicator_id TEXT PRIMARY KEY,
    label        TEXT NOT NULL,
    unit         TEXT NOT NULL,
    table_ids    TEXT NOT NULL        -- ACS table(s) the variables come from, e.g. 'B19013'
);

CREATE OR REPLACE TABLE fact (
    geo_id       TEXT NOT NULL REFERENCES geography (geo_id),
    indicator_id TEXT NOT NULL REFERENCES indicator (indicator_id),
    source_id    TEXT NOT NULL REFERENCES source (source_id),
    value        DOUBLE,              -- NULL when not published
    moe          DOUBLE,              -- 90% margin of error; NULL when not available
    value_status TEXT NOT NULL,       -- ok | suppressed | not_applicable
    moe_status   TEXT NOT NULL,       -- ok | derived | controlled | not_computable | not_applicable
    method       TEXT NOT NULL,       -- direct | apportioned | modeled
    PRIMARY KEY (geo_id, indicator_id, source_id)
);

-- County and state context from sources that do not publish by legislative district
-- (BEA, BLS, DBEDT...). Shown as context for a district's county, never as a district figure.
-- Loaded by pipeline/context.py from files listed in pipeline/raw/manifest.yaml.
CREATE OR REPLACE TABLE context_indicator (
    indicator_id TEXT PRIMARY KEY,
    label        TEXT NOT NULL,
    unit         TEXT NOT NULL,
    table_id     TEXT NOT NULL,       -- publisher's table, e.g. 'CAINC1', 'Data Book 11.03'
    table_url    TEXT NOT NULL,
    table_title  TEXT,                -- the title as printed in the file
    original_source TEXT,             -- when the table republishes another agency's data
    caveat       TEXT                 -- shown with every value, e.g. '11-month average'
);

CREATE OR REPLACE TABLE context_fact (
    geo_id       TEXT NOT NULL REFERENCES geography (geo_id),   -- county or state only
    indicator_id TEXT NOT NULL REFERENCES context_indicator (indicator_id),
    source_id    TEXT NOT NULL REFERENCES source (source_id),
    period       TEXT NOT NULL,       -- e.g. '2024'
    value        DOUBLE,              -- NULL when not published
    value_status TEXT NOT NULL,       -- ok | suppressed | not_published
    note         TEXT,                -- e.g. 'Maui and Kalawao combined'
    PRIMARY KEY (geo_id, indicator_id, source_id)
);

-- DOTAX geographic areas (Individual Income Tax Statistics, Table A-13) and the ZIP codes that
-- make them up (Table A-14). Figures as published for each area; never split across districts.
CREATE OR REPLACE TABLE tax_area (
    area_id        TEXT PRIMARY KEY,  -- 'TAX-oahu-north-shore'
    name           TEXT NOT NULL,     -- with ʻokina: 'Oʻahu North Shore'
    name_published TEXT NOT NULL,     -- as printed: "O'ahu North Shore"
    county_geo_id  TEXT NOT NULL REFERENCES geography (geo_id),
    returns        DOUBLE,            -- resident returns, tax year 2023
    median_agi     DOUBLE             -- median Hawaiʻi AGI per return, dollars
);

CREATE OR REPLACE TABLE tax_area_zip (
    zip        TEXT PRIMARY KEY,
    area_id    TEXT NOT NULL REFERENCES tax_area (area_id),
    returns    DOUBLE,
    median_agi DOUBLE
);

-- Census 2024 district-to-ZCTA relationship files: land area of each overlap (square meters).
CREATE OR REPLACE TABLE district_zcta (
    geo_id        TEXT NOT NULL REFERENCES geography (geo_id),
    zcta          TEXT,               -- NULL: district land outside every ZCTA
    land_part     DOUBLE NOT NULL,
    district_land DOUBLE NOT NULL,
    zcta_land     DOUBLE
);

-- Which DOTAX tax areas overlap each district, from the two tables above. Area figures are shown
-- whole; these shares only describe the overlap and label it.
CREATE OR REPLACE TABLE tax_area_district (
    geo_id         TEXT NOT NULL REFERENCES geography (geo_id),
    area_id        TEXT NOT NULL REFERENCES tax_area (area_id),
    land_overlap   DOUBLE NOT NULL,   -- square meters
    district_share DOUBLE NOT NULL,   -- share of the district's land in this tax area
    area_share     DOUBLE NOT NULL,   -- share of the tax area's (ZCTA) land in this district
    relation       TEXT NOT NULL,     -- 'overlaps' | 'touches the edge'
    PRIMARY KEY (geo_id, area_id)
);