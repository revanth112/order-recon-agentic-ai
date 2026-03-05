# agents/state.py - LangGraph state definition
from typing import TypedDict, Any, Optional, List, Dict


class ReconState(TypedDict, total=False):
    invoice_id: int
    invoice_json: Dict[str, Any]
    extracted_data: Dict[str, Any]
    reconciliation_id: int
    discrepancies: List[Dict[str, Any]]
    pipeline_status: str
    logs: List[str]
    error: Optional[str]
