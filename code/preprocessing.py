import pandas as pd
import numpy as np

# ==============================================================================
# State level: Subset and clean the datasets of interest (Other than voting data)
# ==============================================================================
# ------------CEP data------------------
cep = pd.read_excel(r"..\data\raw-data\cep_2024.xlsx")
# -- Keep cols of interest --
cep_clean = cep.drop(columns=["ISP Category"])
# -- rename --
cep_clean = cep_clean.rename(columns={
    "State": "state_abbrev",
    "School District or Local Education Agency (LEA) ID": "lea_id",
    "School District or Local Education Agency (LEA) Name": "lea_name",
    "School ID": "school_id",
    "School Name": "school_name",
    "Identified Student Percentage (ISP)": "isp",
    "Participation in CEP ": "cep_participation",
    "Enrollment": "enrollment"
})
# -- Convert CEP numeric columns --
# ID has leading zero sometimes, so we keep it as srt type
cep_clean["isp"] = pd.to_numeric(cep_clean["isp"], errors="coerce")
cep_clean["enrollment"] = pd.to_numeric(cep_clean["enrollment"], errors="coerce")

# -- Preparation for aggregation --
"We are going to create columns for cep participation rate (cep schools / total schools) and student-weighted cep participation rate (cep rate weighted by enrollment),"
"but enrollment data is pretty messy so we will follow the procedure below"
" 1 Check zero or nan values in 'cep participation' and 'enrollment'"
" 2 If there are missing values, we will rule out states with more than 10% missing rate from analysis"
cep_school = cep_clean.copy()
# Convert zero into nan
cep_school["enrollment"] = (
    cep_school["enrollment"]
    .replace(0, np.nan)
)
# Sort state based on the rate of missing enrollment
# Based on the result, we are ruling out IA, UT, MS, AK, PA, OK, and MO when using student enrollment weighted CEP
state_missing = (
    cep_school
    .groupby("state_abbrev")
    .agg(
        total_schools=("enrollment", "size"),
        missing_enrollment=("enrollment", lambda x: x.isna().sum())
    )
    .reset_index()
)
state_missing["missing_rate"] = (
    state_missing["missing_enrollment"] /
    state_missing["total_schools"]
)
state_missing.sort_values("missing_rate", ascending=False)

# -- Aggregation of CEP participation and student-weighted one --
# Make binary indicator
cep_school["cep_dummy"] = (cep_school["cep_participation"] == "Yes").astype(int)
# Enrollment in CEP schools
cep_school["cep_enrollment"] = cep_school["cep_dummy"] * cep_school["enrollment"]
# Aggregate to state
cep_state = (
    cep_school
    .groupby("state_abbrev")
    .agg(
        total_schools=("state_abbrev", "size"), # some do not have school id and some have duplicate school names 
        cep_schools=("cep_dummy", "sum"),
        total_enrollment=("enrollment", "sum"),
        cep_enrollment=("cep_enrollment", "sum")
    )
    .reset_index()
)
# Rates
cep_state["cep_rate_school"] = cep_state["cep_schools"] / cep_state["total_schools"]
cep_state["cep_rate_student"] = cep_state["cep_enrollment"] / cep_state["total_enrollment"]
# Put Nan in observations in enrollment and cep_rate_student for the states with high missing value rate 
# (IA, UT, MS, AK, PA, OK, and MO) 
bad_states = ["IA", "UT", "MS", "AK", "PA", "OK", "MO"]
cols_to_null = ["total_enrollment", "cep_enrollment", "cep_rate_student"]
cep_state_clean = cep_state.copy()
cep_state_clean.loc[
    cep_state_clean["state_abbrev"].isin(bad_states),
    cols_to_null
] = np.nan
# For later merge, it is better to add state fips to the state data
state_to_fips = {
    "AL": "01", "AK": "02", "AZ": "04", "AR": "05", "CA": "06",
    "CO": "08", "CT": "09", "DE": "10", "DC": "11", "FL": "12",
    "GA": "13", "HI": "15", "ID": "16", "IL": "17", "IN": "18",
    "IA": "19", "KS": "20", "KY": "21", "LA": "22", "ME": "23",
    "MD": "24", "MA": "25", "MI": "26", "MN": "27", "MS": "28",
    "MO": "29", "MT": "30", "NE": "31", "NV": "32", "NH": "33",
    "NJ": "34", "NM": "35", "NY": "36", "NC": "37", "ND": "38",
    "OH": "39", "OK": "40", "OR": "41", "PA": "42", "RI": "44",
    "SC": "45", "SD": "46", "TN": "47", "TX": "48", "UT": "49",
    "VT": "50", "VA": "51", "WA": "53", "WV": "54", "WI": "55",
    "WY": "56"
}
cep_state_clean["state_fips"] = (
    cep_state_clean["state_abbrev"]
        .map(state_to_fips)
)

# -- arrange the position of stat fips column
cols = list(cep_state_clean.columns)
# Remove state_fips from its current position
cols.remove("state_fips")
# Find position of state_abbrev
idx = cols.index("state_abbrev")
# Insert state_fips right after state_abbrev
cols.insert(idx + 1, "state_fips")
# Store the data 
cep_school.to_csv("../data/derived-data/cep_school.csv", index=False)
# Reorder dataframe
cep_state_clean = cep_state_clean[cols]

# ---------child poverty---------------------
child_pov = pd.read_csv(r"..\data\raw-data\child_poverty_rate_2024.csv", skiprows=[1])
# -- Keep cols of interest --
keep_cols = [
    "GEO_ID",
    "NAME",
    "S1701_C01_005E",  # total population (poverty universe), under age 18
    "S1701_C02_005E",  # count below poverty, under age 18 
    "S1701_C03_005E"   # % below poverty, under age 18   
]
child_pov_clean = child_pov[keep_cols].copy()
# -- rename --
child_pov_clean = child_pov_clean.rename(columns={
    "NAME": "geo_name",
    "S1701_C01_005E": "population_children",
    "S1701_C02_005E": "poverty_count_children",
    "S1701_C03_005E": "poverty_rate_children"
})
# -- Convert numeric columns --
child_pov_clean["population_children"] = pd.to_numeric(
    child_pov_clean["population_children"], errors="coerce"
)

child_pov_clean["poverty_count_children"] = pd.to_numeric(
    child_pov_clean["poverty_count_children"], errors="coerce"
)

child_pov_clean["poverty_rate_children"] = pd.to_numeric(
    child_pov_clean["poverty_rate_children"], errors="coerce"
)
# -- Store the data temprarily --
#child_pov_clean.to_csv("child_pov_clean.csv", index=False)
# -- Separate the data --
# State-level rows
child_pov_state = child_pov_clean[
    child_pov_clean["GEO_ID"].str.startswith("040")
].copy()
child_pov_state["state_fips"] = (
    child_pov_state["GEO_ID"]
        .str[-2:]
)
# County-level rows
child_pov_county = child_pov_clean[
    child_pov_clean["GEO_ID"].str.startswith("050")
].copy()


# -- Add fips columns and tidy them up --
# Add "fips code" columns
child_pov_county["fips"] = child_pov_county["GEO_ID"].str[-5:]
child_pov_county["state_fips"] = child_pov_county["fips"].str[:2]
child_pov_county["county_fips"] = child_pov_county["fips"].str[2:]
# Make sure that they are srt type
child_pov_county["state_fips"] = child_pov_county["state_fips"].astype(str).str.zfill(2)
child_pov_county["county_fips"] = child_pov_county["county_fips"].astype(str).str.zfill(3)
# Store the data
child_pov_county.to_csv("..\data\derived-data\child_pov_county.csv", index=False)

# ---------food insecurity-----------------
food_insec = pd.read_csv(r"..\data\raw-data\food_insecurity_2024.csv")
# -- Keep cols of interest --
# HRFS12MC is related to the suevy question about food insecurity with a household with children
# PWSSWGT is weight (final person level weight) for state level aggregation
keep_cols_2 = [
    "GESTFIPS",
    "GTCO",
    "HRFS12MC",
    "PWSSWGT"
]
food_insec_clean = food_insec[keep_cols_2].copy()
# -- rename --
food_insec_clean = food_insec_clean.rename(columns={
    "HRFS12MC": "child_food_security_status",
    "PWSSWGT": "weights",
    "GESTFIPS": "state_fips",
    "GTCO": "county_fips"
})
# -- Convert numeric columns --
food_insec_clean["child_food_security_status"] = pd.to_numeric(
    food_insec_clean["child_food_security_status"], errors="coerce"
)

food_insec_clean["state_fips"] = pd.to_numeric(
    food_insec_clean["state_fips"], errors="coerce"
)

food_insec_clean["county_fips"] = pd.to_numeric(
    food_insec_clean["county_fips"], errors="coerce"
)
# -- standardize fips code --
cols = ["state_fips", "county_fips"]
# 0 → nan
for col in cols:
    food_insec_clean.loc[food_insec_clean[col] == 0, col] = np.nan
# 
food_insec_clean["state_fips"] = food_insec_clean["state_fips"].apply(
    lambda x: f"{int(x):02d}" if pd.notna(x) else np.nan
)

food_insec_clean["county_fips"] = food_insec_clean["county_fips"].apply(
    lambda x: f"{int(x):03d}" if pd.notna(x) else np.nan
)
food_insec_clean["fips"] = food_insec_clean["state_fips"] + food_insec_clean["county_fips"]
# -- Convert nagative values nan --
# According to the data instruction, negative values mean missing codes
food_insec_clean["child_food_security_status"] = (
    food_insec_clean["child_food_security_status"]
        .apply(lambda x: np.nan if x < 0 else x)
)
# -- Store the data --
food_insec_county = food_insec_clean.copy()
#food_insec_county.to_csv("food_insec_county.csv", index=False)

# -- Aggregate data to state level -- 
"1. According to the survey, households with high or marginal food security is 1, "
" low food seccurity among children is 2, and very low security is 3. So, we are "
" estimaing the percentage of food insecure rate among households with children by"
" dividing the total number of (2+3) by that of (1+2+3)"
"2. This is CPS data, so we need to add weights to the calculation"
# 1) Keep valid rows (status 1/2/3) and valid weights
df = food_insec_county.dropna(subset=["child_food_security_status", "weights"]).copy()
# ensure weights are numeric
df["weights"] = pd.to_numeric(df["weights"], errors="coerce")
df = df.dropna(subset=["weights"])
df = df[df["weights"] > 0]
# 2) Indicator: insecure = 2 or 3
df["insecure"] = df["child_food_security_status"].isin([2, 3]).astype(int)
# 3) Weighted sums by state
food_insec_state = (
    df.groupby("state_fips")
      .apply(lambda g: pd.Series({
          "weighted_total": g["weights"].sum(),
          "weighted_insecure": (g["weights"] * g["insecure"]).sum(),
          "n_obs": len(g)  # unweighted sample size (diagnostic)
      }))
      .reset_index()
)
# 4) Weighted rate
food_insec_state["child_food_insec_rate"] = (
    food_insec_state["weighted_insecure"] / food_insec_state["weighted_total"]
)

# ==================================
# Merge the dataset
# ==================================
# ---------basic master data ----------
# -- Make sure they are both srt type
cep_state_clean["state_fips"] = cep_state_clean["state_fips"].astype(str)
child_pov_state["state_fips"] = child_pov_state["state_fips"].astype(str)

# -- Merge --
# + child poverty
merged_state_pov = cep_state_clean.merge(
    child_pov_state[["state_fips", "geo_name", "poverty_rate_children"]],
    on="state_fips",
    how="left"
)
merged_state_pov[merged_state_pov["geo_name"].isna()]

# + fooe insecurity
merged_state_all = merged_state_pov.merge(
    food_insec_state[["state_fips", "child_food_insec_rate"]],
    on="state_fips",
    how="left"
)

# --Tidy columns--
merged_state_all = merged_state_all.rename(
    columns={"geo_name": "state_name"}
)
cols = merged_state_all.columns.tolist()
# Remove state_name from current position
cols.remove("state_name")
# Find position of state_abbrev
idx = cols.index("state_abbrev")
# Insert state_name right after state_abbrev
cols.insert(idx + 1, "state_name")
# Reorder dataframe
merged_state_all = merged_state_all[cols]

# --------add other variables-------------
from pathlib import Path
DERIVED_DIR = Path(r"..\data\derived-data")
DATA_DIR   = Path(r"..\data\raw-data")
master = merged_state_all.copy()
cycle_files = [
    "Food Sufficiency for Households with Children_cycle01.xlsx",
    "Food Sufficiency for Households with Children_cycle02.xlsx",
    "Food Sufficiency for Households with Children_cycle03.xlsx",
    "Food Sufficiency for Households with Children_cycle04.xlsx",
    "Food Sufficiency for Households with Children_cycle05.xlsx",
    "Food Sufficiency for Households with Children_cycle06.xlsx",
    "Food Sufficiency for Households with Children_cycle07.xlsx",
    "Food Sufficiency for Households with Children_cycle08.xlsx",
    "Food Sufficiency for Households with Children_cycle09.xlsx"
]

rows = []
abbr_map = dict(zip(master["state_abbrev"], master["state_name"]))  # abbrev -> full

for f in cycle_files:
    xls = pd.ExcelFile(DATA_DIR / f)

    for sh in xls.sheet_names:
        if str(sh).strip().lower() in ["us", "u.s.", "united states", "national"]:
            continue

        raw = pd.read_excel(xls, sheet_name=sh, header=None)

        col0 = raw.iloc[:, 0].astype(str).str.strip().str.lower()
        if not (col0 == "select characteristics").any():
            continue
        hdr = col0[col0 == "select characteristics"].index[0]

        h1 = raw.iloc[hdr].fillna("").astype(str).str.replace(r"\s+", " ", regex=True).str.strip()
        h2 = raw.iloc[hdr + 1].fillna("").astype(str).str.replace(r"\s+", " ", regex=True).str.strip()
        cols = (h1 + " " + h2).str.replace(r"\s+", " ", regex=True).str.strip()

        df = raw.iloc[hdr + 2:].copy()
        df.columns = cols

        first_col = df.columns[0]
        col_total = next((c for c in df.columns if c.lower().strip() == "total"), None)
        col_some  = next((c for c in df.columns if "sometimes" in c.lower()), None)
        col_often = next((c for c in df.columns if "often" in c.lower()), None)
        if col_total is None or col_some is None or col_often is None:
            continue

        df[first_col] = df[first_col].astype(str).str.strip()
        rr = df.loc[df[first_col].str.fullmatch("Total", case=False, na=False)]
        if rr.empty:
            continue
        r = rr.iloc[0]

        parse = lambda x: pd.to_numeric(str(x).replace(",", "").replace("-", ""), errors="coerce")
        tot, som, oft = parse(r[col_total]), parse(r[col_some]), parse(r[col_often])
        if pd.isna(tot) or tot == 0 or pd.isna(som) or pd.isna(oft):
            continue

        st = abbr_map.get(str(sh).strip(), None)  # convert abbrev -> full
        if st is None:
            continue

        rows.append([st, som + oft, tot])

food_all = pd.DataFrame(rows, columns=["state_name", "insuff_count", "total_base"])

food_state = (
    food_all.groupby("state_name", as_index=False)
            .agg({"insuff_count": "sum", "total_base": "sum"})
)
food_state["food_insufficiency_weighted"] = food_state["insuff_count"] / food_state["total_base"]
food_state = food_state[["state_name", "food_insufficiency_weighted"]]

master["state_name"] = master["state_name"].astype(str).str.strip().str.replace(r"\s+", " ", regex=True)
food_state["state_name"] = food_state["state_name"].astype(str).str.strip().str.replace(r"\s+", " ", regex=True)

master = master.merge(food_state, on="state_name", how="left")


# 1)total_school_lunch_served
raw = pd.read_excel(DATA_DIR / "total_school_lunch_served.xlsx", header=None)
var_label = str(raw.iloc[0, 0]).strip()

raw.columns = raw.iloc[2]                 
df = raw.iloc[3:].copy().dropna(how="all")

state_col = df.columns[0]               
fy2024_col = df.columns[2]           

df = df[[state_col, fy2024_col]].rename(columns={state_col: "state_name", fy2024_col: var_label})
df["state_name"] = df["state_name"].astype(str).str.strip().str.replace(r"\s+", " ", regex=True)

df[var_label] = (
    df[var_label]
    .replace({"--": np.nan})
    .astype(str)
    .str.replace(",", "", regex=False)
    .str.strip()
    .replace({"": np.nan, "nan": np.nan})
)
df[var_label] = pd.to_numeric(df[var_label], errors="coerce")

master = master.merge(df, on="state_name", how="left")

master = master.rename(columns = {"NATIONAL SCHOOL LUNCH PROGRAM:  TOTAL LUNCHES SERVED": "total_lunch_served"}
) 

# 2) cash_payment_nslp

raw = pd.read_excel(DATA_DIR / "cash_payment_nslp.xlsx", header=None)
var_label = str(raw.iloc[0, 0]).strip()

raw.columns = raw.iloc[2]
df = raw.iloc[3:].copy().dropna(how="all")

state_col = df.columns[0]
fy2024_col = df.columns[2]

df = df[[state_col, fy2024_col]].rename(columns={state_col: "state_name", fy2024_col: var_label})
df["state_name"] = df["state_name"].astype(str).str.strip().str.replace(r"\s+", " ", regex=True)

df[var_label] = (
    df[var_label]
    .replace({"--": np.nan})
    .astype(str)
    .str.replace(",", "", regex=False)
    .str.strip()
    .replace({"": np.nan, "nan": np.nan})
)
df[var_label] = pd.to_numeric(df[var_label], errors="coerce")

master = master.merge(df, on="state_name", how="left")

master = master.rename(columns = {"NATIONAL SCHOOL LUNCH PROGRAM:  CASH PAYMENTS": "total_cash_payments"}
) 

# 3) commodity_cost

raw = pd.read_excel(DATA_DIR / "commodity_cost.xlsx", header=None)
var_label = str(raw.iloc[0, 0]).strip()

raw.columns = raw.iloc[2]
df = raw.iloc[3:].copy().dropna(how="all")

state_col = df.columns[0]
fy2024_col = df.columns[2]

df = df[[state_col, fy2024_col]].rename(columns={state_col: "state_name", fy2024_col: var_label})
df["state_name"] = df["state_name"].astype(str).str.strip().str.replace(r"\s+", " ", regex=True)

df[var_label] = (
    df[var_label]
    .replace({"--": np.nan})
    .astype(str)
    .str.replace(",", "", regex=False)
    .str.strip()
    .replace({"": np.nan, "nan": np.nan})
)
df[var_label] = pd.to_numeric(df[var_label], errors="coerce")

master = master.merge(df, on="state_name", how="left")

master = master.rename(columns = {"NATIONAL SCHOOL LUNCH PROGRAM:  COMMODITY COSTS"
: "total_commodity_costs"}
) 


# 4) ACS 2024 school-age population (pop_by_age) (5–17) 

acs = pd.read_csv(DATA_DIR / "pop_by_age.csv")

labels = acs["Label (Grouping)"].astype(str).str.replace(r"\s+", " ", regex=True)
rows = acs.loc[
    labels.str.contains("5 to 9 years", regex=False)
    | labels.str.contains("10 to 14 years", regex=False)
    | labels.str.contains("15 to 17 years", regex=False)
].copy()

est_cols = [c for c in rows.columns if str(c).endswith("!!Total!!Estimate")]

school_age = rows[est_cols].replace({",": ""}, regex=True)
school_age = school_age.apply(pd.to_numeric, errors="coerce").sum(axis=0).reset_index()
school_age.columns = ["_col", "school_age_pop_2024"]

school_age["state_name"] = school_age["_col"].astype(str).str.split("!!").str[0].str.strip().str.replace(r"\s+", " ", regex=True)
school_age = school_age[["state_name", "school_age_pop_2024"]]

master = master.merge(school_age, on="state_name", how="left")

# Ensure denominator is numeric and nonzero
master["school_age_pop_2024"] = pd.to_numeric(master["school_age_pop_2024"], errors="coerce")
den = master["school_age_pop_2024"].where(master["school_age_pop_2024"] > 0)

# Lunches per school-age child
master["lunches_per_school_age"] = master["total_lunch_served"] / den

# Cash payments per school-age child (USD per child)
master["cash_per_school_age"] = master["total_cash_payments"] / den

# Commodity costs per school-age child (USD per child)
master["commodity_per_school_age"] = master["total_commodity_costs"] / den

# Total NSLP dollars per school-age child (cash + commodity)
master["nslp_total_dollars_per_school_age"] = (master["total_cash_payments"] + master["total_commodity_costs"]) / den

# Optional: dollars per lunch (cost intensity)
master["cash_per_lunch"] = master["total_cash_payments"] / master["total_lunch_served"].where(master["total_lunch_served"] > 0)
master["commodity_per_lunch"] = master["total_commodity_costs"] / master["total_lunch_served"].where(master["total_lunch_served"] > 0)
master["total_dollars_per_lunch"] = (master["total_cash_payments"] + master["total_commodity_costs"]) / master["total_lunch_served"].where(master["total_lunch_served"] > 0)

# -----------------------
# Save
# -----------------------
out_path = DERIVED_DIR / "master_state_merged.csv"
master.to_csv(out_path, index=False)

# ====================================================================
# State level: Subset and clean the datasets of interest (voting data)
# ====================================================================
# ------------------
# Clean the data set
# ------------------
df = pd.read_csv(r"..\data\raw-data\voting_2000-2024.csv")
# 1 Filter 2024
df_2024 = df[df["year"] == 2024]
# 2 Keep only DEM and REP
df_2024 = df_2024[df_2024["party"].isin(["DEMOCRAT", "REPUBLICAN"])]
# 3 Pivot to wide formant
df_wide = (
    df_2024
    .pivot_table(
        index=["state_po", "county_fips", "county_name"],
        columns="party",
        values="candidatevotes",
        aggfunc="sum"
    )
    .reset_index()
)
# 4 Compute total votes
df_wide["total_votes"] = (
    df_wide["DEMOCRAT"] + df_wide["REPUBLICAN"]
)
# 5 Compute democratic margin
df_wide["dem_margin"] = (
    df_wide["DEMOCRAT"] - df_wide["REPUBLICAN"]
) / df_wide["total_votes"]
# 6 Fix Fips
df_wide["county_fips"] = df_wide["county_fips"].astype(str).str.zfill(5)
# 7 State and county level data
vote_county_2024 = df_wide.copy()
vote_state_2024 = (
    df_wide
    .groupby("state_po")[["DEMOCRAT", "REPUBLICAN", "total_votes"]]
    .sum()
    .reset_index()
)
vote_state_2024["dem_margin"] = (
    vote_state_2024["DEMOCRAT"] - vote_state_2024["REPUBLICAN"]
) / vote_state_2024["total_votes"]  

vote_county_2024.to_csv(r"..\data\raw-data\vote_county_2024.csv", index=False)
#vote_state_2024.to_csv("vote_state_2024.csv", index=False)

## Child poverty and CEP rate
master = master.rename(columns={"state_abbrev": "state_po"})
master_state_vars = master[["state_po", "cep_rate_school", "poverty_rate_children"]].copy()

# 3) Merge into vote_state_2024
vote_state_2024 = vote_state_2024.merge(
    master_state_vars,
    on="state_po",
    how="left",
    validate="one_to_one"  # change to "one_to_many" if your vote data has duplicates
)

# 4) Quick check
vote_state_2024_sorted = vote_state_2024.sort_values(
    by="dem_margin",
    ascending=True
)
vote_state_2024_sorted.to_csv(r"..\data\derived-data\vote_state_2024_with_others.csv", index=False)

# ==============================================================================
# County level: Subset and clean the datasets of interest (Other than voting data)
# ==============================================================================

# -----------------------------
# 1) IL: child poverty and vote
# -----------------------------
child_pov_county = pd.read_csv(r"..\data\derived-data\child_pov_county.csv")
child_pov_il = child_pov_county[child_pov_county["state_fips"] == 17].copy()
child_pov_il = child_pov_il.rename(columns={
    "fips": "county_fips",
    "county_fips":"county_fips_3"})
child_pov_il["county_fips"] = (
    child_pov_il["county_fips"]
    .astype(str)
    .str.replace(r"\.0$", "", regex=True)
    .str.strip()
    .str.zfill(5)
)
child_pov_il["county_fips"]
len(child_pov_il)

vote_county_2024 = pd.read_csv(r"..\data\derived-data\vote_county_2024.csv")
vote_county_2024["county_fips"] = vote_county_2024["county_fips"].astype(str).str.zfill(5)
vote_county_2024["county_fips"] = (
    vote_county_2024["county_fips"].astype(str)
    .str.replace(r"\.0$", "", regex=True)
    .str.strip()
    .str.zfill(5)
)
vote_2024_il = vote_county_2024[vote_county_2024["county_fips"].str.startswith("17")].copy()
len(vote_2024_il)

vote_2024_il.to_csv(r"..\data\derived-data\vote_2024_il.csv", index=False)
child_pov_il.to_csv(r"..\data\derived-data\child_pov_il.csv", index=False)

# ------------------------
# 2) IL cep school → county level
# ------------------------

# 1 Load files
cep_school = pd.read_csv(r"..\data\derived-data\cep_school.csv")

# 2 IL school data with county codes
cep_school["isp"] = pd.to_numeric(cep_school["isp"], errors="coerce")
cep_school[cep_school["state_abbrev"] == "IL"]["isp"].isna().sum()
## Subset the data to Illinois data
cep_school_IL = cep_school[cep_school["state_abbrev"] == "IL"]
cep_school_IL["school_id"].nunique()
## cep_school_IL.to_csv("cep_school_IL.csv", index=False)
## Extract county ISBE code
cep_school_IL["county_code_ISBE"] = cep_school_IL["lea_id"].str.split("-").str[1]
## Remove county code "000" and "108" because they are not county institutions
cep_school_IL = cep_school_IL[
    ~cep_school_IL["county_code_ISBE"].isin(["000", "108"])
]
## Convert ISBE code into Fips code
cep_school_IL["county_code_ISBE"] = cep_school_IL["county_code_ISBE"].astype(int)
cep_school_IL["county_fips"] = (
    "17" +
    (2 * cep_school_IL["county_code_ISBE"] - 1)
        .astype(str)
        .str.zfill(3)
)
cep_school_IL["county_fips"].nunique() # This returns 102, equal to the number of counties in IL
cep_school_IL_county = cep_school_IL.copy()

# 3) Aggregate data at the county level
## Aggregate data
cep_county_IL = (
    cep_school_IL_county
    .groupby("county_fips")
    .apply(lambda df: pd.Series({
        "total_schools": df["school_id"].count(),
        "total_students": df["enrollment"].sum(),
        "cep_school_rate": (df["cep_participation"]=="Yes").mean(),
        "cep_student_rate":
            df.loc[df["cep_participation"]=="Yes","enrollment"].sum()
            / df["enrollment"].sum(),
        "weighted_isp":
            (df["isp"]*df["enrollment"]).sum()
            / df["enrollment"].sum()
    }))
    .reset_index()
)
cep_county_IL.to_csv(r"..\data\derived-data\cep_county_IL.csv", index=False)
cep_county_IL["county_fips"]

# -----------------------------
# 2) MO: child poverty and vote
# -----------------------------

child_pov_mo = child_pov_county[child_pov_county["state_fips"] == 29].copy()
child_pov_mo = child_pov_mo.rename(columns={
    "fips": "county_fips",
    "county_fips":"county_fips_3"})
child_pov_mo["county_fips"] = (
    child_pov_mo["county_fips"]
    .astype(str)
    .str.replace(r"\.0$", "", regex=True)
    .str.strip()
    .str.zfill(5)
)
child_pov_mo["county_fips"]
len(child_pov_mo)

vote_county_2024["county_fips"] = vote_county_2024["county_fips"].astype(str).str.zfill(5)
vote_county_2024["county_fips"] = (
    vote_county_2024["county_fips"].astype(str)
    .str.replace(r"\.0$", "", regex=True)
    .str.strip()
    .str.zfill(5)
)
vote_2024_mo = vote_county_2024[vote_county_2024["county_fips"].str.startswith("29")].copy()
len(vote_2024_mo)

vote_2024_mo.to_csv(r"..\data\derived-data\vote_2024_mo.csv", index=False)
child_pov_mo.to_csv(r"..\data\derived-data\child_pov_mo.csv", index=False)

# ----------------------------
# MO:CEP school　→　CEP county
# -----------------------------

# -------------------------
# CEP file
# -------------------------
cep_school["isp"] = pd.to_numeric(cep_school["isp"], errors="coerce")
cep_school[cep_school["state_abbrev"] == "MO"]["isp"].isna().sum()
# Subset the data to Illinois data
cep_school_MO = cep_school[cep_school["state_abbrev"] == "MO"]
# Sanity check: school IDs are unique across the observations?
len(cep_school_MO)
cep_school_MO["school_id"].nunique()
cep_school_MO["lea_id"].nunique()
cep_school_MO.isna().sum()
#cep_school_MO.to_csv("cep_school_MO.csv", index=False)

# -----------------------------------
# Crosswalk (school id → county fips)
# -----------------------------------
# laod necessary data sets
ccd_sch = pd.read_csv(r"..\data\raw-data\crosswalk\ccd_sch.csv")
ncessch = pd.read_excel(r"..\data\raw-data\crosswalk\EDGE_GEOCODE.xlsx")
# Subset to MO data
ccd_sch_mo = ccd_sch[ccd_sch["FIPST"] == 29]
ncessch_mo = ncessch[ncessch["OPSTFIPS"] == 29]
len(ccd_sch_mo)
len(ncessch_mo)
len(cep_school_MO)
ccd_sch_mo["SCH_NAME"].nunique()
# Add county fips data to ccd_sch_mo
ccd_sch_mo["NCESSCH"] = ccd_sch_mo["NCESSCH"].astype(str)
ncessch_mo["NCESSCH"] = ncessch_mo["NCESSCH"].astype(str)
ccd_with_county = ccd_sch_mo.merge(
    ncessch_mo[["NCESSCH", "CNTY"]],
    on="NCESSCH",
    how="left"
)
ccd_with_county = ccd_with_county.rename(
    columns={"CNTY": "county_fips"}
)

# ------------------------------------
# Merge county fips code with cep data
# ------------------------------------
# -------------------------
# (1) Hypothesis check: ST_LEAID (MO-036137) vs CEP lea_id (036-137)
# -------------------------
# Build comparable LEA keys
ccd_mo = ccd_with_county.copy()
cep_mo = cep_school_MO.copy()
ccd_mo["lea6"] = ccd_mo["ST_LEAID"].str.split("-").str[-1].str.zfill(6)     # "036137"
ccd_mo["lea_id_from_ccd"] = ccd_mo["lea6"].str[:3] + "-" + ccd_mo["lea6"].str[3:]  # "036-137"

cep_mo["lea_id"] = cep_mo["lea_id"].astype(str)
cep_mo["lea6"] = cep_mo["lea_id"].str.replace("-", "", regex=False).str.zfill(6)

# Coverage check: what share of CEP lea_id exists in CCD?
lea_match_rate = cep_mo["lea6"].isin(set(ccd_mo["lea6"])).mean()
print(f"LEA match rate (CEP lea_id in CCD): {lea_match_rate:.3f}")
# This returns 98%, so we can moev on with this method

# -----------------------------------
# Build merge keys from CCD
# -----------------------------------
ccd_merge = ccd_with_county.copy()
# Extract 6-digit LEA code
ccd_merge["lea6"] = (
    ccd_merge["ST_LEAID"]
    .str.split("-").str[-1]
    .str.zfill(6)
)
cep_mo["lea6"] = cep_mo["lea_id"].str.replace("-", "", regex=False).str.zfill(6)
# Construct a LEA-to-county crosswalk using the modal (most frequent) county
# Because some lead ids have several schools, which is difficult to detect which county each of them is in
lea_county_mode = (
    ccd_merge.dropna(subset=["county_fips"])
      .groupby(["lea6", "county_fips"]).size()
      .reset_index(name="n")
      .sort_values(["lea6", "n"], ascending=[True, False])
      .drop_duplicates("lea6")
      [["lea6", "county_fips"]]
)
# Merge with cep
cep_county_mo = cep_mo.merge(lea_county_mode, on="lea6", how="left")

# sanity checks
print("CEP rows:", len(cep_county_mo))
print("Missing county_fips:", cep_county_mo["county_fips"].isna().sum())
print("Match rate:", 1 - cep_county_mo["county_fips"].isna().mean())
print("Unique counties in CEP:", cep_county_mo["county_fips"].nunique()) # This means about 20 counties are NA (not eligible for CEP)

# Flag LEAs that span multiple counties
lea_county_n = (
    ccd_mo.groupby("lea6")["county_fips"].nunique().reset_index(name="n_counties")
)
multi_lea = set(lea_county_n.loc[lea_county_n["n_counties"] > 1, "lea6"])
cep_county_mo["multi_county_lea"] = cep_county_mo["lea6"].isin(multi_lea)

print("Rows in multi-county LEAs:", cep_county_mo["multi_county_lea"].sum())

# 📌 Bottom line
#✅ It is plausible and expected that some counties have zero eligible CEP schools in the official 2024–25 CEP list.
#That means your ~20 “missing” counties from the CEP dataset are not necessarily missing due to data errors — they may genuinely have no eligible schools.
#This reinforces your earlier reasoning:
# counties with no eligible schools should be treated as undefined/structural rather than as random missing data.

#--------------------------
# Aggregate county data
#---------------------------
cep_county_mo.isna().sum() 
cep_county_mo_clean = cep_county_mo.dropna(subset=["county_fips"]).copy()
cep_county_MO = (
    cep_county_mo_clean
        .groupby("county_fips")
        .agg(
            n_eligible_schools=("school_id", "count"),
            n_participating=("cep_participation", lambda x: (x == "Yes").sum())
        )
        .reset_index()
)

cep_county_MO["cep_school_rate"] = (
    cep_county_MO["n_participating"] / cep_county_MO["n_eligible_schools"]
)

print("Number of counties:", len(cep_county_MO))
print("Mean CEP school rate:", cep_county_MO["cep_school_rate"].mean())
print("Min/Max CEP school rate:",
      cep_county_MO["cep_school_rate"].min(),
      cep_county_MO["cep_school_rate"].max())

cep_county_MO.to_csv(r"..\data\derived-data\cep_county_MO.csv", index=False)

# =====================================
# Cleaning for OLS
# =====================================

# ============================================================
# Paths
# ============================================================
MASTER_DIR = Path(r"..\data\derived-data")
DATA_DIR   = Path(r"..\data\raw-data")

MASTER_PATH = MASTER_DIR / "master_state_merged.csv"

INC_PATH = DATA_DIR / "Household Income.csv"
EMP_PATH = DATA_DIR / "Employment Status.csv"
HH2_PATH = DATA_DIR / "Household Type 2.csv"
HH_PATH  = DATA_DIR / "Houshold Type.csv"
POP_PATH = DATA_DIR / "Population Type.csv"

# ============================================================
# Load master
# ============================================================
master = pd.read_csv(MASTER_PATH)
master["state_name"] = master["state_name"].astype(str).str.strip().str.replace(r"\s+", " ", regex=True)

# numeric cleaner (handles commas, %, blanks, ACS symbols)
clean = lambda s: pd.to_numeric(
    pd.Series(s).astype(str)
      .str.replace(",", "", regex=False)
      .str.replace("%", "", regex=False)
      .str.strip()
      .replace({"(X)": np.nan, "*****": np.nan, "--": np.nan, "nan": np.nan, "": np.nan}),
    errors="coerce"
).values

# ============================================================
# 1 Median household income (row: Households)
# ============================================================
inc = pd.read_csv(INC_PATH)
inc_cols = [c for c in inc.columns if str(c).endswith("!!Median income (dollars)!!Estimate")]
inc_row = inc.loc[1, inc_cols]  # row 1 = Households

inc_df = pd.DataFrame({
    "state_name": [c.split("!!")[0] for c in inc_cols],
    "median_hh_income": clean(inc_row.values)
})
inc_df["state_name"] = inc_df["state_name"].astype(str).str.strip().str.replace(r"\s+", " ", regex=True)

# ============================================================
# 2 Unemployment rate (row: Population 16 years and over)
# ============================================================
emp = pd.read_csv(EMP_PATH)
emp_cols = [c for c in emp.columns if str(c).endswith("!!Unemployment rate!!Estimate")]
emp_row = emp.loc[0, emp_cols]  # row 0 = Population 16+

emp_df = pd.DataFrame({
    "state_name": [c.split("!!")[0] for c in emp_cols],
    "unemployment_rate": clean(emp_row.values)  # percent points
})
emp_df["state_name"] = emp_df["state_name"].astype(str).str.strip().str.replace(r"\s+", " ", regex=True)

# ============================================================
# 3 SNAP households percent (row: Total/Households)
# ============================================================
hh2 = pd.read_csv(HH2_PATH)
snap_cols = [c for c in hh2.columns if str(c).endswith("!!Percent households receiving food stamps/SNAP!!Estimate")]
snap_row = hh2.loc[0, snap_cols]  # row 0 is overall

snap_df = pd.DataFrame({
    "state_name": [c.split("!!")[0] for c in snap_cols],
    "snap_household_pct": clean(snap_row.values)  # percent points
})
snap_df["state_name"] = snap_df["state_name"].astype(str).str.strip().str.replace(r"\s+", " ", regex=True)

# ============================================================
# 4 Single-parent proxy = (Male no spouse) + (Female no spouse)  [percent]
#    (Note: file does NOT contain "with children" breakdown)
# ============================================================
hh = pd.read_csv(HH_PATH)
hhlab = hh["Label (Grouping)"].astype(str)

male_idx = hhlab[hhlab.str.contains("Male householder, no spouse/partner present", regex=False)].index[0]
fem_idx  = hhlab[hhlab.str.contains("Female householder, no spouse/partner present", regex=False)].index[0]

pct_cols = [c for c in hh.columns if str(c).endswith("!!Percent")]
male_row = hh.loc[male_idx, pct_cols]
fem_row  = hh.loc[fem_idx, pct_cols]

sp_df = pd.DataFrame({
    "state_name": [c.split("!!")[0] for c in pct_cols],
    "single_parent_pct": clean(male_row.values) + clean(fem_row.values)  # percent points
})
sp_df["state_name"] = sp_df["state_name"].astype(str).str.strip().str.replace(r"\s+", " ", regex=True)

# ============================================================
# 5 Race/Ethnicity: % Black (African American) and % Hispanic  [percent]
# ============================================================
pop = pd.read_csv(POP_PATH)
poplab = pop["Label (Grouping)"].astype(str)

# Hispanic row
his_idx = poplab[poplab.str.contains("Hispanic or Latino (of any race)", regex=False)].index[0]
# Black row: use "Black or African American alone" if present; else fallback to "Black or African American"
blk_candidates = poplab[poplab.str.contains("Black or African American alone", regex=False)]
blk_idx = blk_candidates.index[0] if len(blk_candidates) > 0 else poplab[poplab.str.contains("Black or African American", regex=False)].index[0]

pop_pct_cols = [c for c in pop.columns if str(c).endswith("!!Percent")]

his_row = pop.loc[his_idx, pop_pct_cols]
blk_row = pop.loc[blk_idx, pop_pct_cols]

race_df = pd.DataFrame({
    "state_name": [c.split("!!")[0] for c in pop_pct_cols],
    "pct_hispanic": clean(his_row.values),
    "pct_black": clean(blk_row.values)
})
race_df["state_name"] = race_df["state_name"].astype(str).str.strip().str.replace(r"\s+", " ", regex=True)

# ============================================================
# Merge controls into master
# ============================================================
master = master.merge(inc_df, on="state_name", how="left")
master = master.merge(emp_df, on="state_name", how="left")
master = master.merge(snap_df, on="state_name", how="left")
master = master.merge(sp_df, on="state_name", how="left")
master = master.merge(race_df, on="state_name", how="left")

# Save merged master
out_path = MASTER_DIR / "master_state_with_controls.csv"
master.to_csv(out_path, index=False)