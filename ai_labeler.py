import os
import streamlit as st
from openai import OpenAI

def get_api_key():
    if "OPENAI_API_KEY" in st.secrets:
        return st.secrets["OPENAI_API_KEY"]
    return st.session_state.get("OPENAI_API_KEY_SESSION") or os.getenv("OPENAI_API_KEY")

def get_model_name():
    if "OPENAI_MODEL" in st.secrets:
        return st.secrets["OPENAI_MODEL"]
    return os.getenv("OPENAI_MODEL", "gpt-4.1-mini")

def get_client(api_key: str):
    return OpenAI(api_key=api_key)

@st.cache_data(show_spinner=False)
def rename_category_cached(level: str, l1: str, raw_label: str, examples: tuple, model: str):
    api_key = get_api_key()
    if not api_key:
        return raw_label

    client = get_client(api_key)

    prompt = f"""
You are designing a procurement taxonomy for Materials and Services.

Return a SHORT, clean category name (2-4 words max).

Level: {level}
L1: {l1}
Raw keywords: {raw_label}

Examples:
- """ + "\n- ".join(list(examples)[:12]) + """

Rules:
- Output ONLY the category name (no quotes, no punctuation).
- Use standard procurement taxonomy terms (e.g., Mechanical, Electrical, Valves, Pumps, IT Services, Logistics, Repair).
- If unclear, choose the closest broad business category.
"""
    resp = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "developer", "content": "You are a procurement taxonomy expert."},
            {"role": "user", "content": prompt}
        ],
        temperature=0.2
    )
    return (resp.choices[0].message.content or raw_label).strip()
