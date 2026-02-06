
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

import streamlit as st
import pandas as pd
import numpy as np

from utils import (
    read_purchase_file, clean_amount, standardize_date,
    harmonize_names, normalize_description, is_master_like_column,
    parse_fx_to_inr, convert_currency
)

st.set_page_config(page_title="Data Harmonization", page_icon="🧹", layout="wide")
st.title("🧹 App 1 — Data Harmonization")
st.caption("Select which fields/actions to harmonize. Output file will keep ALL rows (changed + unchanged).")

uploaded = st.file_uploader("Upload Purchase Register (CSV/XLSX)", type=["csv", "xlsx", "xls"])
if not uploaded:
    st.info("Upload a purchase register to start.")
    st.stop()

df = read_purchase_file(uploaded)
st.success(f"Loaded {len(df):,} rows × {df.shape[1]} columns")
st.dataframe(df.head(20), use_container_width=True)

# -----------------------------
# Column Mapping (keep master data untouched)
# -----------------------------
st.subheader("1) Column Mapping (fields used for harmonization)")
cols = list(df.columns)

amount_col = st.selectbox("Amount column (Required)", ["(select)"] + cols)
date_col = st.selectbox("Date column (Optional)", ["(none)"] + cols)
desc_col = st.selectbox("Material/Service Description column (Optional)", ["(none)"] + cols)
supplier_col = st.selectbox("Supplier/Vendor column (Optional)", ["(none)"] + cols)
dept_col = st.selectbox("Department/Cost Center column (Optional)", ["(none)"] + cols)
plant_col = st.selectbox("Plant/Site column (Optional)", ["(none)"] + cols)
capex_col = st.selectbox("CAPEX/OPEX column (Optional)", ["(none)"] + cols)

# Currency optional now; future-ready
currency_col = st.selectbox("Currency column (Optional - for later)", ["(none)"] + cols)

if amount_col == "(select)":
    st.error("Amount column is required.")
    st.stop()

# -----------------------------
# Actions selection
# -----------------------------
st.subheader("2) Select Harmonization Actions (multi-select)")

actions = st.multiselect(
    "Choose what to harmonize",
    options=[
        "Standardize Date Format",
        "Harmonize Supplier Names (fuzzy)",
        "Harmonize Department Names (fuzzy)",
        "Harmonize Plant Names (fuzzy)",
        "Normalize Description (light)",
        "Drop Rows with Missing Required Fields",
        "Convert Currency to Target"
    ],
    default=["Standardize Date Format", "Harmonize Supplier Names (fuzzy)", "Drop Rows with Missing Required Fields"]
)

dayfirst = st.checkbox("Day-first date parsing (dd-mm-yyyy)", value=True) if "Standardize Date Format" in actions else True
fuzzy_threshold = st.slider("Fuzzy match threshold", 0.80, 0.98, 0.92, 0.01) if any("Harmonize" in a for a in actions) else 0.92

# -----------------------------
# Currency target selection
# -----------------------------
target_currency = "INR"
default_source_currency = "INR"
fx_to_inr = {"INR": 1.0}

if "Convert Currency to Target" in actions:
    st.subheader("3) Currency Conversion (Target Currency)")

    default_source_currency = st.selectbox(
        "Default SOURCE currency (used if Currency column missing or blank)",
        ["INR", "USD", "EUR", "GBP", "AED", "SGD"],
        index=0
    )
    target_currency = st.selectbox(
        "TARGET currency (output spend currency)",
        ["INR", "USD", "EUR", "GBP", "AED", "SGD"],
        index=0
    )

    with st.expander("FX Table (Rates to INR) — required for conversion", expanded=True):
        st.caption("Enter FX as INR per 1 unit. Example: USD=83.2")
        fx_text = st.text_area(
            "FX rates (to INR)",
            value="INR=1.0\nUSD=83.0\nEUR=90.0\nGBP=105.0\nAED=22.6\nSGD=61.5"
        )
        fx_to_inr = parse_fx_to_inr(fx_text)
        if "INR" not in fx_to_inr:
            fx_to_inr["INR"] = 1.0

# -----------------------------
# Run Harmonization
# -----------------------------
if st.button("Run Harmonization ✅", type="primary"):
    out = df.copy()  # keep ALL original columns as-is (master data untouched)

    # Amount standardized always (needed for spend)
    out["_amount_clean"] = clean_amount(out[amount_col])

    # Date standardization
    if "Standardize Date Format" in actions and date_col != "(none)":
        out["_date_std"] = standardize_date(out[date_col], dayfirst=dayfirst)
        out["_date_iso"] = out["_date_std"].dt.strftime("%Y-%m-%d")
        out["_date_changed"] = out[date_col].astype(str).str.strip().ne(out["_date_iso"].astype(str).str.strip())
    else:
        out["_date_std"] = pd.NaT
        out["_date_iso"] = ""
        out["_date_changed"] = False

    # Description normalization (light; no fuzzy grouping)
    if "Normalize Description (light)" in actions and desc_col != "(none)":
        out["_desc_h"] = normalize_description(out[desc_col])
        out["_desc_changed"] = out["_desc_h"].astype(str).str.strip().ne(out[desc_col].astype(str).str.strip())
    elif desc_col != "(none)":
        out["_desc_h"] = out[desc_col].astype(str)
        out["_desc_changed"] = False
    else:
        out["_desc_h"] = ""
        out["_desc_changed"] = False

    # Supplier harmonization
    if "Harmonize Supplier Names (fuzzy)" in actions and supplier_col != "(none)":
        # Safety: don't allow master-like columns (IDs)
        if is_master_like_column(supplier_col):
            st.warning(f"'{supplier_col}' looks like master/ID column. It will not be harmonized.")
            out["_supplier_h"] = out[supplier_col].astype(str)
            out["_supplier_changed"] = False
            map_sup = pd.DataFrame()
        else:
            out["_supplier_h"], map_sup, chg = harmonize_names(out[supplier_col], threshold=fuzzy_threshold)
            out["_supplier_changed"] = chg
    elif supplier_col != "(none)":
        out["_supplier_h"] = out[supplier_col].astype(str)
        out["_supplier_changed"] = False
        map_sup = pd.DataFrame()
    else:
        out["_supplier_h"] = "Unknown"
        out["_supplier_changed"] = False
        map_sup = pd.DataFrame()

    # Dept harmonization
    if "Harmonize Department Names (fuzzy)" in actions and dept_col != "(none)":
        if is_master_like_column(dept_col):
            st.warning(f"'{dept_col}' looks like master/ID column. It will not be harmonized.")
            out["_dept_h"] = out[dept_col].astype(str)
            out["_dept_changed"] = False
            map_dept = pd.DataFrame()
        else:
            out["_dept_h"], map_dept, chg = harmonize_names(out[dept_col], threshold=fuzzy_threshold)
            out["_dept_changed"] = chg
    elif dept_col != "(none)":
        out["_dept_h"] = out[dept_col].astype(str)
        out["_dept_changed"] = False
        map_dept = pd.DataFrame()
    else:
        out["_dept_h"] = "Unknown"
        out["_dept_changed"] = False
        map_dept = pd.DataFrame()

    # Plant harmonization
    if "Harmonize Plant Names (fuzzy)" in actions and plant_col != "(none)":
        if is_master_like_column(plant_col):
            st.warning(f"'{plant_col}' looks like master/ID column. It will not be harmonized.")
            out["_plant_h"] = out[plant_col].astype(str)
            out["_plant_changed"] = False
            map_plant = pd.DataFrame()
        else:
            out["_plant_h"], map_plant, chg = harmonize_names(out[plant_col], threshold=fuzzy_threshold)
            out["_plant_changed"] = chg
    elif plant_col != "(none)":
        out["_plant_h"] = out[plant_col].astype(str)
        out["_plant_changed"] = False
        map_plant = pd.DataFrame()
    else:
        out["_plant_h"] = "Unknown"
        out["_plant_changed"] = False
        map_plant = pd.DataFrame()

    # CAPEX/OPEX pass-through (no harmonization by default)
    if capex_col != "(none)":
        out["_capexopex"] = out[capex_col].astype(str)
    else:
        out["_capexopex"] = "Unknown"

    # Currency conversion (optional)
    if "Convert Currency to Target" in actions:
        src_currency_series = out[currency_col] if currency_col != "(none)" else None
        out["_spend"], out["_currency_source_used"], out["_currency_target"], out["_missing_fx"] = convert_currency(
            amount=out["_amount_clean"],
            source_currency=src_currency_series,
            target_currency=target_currency,
            fx_to_inr=fx_to_inr,
            default_source=default_source_currency
        )
    else:
        # Default: INR assumption
        out["_spend"] = out["_amount_clean"]
        out["_currency_source_used"] = "INR"
        out["_currency_target"] = "INR"
        out["_missing_fx"] = False

    # Drop missing rows (optional)
    if "Drop Rows with Missing Required Fields" in actions:
        before = len(out)
        required_cols = ["_spend"]
        if date_col != "(none)" and "Standardize Date Format" in actions:
            required_cols.append("_date_std")
        if supplier_col != "(none)":
            required_cols.append("_supplier_h")
        if desc_col != "(none)":
            required_cols.append("_desc_h")

        out = out.dropna(subset=required_cols)
        out = out[out["_spend"].notna()]
        after = len(out)
        st.info(f"Dropped {before-after:,} rows due to missing required fields.")
    else:
        st.info("No rows dropped. Output retains all rows.")

    # Ensure output is the full dataset after harmonization (changed + unchanged)
    # Add a combined "any change" flag:
    out["_any_harmonized"] = (
        out.get("_supplier_changed", False) |
        out.get("_dept_changed", False) |
        out.get("_plant_changed", False) |
        out.get("_desc_changed", False) |
        out.get("_date_changed", False)
    )

    # Store for next apps
    st.session_state["df_harmonized"] = out

    # Output summary
    st.success("✅ Harmonization completed. Output retains ALL rows (changed + unchanged).")
    st.write("Rows in output:", len(out))
    st.write("Rows changed (any harmonization):", int(out["_any_harmonized"].sum()))

    st.subheader("Preview (harmonized columns + flags)")
    preview_cols = []
    if date_col != "(none)":
        preview_cols += ["_date_iso", "_date_changed"]
    preview_cols += ["_spend", "_currency_target", "_missing_fx", "_any_harmonized"]
    if supplier_col != "(none)":
        preview_cols += ["_supplier_h", "_supplier_changed"]
    if dept_col != "(none)":
        preview_cols += ["_dept_h", "_dept_changed"]
    if plant_col != "(none)":
        preview_cols += ["_plant_h", "_plant_changed"]
    if desc_col != "(none)":
        preview_cols += ["_desc_h", "_desc_changed"]

    st.dataframe(out[preview_cols].head(50), use_container_width=True)

    # Mapping previews
    with st.expander("Harmonization Mapping Tables (samples)", expanded=False):
        if "Harmonize Supplier Names (fuzzy)" in actions and supplier_col != "(none)" and not map_sup.empty:
            st.markdown("**Supplier mapping (sample)**")
            st.dataframe(map_sup.head(60), use_container_width=True)
        if "Harmonize Department Names (fuzzy)" in actions and dept_col != "(none)" and not map_dept.empty:
            st.markdown("**Department mapping (sample)**")
            st.dataframe(map_dept.head(60), use_container_width=True)
        if "Harmonize Plant Names (fuzzy)" in actions and plant_col != "(none)" and not map_plant.empty:
            st.markdown("**Plant mapping (sample)**")
            st.dataframe(map_plant.head(60), use_container_width=True)

    # Download harmonized file
