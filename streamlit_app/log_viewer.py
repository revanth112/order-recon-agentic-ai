# streamlit_app/log_viewer.py
# Plug-in tab for the Streamlit UI that renders pipeline logs from SQLite.
# Usage in app.py:
#   from streamlit_app.log_viewer import render_log_viewer
#   with tab_logs:
#       render_log_viewer()

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import streamlit as st
import pandas as pd
from core import logger as pipeline_logger
from core import repositories as repo


# Colour mapping for log levels
_LEVEL_COLOURS = {
  'INFO':    '#4CAF50',
  'WARNING': '#FF9800',
  'ERROR':   '#F44336',
}

_AGENT_ICONS = {
  'EXTRACTOR':        '🔍',
  'MATCHER':          '🔗',
  'EXCEPTION_HANDLER':'⚠️',
  'SYSTEM':           '⚙️',
}


def _level_badge(level: str) -> str:
  colour = _LEVEL_COLOURS.get(level, '#9E9E9E')
  return f'<span style="background:{colour};color:#fff;padding:2px 8px;border-radius:4px;font-size:12px">{level}</span>'


def render_log_viewer():
  """Full Streamlit section: pipeline log browser with filters and validation."""
  st.header('Pipeline Logs')
  st.caption('Browse, filter, and validate every log entry emitted by the agents.')

  # ---- Sidebar / filter controls ----
  col1, col2, col3 = st.columns(3)
  with col1:
    level_filter = st.selectbox(
      'Level',
      options=['All', 'INFO', 'WARNING', 'ERROR'],
      index=0,
      key='log_level_filter'
    )
  with col2:
    agent_filter = st.selectbox(
      'Agent',
      options=['All', 'EXTRACTOR', 'MATCHER', 'EXCEPTION_HANDLER', 'SYSTEM'],
      index=0,
      key='log_agent_filter'
    )
  with col3:
    limit = st.number_input('Max rows', min_value=10, max_value=2000, value=200,
                            step=50, key='log_limit')

  # ---- Fetch logs ----
  logs = pipeline_logger.get_all_logs(
    level=None if level_filter == 'All' else level_filter,
    agent=None if agent_filter == 'All' else agent_filter,
    limit=int(limit),
  )

  if not logs:
    st.info('No log entries found. Run a pipeline first.')
    return

  df = pd.DataFrame(logs)

  # ---- Summary metrics ----
  st.markdown('---')
  m1, m2, m3, m4 = st.columns(4)
  m1.metric('Total Entries', len(df))
  m2.metric('INFO',    int((df['level'] == 'INFO').sum()),    delta=None)
  m3.metric('WARNING', int((df['level'] == 'WARNING').sum()), delta=None,
            delta_color='inverse')
  m4.metric('ERROR',   int((df['level'] == 'ERROR').sum()),   delta=None,
            delta_color='inverse')

  # ---- Run-level validation panel ----
  st.markdown('---')
  st.subheader('Run Validation')
  unique_runs = df['run_id'].unique().tolist()
  selected_run = st.selectbox(
    'Select a pipeline run to validate',
    options=unique_runs,
    format_func=lambda r: r[:16] + '...',
    key='log_run_select'
  )

  if selected_run:
    summary = pipeline_logger.get_run_summary(selected_run)
    sc1, sc2, sc3 = st.columns(3)
    sc1.metric('Log entries (this run)', summary['total'])
    sc2.metric('Agents executed', len(summary['agents_executed']))
    sc3.metric('Has errors', '🔴 Yes' if summary['has_errors'] else '🟢 No')

    # Validation checklist
    st.markdown('#### Validation Checklist')
    agents_executed = summary['agents_executed']
    checks = [
      ('Extractor ran',          'EXTRACTOR' in agents_executed),
      ('Matcher ran',            'MATCHER' in agents_executed),
      ('Exception handler ran',  'EXCEPTION_HANDLER' in agents_executed),
      ('No ERROR logs',          not summary['has_errors']),
      ('Low confidence warning', summary['has_warnings']),
    ]
    for label, passed in checks:
      icon = '✅' if passed else '❌'
      note = '(expected)' if label != 'Low confidence warning' else '(check if applicable)'
      st.write(f"{icon} {label} {note}")

    # Per-run log table
    st.markdown('#### Run Log Timeline')
    run_df = pd.DataFrame(pipeline_logger.get_logs_for_run(selected_run))
    _render_log_table(run_df)

  # ---- Full log table ----
  st.markdown('---')
  st.subheader(f'All Logs (latest {len(df)} entries)')
  _render_log_table(df)

  # ---- Export ----
  csv = df.to_csv(index=False)
  st.download_button(
    label='Export logs as CSV',
    data=csv,
    file_name='pipeline_logs.csv',
    mime='text/csv',
  )


def _render_log_table(df: pd.DataFrame):
  """Render a styled log table."""
  if df.empty:
    st.info('No logs.')
    return

  # Colour-code level column with HTML
  display_cols = ['created_at', 'invoice_id', 'agent', 'level', 'message', 'run_id']
  existing = [c for c in display_cols if c in df.columns]
  df_show = df[existing].copy()

  # Truncate run_id for readability
  if 'run_id' in df_show.columns:
    df_show['run_id'] = df_show['run_id'].str[:12] + '...'

  st.dataframe(
    df_show,
    use_container_width=True,
    column_config={
      'level': st.column_config.TextColumn('Level', width='small'),
      'agent': st.column_config.TextColumn('Agent', width='medium'),
      'message': st.column_config.TextColumn('Message', width='large'),
      'created_at': st.column_config.TextColumn('Timestamp', width='medium'),
      'run_id': st.column_config.TextColumn('Run ID', width='small'),
      'invoice_id': st.column_config.NumberColumn('Invoice', width='small'),
    }
  )
