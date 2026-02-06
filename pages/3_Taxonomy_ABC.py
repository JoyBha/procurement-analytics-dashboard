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

st.set_page_config(page_title="Taxonomy + ABC", page_icon="🧭", layout="wide")
st.title("🧭 3) Taxonomy + ABC")
st.caption("Generates taxonomy hierarchy + ABC classification based on spend at Material_No level.")

# Load harmonized data
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

# Choose the description field used for taxonomy generation
desc_col = st.selectbox(
    "Choose description field for taxonomy",
    options=list(df.columns),
    help="This should be material/service description column (prefer harmonized description)."
)

# ✅ NEW: Choose the Material_No column for ABC classification
material_no_col = st.selectbox(
    "Choose Material_No column for ABC classification",
    options=list(df.columns),
    help="ABC will be calculated based on total spend aggregated at this Material_No field."
)

# Validate spend column
if "_spend" not in df.columns:
    st.error("Missing _spend column. Please run Harmonization to create _spend.")
    st.stop()

# LLM settings
provider, api_key, model, base_url = get_llm_settings()
st.caption(
    "Taxonomy uses an OpenAI-compatible LLM API. You can set API key/model/base_url in Streamlit Secrets."
)

# Optional UI overrides (if not using Secrets)
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

# Refresh settings after optional overrides
provider, api_key, model, base_url = get_llm_settings()
if not api_key:
    st.warning("No API key found. Add OPENAI_API_KEY in Streamlit Secrets, or paste it above.")
    st.stop()

# Parameters for ABC buckets (optional; keep defaults)
with st.expander("ABC Thresholds (optional)", expanded=False):
    a_cut = st.slider("A cutoff (cumulative spend)", 0.50, 0.90, 0.80, 0.01)
    b_cut = st.slider("B cutoff (cumulative spend)", 0.80, 0.99, 0.95, 0.01)

if st.button("Generate Taxonomy + ABC ✅", type="primary"):
    work = df.copy()
    work["_desc_for_taxo"] = work[desc_col].fillna("").astype(str)
    work["_material_no"] = work[material_no_col].fillna("Unknown").astype(str)

    # Classify unique descriptions (cached for repeat runs)
    uniques = work["_desc_for_taxo"].dropna().unique().tolist()
    st.info(f"Unique descriptions to classify: {len(uniques):,} (cached for repeat runs).")

    mapping = {}
    prog = st.progress(0)
    for i, d in enumerate(uniques):
        mapping[d] = classify_description(d, model=model, api_key=api_key, base_url=base_url)
        if len(uniques) > 0:
            prog.progress(int((i + 1) / len(uniques) * 100))

    # Write taxonomy columns
    def get_level(desc, lvl):
        m = mapping.get(desc, {})
        return m.get(lvl, "Other")

    work["L1"] = work["_desc_for_taxo"].map(lambda x: get_level(x, "L1"))
    work["L2"] = work["_desc_for_taxo"].map(lambda x: get_level(x, "L2"))
    work["L3"] = work["_desc_for_taxo"].map(lambda x: get_level(x, "L3"))
    work["L4"] = work["_desc_for_taxo"].map(lambda x: get_level(x, "L4"))
    work["TaxonomyPath"] = work["L1"] + " > " + work["L2"] + " > " + work["L3"] + " > " + work["L4"]

    # ✅ ABC classification based on Material_No-level spend
    # Group by Material_No, sum spend, compute cumulative share, assign A/B/C
    work["ABC_Class"] = abc_classification(
        work,
        group_col="_material_no",
        spend_col="_spend",
        a_cut=a_cut,
        b_cut=b_cut
    )

    # Optional: Spend per Material_No for reference
    mat_spend = (
        work.groupby("_material_no", as_index=False)["_spend"]
            .sum()
            .sort_values("_spend", ascending=False)
            .rename(columns={"_material_no": "Material_No", "_spend": "Total_Spend"})
    )

    # Store for App4
    st.session_state["df_taxonomy"] = work

    st.success("✅ Taxonomy + ABC generated. New columns added to file.")
    st.subheader("Preview: Taxonomy + ABC")
    st.dataframe(
        work[["_material_no", "ABC_Class", "TaxonomyPath", "_spend"]].head(50),
        use_container_width=True
    )

    with st.expander("Material_No spend summary (Top 50)", expanded=False):
        st.dataframe(mat_spend.head(50), use_container_width=True)

    st.download_button(
        "⬇️ Download Taxonomy + ABC File (CSV)",
        data=work.to_csv(index=False).encode("utf-8"),
        file_name="harmonized_with_taxonomy_abc.csv",
        mime="text/csv"
    )
