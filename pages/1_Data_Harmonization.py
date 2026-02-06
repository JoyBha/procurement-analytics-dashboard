import streamlit as st
import pandas as pd
import numpy as np

from utils import (
    read_purchase_file, clean_amount, standardize_date,
    harmonize_names, convert_to_inr
)

st.set_page_config(page_title="Data Harmonization", page_icon="🧹", layout="wide")
st.title("🧹 App 1 — Data Harmonization")
st.caption("Current assumption: all amounts are INR (currency column can be added later).")

uploaded = st.file_uploader("Upload Purchase Register (CSV/XLSX)", type=["csv", "xlsx", "xls"])
if not uploaded:
    st.info("Upload a file to start.")
    st.stop()

df = read_purchase_file(uploaded)
st.success(f"Loaded {len(df):,} rows × {df.shape[1]} columns")
st.dataframe(df.head(25), use_container_width=True)

st.subheader("1) Column Mapping")
cols = list(df.columns)

amount_col = st.selectbox("Amount (Required)", ["(select)"] + cols)
date_col = st.selectbox("Date (Required)", ["(select)"] + cols)
desc_col = st.selectbox("Description (Required)", ["(select)"] + cols)
supplier_col = st.selectbox("Supplier (Required)", ["(select)"] + cols)

currency_col = st.selectbox("Currency (Optional - for later)", ["(none)"] + cols)
dept_col = st.selectbox("Department (Optional)", ["(none)"] + cols)
plant_col = st.selectbox("Plant (Optional)", ["(none)"] + cols)
capex_col = st.selectbox("CAPEX/OPEX (Optional)", ["(none)"] + cols)

if "(select)" in [amount_col, date_col, desc_col, supplier_col]:
    st.warning("Please map required columns: Amount, Date, Description, Supplier.")
    st.stop()

dayfirst = st.checkbox("Day-first date parsing (dd-mm-yyyy)", value=True)
drop_missing = st.checkbox("Drop rows with missing required fields", value=True)

st.subheader("2) Name Harmonization")
fuzzy_threshold = st.slider("Fuzzy match threshold", 0.80, 0.98, 0.92, 0.01)
harm_supplier = st.checkbox("Harmonize supplier names", value=True)
harm_dept = st.checkbox("Harmonize department names", value=True)
harm_plant = st.checkbox("Harmonize plant names", value=True)

with st.expander("Optional: FX settings (use later when currency column exists)", expanded=False):
    fx_default = {"INR": 1.0, "USD": 83.0, "EUR": 90.0, "GBP": 105.0}
    fx_text = st.text_area(
        "FX rates (INR per 1 unit). One per line like: USD=83.2",
        value="\n".join([f"{k}={v}" for k, v in fx_default.items()])
    )
    fx_table = {}
    for line in fx_text.splitlines():
        if "=" in line:
            k, v = line.split("=", 1)
            k = k.strip().upper()
            try:
                fx_table[k] = float(v.strip())
            except:
                pass
else:
    fx_table = {"INR": 1.0}

if st.button("Run Harmonization ✅"):
    work = df.copy()

    work["_amount"] = clean_amount(work[amount_col])
    work["_date"] = standardize_date(work[date_col], dayfirst=dayfirst)
    work["_date_iso"] = work["_date"].dt.strftime("%Y-%m-%d")

    work["_desc"] = work[desc_col].astype(str)
    work["_supplier"] = work[supplier_col].astype(str)

    work["_dept"] = work[dept_col].astype(str) if dept_col != "(none)" else "Unknown"
    work["_plant"] = work[plant_col].astype(str) if plant_col != "(none)" else "Unknown"
    work["_capexopex"] = work[capex_col].astype(str) if capex_col != "(none)" else "Unknown"

    currency_series = work[currency_col] if currency_col != "(none)" else None

    # INR assumption today:
    work["_spend_inr"], work["_missing_fx"], work["_currency_used"] = convert_to_inr(
        amount=work["_amount"],
        currency=currency_series,
        fx_table=fx_table,
        default_currency="INR"
    )

    if drop_missing:
        before = len(work)
        work = work.dropna(subset=["_spend_inr", "_date", "_desc", "_supplier"])
        work = work[work["_desc"].astype(str).str.strip().ne("")]
        work = work[work["_supplier"].astype(str).str.strip().ne("")]
        st.write(f"Dropped {before - len(work):,} rows with missing required fields.")

    mappings = {}

    if harm_supplier:
        work["_supplier_h"], map_sup = harmonize_names(work["_supplier"], threshold=fuzzy_threshold)
        mappings["Supplier"] = map_sup
    else:
        work["_supplier_h"] = work["_supplier"]

    if harm_dept:
        work["_dept_h"], map_dept = harmonize_names(work["_dept"], threshold=fuzzy_threshold)
        mappings["Department"] = map_dept
    else:
        work["_dept_h"] = work["_dept"]

    if harm_plant:
        work["_plant_h"], map_plant = harmonize_names(work["_plant"], threshold=fuzzy_threshold)
        mappings["Plant"] = map_plant
    else:
        work["_plant_h"] = work["_plant"]

    work["_spend"] = work["_spend_inr"]
    work["_date_std"] = work["_date"]

    st.session_state["df_harmonized"] = work
    st.session_state["harmonization_mappings"] = mappings

    st.success("✅ Harmonized data stored in session_state['df_harmonized'].")

    st.subheader("Preview")
    st.dataframe(
        work[["_date_iso", "_spend", "_currency_used", "_supplier_h", "_dept_h", "_plant_h", "_capexopex", "_desc"]].head(50),
        use_container_width=True
    )
