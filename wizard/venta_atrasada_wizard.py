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
        default="nota_venta",
    )

    fecha_real = fields.Date(
        string="Fecha real de venta",
        default=fields.Date.context_today,
    )

    line_ids = fields.One2many(
        "venta.atrasada.wizard.line",
        "wizard_id",
        string="Productos",
    )

    available_payment_method_ids = fields.Many2many(
        "pos.payment.method",
        string="Métodos de pago disponibles",
        related="pos_config_id.payment_method_ids",
    )

    partner_id = fields.Many2one(
        "res.partner",
        string="Cliente",
    )

    metodo_pago_id = fields.Many2one(
        "pos.payment.method",
        string="Método de pago",
        required=True,
    )

    @api.onchange("pos_config_id")
    def _onchange_pos_config_id(self):
        self.metodo_pago_id = False

    def action_crear_venta(self):
        self.ensure_one()

        if not self.line_ids:
            raise UserError("Debes agregar al menos un producto.")

        if self.fecha_real and self.fecha_real > fields.Date.today():
            raise UserError("No puedes registrar una venta con fecha futura.")

        if self.tipo_documento == "boleta" and not self.partner_id:
            raise UserError("Debes seleccionar un cliente para emitir una boleta.")

        for line in self.line_ids:
            if line.qty <= 0:
                raise UserError("La cantidad debe ser mayor a cero.")
            if line.price_unit < 0:
                raise UserError("El precio no puede ser negativo.")

        if self.metodo_pago_id not in self.pos_config_id.payment_method_ids:
            raise UserError("El método de pago no pertenece a la tienda seleccionada.")

        session = self.env["pos.session"].search(
            [
                ("config_id", "=", self.pos_config_id.id),
                ("state", "=", "opened"),
            ],
            limit=1,
        )

        if not session:
            raise UserError("No hay una sesión POS abierta para esta tienda.")

        total = sum(l.qty * l.price_unit for l in self.line_ids)

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
                        "price_subtotal": line.qty * line.price_unit,
                        "price_subtotal_incl": line.qty * line.price_unit,
                        "name": line.product_id.display_name,
                    },
                )
            )

        order_vals = {
            "session_id": session.id,
            "config_id": self.pos_config_id.id,
            "partner_id": self.partner_id.id if self.partner_id else False,
            "sunat_document_type": (
                "NV" if self.tipo_documento == "nota_venta" else "03"
            ),
            "lines": order_lines,
            "amount_total": total,
            "amount_tax": 0,
            "amount_paid": total,
            "amount_return": 0,
            "es_regularizacion": True,
            "fecha_real_venta": self.fecha_real,
            "tipo_regularizacion": self.tipo_documento,
        }

        order = (
            self.env["pos.order"]
            .with_context(force_company=self.pos_config_id.company_id.id)
            .create(order_vals)
        )

        self.env["pos.payment"].create(
            {
                "amount": order.amount_total,
                "payment_method_id": self.metodo_pago_id.id,
                "pos_order_id": order.id,
            }
        )

        order.action_pos_order_paid()

        if hasattr(order, "_create_order_picking"):
            order._create_order_picking()

        if self.tipo_documento == "nota_venta":

            cfg = order.session_id.config_id

            if not cfg.sunat_serie_nota_venta:
                raise UserError("Falta configurar la serie de Nota de Venta en el POS.")
                # TEMPORAL:
            # Actualmente las notas de venta atrasadas usan
            # la secuencia de regularización.
            # Cuando termine la regularización, cambiar
            # a la secuencia normal de nota de venta.
            if not cfg.venta_atrasada_sequence_nota_venta_id:
                raise UserError(
                    "Falta configurar la secuencia de Nota de Venta en el POS."
                )

            correlativo = cfg.venta_atrasada_sequence_nota_venta_id.next_by_id()

            order.write(
                {
                    "sunat_state": "nota_venta",
                    "sunat_document_type": "NV",
                    "sunat_document_number": f"{cfg.sunat_serie_nota_venta}-{correlativo}",
                    "sunat_message": "Nota de Venta - No se envía a SUNAT",
                }
            )

        elif self.tipo_documento == "boleta":

            cfg = order.session_id.config_id

            if not cfg.sunat_serie_boleta:
                raise UserError("Falta configurar la serie de Boleta en el POS.")

            if not cfg.sunat_sequence_boleta_id:
                raise UserError("Falta configurar la secuencia de Boleta en el POS.")

            correlativo = cfg.sunat_sequence_boleta_id.next_by_id()

            order.write(
                {
                    "sunat_state": "boleta",
                    "sunat_document_type": "03",
                    "sunat_document_number": f"{cfg.sunat_serie_boleta}-{correlativo}",
                    "sunat_message": "Pendiente para envío por Resumen Diario",
                }
            )

        order.message_post(
            body=f"{self.tipo_documento.replace('_', ' ').title()} creada desde venta atrasada."
        )

        return {
            "type": "ir.actions.act_window",
            "name": "Venta atrasada creada",
            "res_model": "pos.order",
            "view_mode": "form",
            "res_id": order.id,
            "target": "current",
        }


class VentaAtrasadaWizardLine(models.TransientModel):
    _name = "venta.atrasada.wizard.line"
    _description = "Línea Venta Atrasada"

    wizard_id = fields.Many2one(
        "venta.atrasada.wizard",
        required=True,
        ondelete="cascade",
    )

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

    @api.onchange("product_id")
    def _onchange_product_id(self):
        for line in self:
            if line.product_id:
                line.price_unit = line.product_id.lst_price
