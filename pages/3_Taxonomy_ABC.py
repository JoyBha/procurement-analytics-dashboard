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

# User chooses the description field to use for taxonomy
desc_col = st.selectbox("Choose description field for taxonomy", options=list(df.columns))

# LLM settings (open-source-like: OpenAI-compatible endpoints supported)
provider, api_key, model, base_url = get_llm_settings()
st.caption("Taxonomy uses an OpenAI-compatible LLM API. (You can set API key/model/base_url in Streamlit Secrets.)")  # [5](https://pythonandvba.com/blog/how-to-create-a-streamlit-multi-page-web-app/)

# Optional UI overrides (if you don't want secrets)
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
    st.warning("No API key found. Add OPENAI_API_KEY in Streamlit Secrets, or paste in settings above.")
    st.stop()

if st.button("Generate Taxonomy + ABC ✅", type="primary"):
    work = df.copy()
    work["_desc_for_taxo"] = work[desc_col].fillna("").astype(str)

    # classify unique descriptions
    uniques = work["_desc_for_taxo"].dropna().unique().tolist()
    st.info(f"Unique descriptions to classify: {len(uniques):,} (cached for repeat runs).")

    mapping = {}
    prog = st.progress(0)
    for i, d in enumerate(uniques):
        mapping[d] = classify_description(d, model=model, api_key=api_key, base_url=base_url)
        if len(uniques) > 0:
            prog.progress(int((i + 1) / len(uniques) * 100))

    # write taxonomy columns
    def get_level(desc, lvl):
        m = mapping.get(desc, {})
        return m.get(lvl, "Other")

    work["L1"] = work["_desc_for_taxo"].map(lambda x: get_level(x, "L1"))
    work["L2"] = work["_desc_for_taxo"].map(lambda x: get_level(x, "L2"))
    work["L3"] = work["_desc_for_taxo"].map(lambda x: get_level(x, "L3"))
    work["L4"] = work["_desc_for_taxo"].map(lambda x: get_level(x, "L4"))
    work["TaxonomyPath"] = work["L1"] + " > " + work["L2"] + " > " + work["L3"] + " > " + work["L4"]

    # ABC classification based on total spend by taxonomy path
    if "_spend" not in work.columns:
        st.error("Missing _spend column. Please run Harmonization to create _spend.")
        st.stop()

    work["ABC_Class"] = abc_classification(work, group_col="TaxonomyPath", spend_col="_spend")

    st.session_state["df_taxonomy"] = work

    st.success("Taxonomy + ABC generated. New columns added to file.")
    st.dataframe(work[["TaxonomyPath", "ABC_Class", "_spend"]].head(50), use_container_width=True)

    st.download_button(
        "⬇️ Download Taxonomy + ABC File (CSV)",
        data=work.to_csv(index=False).encode("utf-8"),
        file_name="harmonized_with_taxonomy_abc.csv",
        mime="text/csv"
    )
