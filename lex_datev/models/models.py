# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from datetime import datetime
from collections import namedtuple
from odoo.tools import pycompat, float_repr
import io
import logging

_logger = logging.getLogger(__name__)

BalanceKey = namedtuple('BalanceKey', ['from_code', 'to_code', 'partner_id', 'tax_id'])


class DatevExportCSV(models.AbstractModel):
    _inherit = 'account.general.ledger.report.handler'

    def _l10n_de_datev_get_account_identifier(self, account, partner):
        
        if account.account_type == 'asset_receivable':
            # for customers
            if not partner.l10n_de_datev_identifier_customer:
                partner.l10n_de_datev_identifier_customer = self.env['ir.sequence'].next_by_code('sequence.l10n_de_datev_identifier_customer')
            return partner.l10n_de_datev_identifier_customer
        else:
            # for vendors
            if not partner.l10n_de_datev_identifier:
                partner.l10n_de_datev_identifier = self.env['ir.sequence'].next_by_code('sequence.l10n_de_datev_identifier')
            return partner.l10n_de_datev_identifier

        def _l10n_de_datev_get_partner_list(self, options, customer=True):
            date_to = fields.Date.from_string(options.get('date').get('date_to'))
            fy = self.env.company.compute_fiscalyear_dates(date_to)
    
            fy = datetime.strftime(fy.get('date_from'), '%Y%m%d')
            datev_info = self._l10n_de_datev_get_client_number()
            account_length = self._l10n_de_datev_get_account_length()
    
            output = io.BytesIO()
            writer = pycompat.csv_writer(output, delimiter=';', quotechar='"', quoting=2)
            preheader = ['EXTF', 510, 16, 'Debitoren/Kreditoren', 4, None, None, '', '', '', datev_info[0], datev_info[1], fy, account_length,
                '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '']
            header = ['Konto', 'Name (AdressatentypUnternehmen)', 'Name (Adressatentypnatürl. Person)', '', '', '', 'Adressatentyp']
            lines = [preheader, header]
    
            move_line_ids = set()
            report = self.env['account.report'].browse(options['report_id'])
            for line in report._get_lines({**options, 'unfold_all': True}):
                model, model_id = report._parse_line_id(line['id'])[-1][-2:]
                if model == 'account.move.line':
                    move_line_ids.add(str(model_id))
    
            if len(move_line_ids):
                if customer:
                    move_types = ('out_refund', 'out_invoice', 'out_receipt')
                else:
                    move_types = ('in_refund', 'in_invoice', 'in_receipt')
                select = """SELECT distinct(aml.partner_id)
                            FROM account_move_line aml
                            LEFT JOIN account_move m
                            ON aml.move_id = m.id
                            WHERE aml.id IN %s
                                AND aml.tax_line_id IS NULL
                                AND aml.debit != aml.credit
                                AND aml.matching_number IS NOT NULL
                                AND m.move_type IN %s
                                AND aml.account_id != m.l10n_de_datev_main_account_id"""
                self.env.cr.execute(select, (tuple(move_line_ids), move_types))
            partners = self.env['res.partner'].browse([p.get('partner_id') for p in self.env.cr.dictfetchall()])
            for partner in partners:
                if customer:
                    code = self._l10n_de_datev_find_partner_account(partner.property_account_receivable_id, partner)
                else:
                    code = self._l10n_de_datev_find_partner_account(partner.property_account_payable_id, partner)
                line_value = {
                    'code': code,
                    'company_name': partner.name if partner.is_company else '',
                    'person_name': '' if partner.is_company else partner.name,
                    'natural': partner.is_company and '2' or '1'
                }
                # Idiotic program needs to have a line with 243 elements ordered in a given fashion as it
                # does not take into account the header and non mandatory fields
                array = ['' for x in range(243)]
                array[0] = line_value.get('code')
                array[1] = line_value.get('company_name')
                array[2] = line_value.get('person_name')
                array[6] = line_value.get('natural')
                lines.append(array)
            writer.writerows(lines)
            return output.getvalue()

    # Source: http://www.datev.de/dnlexom/client/app/index.html#/document/1036228/D103622800029
    def _l10n_de_datev_get_csv(self, options, moves):
        # last 2 element of preheader should be filled by "consultant number" and "client number"
        date_from = fields.Date.from_string(options.get('date').get('date_from'))
        date_to = fields.Date.from_string(options.get('date').get('date_to'))
        fy = self.env.company.compute_fiscalyear_dates(date_to)

        date_from = datetime.strftime(date_from, '%Y%m%d')
        date_to = datetime.strftime(date_to, '%Y%m%d')
        fy = datetime.strftime(fy.get('date_from'), '%Y%m%d')
        datev_info = self._l10n_de_datev_get_client_number()
        account_length = self._l10n_de_datev_get_account_length()

        output = io.BytesIO()
        writer = pycompat.csv_writer(output, delimiter=';', quotechar='"', quoting=2)
        preheader = ['EXTF', 510, 21, 'Buchungsstapel', 7, '', '', '', '', '', datev_info[0], datev_info[1], fy, account_length,
            date_from, date_to, '', '', '', '', 0, 'EUR', '', '', '', '', '', '', '', '', '']
        header = ['Umsatz (ohne Soll/Haben-Kz)', 'Soll/Haben-Kennzeichen', 'WKZ Umsatz', 'Kurs', 'Basis-Umsatz', 'WKZ Basis-Umsatz', 'Konto', 'Gegenkonto (ohne BU-Schlüssel)', 'BU-Schlüssel', 'Belegdatum', 'Belegfeld 1', 'Belegfeld 2', 'Skonto', 'Buchungstext', 'Leistungsdatum von', 'Leistungsdatum bis']

        # if we do _get_lines with some unfolded lines, only those will be returned, but we want all of them
        move_line_ids = []
        report = self.env['account.report'].browse(options['report_id'])
        for line in report._get_lines({**options, 'unfold_all': True}):
            model, model_id = report._parse_line_id(line['id'])[-1][-2:]
            if model == 'account.move.line':
                move_line_ids.append(int(model_id))

        lines = [preheader, header]

        for m in moves:
            line_values = {}  # key: BalanceKey
            move_currencies = {}
            payment_account = 0  # Used for non-reconciled payments

            for aml in m.line_ids:
                if aml.debit == aml.credit:
                    # Ignore debit = credit = 0
                    continue
                # If both account and counteraccount are the same, ignore the line
                if aml.account_id == aml.move_id.l10n_de_datev_main_account_id:
                    continue
                # If line is a tax ignore it as datev requires single line with gross amount and deduct tax itself based
                # on account or on the control key code
                if aml.tax_line_id:
                    continue

                aml_taxes = aml.tax_ids.compute_all(aml.balance, aml.company_id.currency_id, partner=aml.partner_id, handle_price_include=False)
                line_amount = aml_taxes['total_included']

                code_correction = ''
                if aml.tax_ids:
                    codes = set(aml.tax_ids.mapped('l10n_de_datev_code'))
                    if len(codes) == 1:
                        # there should only be one max, else skip code
                        code_correction = codes.pop() or ''

                # account and counterpart account
                to_account_code = str(self._l10n_de_datev_find_partner_account(aml.move_id.l10n_de_datev_main_account_id, aml.partner_id))
                account_code = u'{code}'.format(code=self._l10n_de_datev_find_partner_account(aml.account_id, aml.partner_id))

                # We don't want to have lines with our outstanding payment/receipt as they don't represent real moves
                # So if payment skip one move line to write, while keeping the account
                # and replace bank account for outstanding payment/receipt for the other line

                if aml.payment_id:
                    if payment_account == 0:
                        payment_account = account_code
                        continue
                    else:
                        to_account_code = payment_account

                # group lines by account, to_account & partner
                match_key = BalanceKey(from_code=account_code, to_code=to_account_code, partner_id=aml.partner_id,
                                       tax_id=code_correction)

                if match_key in line_values:
                    # values already in line_values
                    line_values[match_key]['line_amount'] += line_amount
                    line_values[match_key]['line_base_amount'] += aml.price_total
                    move_currencies[match_key].add(aml.currency_id)
                    continue

                # reference
                receipt1 = ''
                my_aml = False
                if aml.matching_number:
                    receipt1 = aml.matching_number
                else:
                    my_aml = self.env['account.move.line'].search([('move_id', '=', aml.move_id.id), ('matching_number', '!=', False)])
                    if my_aml:
                        receipt1 = my_aml.matching_number
                #if aml.move_id.journal_id.type == 'purchase' and aml.move_id.ref:
                #    receipt1 = aml.move_id.ref

                # on receivable/payable aml of sales/purchases
                receipt2 = aml.move_id.name
                if to_account_code == account_code and aml.date_maturity:
                    receipt2 = aml.date

                #receipt2 = ''
                #if aml.move_id.ref:
                #    receipt2 = aml.move_id.ref

                # buchungstext = partner_id.name
                buchungstext = ''
                if aml.move_id.partner_id:
                    buchungstext = aml.move_id.partner_id.name

                # Leistungszeitraum von
                servicedate_from = ''
                if aml.move_id.servicedate_from:
                    servicedate_from = datetime.strftime(aml.move_id.servicedate_from, '%-d%m')

                # Leistungszeitraum bis
                servicedate_to = ''
                if aml.move_id.servicedate_to:
                    servicedate_to = datetime.strftime(aml.move_id.servicedate_to, '%-d%m')

                move_currencies[match_key] = set([aml.currency_id])
                currency = aml.company_id.currency_id
                line_values[match_key] = {
                    'waehrung': currency.name,
                    'line_base_amount': aml.price_total,
                    'line_base_currency': aml.currency_id.name,
                    'buschluessel': code_correction,
                    'gegenkonto': to_account_code,
                    'belegfeld1': receipt1,
                    'belegfeld2': receipt2,
                    'datum': datetime.strftime(aml.move_id.date, '%-d%m'),
                    'konto': account_code,
                    'kurs': str(aml.currency_id.rate).replace('.', ','),
                    'buchungstext': buchungstext,
                    'servicedate_from': servicedate_from,
                    'servicedate_to': servicedate_to,
                    'line_amount': line_amount,
                }

            for match_key, line_value in line_values.items():
                # For DateV, we can't have negative amount on a line, so we need to inverse the amount and inverse the
                # credit/debit symbol.
                line_value['sollhaben'] = 'h' if line_value['line_amount'] < 0 else 's'
                line_value['line_amount'] = abs(line_value['line_amount'])
                # Idiotic program needs to have a line with 116 elements ordered in a given fashion as it
                # does not take into account the header and non mandatory fields
                array = ['' for x in range(116)]
                array[0] = float_repr(line_value['line_amount'], aml.company_id.currency_id.decimal_places).replace('.', ',')
                array[1] = line_value.get('sollhaben')
                array[2] = line_value.get('waehrung')
                if (len(move_currencies[match_key]) == 1) and line_value.get('line_base_currency') != line_value.get('waehrung'):
                    array[3] = line_value.get('kurs')
                    array[4] = float_repr(line_value['line_base_amount'], aml.currency_id.decimal_places).replace('.', ',')
                    array[5] = line_value.get('line_base_currency')
                array[6] = line_value.get('konto')
                array[7] = line_value.get('gegenkonto')
                array[8] = line_value.get('buschluessel')
                array[9] = line_value.get('datum')
                array[10] = line_value.get('belegfeld1')
                array[11] = line_value.get('belegfeld2')
                array[13] = line_value.get('buchungstext')
                array[14] = line_value.get('servicedate_from')
                array[15] = line_value.get('servicedate_to')
                lines.append(array)

        writer.writerows(lines)
        return output.getvalue()