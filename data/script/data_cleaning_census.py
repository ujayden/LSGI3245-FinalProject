import pandas as pd
import os

# CONFIG
DATA_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
RAW_DATA_DIR = os.path.join(DATA_DIR, 'raw')
CLEAN_DATA_DIR = os.path.join(DATA_DIR, 'cleaned')

# Census raw file name contains a full-width colon.
CENSUS_RAW_FILENAME = 'DC_21C：Population distribution by district in Hong Kong.csv'
CENSUS_CLEAN_FILENAME = 'census_district.csv'

# The raw census CSV has 5 header rows before the data (1-4 are bilingual
# human-readable group/sub labels, row 5 holds the unique column ids).
# Row index is 0-based, so the machine-readable id row is index 4.
CENSUS_HEADER_ROW = 4

CENSUS_DROP_ROWS = 'LAND TOTAL'

# Read https://static.csdi.gov.hk/csdi-webpage/view/0bf0a7e2009b5f2cb26ed363f74b93b2/sds_view for the data structure.
# Columns dropped before analysis. An entry ending with '_' removes every
# column that starts with that prefix; other entries are exact matches.
# Kept for the district-level facility-provision analysis: identity, age/sex
# counts.
# Dont delete this variable even unused, it works like a comment.
CENSUS_DROP_COLS = [
    # Identity columns (dc_eng is renamed to district instead)
    'dc_class',
    'dc',
    'dc_chi',
    # Derivable / optional detail
    'sr',           # sex ratio, derivable from pop_m and pop_f
    'ma_m',         # median age by sex (t_ma kept)
    'ma_f',
    # Thematic groups out of scope
    'born_',        # place of birth
    'ethn_',        # ethnicity
    'ms_',          # marital status
    'ul_',          # usual spoken language
    'readchi_ablepctn', 'readeng_ablepctn',    # able to read Chinese / English
    'writechi_ablepctn', 'writeeng_ablepctn',  # able to write Chinese / English
    # 'edu_',         # educational attainment
    'pls_',         # place of study
    's_diff_oth',
    't_lf',         # labour force
    'lf_',
    'lfpr_',
    't_wp',         # working population / employment status
    'wp_',
    't_nwp',        # non-working population
    'nwp_',
    'plw_',         # place of work
    'mearn_',       # employment income bands / medians
    'mmearn_',
    't_mmearn',
    't_mmearn_xfdh',
    'whr_',         # weekly usual hours of work
    'pm_',          # internal migration
    'dh',           # number of domestic households
    'dhz_',         # household size
    'adhz',
    'dhc_',         # household composition
    'dhi_',         # household income bands
    'ma_hh',        # median monthly household income
    'ma_econhh',
    'oq_',          # occupied quarters by housing type
    'dh_',          # households by housing type / rooms / tenure
    'dhm_',         # mortgage payment
    'dhr_',         # rent
    'dm_r',
    'dmr_ir',
    'fa_m',         # median floor area
    # population by housing type
    'pop_pub',
    'pop_s',
    'pop_pri',
    'pop_non',
    'pop_tem',
]

# Whitelist of the census columns to keep, mapped to meaningful names.
# Dict order defines the output column order (see data_cleaning.py:rename_columns).
CENSUS_KEEP_COLS_MAP = {
    'dc_eng': 'district',
    't_pop': 'total_population',
    'pop_m': 'male_population',
    'pop_f': 'female_population',
    'age_1': 'age_under_15',
    'age_2': 'age_15_24',
    'age_3': 'age_25_44',
    'age_4': 'age_45_64',
    'age_5': 'age_65_plus',
    't_ma': 'median_age',
    # Education: population aged 15+, highest level attended
    'edu_prepri': 'education_no_schooling_preprimary',
    'edu_pri': 'education_primary',
    'edu_lsed': 'education_lower_secondary',
    'edu_usec': 'education_upper_secondary',
    'edu_dip': 'education_diploma_certificate',
    'edu_sub': 'education_subdegree',
    'edu_deg': 'education_degree',
    # Monthly main-employment income:
    # excludes foreign domestic helpers and unpaid family workers
    'mearn_xfdhfw_1': 'employment_income_under_6000',
    'mearn_xfdhfw_2': 'employment_income_6000_9999',
    'mearn_xfdhfw_3': 'employment_income_10000_19999',
    'mearn_xfdhfw_4': 'employment_income_20000_29999',
    'mearn_xfdhfw_5': 'employment_income_30000_39999',
    'mearn_xfdhfw_6': 'employment_income_40000_59999',
    'mearn_xfdhfw_7': 'employment_income_60000_plus',
}

# These are copied from data_cleaning.py - Remember to keep them in sync! @uJayden
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

def clean_census_data(file_path):
    """
    Stage 1: load the raw census CSV into a DataFrame using the unique column
    ids row (physical line 5) as the header, ignoring the bilingual descriptive
    header rows above it.

    Columns are whitelisted, reordered and renamed via `CENSUS_KEEP_COLS_MAP`
    (see data_cleaning.py:rename_columns). Rows without a district (blank line,
    footnotes, source lines) are removed. The district values are then
    uniformed via `DISTRICT_NAME_FIX_MAP` and checked against
    `CANONICAL_DISTRICT_NAMES`.

    file_path: str, path to the raw census CSV
    returns: pandas.DataFrame
    """
    df = pd.read_csv(
        file_path,
        header=CENSUS_HEADER_ROW,
        dtype=str,
        na_values=['-'],
        encoding='utf-8-sig',
    )
    df.columns = df.columns.str.strip()
    missing = set(CENSUS_KEEP_COLS_MAP) - set(df.columns)
    if missing:
        raise ValueError(
            f"{CENSUS_RAW_FILENAME}: missing expected columns: {sorted(missing)}"
        )
    df = df.loc[:, list(CENSUS_KEEP_COLS_MAP)].rename(columns=CENSUS_KEEP_COLS_MAP)
    df = df[df['district'].notna()].reset_index(drop=True)
    df['district'] = normalize_district_values(df['district'])
    df = df[df['district'] != CENSUS_DROP_ROWS].reset_index(drop=True) # Drop the aggregate row
    warn_if_district_mismatch(df['district'], CENSUS_RAW_FILENAME)
    # Remove thousands separators and spaces from numeric columns, which are stored as strings in the raw CSV
    # What's wrong with the government while making these data?
    for col in df.columns:
        if col == 'district':
            continue
        df[col] = pd.to_numeric(
            df[col].str.replace('[ ,]', '', regex=True), errors='coerce'
        )
    return df


def main():
    """
    Loads, cleans and saves the census district table.
    Also the entry point used by data_cleaning.py when auto-calling.
    returns: pandas.DataFrame
    """
    os.makedirs(CLEAN_DATA_DIR, exist_ok=True)

    raw_path = os.path.join(RAW_DATA_DIR, CENSUS_RAW_FILENAME)
    print(f"Loading census data from: {CENSUS_RAW_FILENAME}")

    census_df = clean_census_data(raw_path)
    save_csv(census_df, os.path.join(CLEAN_DATA_DIR, CENSUS_CLEAN_FILENAME))

    print(
        f"Saved {len(census_df)} rows x {len(census_df.columns)} columns to "
        f"{CENSUS_CLEAN_FILENAME}"
    )
    return census_df


if __name__ == '__main__':
    main()
