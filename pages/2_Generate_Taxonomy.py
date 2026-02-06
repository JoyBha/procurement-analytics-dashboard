import streamlit as st
import pandas as pd

from taxonomy import generate_taxonomy
from ai_labeler import rename_category_cached, get_api_key, get_model_name

st.set_page_config(page_title="Generate Taxonomy", page_icon="🧭", layout="wide")
st.title("🧭 App 2 — Generate Material & Service Taxonomy (AI-assisted)")

if "df_harmonized" not in st.session_state:
    st.warning("Run App 1 first (Data Harmonization). No harmonized data found.")
    st.stop()

df = st.session_state["df_harmonized"].copy()
st.success(f"Using harmonized dataset: {len(df):,} rows")

# API key handling: prefer Streamlit Secrets; fallback to user input
api_key = get_api_key()
model = get_model_name()

if not api_key:
    st.info("No OPENAI_API_KEY found in Streamlit Secrets. You can paste a key below for demo.")
    user_key = st.text_input("OpenAI API Key (demo input)", type="password")
    if user_key:
        st.session_state["OPENAI_API_KEY_SESSION"] = user_key
        api_key = user_key

if not api_key:
    st.stop()

st.subheader("Taxonomy Settings")
desc_col = "_desc"
l2 = st.slider("L2 clusters", 3, 25, 10, 1)
l3 = st.slider("L3 clusters per L2", 2, 12, 4, 1)
sample_n = st.slider("Examples per cluster for AI labeling", 5, 20, 12, 1)

if st.button("Generate AI-assisted Taxonomy ✅"):
    with st.spinner("Step 1/2: Creating taxonomy structure (ML clustering)..."):
        df_tax = generate_taxonomy(df, desc_col=desc_col, l2=l2, l3=l3)

    with st.spinner("Step 2/2: AI labeling taxonomy nodes..."):
        # Rename L2, L3, L4
        for l1 in ["Material", "Service"]:
            sub = df_tax[df_tax["L1"] == l1]

            # L2
            for raw_l2 in sub["L2"].unique():
                examples = tuple(sub[sub["L2"] == raw_l2][desc_col].astype(str).head(sample_n).tolist())
                clean = rename_category_cached(level="L2", l1=l1, raw_label=raw_l2, examples=examples, model=model)
                df_tax.loc[(df_tax["L1"] == l1) & (df_tax["L2"] == raw_l2), "L2"] = clean

            # L3
            pairs = sub[["L2", "L3"]].drop_duplicates().values.tolist()
            for l2_name, raw_l3 in pairs:
                examples = tuple(sub[(sub["L2"] == l2_name) & (sub["L3"] == raw_l3)][desc_col].astype(str).head(sample_n).tolist())
                clean = rename_category_cached(level="L3", l1=l1, raw_label=raw_l3, examples=examples, model=model)
                df_tax.loc[(df_tax["L1"] == l1) & (df_tax["L2"] == l2_name) & (df_tax["L3"] == raw_l3), "L3"] = clean

            # L4
            triples = sub[["L2", "L3", "L4"]].drop_duplicates().values.tolist()
            for l2_name, l3_name, raw_l4 in triples:
                examples = tuple(sub[(sub["L2"] == l2_name) & (sub["L3"] == l3_name) & (sub["L4"] == raw_l4)][desc_col].astype(str).head(sample_n).tolist())
                clean = rename_category_cached(level="L4", l1=l1, raw_label=raw_l4, examples=examples, model=model)
                df_tax.loc[(df_tax["L1"] == l1) & (df_tax["L2"] == l2_name) & (df_tax["L3"] == l3_name) & (df_tax["L4"] == raw_l4), "L4"] = clean

        df_tax["TaxonomyPath"] = df_tax["L1"] + " > " + df_tax["L2"] + " > " + df_tax["L3"] + " > " + df_tax["L4"]

    st.session_state["df_taxonomy"] = df_tax
    st.success("✅ Taxonomy stored in session_state['df_taxonomy'].")

    st.subheader("Preview")
    st.dataframe(df_tax[["L1", "L2", "L3", "L4", "TaxonomyPath", "_spend", "_supplier_h", "_dept_h", "_plant_h"]].head(80),
                 use_container_width=True)

    st.download_button(
        "Download Taxonomy Enriched Data (CSV)",
        df_tax.to_csv(index=False).encode("utf-8"),
        file_name="taxonomy_enriched.csv",
        mime="text/csv"
    )
