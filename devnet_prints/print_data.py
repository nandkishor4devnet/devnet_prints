"""Permission-aware, uncapped data for Devnet's record printouts."""
from pathlib import PurePosixPath
from urllib.parse import urlsplit
import frappe
from frappe.utils import strip_html

LAYOUTS = {
    'Supplier': [('Supplier information', ['supplier_name','supplier_type','supplier_group','country','tax_id','website']), ('Contact and address', ['supplier_primary_contact','supplier_primary_address','mobile_no','email_id']), ('Certification', ['custom_certification_type','custom_certification_number','custom_issuing_authority','custom_certification_expiry_date'])],
    'Item': [('Item specification', ['item_code','item_name','item_group','stock_uom','brand']), ('Batch and shelf life', ['has_batch_no','shelf_life_in_days','end_of_life','default_bom'])],
    'Batch': [('Batch identification', ['batch_id','item','item_name','custom_vendor_lot_number','supplier','parent_batch']), ('Dates and source', ['manufacturing_date','expiry_date','reference_doctype','reference_name','stock_uom','disabled'])],
    'Warehouse': [('Warehouse information', ['warehouse_name','company','parent_warehouse','warehouse_type','is_group','disabled']), ('Location and contact', ['address_line_1','address_line_2','city','state','country','pin','phone_no','mobile_no','email_id'])],
    'Work Order': [('Production instruction', ['production_item','item_name','bom_no','qty','stock_uom','status','company','sales_order']), ('Schedule', ['planned_start_date','planned_end_date','expected_delivery_date','actual_start_date','actual_end_date']), ('Material flow', ['source_warehouse','wip_warehouse','fg_warehouse','scrap_warehouse','produced_qty','material_transferred_for_manufacturing','process_loss_qty'])],
    'Sales Order': [('Customer order', ['customer','customer_name','company','transaction_date','delivery_date','po_no','po_date','status','currency']), ('Delivery and contact', ['customer_address','shipping_address_name','contact_person','contact_display','contact_email','contact_mobile','customer_group','territory']), ('Order totals', ['total_qty','total','net_total','total_taxes_and_charges','grand_total','rounded_total','advance_paid'])],
    'Stock Entry': [('Stock movement', ['stock_entry_type','purpose','company','posting_date','posting_time','work_order','bom_no','fg_completed_qty']), ('Warehouse flow', ['from_warehouse','to_warehouse','total_incoming_value','total_outgoing_value','total_additional_costs'])],
    'Quality Inspection': [('Inspection', ['report_date','inspection_type','quality_inspection_template','status','company','sample_size']), ('Product and reference', ['item_code','item_name','batch_no','item_serial_no','bom_no','reference_type','reference_name']), ('Responsibility', ['inspected_by','verified_by'])],
    'Quality Action': [('Action record', ['corrective_preventive','date','status','review','feedback','goal','procedure'])],
    'Asset Maintenance Log': [('Equipment', ['asset_name','item_code','item_name','asset_maintenance','task_name','maintenance_type']), ('Calibration and maintenance', ['maintenance_status','periodicity','assign_to_name','due_date','completion_date','has_certificate','certificate_attachement'])],
    'Quality Inspection Template': [('Inspection standard', ['quality_inspection_template_name','custom_quality_inspection'])],
}
# Never expose controls, framework internals, passwords, or fields hidden for printing.
SKIP_TYPES = {'Section Break','Column Break','Tab Break','HTML','Button','Password','Fold','Heading'}
BUSINESS_TABLES = {'Work Order': {'required_items'}, 'Sales Order': {'packed_items', 'payment_schedule'}}
SKIP_FIELDS = {'naming_series','amended_from','letter_head','image','website_image','child_row_reference','__islocal'}
TABLE_COLUMNS = {
    'Work Order Item': ['item_code','item_name','required_qty','stock_uom','source_warehouse','transferred_qty','consumed_qty','available_qty_at_source_warehouse'],
    'Sales Order Item': ['item_code','item_name','qty','uom','rate','amount','delivery_date','warehouse'],
    'Stock Entry Detail': ['item_code','item_name','qty','uom','s_warehouse','t_warehouse','batch_no','serial_and_batch_bundle','basic_rate','amount'],
    'Quality Inspection Reading': ['specification','parameter_group','reading_value','reading_1','reading_2','reading_3','reading_4','reading_5','reading_6','reading_7','reading_8','reading_9','reading_10','min_value','max_value','value','status'],
    'Certifications Table': ['certification_type','certification_number','certification_start_date','certification_expiry_date','issuing_authority'],
}


def populated(value):
    return value is not None and value != '' and value != []


def eligible(field, include_hidden=False):
    return field.fieldtype not in SKIP_TYPES and field.fieldname not in SKIP_FIELDS and (include_hidden or not field.get('print_hide'))


def formatted(record, field):
    raw = record.get(field.fieldname)
    if not populated(raw):
        return None
    if field.fieldtype == 'Check':
        return 'Yes' if raw else 'No'
    if field.fieldtype in ('Attach','Attach Image'):
        return PurePosixPath(urlsplit(str(raw)).path).name
    return strip_html(str(record.get_formatted(field.fieldname)))


def details(record, names):
    result=[]
    for name in names:
        field=record.meta.get_field(name)
        if field and eligible(field) and populated(record.get(name)):
            result.append(dict(label=field.label or name, value=formatted(record,field)))
    return result


def table(record, field, selected_rows=None):
    rows=(record.get(field.fieldname) or []) if selected_rows is None else selected_rows
    if not rows:
        return None
    meta=frappe.get_meta(field.options)
    preferred=TABLE_COLUMNS.get(field.options, [])
    names=preferred + [f.fieldname for f in meta.fields if f.fieldname not in preferred]
    cols=[]
    for name in names:
        col=meta.get_field(name)
        if col and eligible(col,include_hidden=name in preferred) and col.fieldtype not in ('Table','Table MultiSelect') and any(populated(r.get(name)) for r in rows):
            # Numeric QC acceptance limits only apply to numeric parameters.
            if field.options == 'Quality Inspection Reading' and name in ('min_value','max_value') and not any(r.numeric for r in rows):
                continue
            if field.options == 'Quality Inspection Reading' and name in ('numeric','manual_inspection','formula_based_criteria'):
                continue
            cols.append(col)
    # Split wide tables into readable column bands, repeating the row identity.
    # This prints every stored column and row rather than squeezing or truncating.
    bands=[]
    key=next((c for c in cols if c.fieldname in ('specification','item_code','employee','certification_type')),None)
    remaining=[c for c in cols if c is not key]
    width=5 if key else 6
    for start in range(0,max(len(remaining),1),width):
        columns=([key] if key else []) + remaining[start:start+width]
        bands.append(dict(columns=[dict(label=c.label or c.fieldname) for c in columns],
            rows=[dict(number=i,values=[formatted(r,c) for c in columns]) for i,r in enumerate(rows,1)]))
    title = 'Required materials' if field.fieldname == 'required_items' else (field.label or field.fieldname.replace('_', ' ').title())
    return dict(title=title,count=len(rows),bands=bands)


def record_sections(record, reading_rows=None):
    sections=[];used=set()
    for title,names in LAYOUTS.get(record.doctype,[]):
        used.update(names);values=details(record,names)
        if values:sections.append(dict(title=title,fields=values))
    additional=[];notes=[];tables=[]
    for field in record.meta.fields:
        if not eligible(field,include_hidden=field.fieldname in BUSINESS_TABLES.get(record.doctype,set())) or not populated(record.get(field.fieldname)):
            continue
        if field.fieldtype in ('Table','Table MultiSelect'):
            data=table(record,field,reading_rows if field.fieldname == 'readings' else None)
            if data:tables.append(data)
        elif field.fieldtype in ('Small Text','Text','Long Text','Text Editor','Code','Markdown Editor'):
            notes.append(dict(title=field.label or field.fieldname,value=formatted(record,field)))
        elif field.fieldname not in used:
            additional.extend(details(record,[field.fieldname]))
    return dict(sections=sections,tables=tables,notes=notes,additional=additional)


def readable(doctype,name):
    if not name or not frappe.db.exists(doctype,name):
        return None
    record=frappe.get_doc(doctype,name)
    return record if record.has_permission('read') else None


def get_print_context(doc, format_name=None):
    """Only enrich the selected record, using its explicit links and permitted rows."""
    doc.check_permission('print')
    from devnet_prints.install import catalog
    spec = next((s for s in catalog() if s['name'] == format_name), None)
    if spec and spec['doctype'] != doc.doctype:
        frappe.throw('This print format belongs to ' + spec['doctype'])
    readings = None
    notice = None
    if spec and doc.doctype == 'Quality Action' and spec['variant']:
        if doc.corrective_preventive != spec['variant']:
            frappe.throw('Select a ' + spec['variant'] + ' action record for this register.')
    if spec and doc.doctype == 'Quality Inspection':
        readings = list(doc.get('readings') or [])
        if spec['variant']:
            area = doc.get('custom_area') or doc.get('area')
            if not area:
                for row in readings:
                    if 'area' in (row.specification or '').lower():
                        area = row.get('reading_value') or row.get('reading_1') or row.get('value')
                        break
            if str(area or '').strip().casefold() != spec['variant'].casefold():
                readings = []
                notice = 'No saved inspection readings for the selected area: ' + spec['variant'] + '.'
        keywords = spec.get('reading_keywords', [])
        if keywords:
            readings = [r for r in readings if any(k.casefold() in (r.specification or '').casefold() for k in keywords)]
        if not readings and not notice:
            notice = 'No matching observations are saved on this record.'
    result=record_sections(doc,readings)
    result['notice'] = notice
    result.update(related=[],stock=None,attachments=[],company=None)
    company=readable('Company',doc.get('company'))
    result['company']=company.name if company else None
    link_specs={
        'Supplier':[('Contact','supplier_primary_contact'),('Address','supplier_primary_address')],
        'Batch':[('Item','item'),('Supplier','supplier'),('Batch','parent_batch')],
        'Work Order':[('Item','production_item'),('BOM','bom_no')],
        'Sales Order':[('Customer','customer'),('Address','customer_address'),('Address','shipping_address_name'),('Contact','contact_person')],
        'Quality Inspection':[('Item','item_code'),('Batch','batch_no'),('Quality Inspection Template','quality_inspection_template')],
        'Asset Maintenance Log':[('Asset Maintenance','asset_maintenance')],
    }
    seen=set()
    for dt,field in link_specs.get(doc.doctype,[]):
        name=doc.get(field)
        if not name or (dt,name) in seen:continue
        seen.add((dt,name));linked=readable(dt,name)
        if linked:
            # Linked customer/contact records contain personal fields; only print the relevant contact profile.
            names={'Contact':['full_name','first_name','last_name','email_id','mobile_no','phone'],
                   'Address':['address_title','address_line1','address_line2','city','county','state','pincode','country','email_id','phone'],
                   'Customer':['customer_name','customer_type','customer_group','territory','tax_id'],
                   'Item':['item_code','item_name','item_group','stock_uom','shelf_life_in_days','has_batch_no'],
                   'BOM':['item','quantity','uom','is_active','is_default'],
                   'Supplier':['supplier_name','supplier_group','supplier_type','country','tax_id'],
                   'Batch':['batch_id','item','manufacturing_date','expiry_date','custom_vendor_lot_number'],
                   'Quality Inspection Template':['quality_inspection_template_name']}.get(dt,[])
            values=details(linked,names)
            notes=[]
            if dt=='Item' and linked.description:notes=[dict(title='Description',value=strip_html(linked.description))]
            if values or notes:result['related'].append(dict(title=dt+' · '+name,fields=values,notes=notes))
    if doc.doctype == 'Batch':
        parent_name=doc.get('parent_batch')
        while parent_name and ('Batch',parent_name) not in seen:
            seen.add(('Batch',parent_name));parent=readable('Batch',parent_name)
            if not parent:break
            values=details(parent,['batch_id','item','manufacturing_date','expiry_date','supplier','custom_vendor_lot_number','parent_batch'])
            if values:result['related'].append(dict(title='Parent batch · '+parent_name,fields=values,notes=[]))
            parent_name=parent.get('parent_batch')
        if frappe.has_permission('Batch','read'):
            children=frappe.get_list('Batch',filters={'parent_batch':doc.name},fields=['name','item','manufacturing_date','expiry_date'],limit_page_length=0,order_by='name')
            for child in children:
                values=[dict(label=k.replace('_',' ').title(),value=str(v)) for k,v in child.items() if populated(v)]
                result['related'].append(dict(title='Child batch · '+child.name,fields=values,notes=[]))
    if doc.doctype == 'Quality Inspection' and doc.get('reference_type') and doc.get('reference_name'):
        ref=readable(doc.reference_type,doc.reference_name)
        if ref:
            values=details(ref,['company','posting_date','posting_time','stock_entry_type','purpose','work_order','bom_no','customer','supplier'])
            if values:result['related'].append(dict(title='Source document · '+ref.name,fields=values,notes=[]))
            for field in ref.meta.fields:
                if field.fieldtype == 'Table' and field.options in ('Stock Entry Detail', 'Delivery Note Item', 'Sales Invoice Item'):
                    saved = table(ref, field)
                    if saved:
                        saved['title'] = 'Source document · ' + ref.name + ' · ' + saved['title']
                        result['tables'].append(saved)
            if ref.get('work_order'):
                work_order = readable('Work Order', ref.work_order)
                if work_order:
                    saved = table(work_order, work_order.meta.get_field('required_items'))
                    if saved:
                        saved['title'] = 'Kitchen production · ' + work_order.name
                        result['tables'].append(saved)
    # Resolve explicitly saved batch links, including ERPNext's batch bundles.
    batches = set()
    for field in doc.meta.fields:
        if field.fieldtype != 'Table':
            continue
        for row in doc.get(field.fieldname) or []:
            if row.get('batch_no'):
                batches.add(row.batch_no)
            if row.get('serial_and_batch_bundle'):
                bundle = readable('Serial and Batch Bundle', row.serial_and_batch_bundle)
                if bundle:
                    batches.update(r.batch_no for r in bundle.entries if r.get('batch_no'))
    for name in sorted(batches):
        batch = readable('Batch', name)
        if batch:
            result['related'].append(dict(title='Recorded batch · ' + name,
                fields=details(batch,['batch_id','item','manufacturing_date','expiry_date','supplier','parent_batch']),notes=[]))
        # Bin is the current saved stock summary. No quantities are inferred from batch masters.
    if doc.doctype in ('Item','Warehouse') and frappe.has_permission('Bin','read'):
        filters={'item_code':doc.name} if doc.doctype=='Item' else {'warehouse':doc.name}
        stock=frappe.get_list('Bin',filters=filters,fields=['item_code','warehouse','actual_qty','reserved_qty','ordered_qty','projected_qty'],limit_page_length=0,order_by='item_code, warehouse')
        if stock:result['stock']=stock
    if frappe.has_permission('File','read'):
        result['attachments']=frappe.get_list('File',filters={'attached_to_doctype':doc.doctype,'attached_to_name':doc.name,'is_folder':0},fields=['file_name','file_url'],limit_page_length=0,order_by='file_name')
    return result
