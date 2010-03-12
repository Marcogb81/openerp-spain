# -*- encoding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (c) 2009 Zikzakmedia S.L. (http://zikzakmedia.com) All Rights Reserved.
#                       Jordi Esteve <jesteve@zikzakmedia.com>
#    $Id$
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

import wizard
import pooler
import base64
import time
import re
from tools import mod10r
from tools.translate import _
import netsvc
logger = netsvc.Logger()

form = """<?xml version="1.0" encoding="utf-8"?>
<form string="Bank statements import according to norm C43">
    <field name="file"/>
</form>"""

fields = {
    'file': {
        'string': 'Bank Statements File',
        'type': 'binary',
        'required': True,
    },
}


def _importar(obj, cursor, user, data, context):
    pool = pooler.get_pool(cursor.dbname)
    statement_obj = pool.get('account.bank.statement')
    statement_line_obj = pool.get('account.bank.statement.line')
    statement_reconcile_obj = pool.get('account.bank.statement.reconcile')
    move_line_obj = pool.get('account.move.line')
    partner_obj = pool.get('res.partner')
    property_obj = pool.get('ir.property')
    model_fields_obj = pool.get('ir.model.fields')
    attachment_obj = pool.get('ir.attachment')
    conceptos_obj = pool.get('l10n.es.extractos.concepto')
    file = data['form']['file']
    statement_id = data['id']

    st = statement_obj.browse(cursor, user, statement_id)
    if st.state == 'confirm':
        raise wizard.except_wizard(_('Error'), _('The bank statement is alredy confirmed. It can not be imported from file.'))

    # Lectura del archivo C43
    num_registros = 0
    extracto = {}
    lextracto = []
    file2 = base64.decodestring(file)
    try:
        unicode(file2, 'utf8')
    except Exception, e: # Si no puede convertir a UTF-8 es que debe estar en ISO-8859-1: Lo convertimos
        file2 = unicode(file2, 'iso-8859-1').encode('utf-8')
        #print e
        #raise wizard.except_wizard(_('Error !'), _('Archivo a importar codificado en ISO-8859-1'))

    for line in file2.split("\n"):
        if len(line) == 0:
            continue
        if line[0:2]=='11': # Registro cabecera de cuenta (obligatorio)
            num_registros += 1
            extracto['entidad'] = line[2:6]
            extracto['oficina'] = line[6:10]
            extracto['cuenta'] = line[10:20]
            extracto['fecha_ini'] = time.strftime('%Y-%m-%d', time.strptime(line[20:26], '%y%m%d'))
            extracto['fecha_fin'] = time.strftime('%Y-%m-%d', time.strptime(line[26:32], '%y%m%d'))
            extracto['saldo_ini'] = float(line[33:45]) + (float(line[45:47]) / 100)
            if line[32:33] == '1': # 1-Deudor 2-Acreedor
                extracto['saldo_ini'] *= -1
            extracto['divisa'] = line[47:50]
            extracto['modalidad'] = line[50:51] # 1,2 o 3
            extracto['nombre_propietario'] = line[51:77] # Nombre abreviado propietario cuenta
        elif line[0:2]=='22': # Registro principal de movimiento (obligatorio)
            num_registros += 1
            lextracto.append({})
            lextracto[-1]['of_origen'] = line[6:10]
            lextracto[-1]['fecha_opera'] = time.strftime('%Y-%m-%d', time.strptime(line[10:16], '%y%m%d'))
            lextracto[-1]['fecha_valor'] = time.strftime('%Y-%m-%d', time.strptime(line[16:22], '%y%m%d'))
            lextracto[-1]['concepto_c'] = line[22:24]
            lextracto[-1]['concepto_p'] = line[24:27]
            lextracto[-1]['importe'] = float(line[28:40]) + (float(line[40:42]) / 100)
            if line[27:28] == '1': # 1-Deudor 2-Acreedor
                lextracto[-1]['importe'] *= -1
            lextracto[-1]['num_documento'] = line[41:52]
            lextracto[-1]['referencia1'] = line[52:64]
            lextracto[-1]['referencia2'] = line[64:]
            lextracto[-1]['conceptos'] = ''
        elif line[0:2]=='23': # Registros complementarios de concepto (opcionales y hasta un máximo de 5)
            num_registros += 1
            lextracto[-1]['conceptos'] += line[4:] # Se han unido los dos conceptos line[4:42]+line[42:] en uno
        elif line[0:2]=='24': # Registro complementario de información de equivalencia del importe (opcional y sin valor contable)
            num_registros += 1
            lextracto[-1]['divisa_eq'] = line[4:7]
            lextracto[-1]['importe_eq'] = float(line[7:19]) + (float(line[19:21]) / 100)
        elif line[0:2]=='33': # Registro final de cuenta
            num_registros += 1
            extracto['num_debe'] = int(line[20:25])
            extracto['debe'] = float(line[25:37]) + (float(line[37:39]) / 100)
            extracto['num_haber'] = int(line[39:44])
            extracto['haber'] = float(line[44:56]) + (float(line[56:58]) / 100)
            extracto['saldo_fin'] = float(line[59:71]) + (float(line[71:73]) / 100)
            if line[58:59] == '1': # 1-Deudor 2-Acreedor
                extracto['saldo_fin'] *= -1
        elif line[0:2]=='88': # Registro de fin de archivo
            extracto['num_registros'] = int(line[20:26])
        else:
            raise wizard.except_wizard(_('Error in C43 file'), _('Not valid record type.'))

    #print extracto
    num_debe = num_haber = debe = haber = 0
    for l in lextracto:
        if l['importe'] < 0:
            num_debe += 1
            debe -= l['importe']
        else:
            num_haber += 1
            haber += l['importe']
        #print l
    saldo_fin = extracto['saldo_ini'] + haber - debe

    # Verificaciones archivo C43 correcto
    if num_registros != extracto['num_registros']:
        raise wizard.except_wizard(_('Error in C43 file'), _('Number of records does not agree with the defined in the last record.'))
    if num_debe != extracto['num_debe']:
        raise wizard.except_wizard(_('Error in C43 file'), _('Number of debit records does not agree with the defined in the last record of account.'))
    if num_haber != extracto['num_haber']:
        raise wizard.except_wizard(_('Error in C43 file'), _('Number of credit records does not agree with the defined in the last record of account.'))
    if round(extracto['debe'] - debe, 2) >= 0.01:
        raise wizard.except_wizard(_('Error in C43 file'), _('Debit amount does not agree with the defined in the last record of account.'))
    if round(extracto['haber'] - haber, 2) >= 0.01:
        raise wizard.except_wizard(_('Error in C43 file'), _('Credit amount does not agree with the defined in the last record of account.'))
    if round(extracto['saldo_fin'] - saldo_fin, 2) >= 0.01:
        raise wizard.except_wizard(_('Error in C43 file'), _('Final balance amount = (initial balance + credit - debit) does not agree with the defined in the last record of account.'))

    model_fields_ids = model_fields_obj.search(cursor, user, [
        ('name', 'in', ['property_account_receivable', 'property_account_payable']),
        ('model', '=', 'res.partner'),
        ], context=context)
    property_ids = property_obj.search(cursor, user, [
        ('fields_id', 'in', model_fields_ids),
        ('res_id', '=', False),
        ], context=context)

    account_receivable = False
    account_payable = False
    for property in property_obj.browse(cursor, user, property_ids, context=context):
        if property.fields_id.name == 'property_account_receivable':
            account_receivable = int(property.value.split(',')[1])
        elif property.fields_id.name == 'property_account_payable':
            account_payable = int(property.value.split(',')[1])

    # La búsqueda del partner se hace a partir del CIF/NIF que se encuentra en:
    #   Banc Sabadell: l['referencia1'][:9]
    #   La Caixa: l['conceptos'][:9]
    #   Caja Rural del Jalón: l['conceptos'][21:30]
    # Referencia de la operación que da el partner:
    #   Banc Sabadell: l['referencia2'] o l['conceptos']
    #   Caja Rural del Jalón: l['conceptos']
    for l in lextracto:
        concepto_id = conceptos_obj.search(cursor, user, [('code', '=', l['concepto_c']),], context=context)
        concepto_name = '-'
        concepto_account_id = False
        if concepto_id:
            concepto = conceptos_obj.browse(cursor, user, concepto_id[0], context=context)
            concepto_name = concepto.name
            concepto_account_id = concepto.account_id.id
        l['referencia2'] = l['referencia2'].strip()
        # try to fit as much as usefull information as possible in ref, because it has a limited size.
        # the complete description will always be available in the note field.
        note = l['conceptos'].strip()
        ref = re.sub(' +', ' ', note).strip()
        values = {
            'name': concepto_name,
            'date': l['fecha_opera'],
            'amount': l['importe'],
            'ref': ref,
            'note': note,
            'type': (l['importe'] >= 0 and 'customer') or 'supplier',
            'statement_id': statement_id,
        }

        if l['concepto_c'] in ['05', '06', '07', '08', '09', '10', '11', '12', '13', '15', '16', '17', '98', '99']:
            values['type'] = 'general'
        if l['concepto_c'] in ['03']: # Recibo/Letra domiciliado
            values['type'] = 'supplier'
        if l['concepto_c'] in ['14']: # Devolución/Impagado
            values['type'] = 'customer'

        # 1) Búsqueda en los apuntes no conciliados por referencia
        line_ids = move_line_obj.search(cursor, user, [
            ('ref', '=', values['ref']),
            ('reconcile_id', '=', False),
            ('account_id.type', 'in', ['receivable', 'payable']),
            ],
            #order='date DESC, id DESC', # En OpenERP 5.0 no funciona
            context=context)
        line2reconcile = False
        partner_id = False
        account_id = False
        for line in move_line_obj.browse(cursor, user, line_ids, context=context):
            if line.partner_id.id:
                partner_id = line.partner_id.id
            if l['importe'] >= 0:
                if round(l['importe'] - line.debit, 2) < 0.01:
                    #line2reconcile = line.id
                    account_id = line.account_id.id
                    break
            else:
                if round(line.credit + l['importe'], 2) < 0.01:
                    #line2reconcile = line.id
                    account_id = line.account_id.id
                    break

        # 2) Búsqueda por el CIF/NIF del partner. Nota: A partir OpenERP 5.0 los CIFs tienen un prefijo de 2 letras que indica el país.
        if not partner_id:
            partner_ids = partner_obj.search(cursor, user, [
                ('vat', 'like', '%'+l['referencia1'][:9]),
                ('active', '=', True),
                ], context=context)
            if not partner_ids:
                partner_ids = partner_obj.search(cursor, user, [
                    ('vat', 'like', '%'+l['conceptos'][:9]),
                    ('active', '=', True),
                    ], context=context)
            if not partner_ids:
                partner_ids = partner_obj.search(cursor, user, [
                    ('vat', 'like', '%'+l['conceptos'][21:30]),
                    ('active', '=', True),
                    ], context=context)
            for line in partner_obj.browse(cursor, user, partner_ids, context=context):
                partner_id = line.id
                if values['type'] == 'customer':
                    if line.property_account_receivable:
                        account_id = line.property_account_receivable.id
                        break
                else:
                    if line.property_account_payable:
                        account_id = line.property_account_payable.id
                        break

        # 3) Búsqueda en los apuntes no conciliados por importe
        if not partner_id:
            if l['importe'] >= 0:
                line_ids = move_line_obj.search(cursor, user, [
                    ('debit', '=', '%.2f' % l['importe']),
                    ('reconcile_id', '=', False),
                    ('account_id.type', 'in', ['receivable', 'payable']),
                    ],
                    #order='date ASC, id ASC', # En OpenERP 5.0 no funciona
                    context=context)
            else:
                line_ids = move_line_obj.search(cursor, user, [
                    ('credit', '=', '%.2f' % -l['importe']),
                    ('reconcile_id', '=', False),
                    ('account_id.type', 'in', ['receivable', 'payable']),
                    ],
                    #order='date ASC, id ASC', # En OpenERP 5.0 no funciona
                    context=context)
            if line_ids:
                line = move_line_obj.browse(cursor, user, line_ids, context=context)[0]
                if line.partner_id.id:
                    partner_id = line.partner_id.id
                #line2reconcile = line.id
                account_id = line.account_id.id

        if partner_id:
            domain = [
                ('partner_id', '=', partner_id),
                ('reconcile_id', '=', False),
                ('account_id.type', 'in', ['receivable', 'payable']),
            ]
            if l['importe'] >= 0:
                domain.append( ('debit', '=', '%.2f' % l['importe']) )
            else:
                domain.append( ('credit', '=', '%.2f' % -l['importe']) )
            line_ids = move_line_obj.search(cursor, user, domain, context=context)
            # Solamente crearemos la conciliacion automatica cuando exista un solo apunte
            # que coincida. Si hay mas de uno el usuario tendra que conciliar manualmente y
            # seleccionar cual de ellos es el correcto.
            if len(line_ids) == 1:
                line2reconcile = line.id

        # 4) No hemos encontrado partner: Ponemos valores por defecto para la cuenta
        if not account_id and values['type'] in ['customer','supplier']:
            if values['type'] == 'customer':
                account_id = account_receivable
            else:
                account_id = account_payable
        if not account_id:
            if not concepto_account_id:
                raise wizard.except_wizard(_('Error'), _('A default account has not been defined for the C43 concept ') + l['concepto_c'] )
            else:
                account_id = concepto_account_id

        values['account_id'] = account_id
        values['partner_id'] = partner_id
        # La conciliación de líneas de extractos bancarios creo que es prematuro hacerla en este momento.
        # Es mejor validar manualmente el extracto bancario importado y posteriormente hacer conciliación automatizada.
        if line2reconcile:
            values['reconcile_id'] = statement_reconcile_obj.create(cursor, user, {
                'line_ids': [(6, 0, [line2reconcile])],
            }, context=context)

        if not line2reconcile:

        #print values
        statement_line_obj.create(cursor, user, values, context=context)

    values = {
        'balance_start': extracto['saldo_ini'],
        'balance_end_real': extracto['saldo_fin'],
        'date': extracto['fecha_fin'],
        }
    statement_obj.write(cursor, user, statement_id, values, context=context)

    attachment_obj.create(cursor, user, {
        'name': 'Extracto bancario',
        'datas': file,
        'datas_fname': 'extracto_bancario.txt',
        'res_model': 'account.bank.statement',
        'res_id': statement_id,
        }, context=context)
    return {}


class importar_extracto(wizard.interface):
    states = {
        'init': {
            'actions': [],
            'result': {
                'type': 'form',
                'arch': form,
                'fields': fields,
                'state': [
                    ('end', 'Cancel', 'gtk-cancel'),
                    ('import', 'Import', 'gtk-ok', True),
                ],
            },
        },
        'import': {
            'actions': [],
            'result': {
                'type': 'action',
                'action': _importar,
                'state': 'end',
            },
        },
    }

importar_extracto('l10n_ES_extractos_bancarios.importar')

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
