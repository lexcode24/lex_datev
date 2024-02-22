# -*- coding: utf-8 -*-
{
    'name': "lex_datev",

    'summary': """
        Eine Erweiterung für Datev-Export""",

    'description': """
        Eine Erweiterung für Datev-Export
    """,

    'author': "My Company",
    'website': "https://www.lexcode.de",

    # Categories can be used to filter modules in modules listing
    # Check https://github.com/odoo/odoo/blob/16.0/odoo/addons/base/data/ir_module_category_data.xml
    # for the full list
    'category': 'Uncategorized',
    'version': '16.0.0.1',

    # any module necessary for this one to work correctly
    'depends': ['base', 'contacts', 'l10n_de_reports', 'lex_service_dates'],

    # always loaded
    'data': [
        'data/datev_sequences.xml',
    ],
    'license': 'OPL-1',
}
