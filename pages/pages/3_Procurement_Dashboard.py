import streamlit as st
import pandas as pd
import plotly.express as px

st.set_page_config(page_title="Procurement Dashboard", page_icon="📊", layout="wide", initial_sidebar_state="collapsed")
st.title("📊 App 3 — Procurement Analytics Dashboard")
st.caption("No sidebar filters • Slice/dice via perspectives + group-by any field")

# Prefer taxonomy dataset
if "df_taxonomy" in st.session_state:
    df = st.session_state["df_taxonomy"].copy()
    st.success("Using taxonomy-enriched dataset (df_taxonomy).")
elif "df_harmonized" in st.session_state:
    df = st.session_state["df_harmonized"].copy()
    st.warning("Taxonomy not found. Using harmonized dataset (df_harmonized). Run App 2 for taxonomy.")
else:
    st.error("No data found. Run App 1 first.")
    st.stop()

# Ensure date column exists
if "_date_std" not in df.columns and "_date" in df.columns:
    df["_date_std"] = df["_date"]

# Perspectives (not sidebar)
c1, c2 = st.columns(2)
with c1:
    p_l1 = st.radio("Perspective: Material vs Service", ["All", "Material", "Service"], horizontal=True)
with c2:
    p_cap = st.radio("Perspective: OPEX vs CAPEX", ["All", "OPEX", "CAPEX"], horizontal=True)

view = df.copy()

if p_l1 != "All" and "L1" in view.columns:
    view = view[view["L1"] == p_l1]

if p_cap != "All":
    cap = view.get("_capexopex", "Unknown").astype(str).str.upper()
    view = view[cap.str.contains(p_cap)]

# KPIs
total_spend = float(view["_spend"].sum()) if "_spend" in view.columns else 0.0
transactions = int(len(view))
sup_col = "_supplier_h" if "_supplier_h" in view.columns else "_supplier"
suppliers = int(view[sup_col].nunique()) if sup_col in view.columns else 0

k1, k2, k3 = st.columns(3)
k1.metric("Total Spend (INR)", f"{total_spend:,.0f}")
k2.metric("Transactions", f"{transactions:,}")
k3.metric("Suppliers", f"{suppliers:,}")

st.divider()

plant_col = "_plant_h" if "_plant_h" in view.columns else ("_plant" if "_plant" in view.columns else None)
dept_col = "_dept_h" if "_dept_h" in view.columns else ("_dept" if "_dept" in view.columns else None)

cc1, cc2 = st.columns(2)

if plant_col:
    plant_sp = view.groupby(plant_col, as_index=False)["_spend"].sum().sort_values("_spend", ascending=False).head(15)
    cc1.plotly_chart(px.bar(plant_sp, x="_spend", y=plant_col, orientation="h", title="Spend by Plant (Top 15)"),
                     use_container_width=True)
else:
    cc1.info("Plant column not available.")

if dept_col:
    dept_sp = view.groupby(dept_col, as_index=False)["_spend"].sum().sort_values("_spend", ascending=False).head(15)
    cc2.plotly_chart(px.bar(dept_sp, x="_spend", y=dept_col, orientation="h", title="Spend by Department (Top 15)"),
                     use_container_width=True)
else:
    cc2.info("Department column not available.")

# Trend with interactive range slider (slicing via chart interaction)
if "_date_std" in view.columns and pd.to_datetime(view["_date_std"], errors="coerce").notna().any():
    tmp = view.copy()
    tmp["_date_std"] = pd.to_datetime(tmp["_date_std"], errors="coerce")
    tmp = tmp.dropna(subset=["_date_std"])
    tmp["Month"] = tmp["_date_std"].dt.to_period("M").dt.to_timestamp()
    monthly = tmp.groupby("Month", as_index=False)["_spend"].sum()
    fig = px.line(monthly, x="Month", y="_spend", markers=True, title="Monthly Spend Trend (use range slider to slice date)")
    fig.update_xaxes(rangeslider_visible=True)
    st.plotly_chart(fig, use_container_width=True)
else:
    st.info("No valid date column for trend.")

st.divider()

# Group-by any field (on-page controls; not sidebar)
st.subheader("🔍 Slice & Dice (Group-by any field)")
metric = st.selectbox("Metric", ["Spend", "Transactions", "Suppliers"], index=0)

candidate_fields = [c for c in view.columns if view[c].dtype == "object" and c not in ["_desc", "_taxo_text"]]
group_field = st.selectbox("Group-by field", candidate_fields if candidate_fields else ["(none)"])

if group_field and group_field != "(none)":
    if metric == "Spend":
        grp = view.groupby(group_field, as_index=False)["_spend"].sum().sort_values("_spend", ascending=False).head(25)
        st.plotly_chart(px.bar(grp, x="_spend", y=group_field, orientation="h", title=f"Spend by {group_field} (Top 25)"),
                        use_container_width=True)
    elif metric == "Transactions":
        grp = view.groupby(group_field, as_index=False)["_spend"].size().rename(columns={"size": "Transactions"}).sort_values("Transactions", ascending=False).head(25)
        st.plotly_chart(px.bar(grp, x="Transactions", y=group_field, orientation="h", title=f"Transactions by {group_field} (Top 25)"),
                        use_container_width=True)
    else:
        grp = view.groupby(group_field, as_index=False)[sup_col].nunique().rename(columns={sup_col: "Suppliers"}).sort_values("Suppliers", ascending=False).head(25)
        st.plotly_chart(px.bar(grp, x="Suppliers", y=group_field, orientation="h", title=f"Suppliers by {group_field} (Top 25)"),
                        use_container_width=True)

# Taxonomy view if present
if "TaxonomyPath" in view.columns:
    st.subheader("🧭 Taxonomy Spend View")
    tax = view.groupby(["L1", "L2"], as_index=False)["_spend"].sum().sort_values("_spend", ascending=False).head(30)
    st.plotly_chart(px.treemap(tax, path=["L1", "L2"], values="_spend", title="Spend by Taxonomy (L1→L2)"),
                    use_container_width=True)

st.divider()
st.subheader("Data Preview")
st.dataframe(view.head(200), use_container_width=True)
