# -*- coding: utf-8 -*-

from odoo import models, fields, api


class AccountMove(models.Model):
    _inherit = "account.move"

    servicedate_from = fields.Date(string="Servicedate from")
    servicedate_to = fields.Date(string="Servicedate to")