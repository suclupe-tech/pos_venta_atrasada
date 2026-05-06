from odoo import fields, models


class PosConfig(models.Model):
    _inherit = "pos.config"

    venta_atrasada_sequence_nota_venta_id = fields.Many2one(
        "ir.sequence",
        string="Secuencia Nota Venta Regularización",
    )
