import pandas as pd
import geopandas as gpd
import os
from functools import lru_cache
from pyproj import Transformer


# CONFIG
DATA_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
RAW_DATA_DIR = os.path.join(DATA_DIR, 'raw')
CLEAN_DATA_DIR = os.path.join(DATA_DIR, 'cleaned')
STAGE_PRE_CLEAN_DATA_DIR = os.path.join(CLEAN_DATA_DIR, 'stage_pre_clean')
STAGE_SQL_READY_DATA_DIR = os.path.join(CLEAN_DATA_DIR, 'stage_sql_ready')
CALL_CENSUS_CLEANING = True

# HKDistrict18 is the authoritative district boundary layer. Every facility
# district is recalculated from its point coordinates against this layer
# instead of trusting the (sometimes wrong / non-district) source value.
DISTRICT_SHP_PATH = os.path.join(RAW_DATA_DIR, 'HK18shp', 'HKDistrict18.shp')
WGS84_CRS = 'EPSG:4326'   # latitude / longitude
HK1980_CRS = 'EPSG:2326'  # northing / easting
# Points that fall just outside every district polygon (e.g. a waterfront
# site) are assigned to the nearest district within this distance.
NEAREST_DISTRICT_MAX_DISTANCE_M = 100

# Pre-file Config
# Whitelist of columns kept per raw CSV, mapped to their cleaned names.
# Generally, these are dropped.
#   1. All Traditional Chinese columns (suffix _TC / *TC)
#   2. Website columns (NSEARCH06_* / WebsiteEN+WebsiteTC)
#   3. Contact information columns (NSEARCH03_* / NSEARCH04_* / NSEARCH05_*)
#   4. Duplicated geo information (Geometry_*) - It AVOID confusion and mismatch when someone pick WRONG coloum.
KEEP_COLS_MAP = {
    "badminton_courts.csv": {
        #"DATASET_EN": "dataset", It is broken. Discard.
        "NAME_EN": "facility_name",
        "LATITUDE": "latitude",
        "LONGITUDE": "longitude",
        "NORTHING": "northing",
        "EASTING": "easting",
        "SEARCH02_EN": "facility_type",
        "SEARCH01_EN": "district",
        "ADDRESS_EN": "address",
        # "NSEARCH01_EN": "facility_details", Too many different values can cannot be unified. Discard.
        # "NSEARCH02_EN": "opening_hours", Too many missing values. Discard.
        "No__of_Badminton_Courts_EN": "unit_count",
    },
    "basketball_courts.csv": {
        # "DATASET_EN": "dataset", Discard.
        "NAME_EN": "facility_name",
        "LATITUDE": "latitude",
        "LONGITUDE": "longitude",
        "NORTHING": "northing",
        "EASTING": "easting",
        "SEARCH02_EN": "facility_type",
        "SEARCH01_EN": "district",
        "ADDRESS_EN": "address",
        # "NSEARCH01_EN": "facility_details",
        # "NSEARCH02_EN": "opening_hours", Too many N.A. values.
        "No__of_Basketball_Courts_EN": "unit_count",
    },
    "tennis_courts.csv": {
        # "DATASET_EN": "dataset", Discard.
        "NAME_EN": "facility_name",
        "LATITUDE": "latitude",
        "LONGITUDE": "longitude",
        "NORTHING": "northing",
        "EASTING": "easting",
        "SEARCH02_EN": "facility_type",
        "SEARCH01_EN": "district",
        "ADDRESS_EN": "address",
        # "NSEARCH01_EN": "facility_details",
        # "NSEARCH02_EN": "opening_hours",
        "No__of_Tennis_Courts_EN": "unit_count",
    },
    "fitness_rooms.csv": {
        # "DATASET_EN": "dataset", Discard.
        "NameEN": "facility_name",
        "LATITUDE": "latitude",
        "LONGITUDE": "longitude",
        "NORTHING": "northing",
        "EASTING": "easting",
        "FacilityTypeEN": "facility_type",
        "DistrictEN": "district",
        "AddressEN": "address",
        # "FacilityDetailsEN": "facility_details",
        # "OpeningHoursEN": "opening_hours",
    },
    "parks_zoos_and_gardens.csv": {
        # "DATASET_EN": "dataset", Discard.
        "NameEN": "facility_name",
        "LATITUDE": "latitude",
        "LONGITUDE": "longitude",
        "NORTHING": "northing",
        "EASTING": "easting",
        "FacilityTypeEN": "facility_type",
        "DistrictEN": "district",
        "AddressEN": "address",
        # "FacilityDetailsEN": "facility_details",
        # "OpeningHoursEN": "opening_hours",
    },
    "swimming_pools.csv": {
        # "DATASET_EN": "dataset", Discard.
        "NameEN": "facility_name",
        "LATITUDE": "latitude",
        "LONGITUDE": "longitude",
        "NORTHING": "northing",
        "EASTING": "easting",
        "FacilityTypeEN": "facility_type",
        "DistrictEN": "district",
        "AddressEN": "address",
        # "FacilityDetailsEN": "facility_details",
        # "OpeningHoursEN": "opening_hours",
    },
    "country_parks.csv": {
        # "DATASET_EN": "dataset", Discard.
        "NAME_EN": "facility_name",
        "GeometryNorthing": "northing",
        "GeometryEasting": "easting",
        # district is recalculated from the coordinates (see assign_district).
    },
    "sports_grounds.csv": {
        # "DATASET_EN": "dataset", Discard.
        "NAME_EN": "facility_name",
        "LATITUDE": "latitude",
        "LONGITUDE": "longitude",
        "NORTHING": "northing",
        "EASTING": "easting",
        "SEARCH02_EN": "facility_type",
        "SEARCH01_EN": "district",
        "ADDRESS_EN": "address",
        # "NSEARCH01_EN": "facility_details",
        # "NSEARCH02_EN": "opening_hours",
        # "Premises_based_EN": "premises_based", Useless in geo-analysis. Discard.
        # "Site_area__sq__m____EN": "site_area_sq_m", May useless. Discard.
        # "Status_of_facilities_EN": "status_of_facilities", WTF is this column? All are Existing. Discard.
    },
}

DISTRICT_NAME_FIX_MAP = {
    'CENTRAL AND WESTERN': 'CENTRAL & WESTERN',
}

CANONICAL_DISTRICT_NAMES = {
    'WONG TAI SIN',
    'KOWLOON CITY',
    'KWUN TONG',
    'SAI KUNG',
    'NORTH',
    'CENTRAL & WESTERN',
    'WAN CHAI',
    'EASTERN',
    'TUEN MUN',
    'YUEN LONG',
    'SOUTHERN',
    'ISLANDS',
    'SHAM SHUI PO',
    'YAU TSIM MONG',
    'KWAI TSING',
    'TSUEN WAN',
    'TAI PO',
    'SHA TIN',
}

# district_code is a slug derived from the (normalized) district name, so it
# satisfies sql/schema.sql: CHECK (district_code ~ '^[a-z][a-z0-9_]*$').
# Keep one entry per CANONICAL_DISTRICT_NAMES value.
DISTRICT_CODE_MAP = {
    'WONG TAI SIN': 'wong_tai_sin',
    'KOWLOON CITY': 'kowloon_city',
    'KWUN TONG': 'kwun_tong',
    'SAI KUNG': 'sai_kung',
    'NORTH': 'north',
    'CENTRAL & WESTERN': 'central_and_western',
    'WAN CHAI': 'wan_chai',
    'EASTERN': 'eastern',
    'TUEN MUN': 'tuen_mun',
    'YUEN LONG': 'yuen_long',
    'SOUTHERN': 'southern',
    'ISLANDS': 'islands',
    'SHAM SHUI PO': 'sham_shui_po',
    'YAU TSIM MONG': 'yau_tsim_mong',
    'KWAI TSING': 'kwai_tsing',
    'TSUEN WAN': 'tsuen_wan',
    'TAI PO': 'tai_po',
    'SHA TIN': 'sha_tin',
}

def load_csv(file_path):
    """
    Loads a CSV file into a pandas DataFrame.
    file_path: str, path to the CSV file
    returns: pandas.DataFrame
    """
    return pd.read_csv(file_path)

def save_csv(df, file_path):
    """
    Saves a pandas DataFrame to a CSV file.
    df: pandas.DataFrame, the DataFrame to save
    file_path: str, path to the CSV file
    """
    df.to_csv(file_path, index=False)


def hk1980_to_wgs84(easting, northing):
    """
    Converts HK1980 Grid (EPSG:2326) coordinates to WGS84 (EPSG:4326).
    easting, northing: pandas.Series or array-like of numbers
    returns: (latitude, longitude) as numpy arrays
    """
    transformer = Transformer.from_crs(
        HK1980_CRS,
        WGS84_CRS,
        always_xy=True,
    )
    longitude, latitude = transformer.transform(
        pd.to_numeric(easting),
        pd.to_numeric(northing),
    )
    return latitude, longitude


def add_wgs84_coordinates(df):
    """
    Derives latitude / longitude (WGS84) from northing / easting (HK1980).
    df: pandas.DataFrame with northing / easting columns
    returns: pandas.DataFrame
    """
    latitude, longitude = hk1980_to_wgs84(df['easting'], df['northing'])
    df.insert(1, 'latitude', latitude)
    df.insert(2, 'longitude', longitude)
    return df


def ensure_wgs84_coordinates(df):
    """
    Adds latitude / longitude only when the source provides grid coordinates
    but no WGS84 coordinates.
    df: pandas.DataFrame
    returns: pandas.DataFrame
    """
    if 'latitude' in df.columns and 'longitude' in df.columns:
        return df
    return add_wgs84_coordinates(df)


def normalize_district_values(series):
    normalized = series.copy()
    non_null_mask = normalized.notna()
    normalized.loc[non_null_mask] = (
        normalized.loc[non_null_mask]
        .astype(str)
        .str.strip()
        .str.upper()
        .replace(DISTRICT_NAME_FIX_MAP)
    )
    return normalized


def warn_if_district_mismatch(series, dataframe_name):
    normalized = normalize_district_values(series).dropna()
    normalized = normalized[(normalized != '') & (normalized != 'NAN')]
    mismatched = sorted(set(normalized) - CANONICAL_DISTRICT_NAMES)
    if mismatched:
        print(
            f"Warning: {dataframe_name} has district names not in "
            f"HKDistrict18 ENAME: {mismatched}"
        )


@lru_cache(maxsize=1)
def load_district_geodataframe():
    """
    Loads the HKDistrict18 boundaries with `district` and `district_id`.
    Cached because every dataset is joined against the same layer.
    `district_id` is the shapefile feature ID (ID) and is the authoritative
    hk_district primary key used across all SQL-ready tables.
    returns: geopandas.GeoDataFrame in WGS84
    """
    districts = gpd.read_file(DISTRICT_SHP_PATH)
    districts = (
        districts.loc[:, ['ID', 'ENAME', 'geometry']]
        .rename(columns={'ENAME': 'district', 'ID': 'district_id'})
    )
    districts['district_id'] = districts['district_id'].astype(int)
    districts['district'] = normalize_district_values(districts['district'])
    districts = districts.sort_values('district_id')
    return districts.to_crs(WGS84_CRS)


@lru_cache(maxsize=1)
def district_ids_by_name():
    """
    Mapping of normalized district name to HKDistrict18 district_id.
    returns: pandas.Series indexed by district name
    """
    districts = load_district_geodataframe()
    return pd.Series(
        districts['district_id'].to_numpy(),
        index=districts['district'].to_numpy(),
    )


def district_code_from_name(series):
    """
    Maps district names to their district_code slug.
    Names are normalized first, so 'Central and Western' also resolves.
    series: pandas.Series of district names
    returns: pandas.Series of district_code values
    """
    normalized = normalize_district_values(series)
    codes = normalized.map(DISTRICT_CODE_MAP)
    missing = sorted(set(normalized[codes.isna() & normalized.notna()]))
    if missing:
        raise ValueError(
            f"No district_code mapping for district name(s): {missing}"
        )
    return codes


def nearest_district_names(points):
    """
    Assigns the nearest district to points that fall outside every district
    polygon, within NEAREST_DISTRICT_MAX_DISTANCE_M metres.
    points: geopandas.GeoDataFrame in WGS84
    returns: pandas.Series of district names, indexed like `points`
    """
    districts = (
        load_district_geodataframe()
        .rename(columns={'district': 'district_calc'})
        .to_crs(HK1980_CRS)
    )
    nearest = gpd.sjoin_nearest(
        points.to_crs(HK1980_CRS),
        districts,
        how='left',
        max_distance=NEAREST_DISTRICT_MAX_DISTANCE_M,
    )
    # Ties can return several rows per point; keep one and restore alignment.
    nearest = nearest[~nearest.index.duplicated(keep='first')]
    return nearest.reindex(points.index)['district_calc']


def assign_district(df, dataframe_name):
    """
    Recalculates `district` for every facility by spatially joining its
    latitude / longitude against the HKDistrict18 boundaries. The district
    value from the source CSV is overwritten, so the output is consistent
    with the authoritative boundary layer.
    df: pandas.DataFrame with latitude / longitude columns
    dataframe_name: str, used in messages
    returns: pandas.DataFrame
    """
    source_district = (
        normalize_district_values(df['district'])
        if 'district' in df.columns
        else None
    )
    points = gpd.GeoDataFrame(
        df,
        geometry=gpd.points_from_xy(
            pd.to_numeric(df['longitude']),
            pd.to_numeric(df['latitude']),
        ),
        crs=WGS84_CRS,
    )
    districts = (
        load_district_geodataframe()
        .rename(columns={'district': 'district_calc'})
    )
    joined = gpd.sjoin(points, districts, how='left', predicate='within')
    joined = joined.drop(columns=['index_right'], errors='ignore')
    # A point can only be within one district, but guard against duplicates.
    joined = joined[~joined.index.duplicated(keep='first')].reindex(df.index)
    computed = joined['district_calc'].copy()

    outside = computed.isna()
    if outside.any():
        computed.loc[outside] = nearest_district_names(points.loc[outside])

    unresolved = computed.isna()
    if unresolved.any():
        print(
            f"Warning: {dataframe_name}: {int(unresolved.sum())} row(s) could not "
            f"be matched to a district within "
            f"{NEAREST_DISTRICT_MAX_DISTANCE_M} m"
        )

    if source_district is not None:
        changed = (
            computed.notna()
            & source_district.notna()
            & (computed != source_district)
        )
        if changed.any():
            print(
                f"Note: {dataframe_name}: {int(changed.sum())} district value(s) "
                f"recalculated from coordinates"
            )

    df['district'] = computed
    warn_if_district_mismatch(df['district'], dataframe_name)
    return df


# Output column order shared by all facility tables.
FACILITY_COLUMN_ORDER = [
    'facility_name',
    'latitude',
    'longitude',
    'northing',
    'easting',
    'facility_type',
    'district',
    'address',
    'unit_count',
]


def finalize_columns(df):
    """
    Puts the output columns in a consistent order. Columns the source dataset
    does not provide (e.g. `unit_count`) are not added.
    df: pandas.DataFrame
    returns: pandas.DataFrame
    """
    ordered = [col for col in FACILITY_COLUMN_ORDER if col in df.columns]
    remaining = [col for col in df.columns if col not in ordered]
    return df.loc[:, ordered + remaining]


def clean_badminton_courts():
    filename = 'badminton_courts.csv'
    df = load_csv(os.path.join(RAW_DATA_DIR, filename))
    df = rename_columns(df, filename)
    df = ensure_wgs84_coordinates(df)
    df = assign_district(df, filename)
    df = finalize_columns(df)
    # save_csv(df, os.path.join(STAGE_PRE_CLEAN_DATA_DIR, filename))
    return df


def clean_basketball_courts():
    filename = 'basketball_courts.csv'
    df = load_csv(os.path.join(RAW_DATA_DIR, filename))
    df = rename_columns(df, filename)
    df = ensure_wgs84_coordinates(df)
    df = assign_district(df, filename)
    df = finalize_columns(df)
    # save_csv(df, os.path.join(STAGE_PRE_CLEAN_DATA_DIR, filename))
    return df


def clean_tennis_courts():
    filename = 'tennis_courts.csv'
    df = load_csv(os.path.join(RAW_DATA_DIR, filename))
    df = rename_columns(df, filename)
    df = ensure_wgs84_coordinates(df)
    df = assign_district(df, filename)
    df = finalize_columns(df)
    # save_csv(df, os.path.join(STAGE_PRE_CLEAN_DATA_DIR, filename))
    return df


def clean_fitness_rooms():
    filename = 'fitness_rooms.csv'
    df = load_csv(os.path.join(RAW_DATA_DIR, filename))
    df = rename_columns(df, filename)
    df = ensure_wgs84_coordinates(df)
    df = assign_district(df, filename)
    df = finalize_columns(df)
    # save_csv(df, os.path.join(STAGE_PRE_CLEAN_DATA_DIR, filename))
    return df


def clean_parks_zoos_and_gardens():
    filename = 'parks_zoos_and_gardens.csv'
    df = load_csv(os.path.join(RAW_DATA_DIR, filename))
    df = rename_columns(df, filename)
    df = ensure_wgs84_coordinates(df)
    df = assign_district(df, filename)
    df = finalize_columns(df)
    # save_csv(df, os.path.join(STAGE_PRE_CLEAN_DATA_DIR, filename))
    return df


def clean_swimming_pools():
    filename = 'swimming_pools.csv'
    df = load_csv(os.path.join(RAW_DATA_DIR, filename))
    df = rename_columns(df, filename)
    df = ensure_wgs84_coordinates(df)
    df = assign_district(df, filename)
    df = finalize_columns(df)
    # save_csv(df, os.path.join(STAGE_PRE_CLEAN_DATA_DIR, filename))
    return df


def clean_country_parks():
    filename = 'country_parks.csv'
    df = load_csv(os.path.join(RAW_DATA_DIR, filename))
    df = rename_columns(df, filename)
    df = ensure_wgs84_coordinates(df)
    df = assign_district(df, filename)
    df = finalize_columns(df)
    # save_csv(df, os.path.join(STAGE_PRE_CLEAN_DATA_DIR, filename))
    return df


def clean_sports_grounds():
    filename = 'sports_grounds.csv'
    df = load_csv(os.path.join(RAW_DATA_DIR, filename))
    df = rename_columns(df, filename)
    df = ensure_wgs84_coordinates(df)
    df = assign_district(df, filename)
    df = finalize_columns(df)
    # save_csv(df, os.path.join(STAGE_PRE_CLEAN_DATA_DIR, filename))
    return df


def rename_columns(df, filename):
    """
    Keeps and renames whitelisted columns. Final column order is applied by
    `finalize_columns`.
    df: pandas.DataFrame
    filename: str, the name of the CSV file being processed
    returns: pandas.DataFrame
    """
    column_map = KEEP_COLS_MAP[filename]
    missing_columns = set(column_map) - set(df.columns)
    if missing_columns:
        raise ValueError(f"{filename}: missing expected columns: {sorted(missing_columns)}")

    return df.loc[:, list(column_map)].rename(columns=column_map)

def save_all_df(dataframes):
    """
    Saves all pre-cleaned dataframes to CSV files named after their variable
    names under STAGE_PRE_CLEAN_DATA_DIR.
    dataframes: mapping of variable names to pandas.DataFrame
    """
    for variable_name, df in dataframes.items():
        save_csv(df, os.path.join(STAGE_PRE_CLEAN_DATA_DIR, f'{variable_name}.csv'))


# Column order of the SQL-ready `facility` table (see sql/schema.sql).
FACILITY_TABLE_COLUMNS = [
    'facility_name',
    'type_id',
    'district_id',
    'address',
    'coordinate_hk80',
    'coordinate_wgs84',
    'unit_count',
]


# Column order of the SQL-ready `facility_type` table (see sql/schema.sql).
FACILITY_TYPE_TABLE_COLUMNS = ['type_id', 'type_code', 'type_name']

# Friendly display names for each source dataset. The dataset key is also the
# facility_type.type_code, which satisfies
# CHECK (type_code ~ '^[a-z][a-z0-9_]*$').
FACILITY_TYPE_NAMES = {
    'badminton_courts': 'Badminton Courts',
    'basketball_courts': 'Basketball Courts',
    'country_parks': 'Country Parks',
    'fitness_rooms': 'Fitness Rooms',
    'parks_zoos_and_gardens': 'Parks, Zoos and Gardens',
    'sports_grounds': 'Sports Grounds',
    'swimming_pools': 'Swimming Pools',
    'tennis_courts': 'Tennis Courts',
}


def build_facility_type_table():
    """
    Builds the SQL-ready `facility_type` table.

    One row per source dataset:
      - type_id   : 1..N, assigned in A-Z order of type_code, so ids are
                    stable and easy to read.
      - type_code : the dataset name (e.g. 'badminton_courts').
      - type_name : a friendly English name (e.g. 'Badminton Courts').

    returns: pandas.DataFrame
    """
    type_codes = sorted(FACILITY_TYPE_NAMES)
    table = pd.DataFrame({
        'type_id': pd.array(range(1, len(type_codes) + 1), dtype='Int64'),
        'type_code': type_codes,
        'type_name': [FACILITY_TYPE_NAMES[code] for code in type_codes],
    })
    return table.loc[:, FACILITY_TYPE_TABLE_COLUMNS]


def save_facility_type_table(type_df):
    """
    Saves the SQL-ready facility_type table to STAGE_SQL_READY_DATA_DIR.
    type_df: pandas.DataFrame from build_facility_type_table
    """
    save_csv(
        type_df, os.path.join(STAGE_SQL_READY_DATA_DIR, 'facility_type.csv')
    )


# Column order of the SQL-ready `hk_district` table (see sql/schema.sql).
# Only the attributes are exported; the boundary comes from the shapefile.
DISTRICT_TABLE_COLUMNS = [
    'district_id',
    'district_code',
    'district_name',
    'district_area',
    'centroid',
]


def build_facility_table(dataframes):
    """
    Builds the SQL-ready `facility` table from the pre-cleaned dataframes.

    The output mirrors sql/schema.sql:facility:
      - facility_id is omitted; PostgreSQL generates it.
      - district_id is filled from HKDistrict18.shp via the district name
        (see district_ids_by_name), so it matches hk_district.district_id.
      - type_id is the facility_type.type_id of the source dataset
        (see build_facility_type_table).
      - address is empty when the source dataset has no address.
      - coordinate_hk80 is the HK1980 Grid (EPSG:2326) point in WKT,
        built from the easting / northing columns.
      - coordinate_wgs84 is the WGS84 (EPSG:4326) point in WKT, in
        longitude latitude order, derived from coordinate_hk80.
      - unit_count is empty when the source dataset has no unit count.
        Latitude / longitude are not carried into this table: the location is
        stored as coordinate_hk80 / coordinate_wgs84 only.

    dataframes: mapping of dataset names to pandas.DataFrame
    returns: pandas.DataFrame
    """
    district_ids = district_ids_by_name()
    facility_types = build_facility_type_table()
    type_ids = facility_types.set_index('type_code')['type_id']

    unknown = sorted(set(dataframes) - set(type_ids.index))
    if unknown:
        raise ValueError(f"No facility_type entry for dataset(s): {unknown}")

    frames = []
    for dataset_name, df in dataframes.items():
        empty_ids = pd.array([pd.NA] * len(df), dtype='Int64')
        easting = pd.to_numeric(df['easting'], errors='coerce')
        northing = pd.to_numeric(df['northing'], errors='coerce')
        latitude, longitude = hk1980_to_wgs84(easting, northing)

        table = pd.DataFrame(index=df.index)
        table['facility_name'] = df['facility_name']
        table['type_id'] = int(type_ids[dataset_name])
        table['district_id'] = df['district'].map(district_ids).astype('Int64')
        table['address'] = df['address'] if 'address' in df.columns else pd.NA
        table['coordinate_hk80'] = [
            pd.NA if pd.isna(e) or pd.isna(n) else f'POINT({e} {n})'
            for e, n in zip(easting, northing)
        ]
        table['coordinate_wgs84'] = [
            pd.NA if pd.isna(lat) or pd.isna(lon) else f'POINT({lon} {lat})'
            for lat, lon in zip(latitude, longitude)
        ]
        if 'unit_count' in df.columns:
            table['unit_count'] = pd.array(df['unit_count'], dtype='Int64')
        else:
            table['unit_count'] = empty_ids
        frames.append(table)

    facility_df = pd.concat(frames, ignore_index=True)

    missing = facility_df.loc[facility_df['district_id'].isna(), 'facility_name']
    if not missing.empty:
        raise ValueError(
            f"{len(missing)} facility row(s) have no district_id, e.g. "
            f"{list(missing.head())}"
        )

    return facility_df.loc[:, FACILITY_TABLE_COLUMNS]


def save_facility_table(facility_df):
    """
    Saves the SQL-ready facility table to STAGE_SQL_READY_DATA_DIR.
    facility_df: pandas.DataFrame from build_facility_table
    """
    save_csv(facility_df, os.path.join(STAGE_SQL_READY_DATA_DIR, 'facility.csv'))


def build_district_table():
    """
    Builds the SQL-ready `hk_district` table from the HKDistrict18 shapefile.

    Output mirrors sql/schema.sql:hk_district:
      - district_id   : the shapefile feature ID (`ID`). This is the single
                        authoritative district key used by every SQL-ready
                        table, including the census tables.
      - district_code : slug derived from the district name via
                        DISTRICT_CODE_MAP (e.g. 'wong_tai_sin').
      - district_name : the shapefile `ENAME`, normalized to upper case.
      - district_area : polygon area in square kilometres, measured on the
                        EPSG:2326 (HK1980 Grid, metre) geometry.
      - centroid      : polygon centroid in EPSG:2326 as WKT.
    The boundary geometry itself is not exported; import it from the
    shapefile into `geometry_shape`.

    returns: pandas.DataFrame
    """
    districts = gpd.read_file(DISTRICT_SHP_PATH).to_crs(HK1980_CRS)
    districts['district_id'] = districts['ID'].astype(int)
    districts['district_name'] = normalize_district_values(districts['ENAME'])
    districts['district_code'] = district_code_from_name(districts['ENAME'])
    districts['district_area'] = districts.geometry.area / 1_000_000.0
    centroids = districts.geometry.centroid
    districts['centroid'] = [f'POINT({p.x} {p.y})' for p in centroids]

    districts = districts.sort_values('district_id')
    return districts.loc[:, DISTRICT_TABLE_COLUMNS].reset_index(drop=True)


def save_district_table(district_df):
    """
    Saves the SQL-ready hk_district table to STAGE_SQL_READY_DATA_DIR.
    district_df: pandas.DataFrame from build_district_table
    """
    save_csv(district_df, os.path.join(STAGE_SQL_READY_DATA_DIR, 'hk_district.csv'))


# ---------------------------------------------------------------------------
# Census-derived SQL-ready tables
# ---------------------------------------------------------------------------

# Column order of the SQL-ready `district_population` table.
DISTRICT_POPULATION_COLUMNS = [
    'district_id',
    'total_population',
    'male_population',
    'female_population',
]

# Column order of the SQL-ready `population_age` table.
POPULATION_AGE_COLUMNS = ['district_id', 'age_band', 'population']

# Column order of the SQL-ready `working_income` table.
WORKING_INCOME_COLUMNS = ['district_id', 'income_band', 'worker_count']

# Census pre-clean column -> population_age.age_band.
# Labels are the ones allowed by sql/schema.sql: population_age.age_band_allowed.
AGE_BAND_MAP = {
    'age_under_15': '<15',
    'age_15_24': '15-24',
    'age_25_44': '25-44',
    'age_45_64': '45-64',
    'age_65_plus': '65+',
}

# Census pre-clean column -> working_income.income_band.
# Labels are short slugs (no spaces) derived from the source column names, so
# they stay stable and easy to reference in SQL.
INCOME_BAND_MAP = {
    'employment_income_under_6000': 'income_under_6000',
    'employment_income_6000_9999': 'income_6000_9999',
    'employment_income_10000_19999': 'income_10000_19999',
    'employment_income_20000_29999': 'income_20000_29999',
    'employment_income_30000_39999': 'income_30000_39999',
    'employment_income_40000_59999': 'income_40000_59999',
    'employment_income_60000_plus': 'income_60000_and_over',
}


def require_columns(df, columns, table_name):
    """
    Ensures `columns` exist and hold no NULLs. Both are NOT NULL in the schema.
    df: pandas.DataFrame (census pre-clean)
    columns: iterable of column names
    table_name: str, used in the error message
    """
    missing = [col for col in columns if col not in df.columns]
    if missing:
        raise ValueError(f"{table_name}: missing census columns: {missing}")
    nulls = [col for col in columns if df[col].isna().any()]
    if nulls:
        raise ValueError(
            f"{table_name}: NULL values found in NOT NULL column(s): {nulls}"
        )


def require_unique(df, columns, table_name):
    """
    Ensures the combination of `columns` is unique (schema PRIMARY KEY).
    """
    duplicated = df.duplicated(subset=columns)
    if duplicated.any():
        raise ValueError(
            f"{table_name}: duplicate key {columns} in "
            f"{int(duplicated.sum())} row(s)"
        )


def melt_band_table(census_df, band_map, value_name, table_name):
    """
    Converts one row per district with one column per band into a long table
    keyed by (district_id, band). Shared by population_age and working_income.

    census_df: pandas.DataFrame (census pre-clean)
    band_map: dict of census column -> band label
    value_name: str, name of the measure column
    table_name: str, used in messages
    returns: pandas.DataFrame
    """
    band_columns = list(band_map)
    require_columns(census_df, ['district_id'] + band_columns, table_name)

    long_df = census_df.loc[:, ['district_id'] + band_columns].melt(
        id_vars='district_id',
        value_vars=band_columns,
        var_name='band_column',
        value_name=value_name,
    )
    long_df['band'] = long_df['band_column'].map(band_map)
    # Keep the source band order rather than an alphabetical sort.
    long_df['band_order'] = long_df['band_column'].map(
        {col: i for i, col in enumerate(band_columns)}
    )
    long_df = long_df.drop(columns='band_column')

    return long_df


def build_district_population_table(census_df):
    """
    Builds the SQL-ready `district_population` table.
    One row per district; total / male / female are all NOT NULL in the schema.

    census_df: pandas.DataFrame from data_cleaning_census.main()
    returns: pandas.DataFrame
    """
    columns = DISTRICT_POPULATION_COLUMNS[1:]
    require_columns(census_df, ['district_id'] + columns, 'district_population')
    require_unique(census_df, ['district_id'], 'district_population')

    table = census_df.loc[:, DISTRICT_POPULATION_COLUMNS].copy()
    table = table.sort_values('district_id').reset_index(drop=True)
    for col in columns:
        table[col] = table[col].astype('Int64')
    return table


def build_population_age_table(census_df):
    """
    Builds the SQL-ready `population_age` table (one row per district + band).
    Age band labels follow sql/schema.sql: age_band_allowed.

    census_df: pandas.DataFrame from data_cleaning_census.main()
    returns: pandas.DataFrame
    """
    table = melt_band_table(
        census_df, AGE_BAND_MAP, 'population', 'population_age'
    )
    table = table.rename(columns={'band': 'age_band'})
    table['population'] = table['population'].astype('Int64')
    table = table.sort_values(
        ['district_id', 'band_order']
    ).reset_index(drop=True)
    require_unique(table, ['district_id', 'age_band'], 'population_age')
    return table.loc[:, POPULATION_AGE_COLUMNS]


def build_working_income_table(census_df):
    """
    Builds the SQL-ready `working_income` table (one row per district + band).
    Income band labels are compact slugs mirroring the source columns, e.g.
    'income_6000_9999'. They describe the monthly income from main employment,
    excluding foreign domestic helpers and unpaid family workers.

    census_df: pandas.DataFrame from data_cleaning_census.main()
    returns: pandas.DataFrame
    """
    table = melt_band_table(
        census_df, INCOME_BAND_MAP, 'worker_count', 'working_income'
    )
    table = table.rename(columns={'band': 'income_band'})
    table['worker_count'] = table['worker_count'].astype('Int64')
    table = table.sort_values(
        ['district_id', 'band_order']
    ).reset_index(drop=True)
    require_unique(table, ['district_id', 'income_band'], 'working_income')
    return table.loc[:, WORKING_INCOME_COLUMNS]


def save_census_tables(census_df):
    """
    Builds and saves all census-derived SQL-ready tables.
    census_df: pandas.DataFrame from data_cleaning_census.main()
    """
    tables = {
        'district_population': build_district_population_table(census_df),
        'population_age': build_population_age_table(census_df),
        'working_income': build_working_income_table(census_df),
    }
    for table_name, table_df in tables.items():
        save_csv(
            table_df,
            os.path.join(STAGE_SQL_READY_DATA_DIR, f'{table_name}.csv'),
        )


def report_sql_ready_tables(report_rows=2):
    """
    Prints a short report for every CSV in STAGE_SQL_READY_DATA_DIR: the row
    and column count plus the first `report_rows` rows, so the generated table
    contents can be checked at a glance after each run.

    report_rows: int, how many leading rows to show per table
    """
    if not os.path.isdir(STAGE_SQL_READY_DATA_DIR):
        print(f"No SQL-ready output directory: {STAGE_SQL_READY_DATA_DIR}")
        return

    table_files = sorted(
        name
        for name in os.listdir(STAGE_SQL_READY_DATA_DIR)
        if name.endswith('.csv')
    )
    if not table_files:
        print("No SQL-ready CSV files were created.")
        return

    print("\n" + "=" * 78)
    print(f"SQL-READY REPORT ({len(table_files)} table(s))")
    print("=" * 78)
    for name in table_files:
        df = load_csv(os.path.join(STAGE_SQL_READY_DATA_DIR, name))
        print(f"\n[{name}] rows={len(df)} columns={len(df.columns)}")
        print(
            df.head(report_rows)
            .to_string(index=False, max_colwidth=40)
        )
    print("\n" + "=" * 78)


def census_cleaning():
    """
    Runs the census cleaning (data_cleaning_census.py) when
    CALL_CENSUS_CLEANING_AUTO is True.
    """
    if not CALL_CENSUS_CLEANING:
        return None
    else:
        # An error will be raise if the census data cleaning FAIL!
        import data_cleaning_census
        return data_cleaning_census.main()


if __name__ == '__main__':
    os.makedirs(STAGE_PRE_CLEAN_DATA_DIR, exist_ok=True)
    os.makedirs(STAGE_SQL_READY_DATA_DIR, exist_ok=True)
    print("Preparing to clean data files...")

    badminton_courts = clean_badminton_courts()
    basketball_courts = clean_basketball_courts()
    tennis_courts = clean_tennis_courts()
    fitness_rooms = clean_fitness_rooms()
    parks_zoos_and_gardens = clean_parks_zoos_and_gardens()
    swimming_pools = clean_swimming_pools()
    country_parks = clean_country_parks()
    sports_grounds = clean_sports_grounds()

    all_cleaned_dataframes = {
        'badminton_courts': badminton_courts,
        'basketball_courts': basketball_courts,
        'tennis_courts': tennis_courts,
        'fitness_rooms': fitness_rooms,
        'parks_zoos_and_gardens': parks_zoos_and_gardens,
        'swimming_pools': swimming_pools,
        'country_parks': country_parks,
        'sports_grounds': sports_grounds,
    }

    save_all_df(all_cleaned_dataframes)

    census_df = census_cleaning()

    # SQL-ready outputs.
    save_facility_type_table(build_facility_type_table())
    save_district_table(build_district_table())
    if census_df is not None:
        save_census_tables(census_df)
    else:
        print("Census cleaning disabled: skipping census tables")
    facility_df = build_facility_table(all_cleaned_dataframes)
    save_facility_table(facility_df)

    report_sql_ready_tables()

    print("Data cleaning complete!")