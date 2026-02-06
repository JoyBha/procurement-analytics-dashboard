import os
import json
import streamlit as st
from openai import OpenAI  # [5](https://pythonandvba.com/blog/how-to-create-a-streamlit-multi-page-web-app/)

def get_llm_settings():
    # Defaults
    provider = st.secrets.get("LLM_PROVIDER", "openai") if hasattr(st, "secrets") else "openai"
    api_key = st.secrets.get("OPENAI_API_KEY", "") if hasattr(st, "secrets") else ""
    model = st.secrets.get("OPENAI_MODEL", "gpt-4.1-mini") if hasattr(st, "secrets") else "gpt-4.1-mini"
    base_url = st.secrets.get("OPENAI_BASE_URL", "https://api.openai.com/v1") if hasattr(st, "secrets") else "https://api.openai.com/v1"

    # Session overrides (optional UI entry)
    api_key = st.session_state.get("OPENAI_API_KEY_SESSION", api_key)
    model = st.session_state.get("OPENAI_MODEL_SESSION", model)
    base_url = st.session_state.get("OPENAI_BASE_URL_SESSION", base_url)

    return provider, api_key, model, base_url

def get_client(api_key: str, base_url: str):
    return OpenAI(api_key=api_key, base_url=base_url)  # OpenAI SDK supports client usage [5](https://pythonandvba.com/blog/how-to-create-a-streamlit-multi-page-web-app/)

SYSTEM_INSTRUCTIONS = """
You are a procurement taxonomy expert.
Given a short item description (material or service), produce a 4-level hierarchy.

Return STRICT JSON:
{
  "L1": "Material|Service",
  "L2": "...",
  "L3": "...",
  "L4": "..."
}

Rules:
- Keep each level 1–4 words.
- Use procurement-friendly categories (Mechanical, Electrical, IT Services, Logistics, Repair, etc.).
- If uncertain, choose the closest broad category.
"""

@st.cache_data(show_spinner=False)
def classify_description(desc: str, model: str, api_key: str, base_url: str) -> dict:
    client = get_client(api_key, base_url)
    prompt = f"Description: {desc}"
    resp = client.chat.completions.create(  # chat completions per SDK [5](https://pythonandvba.com/blog/how-to-create-a-streamlit-multi-page-web-app/)
        model=model,
        messages=[
            {"role": "developer", "content": SYSTEM_INSTRUCTIONS},
            {"role": "user", "content": prompt},
        ],
        temperature=0.2
    )
    txt = resp.choices[0].message.content.strip()
    # Try parse JSON
    try:
        return json.loads(txt)
    except Exception:
        # fallback heuristic
        lower = desc.lower()
        l1 = "Service" if any(k in lower for k in ["service", "repair", "maintenance", "consult", "support", "license"]) else "Material"
        return {"L1": l1, "L2": "Other", "L3": "Other", "L4": "Other"}
