import ast
import json
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from jinja2 import Environment

from divinefoods.print_format.sync import load_format_definition


APP_ROOT = Path(__file__).resolve().parents[1]
FORMAT_PATH = APP_ROOT / "print_format" / "df_quality_action_register" / "df_quality_action_register.json"
FIXTURE_PATH = APP_ROOT / "fixtures" / "custom_field.json"
SYNC_PATH = APP_ROOT / "print_format" / "sync.py"


class TestCAPAPrintFormatSource(unittest.TestCase):
    class FakePrintFormat(dict):
        def __getattr__(self, name):
            try:
                return self[name]
            except KeyError as error:
                raise AttributeError(name) from error

        def __setattr__(self, name, value):
            self[name] = value

        def update(self, values):
            self.last_update = dict(values)
            super().update(values)

        def save(self):
            self.save_calls = self.get("save_calls", 0) + 1

        def insert(self):
            self.insert_calls = self.get("insert_calls", 0) + 1

    def setUp(self):
        self.definition = load_format_definition()

    def _mock_frappe(self, existing=None):
        def make_meta(doctype):
            fields = (
                {
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
                }[doctype]
            )

            def get_field(fieldname):
                fieldtype = fields.get(fieldname)
                options = "Quality Action Resolution" if fieldname == "resolutions" else None
                return SimpleNamespace(fieldtype=fieldtype, options=options) if fieldtype else None

            return SimpleNamespace(get_field=get_field)

        custom_fields = {
            "Quality Action Resolution-incident_date": SimpleNamespace(
                dt="Quality Action Resolution",
                fieldname="incident_date",
                fieldtype="Date",
                insert_after="problem",
                module="Divine Foods",
            ),
            "Quality Action Resolution-root_cause": SimpleNamespace(
                dt="Quality Action Resolution",
                fieldname="root_cause",
                fieldtype="Long Text",
                insert_after="incident_date",
                module="Divine Foods",
            ),
        }
        db = MagicMock()
        db.exists.side_effect = lambda doctype, name: (
            name == "Divine Foods" if doctype == "Module Def" else
            name if doctype == "Print Format" and existing is not None else
            None
        )
        db.get_value.side_effect = lambda doctype, name, fields, as_dict=False: (
            custom_fields.get(name) if doctype == "Custom Field" else None
        )
        fake_frappe = SimpleNamespace(
            db=db,
            get_meta=MagicMock(side_effect=make_meta),
            get_doc=MagicMock(),
            throw=lambda message: (_ for _ in ()).throw(RuntimeError(message)),
        )

        if existing is not None:
            fake_frappe.get_doc.return_value = existing
        else:
            inserted = self.FakePrintFormat()
            fake_frappe.get_doc.return_value = inserted
            fake_frappe.inserted_doc = inserted

        return fake_frappe

    def _matching_existing(self):
        from divinefoods.print_format.sync import FORMAT_FIELDS

        values = {field: self.definition[field] for field in FORMAT_FIELDS if field in self.definition}
        values.update(name="DF - Quality Action Register", unrelated_custom_field="preserve me")
        return self.FakePrintFormat(values)

    def test_format_identity_and_jinja(self):
        definition = self.definition
        self.assertEqual(definition["name"], "DF - Quality Action Register")
        self.assertEqual(definition["print_format_for"], "DocType")
        self.assertEqual(definition["doc_type"], "Quality Action")
        self.assertIsNone(definition["report"])
        self.assertEqual(definition["module"], "Divine Foods")
        self.assertEqual(definition["standard"], "No")
        self.assertEqual(definition["custom_format"], 1)
        self.assertEqual(definition["print_format_type"], "Jinja")
        Environment().parse(definition["html"])

    def test_explicit_sync_entry_point_is_registered_in_source(self):
        source = ast.parse(SYNC_PATH.read_text(encoding="utf-8"))
        functions = {
            node.name
            for node in ast.walk(source)
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        }
        self.assertIn("sync_capa_print_format", functions)
        self.assertIn("_validate_live_schema", functions)

    def test_existing_resolution_custom_fields_are_preserved(self):
        fields = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
        by_name = {field["name"]: field for field in fields}
        expected = {
            "Quality Action Resolution-incident_date": {
                "fieldname": "incident_date",
                "fieldtype": "Date",
                "insert_after": "problem",
            },
            "Quality Action Resolution-root_cause": {
                "fieldname": "root_cause",
                "fieldtype": "Long Text",
                "insert_after": "incident_date",
            },
        }

        for name, values in expected.items():
            self.assertIn(name, by_name)
            field = by_name[name]
            self.assertEqual(field["dt"], "Quality Action Resolution")
            self.assertEqual(field["module"], "Divine Foods")
            for key, value in values.items():
                self.assertEqual(field[key], value)

    def test_required_real_field_bindings_and_safe_optional_sections(self):
        definition = json.loads(FORMAT_PATH.read_text(encoding="utf-8"))
        html = definition["html"]
        required_bindings = (
            "doc.name",
            "doc.date",
            "doc.corrective_preventive",
            "doc.status",
            "doc.resolutions",
            "row.incident_date",
            "row.problem",
            "row.root_cause",
            "row.resolution",
            "row.status",
            "row.responsible",
            "row.completion_by",
        )
        for binding in required_bindings:
            self.assertIn(binding, html)

        for fieldname in ("goal", "procedure", "review", "feedback"):
            self.assertIn(f"{{% if doc.{fieldname} %}}", html)
        self.assertIn("{% if not doc.resolutions %}", html)
        self.assertIn("Not assigned", html)
        self.assertIn("<table class=\"df-table\">", html)
        self.assertIn("HACCP Team Leader", html)
        self.assertIn("Verified / Closed By", html)
        self.assertIn("df-sign-line", html)
        self.assertIn("df-sign-date-line", html)

    def test_sync_inserts_when_format_is_absent(self):
        from divinefoods.print_format.sync import sync_capa_print_format

        frappe = self._mock_frappe()
        with patch.dict(sys.modules, {"frappe": frappe}):
            self.assertEqual(sync_capa_print_format(), "DF - Quality Action Register")

        inserted = frappe.inserted_doc
        self.assertEqual(inserted.insert_calls, 1)
        inserted_values = frappe.get_doc.call_args.args[0]
        self.assertEqual(inserted_values["name"], "DF - Quality Action Register")
        self.assertIsNone(inserted_values["report"])
        frappe.db.exists.assert_any_call("Print Format", "DF - Quality Action Register")

    def test_sync_is_noop_when_existing_format_matches(self):
        from divinefoods.print_format.sync import sync_capa_print_format

        existing = self._matching_existing()
        frappe = self._mock_frappe(existing)
        with patch.dict(sys.modules, {"frappe": frappe}):
            self.assertEqual(sync_capa_print_format(), "DF - Quality Action Register")

        self.assertEqual(existing.get("save_calls", 0), 0)
        self.assertEqual(existing.unrelated_custom_field, "preserve me")

    def test_sync_updates_managed_fields_and_preserves_unmanaged_fields(self):
        from divinefoods.print_format.sync import FORMAT_FIELDS, sync_capa_print_format

        existing = self._matching_existing()
        existing.html = "old template"
        frappe = self._mock_frappe(existing)
        with patch.dict(sys.modules, {"frappe": frappe}):
            self.assertEqual(sync_capa_print_format(), "DF - Quality Action Register")

        self.assertEqual(existing.get("save_calls", 0), 1)
        self.assertEqual(existing.html, self.definition["html"])
        self.assertEqual(existing.unrelated_custom_field, "preserve me")
        self.assertFalse(
            any(
                key not in FORMAT_FIELDS
                for key in existing.last_update
            )
        )

    def test_sync_rejects_conflicting_identity_without_writes(self):
        from divinefoods.print_format.sync import sync_capa_print_format

        for fieldname, value in (
            ("module", "Other App"),
            ("doc_type", "Supplier"),
            ("print_format_for", "Report"),
            ("standard", "Yes"),
            ("custom_format", 0),
            ("print_format_type", "HTML"),
            ("report", "Unrelated Report"),
        ):
            with self.subTest(fieldname=fieldname):
                existing = self._matching_existing()
                setattr(existing, fieldname, value)
                frappe = self._mock_frappe(existing)
                with patch.dict(sys.modules, {"frappe": frappe}):
                    with self.assertRaisesRegex(RuntimeError, "Refusing to overwrite conflicting Print Format"):
                        sync_capa_print_format()

                self.assertEqual(existing.get("save_calls", 0), 0)
                frappe.db.set_value.assert_not_called()
                frappe.db.delete.assert_not_called()
                frappe.db.insert.assert_not_called()

    def test_sync_performs_no_write_when_schema_validation_fails(self):
        from divinefoods.print_format.sync import sync_capa_print_format

        frappe = self._mock_frappe()
        frappe.get_meta.side_effect = RuntimeError("schema validation failed")
        with patch.dict(sys.modules, {"frappe": frappe}):
            with self.assertRaisesRegex(RuntimeError, "schema validation failed"):
                sync_capa_print_format()

        frappe.get_doc.assert_not_called()
        frappe.db.set_value.assert_not_called()
        frappe.db.delete.assert_not_called()
        frappe.db.insert.assert_not_called()


if __name__ == "__main__":
    unittest.main()
