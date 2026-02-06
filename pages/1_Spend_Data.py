# -*- coding: utf-8 -*-
import sys
from pathlib import Path

# Ensure repo root is importable so "import utils" works from pages/
ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

import streamlit as st
from utils import read_purchase_file

st.set_page_config(page_title="Spend Data", page_icon="📥", layout="wide")  # [3](https://liz-in-tech.github.io/blog/posts/llm/003_streamlit.html)
st.title("📥 1) Spend Data — Upload Purchase Register")

uploaded = st.file_uploader("Upload Purchase Register (CSV/XLSX)", type=["csv", "xlsx", "xls"])
if not uploaded:
    st.info("Upload your purchase register to proceed.")
    st.stop()

df = read_purchase_file(uploaded)
st.session_state["df_raw"] = df

st.success(f"Loaded {len(df):,} rows × {df.shape[1]} columns")
st.dataframe(df, use_container_width=True)
