import streamlit as st

st.set_page_config(
    page_title="Procurement Analytics Dashboard",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)  # [6](https://docs.streamlit.io/develop/api-reference/configuration/st.set_page_config)

st.title("📊 Procurement Analytics Dashboard")
st.markdown(
    """
Welcome! This suite runs in 4 steps:

1. **Spend Data** → Upload purchase register & preview  
2. **Harmonization** → Select multiple fields to harmonize (includes currency conversion)  
3. **Taxonomy + ABC** → LLM-backed hierarchy + ABC classification added as new columns  
4. **Spend Analytics** → OPEX vs CAPEX pie + sidebar filters (not on dashboard)
"""
)

st.info("Use the left sidebar page navigation to move between apps (auto-created from the pages/ folder).")
