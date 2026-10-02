app_name = "devnet_prints"
app_title = "Devnet Prints"
app_publisher = "4Devnet"
app_description = "Print formats for Frappe and ERPNext"
app_license = "MIT"
required_apps = ["erpnext"]

fixtures = [{"dt": "Print Format", "filters": [["module", "=", "Devnet Prints"]]}]

# Synchronise app-owned print formats for existing DocTypes.
after_install = 'devnet_prints.install.install'
after_migrate = 'devnet_prints.install.install'

jinja = {"methods": ["devnet_prints.print_data.get_print_context"]}
