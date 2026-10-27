pgsql
CREATE DATABASE lsgi3245_fp;
\c lsgi3245_fp
CREATE EXTENSION IF NOT EXISTS postgis;


CMD.exe 
set "PATH=C:\Program Files\PostgreSQL\17\bin;%PATH%"
shp2pgsql -s 4326:2326 -I -g geometry_shape ".\Hk18shp\HkDistrict18.shp" hk_district > district_import.sql
psql -h localhost -U postgres -d lsgi3245_fp -v ON_ERROR_STOP=1 -f .\district_import.sql

pgsql
CREATE TABLE hk_district_before_fix AS
SELECT * FROM hk_district;

BEGIN;

UPDATE hk_district
SET geometry_shape =
    ST_Multi(
        ST_CollectionExtract(
            ST_MakeValid(geometry_shape),
            3
        )
    )
WHERE NOT ST_IsValid(geometry_shape);

COMMIT;
```

The repair corrects the source SRID, extracts polygon components, fixes
invalid geometries, converts them to `MULTIPOLYGON`, and transforms them to
EPSG:2326. Drop `hk_district_before_fix` after verifying the result.

pgsql
BEGIN;

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

COMMIT;

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

CREATE TABLE facility (
    facility_id integer GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    facility_name text NOT NULL,
    type_id integer NOT NULL
        REFERENCES facility_type(type_id) ON DELETE RESTRICT,
    district_id integer NOT NULL
        REFERENCES hk_district(district_id) ON DELETE RESTRICT,
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

CREATE INDEX facility_type_idx ON facility(type_id);
CREATE INDEX facility_district_idx ON facility(district_id);
CREATE INDEX facility_geom_gix
    ON facility USING gist(coordinate_hk80);


CREATE TABLE district_population (
    district_id integer PRIMARY KEY
        REFERENCES hk_district(district_id) ON DELETE RESTRICT,
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


CREATE TABLE population_age (
    district_id integer NOT NULL
        REFERENCES hk_district(district_id) ON DELETE RESTRICT,
    age_band text NOT NULL,
    population integer NOT NULL,

    PRIMARY KEY (district_id, age_band),

    CONSTRAINT age_band_allowed
        CHECK (age_band IN ('<15', '15-24', '25-44', '45-64', '65+')),
    CONSTRAINT age_population_nonnegative
        CHECK (population >= 0)
);


CREATE TABLE working_income (
    district_id integer NOT NULL
        REFERENCES hk_district(district_id) ON DELETE RESTRICT,
    income_band text NOT NULL,
    worker_count integer NOT NULL,

    PRIMARY KEY (district_id, income_band),

    CONSTRAINT income_band_allowed
        CHECK (income_band IN (
            'income_under_6000',
            'income_6000_9999',
            'income_10000_19999',
            'income_20000_29999',
            'income_30000_39999',
            'income_40000_59999',
            'income_60000_and_over'
        )),
    CONSTRAINT worker_count_nonnegative
        CHECK (worker_count >= 0)
);

\copy district_population (district_id, total_population, male_population, female_population) FROM 'sql_ready_csv/district_population.csv' WITH (FORMAT csv, HEADER true, ENCODING 'UTF8')

\copy population_age (district_id, age_band, population) FROM 'sql_ready_csv/population_age.csv' WITH (FORMAT csv, HEADER true, ENCODING 'UTF8')

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