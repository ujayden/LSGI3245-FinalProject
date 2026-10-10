import pandas as pd
import os
from pyproj import Transformer


# CONFIG
DATA_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
RAW_DATA_DIR = os.path.join(DATA_DIR, 'raw')
CLEAN_DATA_DIR = os.path.join(DATA_DIR, 'cleaned')
CALL_CENSUS_CLEANING = True

# Pre-file Config
# Whitelist of columns kept per raw CSV, mapped to their cleaned names.
# Generally, these are dropped.
#   1. All Traditional Chinese columns (suffix _TC / *TC)
#   2. Website columns (NSEARCH06_* / WebsiteEN+WebsiteTC)
#   3. Contact information columns (NSEARCH03_* / NSEARCH04_* / NSEARCH05_*)
#   4. Duplicated geo information (Geometry_*) - It AVOID confusion and mismatch when someone pick WRONG coloum.
# Note: latitude / longitude is WGS84, northing / easting is HK1980 Grid System.
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
        "No__of_Badminton_Courts_EN": "badminton_courts_count",
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
        "No__of_Basketball_Courts_EN": "basketball_courts_count",
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
        "No__of_Tennis_Courts_EN": "tennis_courts_count",
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


def add_wgs84_coordinates(df):
    transformer = Transformer.from_crs(
        'EPSG:2326', #HK1980 Grid System
        'EPSG:4326', #WGS84
        always_xy=True,
    )
    longitude, latitude = transformer.transform(
        pd.to_numeric(df['easting']),
        pd.to_numeric(df['northing']),
    )
    df.insert(1, 'latitude', latitude)
    df.insert(2, 'longitude', longitude)
    return df


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


def clean_badminton_courts():
    filename = 'badminton_courts.csv'
    df = load_csv(os.path.join(RAW_DATA_DIR, filename))
    df = rename_columns(df, filename)
    warn_if_district_mismatch(df['district'], filename)
    # save_csv(df, os.path.join(CLEAN_DATA_DIR, filename))
    return df


def clean_basketball_courts():
    filename = 'basketball_courts.csv'
    df = load_csv(os.path.join(RAW_DATA_DIR, filename))
    df = rename_columns(df, filename)
    warn_if_district_mismatch(df['district'], filename)
    # save_csv(df, os.path.join(CLEAN_DATA_DIR, filename))
    return df


def clean_tennis_courts():
    filename = 'tennis_courts.csv'
    df = load_csv(os.path.join(RAW_DATA_DIR, filename))
    df = rename_columns(df, filename)
    warn_if_district_mismatch(df['district'], filename)
    # save_csv(df, os.path.join(CLEAN_DATA_DIR, filename))
    return df


def clean_fitness_rooms():
    filename = 'fitness_rooms.csv'
    df = load_csv(os.path.join(RAW_DATA_DIR, filename))
    df = rename_columns(df, filename)
    warn_if_district_mismatch(df['district'], filename)
    # save_csv(df, os.path.join(CLEAN_DATA_DIR, filename))
    return df


def clean_parks_zoos_and_gardens():
    filename = 'parks_zoos_and_gardens.csv'
    df = load_csv(os.path.join(RAW_DATA_DIR, filename))
    df = rename_columns(df, filename)
    warn_if_district_mismatch(df['district'], filename)
    # save_csv(df, os.path.join(CLEAN_DATA_DIR, filename))
    return df


def clean_swimming_pools():
    filename = 'swimming_pools.csv'
    df = load_csv(os.path.join(RAW_DATA_DIR, filename))
    df = rename_columns(df, filename)
    warn_if_district_mismatch(df['district'], filename)
    # save_csv(df, os.path.join(CLEAN_DATA_DIR, filename))
    return df


def clean_country_parks():
    filename = 'country_parks.csv'
    df = load_csv(os.path.join(RAW_DATA_DIR, filename))
    df = rename_columns(df, filename)
    df = add_wgs84_coordinates(df)
    # save_csv(df, os.path.join(CLEAN_DATA_DIR, filename))
    return df


def clean_sports_grounds():
    filename = 'sports_grounds.csv'
    df = load_csv(os.path.join(RAW_DATA_DIR, filename))
    df = rename_columns(df, filename)
    warn_if_district_mismatch(df['district'], filename)
    # save_csv(df, os.path.join(CLEAN_DATA_DIR, filename))
    return df


def rename_columns(df, filename):
    """
    Keeps and renames whitelisted columns, then applies the output order.
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
    Saves all dataframes to CSV files named after their variable names.
    dataframes: mapping of variable names to pandas.DataFrame
    """
    for variable_name, df in dataframes.items():
        save_csv(df, os.path.join(CLEAN_DATA_DIR, f'{variable_name}.csv'))

def merge_cleaned_dataframes(dataframes):
    """
    Merges cleaned dataframes and identifies each row by its dataset.
    dataframes: mapping of dataset names to pandas.DataFrame
    returns: pandas.DataFrame
    """
    dataframes_with_dataset = []
    for dataset_name, df in dataframes.items():
        dataset_df = df.copy()
        dataset_df.insert(0, 'dataset', dataset_name)
        dataframes_with_dataset.append(dataset_df)

    return pd.concat(dataframes_with_dataset, ignore_index=True)

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
    os.makedirs(CLEAN_DATA_DIR, exist_ok=True)
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

    # Merge all cleaned dataframes (excluding census) into a single dataframe
    merged_df = merge_cleaned_dataframes(all_cleaned_dataframes)
    save_csv(merged_df, os.path.join(CLEAN_DATA_DIR, 'merged_cleaned_data.csv'))

    print("Data cleaning complete!")
