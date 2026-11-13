-- patch_v1.sql

BEGIN;

-- Fail loudly on a repeat run instead of half-applying the patch.
DO $$
BEGIN
    IF to_regclass('public.hk_admin') IS NOT NULL
       AND to_regclass('public.district') IS NULL THEN
        RAISE EXCEPTION
            'patch_v1 already applied: public.hk_admin exists, public.district does not';
    END IF;

    IF to_regclass('public.district') IS NULL THEN
        RAISE EXCEPTION
            'patch_v1 cannot run: public.district does not exist';
    END IF;

    IF to_regclass('public.district_population') IS NULL THEN
        RAISE EXCEPTION
            'patch_v1 cannot run: public.district_population does not exist';
    END IF;
END
$$;

-- 1. Tables. Foreign keys keep pointing at the renamed table (same OID), and
--    PostgreSQL updates their displayed definition automatically.
ALTER TABLE public.district RENAME TO hk_admin;

ALTER TABLE public.district_population RENAME TO census;

-- 2. Indexes.
ALTER INDEX public.district_geom_gix RENAME TO hk_admin_geom_gix;

-- shp2pgsql -I created this second GiST index on the imported shapefile, so it
-- only exists in instances built with the shapefile import step.
DO $$
BEGIN
    IF to_regclass('public.district_geometry_shape_idx') IS NOT NULL THEN
        ALTER INDEX public.district_geometry_shape_idx
            RENAME TO hk_admin_geometry_shape_idx;
    END IF;
END
$$;

-- 3. Constraints of hk_admin (formerly district).
ALTER TABLE public.hk_admin
    RENAME CONSTRAINT district_pkey TO hk_admin_pkey;

ALTER TABLE public.hk_admin
    RENAME CONSTRAINT district_id_positive TO hk_admin_id_positive;

ALTER TABLE public.hk_admin
    RENAME CONSTRAINT district_code_not_blank TO hk_admin_code_not_blank;

ALTER TABLE public.hk_admin
    RENAME CONSTRAINT district_code_format TO hk_admin_code_format;

ALTER TABLE public.hk_admin
    RENAME CONSTRAINT district_name_not_blank TO hk_admin_name_not_blank;

ALTER TABLE public.hk_admin
    RENAME CONSTRAINT district_geom_not_empty TO hk_admin_geom_not_empty;

ALTER TABLE public.hk_admin
    RENAME CONSTRAINT district_geom_valid TO hk_admin_geom_valid;

ALTER TABLE public.hk_admin
    RENAME CONSTRAINT district_area_nonnegative TO hk_admin_area_nonnegative;

ALTER TABLE public.hk_admin
    RENAME CONSTRAINT district_centroid_not_empty TO hk_admin_centroid_not_empty;

-- 4. Constraints of census (formerly district_population). The three
--    *_population_nonnegative check names are generic and stay as they are.
ALTER TABLE public.census
    RENAME CONSTRAINT district_population_pkey TO census_pkey;

ALTER TABLE public.census
    RENAME CONSTRAINT district_population_district_id_fkey TO census_district_id_fkey;

COMMIT;

-- 5. Verification. Expect no row for district / district_population.
SELECT c.relname, c.relkind
FROM pg_class AS c
JOIN pg_namespace AS n ON n.oid = c.relnamespace
WHERE n.nspname = 'public'
  AND c.relname IN ('district', 'district_population')
ORDER BY c.relname;

-- Renamed relations: 9 tables/views, including hk_admin and census.
SELECT c.relname, c.relkind
FROM pg_class AS c
JOIN pg_namespace AS n ON n.oid = c.relnamespace
WHERE n.nspname = 'public'
  AND c.relkind IN ('r', 'v')
ORDER BY c.relname;

-- Row counts: hk_admin 18, census 18, facility 774, population_age 90,
-- working_income 126.
SELECT 'hk_admin' AS tbl, count(*) FROM hk_admin
UNION ALL SELECT 'census', count(*) FROM census
UNION ALL SELECT 'facility', count(*) FROM facility
UNION ALL SELECT 'population_age', count(*) FROM population_age
UNION ALL SELECT 'working_income', count(*) FROM working_income;

-- The views must still resolve after the rename: 18 and 774.
SELECT count(*) AS districts FROM district_spatial_summary;
SELECT count(*) AS facilities FROM facility_details;

-- Remaining constraint names after the patch.
SELECT conrelid::regclass AS tbl, conname
FROM pg_constraint
WHERE connamespace = 'public'::regnamespace
  AND conrelid IN ('public.hk_admin'::regclass, 'public.census'::regclass)
ORDER BY 1, 2;
