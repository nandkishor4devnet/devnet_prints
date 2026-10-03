"""PDF-specified registers, containing only permission-visible saved records."""
import frappe
from devnet_prints.print_data import readable


def suppliers(filters=None):
    columns = [dict(label=label,fieldname=key,fieldtype=kind,width=width,**({'options':options} if options else {})) for label,key,kind,width,options in [
        ('Item Group','item_group','Link',160,'Item Group'),('Supplier','supplier','Link',180,'Supplier'),
        ('Supplier Name','supplier_name','Data',200,None),('Certification','certification','Data',180,None),
        ('Certificate Number','number','Data',150,None),('Expiry Date','expiry','Date',120,None),('Audit Grade','audit_grade','Data',120,None)]]
    groups = {}
    for item in frappe.get_list('Item',fields=['name','item_group'],limit_page_length=0):
        record = readable('Item',item.name)
        if record:
            for link in record.get('supplier_items') or []:
                groups.setdefault(link.supplier,set()).add(item.item_group)
    data = []
    for row in frappe.get_list('Supplier',filters={'disabled':0},fields=['name'],limit_page_length=0,order_by='name'):
        supplier = readable('Supplier',row.name)
        if not supplier:
            continue
        certificates = supplier.get('custom_certification') or [frappe._dict(
            certification_type=supplier.get('custom_certification_type'),certification_number=supplier.get('custom_certification_number'),
            certification_expiry_date=supplier.get('custom_certification_expiry_date'))]
        for group in sorted(groups.get(row.name,{''})):
            for cert in certificates:
                data.append(dict(item_group=group,supplier=row.name,supplier_name=supplier.supplier_name,
                    certification=cert.get('certification_type'),number=cert.get('certification_number'),
                    expiry=cert.get('certification_expiry_date'),audit_grade=supplier.get('custom_audit_grade')))
    return columns,sorted(data,key=lambda r:(r['item_group'],r['supplier']))


def ncr(filters=None):
    columns = [dict(label=label,fieldname=key,fieldtype=kind,width=width,**({'options':options} if options else {})) for label,key,kind,width,options in [
        ('Stock Entry','stock_entry','Link',190,'Stock Entry'),('Receipt Date','date','Date',120,None),
        ('Goods Receipt','purchase_receipt','Link',180,'Purchase Receipt'),('Item','item','Link',180,'Item'),
        ('Batch','batch','Link',180,'Batch'),('Rejected Inspection','inspection','Link',190,'Quality Inspection'),('Quantity','qty','Float',110,None)]]
    data = []
    for row in frappe.get_list('Stock Entry',filters={'purpose':'Material Receipt','docstatus':['!=',2]},fields=['name'],limit_page_length=0):
        receipt = readable('Stock Entry',row.name)
        if not receipt:
            continue
        for item in receipt.items:
            inspection = readable('Quality Inspection',item.get('quality_inspection'))
            if inspection and inspection.status == 'Rejected':
                batches = [item.get('batch_no')] if item.get('batch_no') else []
                bundle = readable('Serial and Batch Bundle',item.get('serial_and_batch_bundle'))
                if bundle:
                    batches.extend(r.batch_no for r in bundle.entries if r.get('batch_no'))
                for batch in sorted(set(batches)) or [None]:
                    data.append(dict(stock_entry=receipt.name,date=receipt.posting_date,purchase_receipt=receipt.get('purchase_receipt_no'),
                        item=item.item_code,batch=batch,inspection=inspection.name,qty=item.qty))
    return columns,data
