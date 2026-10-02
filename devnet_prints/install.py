"""Install print formats for existing ERPNext DocTypes only."""
import json
from pathlib import Path
import frappe


def catalog():
    specs = json.loads((Path(__file__).parent / 'catalog.json').read_text())
    doctypes = [spec['doctype'] for spec in specs]
    if len(doctypes) != len(set(doctypes)):
        raise ValueError('Devnet Prints supports exactly one print format per DocType.')
    return specs


def sync_formats():
    for spec in catalog():
        frappe.get_meta(spec['doctype'])
        # Layout and data enrichment are shared; values are read at print time.
        template = 'templates/audit_record.html'
        html = '\n'.join([
            '{% set format_title = ' + json.dumps(spec['name'][5:]) + ' %}',
            '{% set variant = ' + json.dumps(spec['variant'] or '') + ' %}',
            '{% set format_name = ' + json.dumps(spec['name']) + ' %}',
            '{% include ' + json.dumps(template) + ' %}',
        ])
        values = dict(doc_type=spec['doctype'], module='Devnet Prints', standard='No', custom_format=1,
                      print_format_type='Jinja', pdf_generator='chrome', html=html, disabled=0, print_designer=0,
                      margin_top=12, margin_bottom=12, margin_left=12, margin_right=12)
        if frappe.db.exists('Print Format', spec['name']):
            doc = frappe.get_doc('Print Format', spec['name'])
            if doc.module != 'Devnet Prints':
                frappe.throw('Refusing to overwrite a print format outside Devnet Prints: ' + doc.name)
            doc.update(values)
            doc.save()
        else:
            frappe.get_doc(dict(doctype='Print Format', name=spec['name'], **values)).insert()


def install():
    """Safe, repeatable local setup, also used by install/migrate hooks."""
    if not frappe.db.exists('Module Def', 'Devnet Prints'):
        frappe.get_doc(dict(doctype='Module Def', module_name='Devnet Prints', app_name='devnet_prints')).insert()
    sync_formats()
    for name, dt in [('GMP Form 1F - Approved Supplier Register', 'Supplier'), ('GMP Form 11 - PO Form 2 - NCR Ledger', 'Stock Entry')]:
        if not frappe.db.exists('Report', name):
            frappe.get_doc(dict(doctype='Report', report_name=name, ref_doctype=dt,
                module='Devnet Prints', is_standard='Yes', report_type='Script Report',
                roles=[dict(role='System Manager')])).insert()
    # Archive obsolete app-owned layouts before removing them. Other modules
    # and business records are deliberately outside this reconciliation.
    wanted = {spec['name'] for spec in catalog()}
    obsolete = [name for name in frappe.get_all('Print Format', filters={'module': 'Devnet Prints'}, pluck='name') if name not in wanted]
    if obsolete:
        from frappe.utils import now_datetime
        archive = Path(frappe.get_site_path('private', 'files', 'devnet-print-archives'))
        archive.mkdir(parents=True, exist_ok=True)
        target = archive / (now_datetime().strftime('%Y%m%d-%H%M%S-%f') + '.json')
        target.write_text(frappe.as_json([frappe.get_doc('Print Format', name).as_dict() for name in obsolete]))
        for name in obsolete:
            frappe.delete_doc('Print Format', name)
    return {'formats': len(catalog()), 'doctypes': 0}
