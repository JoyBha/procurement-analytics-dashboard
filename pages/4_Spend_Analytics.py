# -*- coding: utf-8 -*-
import sys
from pathlib import Path
ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

import streamlit as st
import pandas as pd
import plotly.express as px

st.set_page_config(page_title="Spend Analytics", page_icon="📈", layout="wide")
st.title("📈 4) Spend Analytics")
st.caption("Filters are placed in the sidebar (not on the dashboard body).")

df = st.session_state.get("df_taxonomy") or st.session_state.get("df_harmonized")
if df is None:
    up = st.file_uploader("Upload Taxonomy+ABC CSV (recommended) or Harmonized CSV", type=["csv"])
    if up:
        df = pd.read_csv(up)

if df is None:
    st.info("Run Taxonomy+ABC (recommended) or Harmonization first, or upload the processed CSV.")
    st.stop()

# Ensure _spend exists
if "_spend" not in df.columns:
    st.error("Missing _spend column. Please run Harmonization.")
    st.stop()

# Sidebar filters (NOT on dashboard)
st.sidebar.header("🔎 Filters")

def multi_filter(col, label):
    if col in df.columns:
        opts = sorted(df[col].astype(str).fillna("Unknown").unique().tolist())
        return st.sidebar.multiselect(label, opts, default=[])
    return []

# Date filter
df["_date_std"] = pd.to_datetime(df["_date_std"], errors="coerce") if "_date_std" in df.columns else pd.NaT
if "_date_std" in df.columns and df["_date_std"].notna().any():
    min_d = df["_date_std"].min().date()
    max_d = df["_date_std"].max().date()
    date_range = st.sidebar.date_input("Date range", value=(min_d, max_d))
else:
    date_range = None

capex_filter = multi_filter("_capexopex", "CAPEX/OPEX")
plant_filter = multi_filter("_plant", "Plant")
dept_filter = multi_filter("_dept", "Department")
l1_filter = multi_filter("L1", "Material/Service (L1)")
l2_filter = multi_filter("L2", "Taxonomy L2")
l3_filter = multi_filter("L3", "Taxonomy L3")
abc_filter = multi_filter("ABC_Class", "ABC Class")
supplier_filter = multi_filter("_supplier_h", "Supplier (harmonized)") if "_supplier_h" in df.columns else []

# Apply filters
dff = df.copy()

if date_range and isinstance(date_range, tuple) and len(date_range) == 2 and "_date_std" in dff.columns:
    start = pd.to_datetime(date_range[0])
    end = pd.to_datetime(date_range[1])
    dff = dff[(dff["_date_std"].isna()) | ((dff["_date_std"] >= start) & (dff["_date_std"] <= end))]

def apply_list_filter(frame, col, selected_vals):
    if selected_vals and col in frame.columns:
        return frame[frame[col].astype(str).isin([str(x) for x in selected_vals])]
    return frame

dff = apply_list_filter(dff, "_capexopex", capex_filter)
dff = apply_list_filter(dff, "_plant", plant_filter)
dff = apply_list_filter(dff, "_dept", dept_filter)
dff = apply_list_filter(dff, "L1", l1_filter)
dff = apply_list_filter(dff, "L2", l2_filter)
dff = apply_list_filter(dff, "L3", l3_filter)
dff = apply_list_filter(dff, "ABC_Class", abc_filter)
if "_supplier_h" in dff.columns:
    dff = apply_list_filter(dff, "_supplier_h", supplier_filter)

# Dashboard visuals
st.subheader("OPEX vs CAPEX — Spend Split (Pie)")

if "_capexopex" in dff.columns:
    pie_df = dff.groupby("_capexopex", as_index=False)["_spend"].sum()
    fig = px.pie(pie_df, names="_capexopex", values="_spend", hole=0.45)
    st.plotly_chart(fig, use_container_width=True)
else:
    st.info("No CAPEX/OPEX column found in the dataset.")

# Additional views
c1, c2 = st.columns(2)

if "TaxonomyPath" in dff.columns:
    top_tax = dff.groupby("TaxonomyPath", as_index=False)["_spend"].sum().sort_values("_spend", ascending=False).head(15)
    c1.plotly_chart(px.bar(top_tax, x="_spend", y="TaxonomyPath", orientation="h", title="Top Taxonomy Paths (Top 15)"),
                    use_container_width=True)
else:
    c1.info("TaxonomyPath not found (run Taxonomy+ABC).")

if "_supplier_h" in dff.columns:
    top_sup = dff.groupby("_supplier_h", as_index=False)["_spend"].sum().sort_values("_spend", ascending=False).head(15)
    c2.plotly_chart(px.bar(top_sup, x="_spend", y="_supplier_h", orientation="h", title="Top Suppliers (Top 15)"),
                    use_container_width=True)
else:
    c2.info("Supplier harmonization column not found.")

st.divider()
st.subheader("Filtered Data Preview")
st.dataframe(dff.head(300), use_container_width=True)
