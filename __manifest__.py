{
    "name": "POS Venta Atrasada",
    "version": "1.0",
    "category": "Point of Sale",
    "summary": "Registrar ventas atrasadas desde backend como órdenes POS",
    "depends": [
        "point_of_sale",
        "stock",
    ],
    "data": [
        "views/venta_atrasada_wizard_views.xml",
        "views/pos_order_views.xml",
    ],
    "installable": True,
    "application": False,
    "license": "LGPL-3",
}