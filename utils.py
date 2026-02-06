import re
import numpy as np
import pandas as pd
import requests
import streamlit as st
from difflib import SequenceMatcher

# -----------------------------
# File IO
# -----------------------------
def read_purchase_file(uploaded_file) -> pd.DataFrame:
    name = uploaded_file.name.lower()
    if name.endswith(".csv"):
        return pd.read_csv(uploaded_file)
    if name.endswith(".xlsx") or name.endswith(".xls"):
        return pd.read_excel(uploaded_file, engine="openpyxl")
    raise ValueError("Unsupported file type. Upload CSV/XLSX.")


def clean_amount(series: pd.Series) -> pd.Series:
    s = series.astype(str).str.replace(r"[,\s]", "", regex=True)
    s = s.str.replace(r"[^0-9\.\-]", "", regex=True)
    return pd.to_numeric(s, errors="coerce")


def standardize_date(series: pd.Series, dayfirst=True) -> pd.Series:
    return pd.to_datetime(series, errors="coerce", dayfirst=dayfirst, infer_datetime_format=True)


def normalize_text(x: str) -> str:
    x = "" if pd.isna(x) else str(x)
    x = x.strip().lower()
    x = re.sub(r"[^a-z0-9\s]", " ", x)
    x = re.sub(r"\s+", " ", x).strip()
    return x


def normalize_description(series: pd.Series) -> pd.Series:
    s = series.fillna("").astype(str)
    s = s.str.replace(r"\s+", " ", regex=True).str.strip()
    return s


# -----------------------------
# Candidate harmonizable fields (exclude IDs/codes)
# -----------------------------
EXCLUDE_PATTERNS = [
    r"\bid\b", r"\bcode\b", r"\bsku\b", r"\bhsn\b", r"\bsac\b",
    r"\bmaterial\s*id\b", r"\bitem\s*id\b", r"\bvendor\s*id\b", r"\bsupplier\s*id\b",
    r"\bgl\b", r"\baccount\b", r"\basset\b", r"\bserial\b"
]

def is_excluded_field(col: str) -> bool:
    c = normalize_text(col)
    return any(re.search(p, c) for p in EXCLUDE_PATTERNS)

def harmonizable_fields(df: pd.DataFrame) -> list[str]:
    return [c for c in df.columns if not is_excluded_field(c)]


# -----------------------------
# Fuzzy harmonization for names (supplier, plant, dept, etc.)
# -----------------------------
def similarity(a: str, b: str) -> float:
    return SequenceMatcher(None, a, b).ratio()

def harmonize_names(series: pd.Series, threshold: float = 0.92, min_len: int = 3, max_uniques: int = 3000):
    """
    Returns:
      canonical_series, mapping_df, changed_mask
    """
    s_raw = series.fillna("").astype(str)
    s_norm = s_raw.map(normalize_text)

    uniques = s_norm.value_counts().index.tolist()
    if len(uniques) > max_uniques:
        uniques = uniques[:max_uniques]

    freq = s_norm.value_counts().to_dict()

    assigned = {}
    clusters = []
    for u in uniques:
        if u in assigned:
            continue
        cluster = [u]
        assigned[u] = u
        for v in uniques:
            if v in assigned:
                continue
            if len(u) >= min_len and len(v) >= min_len and similarity(u, v) >= threshold:
                assigned[v] = u
                cluster.append(v)
        clusters.append(cluster)

    # choose canonical (most frequent)
    cluster_best = {}
    for cluster in clusters:
        best = max(cluster, key=lambda x: freq.get(x, 0))
        for member in cluster:
            cluster_best[member] = best

    canon_norm = s_norm.map(lambda x: cluster_best.get(x, x))

    tmp = pd.DataFrame({"raw": s_raw, "canon_norm": canon_norm})
    best_raw = (
        tmp.groupby("canon_norm")["raw"]
        .agg(lambda x: x.value_counts().index[0] if len(x) else "")
        .to_dict()
    )
    canon_final = canon_norm.map(lambda x: best_raw.get(x, x))
    changed_mask = canon_final.astype(str).str.strip().ne(s_raw.astype(str).str.strip())

    mapping_df = (
        tmp.assign(canonical=canon_final)
           .drop_duplicates()
           .sort_values(["canonical", "raw"])
           .reset_index(drop=True)
    )
    return canon_final, mapping_df, changed_mask


# -----------------------------
# FX using Frankfurter (open-source, no key) [3](https://frankfurter.dev/)[4](https://github.com/lineofflight/frankfurter)
# -----------------------------
@st.cache_data(show_spinner=False)
def frankfurter_rate(from_ccy: str, to_ccy: str, date_iso: str | None = None) -> float | None:
    """
    Returns rate: 1 FROM = rate TO
    Uses Frankfurter endpoints (latest or historical).
    """
    from_ccy = str(from_ccy).upper().strip()
    to_ccy = str(to_ccy).upper().strip()

    # New API host in docs is api.frankfurter.dev; legacy is api.frankfurter.app
    if date_iso:
        url = f"https://api.frankfurter.dev/v1/{date_iso}?base={from_ccy}&symbols={to_ccy}"
    else:
        url = f"https://api.frankfurter.dev/v1/latest?base={from_ccy}&symbols={to_ccy}"

    try:
        r = requests.get(url, timeout=20)
        r.raise_for_status()
        data = r.json()
        rate = data.get("rates", {}).get(to_ccy)
        return float(rate) if rate is not None else None
    except Exception:
        return None


def convert_currency_df(df: pd.DataFrame, amount_col: str, ccy_col: str, target_ccy: str, date_col: str | None = None):
    """
    Adds:
      _spend_converted, _ccy_source, _ccy_target, _fx_rate_used, _fx_missing
    """
    out = df.copy()
    out["_ccy_source"] = out[ccy_col].fillna(target_ccy).astype(str).str.upper().str.strip()
    out["_ccy_target"] = str(target_ccy).upper().strip()

    amt = clean_amount(out[amount_col])

    # If date_col provided, use row date for fx lookup; else use latest
    if date_col and date_col in out.columns:
        dates = standardize_date(out[date_col], dayfirst=True).dt.strftime("%Y-%m-%d")
    else:
        dates = pd.Series([None] * len(out), index=out.index)

    # Map unique (src, date) pairs
    pairs = pd.DataFrame({"src": out["_ccy_source"], "date": dates}).drop_duplicates()
    rate_map = {}
    for _, row in pairs.iterrows():
        src = row["src"]
        d = row["date"]
        if src == out["_ccy_target"].iloc[0]:
            rate_map[(src, d)] = 1.0
        else:
            rate_map[(src, d)] = frankfurter_rate(src, out["_ccy_target"].iloc[0], d)

    out["_fx_rate_used"] = [
        rate_map.get((s, d), None) for s, d in zip(out["_ccy_source"].tolist(), dates.tolist())
    ]
    out["_fx_missing"] = pd.isna(out["_fx_rate_used"])
    out["_spend_converted"] = amt * pd.to_numeric(out["_fx_rate_used"], errors="coerce")

    return out


# -----------------------------
# ABC classification
# -----------------------------
def abc_classification(df: pd.DataFrame, group_col: str, spend_col: str, a_cut=0.80, b_cut=0.95):
    """
    Returns dataframe with ABC_Class per row based on cumulative spend share of group_col.
    """
    agg = df.groupby(group_col, dropna=False)[spend_col].sum().sort_values(ascending=False)
    total = agg.sum()
    if total == 0:
        return pd.Series(["C"] * len(df), index=df.index)

    cum = agg.cumsum() / total

    cls = {}
    for k, v in cum.items():
        if v <= a_cut:
            cls[k] = "A"
        elif v <= b_cut:
            cls[k] = "B"
        else:
            cls[k] = "C"

    return df[group_col].map(lambda x: cls.get(x, "C")).fillna("C")
``
