# streamlit_app/app.py - Main Streamlit UI for Order Reconciliation System
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import json
from pathlib import Path
import streamlit as st
import pandas as pd
from datetime import datetime, timezone

from core.db import init_db, get_connection
from core import repositories as repo
from core import logger as pipeline_logger
from core.services import compute_template_hash, start_invoice_pipeline
from core.metrics import get_dashboard_metrics
from core.config import RULES_DIR, RAG_PERSIST_DIR
from core.rules_rag import ask_rules, reload_rules
from agents.graph import recon_graph
from streamlit_app.log_viewer import render_log_viewer

# --- Page config ---
st.set_page_config(
    page_title="Order Reconciliation AI",
    page_icon="📊",
    layout="wide",
)

# --- Init DB on startup ---
init_db()

# --- Sidebar navigation ---
PAGES = [
    "Upload & Run Pipeline",
    "Database Explorer",
    "Order Tracker",
    "Exceptions Dashboard",
    "RAG Management",
    "Observability Metrics",
]

st.sidebar.title("📊 Order Recon AI")
st.sidebar.markdown("---")
page = st.sidebar.radio("Navigate", PAGES)


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
# PAGE 2: Database Explorer
# ============================================================
elif page == "Database Explorer":
    st.title("🗄️ Database Explorer")
    st.markdown("Browse and inspect all database tables used by the reconciliation system.")

    TABLE_OPTIONS = [
        "orders",
        "order_lines",
        "invoices",
        "invoice_lines",
        "reconciliations",
        "reconciliation_lines",
        "exceptions",
        "invoice_templates",
        "metrics_runs",
        "pipeline_logs",
    ]

    selected_table = st.selectbox("Select Table", TABLE_OPTIONS, key="db_table_select")

    # Fetch data based on selected table
    TABLE_FETCHERS = {
        "orders": repo.get_all_orders,
        "invoices": repo.get_all_invoices,
        "reconciliations": repo.get_all_reconciliations,
        "exceptions": repo.get_all_exceptions,
        "invoice_templates": repo.get_all_templates,
        "metrics_runs": repo.get_metrics_history,
    }

    def _fetch_table(table_name: str) -> list:
        if table_name not in TABLE_OPTIONS:
            return []
        fetcher = TABLE_FETCHERS.get(table_name)
        if fetcher:
            return fetcher()
        with get_connection() as conn:
            rows = conn.execute(
                f"SELECT * FROM [{table_name}] ORDER BY id DESC LIMIT 500"
            ).fetchall()
            return [dict(r) for r in rows]

    rows = _fetch_table(selected_table)

    if not rows:
        st.info(f"No data in **{selected_table}** yet. Run the pipeline to populate data.")
    else:
        df = pd.DataFrame(rows)

        # Summary metrics
        col1, col2 = st.columns(2)
        col1.metric("Total Rows", len(df))
        col2.metric("Columns", len(df.columns))

        # Column filter
        st.markdown("---")
        search_col, search_val = st.columns(2)
        with search_col:
            filter_column = st.selectbox(
                "Filter by column", ["(no filter)"] + list(df.columns),
                key="db_filter_col",
            )
        with search_val:
            filter_value = st.text_input("Filter value (contains)", key="db_filter_val")

        if filter_column != "(no filter)" and filter_value:
            df = df[df[filter_column].astype(str).str.contains(filter_value, case=False, na=False)]
            st.caption(f"Showing {len(df)} row(s) matching **{filter_column}** contains '{filter_value}'")

        st.dataframe(df, use_container_width=True)

        # Export
        csv = df.to_csv(index=False)
        st.download_button(
            label=f"Export {selected_table} as CSV",
            data=csv,
            file_name=f"{selected_table}.csv",
            mime="text/csv",
        )


# ============================================================
# PAGE 3: Order Tracker
# ============================================================
elif page == "Order Tracker":
    st.title("📦 Order Tracker")
    st.markdown("Track orders end-to-end: from PO through invoice reconciliation to exception resolution.")

    tracker_tab1, tracker_tab2, tracker_tab3 = st.tabs([
        "📋 Invoice History",
        "🔗 Reconciliation Details",
        "📜 Pipeline Logs",
    ])

    # ---- Tab 1: Invoice History ----
    with tracker_tab1:
        st.subheader("All Processed Invoices")
        invoices = repo.get_all_invoices()

        if not invoices:
            st.info("No invoices processed yet. Upload an invoice to get started.")
        else:
            inv_df = pd.DataFrame(invoices)
            display_cols = [c for c in ["id", "invoice_number", "vendor_id", "vendor_name",
                                        "status", "extraction_confidence", "created_at"]
                           if c in inv_df.columns]
            st.dataframe(inv_df[display_cols], use_container_width=True)

            # Drill into a specific invoice
            st.markdown("---")
            st.subheader("Invoice Detail View")
            invoice_ids = [inv["id"] for inv in invoices]
            selected_inv_id = st.selectbox(
                "Select Invoice ID", invoice_ids, key="tracker_inv_select",
            )

            if selected_inv_id:
                inv = repo.get_invoice_by_id(selected_inv_id)
                if inv:
                    col1, col2, col3, col4 = st.columns(4)
                    col1.metric("Invoice #", inv.get("invoice_number", "N/A"))
                    col2.metric("Vendor", inv.get("vendor_name", "N/A"))
                    col3.metric("Confidence", f"{(inv.get('extraction_confidence') or 0):.0%}")
                    col4.metric("Status", inv.get("status", "N/A"))

                    # Invoice lines
                    lines = repo.get_invoice_lines(selected_inv_id)
                    if lines:
                        st.markdown("**Extracted Invoice Lines:**")
                        st.dataframe(pd.DataFrame(lines), use_container_width=True)

                    # Linked reconciliations
                    recons = repo.get_reconciliations_for_invoice(selected_inv_id)
                    if recons:
                        st.markdown("**Reconciliation Runs:**")
                        st.dataframe(pd.DataFrame(recons), use_container_width=True)

                    # Linked exceptions
                    for recon in recons:
                        exceptions = repo.get_exceptions_for_reconciliation(recon["id"])
                        if exceptions:
                            st.markdown(f"**Exceptions for Reconciliation #{recon['id']}:**")
                            exc_df = pd.DataFrame(exceptions)
                            st.dataframe(exc_df, use_container_width=True)

    # ---- Tab 2: Reconciliation Details ----
    with tracker_tab2:
        st.subheader("Reconciliation History")
        recons = repo.get_all_reconciliations()

        if not recons:
            st.info("No reconciliations yet. Run the pipeline to generate reconciliation data.")
        else:
            recon_df = pd.DataFrame(recons)
            display_cols = [c for c in ["id", "invoice_id", "po_number", "overall_status",
                                        "reconciliation_confidence", "latency_ms",
                                        "started_at", "completed_at"]
                           if c in recon_df.columns]
            st.dataframe(recon_df[display_cols], use_container_width=True)

            # Status summary
            if "overall_status" in recon_df.columns:
                st.markdown("---")
                st.subheader("Status Breakdown")
                status_counts = recon_df["overall_status"].value_counts()
                col1, col2 = st.columns(2)
                with col1:
                    st.bar_chart(status_counts)
                with col2:
                    for status, count in status_counts.items():
                        emoji = {"MATCHED": "✅", "PARTIAL_MATCH": "⚠️", "MISMATCH": "❌"}.get(
                            status, "ℹ️")
                        st.write(f"{emoji} **{status}**: {count}")

            # Drill into reconciliation lines
            st.markdown("---")
            st.subheader("Reconciliation Line Details")
            recon_ids = [r["id"] for r in recons]
            selected_recon_id = st.selectbox(
                "Select Reconciliation ID", recon_ids, key="tracker_recon_select",
            )

            if selected_recon_id:
                recon = repo.get_reconciliation_by_id(selected_recon_id)
                if recon:
                    col1, col2, col3 = st.columns(3)
                    col1.metric("PO Number", recon.get("po_number", "N/A"))
                    col2.metric("Status", recon.get("overall_status", "N/A"))
                    col3.metric("Confidence", f"{(recon.get('reconciliation_confidence') or 0):.0%}")

                recon_lines = repo.get_reconciliation_lines(selected_recon_id)
                if recon_lines:
                    st.markdown("**Line-by-Line Match Results:**")
                    st.dataframe(pd.DataFrame(recon_lines), use_container_width=True)
                else:
                    st.info("No reconciliation lines for this run.")

                exceptions = repo.get_exceptions_for_reconciliation(selected_recon_id)
                if exceptions:
                    st.markdown("**Exceptions:**")
                    exc_df = pd.DataFrame(exceptions)
                    st.dataframe(exc_df, use_container_width=True)

    # ---- Tab 3: Pipeline Logs ----
    with tracker_tab3:
        render_log_viewer()


# ============================================================
# PAGE 4: Exceptions Dashboard
# ============================================================
elif page == "Exceptions Dashboard":
    st.title("⚠️ Exceptions Dashboard")
    st.markdown("Review and resolve reconciliation exceptions requiring human attention.")

    exc_tab1, exc_tab2 = st.tabs(["🔴 Unresolved", "📁 All Exceptions"])

    with exc_tab1:
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
                        datetime.now(timezone.utc).isoformat(),
                    )
                    st.success(f"Exception #{exc_id} resolved by {resolved_by}.")
                    st.rerun()
                else:
                    st.error("Please enter your name/ID before resolving.")

    with exc_tab2:
        all_exceptions = repo.get_all_exceptions()
        if not all_exceptions:
            st.info("No exceptions recorded yet.")
        else:
            all_exc_df = pd.DataFrame(all_exceptions)

            # Summary by severity
            col1, col2, col3 = st.columns(3)
            col1.metric("Total Exceptions", len(all_exc_df))
            resolved_count = int(all_exc_df["resolved"].sum()) if "resolved" in all_exc_df.columns else 0
            col2.metric("Resolved", resolved_count)
            col3.metric("Unresolved", len(all_exc_df) - resolved_count)

            # Severity breakdown
            if "severity" in all_exc_df.columns:
                st.markdown("**Severity Breakdown:**")
                sev_counts = all_exc_df["severity"].value_counts()
                st.bar_chart(sev_counts)

            st.dataframe(all_exc_df, use_container_width=True)

            csv = all_exc_df.to_csv(index=False)
            st.download_button(
                label="Export exceptions as CSV",
                data=csv,
                file_name="all_exceptions.csv",
                mime="text/csv",
            )


# ============================================================
# PAGE 5: RAG Management
# ============================================================
elif page == "RAG Management":
    st.title("🧠 RAG Management")
    st.markdown("View business rules, test the RAG query engine, and reload the index.")

    rag_tab1, rag_tab2, rag_tab3 = st.tabs([
        "📄 Rules Files",
        "🔍 Test RAG Queries",
        "⚙️ Manage Index",
    ])

    # ---- Tab 1: View Rules Files ----
    with rag_tab1:
        st.subheader("Business Rules Documents")
        rules_path = Path(RULES_DIR)
        rule_files = sorted(rules_path.glob("*.md")) + sorted(rules_path.glob("*.txt"))

        if not rule_files:
            st.warning(f"No rule files found in `{RULES_DIR}`. Add `.md` or `.txt` files.")
        else:
            st.info(f"Found **{len(rule_files)}** rule file(s) in `{RULES_DIR}`")

            for rule_file in rule_files:
                with st.expander(f"📄 {rule_file.name}", expanded=False):
                    content = rule_file.read_text(encoding="utf-8")
                    st.markdown(content)

    # ---- Tab 2: Test RAG Queries ----
    with rag_tab2:
        st.subheader("Test RAG Query Engine")
        st.markdown(
            "Enter a reconciliation question to test the RAG system. "
            "The system will retrieve relevant rules and generate an answer."
        )

        # Preset questions
        preset_questions = [
            "(Custom question)",
            "What should happen when a product code is not found in any open PO?",
            "What is the quantity tolerance for standard products?",
            "When should an invoice be auto-approved?",
            "What happens if extraction confidence is below 0.8?",
            "What is the price tolerance when quantity matches exactly?",
        ]

        selected_preset = st.selectbox("Preset questions", preset_questions, key="rag_preset")
        custom_question = st.text_area(
            "Question",
            value="" if selected_preset == "(Custom question)" else selected_preset,
            key="rag_question",
        )

        if st.button("Ask RAG", type="primary"):
            if custom_question.strip():
                with st.spinner("Querying RAG system..."):
                    try:
                        answer = ask_rules(custom_question.strip())
                        st.success("RAG Response:")
                        st.markdown(answer)
                    except FileNotFoundError as e:
                        st.error(f"RAG initialization failed: {e}")
                    except Exception as e:
                        st.error(f"RAG query failed: {e}")
            else:
                st.warning("Please enter a question.")

        # Query history in session state
        if "rag_history" not in st.session_state:
            st.session_state["rag_history"] = []

        if st.button("Ask & Save to History"):
            if custom_question.strip():
                with st.spinner("Querying RAG system..."):
                    try:
                        answer = ask_rules(custom_question.strip())
                        st.session_state["rag_history"].append({
                            "question": custom_question.strip(),
                            "answer": answer,
                            "timestamp": datetime.now(timezone.utc).isoformat(),
                        })
                        st.success("RAG Response:")
                        st.markdown(answer)
                    except Exception as e:
                        st.error(f"RAG query failed: {e}")

        if st.session_state.get("rag_history"):
            st.markdown("---")
            st.subheader("Query History")
            for i, entry in enumerate(reversed(st.session_state["rag_history"])):
                with st.expander(f"Q{len(st.session_state['rag_history']) - i}: {entry['question'][:80]}..."):
                    st.markdown(f"**Question:** {entry['question']}")
                    st.markdown(f"**Answer:** {entry['answer']}")
                    st.caption(f"Queried at: {entry['timestamp']}")

    # ---- Tab 3: Manage Index ----
    with rag_tab3:
        st.subheader("RAG Index Management")

        col1, col2 = st.columns(2)
        with col1:
            st.markdown("**Reload RAG Index**")
            st.markdown(
                "Rebuild the vector index from rule files. "
                "Use this after updating rule documents."
            )
            if st.button("🔄 Reload RAG Index", type="primary"):
                with st.spinner("Reloading RAG index..."):
                    try:
                        reload_rules()
                        st.success("RAG index reloaded successfully!")
                    except FileNotFoundError as e:
                        st.error(f"Failed: {e}")
                    except Exception as e:
                        st.error(f"Reload failed: {e}")

        with col2:
            st.markdown("**Index Status**")
            index_path = Path(RAG_PERSIST_DIR)
            if index_path.exists():
                index_files = list(index_path.rglob("*"))
                st.success(f"Index directory exists: `{RAG_PERSIST_DIR}`")
                st.write(f"Files in index: **{len(index_files)}**")
            else:
                st.warning("Index not yet created. Query the RAG or reload to initialize.")

        st.markdown("---")
        st.subheader("Rules Directory Info")
        rules_path = Path(RULES_DIR)
        if rules_path.exists():
            md_files = list(rules_path.glob("*.md"))
            txt_files = list(rules_path.glob("*.txt"))
            st.write(f"📁 Rules directory: `{RULES_DIR}`")
            st.write(f"- Markdown files: **{len(md_files)}**")
            st.write(f"- Text files: **{len(txt_files)}**")
            all_rule_files = md_files + txt_files
            if all_rule_files:
                file_info = []
                for f in all_rule_files:
                    content = f.read_text(encoding="utf-8")
                    file_info.append({
                        "File": f.name,
                        "Size (bytes)": f.stat().st_size,
                        "Lines": len(content.splitlines()),
                    })
                st.dataframe(pd.DataFrame(file_info), use_container_width=True)
        else:
            st.error(f"Rules directory not found: `{RULES_DIR}`")


# ============================================================
# PAGE 6: Observability Metrics
# ============================================================
elif page == "Observability Metrics":
    st.title("📈 Observability Metrics")
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
