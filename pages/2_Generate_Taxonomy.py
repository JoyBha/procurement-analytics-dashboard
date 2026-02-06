import streamlit as st
import pandas as pd

from taxonomy import generate_taxonomy
from ai_labeler import rename_category_cached, get_api_key, get_model_name

st.set_page_config(page_title="Generate Taxonomy", page_icon="🧭", layout="wide")
st.title("🧭 App 2 — Generate Material & Service Taxonomy (AI-assisted)")

# Load data: session first, else upload harmonized file
df = None
if "df_harmonized" in st.session_state:
    df = st.session_state["df_harmonized"].copy()
    st.success("Loaded harmonized data from App1 (session).")
else:
    up = st.file_uploader("Upload Harmonized File (CSV) from App1", type=["csv"])
    if up:
        df = pd.read_csv(up)
        st.success("Loaded harmonized data from uploaded file.")

if df is None:
    st.info("Run App1 first OR upload the harmonized CSV.")
    st.stop()

st.write(f"Rows: {len(df):,}")

# AI key handling
api_key = get_api_key()
model = get_model_name()

if not api_key:
    st.info("No OPENAI_API_KEY found in Secrets. Paste a key for demo (stored only in session).")
    user_key = st.text_input("OpenAI API Key", type="password")
    if user_key:
        st.session_state["OPENAI_API_KEY_SESSION"] = user_key
        api_key = user_key

if not api_key:
    st.stop()

st.subheader("Taxonomy Settings")
desc_col = "_desc_h" if "_desc_h" in df.columns else "_desc" if "_desc" in df.columns else None
if not desc_col:
    st.error("No description column found (_desc_h/_desc). Please harmonize description in App1 or map description column.")
    st.stop()

l2 = st.slider("L2 clusters", 3, 25, 10, 1)
l3 = st.slider("L3 clusters per L2", 2, 12, 4, 1)
sample_n = st.slider("Examples per cluster for AI labeling", 5, 20, 12, 1)

if st.button("Generate AI-assisted Taxonomy ✅", type="primary"):
    with st.spinner("Step 1/2: Creating taxonomy structure (ML clustering)..."):
        df_tax = generate_taxonomy(df, desc_col=desc_col, l2=l2, l3=l3)

    with st.spinner("Step 2/2: AI labeling taxonomy nodes..."):
        model = get_model_name()

        for l1 in ["Material", "Service"]:
            sub = df_tax[df_tax["L1"] == l1]

            # Rename L2
            for raw_l2 in sub["L2"].unique():
                examples = tuple(sub[sub["L2"] == raw_l2][desc_col].astype(str).head(sample_n).tolist())
                clean = rename_category_cached(level="L2", l1=l1, raw_label=raw_l2, examples=examples, model=model)
                df_tax.loc[(df_tax["L1"] == l1) & (df_tax["L2"] == raw_l2), "L2"] = clean

            # Rename L3
            pairs = sub[["L2", "L3"]].drop_duplicates().values.tolist()
            for l2_name, raw_l3 in pairs:
                examples = tuple(sub[(sub["L2"] == l2_name) & (sub["L3"] == raw_l3)][desc_col].astype(str).head(sample_n).tolist())
                clean = rename_category_cached(level="L3", l1=l1, raw_label=raw_l3, examples=examples, model=model)
                df_tax.loc[(df_tax["L1"] == l1) & (df_tax["L2"] == l2_name) & (df_tax["L3"] == raw_l3), "L3"] = clean

            # Rename L4
            triples = sub[["L2", "L3", "L4"]].drop_duplicates().values.tolist()
            for l2_name, l3_name, raw_l4 in triples:
                examples = tuple(sub[(sub["L2"] == l2_name) & (sub["L3"] == l3_name) & (sub["L4"] == raw_l4)][desc_col].astype(str).head(sample_n).tolist())
                clean = rename_category_cached(level="L4", l1=l1, raw_label=raw_l4, examples=examples, model=model)
                df_tax.loc[(df_tax["L1"] == l1) & (df_tax["L2"] == l2_name) & (df_tax["L3"] == l3_name) & (df_tax["L4"] == raw_l4), "L4"] = clean

        # Rebuild taxonomy path
        df_tax["TaxonomyPath"] = df_tax["L1"] + " > " + df_tax["L2"] + " > " + df_tax["L3"] + " > " + df_tax["L4"]

    # Store and export
    st.session_state["df_taxonomy"] = df_tax
    st.success("✅ Taxonomy columns added. Dataset stored in session_state['df_taxonomy'].")

    st.subheader("Preview")
    st.dataframe(df_tax[["L1","L2","L3","L4","TaxonomyPath","_spend"]].head(80), use_container_width=True)

    st.subheader("Download Taxonomy-Enriched File (for App3)")
    st.download_button(
        "⬇️ Download Taxonomy Enriched CSV",
        data=df_tax.to_csv(index=False).encode("utf-8"),
        file_name="purchase_register_harmonized_with_taxonomy.csv",
        mime="text/csv"
    )
