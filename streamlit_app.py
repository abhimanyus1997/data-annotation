import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime
import plotly.express as px
from sqlalchemy import create_engine, text

# =====================================================
# CONFIG
# =====================================================
st.set_page_config(
    page_title="AnnotatePro SQL + In-Memory",
    layout="wide",
    initial_sidebar_state="expanded"
)

# =====================================================
# STATE MANAGEMENT
# =====================================================
if "db" not in st.session_state:
    st.session_state.db = {}

if "active_cid" not in st.session_state:
    st.session_state.active_cid = None

if "annotator" not in st.session_state:
    st.session_state.annotator = ""

# =====================================================
# HELPERS
# =====================================================
def initialize_df(df, labels, engine=None, table_name=None):
    """Ensures necessary annotation columns exist."""
    df = df.copy()
    for col in ["label", "confidence", "notes", "annotated_by", "annotated_at"]:
        if col not in df.columns:
            df[col] = None
    
    config = {
        "df": df,
        "labels": [l.strip() for l in labels.split(",")],
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "engine": engine,
        "table_name": table_name
    }
    return config

def load_demo():
    df = pd.DataFrame({
        "ID": range(1, 6),
        "Text": ["Login fails on iOS 17", "Add dark mode", "Amazing support", "Checkout timeout", "API v3?"],
        "System_Log": ["500", "REQ", "OK", "TIMEOUT", "INFO"]
    })
    st.session_state.db["Demo_Feedback"] = initialize_df(df, "Critical,Bug,Feature,Support,General")
    st.session_state.active_cid = "Demo_Feedback"

# =====================================================
# SIDEBAR
# =====================================================
with st.sidebar:
    st.title("AnnotatePro")
    st.caption("v2026.1 - SQL Cloud Enabled")

    st.session_state.annotator = st.text_input("👤 Annotator ID", value=st.session_state.annotator)

    st.divider()

    if st.session_state.db:
        st.session_state.active_cid = st.selectbox(
            "Active Campaign",
            options=list(st.session_state.db.keys())
        )
    else:
        if st.button("🚀 Load Demo Data", width="stretch"):
            load_demo()
            st.rerun()

    st.divider()
    
    # --- SQL CONNECTION ---
    with st.expander("🔗 SQL Database"):
        url = st.text_input("SQLAlchemy URL", placeholder="sqlite:///local.db")
        tbl = st.text_input("Table Name")
        sql_labs = st.text_input("SQL Labels", "Positive,Negative")
        if st.button("Connect & Fetch"):
            try:
                engine = create_engine(url)
                df_sql = pd.read_sql(f"SELECT * FROM {tbl}", engine)
                st.session_state.db[tbl] = initialize_df(df_sql, sql_labs, engine, tbl)
                st.session_state.active_cid = tbl
                st.success("Database Connected!")
                st.rerun()
            except Exception as e:
                st.error(f"Connection Failed: {e}")

    # --- CSV UPLOAD ---
    with st.expander("📁 CSV Upload"):
        name = st.text_input("Project Name")
        file = st.file_uploader("CSV File", type="csv")
        csv_labs = st.text_input("CSV Labels", "A,B,C")
        if st.button("Create CSV Campaign"):
            if name and file:
                df_csv = pd.read_csv(file)
                st.session_state.db[name] = initialize_df(df_csv, csv_labs)
                st.session_state.active_cid = name
                st.rerun()

# =====================================================
# MAIN APP LOGIC
# =====================================================
if not st.session_state.active_cid:
    st.title("Welcome to AnnotatePro")
    st.info("Please use the sidebar to connect to a SQL database or upload a CSV file.")
    st.stop()

proj = st.session_state.db[st.session_state.active_cid]
df = proj["df"]

# Stats calculation
total = len(df)
done = df["label"].notna().sum()
remaining = total - done

tab1, tab2, tab3, tab4 = st.tabs(["📊 Overview", "🏷️ Annotator", "🔍 Data", "🧪 Quality"])

# 1. OVERVIEW
with tab1:
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total", total)
    c2.metric("Completed", done, f"{int(done/total*100) if total > 0 else 0}%")
    c3.metric("Pending", remaining)
    c4.metric("Annotators", df["annotated_by"].nunique())

    st.divider()

    if done > 0:
        # Fixed Pandas Aggregation for 2026 Compatibility
        label_counts = df["label"].value_counts().reset_index()
        label_counts.columns = ["label", "count"]

        col_l, col_r = st.columns(2)
        with col_l:
            fig_bar = px.bar(label_counts, x="label", y="count", text="count", title="Label Distribution")
            st.plotly_chart(fig_bar, width="stretch")
        with col_r:
            fig_pie = px.pie(label_counts, names="label", values="count", hole=0.4, title="Label Share")
            st.plotly_chart(fig_pie, width="stretch")
    else:
        st.info("No data annotated yet.")

# 2. ANNOTATOR
with tab2:
    if not st.session_state.annotator:
        st.warning("⚠️ Enter an Annotator ID in the sidebar to begin.")
    else:
        queue = df[df["label"].isna()]
        if queue.empty:
            st.success("🎯 All records annotated!")
        else:
            idx = queue.index[0] # Grab first available record
            st.progress(done / total)
            
            left, right = st.columns([2, 1])
            with left:
                st.markdown(f"#### Record Details (Index: {idx})")
                for col in df.columns:
                    if col not in ["label", "confidence", "notes", "annotated_by", "annotated_at"]:
                        st.text_input(col, value=str(df.at[idx, col]), disabled=True)

            with right:
                st.markdown("#### Annotation")
                new_label = st.radio("Label", proj["labels"])
                new_conf = st.slider("Confidence", 1, 5, 3)
                new_notes = st.text_area("Notes")

                if st.button("✅ Submit & Sync", width="stretch"):
                    # Update Memory
                    df.at[idx, "label"] = new_label
                    df.at[idx, "confidence"] = new_conf
                    df.at[idx, "notes"] = new_notes
                    df.at[idx, "annotated_by"] = st.session_state.annotator
                    df.at[idx, "annotated_at"] = datetime.now()

                    # Sync to SQL if engine exists
                    if proj["engine"]:
                        try:
                            # Using 'replace' for simplicity in this demo; 
                            # in large apps, use SQL UPDATE for performance.
                            df.to_sql(proj["table_name"], proj["engine"], if_exists="replace", index=False)
                            st.toast("Synced to SQL")
                        except Exception as e:
                            st.error(f"Sync Error: {e}")
                    
                    st.rerun()

# 3. DATA
with tab3:
    st.dataframe(df, width="stretch")
    st.download_button("⬇ Export to CSV", df.to_csv(index=False), file_name="export.csv")

# 4. QUALITY
with tab4:
    st.subheader("Low Confidence Audit")
    low_df = df[df["confidence"].fillna(5).astype(float) <= 2]
    st.dataframe(low_df, width="stretch")

    st.subheader("Performance by Annotator")
    if df["annotated_by"].notna().any():
        # Cross-tabulation for annotator performance
        perf = pd.crosstab(df["annotated_by"], df["label"])
        st.bar_chart(perf)