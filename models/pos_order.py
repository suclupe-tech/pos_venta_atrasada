from odoo import fields, models


class PosOrder(models.Model):
    _inherit = "pos.order"

    es_regularizacion = fields.Boolean(
        string="Regularización",
        default=False,
        copy=False,
    )

    fecha_real_venta = fields.Date(
        string="Fecha real de venta",
        copy=False,
    )

    tipo_regularizacion = fields.Selection(
        [
            ("nota_venta", "Nota de venta"),
            ("boleta", "Boleta"),
        ],
        string="Tipo regularización",
        copy=False,
    )