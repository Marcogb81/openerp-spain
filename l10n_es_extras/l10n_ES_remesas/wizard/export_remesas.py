# -*- encoding: utf-8 -*-
##############################################################################
#
# Copyright (c) 2006 ACYSOS S.L.. (http://acysos.com) All Rights Reserved.
#    Pedro Tarrafeta <pedro@acysos.com>
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
import netsvc
logger = netsvc.Logger()

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


def digitos_cc(cc_in):
    """Quita los espacios en blanco del número de C.C. (por ej. los que pone el módulo l10n_ES_partner)"""
    cc = ""
    for i in cc_in:
        try:
            int(i)
            cc += i
        except ValueError:
            pass
    return cc


def conv_ascii(text):
    """Convierte vocales accentuadas, ñ y ç a sus caracteres equivalentes ASCII"""
    old_chars = ['á','é','í','ó','ú','à','è','ì','ò','ù','ä','ë','ï','ö','ü','â','ê','î','ô','û','Á','É','Í','Ú','Ó','À','È','Ì','Ò','Ù','Ä','Ë','Ï','Ö','Ü','Â','Ê','Î','Ô','Û','ñ','Ñ','ç','Ç','ª','º']
    new_chars = ['a','e','i','o','u','a','e','i','o','u','a','e','i','o','u','a','e','i','o','u','A','E','I','O','U','A','E','I','O','U','A','E','I','O','U','A','E','I','O','U','n','N','c','C','a','o']
    for old, new in zip(old_chars, new_chars):
        text = text.replace(unicode(old,'UTF-8'), new)
    return text


class Log(Exception):
    def __init__(self):
        self.content = ""
        self.error = False
    def add(self, s, error=True):
        self.content = self.content + s
        if error:
            self.error = error
    def __call__(self):
        return self.content
    def __str__(self):
        return self.content


def _create_payment_file(self, cr, uid, data, context):

    def _cabecera_presentador_19(self):
        texto = '5180'
        texto += (orden.mode.bank_id.partner_id.vat[2:] + orden.mode.sufijo).zfill(12)
        date_now = now().strftime('%d%m%y')
        texto += date_now
        texto += 6*' '
        texto += conv_ascii(orden.mode.nombre).ljust(40)
        texto += 20*' '
        texto += cc[0:8]
        texto += 66*' '
        texto += '\r\n'
        #logger.notifyChannel('cabecera presentador: ',netsvc.LOG_INFO, texto)
        return texto

    def _cabecera_ordenante_19(self):
        texto = '5380'
        texto += (orden.mode.bank_id.partner_id.vat[2:] + orden.mode.sufijo).zfill(12)
        date_now = now().strftime('%d%m%y')
        texto += date_now
        if not orden.date_planned:
            log.add(_('User error:\n\nFixed date of charge has not been defined.'), True)
            raise log
        date_cargo = mx.DateTime.strptime(orden.date_planned,'%Y-%m-%d')
        texto += date_cargo.strftime('%d%m%y')
        texto += conv_ascii(orden.mode.nombre).ljust(40)
        texto += cc[0:20]
        texto += 8*' '
        texto += '01'
        texto += 64*' '
        texto += '\r\n'
        return texto

    def _individual_obligatorio_19(self, recibo):
        # Comprobamos que exista número de C.C. y que tenga 20 dígitos
        if type(recibo['bank_id'].acc_number) != unicode:
            log.add(_('User error:\n\nThe bank account number of the customer %s is not defined.') % (recibo['partner_id'].name), True)
            raise log
        ccc = digitos_cc(recibo['bank_id'].acc_number)
        if len(ccc) != 20:
            log.add(_('User error:\n\nThe bank account number of the customer %s has not 20 digits.') % (recibo['partner_id'].name), True)
            raise log
        texto = '5680'
        texto += (orden.mode.bank_id.partner_id.vat[2:] + orden.mode.sufijo).zfill(12)
        texto += str(recibo['name']).zfill(12)
        nombre = conv_ascii(recibo['partner_id'].name)
        texto += nombre[0:40].ljust(40)
        texto += str(ccc)[0:20].zfill(20)
        importe = int(round(-recibo['amount']*100,0))
        texto += str(importe).zfill(10)
        texto += 16*' '
        concepto = ''
        if recibo['communication']:
            concepto = recibo['communication']
        texto += conv_ascii(concepto)[0:48].ljust(48)
        # Esto es lo convencional, descripción de 40 caracteres, pero se puede aprovechar los 8 espacios en blanco finales
        #texto += conv_ascii(concepto)[0:40].ljust(40)
        #texto += 8*' '
        texto += '\r\n'
        #logger.notifyChannel('Individual obligatorio: ',netsvc.LOG_INFO, texto)
        return texto

    def _individual_opcional_19(self, recibo):
        """Para poner el segundo texto de comunicación (en lugar de nombre, domicilio y localidad opcional)"""
        texto = '5686'
        texto += (orden.mode.bank_id.partner_id.vat[2:] + orden.mode.sufijo).zfill(12)
        texto += str(recibo['name']).zfill(12)
        texto += conv_ascii(recibo['communication2'])[0:115].ljust(115)
        texto += '00000' # Campo de código postal ficticio
        texto += 14*' '
        texto += '\n'
        #logger.notifyChannel('Individual opcional: ',netsvc.LOG_INFO, texto)
        return texto

    def _total_ordenante_19(self):
        texto = '5880'
        texto += (orden.mode.bank_id.partner_id.vat[2:] + orden.mode.sufijo).zfill(12)
        texto += 72*' '
        totalordenante = int(round(-orden.total * 100,0))
        texto += str(totalordenante).zfill(10)
        texto += 6*' '
        #logger.notifyChannel('Numero total de recibos: ',netsvc.LOG_INFO, str(num_recibos))
        texto += str(num_recibos).zfill(10)
        texto += str(num_recibos + num_lineas_opc + 2).zfill(10)
        texto += 38*' '
        texto += '\r\n'
        return texto

    def _total_general_19(self):
        texto = '5980'
        texto += (orden.mode.bank_id.partner_id.vat[2:] + orden.mode.sufijo).zfill(12)
        texto += 52*' '
        texto += '0001'
        texto += 16*' '
        totalremesa = int(round(-orden.total * 100,0))
        texto += str(totalremesa).zfill(10)
        texto += 6*' '
        #logger.notifyChannel('Numero total de recibos: ',netsvc.LOG_INFO, str(num_recibos))
        texto += str(num_recibos).zfill(10)
        texto += str(num_recibos + num_lineas_opc + 4).zfill(10)
        texto += 38*' '
        texto += '\r\n'
        return texto
        texto += '\r\n'
        return texto

    def _cabecera_presentador_58(self):
        texto = '5170'
        texto += (orden.mode.bank_id.partner_id.vat[2:] + orden.mode.sufijo).zfill(12)
        date_now = now().strftime('%d%m%y')
        texto += date_now
        texto += 6*' '
        texto += conv_ascii(orden.mode.nombre).ljust(40)
        texto += 20*' '
        texto += cc[0:8]
        texto += 66*' '
        texto += '\n'
        #logger.notifyChannel('cabecera presentador: ',netsvc.LOG_INFO, texto)
        return texto

    def _cabecera_ordenante_58(self):
        texto = '5370'
        texto += (orden.mode.bank_id.partner_id.vat[2:] + orden.mode.sufijo).zfill(12)
        date_now = now().strftime('%d%m%y')
        texto += date_now
        texto += 6*' '
        texto += conv_ascii(orden.mode.nombre).ljust(40)
        texto += cc[0:20]
        texto += 8*' '
        texto += '06'
        texto += 52*' '
        # Codigo INE de la plaza... en blanco...
        texto += 9*' '
        texto += 3*' '
        texto += '\n'
        return texto

    def _individual_obligatorio_58(self, recibo):
        # Comprobamos que exista número de C.C. y que tenga 20 dígitos
        if type(recibo['bank_id'].acc_number) != unicode:
            log.add(_('User error:\n\nThe bank account number of the customer %s is not defined.') % (recibo['partner_id'].name), True)
            raise log
        ccc = digitos_cc(recibo['bank_id'].acc_number)
        if len(ccc) != 20:
            log.add(_('User error:\n\nThe bank account number of the customer %s has not 20 digits.') % (recibo['partner_id'].name), True)
            raise log
        texto = '5670'
        texto += (orden.mode.bank_id.partner_id.vat[2:] + orden.mode.sufijo).zfill(12)
        texto += str(recibo['name']).zfill(12)
        nombre = conv_ascii(recibo['partner_id'].name)
        texto += nombre[0:40].ljust(40)
        texto += str(ccc)[0:20].zfill(20)
        importe = int(round(-recibo['amount']*100,0))
        texto += str(importe).zfill(10)
        texto += 16*' '
        concepto = ''
        if recibo['communication']:
            concepto = recibo['communication']
        texto += conv_ascii(concepto)[0:40].ljust(40)
        if recibo['date']:
            date_cargo = mx.DateTime.strptime(recibo['date'],'%Y-%m-%d')
        else:
            date_cargo = mx.DateTime.strptime(recibo['ml_maturity_date'],'%Y-%m-%d')
        texto += date_cargo.strftime('%d%m%y')
        texto += 2*' '
        texto += '\n'
        #logger.notifyChannel('Individual obligatorio: ',netsvc.LOG_INFO, texto)
        return texto

    def _individual_opcional_58(self, recibo):
        """Para poner el segundo texto de comunicación"""
        texto = '5671'
        texto += (orden.mode.bank_id.partner_id.vat[2:] + orden.mode.sufijo).zfill(12)
        texto += str(recibo['name']).zfill(12)
        texto += conv_ascii(recibo['communication2'])[0:134].ljust(134)
        texto += '\n'
        #logger.notifyChannel('Individual opcional: ',netsvc.LOG_INFO, texto)
        return texto

    def _registro_obligatorio_domicilio_58(self, recibo):
        """registro obligatorio domicilio 58 para los no domiciliados (por ahora no se contempla)"""
        texto = '5676'
        texto += (orden.mode.bank_id.partner_id.vat[2:] + orden.mode.sufijo).zfill(12)
        texto += str(recibo['name']).zfill(12)
        texto += conv_ascii(recibo['partner_id'].name).ljust(40)
        texto += str(recibo['bank_id'].acc_number)[0:20].zfill(20)
        importe = int(-recibo['amount']*100)
        texto += str(importe).zfill(10)
        texto += 16*' '
        concepto = ''
        if recibo['communication']:
            concepto = recibo['communication']
        texto += conv_ascii(concepto)[0:40].ljust(40)
        if recibo['date']:
            texto += recibo['date']
        else:
            texto += recibo['ml_maturity_date']
        texto += '  '
        texto += '\n'
        #logger.notifyChannel('Individual obligatorio: ',netsvc.LOG_INFO, texto)
        return texto

    def _total_ordenante_58(self):
        texto = '5870'
        texto += (orden.mode.bank_id.partner_id.vat[2:] + orden.mode.sufijo).zfill(12)
        texto += 72*' '
        totalordenante = int(-orden.total * 100)
        texto += str(totalordenante).zfill(10)
        texto += 6*' '
        #logger.notifyChannel('Numero total de recibos: ',netsvc.LOG_INFO, str(num_recibos))
        texto += str(num_recibos).zfill(10)
        texto += str(num_recibos + num_lineas_opc + 2).zfill(10)
        texto += 38*' '
        texto += '\n'
        return texto

    def _total_general_58(self):
        texto = '5970'
        texto += (orden.mode.bank_id.partner_id.vat[2:] + orden.mode.sufijo).zfill(12)
        texto += 52*' '
        texto += '0001'
        texto += 16*' '
        totalremesa = int(round(-orden.total * 100,0))
        texto += str(totalremesa).zfill(10)
        texto += 6*' '
        #logger.notifyChannel('Numero total de recibos: ',netsvc.LOG_INFO, str(num_recibos))
        texto += str(num_recibos).zfill(10)
        texto += str(num_recibos + num_lineas_opc + 4).zfill(10)
        texto += 38*' '
        texto += '\n'
        return texto

    txt_remesa = ''
    num_recibos = 0
    num_lineas_opc = 0
    log = Log()

    try:
        pool = pooler.get_pool(cr.dbname)
        orden = pool.get('payment.order').browse(cr, uid, data['id'], context)
        if not orden.line_ids:
            log.add(_('User error:\n\nWizard can not generate export file, there are not payment lines.'), True)
            raise log

        # Comprobamos que exista número de C.C. y que tenga 20 dígitos
        if not orden.mode.bank_id:
            log.add(_('User error:\n\nThe bank account of the company %s is not defined.') % (orden.mode.partner_id.name), True)
            raise log
        cc = digitos_cc(orden.mode.bank_id.acc_number)
        if len(cc) != 20:
            log.add(_('User error:\n\nThe bank account number of the company %s has not 20 digits.') % (orden.mode.partner_id.name), True)
            raise log
        # Comprobamos que exista el CIF de la compañía asociada al C.C. del modo de pago
        if not orden.mode.bank_id.partner_id.vat:
            log.add(_('User error:\n\nThe company VAT number related to the bank account of the payment mode is not defined.'), True)
            raise log

        recibos = []
        if data['form']['join']:
            # Lista con todos los partners+bancos diferentes de la remesa
            partner_bank_l = reduce(lambda l, x: x not in l and l.append(x) or l,
                                     [(recibo.partner_id,recibo.bank_id) for recibo in orden.line_ids], [])
            # Cómputo de la lista de recibos agrupados por mismo partner+banco.
            # Los importes se suman, los textos se concatenan con un espacio en blanco y las fechas se escoge el máximo
            for partner,bank in partner_bank_l:
                lineas = [recibo for recibo in orden.line_ids if recibo.partner_id==partner and recibo.bank_id==bank]
                recibos.append({
                    'partner_id': partner,
                    'bank_id': bank,
                    'name': reduce(lambda x, y: x+' '+y, [l.name for l in lineas], ''),
                    'amount': reduce(lambda x, y: x+y, [l.amount for l in lineas], 0),
                    'communication': reduce(lambda x, y: x+' '+(y or ''), [l.communication for l in lineas], ''),
                    'communication2': reduce(lambda x, y: x+' '+(y or ''), [l.communication2 for l in lineas], ''),
                    'date': max([l.date for l in lineas]),
                    'ml_maturity_date': max([l.ml_maturity_date]),
                })
        else:
            # Cada línea de pago es un recibo
            for l in orden.line_ids:
                recibos.append({
                    'partner_id': l.partner_id,
                    'bank_id': l.bank_id,
                    'name': l.name,
                    'amount': l.amount,
                    'communication': l.communication,
                    'communication2': l.communication2,
                    'date': l.date,
                    'ml_maturity_date': l.ml_maturity_date,
                })

        if orden.mode.tipo == 'csb_19':
            txt_remesa += _cabecera_presentador_19(self)
            txt_remesa += _cabecera_ordenante_19(self)

            for recibo in recibos:
                txt_remesa += _individual_obligatorio_19(self, recibo)
                num_recibos = num_recibos + 1
                if recibo['communication2']:
                    txt_remesa += _individual_opcional_19(self, recibo)
                    num_lineas_opc = num_lineas_opc + 1

            txt_remesa += _total_ordenante_19(self)
            txt_remesa += _total_general_19(self)

        elif orden.mode.tipo == 'csb_58':
            txt_remesa += _cabecera_presentador_58(self)
            txt_remesa += _cabecera_ordenante_58(self)

            for recibo in recibos:
                txt_remesa += _individual_obligatorio_58(self, recibo)
                num_recibos = num_recibos + 1
                if recibo['communication2']:
                    txt_remesa += _individual_opcional_58(self, recibo)
                    num_lineas_opc = num_lineas_opc + 1

            txt_remesa += _total_ordenante_58(self)
            txt_remesa += _total_general_58(self)

        else:
            log.add(_('User error:\n\nThe payment mode is not CSB 19 or CSB 58'), True)
            raise log

        #logger.notifyChannel('remesas texto: ',netsvc.LOG_INFO, '\r\n' + txt_remesa)

    except Log:
        return {'note':log(), 'reference':orden.id, 'pay':False, 'state':'failed'}
    else:
        file = base64.encodestring(txt_remesa)
        fname = (_('remesa') + '_' + orden.mode.tipo + '_' + orden.reference + '.txt').replace('/','-')
        pool.get('ir.attachment').create(cr, uid, {
            'name': _('Remesa ') + orden.mode.tipo + ' ' + orden.reference,
            'datas': file,
            'datas_fname': fname,
            'res_model': 'payment.order',
            'res_id': orden.id,
            }, context=context)
        log.add(_("Successfully Exported\n\nSummary:\n Total amount paid: %.2f\n Total Number of Payments: %d\n") % (-orden.total, num_recibos))
        pool.get('payment.order').set_done(cr,uid,orden.id,context)
        return {'note':log(), 'reference':orden.id, 'pay':file, 'pay_fname':fname, 'state':'succeeded'}


class wizard_payment_file_19_58(wizard.interface):
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
wizard_payment_file_19_58('export_payment_file_19_58')
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:

