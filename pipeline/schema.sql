-- Fact store schema

CREATE OR REPLACE TABLE source (
    source_id    TEXT PRIMARY KEY,
    publisher    TEXT NOT NULL,
    dataset      TEXT NOT NULL,
    url          TEXT NOT NULL,
    year         TEXT NOT NULL,
    retrieved_at TIMESTAMP NOT NULL
);

CREATE OR REPLACE TABLE geography (
    geo_id          TEXT PRIMARY KEY,   -- 'HD-22', 'SD-11'
    geo_type        TEXT NOT NULL,      -- 'house' | 'senate'
    name            TEXT NOT NULL,      -- 'House District 22'
    district_number INTEGER NOT NULL
);

CREATE OR REPLACE TABLE indicator (
    indicator_id TEXT PRIMARY KEY,
    label        TEXT NOT NULL,
    unit         TEXT NOT NULL
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