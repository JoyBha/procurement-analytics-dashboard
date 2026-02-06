# -*- coding: utf-8 -*-
import sys
from pathlib import Path

# Ensure repo root is importable (so "import utils" works from pages/)
ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

import streamlit as st
import pandas as pd

from utils import (
    read_purchase_file, clean_amount, standardize_date,
    harmonize_names, normalize_description
)

st.set_page_config(page_title="Data Harmonization", page_icon="🧹", layout="wide")  # page config supported by Streamlit [3](https://typethepipe.com/post/streamlit-chat-conversational-app-st-chat_message/)
st.title("🧹 App 1 — Data Harmonization")
st.caption("Standardizes Supplier Name, Short Material Description, and Date Format (no user field selection).")

uploaded = st.file_uploader("Upload Purchase Register (CSV/XLSX)", type=["csv", "xlsx", "xls"])
if not uploaded:
    st.info("Upload a purchase register to start.")
    st.stop()

df = read_purchase_file(uploaded)
st.success(f"Loaded {len(df):,} rows × {df.shape[1]} columns")
st.dataframe(df.head(20), use_container_width=True)

st.subheader("Column Mapping (Required for harmonization)")
cols = list(df.columns)

amount_col = st.selectbox("Amount column (Required)", ["(select)"] + cols)
supplier_col = st.selectbox("Supplier Name column (Required)", ["(select)"] + cols)
short_desc_col = st.selectbox("Short Material Description column (Required)", ["(select)"] + cols)
date_col = st.selectbox("Date column (Required)", ["(select)"] + cols)

# Optional pass-through dims (not harmonized here; just kept for downstream use)
dept_col = st.selectbox("Department/Cost Center (Optional)", ["(none)"] + cols)
plant_col = st.selectbox("Plant/Site (Optional)", ["(none)"] + cols)
capex_col = st.selectbox("CAPEX/OPEX (Optional)", ["(none)"] + cols)

if "(select)" in [amount_col, supplier_col, short_desc_col, date_col]:
    st.warning("Please map all required columns: Amount, Supplier, Short Description, Date.")
    st.stop()

dayfirst = st.checkbox("Day-first date parsing (dd-mm-yyyy)", value=True)
fuzzy_threshold = st.slider("Supplier fuzzy match threshold", 0.80, 0.98, 0.92, 0.01)
drop_missing = st.checkbox("Drop rows with missing required fields", value=True)

if st.button("Run Harmonization ✅", type="primary"):
    out = df.copy()  # keep all original columns unchanged

    # Clean spend (assume INR today)
    out["_amount_clean"] = clean_amount(out[amount_col])
    out["_spend"] = out["_amount_clean"]
    out["_currency_target"] = "INR"

    # Standardize date
    out["_date_std"] = standardize_date(out[date_col], dayfirst=dayfirst)
    out["_date_iso"] = out["_date_std"].dt.strftime("%Y-%m-%d")
    out["_date_changed"] = out[date_col].astype(str).str.strip().ne(out["_date_iso"].astype(str).str.strip())

    # Normalize short description (light)
    out["_short_desc_h"] = normalize_description(out[short_desc_col])
    out["_short_desc_changed"] = out["_short_desc_h"].astype(str).str.strip().ne(out[short_desc_col].astype(str).str.strip())

    # Harmonize supplier (fuzzy)
    out["_supplier_h"], map_sup, chg = harmonize_names(out[supplier_col], threshold=fuzzy_threshold)
    out["_supplier_changed"] = chg

    # Optional pass-through dims for later slicing/dicing
    out["_dept"] = out[dept_col].astype(str) if dept_col != "(none)" else "Unknown"
    out["_plant"] = out[plant_col].astype(str) if plant_col != "(none)" else "Unknown"
    out["_capexopex"] = out[capex_col].astype(str) if capex_col != "(none)" else "Unknown"

    # Drop missing required fields (optional)
    if drop_missing:
        before = len(out)
        out = out.dropna(subset=["_spend", "_date_std", "_supplier_h", "_short_desc_h"])
        out = out[out["_supplier_h"].astype(str).str.strip().ne("")]
        out = out[out["_short_desc_h"].astype(str).str.strip().ne("")]
        out = out[out["_spend"].notna()]
        st.info(f"Dropped {before - len(out):,} rows with missing required fields.")
    else:
        st.info("No rows dropped. Output retains all rows.")

    # Any harmonization flag (keeps ALL rows)
    out["_any_harmonized"] = out["_supplier_changed"] | out["_short_desc_changed"] | out["_date_changed"]

    # Store for next apps
    st.session_state["df_harmonized"] = out

    st.success("✅ Harmonization completed. Output retains ALL rows (changed + unchanged).")
    st.write("Rows in output:", len(out))
    st.write("Rows changed (any):", int(out["_any_harmonized"].sum()))

    st.subheader("Preview (harmonized columns + flags)")
    st.dataframe(
        out[["_date_iso", "_date_changed",
             "_supplier_h", "_supplier_changed",
             "_short_desc_h", "_short_desc_changed",
             "_spend", "_currency_target",
             "_dept", "_plant", "_capexopex",
             "_any_harmonized"]].head(50),
        use_container_width=True
    )

    with st.expander("Supplier Harmonization Mapping (sample)", expanded=False):
        st.dataframe(map_sup.head(100), use_container_width=True)

    st.subheader("Download Harmonized Output (for App2 / App3)")
    st.download_button(
        "⬇️ Download Harmonized File (CSV)",
        data=out.to_csv(index=False).encode("utf-8"),
