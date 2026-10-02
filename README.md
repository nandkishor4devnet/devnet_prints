# Devnet Prints

The catalog follows **ERPNext DocType to Print Format Specification Guide.pdf**:
9 A4 print layouts (one per DocType) and two Script Reports in the existing **Devnet Prints** module.
No new DocTypes or sample business records are created by installation.

Print values come from the selected document, its saved child rows, permission-visible
linked records, saved batch bundles and saved attachments. Labels, form titles and
styling are fixed; business values have no sample fallbacks. Empty data stays empty.
Wide tables use repeated row numbers in column bands; all saved rows are retained.
The layouts use teal/navy accents, A4 sizing and repeating table headers.

## Existing DocType mapping

| PDF record | Existing DocType |
| --- | --- |
| Kitchen production / Form 13A | Work Order |
| Packing production | Stock Entry |
| Product release, CCP, hygiene, hazards, injury, training, induction | Quality Inspection |
| Dispatch | Delivery Note |
| Customer complaint | Issue |
| Corrective / preventive / incident requests | Quality Action |
| Maintenance checklist | Maintenance Visit |
| Calibration | Asset Maintenance Log |
| Audit / review | Quality Review |
| Supplier register report | Supplier, Item supplier links and saved certificates |
| NCR report | Material Receipt Stock Entries with linked rejected Quality Inspections |

Several PDF-named operational DocTypes do not exist on this site. Quality Inspection
is the existing inspection-record fallback; those forms require actual saved observations.
This package does not create missing workflows, attendance records, audit scoring,
12 measurements, shelf-life rules, email alerts or signatures. Form 14 includes saved
weight and sensory readings rather than creating separate print formats for them.

Quality Inspection uses one shared layout showing all saved readings. Quality Action
uses one register for both Corrective and Preventive actions. Quality Review uses
one audit layout. Separate variants are not installed.

Supplier approval is represented by the existing enabled Supplier flag; no separate
approval workflow is present. Report groups come from real Item supplier associations.
Audit grades appear only if the existing custom audit-grade field is populated.
NCR quantities are the stored receipt-line quantities, not inferred rejected quantities.

## Synchronization

```bash
bench --site YOUR_SITE execute devnet_prints.install.install
bench --site YOUR_SITE export-fixtures --app devnet_prints
```

Install/migrate reconciles only Print Formats owned by **Devnet Prints**. Obsolete
formats are backed up under the site's `private/files/devnet-print-archives/` before
removal. Other modules and business records are untouched. Repeated syncs keep exactly
9 catalog formats, with one format per DocType. The catalog rejects duplicate DocType entries. Script Report definitions are included in the module source.

Open an existing document, choose Print and select the corresponding `DP - ...` format.
The two register reports are available from ERPNext's Report search.

## Backend source to push

Push the `apps/devnet_prints` Git repository, including `devnet_prints/catalog.json`,
`devnet_prints/install.py`, `devnet_prints/print_data.py`,
`devnet_prints/templates/audit_record.html`, `devnet_prints/fixtures/print_format.json`,
`devnet_prints/hooks.py` and the report source directories. Install the app on the
target site and run `bench --site YOUR_SITE migrate` to synchronize the formats.
The one-format rule applies to this app’s formats; formats owned by other apps remain untouched.
