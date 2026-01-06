import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime
import plotly.express as px

# =====================================================
# CONFIG
# =====================================================
st.set_page_config(
    page_title="AnnotatePro (In-Memory)",
    layout="wide",
    initial_sidebar_state="expanded"
)

# =====================================================
# STATE (IN-MEMORY ONLY)
# =====================================================
if "db" not in st.session_state:
    st.session_state.db = {}

if "active_cid" not in st.session_state:
    st.session_state.active_cid = None

if "annotator" not in st.session_state:
    st.session_state.annotator = ""

# =====================================================
# STYLES
# =====================================================
st.markdown("""
<style>
.stMetric {
    padding: 15px;
    border-radius: 10px;
    border: 1px solid #e5e7eb;
}
</style>
""", unsafe_allow_html=True)

# =====================================================
# HELPERS
# =====================================================
def create_campaign(name, df, labels):
    df = df.copy()
    for col in ["label", "confidence", "notes", "annotated_by", "annotated_at"]:
        if col not in df.columns:
            df[col] = None

    st.session_state.db[name] = {
        "df": df,
        "labels": [l.strip() for l in labels.split(",")],
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M")
    }
    st.session_state.active_cid = name

def load_demo():
    df = pd.DataFrame({
        "ID": range(1, 6),
        "Text": [
            "Login fails on iOS 17",
            "Please add dark mode",
            "Support team was amazing",
            "Checkout timeout issue",
            "Is API v3 coming?"
        ],
        "System_Log": ["500", "REQ", "OK", "TIMEOUT", "INFO"]
    })
    create_campaign(
        "Demo_Feedback",
        df,
        "Critical,Bug,Feature,Support,General"
    )

# =====================================================
# SIDEBAR
# =====================================================
with st.sidebar:
    st.title("AnnotatePro")
    st.caption("In-Memory Edition")

    st.session_state.annotator = st.text_input(
        "👤 Annotator ID",
        value=st.session_state.annotator
    )

    st.divider()

    if st.session_state.db:
        st.session_state.active_cid = st.selectbox(
            "Active Campaign",
            options=list(st.session_state.db.keys())
        )
    else:
        if st.button("🚀 Load Demo"):
            load_demo()
            st.rerun()

    st.divider()
    with st.expander("📁 New Campaign"):
        name = st.text_input("Project Name")
        file = st.file_uploader("CSV File", type="csv")
        labels = st.text_input("Labels (comma separated)", "Positive,Negative")

        if st.button("Create Campaign"):
            if name and file:
                create_campaign(name, pd.read_csv(file), labels)
                st.rerun()

# =====================================================
# MAIN
# =====================================================
if not st.session_state.active_cid:
    st.title("Welcome to AnnotatePro")
    st.write("Create or select a campaign to begin.")
    st.stop()

proj = st.session_state.db[st.session_state.active_cid]
df = proj["df"]

total = len(df)
done = df["label"].notna().sum()
remaining = total - done

tab1, tab2, tab3, tab4 = st.tabs(
    ["📊 Overview", "🏷️ Annotator", "🔍 Data", "🧪 Quality"]
)

# =====================================================
# OVERVIEW (PLOTLY)
# =====================================================
with tab1:
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total", total)
    c2.metric("Completed", done, f"{int(done/total*100)}%")
    c3.metric("Pending", remaining)
    c4.metric("Annotators", df["annotated_by"].nunique())

    st.divider()

    if done:
        # FIX: Robust counting logic
        label_counts = df["label"].value_counts().reset_index()
        label_counts.columns = ["label", "count"]

        col_l, col_r = st.columns(2)

        with col_l:
            st.subheader("Label Distribution")
            fig_bar = px.bar(
                label_counts,
                x="label",
                y="count",
                text="count"
            )
            fig_bar.update_traces(textposition="outside")
            # FIX: Updated width parameter
            st.plotly_chart(fig_bar, width="stretch")

        with col_r:
            st.subheader("Label Share")
            fig_pie = px.pie(
                label_counts,
                names="label",
                values="count",
                hole=0.4
            )
            # FIX: Updated width parameter
            st.plotly_chart(fig_pie, width="stretch")

# =====================================================
# ANNOTATOR
# =====================================================
with tab2:
    if not st.session_state.annotator:
        st.warning("Enter an Annotator ID in the sidebar.")
    else:
        queue = df[df["label"].isna()]
        if queue.empty:
            st.success("🎯 All records annotated")
        else:
            idx = np.random.choice(queue.index)

            st.progress(done / total)
            st.markdown(f"### Record {idx + 1} of {total}")

            left, right = st.columns([2, 1])

            with left:
                for col in df.columns:
                    if col not in ["label", "confidence", "notes", "annotated_by", "annotated_at"]:
                        st.text_area(col, value=str(df.at[idx, col]), disabled=True)

            with right:
                label = st.radio("Label", proj["labels"])
                confidence = st.slider("Confidence", 1, 5, 3)
                notes = st.text_area("Notes")

                if st.button("✅ Submit & Next", use_container_width=True):
                    df.at[idx, "label"] = label
                    df.at[idx, "confidence"] = confidence
                    df.at[idx, "notes"] = notes
                    df.at[idx, "annotated_by"] = st.session_state.annotator
                    df.at[idx, "annotated_at"] = datetime.now()
                    st.toast("Saved")
                    st.rerun()

# =====================================================
# DATA
# =====================================================
with tab3:
    st.dataframe(df, use_container_width=True)
    st.download_button(
        "⬇ Export CSV",
        df.to_csv(index=False),
        file_name=f"{st.session_state.active_cid}.csv"
    )

# =====================================================
# QUALITY
# =====================================================
with tab4:
    st.subheader("Low Confidence (≤2)")
    low = df[df["confidence"].notna() & (df["confidence"] <= 2)]
    st.dataframe(low, use_container_width=True)

    st.subheader("Labels by Annotator")
    if df["annotated_by"].notna().any():
        qc = df.groupby(["annotated_by", "label"]).size().unstack().fillna(0)
        st.bar_chart(qc)
    else:
        st.info("No annotations yet.")
