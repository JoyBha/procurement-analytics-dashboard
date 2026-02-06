# -*- coding: utf-8 -*-
import sys
from pathlib import Path
ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

import streamlit as st
import pandas as pd
from utils import (
    harmonizable_fields, clean_amount, standardize_date,
    harmonize_names, normalize_description,
    convert_currency_df
)

st.set_page_config(page_title="Harmonization", page_icon="🧹", layout="wide")
st.title("🧹 2) Harmonization")

# Load raw data from page 1 or allow upload fallback
df = st.session_state.get("df_raw")
if df is None:
    up = st.file_uploader("Upload Purchase Register (CSV) (fallback)", type=["csv"])
    if up:
        df = pd.read_csv(up)
        st.session_state["df_raw"] = df

if df is None:
    st.info("Go to **Spend Data** page and upload your purchase register first.")
    st.stop()

st.write("Preview:")
st.dataframe(df.head(30), use_container_width=True)

fields = harmonizable_fields(df)

st.subheader("Choose fields to harmonize (multi-select)")
selected = st.multiselect(
    "Select one or more fields",
    options=fields,
    default=[]
)

st.subheader("Map core columns (needed for spend & optional FX)")
amount_col = st.selectbox("Amount/Spend column (required)", options=["(select)"] + list(df.columns))
date_col = st.selectbox("Date column (optional; helps date standardization and historical FX)", options=["(none)"] + list(df.columns))
currency_col = st.selectbox("Currency column (optional; needed only if you select currency conversion)", options=["(none)"] + list(df.columns))

if amount_col == "(select)":
    st.warning("Select the Amount/Spend column to proceed.")
    st.stop()

dayfirst = st.checkbox("Day-first date parsing (dd-mm-yyyy)", value=True)

# FX settings appear only if user selected the currency field OR currency_col mapped
do_fx = (currency_col != "(none)") and (currency_col in selected)

target_ccy = "INR"
use_txn_date_for_fx = False
if do_fx:
    st.markdown("### Currency Conversion (open-source FX)")
    st.caption("Uses Frankfurter open-source FX API (no key).")  # [3](https://frankfurter.dev/)[4](https://github.com/lineofflight/frankfurter)
    target_ccy = st.selectbox("Base/Target currency", ["INR","USD","EUR","GBP","AED","SGD"], index=0)
    use_txn_date_for_fx = st.checkbox("Use transaction date for FX (if Date is mapped)", value=False)

fuzzy_threshold = st.slider("Fuzzy match threshold (names)", 0.80, 0.98, 0.92, 0.01)

if st.button("Run Harmonization ✅", type="primary"):
    out = df.copy()

    # Always create normalized spend column
    out["_amount_clean"] = clean_amount(out[amount_col])
    out["_spend"] = out["_amount_clean"]

    # Date standardization if selected
    if date_col != "(none)" and date_col in selected:
        out["_date_std"] = standardize_date(out[date_col], dayfirst=dayfirst)
        out["_date_iso"] = out["_date_std"].dt.strftime("%Y-%m-%d")
        out["_date_changed"] = out[date_col].astype(str).str.strip().ne(out["_date_iso"].astype(str).str.strip())
    else:
        out["_date_std"] = pd.NaT
        out["_date_iso"] = ""
        out["_date_changed"] = False

    # Harmonize each selected field:
    change_flags = []

    for col in selected:
        col_lower = col.lower()

        # Currency conversion handled separately
        if col == currency_col:
            continue

        # If looks like a date field already mapped, skip (handled above)
        if col == date_col:
            continue

        # Short description: light normalize (no fuzzy)
        if any(k in col_lower for k in ["desc", "description", "short text", "item text", "material description", "service description"]):
            out[f"{col}__H"] = normalize_description(out[col])
            out[f"{col}__CHANGED"] = out[f"{col}__H"].astype(str).str.strip().ne(out[col].astype(str).str.strip())
            change_flags.append(out[f"{col}__CHANGED"])
            continue

        # Supplier / Vendor / Plant / Dept etc: fuzzy harmonize
        out[f"{col}__H"], _, chg = harmonize_names(out[col], threshold=fuzzy_threshold)
        out[f"{col}__CHANGED"] = chg
        change_flags.append(out[f"{col}__CHANGED"])

    # Currency conversion (only if selected)
    if do_fx:
        fx_date_col = date_col if (use_txn_date_for_fx and date_col != "(none)") else None
        tmp = convert_currency_df(out, amount_col=amount_col, ccy_col=currency_col, target_ccy=target_ccy, date_col=fx_date_col)
        # overwrite spend with converted spend
        out["_spend"] = tmp["_spend_converted"]
        out["_ccy_source"] = tmp["_ccy_source"]
        out["_ccy_target"] = tmp["_ccy_target"]
        out["_fx_rate_used"] = tmp["_fx_rate_used"]
        out["_fx_missing"] = tmp["_fx_missing"]
    else:
        out["_ccy_target"] = "INR"

    # Any-harmonized flag: keep all rows
    if change_flags:
        out["_any_harmonized"] = change_flags[0]
        for f in change_flags[1:]:
            out["_any_harmonized"] = out["_any_harmonized"] | f
        out["_any_harmonized"] = out["_any_harmonized"] | out["_date_changed"]
    else:
        out["_any_harmonized"] = out["_date_changed"]

    st.session_state["df_harmonized"] = out

    st.success("Harmonization complete. Output retains ALL rows (changed + unchanged).")
    st.write("Total rows:", len(out))
    st.write("Rows changed:", int(out["_any_harmonized"].sum()) if "_any_harmonized" in out.columns else 0)

    st.dataframe(out.head(100), use_container_width=True)

    st.download_button(
        "⬇️ Download Harmonized File (CSV)",
        data=out.to_csv(index=False).encode("utf-8"),
        file_name="harmonized_spend.csv",
        mime="text/csv"
    )
