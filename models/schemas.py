# models/schemas.py - Pydantic models for structured GPT output and validation
from typing import Optional, List
from pydantic import BaseModel, Field


class InvoiceLine(BaseModel):
    line_number: Optional[int] = Field(None, description="Line number on invoice")
    product_code: str = Field(..., description="Product or SKU code")
    description: Optional[str] = Field(None, description="Product description")
    quantity: float = Field(..., description="Quantity on invoice")
    unit_price: float = Field(..., description="Unit price on invoice")
    tax_rate: Optional[float] = Field(0.0, description="Tax rate as decimal e.g. 0.18")


class ExtractedInvoice(BaseModel):
    invoice_number: Optional[str] = Field(None, description="Invoice number")
    vendor_id: Optional[str] = Field(None, description="Vendor ID")
    vendor_name: Optional[str] = Field(None, description="Vendor name")
    invoice_date: Optional[str] = Field(None, description="Invoice date YYYY-MM-DD")
    po_number: Optional[str] = Field(None, description="Purchase order number if present")
    currency: Optional[str] = Field("USD", description="Currency code")
    line_items: List[InvoiceLine] = Field(default_factory=list, description="Invoice line items")


class ReconciliationResult(BaseModel):
    reconciliation_id: int
    invoice_id: int
    po_number: Optional[str]
    overall_status: str  # MATCHED, PARTIAL_MATCH, MISMATCH
    reconciliation_confidence: float
    discrepancy_count: int
    latency_ms: int


class ExceptionRecord(BaseModel):
    id: int
    reconciliation_id: int
    type: str
    severity: str
    description: str
    auto_action: str
    resolved: bool
    resolved_by: Optional[str]
    resolved_at: Optional[str]
