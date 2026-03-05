# streamlit_app/app.py - Main Streamlit UI for Order Reconciliation System
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import json
import streamlit as st
import pandas as pd
from datetime import datetime

from core.db import init_db
from core import repositories as repo
from core.services import compute_template_hash, start_invoice_pipeline
from core.metrics import get_dashboard_metrics
from agents.graph import recon_graph

# --- Page config ---
st.set_page_config(
    page_title="Order Reconciliation AI",
    page_icon="📊",
    layout="wide",
)

# --- Init DB on startup ---
init_db()

# --- Sidebar navigation ---
page = st.sidebar.selectbox(
    "Navigate",
    ["Upload & Run Pipeline", "Exceptions Dashboard", "Observability Metrics"],
)


# ============================================================
# PAGE 1: Upload & Run Pipeline
# ============================================================
if page == "Upload & Run Pipeline":
    st.title("Invoice Reconciliation Pipeline")
    st.markdown("Upload an invoice JSON and run the multi-agent reconciliation pipeline.")

    uploaded_file = st.file_uploader("Upload Invoice JSON", type=["json"])

    if uploaded_file is not None:
        raw = uploaded_file.read().decode("utf-8")
        invoice_json = json.loads(raw)

        st.subheader("Invoice Preview")
        st.json(invoice_json)

        vendor_id = invoice_json.get("vendor_id", "V-UNKNOWN")
        vendor_name = invoice_json.get("vendor_name", "Unknown Vendor")
        template_hash = compute_template_hash(invoice_json)

        if st.button("Run Reconciliation Pipeline", type="primary"):
            invoice_id = start_invoice_pipeline(raw, vendor_id, vendor_name, template_hash)
            st.session_state["current_invoice_id"] = invoice_id
            st.session_state["pipeline_logs"] = []

            initial_state = {
                "invoice_id": invoice_id,
                "invoice_json": invoice_json,
                "logs": [],
                "pipeline_status": "UPLOADED",
            }

            # ---- Pipeline Stepper UI ----
            steps = ["UPLOADED", "EXTRACTING", "MATCHING", "EXCEPTION_HANDLING", "COMPLETED"]
            step_labels = {
                "UPLOADED": "Upload",
                "EXTRACTING": "Extractor Agent",
                "MATCHING": "Matcher Agent",
                "EXCEPTION_HANDLING": "Exception Handler",
                "COMPLETED": "Completed",
            }

            progress_placeholder = st.empty()
            log_placeholder = st.empty()
            status_placeholder = st.empty()

            with st.spinner("Running reconciliation pipeline..."):
                final_state = recon_graph.invoke(initial_state)

            st.session_state["pipeline_logs"] = final_state.get("logs", [])
            current_status = final_state.get("pipeline_status", "COMPLETED")

            # show stepper
            cols = st.columns(len(steps))
            for i, step in enumerate(steps):
                done = steps.index(step) <= steps.index(current_status)
                icon = "green" if done else "gray"
                cols[i].markdown(
                    f"<div style='text-align:center; color:{icon}; font-weight:bold;'>{'checkmark' if done else 'o'} {step_labels[step]}</div>",
                    unsafe_allow_html=True,
                )

            st.success(f"Pipeline completed! Status: {current_status}")

    # Show pipeline logs and results
    if "current_invoice_id" in st.session_state:
        invoice_id = st.session_state["current_invoice_id"]
        invoice = repo.get_invoice_by_id(invoice_id)

        if invoice:
            st.subheader(f"Invoice #{invoice_id} - Status: {invoice['status']}")
            col1, col2, col3 = st.columns(3)
            col1.metric("Vendor", invoice.get("vendor_name", "N/A"))
            col2.metric("Confidence", f"{(invoice.get('extraction_confidence') or 0):.0%}")
            col3.metric("Status", invoice.get("status", "N/A"))

        if st.session_state.get("pipeline_logs"):
            st.subheader("Pipeline Logs")
            for log_line in st.session_state["pipeline_logs"]:
                st.write(f"- {log_line}")

        # Show extracted lines
        lines = repo.get_invoice_lines(invoice_id)
        if lines:
            st.subheader("Extracted Invoice Lines")
            st.dataframe(pd.DataFrame(lines))


# ============================================================
# PAGE 2: Exceptions Dashboard
# ============================================================
elif page == "Exceptions Dashboard":
    st.title("Exceptions Dashboard")
    st.markdown("Review and resolve reconciliation exceptions requiring human attention.")

    exceptions = repo.get_unresolved_exceptions()

    if not exceptions:
        st.success("No unresolved exceptions! All reconciliations are clean.")
    else:
        st.warning(f"{len(exceptions)} unresolved exception(s) need attention.")

        df = pd.DataFrame(exceptions)
        st.dataframe(df, use_container_width=True)

        st.subheader("Resolve an Exception")
        exc_id = st.number_input("Exception ID to resolve", min_value=1, step=1)
        resolved_by = st.text_input("Your name / ID")

        if st.button("Mark as Resolved"):
            if resolved_by.strip():
                repo.resolve_exception(
                    int(exc_id),
                    resolved_by.strip(),
                    datetime.utcnow().isoformat(),
                )
                st.success(f"Exception #{exc_id} resolved by {resolved_by}.")
                st.rerun()
            else:
                st.error("Please enter your name/ID before resolving.")


# ============================================================
# PAGE 3: Observability Metrics
# ============================================================
elif page == "Observability Metrics":
    st.title("Observability Metrics")
    st.markdown("Track pipeline performance, extraction accuracy, and mismatch rates.")

    metrics = get_dashboard_metrics()

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Total Runs", metrics["total_runs"])
    col2.metric("Avg Mismatch Rate", f"{metrics['avg_mismatch_rate']:.1%}")
    col3.metric("Avg Extraction Confidence", f"{metrics['avg_confidence']:.1%}")
    col4.metric("Avg Latency (ms)", f"{metrics['avg_latency_ms']:.0f}")

    if metrics.get("history"):
        st.subheader("Run History")
        df = pd.DataFrame(metrics["history"])
        st.dataframe(df, use_container_width=True)

        st.subheader("Mismatch Rate Over Time")
        if "run_timestamp" in df.columns and "mismatch_rate" in df.columns:
            chart_df = df[["run_timestamp", "mismatch_rate"]].set_index("run_timestamp")
            st.line_chart(chart_df)

        st.subheader("Extraction Confidence Over Time")
        if "avg_extraction_confidence" in df.columns:
            chart_df2 = df[["run_timestamp", "avg_extraction_confidence"]].set_index("run_timestamp")
            st.line_chart(chart_df2)
    else:
        st.info("No metrics data yet. Run the pipeline first.")
