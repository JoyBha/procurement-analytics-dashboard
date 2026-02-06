import re
import io
import numpy as np
import pandas as pd
from difflib import SequenceMatcher


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
    dt = pd.to_datetime(series, errors="coerce", dayfirst=dayfirst, infer_datetime_format=True)
    return dt


def normalize_text(x: str) -> str:
    x = "" if pd.isna(x) else str(x)
    x = x.strip().lower()
    x = re.sub(r"[^a-z0-9\s]", " ", x)
    x = re.sub(r"\s+", " ", x).strip()
    return x


def similarity(a: str, b: str) -> float:
    return SequenceMatcher(None, a, b).ratio()


def harmonize_names(series: pd.Series, threshold: float = 0.92, min_len: int = 3, max_uniques: int = 2000):
    """
    Fuzzy harmonize values in a column.
    Returns:
      canonical_series, mapping_df
    Notes:
      - This is O(U^2) on unique normalized values. For huge U it can be slow.
      - We cap uniques to max_uniques for demo safety.
    """
    s_raw = series.fillna("").astype(str)
    s_norm = s_raw.map(normalize_text)

    # Limit unique values to avoid worst-case blowups
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

    # choose canonical by max frequency within each cluster
    cluster_best = {}
    for cluster in clusters:
        best = max(cluster, key=lambda x: freq.get(x, 0))
        for member in cluster:
            cluster_best[member] = best

    canon_norm = s_norm.map(lambda x: cluster_best.get(x, x))

    # pick most common raw string per canonical normalized value
    tmp = pd.DataFrame({"raw": s_raw, "canon_norm": canon_norm})
    best_raw = (
        tmp.groupby("canon_norm")["raw"]
        .agg(lambda x: x.value_counts().index[0] if len(x) else "")
        .to_dict()
    )
    canon_final = canon_norm.map(lambda x: best_raw.get(x, x))

    mapping_df = (
        tmp.assign(canonical=canon_final)
           .drop_duplicates()
           .sort_values(["canonical", "raw"])
           .reset_index(drop=True)
    )

    return canon_final, mapping_df


def convert_to_inr(amount: pd.Series, currency: pd.Series | None, fx_table: dict, default_currency: str = "INR"):
    """
    Convert amounts to INR.
    - If currency column missing (currency=None): assumes default_currency for all rows.
    - Future-ready: if currency column exists later, pass it to get row-wise conversion.

    Returns:
      amount_in_inr, missing_fx_mask, currency_used
    """
    amt = pd.to_numeric(amount, errors="coerce")

    if currency is None:
        cur = pd.Series([default_currency] * len(amt), index=amt.index)
    else:
        cur = currency.fillna(default_currency).astype(str)

    cur = cur.str.upper().str.strip()
    fx = cur.map(lambda c: fx_table.get(c, np.nan))

    inr = amt * fx
    missing = fx.isna()

    return inr, missing, cur
