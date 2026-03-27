# code/app.py
# ============================================================
# Streamlit Dashboard: School Lunch Policy (State + County)
# ------------------------------------------------------------
# Key choices
#   - State plots: Altair
#   - County scatter: Altair
#   - County maps: Matplotlib (geopandas plot) for Streamlit stability
#   - Friendly labels (avoid raw variable names in UI/axes)
#   - Robust to Altair duplicate-name issues by using x_val/y_val fields
#
# Expected repo layout
#   <repo_root>/
#     code/app.py
#     data/
#       raw-data/
#         master_state_with_controls.csv
#         child_pov_il.csv, vote_2024_il.csv, cep_county_IL.csv
#         child_pov_mo.csv, vote_2024_mo.csv, cep_county_MO.csv
#         shp_file/county/tl_2025_us_county.shp (+ .dbf .shx .prj ...)
#       derived-data/ (optional)
#
# Run (from repo root)
#   streamlit run code/app.py
# ============================================================

from pathlib import Path
import numpy as np
import pandas as pd
import streamlit as st

import altair as alt
import geopandas as gpd
import statsmodels.api as sm

import matplotlib.pyplot as plt
from matplotlib.colors import TwoSlopeNorm

import zipfile
import requests

alt.data_transformers.disable_max_rows()

# -----------------------------
# App config
# -----------------------------
st.set_page_config(page_title="School Lunch Policy | Story Dashboard", layout="wide")
st.title("School Lunch Policy Dashboard")
st.caption("By Byeol Choi | Narrative dashboard for state and county patterns in child poverty, food insecurity, and CEP participation")

# -----------------------------
# Paths (repo-safe)
# -----------------------------
REPO_DIR = Path(__file__).resolve().parent.parent
RAW_DIR = REPO_DIR / "data" / "raw-data"
DERIVED_DIR = REPO_DIR / "data" / "derived-data"

CENSUS_COUNTY_ZIP_URL = "https://www2.census.gov/geo/tiger/TIGER2024/COUNTY/tl_2024_us_county.zip"
COUNTY_SHP_LOCAL = RAW_DIR / "shp_file" / "county" / "tl_2025_us_county.shp"
GIS_CACHE_DIR = REPO_DIR / ".cache_gis"


@st.cache_data(show_spinner=True)
def ensure_county_shapefile(local_shp_path: Path, cache_dir: Path) -> Path:
    if local_shp_path.exists():
        return local_shp_path

    cache_dir.mkdir(parents=True, exist_ok=True)

    zip_path = cache_dir / "tl_2024_us_county.zip"
    shp_path = cache_dir / "tl_2024_us_county.shp"

    if not zip_path.exists():
        r = requests.get(CENSUS_COUNTY_ZIP_URL, stream=True, timeout=60)
        r.raise_for_status()

        with open(zip_path, "wb") as f:
            for chunk in r.iter_content(chunk_size=1024 * 1024):
                if chunk:
                    f.write(chunk)

    if not shp_path.exists():
        with zipfile.ZipFile(zip_path, "r") as zf:
            zf.extractall(cache_dir)

    if not shp_path.exists():
        candidates = list(cache_dir.rglob("*.shp"))
        if not candidates:
            raise FileNotFoundError("County shapefile not found.")
        shp_path = candidates[0]

    return shp_path


COUNTY_SHP_PATH = ensure_county_shapefile(
    COUNTY_SHP_LOCAL,
    GIS_CACHE_DIR
)


def pick_csv(fname: str) -> Path:
    """Prefer derived-data, fallback raw-data."""
    p1 = DERIVED_DIR / fname
    p2 = RAW_DIR / fname
    return p1 if p1.exists() else p2


MASTER_STATE_PATH = pick_csv("master_state_with_controls.csv")

CEP_IL = pick_csv("cep_county_IL.csv")
POV_IL = pick_csv("child_pov_il.csv")
VOTE_IL = pick_csv("vote_2024_il.csv")

CEP_MO = pick_csv("cep_county_MO.csv")
POV_MO = pick_csv("child_pov_mo.csv")
VOTE_MO = pick_csv("vote_2024_mo.csv")

# -----------------------------
# Friendly labels
# -----------------------------
STATE_VAR_LABELS = {
    "poverty_rate_children": "Child poverty rate",
    "child_food_insec_rate": "Child food insecurity rate",
    "food_insufficiency_weighted": "Food insufficiency (weighted)",
    "cep_rate_school": "CEP participation rate (schools)",
    "cep_rate_student": "CEP participation rate (students)",
    "dem_margin": "Democratic margin",
    "nslp_total_dollars_per_school_age": "NSLP dollars per school-age child",
    "lunches_per_school_age": "Lunches per school-age child",
    "cash_per_lunch": "Cash subsidy per lunch",
    "commodity_per_lunch": "Commodity value per lunch",
    "total_dollars_per_lunch": "Total value per lunch",
    "median_hh_income_k": "Median household income (thousands)",
    "unemployment_rate": "Unemployment rate",
    "snap_household_pct": "SNAP household share",
    "single_parent_pct": "Single-parent household share",
    "pct_hispanic": "Share Hispanic",
    "pct_black": "Share Black",
}

COUNTY_VAR_LABELS = {
    "cep_school_rate": "CEP participation rate (schools)",
    "poverty_rate_children": "Child poverty rate",
    "dem_margin": "Democratic margin",
}


def label_for(var: str, mapping: dict[str, str]) -> str:
    return mapping.get(var, var)


# ============================================================
# Data helpers
# ============================================================
def _to_numeric_safe(s: pd.Series) -> pd.Series:
    return pd.to_numeric(s, errors="coerce")


def coerce_numeric(df: pd.DataFrame, cols: list[str]) -> pd.DataFrame:
    out = df.copy()
    for c in cols:
        if c in out.columns:
            out[c] = _to_numeric_safe(out[c])
    return out


@st.cache_data(show_spinner=False)
def load_state_master(path: Path) -> pd.DataFrame:
    """Load state master; keep types consistent."""
    df = pd.read_csv(path)

    for c in ["state_abbrev", "state_name"]:
        if c in df.columns:
            df[c] = df[c].astype(str).str.strip()

    df = coerce_numeric(df, list(STATE_VAR_LABELS.keys()))

    for c in ["fips", "state_fips", "STATEFP", "statefp"]:
        if c in df.columns:
            df[c] = _to_numeric_safe(df[c])

    return df


@st.cache_data(show_spinner=False)
def load_county_inputs(
    cep_path: Path, pov_path: Path, vote_path: Path
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """
    Load county CSVs and standardize county_fips.
    """
    cep = pd.read_csv(cep_path).copy()
    pov = pd.read_csv(pov_path).copy()
    vote = pd.read_csv(vote_path).copy()

    for d in (cep, pov, vote):
        if "county_fips" not in d.columns:
            raise ValueError(f"Missing 'county_fips' in columns: {d.columns.tolist()}")
        d["county_fips"] = (
            d["county_fips"].astype(str).str.replace(r"\.0$", "", regex=True).str.zfill(5)
        )

    if "cep_school_rate" in cep.columns:
        cep["cep_school_rate"] = _to_numeric_safe(cep["cep_school_rate"])

    if "poverty_rate_children" in pov.columns:
        pov["poverty_rate_children"] = _to_numeric_safe(pov["poverty_rate_children"])
        if pov["poverty_rate_children"].dropna().max() > 1.5:
            pov["poverty_rate_children"] = pov["poverty_rate_children"] / 100.0

    if "dem_margin" in vote.columns:
        vote["dem_margin"] = _to_numeric_safe(vote["dem_margin"])

    return cep, pov, vote


@st.cache_data(show_spinner=False)
def build_county_gdf_threepanel(
    shp_path: Path,
    cep_path: Path,
    pov_path: Path,
    vote_path: Path,
    statefp: str,
) -> gpd.GeoDataFrame:
    """
    Build county GeoDataFrame for one state and merge in metrics.
    Returns geometry in EPSG:5070 (meters), helpful for simplification.
    """
    cep, pov, vote = load_county_inputs(cep_path, pov_path, vote_path)

    gdf = gpd.read_file(shp_path, engine="pyogrio")

    required = {"STATEFP", "COUNTYFP"}
    if not required.issubset(set(gdf.columns)):
        raise ValueError(f"County shapefile must include {sorted(required)}. Found: {gdf.columns.tolist()}")

    gdf["county_fips"] = (
        gdf["STATEFP"].astype(str).str.zfill(2) +
        gdf["COUNTYFP"].astype(str).str.zfill(3)
    )

    gdf_state = gdf[gdf["STATEFP"].astype(str).str.zfill(2) == str(statefp).zfill(2)].copy()

    metrics = (
        cep[["county_fips", "cep_school_rate"]]
        .merge(pov[["county_fips", "poverty_rate_children"]], on="county_fips", how="left")
        .merge(vote[["county_fips", "dem_margin"]], on="county_fips", how="left")
    )

    gdf_state = gdf_state.merge(metrics, on="county_fips", how="left")

    if gdf_state.crs is None:
        gdf_state = gdf_state.set_crs(epsg=4326, allow_override=True)

    gdf_state = gdf_state.to_crs(epsg=5070)
    gdf_state["geometry"] = gdf_state["geometry"].buffer(0)

    return gdf_state


# ============================================================
# Altair charts (robust to x==y selection)
# ============================================================
def altair_state_scatter_with_regression(
    df: pd.DataFrame,
    x: str,
    y: str,
    label_col: str,
    height: int = 560,
) -> alt.Chart:
    """
    Scatter + regression.
    Use x_val/y_val to avoid duplicate-column errors when x==y.
    """
    d = df[[x, y, label_col]].dropna(subset=[x, y]).copy()

    plot = pd.DataFrame({
        "x_val": d[x].values,
        "y_val": d[y].values,
        "label": d[label_col].astype(str).values,
    })

    base = alt.Chart(plot).encode(
        x=alt.X("x_val:Q", title=label_for(x, STATE_VAR_LABELS)),
        y=alt.Y("y_val:Q", title=label_for(y, STATE_VAR_LABELS)),
        tooltip=[
            alt.Tooltip("label:N", title="State"),
            alt.Tooltip("x_val:Q", title=label_for(x, STATE_VAR_LABELS), format=".3f"),
            alt.Tooltip("y_val:Q", title=label_for(y, STATE_VAR_LABELS), format=".3f"),
        ],
    )

    pts = base.mark_circle(size=70, opacity=0.85)
    reg = base.transform_regression("x_val", "y_val").mark_line()

    return (pts + reg).properties(height=height)


def altair_state_choropleth(
    df: pd.DataFrame,
    value_col: str,
    title: str,
    height: int = 620,
) -> alt.Chart:
    """
    State choropleth using US Atlas TopoJSON + lookup.
    Requires a numeric state id key: fips/state_fips/STATEFP/statefp.
    """
    d = df.copy()
    key_candidates = ["fips", "state_fips", "STATEFP", "statefp"]
    key_col = next((c for c in key_candidates if c in d.columns), None)
    if key_col is None:
        raise ValueError("Need a state FIPS key column (e.g., 'fips' or 'state_fips').")

    d[key_col] = _to_numeric_safe(d[key_col])
    d[value_col] = _to_numeric_safe(d[value_col])
    d = d.dropna(subset=[key_col]).copy()

    states = alt.topo_feature(
        "https://cdn.jsdelivr.net/npm/us-atlas@3/states-10m.json",
        "states"
    )

    base = alt.Chart(states).mark_geoshape(stroke="white", strokeWidth=0.5).properties(height=height)

    colored = (
        base.transform_lookup(
            lookup="id",
            from_=alt.LookupData(d, key=key_col, fields=[value_col, "state_name", "state_abbrev"]),
        )
        .encode(
            color=alt.Color(
                f"{value_col}:Q",
                title=label_for(value_col, STATE_VAR_LABELS),
                scale=alt.Scale(scheme="blues"),
            ),
            tooltip=[
                alt.Tooltip("state_name:N", title="State"),
                alt.Tooltip(f"{value_col}:Q", title=label_for(value_col, STATE_VAR_LABELS), format=".3f"),
            ],
        )
        .properties(title=title)
    )
    return colored


def altair_county_scatter(
    county_df: pd.DataFrame,
    x: str,
    y: str,
    height: int = 760,
) -> alt.Chart:
    """
    County scatter using x_val/y_val to avoid duplicate-column errors.
    """
    d = county_df.dropna(subset=[x, y]).copy()

    plot = pd.DataFrame({
        "x_val": d[x].values,
        "y_val": d[y].values,
        "dem_margin": d["dem_margin"].values if "dem_margin" in d.columns else np.nan,
        "county_fips": d["county_fips"].astype(str).values if "county_fips" in d.columns else "",
    })

    return (
        alt.Chart(plot)
        .mark_circle(size=70, opacity=0.85)
        .encode(
            x=alt.X("x_val:Q", title=label_for(x, COUNTY_VAR_LABELS)),
            y=alt.Y("y_val:Q", title=label_for(y, COUNTY_VAR_LABELS)),
            color=alt.Color(
                "dem_margin:Q",
                title=COUNTY_VAR_LABELS["dem_margin"],
                scale=alt.Scale(scheme="redblue", domainMid=0),
            ),
            tooltip=[
                alt.Tooltip("county_fips:N", title="County FIPS"),
                alt.Tooltip("x_val:Q", title=label_for(x, COUNTY_VAR_LABELS), format=".3f"),
                alt.Tooltip("y_val:Q", title=label_for(y, COUNTY_VAR_LABELS), format=".3f"),
                alt.Tooltip("dem_margin:Q", title=COUNTY_VAR_LABELS["dem_margin"], format=".2f"),
            ],
        )
        .properties(height=height)
    )


# ============================================================
# Matplotlib county maps (3 panels)
# ============================================================
def county_maps_three_panels_matplotlib(
    gdf_5070: gpd.GeoDataFrame,
    state_title: str,
    simplify_tol_m: float = 12000.0,
) -> plt.Figure:
    """
    Draw 3 county maps with GeoPandas + Matplotlib.
    Panels:
      - CEP (cep_school_rate, 0-1)
      - Child poverty (poverty_rate_children, 0-1)
      - Dem margin (dem_margin, diverging around 0)

    Geometry:
      - simplify in EPSG:5070 meters (optional) to keep rendering fast
    """
    gdf = gdf_5070.copy()
    gdf["geometry"] = gdf["geometry"].buffer(0)

    if simplify_tol_m and simplify_tol_m > 0:
        try:
            gdf["geometry"] = gdf["geometry"].simplify(float(simplify_tol_m), preserve_topology=True)
        except Exception:
            pass

    fig = plt.figure(figsize=(18, 7.2), dpi=140)
    gs = fig.add_gridspec(1, 3, wspace=0.08)

    ax1 = fig.add_subplot(gs[0, 0])
    ax2 = fig.add_subplot(gs[0, 1])
    ax3 = fig.add_subplot(gs[0, 2])

    for ax in (ax1, ax2, ax3):
        ax.set_axis_off()

    fig.suptitle(state_title, fontsize=14, y=0.98)

    ax1.set_title("CEP", fontsize=12)
    m1 = gdf.plot(
        column="cep_school_rate",
        ax=ax1,
        cmap="Blues",
        vmin=0, vmax=1,
        missing_kwds={"color": "#e0e0e0", "label": "Missing"},
        linewidth=0.25,
        edgecolor="#666666",
    )
    cb1 = fig.colorbar(m1.collections[0], ax=ax1, fraction=0.035, pad=0.01)
    cb1.ax.tick_params(labelsize=9)
    cb1.set_label(COUNTY_VAR_LABELS["cep_school_rate"], fontsize=10)

    ax2.set_title("Child poverty", fontsize=12)
    m2 = gdf.plot(
        column="poverty_rate_children",
        ax=ax2,
        cmap="Reds",
        vmin=0, vmax=1,
        missing_kwds={"color": "#e0e0e0", "label": "Missing"},
        linewidth=0.25,
        edgecolor="#666666",
    )
    cb2 = fig.colorbar(m2.collections[0], ax=ax2, fraction=0.035, pad=0.01)
    cb2.ax.tick_params(labelsize=9)
    cb2.set_label(COUNTY_VAR_LABELS["poverty_rate_children"], fontsize=10)

    ax3.set_title("Political leaning", fontsize=12)
    dem = pd.to_numeric(gdf["dem_margin"], errors="coerce")
    max_abs = np.nanmax(np.abs(dem.values)) if np.isfinite(dem).any() else 1.0
    max_abs = float(max(max_abs, 0.5))
    norm = TwoSlopeNorm(vmin=-max_abs, vcenter=0.0, vmax=max_abs)

    m3 = gdf.plot(
        column="dem_margin",
        ax=ax3,
        cmap="RdBu",
        norm=norm,
        missing_kwds={"color": "#e0e0e0", "label": "Missing"},
        linewidth=0.25,
        edgecolor="#666666",
    )
    cb3 = fig.colorbar(m3.collections[0], ax=ax3, fraction=0.035, pad=0.01)
    cb3.ax.tick_params(labelsize=9)
    cb3.set_label(COUNTY_VAR_LABELS["dem_margin"], fontsize=10)

    return fig


# ============================================================
# OLS helpers (tables)
# ============================================================
def run_ols_table_state(df: pd.DataFrame, y: str, x_main: list[str], controls: list[str]) -> pd.DataFrame:
    cols = [y] + x_main + controls
    cols = [c for c in cols if c in df.columns]
    d = df[cols].dropna().copy()

    if y not in d.columns or len(d) < 5:
        return pd.DataFrame({
            "term": ["(insufficient data)"],
            "coef": [np.nan],
            "std_err": [np.nan],
            "t": [np.nan],
            "p_value": [np.nan],
            "n": [len(d)]
        })

    X = d[[c for c in cols if c != y]].copy()
    X = sm.add_constant(X, has_constant="add")
    yvec = d[y].copy()

    m = sm.OLS(yvec, X).fit()

    out = pd.DataFrame({
        "term": m.params.index,
        "coef": m.params.values,
        "std_err": m.bse.values,
        "t": m.tvalues.values,
        "p_value": m.pvalues.values,
    })
    out["n"] = int(m.nobs)

    def friendly_term(t: str) -> str:
        if t == "const":
            return "Intercept"
        return STATE_VAR_LABELS.get(t, t)

    out["term"] = out["term"].map(friendly_term)
    out["coef"] = out["coef"].round(4)
    out["std_err"] = out["std_err"].round(4)
    out["t"] = out["t"].round(3)
    out["p_value"] = out["p_value"].round(4)

    return out


def run_ols_table_county(county_df: pd.DataFrame, y: str, x: str) -> pd.DataFrame:
    needed = ["dem_margin", y, x]
    d = county_df.dropna(subset=[c for c in needed if c in county_df.columns]).copy()

    if len(d) < 5:
        return pd.DataFrame({
            "term": ["(insufficient data)"],
            "coef": [np.nan],
            "std_err": [np.nan],
            "t": [np.nan],
            "p_value": [np.nan],
            "n": [len(d)]
        })

    X = d[[x, "dem_margin"]].copy()
    X = sm.add_constant(X, has_constant="add")
    yvec = d[y].copy()

    m = sm.OLS(yvec, X).fit()

    out = pd.DataFrame({
        "term": m.params.index,
        "coef": m.params.values,
        "std_err": m.bse.values,
        "t": m.tvalues.values,
        "p_value": m.pvalues.values,
    })
    out["n"] = int(m.nobs)

    def friendly_term(t: str) -> str:
        if t == "const":
            return "Intercept"
        if t in COUNTY_VAR_LABELS:
            return COUNTY_VAR_LABELS[t]
        return t

    out["term"] = out["term"].map(friendly_term)
    out["coef"] = out["coef"].round(4)
    out["std_err"] = out["std_err"].round(4)
    out["t"] = out["t"].round(3)
    out["p_value"] = out["p_value"].round(4)

    return out


def safe_corr(df: pd.DataFrame, x: str, y: str) -> float:
    d = df[[x, y]].dropna()
    if len(d) < 3:
        return np.nan
    return float(d[x].corr(d[y]))


def format_signed(value: float, digits: int = 2) -> str:
    if pd.isna(value):
        return "N/A"
    return f"{value:+.{digits}f}"


def summarize_state_story(df: pd.DataFrame, x_var: str, y_var: str) -> dict[str, object]:
    d = df[[c for c in ["state_name", x_var, y_var] if c in df.columns]].dropna().copy()
    corr = safe_corr(d, x_var, y_var)
    out = {"corr": corr, "highest_x": None, "highest_y": None}

    if len(d) == 0:
        return out

    if "state_name" in d.columns:
        out["highest_x"] = d.loc[d[x_var].idxmax(), "state_name"]
        out["highest_y"] = d.loc[d[y_var].idxmax(), "state_name"]
    return out


def summarize_county_story(county_df: pd.DataFrame) -> dict[str, object]:
    d = county_df[[c for c in ["county_fips", "cep_school_rate", "poverty_rate_children", "dem_margin"] if c in county_df.columns]].dropna().copy()
    out = {
        "corr_cep_poverty": np.nan,
        "corr_margin_poverty": np.nan,
        "top_poverty_county": None,
        "top_cep_county": None,
    }
    if len(d) == 0:
        return out

    out["corr_cep_poverty"] = safe_corr(d, "cep_school_rate", "poverty_rate_children") if {"cep_school_rate", "poverty_rate_children"}.issubset(d.columns) else np.nan
    out["corr_margin_poverty"] = safe_corr(d, "dem_margin", "poverty_rate_children") if {"dem_margin", "poverty_rate_children"}.issubset(d.columns) else np.nan
    if "county_fips" in d.columns:
        out["top_poverty_county"] = d.loc[d["poverty_rate_children"].idxmax(), "county_fips"]
        out["top_cep_county"] = d.loc[d["cep_school_rate"].idxmax(), "county_fips"]
    return out


def narrative_intro() -> None:
    st.markdown(
        """
        This dashboard is designed to do two things: show where child need is concentrated and show how school lunch support compares across places.
        Use **Story view** for a guided narrative, then switch to **Explore view** to test alternative variable combinations.
        """
    )


def metric_card_row(items: list[tuple[str, str, str]]) -> None:
    cols = st.columns(len(items))
    for col, (label, value, help_text) in zip(cols, items):
        col.metric(label, value, help=help_text)


# ============================================================
# Load state data
# ============================================================
if not MASTER_STATE_PATH.exists():
    st.error(f"State master CSV not found:\n{MASTER_STATE_PATH}")
    st.stop()

state_df = load_state_master(MASTER_STATE_PATH)

# ============================================================
# Sidebar navigation
# ============================================================
st.sidebar.markdown("## Dashboard controls")
view_mode = st.sidebar.radio("View mode", ["Story view", "Explore view"], index=0)
level = st.sidebar.radio("Analysis level", ["State level", "County level"])


# ============================================================
# STATE LEVEL VIEW
# ============================================================
if level == "State level":
    st.sidebar.markdown("### State-level settings")

    x_candidates = [c for c in STATE_VAR_LABELS.keys() if c in state_df.columns]
    y_candidates = [c for c in ["poverty_rate_children", "child_food_insec_rate", "food_insufficiency_weighted"] if c in state_df.columns]

    if not x_candidates or not y_candidates:
        st.error("State master is missing expected columns. Check master_state_with_controls.csv.")
        st.stop()

    default_x = "cep_rate_school" if "cep_rate_school" in x_candidates else x_candidates[0]
    default_y = "child_food_insec_rate" if "child_food_insec_rate" in y_candidates else y_candidates[0]

    x_var = st.sidebar.selectbox(
        "X variable",
        x_candidates,
        index=x_candidates.index(default_x),
        format_func=lambda v: label_for(v, STATE_VAR_LABELS),
    )

    y_candidates_filtered = [v for v in y_candidates if v != x_var] or y_candidates
    default_y_filtered = default_y if default_y in y_candidates_filtered else y_candidates_filtered[0]
    y_var = st.sidebar.selectbox(
        "Y variable",
        y_candidates_filtered,
        index=y_candidates_filtered.index(default_y_filtered),
        format_func=lambda v: label_for(v, STATE_VAR_LABELS),
    )

    control_pool = [c for c in ["median_hh_income_k", "unemployment_rate", "snap_household_pct", "single_parent_pct", "pct_hispanic", "pct_black", "dem_margin"] if c in state_df.columns]
    controls = st.sidebar.multiselect(
        "OLS controls (optional)",
        options=control_pool,
        default=[c for c in control_pool if c in ["median_hh_income_k", "unemployment_rate"]],
        format_func=lambda v: label_for(v, STATE_VAR_LABELS),
    )

    label_col = "state_name" if "state_name" in state_df.columns else ("state_abbrev" if "state_abbrev" in state_df.columns else None)
    if label_col is None:
        state_df["_label_tmp"] = np.arange(len(state_df)).astype(str)
        label_col = "_label_tmp"

    story = summarize_state_story(state_df, x_var, y_var)

    if view_mode == "Story view":
        narrative_intro()
        st.markdown("### What this view is showing")
        st.write(
            f"This comparison centers on **{label_for(x_var, STATE_VAR_LABELS)}** and **{label_for(y_var, STATE_VAR_LABELS)}**. "
            "The goal is to see whether states with stronger lunch-policy coverage also look different on child need outcomes."
        )
        metric_card_row([
            (
                "Correlation",
                format_signed(story["corr"], 2),
                f"Linear association between {label_for(x_var, STATE_VAR_LABELS)} and {label_for(y_var, STATE_VAR_LABELS)}.",
            ),
            (
                f"Highest {label_for(x_var, STATE_VAR_LABELS)}",
                str(story["highest_x"] or "N/A"),
                "State with the highest value on the selected X variable.",
            ),
            (
                f"Highest {label_for(y_var, STATE_VAR_LABELS)}",
                str(story["highest_y"] or "N/A"),
                "State with the highest value on the selected Y variable.",
            ),
        ])

        left, right = st.columns([1.2, 1.0], gap="large")
        with left:
            st.subheader("1. Cross-state relationship")
            st.altair_chart(
                altair_state_scatter_with_regression(state_df, x=x_var, y=y_var, label_col=label_col, height=500),
                use_container_width=True,
            )
            st.caption("Each point is a state. The fitted line helps you see the overall direction without losing the individual observations.")

        with right:
            st.subheader("2. Geographic pattern")
            try:
                title = f"{label_for(x_var, STATE_VAR_LABELS)} by state"
                st.altair_chart(
                    altair_state_choropleth(state_df, value_col=x_var, title=title, height=560),
                    use_container_width=True,
                )
            except Exception as e:
                st.info("State choropleth not available (missing a usable state FIPS key).")
                with st.expander("Details"):
                    st.write(str(e))

        st.subheader("3. Model summary")
        st.write(
            "The table below estimates the association between the selected outcome and your chosen predictor, with optional controls. "
            "This is useful for a quick directional check, not a causal claim."
        )
        ols_tbl = run_ols_table_state(state_df, y=y_var, x_main=[x_var], controls=controls)
        st.dataframe(ols_tbl, use_container_width=True)

    else:
        left, right = st.columns([1.1, 1.0], gap="large")

        with left:
            st.subheader("State scatter")
            st.altair_chart(
                altair_state_scatter_with_regression(state_df, x=x_var, y=y_var, label_col=label_col, height=560),
                use_container_width=True,
            )

            st.subheader("OLS table")
            ols_tbl = run_ols_table_state(state_df, y=y_var, x_main=[x_var], controls=controls)
            st.dataframe(ols_tbl, use_container_width=True)

        with right:
            st.subheader("State choropleth")
            try:
                title = f"{label_for(x_var, STATE_VAR_LABELS)} by state"
                st.altair_chart(
                    altair_state_choropleth(state_df, value_col=x_var, title=title, height=620),
                    use_container_width=True,
                )
            except Exception as e:
                st.info("State choropleth not available (missing a usable state FIPS key).")
                with st.expander("Details"):
                    st.write(str(e))


# ============================================================
# COUNTY LEVEL VIEW
# ============================================================
else:
    st.sidebar.markdown("### County-level settings")

    state_choice = st.sidebar.selectbox("Select state", ["Illinois (IL)", "Missouri (MO)"], index=0)

    simplify_tol_m = st.sidebar.slider(
        "Geometry simplification (meters)",
        min_value=0,
        max_value=25000,
        value=8000,
        step=1000,
        help="Higher value simplifies boundaries and speeds rendering.",
    )

    if not COUNTY_SHP_PATH.exists():
        st.error(f"County shapefile not found:\n{COUNTY_SHP_PATH}")
        st.stop()

    if "Illinois" in state_choice:
        cep_path, pov_path, vote_path = CEP_IL, POV_IL, VOTE_IL
        statefp = "17"
        map_title = "Illinois counties"
    else:
        cep_path, pov_path, vote_path = CEP_MO, POV_MO, VOTE_MO
        statefp = "29"
        map_title = "Missouri counties"

    missing = [p for p in [cep_path, pov_path, vote_path] if not p.exists()]
    if missing:
        st.error("Missing required county CSV(s):\n" + "\n".join([str(m) for m in missing]))
        st.stop()

    gdf_state = build_county_gdf_threepanel(
        shp_path=COUNTY_SHP_PATH,
        cep_path=cep_path,
        pov_path=pov_path,
        vote_path=vote_path,
        statefp=statefp,
    )

    cep, pov, vote = load_county_inputs(cep_path, pov_path, vote_path)
    county_df = (
        cep[["county_fips", "cep_school_rate"]]
        .merge(pov[["county_fips", "poverty_rate_children"]], on="county_fips", how="left")
        .merge(vote[["county_fips", "dem_margin"]], on="county_fips", how="left")
    )

    x_opts = [v for v in ["cep_school_rate", "dem_margin"] if v in county_df.columns]
    y_opts = [v for v in ["poverty_rate_children"] if v in county_df.columns]

    x_var = st.sidebar.selectbox("Scatter X axis", x_opts, index=0, format_func=lambda v: label_for(v, COUNTY_VAR_LABELS))
    y_var = st.sidebar.selectbox("Scatter Y axis", y_opts, index=0, format_func=lambda v: label_for(v, COUNTY_VAR_LABELS))

    county_story = summarize_county_story(county_df)

    if view_mode == "Story view":
        narrative_intro()
        st.markdown(f"### County story: {state_choice}")
        st.write(
            "This section compares county-level CEP participation, child poverty, and political context. "
            "Read the maps first, then use the scatter to see how those county patterns line up numerically."
        )

        metric_card_row([
            (
                "CEP ↔ Poverty correlation",
                format_signed(county_story["corr_cep_poverty"], 2),
                "Association between county CEP participation and child poverty.",
            ),
            (
                "Politics ↔ Poverty correlation",
                format_signed(county_story["corr_margin_poverty"], 2),
                "Association between county Democratic margin and child poverty.",
            ),
            (
                "Highest-poverty county",
                str(county_story["top_poverty_county"] or "N/A"),
                "County FIPS with the highest child poverty rate in the selected state.",
            ),
            (
                "Highest-CEP county",
                str(county_story["top_cep_county"] or "N/A"),
                "County FIPS with the highest CEP participation rate in the selected state.",
            ),
        ])

        left, right = st.columns([1.6, 1.0], gap="large")
        with left:
            st.subheader("1. County maps")
            fig = county_maps_three_panels_matplotlib(
                gdf_5070=gdf_state,
                state_title=map_title,
                simplify_tol_m=float(simplify_tol_m),
            )
            st.pyplot(fig, use_container_width=True)
            plt.close(fig)
            st.caption("Read the three panels together: CEP participation, child poverty, and political leaning may overlap in some areas and diverge in others.")

        with right:
            st.subheader("2. County scatter")
            st.altair_chart(
                altair_county_scatter(county_df, x=x_var, y=y_var, height=620),
                use_container_width=True,
            )
            st.caption("Dots are counties, colored by political leaning. This helps separate geographic clustering from the broader county-level relationship.")

        st.subheader("3. Model summary")
        st.write(
            "The OLS table uses the selected X variable together with political leaning to summarize county-level relationships. "
            "Treat this as a compact descriptive model."
        )
        ols_tbl = run_ols_table_county(county_df, y=y_var, x=x_var)
        st.dataframe(ols_tbl, use_container_width=True)

    else:
        left, right = st.columns([1.6, 1.0], gap="large")

        with left:
            st.subheader("County maps")
            fig = county_maps_three_panels_matplotlib(
                gdf_5070=gdf_state,
                state_title=map_title,
                simplify_tol_m=float(simplify_tol_m),
            )
            st.pyplot(fig, use_container_width=True)
            plt.close(fig)

        with right:
            st.subheader("County scatter")
            st.altair_chart(
                altair_county_scatter(county_df, x=x_var, y=y_var, height=760),
                use_container_width=True,
            )

            st.subheader("OLS table")
            ols_tbl = run_ols_table_county(county_df, y=y_var, x=x_var)
            st.dataframe(ols_tbl, use_container_width=True)