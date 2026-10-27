BEGIN;

CREATE EXTENSION IF NOT EXISTS postgis;

-- hk_district is created by shp2pgsql and repaired before this script runs.
ALTER TABLE hk_district
    RENAME COLUMN id TO district_id;

ALTER TABLE hk_district
    ALTER COLUMN district_id TYPE integer
    USING district_id::integer;

ALTER TABLE hk_district
    RENAME COLUMN ename TO district_name;

ALTER TABLE hk_district
    DROP CONSTRAINT hk_district_pkey;

ALTER TABLE hk_district
    ADD CONSTRAINT hk_district_pkey PRIMARY KEY (district_id);

ALTER TABLE hk_district
    DROP COLUMN gid,
    DROP COLUMN objectid,
    DROP COLUMN cname,
    DROP COLUMN cname_s,
    DROP COLUMN shape_leng,
    DROP COLUMN shape_area;

ALTER TABLE hk_district
    ADD COLUMN district_code text,
    ADD COLUMN district_area double precision,
    ADD COLUMN centroid geometry(Point, 2326);

CREATE TEMP TABLE district_csv (
    district_id integer PRIMARY KEY,
    district_code text,
    district_name text,
    district_area double precision,
    centroid text
);

\copy district_csv FROM 'sql_ready_csv/hk_district.csv' WITH (FORMAT csv, HEADER true, ENCODING 'UTF8')

UPDATE hk_district AS d
SET
    district_code = c.district_code,
    district_name = c.district_name,
    district_area = c.district_area,
    centroid = ST_GeomFromText(NULLIF(c.centroid, ''), 2326)
FROM district_csv AS c
WHERE d.district_id = c.district_id;

ALTER TABLE hk_district
    ALTER COLUMN district_code SET NOT NULL,
    ALTER COLUMN district_area SET NOT NULL;

ALTER TABLE hk_district
    ADD CONSTRAINT hk_district_id_positive
        CHECK (district_id > 0),
    ADD CONSTRAINT district_code_not_blank
        CHECK (btrim(district_code) <> ''),
    ADD CONSTRAINT district_code_format
        CHECK (district_code ~ '^[a-z][a-z0-9_]*$'),
    ADD CONSTRAINT district_name_not_blank
        CHECK (btrim(district_name) <> ''),
    ADD CONSTRAINT district_geom_not_empty
        CHECK (NOT ST_IsEmpty(geometry_shape)),
    ADD CONSTRAINT district_geom_valid
        CHECK (ST_IsValid(geometry_shape)),
    ADD CONSTRAINT district_area_nonnegative
        CHECK (district_area >= 0),
    ADD CONSTRAINT district_centroid_not_empty
        CHECK (centroid IS NULL OR NOT ST_IsEmpty(centroid));

CREATE INDEX hk_district_geom_gix
    ON hk_district USING gist (geometry_shape);

-- facility_type
-- type_id is supplied by facility_type.csv (1..8, A-Z by type_code), so it is
-- an ordinary integer PK rather than an IDENTITY column.
CREATE TABLE facility_type (
    type_id integer PRIMARY KEY,

    type_code text NOT NULL UNIQUE,

    type_name text NOT NULL,

    CONSTRAINT facility_type_id_positive
        CHECK (type_id > 0),

    CONSTRAINT facility_type_code_format
        CHECK (type_code ~ '^[a-z][a-z0-9_]*$'),

    CONSTRAINT facility_type_name_not_blank
        CHECK (btrim(type_name) <> '')
);

    \copy facility_type (type_id, type_code, type_name) FROM 'sql_ready_csv/facility_type.csv' WITH (FORMAT csv, HEADER true, ENCODING 'UTF8')

-- facility
-- facility_id is NOT in facility.csv: it stays an IDENTITY column and is
-- generated on import. facility.csv also carries latitude / longitude helper
-- columns that are derived here by the facility_coordinates view instead.
-- The source_name / source_record_id provenance columns were removed: the
-- cleaned data set does not provide them.
CREATE TABLE facility (
    facility_id integer GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    facility_name text NOT NULL,

    type_id integer NOT NULL
        REFERENCES facility_type (type_id)
        ON DELETE RESTRICT,

    district_id integer NOT NULL
        REFERENCES hk_district (district_id)
        ON DELETE RESTRICT,

    address text,

    coordinate_hk80 geometry(Point, 2326) NOT NULL,

    unit_count integer,

    CONSTRAINT facility_name_not_blank
        CHECK (btrim(facility_name) <> ''),

    CONSTRAINT facility_unit_count_nonnegative
        CHECK (unit_count >= 0),

    CONSTRAINT facility_coordinate_not_empty
        CHECK (NOT ST_IsEmpty(coordinate_hk80))
);

CREATE INDEX facility_type_idx
    ON facility (type_id);

CREATE INDEX facility_district_idx
    ON facility (district_id);

CREATE INDEX facility_geom_gix
    ON facility USING gist (coordinate_hk80);

-- district_population
-- One row per district. The cleaned data has no dataset_id / reference year,
-- so the statistical_dataset table and its FK are dropped; the snapshot's
-- source and year are documented externally.
-- All three counts are NOT NULL in the data set.
CREATE TABLE district_population (
    district_id integer PRIMARY KEY
        REFERENCES hk_district (district_id)
        ON DELETE RESTRICT,

    total_population integer NOT NULL,
    male_population integer NOT NULL,
    female_population integer NOT NULL,

    CONSTRAINT total_population_nonnegative
        CHECK (total_population >= 0),

    CONSTRAINT male_population_nonnegative
        CHECK (male_population >= 0),

    CONSTRAINT female_population_nonnegative
        CHECK (female_population >= 0)
);

    \copy district_population (district_id, total_population, male_population, female_population) FROM 'sql_ready_csv/district_population.csv' WITH (FORMAT csv, HEADER true, ENCODING 'UTF8')

-- population_age
-- district_id / age_band / population, with the age band label stored directly.
-- The age_band lookup table is dropped: the data already uses these 5 labels.
CREATE TABLE population_age (
    district_id integer NOT NULL
        REFERENCES hk_district (district_id)
        ON DELETE RESTRICT,

    age_band text NOT NULL,

    population integer NOT NULL,

    PRIMARY KEY (district_id, age_band),

    CONSTRAINT age_band_allowed
        CHECK (age_band IN ('<15', '15-24', '25-44', '45-64', '65+')),

    CONSTRAINT age_population_nonnegative
        CHECK (population >= 0)
);

    \copy population_age (district_id, age_band, population) FROM 'sql_ready_csv/population_age.csv' WITH (FORMAT csv, HEADER true, ENCODING 'UTF8')

-- working_income
-- district_id / income_band / worker_count. The income band label is the
-- cleaned slug used by the data set, so the income_band lookup table is
-- dropped. The bands describe the monthly income from main employment,
-- excluding foreign domestic helpers and unpaid family workers.
CREATE TABLE working_income (
    district_id integer NOT NULL
        REFERENCES hk_district (district_id)
        ON DELETE RESTRICT,

    income_band text NOT NULL,

    worker_count integer NOT NULL,

    PRIMARY KEY (district_id, income_band),

    CONSTRAINT income_band_allowed
        CHECK (
            income_band IN (
                'income_under_6000',
                'income_6000_9999',
                'income_10000_19999',
                'income_20000_29999',
                'income_30000_39999',
                'income_40000_59999',
                'income_60000_and_over'
            )
        ),

    CONSTRAINT worker_count_nonnegative
        CHECK (worker_count >= 0)
);

\copy working_income (district_id, income_band, worker_count) FROM 'sql_ready_csv/working_income.csv' WITH (FORMAT csv, HEADER true, ENCODING 'UTF8')

CREATE TEMP TABLE facility_csv (
    facility_name text,
    type_id integer,
    district_id integer,
    address text,
    coordinate_hk80 text,
    unit_count numeric,
    coordinate_wgs84 text,
    latitude double precision,
    longitude double precision,

    CHECK (unit_count = trunc(unit_count))
);

\copy facility_csv FROM 'sql_ready_csv/facility.csv' WITH (FORMAT csv, HEADER true, ENCODING 'UTF8')

INSERT INTO facility (
    facility_name,
    type_id,
    district_id,
    address,
    coordinate_hk80,
    unit_count
)
SELECT
    facility_name,
    type_id,
    district_id,
    address,
    ST_GeomFromText(coordinate_hk80, 2326),
    unit_count::integer
FROM facility_csv;

-- Views
-- district_area / centroid are stored columns on hk_district, so the summary
-- view reports the stored values next to the recalculated ones.
CREATE VIEW district_spatial_summary AS
SELECT
    district_id,
    district_code,
    district_name,

    district_area AS stored_area_km2,
    centroid AS stored_centroid_hk80,

    ST_Area(geometry_shape) AS calculated_area_m2,

    ST_Area(geometry_shape) / 1000000.0 AS calculated_area_km2,

    ST_Centroid(geometry_shape) AS calculated_centroid_hk80,

    ST_PointOnSurface(geometry_shape) AS label_point_hk80
FROM hk_district;

-- WGS84 is derived from coordinate_hk80, not stored a second time.
CREATE VIEW facility_coordinates AS
SELECT
    facility_id,
    facility_name,

    ST_X(coordinate_hk80) AS easting,
    ST_Y(coordinate_hk80) AS northing,

    ST_Transform(coordinate_hk80, 4326)::geometry(Point, 4326)
        AS geom_wgs84,

    ST_X(ST_Transform(coordinate_hk80, 4326)) AS longitude,
    ST_Y(ST_Transform(coordinate_hk80, 4326)) AS latitude
FROM facility;

CREATE VIEW facility_details AS
SELECT
    f.facility_id,
    f.facility_name,
    t.type_code,
    t.type_name,
    d.district_code,
    d.district_name,
    f.address,
    f.unit_count,
    f.coordinate_hk80
FROM facility AS f
JOIN facility_type AS t
    ON t.type_id = f.type_id
JOIN hk_district AS d
    ON d.district_id = f.district_id;

COMMIT;
