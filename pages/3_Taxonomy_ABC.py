# -*- coding: utf-8 -*-
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

import streamlit as st
import pandas as pd

from utils import abc_classification
from llm_taxonomy import get_llm_settings, classify_description

st.set_page_config(page_title="Taxonomy + ABC", page_icon="🧭", layout="wide")  # [3](https://liz-in-tech.github.io/blog/posts/llm/003_streamlit.html)
st.title("🧭 3) Taxonomy + ABC")
st.caption("Taxonomy hierarchy + GLOBAL ABC classification based on spend at Material_No level.")

# -----------------------------
# Load harmonized data
# -----------------------------
df = st.session_state.get("df_harmonized")
if df is None:
    up = st.file_uploader("Upload Harmonized File (CSV)", type=["csv"])
    if up:
        df = pd.read_csv(up)
        st.session_state["df_harmonized"] = df

if df is None:
    st.info("Run **Harmonization** first or upload the harmonized CSV.")
    st.stop()

st.write("Preview:")
st.dataframe(df.head(30), use_container_width=True)

# -----------------------------
# Required columns selection
# -----------------------------
desc_col = st.selectbox(
    "Choose description field for taxonomy",
    options=list(df.columns),
    help="Prefer a harmonized description column if available."
)

material_no_col = st.selectbox(
    "Choose Material_No column for GLOBAL ABC classification",
    options=list(df.columns),
    help="ABC will be calculated based on total spend aggregated at this Material_No field."
)

if "_spend" not in df.columns:
    st.error("Missing _spend column. Please run Harmonization to create _spend.")
    st.stop()

# -----------------------------
# LLM settings (OpenAI-compatible)
# -----------------------------
provider, api_key, model, base_url = get_llm_settings()
st.caption(
    "Taxonomy uses an OpenAI-compatible LLM API (set OPENAI_API_KEY / OPENAI_MODEL / OPENAI_BASE_URL in Streamlit Secrets)."
)  # OpenAI SDK supports this client style [4](https://github.com/streamlit/streamlit/issues/10220)

# Optional overrides in UI (only if you don't want Secrets)
with st.expander("Optional LLM Settings (if not using Secrets)", expanded=False):
    key_in = st.text_input("API Key", type="password", value="")
    model_in = st.text_input("Model", value=model)
    base_in = st.text_input("Base URL (OpenAI-compatible)", value=base_url)

    if key_in:
        st.session_state["OPENAI_API_KEY_SESSION"] = key_in
    if model_in:
        st.session_state["OPENAI_MODEL_SESSION"] = model_in
    if base_in:
        st.session_state["OPENAI_BASE_URL_SESSION"] = base_in

# Refresh settings
provider, api_key, model, base_url = get_llm_settings()
if not api_key:
    st.warning("No API key found. Add OPENAI_API_KEY in Streamlit Secrets, or paste it above.")
    st.stop()

# ABC thresholds
with st.expander("ABC Thresholds (optional)", expanded=False):
    a_cut = st.slider("A cutoff (cumulative spend)", 0.50, 0.90, 0.80, 0.01)
    b_cut = st.slider("B cutoff (cumulative spend)", 0.80, 0.99, 0.95, 0.01)

# -----------------------------
# Generate taxonomy + ABC
# -----------------------------
if st.button("Generate Taxonomy + GLOBAL ABC ✅", type="primary"):
    work = df.copy()
    work["_desc_for_taxo"] = work[desc_col].fillna("").astype(str)
    work["_material_no"] = work[material_no_col].fillna("Unknown").astype(str)

    # ---- Taxonomy: classify unique descriptions (cached)
    uniques = work["_desc_for_taxo"].dropna().unique().tolist()
    st.info(f"Unique descriptions to classify: {len(uniques):,} (cached for repeat runs).")

    mapping = {}
    prog = st.progress(0)
    for i, d in enumerate(uniques):
        mapping[d] = classify_description(d, model=model, api_key=api_key, base_url=base_url)
        if len(uniques) > 0:
            prog.progress(int((i + 1) / len(uniques) * 100))

    def get_level(desc, lvl):
        m = mapping.get(desc, {})
        return m.get(lvl, "Other")

    work["L1"] = work["_desc_for_taxo"].map(lambda x: get_level(x, "L1"))
    work["L2"] = work["_desc_for_taxo"].map(lambda x: get_level(x, "L2"))
    work["L3"] = work["_desc_for_taxo"].map(lambda x: get_level(x, "L3"))
    work["L4"] = work["_desc_for_taxo"].map(lambda x: get_level(x, "L4"))
    work["TaxonomyPath"] = work["L1"] + " > " + work["L2"] + " > " + work["L3"] + " > " + work["L4"]

    # ---- GLOBAL ABC based on Material_No spend
    work["ABC_Class"] = abc_classification(
        work,
        group_col="_material_no",
        spend_col="_spend",
        a_cut=a_cut,
        b_cut=b_cut
    )

    # Summary table for Material_No
    mat_spend = (
        work.groupby("_material_no", as_index=False)["_spend"]
            .sum()
            .sort_values("_spend", ascending=False)
            .rename(columns={"_material_no": "Material_No", "_spend": "Total_Spend"})
    )

    # Store for next app
    st.session_state["df_taxonomy"] = work

    st.success("✅ Taxonomy + GLOBAL ABC generated. New columns added to the dataset.")
    st.subheader("Preview: Material_No ABC + Taxonomy")
    st.dataframe(
        work[["_material_no", "ABC_Class", "TaxonomyPath", "_spend"]].head(60),
        use_container_width=True
    )

    with st.expander("Material_No Spend Summary (Top 100)", expanded=False):
        st.dataframe(mat_spend.head(100), use_container_width=True)

    st.download_button(
        "⬇️ Download Taxonomy + ABC File (CSV)",
        data=work.to_csv(index=False).encode("utf-8"),
        file_name="harmonized_with_taxonomy_globalABC_materialNo.csv",
        mime="text/csv"
    )
