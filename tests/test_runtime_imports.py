import importlib


MODULES = [
    'modules.home',
    'modules.dashboard',
    'modules.projects',
    'modules.engineering_workspace',
    'modules.bom',
    'modules.bom_hierarchy',
    'modules.manufacturing_formulas',
    'modules.should_costing',
    'modules.costing',
    'modules.routing',
    'modules.suppliers',
    'modules.rfq',
    'modules.quote_generator',
    'modules.project_save',
    'modules.forecasting',
    'modules.reporting',
]


ENGINES = [
    'engines.cost_engine',
    'engines.margin_engine',
    'engines.routing_engine',
    'engines.routing_pro_engine',
    'engines.process_engine',
    'engines.bom_engine',
    'engines.bom_intelligence_engine',
    'engines.bom_hierarchy_engine',
    'engines.manufacturing_formula_engine',
    'engines.supplier_engine',
    'engines.setup_engine',
    'engines.subcontract_engine',
    'engines.dashboard_engine',
    'engines.should_cost_engine',
]


SERVICES = [
    'services.database_service',
    'services.export_service',
    'services.excel_export_service',
    'services.report_service',
    'services.pdf_quote_service',
    'services.auth_service',
    'services.api_service',
]


def test_all_modules_import():
    for module_name in MODULES + ENGINES + SERVICES:
        importlib.import_module(module_name)
