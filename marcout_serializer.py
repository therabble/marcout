#!/usr/bin/python3

import marcout_iso2709 as iso


# =============================================================================
#
# ================== SERIALIZATION FUNCTIONS ==================================


def serialize_text(marc_record_fields, verbose):

    if verbose:
        print()
        print('==================================================')
        print('SERIALIZING:')
        print(marc_record_fields)
        print('==================================================')
        print()

    retval = ''

    for field in marc_record_fields:
        retval += '='
        retval += field['tag']
        retval += '  '
        for indcname in ('indicator_1', 'indicator_2'):
            # when there's no indicator at all, we represent in text as a single space
            indc_val = ' ' 
            if indcname in field:
                indc_val = field[indcname]
                if not indc_val.strip():
                    # the indicator is a space, which is represented as "\".
                    # We need to escape the backslash character by doubling it.
                    indc_val = '\\'
            retval += indc_val

        if 'fixed' in field:
            retval += field['fixed']

        if 'content' in field:
            retval += field['content']

        # foreach will be a list of subfields, in order, with optional preceding
        # or subsequent delimiters
        elif 'foreach' in field:
            for group_item in field['foreach']:
                # group_item is a list of dicts
                for sub_item in group_item:
                    # sub_item dict should only ever have one key & 
                    # one associated value.
                    key = list(sub_item.keys())[0]
                    if key.startswith('group_'):
                        # it's a group marker, not a data field. 
                        # Just append the value.
                        retval += sub_item[key]
                    else:
                        # it's a subfield
                        retval += '$'
                        subfield_code = key
                        subfield_val = sub_item[subfield_code]
                        retval += subfield_code
                        retval += subfield_val

        elif 'subfields' in field:
            for subfield in field['subfields']:
                retval += '$'
                # subfield dict should only ever have one key & 
                # one associated value.
                subfield_code = list(subfield.keys())[0]
                subfield_val = str(subfield[subfield_code])
                retval += subfield_code
                retval += subfield_val
        if 'terminator' in field:
            if field['terminator']:
                retval += field['terminator']
        retval += '\n'

    return retval

def serialize_iso2709(marc_record_fields, verbose):

    retval = ''

    retval = iso.raw_record_2_iso(marc_record_fields)


    return retval


def serialize_raw(marc_record_fields, verbose):
    '''Returns serialized data structures in Python/Javascript evaluable form.
    '''
    return str(marc_record_fields)


def serialize_xml(marc_record_fields, verbose):
    '''Returns MARCXML representation
    '''
    raise Exception('serialize_xml not yet implemented.')


def serialize_records(marc_record_list, sz_name, verbose=False):
    '''Accepts a list of MARCout records in raw data form and applies
    requested serialization to each.
    '''
    retval = []
    for marc_record in marc_record_list:
        retval.append(serializations[sz_name](marc_record, verbose))

    return retval


# =============================================================================
#
# ================== CONSTANTS ================================================



# serialization functions to be called, keyed by serialization_name
serializations = {
    'marc-text': serialize_text,
    'iso2709' : serialize_iso2709,
    'raw-datastructure': serialize_raw,
    'marc-xml': serialize_xml,
}

