#!/usr/bin/python3

import marcout_parser as parser
import copy
import hashlib


debug_output = False

# =============================================================================
#
# ================== MARCout EXPRESSION BUILT-IN IMPLEMENTATIONS ===============


# FUNCTIONS IMPLICITLY CALLED WHEN PARSER FINDS KEYWORD

# - `IS`: operator that compares two sub-expressions for equality.
#     Equivalent to `==` in Python or JavaScript. No function: direct
#     substitution in parser.

# `PRESENT`: an expression is `PRESENT` if it can be evaluated.
def marcout_is_present(expr_string):
    try:
        eval(expr_string)
        return True
    except:
        return False

# - `IS TRUE`: postfix operator that resolves to True if the preceding
#     expression is a MARCout distinguished value for `TRUE`.
def marcout_is_true(expr):

    # boolean is ok
    if isinstance(expr, bool):
        return expr

    # test for numeric 1 as distinguished value for `TRUE`
    elif isinstance(expr, int):
        return expr == 1

    elif isinstance(expr, str):
        check_expr = str(expr).lower()
        if check_expr in ('true', 'yes'):
            return True
        else:
            # complex string. evaluate expression
            try:
                expr = eval(expr)
                # if it comes out as a boolean, it was a proper
                # boolean function call
                if isinstance(expr, bool):
                    return expr
                else:
                    # not a boolean function call
                    return False
            except:
                # if it blows up, it's not `PRESENT`
                return False
    else:
        return False


# - `IS FALSE`: postfix operator that resolves to True if the preceding
#     expression is a MARCout distinguished value for `FALSE`

def marcout_is_false(expr):

    # boolean is ok
    if isinstance(expr, bool):
        # reverse the sense
        return not expr

    # test for numeric 0 as distinguished value for `FALSE`
    elif isinstance(expr, int):
        return expr == 0

    elif isinstance(expr, str):
        check_expr = str(expr).lower()
        if check_expr in ('false', 'no'):
            return True
        else:
            # complex string. evaluate expression
            try:
                expr = eval(expr)
                # if it comes out as a boolean, it was a proper
                # boolean function call.
                # reverse the sense
                if isinstance(expr, bool):
                    return notexpr
                else:
                    # not a boolean function call
                    return False
            except:
                # if it blows up, it's not `PRESENT`
                return False
    else:
        return False


# - `HAS VALUE`: postfix operator that resolves to True if the preceding
    # expression is PRESENT and not `EMPTY`. In other words, the expression
    # has meaning over and above the ambiguous empty values.

def marcout_has_value(expr):

    if expr is None:
        return False

    if isinstance(expr, str):
        check_expr = expr.strip()
        # False if `EMPTY`: whitespace or empty string
        if len(check_expr) == 0:
            return False
        else:
            # `expr` might be an evaluable expression
            try:
                expr = eval(expr)
                # recurse with results of evaluation
                return marcout_has_value(expr)
            except:
                # not an evaluable expression. Just a non-empty string
                return True

    elif isinstance(expr, (list, tuple, dict, set)):
        # False if `expr` is a data structure with no content
        # otherwise True
        return len(expr) > 0

    else:
        # other types do not have defined `EMPTY` values
        return True

# - `HAS NO VALUE`: postfix operator that resolves to True if the preceding
#     expression is not `PRESENT`, or, if `PRESENT`, is `EMPTY`.
def marcout_has_no_value(expr_string):

    if expr is None:
        return True

    if isinstance(expr, str):
        check_expr = expr.strip()
        # True if `EMPTY`: whitespace or empty string
        if len(check_expr) == 0:
            return True
        else:
            # `expr` might be an evaluable expression
            try:
                expr = eval(expr)
                # recurse with results of evaluation
                return marcout_has_value(expr)
            except:
                # not an evaluable expression. Just a non-empty string
                return False

    elif isinstance(expr, (list, tuple, dict, set)):
        # True if `expr` is a data structure with no content
        # otherwise False
        return len(expr) == 0

    else:
        # other types do not have defined `EMPTY` values
        return False


# - `NOTHING`: keyword for an empty value. Depending on context, equivalent
#     to an empty string, or to a non-value such as Python `None` or
#     JSON `null`.

def marcout_nothing_value(type):
    if type in (str, unicode):
        return ''
    else:
        return None

# - `STARTS WITH`: operator for string values. Resolves to True if the
#     preceding string starts with the subsequent string.
def marcout_startswith(tested_expr, start_expr):
    return tested_expr.startswith(start_expr)

# - `CONTAINS`: operator for string values. Resolves to True if the
#     preceding string starts with the subsequent string
def marcout_contains(tested_expr, search_expr):
    return (search_expr in tested_expr)

# No function necessary: parser leaves in place.
# - `+`: the concatenation operator for string values. Does NOT represent
#     numeric addition.

# =============================================================================
#
# ================== EXPRESSION FUNCTIONS CALLABLE IN MARCEXPORT.DEFINE =======

# And their helper functions


def normalize_date(dateval):
    if not dateval:
        return ''
    dateval = str(dateval)
    dateval = dateval.split('T')[0]
    return dateval


def biblio_name(person_name):
    if ',' not in person_name:
        name_segments = person_name.split()     # split on spaces
        if len(name_segments) > 1:
            person_name = ', '.join([name_segments[-1], ' '.join(name_segments[:-1])])
    return person_name


def release_year(release_date):
    return str(release_date).split('-')[0]


def release_decade(release_date):
    decade_string = release_date.split("-")[0][0:3]    # first 3 chars of year
    decade_number = int(decade_string)
    decade_literal = str(decade_number) + "1-" + str(decade_number + 1) + "0";
    return decade_literal



def pretty_comma_list(listexpr, oxford=False):
    '''Accepts a comma separated list in string form, and a boolean
    that, if set to True, will stipulate use of the Oxford comma.
    Returns the list with leading and trailing whitespace stripped from
    list items, separated by commas, with " and " inserted in lieu of
    the final separator.'''

    last_sep = ' and '
    if oxford:
        last_sep = ', and '

    # Python 3: changed `unicode.strip` to `str.strip`
    listexpr = map(str.strip, listexpr.split(','))
    # Python 3: `map` returns an iterator not a list. Convert.
    listexpr = list(listexpr)
    if len(listexpr) == 1:
        return listexpr[0]

    return ', '.join(listexpr[:-1]) + last_sep + listexpr[-1]


def zeropad(chars, length):
    retval = '0' * length
    # print('zeropad retval: ' + retval)
    retval = retval + chars
    # print('zeropad retval: ' + retval)
    return retval[-length:]


def h_m_s(duration_in_float_seconds):
    '''This function takes a high-precision number in seconds
    (e.g. 364.61401360544215) and returns an h:m:s value
    '''
    hours = 0
    minutes = 0
    seconds = 0

    seconds = int(round(duration_in_float_seconds))
    # print('raw integer seconds: ' + str(seconds))

    hours = seconds // 3600
    if hours:
        seconds -= hours * 3600

    minutes = seconds // 60
    if minutes:
        seconds -= minutes * 60

    retval = ':' + zeropad(str(seconds), 2)
    if minutes:
        if hours:
            retval = ':' + zeropad(str(minutes), 2) + retval
        else:
            retval = str(minutes) + retval
    if hours:
        retval = str(hours) + ':' + retval

    return retval


def render_duration(duration_in_float_seconds):
    '''Wrapper function that coerces representation to float
    (because JSON might wrap value in quotes) and rounds it to
    standard hours, minutes, seconds representation.
    '''
    return '(' + h_m_s(duration_in_float_seconds) + ')'


def total_play_length(tracks):
    float_seconds = 0.0
    for track in tracks:
        try:
            float_seconds += track['duration']
        except:
            print('=========================================== ERROR:')
            print(track)
    return h_m_s(float_seconds)

def compute_control_number(album_id, collection_abbr):
    # Generation procedure:
    #  - obtain SHA1 hash of the album slug [here "album_id"]
    #  - take the last 7 digits of the hex digest
    #  - append 'a' as a collision shock absorber (intent is to go through
    #     the alphabet and then use single digits as necessary.)
    #  - prepend 3-character library collection code, demarcated with "_"
    #     Note that the collection code must be lower case, e.g. 'ccr', 'nbb', 'spb'
    # Javascript from musicat-api/utilities:
    # var album_slug_shasum = crypto.createHash("sha1");
    # album_slug_shasum.update(album_slug);
    # album_slug_shasum.id = album_slug_shasum.digest("hex");
    # last_seven_indx = album_slug_shasum.id.length - 7;
    # last_seven_chars = album_slug_shasum.id.slice(last_seven_indx);
    # control_number = collection_code + '_' + last_seven_chars + 'a';

    # sha1 of album_id
    # Python 3 specific: since album_id is unicode, it needs to be encoded
    # to bytes
    album_id = album_id.encode('utf-8')
    sha = hashlib.sha1(album_id).hexdigest()
    # put it all together
    control_number = collection_abbr.lower() + '_' + sha[-7:] + 'a'

    return control_number


def map_target2_audience(target_audience,explicit):
    #The 23rd value in the 008 field: e - Adult, j - Juvenile
    #MUSICat album json intendedAudienceOptions are "adult", "juvenile"
    mapped_audience_result = '\\'
    if target_audience == 'juvenile':
      mapped_audience_result = 'j'
    if explicit == True:
      mapped_audience_result = 'e'
    return mapped_audience_result


def yymmdd_date(date):
    #the 008 field starts with an immutable date the record was first created on
    #expects a normalized date.
    yymmdd_date = '\\\\\\\\\\\\'
    if date:
      yy_string = date.split("-")[0][2:4]    # last 2 chars of year
      mm_string = date.split("-")[1]   # 2 digit month
      dd_string = date.split("-")[2]   # 2 digit day
      yymmdd_date = yy_string + mm_string + dd_string    #when you know what you are getting, make a yymmdd date from date passed
    return yymmdd_date



def map_capture2_technique(capture_technique):
    #The last value in the 007 field: e = analog, d = digital, u = unknown
    #MUSICat album json captureTechniqueOptions are "analog", "digital"
    mapped_capture_result = 'u'
    if capture_technique == 'analog':
      mapped_capture_result = 'a'
    if capture_technique == 'digital':
      mapped_capture_result = 'd'
    return mapped_capture_result


def foo(bar):
    baz = bar
    return baz;


# =============================================================================



# =============================================================================
#
# ================== CORE FUNCTIONS FOR EXPORTING MARC RECORDS ================


def compute_extracts(extract_block, jsonobj):
    # print('COMPUTING EXTRACTS.')
    # print(extract_block)
    # print
    retval = {}
    album_json = jsonobj
    for propname in extract_block:
        if not propname:
            # empty key got in. gotta fix the parse
            continue
        # print(propname + ':')
        # print(extract_block[propname])
        extracted_val = eval(extract_block[propname])
        # print(extracted_val)
        retval[propname] = extracted_val
    return retval



def rewrite_for_context(marcout_expr, context_expr, context_varname):
    '''Translates context-identifying MARCout expression into an evaluable form.
    Parameters: `marcout_expr` is the MARCout expression.
    `context_expr` is the MARCout identifier for the context.
    `context_varname` is the evaluable variable reference for the context.

    EXAMPLE from FOREACH block:
    marcout_expr: 'render_duration(track::duration)'
    context_expr: 'track::'
    context_varname: 'current_item'
    return value: "render_duration(current_item['duration'])"
    '''
    tokens = parser.tokenize(marcout_expr)
    for indx, token in enumerate(tokens):
        if token.startswith(context_expr):
            # change from MARCout notation to dict notation
            tokens[indx] = token.replace(context_expr, context_varname + '[\'') + '\']'
        # print(token)
    return ''.join(tokens)


def evaluate_foreach(foreach_def_block, current_rec_extracts, collection_info):
    '''This function analyzes, sorts, and computes MARC subfield content
    that is defined in a MARCout FOREACH block.
    It returns each subfield's content, properly rendered, with declared
    demarcators(prefix, suffix) in a List,
    ordered according to the SORTBY property of the foreach block.
    '''
    retval = []

    if debug_output:
        print('CURRENT REC EXTRACTS:')
        print(current_rec_extracts)
        print()
        print('FOREACH DEF BLOCK:')
        print(foreach_def_block)
        print()

    # local variables for notational simplicity:
    itemsource_key = foreach_def_block['itemsource']
    itemsource = current_rec_extracts[itemsource_key]
    eachitem_name = foreach_def_block['eachitem']
    eachitem_expr = eachitem_name + '::'

    # DEMARCATORS
    # if you do not eval() a string literal expression, it will
    # retain any accumulated enclosing quotes.
    #demarc = eval(demarc)
    prefix = None
    if 'prefix' in foreach_def_block:
        prefix = foreach_def_block['prefix']
        if prefix:
            prefix = eval(prefix)
    suffix = None
    if 'suffix' in foreach_def_block:
        suffix = foreach_def_block['suffix']
        if suffix:
            suffix = eval(suffix)
    # deprecated! Will treat as 'suffix'
    demarc = None
    if 'demarcator' in foreach_def_block:
        demarc = foreach_def_block['demarcator']
        if demarc:
            demarc = eval(demarc)

    # NOTES ABOUT SORTING:

    # 1) This sort sorts the GROUPS (e.g. all tracks in an album) and
    # does not touch the subfield ordering WITHIN a group. The internal
    # subfield ordering is established in the MARCout declaration.

    # 2) The sort key is evaluated by evaluating the group-level SORT BY
    # in the MARCout declaration.

    sortkeys = foreach_def_block['sortby']
    # TODO: deal with sortby for cascade if more than one sort key in this list
    sortkey = sortkeys[0].lstrip(eachitem_expr)
    subfield_defs = foreach_def_block['subfields']

    # sort the list being iterated
    # TODO: make a better sort function for cascading sort
    itemsource.sort(key=lambda x: x[sortkey])

    # append rendered and demarcated subfields to retval
    for eachitem in itemsource:

        rendered_subfields = []

        # this respects subfield definition order
        for subfield_def in subfield_defs:

            # a subfield_def is a dict of form
            # {subfield_code: evaluable expression}
            for subcode in subfield_def.keys():
                if subcode.startswith('group_'):
                    # this doesn't get processed here. It's group level.
                    pass

                # now with genuine subfields...
                subfield_expr = subfield_def[subcode]

                # print('  ' + subcode + ': ' + subfield_expr)

                subfield_expr = rewrite_for_context(subfield_expr, eachitem_expr, 'eachitem')
                # print('  ' + subcode + ': ' + subfield_expr)
                # print('  ' + subcode + ': ' + eval(subfield_expr))
                eval_expr = eval(subfield_expr)
                rendered_subfields.append({subcode: eval_expr})

        # demarcators applied at group level in rendered_subfields
        if prefix:
            rendered_subfields.insert(0, {'group_prefix': prefix})
        if suffix:
            rendered_subfields.append({'group_suffix': suffix})
        if demarc:
            rendered_subfields.append({'group_demarc': demarc})

        retval.append(rendered_subfields)

    return retval


def compute_expr(expr, current_rec_extracts, collection_info):
    retval = expr

    # this is a parse
    tokens = parser.tokenize(expr)
    for indx, token in enumerate(tokens):
        if debug_output:
            print('TOKEN: ' + token)
        if token[0] in parser.opaques:
            # this is a string literal. Don't mess with it.
            continue

        # For code expressions:

        # record-specific values
        # replace reference to extract name with actual value extracted from JSON.
        # ensure that the result is quotes as a literal.
        for extract in current_rec_extracts:
            if extract in token:
                if debug_output:
                    print('EXTRACT: ' + str(extract))

                extractval = current_rec_extracts[extract]

                if debug_output:
                    print('EXTRACTVAL: ' + str(extractval))
                    print('IS STR: ' + str(isinstance(extractval, str)))
                if isinstance(extractval, str):
                    # direct substitution WITH enclosing "" so it evals as a
                    # string literal on the way out of this function
                    token = token.replace(extract, '"' + extractval + '"')
                else:
                    token = token.replace(extract, str(extractval))
                if debug_output:
                    print('TOKEN: ' + token)

        # collection-specific parametric values
        for param in collection_info.keys():
            if param in token:
                if debug_output:
                    print('PARAM: ' + param)
                paramval = collection_info[param]
                if isinstance(paramval, str):
                    # direct substitution WITH enclosing "" so it evals as a
                    # string literal on the way out of this function
                    token = token.replace(param, '"' + paramval + '"')
                else:
                    token = token.replace(extract, str(extractval))
                if debug_output:
                    print('TOKEN: ' + token)

        # whatever modifications have been made to token, update the tokens list

        if str(token) == 'None':
            token = '"' + str(token) + '"'

        tokens[indx] = str(token)

    # concat tokens into content
    evaluable = ''.join(tokens)

    retval = ''

    # this second-stage eval applies functions, concats, etc
    if evaluable:
        try:
            if debug_output:
                print('EVALUATING "' + evaluable + '"')
            retval = eval(evaluable)
            if debug_output:
                print('EVALUATED TO: ' + str(retval))
        except Exception as ex:
            if verbose:
                print('tokens: ')
                print(tokens)
                print('DIED ON ' + evaluable)

    return retval


def export_marc_field(template, current_rec_extracts, collection_info):
    '''This function returns a copy of the template, with record-specific
    values computed in place of the various expressions.
    '''

    # redundant use of deepcopy: belt, suspenders, 2 condoms & a bike helmet.
    retval = copy.deepcopy(template)

    for propname in retval:

        if propname in ('tag', 'indicator_1', 'indicator_2', 'fixed'):

            # do not evaluate. These are fixed, not computed.
            continue

        elif propname in ('content',):
            retval[propname] = compute_expr(retval[propname], current_rec_extracts, collection_info)

        elif propname == 'subfields':
            # "subfields" is a list to preserve order in which subfields
            # are defined. Each list item is a dict. Each dict is of the form
            # {subfield_code: expr} and has len() == 1
            for subfield_dict in retval[propname]:
                for subfield_code in subfield_dict:

                    subfield_dict[subfield_code] = compute_expr(subfield_dict[subfield_code], current_rec_extracts, collection_info)

        elif propname == 'foreach':
            # this is a dict. Keys are
            # 'demarcator': literal,
            # 'itemsource': expr,
            # 'sortby': array of exprs, e.g. ['track::position'],
            # 'subfields': array of subfield dicts, e.g. [{'t': 'track::title'}, {'g': 'render_duration(track::duration)'}],
            # 'eachitem': name assigned for notation. e.g. 'track',
            retval[propname] = evaluate_foreach(retval[propname], current_rec_extracts, collection_info)

        elif propname in('export_if', 'export_if_not'):
            # conditional
            retval[propname] = compute_expr(retval[propname], current_rec_extracts, collection_info)

    return retval


def export_records_per_marcdef(export_workset, verbose):
    '''The parameter is an Export Workset. This is a dict containing all
    necessary information to export the records it contains:
    {
        'marcout_engine': marcout_engine parsed from MARCout export definition document
        'serialization': sz_name : valid serialization name from unified JSON
        'collection_info': collection info from unified JSON
        'records_to_export': expected JSON representation of records
    }
    RETURNS a List of exported records
    '''

    if verbose:
        print()
        print('=============================================')
        print('SERIALIZER INPUT: EXPORT_WORKSET')
        print(export_workset)
        print('=============================================')
        print()


    # return value
    exported_marc_records = []

    # convenience variable
    engine_json_extractors = export_workset['marcout_engine']['json_extracted_properties']
    engine_field_templates = export_workset['marcout_engine']['marc_field_templates']
    collection_info = export_workset['collection_info']

    for record in export_workset['records_to_export']:

        # expected name, per MARCout convention
        album_json = record

        # Extract content of JSON record into locally scoped variables.
        # This reconstructs the assignment form in the original
        # MARCout syntax.
        # These variables will then be referenceable in the
        # MARC field template expressions.

        # a convenient parametric form for passing around extracted values.
        current_rec_extracts = {}

        # Execute these extraction statements in context of the record.
        # Stash values in current_rec_extracts.
        for key in engine_json_extractors:
            # coerce to strings
            varname = str(key)
            varval_expr = str(engine_json_extractors[key])

            if verbose:
                indent = ' ' * 2
                print(indent + 'resolving `' + varname + ': ' + varval_expr)

            # apply any defaults left embedded by parser
            default = ''
            if '::DEFAULT' in varval_expr:
                varval_expr, default = varval_expr.split('::DEFAULT')
                varval_expr = varval_expr.rstrip()
                default = default.strip()

            try:
                varval = eval(varval_expr)
            except Exception as e:
                if verbose:
                    indent = ' ' * 4
                    print(indent + 'ATTEMPTING TO RESOLVE `' + varval_expr + '`')
                    print(indent + 'EVAL EXCEPTION of type "' + str(type(e)) + '":')
                    print(e)
                    print(indent + indent + 'APPLYING DEFAULT `' + default + '`')
                    print()
                varval = default

            # add evaluation of varval to current_rec_extracts
            if verbose:
                indent = ' ' * 2
                print(indent + 'adding `' + str(varval) + '` to current_rec_extracts')
            current_rec_extracts[varname] = varval


        # TODO ensure named functions are also in scope.


        # Populate MARC field data structures by copying templates and
        # evaluating from the JSON content
        # and the application of the MARCout functions.

        record_output = []
        # need to use copy.deepcopy to avoid modifying templates: otherwise
        # content would be propagated forward into a subsequent record, which
        # would blow things up: eval() on *values*, rather than parsed MARCout
        # expressions, would generally not work. (And in cases where it DID
        # work, that would be even worse, creating corrupt records.)
        for template in copy.deepcopy(engine_field_templates):

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

            exported_field = export_marc_field(template, current_rec_extracts, collection_info)
            if verbose:
                indent = ' ' * 2
                print(indent + 'EXPORTING ' + template['tag'])

            record_output.append(exported_field)

        # put all of the fields for this record in the return val
        exported_marc_records.append(record_output)


    if verbose:
        print()
        print('=============================================')
        print('SERIALIZER OUTPUT: EXPORTED_MARC_RECORDS:')
        print(exported_marc_records)
        print('=============================================')
        print()


    return exported_marc_records
