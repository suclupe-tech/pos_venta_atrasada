from odoo import models, fields, api
from odoo.exceptions import UserError


class VentaAtrasadaWizard(models.TransientModel):
    _name = "venta.atrasada.wizard"
    _description = "Registrar Venta Atrasada"

    pos_config_id = fields.Many2one(
        "pos.config",
        string="Tienda / POS",
        required=True,
    )

    tipo_documento = fields.Selection(
        [
            ("nota_venta", "Nota de Venta"),
            ("boleta", "Boleta"),
        ],
        string="Tipo de documento",
        required=True,
    )

    fecha_real = fields.Date(
        string="Fecha real de venta",
    )

    line_ids = fields.One2many(
        "venta.atrasada.wizard.line",
        "wizard_id",
        string="Productos",
    )

    metodo_pago_id = fields.Many2one(
        "pos.payment.method",
        string="Método de pago",
        required=True,
    )

    def action_crear_venta(self):
        self.ensure_one()

        if not self.line_ids:
            raise UserError("Debes agregar al menos un producto.")

        # Buscar sesión abierta
        session = self.env["pos.session"].search(
            [
                ("config_id", "=", self.pos_config_id.id),
                ("state", "=", "opened"),
            ],
            limit=1,
        )

        if not session:
            raise UserError("No hay una sesión POS abierta para esta tienda.")

        order_lines = []

        for line in self.line_ids:
            order_lines.append(
                (
                    0,
                    0,
                    {
                        "product_id": line.product_id.id,
                        "qty": line.qty,
                        "price_unit": line.price_unit,
                        "name": line.product_id.display_name,
                    },
                )
            )

        order_vals = {
            "session_id": session.id,
            "config_id": self.pos_config_id.id,
            "lines": order_lines,
            "amount_total": sum(l.qty * l.price_unit for l in self.line_ids),
            "amount_paid": sum(l.qty * l.price_unit for l in self.line_ids),
            "amount_return": 0,
            "es_regularizacion": True,
            "fecha_real_venta": self.fecha_real,
            "tipo_regularizacion": self.tipo_documento,
        }

        order = self.env["pos.order"].create(order_vals)

        # Crear pago
        self.env["pos.payment"].create(
            {
                "amount": order.amount_total,
                "payment_method_id": self.metodo_pago_id.id,
                "pos_order_id": order.id,
            }
        )

        # Confirmar orden (esto descuenta stock)
        order._process_order()

        return {"type": "ir.actions.act_window_close"}


class VentaAtrasadaWizardLine(models.TransientModel):
    _name = "venta.atrasada.wizard.line"
    _description = "Línea Venta Atrasada"

    wizard_id = fields.Many2one("venta.atrasada.wizard")

    product_id = fields.Many2one(
        "product.product",
        string="Producto",
        required=True,
    )

    qty = fields.Float(
        string="Cantidad",
        required=True,
        default=1,
    )

    price_unit = fields.Float(
        string="Precio",
        required=True,
    )
