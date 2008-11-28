# -*- encoding: utf-8 -*-
{
    "name" : "Datos iniciales para módulo base",
    "version" : "1.0",
    "author" : "Pablo Rocandio, Zikzakmedia SL",
    "website" : "http://www.zikzakmedia.com",
    "category" : "Localisation/Europe",
    "description": """Añade datos iniciales a las tablas:
    * Canales
    * Estados de ánimo
    * Categorías de empresas
    * Cargos de contactos""",
    "depends" : [
        "base",
        ],
    "init_xml" : [
        "data/data_partner_events.xml",     # Canales y estados de ánimo
        "data/data_partner_categories.xml", # Categorías de empresas
        "data/data_partner_functions.xml",  # Cargos de contactos
        ],
    "demo_xml" : [],
    "update_xml" :[],
    "active": False,
    "installable": True
}


