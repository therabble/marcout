#!/usr/bin/python3

import sys
import os, os.path
import json
import datetime
import hashlib
import copy

import raw_iso2709_converter as iso

# change this to True for ridiculous detail output
debug_output = False


# =============================================================================
#
# ================== ONE FUNCTION TO RULE THEM ALL ============================

def export_records(unified_json_parameter, verbose=False):
    '''
    '''
    retval = ''

    # defaults for parameters and derived content
    marcout_sourcecode = None
    marcout_defn_structure = None
    collection_info = []
    records_to_export = []
    requested_serialization = None

    # the Flask catcher gets the JSON object as an ImmutableMultiDict
    # which looks VERY messed up when serialized... can we just treat it
    # as a JSON object?
    unified_json_obj = unified_json_parameter
    if isinstance(unified_json_parameter, str):
        unified_json_obj = json.loads(unified_json_parameter)


    # should be JSON
    # unified_json_parameter = str(unified_json_parameter)
    
    if verbose:
        retval += 'UNIFIED JSON PARAMETER PARSED SUCCESSFULLY.\n'

    # extract unified content into discrete variables
    marcout_sourcecode = unified_json_obj['marcout_sourcecode']
    records_to_export = unified_json_obj['records']
    collection_info = unified_json_obj['collection_info']
    requested_serialization = unified_json_obj['requested_serialization']

    # print(requested_serialization)

    sz_name = requested_serialization['serialization-name']
    if sz_name not in serializations:
        raise ValueError('Requested serialization `' + sz_name + '` not known.')

    # ------------- PARSE MARCout text ----------------
    # unescape characters escaped for JSON
    marcout_sourcecode = marcout_sourcecode.replace('\\n', '\n')
    marcout_sourcecode = marcout_sourcecode.replace('\\"', '"')

    # cut the text clob into array of lines, and parse
    marcout_lines = marcout_sourcecode.split('\n')
    marcout_structures = parse_marcexport_deflines(marcout_lines)

    # convenience variables for MARCout export definitions
    expdef_functions = marcout_structures['functions']
    expdef_paramnames = marcout_structures['known_parameters']
    expdef_json_extracts = marcout_structures['json_extracted_properties']
    expdef_field_templates = marcout_structures['marc_field_templates']

    # Sanity:
    # (This is a likely mistake when composing unified JSON parameter.)
    # Verify that the collection params specified in MARCout
    # are present in the JSON unified parameter, and vice versa
    marcout_paramnames = set(expdef_paramnames)
    json_paramnames = set(collection_info.keys())
    # Set math: symmetric difference `^` operator will return empty 
    # set if no mismatch between operands:
    all_mismatches = marcout_paramnames ^ json_paramnames

    if all_mismatches:
        errmsg = 'Collection parameter mismatch.'
        marcout_not_in_json = marcout_paramnames - json_paramnames
        json_not_in_marcout = json_paramnames - marcout_paramnames

        if marcout_not_in_json:
            errmsg = '\nCollection params defined in MARCout but not supplied in JSON:'
            errmsg += '\n  ' + ', '.join(marcout_not_in_json)
        if json_not_in_marcout:
            errmsg += '\nCollection params in JSON that are not defined in MARCout:'
            errmsg += '\n  ' + ', '.join(json_not_in_marcout)
        raise ValueError(errmsg)

    # Second:
    # Need to instantiate values for these variable names
    # for param_expr in expdef_paramnames:
    #     assign = param_expr + ' = \'' + collection_info[param_expr] + '\''
    #     if verbose:
    #         retval += 'executing: ' + assign + '\n'
    #     exec(assign)

    if verbose:
        retval += '\n'
        retval += 'MARCout STRUCTURES:\n'
        retval += '\n'

    # ------------- EXPORT RECORDS ---------------------
    if verbose:
        retval += '\n'
        retval += 'HOW MANY RECORDS TO EXPORT? ' + str(len(records_to_export)) + '\n'
        retval += '\n'


    exported_marc_records = []
    for record in records_to_export:
        album_json = record

        # Extract content of JSON record into locally scoped variables.
        # This reconstructs the assignment form in the original 
        # MARCout syntax.
        # These variables will then be referenceable in the
        # MARC field template expressions.

        current_rec_extracts = {}

        for key in expdef_json_extracts:
            # coerce to strings
            varname = str(key)
            varval = str(expdef_json_extracts[key])
            expr = varname + ' = ' + varval
            try:
                exec(expr)
            except Exception as ex:
                msg = 'Failure to execute "' + expr + '":'
                msg += str(ex)
                retval += msg + '\n'

            expr = 'current_rec_extracts[\'' + varname + '\'] = ' + varval
            try:
                exec(expr)
            except Exception as ex:
                msg = 'Failure to execute "' + expr + '":'
                msg += str(ex)
                retval += msg + '\n'

        if verbose:
            retval += '\n'
            retval += 'THESE ARE THE EXTRACTED VARIABLES:\n'
            for key in sorted(expdef_json_extracts.keys()):
                # coerce to strings
                varname = str(key)
            retval += '\n'

        # TODO ensure named functions are in scope.

        # Populate MARC field data structures by copying templates and
        # evaluating from the JSON content
        # and the application of the MARCout functions.

        record_output = []
        # need to use copy.deepcopy to avoid modifying templates: otherwise 
        # content would be propagated forward into a subsequent record, which
        # would blow things up: eval() on values, rather than parsed MARCout
        # expressions, would generally not work. (And in cases where it DID 
        # work, that would be even worse, creating corrupt records.)
        for template in copy.deepcopy(expdef_field_templates):

            # observe export conditionals
            if 'export_if' in template:
                evaluated_conditional = compute_expr(template['export_if'], current_rec_extracts, collection_info)
                if not evaluated_conditional:
                    # fail: this template does not get filled and
                    # placed in the return
                    continue

            if 'export_if_not' in template:
                evaluated_conditional = compute_expr(template['export_if_not'], current_rec_extracts, collection_info)
                # print('evaluates to: ' + str(evaluated_conditional))
                if evaluated_conditional:
                    # fail: the True condition prevents this template from 
                    # being filled and placed in the return
                    continue

            record_output.append(populate_marc_field(template, current_rec_extracts, collection_info))

        exported_marc_records.append(record_output)

        if verbose:   
            retval += '\n'
            retval += '-------------------------------\n'
            for item in exported_marc_records:
                retval += '\n'
                retval += str(item) + '\n'


    # SERIALIZE OUTPUT
    sz_func = serializations[sz_name]

    if verbose:
        retval += 'Serializing as ' + sz_name + '\n'
        retval += '\n'
        retval += '-------------------------------\n\n'

    for marc_record in exported_marc_records:
        serialized_record = sz_func(marc_record)
        # ensure exactly one blank line after record
        serialized_record = serialized_record.rstrip('\n')
        retval += serialized_record + '\n\n'

    return retval


# =============================================================================
#
# ================== CONSTANTS ================================================




# =============================================================================
#
# ================== UTILITY FUNCTIONS ========================================


# =============================================================================
#
# ================== MARCout PARSE FUNCTIONS ==================================




# serialization functions to be called, keyed by serialization_name
serializations = {
    'marc-text': serialize_text,
    'iso2709' : serialize_iso2709,
    'raw': serialize_raw
}

