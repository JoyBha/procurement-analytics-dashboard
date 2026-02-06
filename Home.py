import streamlit as st

st.set_page_config(
    page_title="Procurement Analytics Dashboard",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="collapsed"
)  # Page title/config via Streamlit API [4](https://typethepipe.com/post/streamlit-chat-conversational-app-st-chat_message/)

st.title("📊 Procurement Analytics Dashboard")
st.caption("Multi-app suite: Data Harmonization → AI Taxonomy → Procurement Dashboard")

st.markdown("### Choose an app")

c1, c2, c3 = st.columns(3)

with c1:
    st.subheader("🧹 App 1")
    st.write("**Data Harmonization**")
    st.write("- Standardize date\n- Drop missing rows\n- Harmonize supplier/material names\n- Assume INR (currency-ready for later)")
    if st.button("Open Data Harmonization →"):
        st.switch_page("pages/1_Data_Harmonization.py")  # Programmatic navigation [5](https://developers.openai.com/cookbook/examples/azure/chat)

with c2:
    st.subheader("🧭 App 2")
    st.write("**AI-assisted Taxonomy**")
    st.write("- Material vs Service\n- L1→L4 hierarchy\n- AI labels (Mechanical → Valve → Ball Valve)")
    if st.button("Open Taxonomy Generator →"):
        st.switch_page("pages/2_Generate_Taxonomy.py")  # [5](https://developers.openai.com/cookbook/examples/azure/chat)

with c3:
    st.subheader("📈 App 3")
    st.write("**Dashboard**")
    st.write("- No sidebar filters\n- Slice/dice via perspectives\n- Group-by any field")
    if st.button("Open Dashboard →"):
        st.switch_page("pages/3_Procurement_Dashboard.py")  # [5](https://developers.openai.com/cookbook/examples/azure/chat)

st.divider()
st.info("Tip: Run App 1 first, then App 2, then App 3.")
