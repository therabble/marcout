#!/usr/bin/python3

import marcout_common as common
import marcout_parser as parser
import marcout_exporter as exporter
import marcout_serializer as serializer

import json


# =============================================================================
#
# ================== CONSTANTS ================================================






# =============================================================================
#
# ================== FUNCTIONS ================================================


def parse_unified_json(param, verbose=False):

    # the Flask catcher gets the JSON object as an ImmutableMultiDict
    # which looks VERY messed up when serialized... can we just treat it

    # logic: assume it's already a parsed JSON object
    jsonobj = param
    errors = []

    if isinstance(param, (str, bytes,)):
        # param might be a filepath, or raw content
        jsontext = common.get_param_content(param)

        if jsontext:

            # parse content
            if verbose:
                print('JSON text content:')
                print(common.truncate_msg(jsontext, 120))

            try:
                jsonobj = json.loads(jsonobj)
                if verbose:
                    print('...successfully parsed JSON content.')
            except Exception as e:
                # parse died --> no good
                print('JSON parse failed.')
                print(e)
        else:
            # we struck out
            if verbose:
                print('No JSON Content found.')
            jsonobj = None

    return jsonobj


def resolve_unified_json(unified_jsonobj, verbose=False):
    '''This function accepts a parsed JSON object, interprets it,
    and returns a dictionary containing four items:
        - the MARCout Engine parsed from "marcout_sourcecode";
        - the requested serialization, by name;
        - the collection info;
        - the list of records to be exported.
    Obvious missing, wrong, or inconsistent elements raise a ValueError.
    '''
    retval = {}

    # defaults for parameter content
    marcout_sourcecode = None
    requested_serialization = None
    collection_info = []
    records_to_export = []

    marcout_structures = {}
    sz_name = None


    # extract unified content into discrete variables
    errors = []
    json_contentnames = ('marcout_sourcecode', 'requested_serialization',
        'collection_info', 'records',)

    for contentname in json_contentnames:
        if not contentname in unified_jsonobj:
            errors.append('Missing "' + contentname + '" in Unified JSON.')
    if errors:
        raise ValueError('\n'.join(errors) + '\n')

    # populate convenience variables
    marcout_sourcecode = unified_jsonobj['marcout_sourcecode']
    requested_serialization = unified_jsonobj['requested_serialization']
    collection_info = unified_jsonobj['collection_info']
    records_to_export = unified_jsonobj['records']

    # there might be other info in the serialization request,
    # but the name MUST be present.
    sz_name = requested_serialization['serialization-name']
    # does the serializer know about this?
    if sz_name not in serializer.serializations:
        raise ValueError('Requested serialization `' + sz_name + '` not known.')

    # ------------- PARSE MARCout text ----------------
    # unescape characters escaped for JSON
    marcout_sourcecode = marcout_sourcecode.replace('\\n', '\n')
    marcout_sourcecode = marcout_sourcecode.replace('\\"', '"')

    # one of the returned values. The MARCout Engine is a set of
    # statements to govern selection, content, and formatting for
    # exported MARC record fields.

    # Parser is line-oriented. Cut the text clob into array of lines,
    # and parse
    marcout_lines = marcout_sourcecode.split('\n')
    marcout_engine = parser.parse_marcexport_deflines(marcout_lines)

    # Sanity:
    # (This is a likely mistake when composing unified JSON parameter.)
    # Verify that the collection params specified in MARCout
    # are present in the JSON unified parameter, and vice versa
    marcout_paramnames = set(marcout_engine['known_parameters'])
    json_paramnames = set(collection_info.keys())
    # Using set math: symmetric difference `^` operator will return empty
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

    # We're still here, so the JSON was broadly OK: Not validated,
    # but at least claims to have the right content.
    # This is the Export Workset datastructure.
    retval = {'marcout_engine': marcout_engine,
        'serialization': sz_name,
        'collection_info': collection_info,
        'records_to_export': records_to_export,
    }

    return retval


def export_records(unified_jsonobj, as_string=False, verbose=False):

    unified_jsonobj = parse_unified_json(unified_jsonobj, verbose)

    # turn the JSON into the Export Workset, with parsed MARCout Engine,
    # records in the anticipated JSON form, and export directives &
    # collection-specific metadata.
    export_workset = resolve_unified_json(unified_jsonobj, verbose)

    # The Export Workset, without external data dependencies, contains sufficient
    # information to generate a list of exported record datastructures.
    export_list = exporter.export_records_per_marcdef(export_workset, verbose)

    # apply requested serialization
    sz_name = export_workset['serialization']
    export_list = serializer.serialize_records(export_list, sz_name, verbose)

    if as_string:
        export_list = ''.join(export_list)

    return export_list


