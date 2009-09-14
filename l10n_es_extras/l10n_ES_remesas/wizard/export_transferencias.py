# -*- encoding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (c) 2006 ACYSOS S.L. (http://acysos.com) All Rights Reserved.
#                       Pedro Tarrafeta <pedro@acysos.com>
#    Copyright (c) 2008 Pablo Rocandio. All Rights Reserved.
#    Copyright (c) 2009 Zikzakmedia S.L. (http://zikzakmedia.com) All Rights Reserved.
#                       Jordi Esteve <jesteve@zikzakmedia.com>
#    Copyright (c) 2009 NaN (http://www.nan-tic.com) All Rights Reserved.
#                       Albert Cervera i Areny <albert@nan-tic.com>
#    $Id$
#
# Corregido para instalación TinyERP estándar 4.2.0: Zikzakmedia S.L. 2008
#   Jordi Esteve <jesteve@zikzakmedia.com>
#
# Añadidas cuentas de remesas y tipos de pago. 2008
#    Pablo Rocandio <salbet@gmail.com>
#
# Rehecho de nuevo para instalación OpenERP 5.0.0 sobre account_payment_extension: Zikzakmedia S.L. 2009
#   Jordi Esteve <jesteve@zikzakmedia.com>
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
#    You should have received a copy of the GNU General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
##############################################################################

import pooler
import wizard
import base64
import mx.DateTime
from mx.DateTime import now
from tools.translate import _
from common import *

join_form = """<?xml version="1.0"?>
<form string="Payment order export">
    <field name="join"/>
</form>"""

join_fields = {
    'join' : {'string':'Join payment lines of the same partner and bank account', 'type':'boolean'},
}

export_form = """<?xml version="1.0"?>
<form string="Payment order export">
    <field name="pay" filename="pay_fname"/>
    <field name="pay_fname" invisible="1"/>
    <field name="note" colspan="4" nolabel="1"/>
</form>"""

export_fields = {
    'pay' : {
        'string':'Payment order file',
        'type':'binary',
        'required': False,
        'readonly':True,
    },
    'pay_fname': {'string':'File name', 'type':'char', 'size':64},
    'note' : {'string':'Log', 'type':'text'},
}

class payment_file_creator:
    def convert_text(self, text, size):
        return conv_ascii(text)[:size].ljust(size)

    def convert_float(self, number, size):
        # Set context for translations
        context = self.context

        text = str( int( round( number * 100, 0 ) ) )
        if len(text) > size:
            self.log.add(_('Error:\n\nCan not convert float number %(number).2f to fit in %(size)d characters.') % {'number': number, 'size': size})
            raise self.log
        return text.zfill(size)

    def convert_int(self, number, size):
        # Set context for translations
        context = self.context

        text = str( number )
        if len(text) > size:
            self.log.add(_('Error:\n\nCan not convert integer number %(number)d to fit in %(size)d characters.') % {'number': number, 'size': size})
            raise self.log
        return text.zfill(size)

    def convert(self, value, size):
        if value == False:
            return self.convert_text('', size)
        elif isinstance(value, float):
            return self.convert_float(value, size)
        elif isinstance(value, int):
            return self.convert_int(value, size)
        else:
            return self.convert_text(value, size)

    def convert_bank_account(self, value, partner_name):
        if not isinstance(value, basestring):
            self.log.add(_('User error:\n\nThe bank account number of %s is not defined.') % partner_name)
            raise self.log
        ccc = digitos_cc(value)
        if len(ccc) != 20:
            self.log.add(_('User error:\n\nThe bank account number of %s does not have 20 digits.') % partner_name)
            raise self.log
        return ccc

    def start(self):
        return self.convert(self.order.mode.bank_id.partner_id.vat[2:] + self.order.mode.sufijo, 12)

    def _cabecera_ordenante_34(self):
        today = now().strftime('%d%m%y')

        text = ''

        # Primer tipo
        text += '0362'
        text += self.start()
        text += 12*' '
        text += '001'
        text += today
        if self.order.date_planned:
            planned = mx.DateTime.strptime(self.order.date_planned, '%Y-%m-%d')
            text += planned.strftime('%d%m%y')
        else:
            text += today
        #text += self.convert(self.order.mode.nombre, 40)
        text += self.convert_bank_account(self.order.mode.bank_id.acc_number, self.order.mode.partner_id.name)
        text += '0'
        text += 8*' '
        text += '\n'

        # Segundo Tipo 
        text += '0362'
        text += self.start()
        text += 12*' '
        text += '002'
        text += self.convert(self.order.mode.bank_id.partner_id.name, 36)
        text += 5*' '
        text += '\n'

        # Tercer Tipo 
        text += '0362'
        text += self.start()
        text += 12*' '
        text += '003'
        # Direccion
        address_id = self.pool.get('res.partner').address_get(self.cr, self.uid, [self.order.mode.bank_id.partner_id.id], ['invoice'])['invoice']
        if not address_id:
            self.log.add(_('User error:\n\nCompany %s has no invoicing address.') % address_id)
            raise self.log

        street = self.pool.get('res.partner.address').read(self.cr, self.uid, [address_id], ['street'], self.context)[0]['street']
        text += self.convert(street, 36)
        text += 5*' '
        text += '\n'

        # Cuarto Tipo 
        text += '0362'
        text += self.start()
        text += 12*' '
        text += '004'
        text += self.convert(self.order.mode.bank_id.street, 36)
        text += 5*' '
        text += '\n'
        return text

    def _cabecera_nacionales_34(self):
        text = '0456'
        text += self.start()
        text += 12*' '
        text += 3*' '
        text += 41*' '
        text += '\n'
        return text

    def _detalle_nacionales_34(self, recibo):
        # Primer Registro
        text = ''
        text += '0656'
        text += self.start()
        text += self.convert(recibo['partner_id'].vat, 12)
        text += '010'
        text += self.convert(recibo['amount'], 12)
        text += self.convert_bank_account(recibo['bank_id'].acc_number, recibo['partner_id'].name)
        text += '1'
        text += '9' # Otros conceptos (ni Nomina ni Pension)
        text += '1'
        text += 6*' '
        text += '\n'

        # Segundo Registro
        text += '0656'
        text += self.start()
        text += self.convert( recibo['partner_id'].vat, 12)
        text += '011'
        text += self.convert( recibo['partner_id'].name, 36)
        text += 5*' '
        text += '\n'
        return text

    def _totales_nacionales_34(self):
        text = '0856'
        text += self.start()
        text += 12*' '
        text += 3*' '
        text += self.convert(self.order.total, 12)
        text += self.convert(self.payment_line_count, 8)
        text += self.convert(1 + (self.payment_line_count * 2) + 1, 10)
        text += 6*' '
        text += 5*' '
        text += '\n'
        return text

    def _total_general_34(self):
        text = '0962'
        text += self.start()
        text += 12*' '
        text += 3*' '
        text += self.convert(self.order.total, 12)
        text += self.convert(self.payment_line_count, 8)
        text += self.convert(4 + 1 + (self.payment_line_count * 2 ) + 1 + 1, 10)
        text += 6*' '
        text += 5*' '
        text += '\n'
        return text

    def create_file(self):
        self.pool = pooler.get_pool(self.cr.dbname)
        self.order = self.pool.get('payment.order').browse(self.cr, self.uid, self.data['id'], self.context)
        if not self.order.line_ids:
            self.log.add(_('User error:\n\nWizard can not generate export file, there are no payment lines.'))
            raise self.log

        # Comprobamos que exista el CIF de la compañía asociada al C.C. del modo de pago
        if not self.order.mode.bank_id.partner_id.vat:
            self.log.add(_('User error:\n\nThe company VAT number related to the bank account of the payment mode is not defined.'))
            raise self.log

        recibos = []
        if self.data['form']['join']:
            # Lista con todos los partners+bancos diferentes de la orden
            partner_bank_l = reduce(lambda l, x: x not in l and l.append(x) or l,
                                     [(recibo.partner_id,recibo.bank_id) for recibo in self.order.line_ids], [])
            # Cómputo de la lista de recibos agrupados por mismo partner+banco.
            # Los importes se suman, los textos se concatenan con un espacio en blanco y las fechas se escoge el máximo
            for partner,bank in partner_bank_l:
                lineas = [recibo for recibo in self.order.line_ids if recibo.partner_id==partner and recibo.bank_id==bank]
                recibos.append({
                    'partner_id': partner,
                    'bank_id': bank,
                    'name': partner.ref,
                    'amount': reduce(lambda x, y: x+y, [l.amount for l in lineas], 0),
                    'communication': reduce(lambda x, y: x+' '+(y or ''), [l.name+' '+l.communication for l in lineas], ''),
                    'communication2': reduce(lambda x, y: x+' '+(y or ''), [l.communication2 for l in lineas], ''),
                    'date': max([l.date for l in lineas]),
                    'ml_maturity_date': max([l.ml_maturity_date]),
                })
        else:
            # Cada línea de pago es un recibo
            for l in self.order.line_ids:
                recibos.append({
                    'partner_id': l.partner_id,
                    'bank_id': l.bank_id,
                    'name': l.partner_id.ref,
                    'amount': l.amount,
                    'communication': l.name+' '+l.communication,
                    'communication2': l.communication2,
                    'date': l.date,
                    'ml_maturity_date': l.ml_maturity_date,
                })

        if self.order.mode.tipo != 'csb_34':
            self.log.add(_('User error:\n\nThe payment mode is not CSB 34'))
            raise self.log

        self.payment_line_count = 0
        self.record_count = 0

        file = ''
        file += self._cabecera_ordenante_34()
        file += self._cabecera_nacionales_34()
        for recibo in recibos:
            file += self._detalle_nacionales_34(recibo)
            self.payment_line_count += 1
            self.record_count += 2
        file += self._totales_nacionales_34()
        self.record_count += 1
        file += self._total_general_34()
        return file

    def create(self, cr, uid, data, context):
        self.cr = cr
        self.uid = uid
        self.data = data
        self.context = context

        self.log = Log()
        try:
            file = self.create_file()
        except Log:
            return {'note': self.log(), 'reference':self.order.id, 'pay':False, 'state':'failed'}

        file = base64.encodestring(file)
        fname = '%s_%s.txt' % (self.order.mode.tipo, self.order.reference)
        fname = fname.replace('/', '-')
        self.pool.get('ir.attachment').create(cr, uid, {
            'name': _('Remesa ') + self.order.mode.tipo + ' ' + self.order.reference,
            'datas': file,
            'datas_fname': fname,
            'res_model': 'payment.order',
            'res_id': self.order.id,
        }, context=context)
        self.log.add(_("Successfully Exported\n\nSummary:\n Total amount paid: %(amount).2f\n Total Number of Payments: %(number)d\n") % {'amount': self.order.total, 'number': self.payment_line_count} )
        self.pool.get('payment.order').set_done(cr,uid,self.order.id,context)
        return {'note': self.log(), 'reference':self.order.id, 'pay':file, 'pay_fname':fname, 'state':'succeeded'}


class wizard_payment_file_34(wizard.interface):
    def _create_payment_file(self, cr, uid, data, context):
        creator = payment_file_creator()
        return creator.create( cr, uid, data, context )

    states = {
        'init' : {
            'actions' : [],
            'result' : {'type' : 'form',
                        'arch' : join_form,
                        'fields' : join_fields,
                        'state' : [('export', 'Ok','gtk-ok') ]}
        },
        'export': {
            'actions' : [_create_payment_file],
            'result' : {'type' : 'form',
                        'arch' : export_form,
                        'fields' : export_fields,
                        'state' : [('end', 'Ok','gtk-ok') ]}
        }

    }
wizard_payment_file_34('export_payment_file_34')

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:

