# Initial database setup for LSGI3245-FinalProject

Builds the `lsgi3245_fp` database (PostgreSQL 17 + PostGIS) from the HKDistrict18
shapefile and the cleaned CSV extracts.

## 1. Prerequisites

| Item | Value |
| --- | --- |
| PostgreSQL | 17, its `bin` directory added to `PATH` (supplies `psql` and `shp2pgsql`) |
| Extension | PostGIS 3.x |
| Spatial reference | district polygons in `EPSG:2326` (HK1980 Grid); source shapefile in `EPSG:4326` |
| Working directory | this folder (`initialize_database\`) — required. |

```bat
cd initialize_database
set "PATH=C:\Program Files\PostgreSQL\17\bin;%PATH%"
```

Inputs:

| File | Purpose | Rows |
| --- | --- | --- |
| `HK18shp\HKDistrict18.shp` (plus `.dbf`, `.shx`, `.prj`, `.cpg`) | district polygons → table `hk_admin`, WGS84 per `.prj`, UTF-8 | 18 |
| `sql_ready_csv\hk_district.csv` | district code, area, centroid for `hk_admin` | 18 |
| `sql_ready_csv\facility_type.csv` | facility type lookup | 8 |
| `sql_ready_csv\facility.csv` | facilities with EPSG:2326 and EPSG:4326 coordinates | 774 |
| `sql_ready_csv\district_population.csv` | population totals, loaded into table `census` | 18 |
| `sql_ready_csv\population_age.csv` | five age bands per district | 90 |
| `sql_ready_csv\working_income.csv` | seven income bands per district | 126 |

## 2. Create the database and enable PostGIS

`CREATE DATABASE` cannot run inside a transaction block, so issue it on its own.

```bat
psql -h localhost -U postgres -d postgres -v ON_ERROR_STOP=1 ^
     -c "CREATE DATABASE lsgi3245_fp;"

psql -h localhost -U postgres -d lsgi3245_fp -v ON_ERROR_STOP=1 ^
     -c "CREATE EXTENSION IF NOT EXISTS postgis;"
```

## 3. Import the HKDistrict18 polygons into `hk_admin` with `shp2pgsql`

`-s 4326:2326` declares the source SRID (matching `HKDistrict18.prj` = WGS84) and
reprojects to HK1980 Grid during import; `-I` creates a GiST index; `-g geometry_shape`
names the geometry column used by every later step. The target table is `hk_admin`
(HKDistrict18 administrative areas); `schema.sql` expects exactly that name. The
shapefile contains degenerate zero-area rings (4-vertex slivers up to ~3 m across, first
vertex repeated last) in five districts — SAI KUNG, NORTH, TUEN MUN, SOUTHERN and
ISLANDS — which make `ST_IsValid` fail; `schema.sql` collapses them before adding the
validity constraint.

```bat
shp2pgsql -s 4326:2326 -I -g geometry_shape ^
    ".\HK18shp\HKDistrict18.shp" hk_admin > hk_admin_import.sql

psql -h localhost -U postgres -d lsgi3245_fp -v ON_ERROR_STOP=1 -f .\hk_admin_import.sql
```

## 4. Build the attribute schema and load the CSVs

[schema.sql](./schema.sql) is the consolidated version of the remaining steps. Inside a
single `BEGIN … COMMIT` it:

- renames and retypes the imported columns (`id` → `district_id`, `ename` → `district_name`);
- drops the leftover shapefile columns (`gid`, `objectid`, `cname`, `cname_s`, `shape_leng`, `shape_area`);
- adds `district_code`, `district_area` and `centroid`, repairs the invalid imported polygons, then applies `NOT NULL`, CHECK constraints and the GiST index;
- creates `facility_type`, `facility`, `census`, `population_age` and `working_income`;
- loads every CSV, then creates the `district_spatial_summary`, `facility_coordinates` and `facility_details` views.

Column names such as `district_id` are shared by every table (and by `NATURAL JOIN`), so
the two renamed tables are `district` → `hk_admin` and `district_population` → `census`
while their columns keep their names.

```bat
psql -h localhost -U postgres -d lsgi3245_fp -v ON_ERROR_STOP=1 -f .\schema.sql
```

Load order is FK-safe: `hk_admin` → `facility_type` → `facility` →
`census` → `population_age` → `working_income`. The CSV file names keep the
`district_population` prefix even though the table is `census`. `facility.csv` is staged in
the temporary table `facility_csv` and inserted with
`ST_GeomFromText(coordinate_hk80, 2326)` and `ST_GeomFromText(coordinate_wgs84, 4326)`.
Both coordinate systems come straight from the CSV and are never recalculated, and
`unit_count` may be empty.

## 5. Verify

```sql
SELECT 'hk_admin' AS tbl, count(*) FROM hk_admin
UNION ALL SELECT 'facility_type', count(*) FROM facility_type
UNION ALL SELECT 'facility', count(*) FROM facility
UNION ALL SELECT 'census', count(*) FROM census
UNION ALL SELECT 'population_age', count(*) FROM population_age
UNION ALL SELECT 'working_income', count(*) FROM working_income;
-- 18 | 8 | 774 | 18 | 90 | 126
```

```sql
-- every district must have population, age and income rows
SELECT d.district_id
FROM hk_admin AS d
LEFT JOIN census AS p USING (district_id)
LEFT JOIN population_age AS a USING (district_id)
LEFT JOIN working_income AS w USING (district_id)
WHERE p.district_id IS NULL
   OR a.district_id IS NULL
   OR w.district_id IS NULL;
-- expect 0 rows

-- spatial sanity
SELECT postgis_full_version();
SELECT * FROM district_spatial_summary ORDER BY district_id LIMIT 3;
SELECT * FROM facility_coordinates LIMIT 5;

-- stored area should agree with the geometry area
SELECT district_code, stored_area_km2, calculated_area_km2
FROM district_spatial_summary
WHERE abs(stored_area_km2 - calculated_area_km2) > 0.01 * stored_area_km2;
```

## 6. Updating an existing instance

A database built before the rename (`district`, `district_population`) is updated in
place by [`../sql/patch_v1.sql`](../sql/patch_v1.sql); no reload is needed.

```bat
psql -h localhost -U postgres -d lsgi3245_fp -v ON_ERROR_STOP=1 -f ..\sql\patch_v1.sql
```

The patch renames the tables to `hk_admin` and `census`, renames the indexes, primary
keys, foreign key and `district_*` CHECK constraints that carry the old name, and keeps
all column names — so `district_id` and the `NATURAL JOIN` examples still work. A fresh
import from this folder needs no patch, and `sql/lsgi3245_backup.*` should be re-dumped
afterwards so the dump matches the instance.