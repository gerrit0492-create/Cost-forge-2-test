"""
Change order / scope variation schema and helpers.
"""
from __future__ import annotations

SCHEMA_CHANGE_ORDERS = {
    "co_id":               "string",
    "title":               "string",
    "description":         "string",
    "requested_by":        "string",   # "Customer" / "Internal" / "Supplier"
    "category":            "string",   # see CO_CATEGORIES
    "cost_delta_eur":      "float64",  # + = cost increase
    "revenue_delta_eur":   "float64",  # + = revenue increase
    "status":              "string",   # see CO_STATUSES
    "submitted_date":      "string",
    "approved_date":       "string",
    "approved_by":         "string",
    "impact_on_delivery":  "string",
    "notes":               "string",
}

CO_CATEGORIES = [
    "Scope addition",
    "Scope reduction",
    "Design change",
    "Material substitution",
    "Schedule",
]

CO_STATUSES = ["Pending", "Approved", "Rejected", "On hold"]

CO_REQUESTORS = ["Customer", "Internal", "Supplier"]

CO_DELIVERY_IMPACTS = ["None", "+1 week", "+2 weeks", "+4 weeks", "TBD"]
