-- Avalanche Accident Risk Analysis – shared schema (SQLite + PostgreSQL)

CREATE TABLE IF NOT EXISTS regions (
    region_id      TEXT PRIMARY KEY,
    major_region   TEXT,
    centroid_lon   DOUBLE PRECISION,
    centroid_lat   DOUBLE PRECISION
);

CREATE TABLE IF NOT EXISTS bulletin_region_day (
    date                 DATE NOT NULL,
    region_id            TEXT NOT NULL,
    bulletin_id          TEXT,
    danger_level         INTEGER,
    danger_label         TEXT,
    danger_subdivision   TEXT,
    n_problems           INTEGER,
    problem_types        TEXT,
    critical_aspects     TEXT,
    critical_elev_min    DOUBLE PRECISION,
    critical_elev_max    DOUBLE PRECISION,
    publication_time     TEXT,
    PRIMARY KEY (date, region_id)
);

CREATE TABLE IF NOT EXISTS bulletin_problem (
    id                 INTEGER PRIMARY KEY, -- AUTOINCREMENT in SQLite, SERIAL in PG via loader
    date               DATE NOT NULL,
    region_id          TEXT NOT NULL,
    bulletin_id        TEXT,
    problem_type       TEXT,
    aspects            TEXT,
    elev_min           DOUBLE PRECISION,
    elev_max           DOUBLE PRECISION,
    valid_time_period  TEXT
);

CREATE TABLE IF NOT EXISTS stations (
    station_code   TEXT PRIMARY KEY,
    label          TEXT,
    lon            DOUBLE PRECISION,
    lat            DOUBLE PRECISION,
    elevation      DOUBLE PRECISION,
    station_type   TEXT,
    active         INTEGER,
    region_id      TEXT
);

CREATE TABLE IF NOT EXISTS station_day (
    station_code   TEXT NOT NULL,
    date           DATE NOT NULL,
    hs             DOUBLE PRECISION,
    hn_1d          DOUBLE PRECISION,
    hn_3d          DOUBLE PRECISION,
    ta_mean        DOUBLE PRECISION,
    ta_max         DOUBLE PRECISION,
    ta_min         DOUBLE PRECISION,
    vw_mean        DOUBLE PRECISION,
    vw_max         DOUBLE PRECISION,
    PRIMARY KEY (station_code, date)
);

CREATE TABLE IF NOT EXISTS accidents (
    avalanche_id            TEXT PRIMARY KEY,
    date                    DATE,
    hydrological_year       TEXT,
    canton                  TEXT,
    municipality            TEXT,
    lat                     DOUBLE PRECISION,
    lon                     DOUBLE PRECISION,
    coordinates_quality     DOUBLE PRECISION,
    elevation               DOUBLE PRECISION,
    aspect                  TEXT,
    inclination             DOUBLE PRECISION,
    danger_level_reported   DOUBLE PRECISION,
    n_dead                  DOUBLE PRECISION,
    n_caught                DOUBLE PRECISION,
    n_buried                DOUBLE PRECISION,
    activity                TEXT,
    region_id               TEXT,
    in_critical_aspect      INTEGER,
    in_critical_elevation   INTEGER
);

CREATE TABLE IF NOT EXISTS weather_day (
    region_id    TEXT NOT NULL,
    date         DATE NOT NULL,
    t_max        DOUBLE PRECISION,
    t_min        DOUBLE PRECISION,
    precip       DOUBLE PRECISION,
    snowfall     DOUBLE PRECISION,
    wind_max     DOUBLE PRECISION,
    sunshine_s   DOUBLE PRECISION,
    PRIMARY KEY (region_id, date)
);

CREATE TABLE IF NOT EXISTS holidays (
    date         DATE PRIMARY KEY,
    name         TEXT,
    type         TEXT,
    nationwide   INTEGER,
    is_holiday   INTEGER
);

CREATE TABLE IF NOT EXISTS region_day (
    date                 DATE NOT NULL,
    region_id            TEXT NOT NULL,
    major_region         TEXT,
    danger_level         INTEGER,
    danger_label         TEXT,
    danger_subdivision   TEXT,
    n_problems           INTEGER,
    problem_types        TEXT,
    critical_aspects     TEXT,
    critical_elev_min    DOUBLE PRECISION,
    critical_elev_max    DOUBLE PRECISION,
    hs_mean              DOUBLE PRECISION,
    hn_1d_mean           DOUBLE PRECISION,
    hn_3d_mean           DOUBLE PRECISION,
    ta_mean              DOUBLE PRECISION,
    vw_max               DOUBLE PRECISION,
    n_stations           INTEGER,
    t_max                DOUBLE PRECISION,
    t_min                DOUBLE PRECISION,
    precip               DOUBLE PRECISION,
    snowfall             DOUBLE PRECISION,
    wind_max             DOUBLE PRECISION,
    sunshine_s           DOUBLE PRECISION,
    is_weekend           INTEGER,
    is_holiday           INTEGER,
    n_accidents          INTEGER,
    accident_occurred    INTEGER,
    PRIMARY KEY (date, region_id)
);

CREATE INDEX IF NOT EXISTS idx_brd_danger ON bulletin_region_day (danger_level);
CREATE INDEX IF NOT EXISTS idx_acc_date ON accidents (date);
CREATE INDEX IF NOT EXISTS idx_acc_region ON accidents (region_id);
CREATE INDEX IF NOT EXISTS idx_rd_accident ON region_day (accident_occurred);
CREATE INDEX IF NOT EXISTS idx_station_day_date ON station_day (date);
