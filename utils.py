import re
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
    return pd.to_datetime(series, errors="coerce", dayfirst=dayfirst, infer_datetime_format=True)


def normalize_description(series: pd.Series) -> pd.Series:
    s = series.fillna("").astype(str)
    s = s.str.replace(r"\s+", " ", regex=True).str.strip()
    return s


EXCLUDE_HARMONIZE_PATTERNS = [
    r"\bid\b", r"\bcode\b", r"\bsku\b", r"\bhsn\b", r"\bsac\b", r"\bpan\b", r"\bgstin\b",
    r"\bmaterial\s*id\b", r"\bitem\s*id\b", r"\bvendor\s*id\b", r"\bsupplier\s*id\b",
    r"\bgl\b", r"\baccount\b", r"\basset\s*id\b", r"\bserial\b"
]

def is_master_like_column(colname: str) -> bool:
    c = (colname or "").strip().lower()
    return any(re.search(pat, c) for pat in EXCLUDE_HARMONIZE_PATTERNS)


def _normalize_text(x: str) -> str:
    x = "" if pd.isna(x) else str(x)
    x = x.strip().lower()
    x = re.sub(r"[^a-z0-9\s]", " ", x)
    x = re.sub(r"\s+", " ", x).strip()
    return x


def _similarity(a: str, b: str) -> float:
    return SequenceMatcher(None, a, b).ratio()


def harmonize_names(series: pd.Series, threshold: float = 0.92, min_len: int = 3, max_uniques: int = 2000):
    s_raw = series.fillna("").astype(str)
    s_norm = s_raw.map(_normalize_text)

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
            if len(u) >= min_len and len(v) >= min_len and _similarity(u, v) >= threshold:
                assigned[v] = u
                cluster.append(v)
        clusters.append(cluster)

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


def parse_fx_to_inr(text: str) -> dict:
    fx = {}
    for line in (text or "").splitlines():
        if "=" in line:
            k, v = line.split("=", 1)
            k = k.strip().upper()
            try:
                fx[k] = float(v.strip())
            except:
                pass
    return fx


def convert_currency(
    amount: pd.Series,
    source_currency: pd.Series | None,
    target_currency: str,
    fx_to_inr: dict,
    default_source: str = "INR"
):
    amt = pd.to_numeric(amount, errors="coerce")

    if source_currency is None:
        src = pd.Series([default_source] * len(amt), index=amt.index)
    else:
        src = source_currency.fillna(default_source).astype(str)

    src = src.astype(str).str.upper().str.strip()
    tgt = str(target_currency).upper().strip()

    src_fx = src.map(lambda c: fx_to_inr.get(c, np.nan))
    tgt_fx = fx_to_inr.get(tgt, np.nan)

    missing = src_fx.isna() | pd.isna(tgt_fx)

    inr = amt * src_fx
    converted = inr / tgt_fx if not pd.isna(tgt_fx) else pd.Series([np.nan] * len(amt), index=amt.index)

    return converted, src, tgt, missing
