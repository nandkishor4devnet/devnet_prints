"""Explicit synchronization for the Divine Foods CAPA print format."""

import json
from pathlib import Path


FORMAT_PATH = Path(__file__).parent / "df_quality_action_register" / "df_quality_action_register.json"
FORMAT_NAME = "DF - Quality Action Register"
FORMAT_DOCTYPE = "Quality Action"
FORMAT_MODULE = "Divine Foods"

FORMAT_FIELDS = (
    "name",
    "print_format_for",
    "doc_type",
    "report",
    "module",
    "standard",
    "custom_format",
    "disabled",
    "print_format_type",
    "pdf_generator",
    "html",
    "margin_top",
    "margin_bottom",
    "margin_left",
    "margin_right",
)

REQUIRED_FIELDS = {
    "Quality Action": {
        "date": "Date",
        "corrective_preventive": "Select",
        "status": "Select",
        "goal": "Link",
        "procedure": "Link",
        "review": "Link",
        "feedback": "Link",
        "resolutions": "Table",
    },
    "Quality Action Resolution": {
        "problem": "Long Text",
        "incident_date": "Date",
        "root_cause": "Long Text",
        "resolution": "Text Editor",
        "status": "Select",
        "responsible": "Link",
        "completion_by": "Date",
    },
}


def load_format_definition():
    """Load and validate the source JSON without accessing or changing site data."""
    with FORMAT_PATH.open(encoding="utf-8") as source:
        definition = json.load(source)

    expected = {
        "name": FORMAT_NAME,
        "print_format_for": "DocType",
        "doc_type": FORMAT_DOCTYPE,
        "report": None,
        "module": FORMAT_MODULE,
        "standard": "No",
        "custom_format": 1,
        "print_format_type": "Jinja",
    }
    for key, value in expected.items():
        if definition.get(key) != value:
            raise ValueError(f"Unexpected CAPA print-format metadata: {key}")

    if not definition.get("html"):
        raise ValueError("CAPA print-format HTML is empty")
    return definition


def _validate_live_schema():
    import frappe

    parent_meta = frappe.get_meta(FORMAT_DOCTYPE)
    child_field = parent_meta.get_field("resolutions")
    if not child_field or child_field.fieldtype != "Table" or child_field.options != "Quality Action Resolution":
        frappe.throw("Quality Action.resolutions must link to Quality Action Resolution.")

    for doctype, fields in REQUIRED_FIELDS.items():
        meta = frappe.get_meta(doctype)
        for fieldname, fieldtype in fields.items():
            field = meta.get_field(fieldname)
            if not field or field.fieldtype != fieldtype:
                frappe.throw(f"Required CAPA field {doctype}.{fieldname} ({fieldtype}) is missing or incompatible.")

    for fieldname, fieldtype, insert_after in (
        ("incident_date", "Date", "problem"),
        ("root_cause", "Long Text", "incident_date"),
    ):
        custom_field_name = f"Quality Action Resolution-{fieldname}"
        custom_field = frappe.db.get_value(
            "Custom Field",
            custom_field_name,
            ["dt", "fieldname", "fieldtype", "insert_after", "module"],
            as_dict=True,
        )
        if not custom_field or (
            custom_field.dt != "Quality Action Resolution"
            or custom_field.fieldname != fieldname
            or custom_field.fieldtype != fieldtype
            or custom_field.insert_after != insert_after
            or custom_field.module != FORMAT_MODULE
        ):
            frappe.throw(f"Existing custom field {custom_field_name} is missing or incompatible.")


def _validate_existing_format(print_format):
    import frappe

    expected = {
        "name": FORMAT_NAME,
        "print_format_for": "DocType",
        "doc_type": FORMAT_DOCTYPE,
        "report": None,
        "module": FORMAT_MODULE,
        "standard": "No",
        "custom_format": 1,
        "print_format_type": "Jinja",
    }
    for fieldname, expected_value in expected.items():
        if print_format.get(fieldname) != expected_value:
            frappe.throw(
                f"Refusing to overwrite conflicting Print Format {FORMAT_NAME}: "
                f"{fieldname} does not match the Divine Foods CAPA definition."
            )


def sync_capa_print_format():
    """Create or update only this app-owned format when explicitly invoked."""
    import frappe

    definition = load_format_definition()
    _validate_live_schema()

    if not frappe.db.exists("Module Def", FORMAT_MODULE):
        frappe.throw(f"Module Def {FORMAT_MODULE} must exist before installing the CAPA print format.")

    values = {field: definition[field] for field in FORMAT_FIELDS if field in definition}
    existing_name = frappe.db.exists("Print Format", FORMAT_NAME)
    if existing_name:
        print_format = frappe.get_doc("Print Format", existing_name)
        _validate_existing_format(print_format)
        changes = {
            key: value
            for key, value in values.items()
            if key != "name" and print_format.get(key) != value
        }
        if changes:
            print_format.update(changes)
            print_format.save()
    else:
        frappe.get_doc({"doctype": "Print Format", **values}).insert()

    return FORMAT_NAME
