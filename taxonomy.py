import numpy as np
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.cluster import KMeans


SERVICE_HINTS = [
    "service","maintenance","repair","amc","consulting","freight","transport",
    "security","manpower","audit","legal","software","license","licence","subscription",
    "training","calibration","inspection","testing","installation","support","contract"
]


def clean_text(s: pd.Series) -> pd.Series:
    x = s.fillna("").astype(str).str.lower()
    x = x.str.replace(r"[^a-z0-9\s]", " ", regex=True)
    x = x.str.replace(r"\s+", " ", regex=True).str.strip()
    return x


def infer_l1(desc: pd.Series) -> pd.Series:
    t = clean_text(desc)

    def f(x: str) -> str:
        return "Service" if any(k in x for k in SERVICE_HINTS) else "Material"

    return t.map(f)


def safe_k(n: int, desired: int) -> int:
    if n <= 2:
        return 1
    return max(1, min(desired, n - 1))


def top_terms(vectorizer: TfidfVectorizer, kmeans: KMeans, cid: int, top_n=4) -> str:
    centroid = kmeans.cluster_centers_[cid]
    terms = vectorizer.get_feature_names_out()
    idx = np.argsort(centroid)[::-1][:top_n]
    lbl = " ".join([terms[i] for i in idx if centroid[i] > 0]).strip()
    return lbl if lbl else f"Cluster {cid}"


def compute_l4_phrase(texts, max_texts=300):
    """
    Heuristic L4: most common bigram/trigram among sample texts.
    """
    grams = []
    for t in texts[:max_texts]:
        tokens = t.split()
        for n in (2, 3):
            for i in range(len(tokens) - n + 1):
                g = " ".join(tokens[i:i+n])
                if len(g) >= 6:
                    grams.append(g)
    if not grams:
        return ""
    vals, counts = np.unique(grams, return_counts=True)
    return vals[np.argmax(counts)]


def generate_taxonomy(df: pd.DataFrame, desc_col: str, l2=10, l3=4, random_state=42) -> pd.DataFrame:
    """
    Returns df with:
      L1, L2, L3, L4, TaxonomyPath (raw labels; App2 will AI-rename them)
    """
    out = df.copy()
    out["_taxo_text"] = clean_text(out[desc_col])
    out["L1"] = infer_l1(out[desc_col])

    results = []

    for l1_name in ["Material", "Service"]:
        sub = out[out["L1"] == l1_name].copy()
        if sub.empty:
            continue

        vec = TfidfVectorizer(max_features=8000, ngram_range=(1, 2), stop_words="english")
        X = vec.fit_transform(sub["_taxo_text"])

        k2 = safe_k(X.shape[0], l2)
        km2 = KMeans(n_clusters=k2, random_state=random_state, n_init=10)
        sub["L2_id"] = km2.fit_predict(X)
        sub["L2"] = sub["L2_id"].map(lambda cid: top_terms(vec, km2, cid, top_n=4))

        # L3 within each L2
        sub["L3_id"] = -1
        sub["L3"] = ""
        for cid in sorted(sub["L2_id"].unique()):
            idx = sub.index[sub["L2_id"] == cid].tolist()
            sub2 = sub.loc[idx]

            if len(sub2) < 8:
                sub.loc[idx, "L3"] = sub.loc[idx, "L2"]
                sub.loc[idx, "L3_id"] = 0
                continue

            vec3 = TfidfVectorizer(max_features=4000, ngram_range=(1, 2), stop_words="english")
            X3 = vec3.fit_transform(sub2["_taxo_text"])

            k3 = safe_k(X3.shape[0], l3)
            km3 = KMeans(n_clusters=k3, random_state=random_state, n_init=10)
            ids3 = km3.fit_predict(X3)

            labels3 = {scid: top_terms(vec3, km3, scid, top_n=3) for scid in np.unique(ids3)}
            sub.loc[idx, "L3_id"] = ids3
            sub.loc[idx, "L3"] = [labels3[i] for i in ids3]

        # L4 heuristic per (L2, L3)
        l4_map = {}
        for (l2_lbl, l3_lbl), grp in sub.groupby(["L2", "L3"]):
            phrase = compute_l4_phrase(grp["_taxo_text"].tolist())
            l4_map[(l2_lbl, l3_lbl)] = phrase if phrase else l3_lbl

        sub["L4"] = sub.apply(lambda r: l4_map.get((r["L2"], r["L3"]), r["L3"]), axis=1)

        sub["TaxonomyPath"] = sub["L1"] + " > " + sub["L2"] + " > " + sub["L3"] + " > " + sub["L4"]

        results.append(sub.drop(columns=["L2_id", "L3_id"], errors="ignore"))

    return pd.concat(results, axis=0).sort_index()
