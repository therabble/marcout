#!/usr/bin/python3

# This module contains necessary functions and content to convert
#  a MARCout export definition source file into a MARCout Export Engine.

import copy

import marcout_common as common


# =============================================================================
#
# ================== CONSTANTS ================================================

# Characters significant for subfield expression parse operations
opaques = {'"': '"', "'": "'"}
nestables = {'(':')', '[':']', '{':'}'}


# less ambiguous substitutes for MARCout reserved phrases
marcout_keyword_replacements = {
    'IS NOT': 'IS_NOT',
    'IS TRUE': 'IS_TRUE',
    'IS FALSE': 'IS_FALSE',
    'HAS VALUE': 'HAS_VALUE',
    'HAS NO VALUE': 'HAS_NO_VALUE',
    'STARTS WITH': 'STARTS_WITH'
}

marcout_rewrites = {

    # - `IS`: operator that compares two sub-expressions for equality.
    #     Equivalent to `==` in Python.
    ' IS ': [' == ', 'replace'],

    # - `IS NOT`: infix operator that compares two sub-expressions for inequality.
    #     Equivalent to `!=` in Python.
    ' IS_NOT ': [' != ', 'replace'],

    # - `IS TRUE`: postfix operator that resolves to True if the preceding
    #     expression is a MARCout values of `TRUE`.
    ' IS_TRUE': ['marcout_is_true', 'postfix'],

    # - `IS FALSE`: postfix operator that resolves to True if the preceding
    #     expression is true, for MARCout values of `FALSE`.
    ' IS_FALSE': ['marcout_is_false', 'postfix'],

    # - `HAS VALUE`: postfix operator that resolves to True if the preceding
    #     expression is PRESENT and not `EMPTY`. In other words, the expression
    #     has meaning over and above the ambiguous empty values.
    ' HAS_VALUE': ['marcout_has_value', 'postfix'],

    # - `HAS NO VALUE`: postfix operator that resolves to True if the preceding
    #     expression is not `PRESENT`, or, if `PRESENT`, is `EMPTY`.
    ' HAS_NO_VALUE': ['marcout_has_no_value', 'postfix'],

    # - `NOTHING`: alias (non-operator) keyword for generation of an empty value.
    #     Depending on context, makes an empty string, or a non-value such as
    #     Python `None` or JSON `null`.
    'NOTHING': ['marcout_nothing_value', 'replace'],

    # - `STARTS WITH`: infix operator for string values. Resolves to True if the
    #     preceding string starts with the subsequent string.
    ' STARTS_WITH ': ['marcout_startswith', 'infix'],

    # - `CONTAINS`: infix operator for string values. Resolves to True if the
    #     preceding string starts with the subsequent string.
    ' CONTAINS ': ['marcout_contains', 'infix']

    # - `+`: the concatenation operator for string values. Does NOT represent
    #     numeric addition, date addition, etc.
}

# ISO 2709 LDR: MARCout constant, 24 chars in length
iso_2709_ldr_template = '00000....a2200000...4500'
iso_2709_ldr_defaults = {'05': 'n', '06': 'j', '07': 'm', '17': '1'}



# =============================================================================
#
# ================== MARCout PARSE FUNCTIONS ==================================


def value_after_first(expr, split_expr):
    '''This function prevents collision between differing usages of
    demarcators (":" in the current implementation.) Returns the portion
    of `expr` AFTER the first occurrence of `split_expr`. If `split_expr`
    does not appear in `expr`, returns `expr` unmodified. In either case,
    the return value is stripped of leading and trailing whitespace.
    '''
    return split_expr.join(expr.split(split_expr)[1:]).strip()


def rewrite_keyword_expr(expr):
    '''This function replaces reserved keyword characters, words, and phrases
    with equivalent expressions in order to create an evaluable expression
    form. Sometimes, as in the case of postfix expressions, it's necessary to
    reorder the parts of the expression. Note that the resulting expression
    cannot, in general, be evaluated until the content of a JSON record is
    available.
    '''
    retval = expr

    # replace token phrases with unified keyword forms
    for keyword in marcout_keyword_replacements:
        retval = retval.replace(keyword, marcout_keyword_replacements[keyword])

    # replace keyword expressions
    for keyword in marcout_rewrites:
        if keyword in retval:
            # the value of marcout_rewrites[keyword] is a list containing
            # [replacement, mode], where `mode` describes how the replacement
            # is applied.
            replacement = marcout_rewrites[keyword][0]
            replacement_mode = marcout_rewrites[keyword][1]

            if replacement_mode == 'replace':
                # the replacement val is a string that directly replaces
                # the keyword
                retval = retval.replace(keyword, replacement)

            elif replacement_mode == 'postfix':
                # the replacement value is a function name with a single
                # argument. The argument is the entire exression, but with the
                # keyword removed)
                retval = replacement + '(' + retval.replace(keyword, '') + ')'

            elif replacement_mode == 'infix':
                # the replacement value is a function name with two arguments:
                # the portion of the expression before the keyword, and the
                # portion of the expression after the keyword.
                portions = retval.split(keyword)
                retval = replacement + '(' + portions[0] + ', ' + portions[1] + ')'

            else:
                raise ValueError('Unknown replacement mode "' + replacement_mode + '".')

    return retval


def render_ldr(ldr_field_def):
    '''Accepts a field dict of the following general type:
    {'tag': 'LDR',
    '17': 'e',
    '19': 'g',
    'terminator': '',
    '05': 'a',
    '06': 'b',
    '07': 'c',
    '18': 'f'}
    returns the 24-character representation with zeroes for run time content,
    spaces for non-valued content.
    '''
    #TODO this is not very efficient, I think...

    retval = iso_2709_ldr_template

    # apply defaults
    for key in iso_2709_ldr_defaults:
        pos = int(key)
        retval = retval[:pos] + iso_2709_ldr_defaults[key] + retval[pos + 1:]

    # apply MARCout override declarations
    for key in ldr_field_def.keys():
        if key.isdigit() and ldr_field_def[key]:
            # this is something to write
            pos = int(key)
            retval = retval[:pos] + ldr_field_def[key] + retval[pos + 1:]

    return retval.replace('.', ' ')


def parse_marcexport_deflines(deflines):
    '''This function turns the marcexport define text content into datastructures.
    It does this by reading the MARCout text line by line in multiple passes
    to accomplish different ends.

    From those blocks, it parses source content for the different
    categories of information. (It ignores "DESCRIPTION", which is
    non-machine-parseable documentation for humans.)

    From the content, it parses a dictionary/map/hash/object of marcexport
    datastructures:
        - 'known_parameters', required parameters
        - 'functions', function names anb brief signature/descriptions
        - 'json_extracted_properties', named expressions for pulling values from a
            JSON instance.
        - 'marc_field_templates', an ordered sequence of data structures listing
            desired fixed values, and album JSON extraction expressions, for MARC
            fields.
            This list of templates thus controls field order, subfield order,
            and instructions for pulling data from the expected JSON instance.

    This marcexport datastructures dictionary/map/hash/object is returned.
    '''

    # FIRST PASS: REMOVE COMMENTS (AND TRAILING NEWLINES)
    contentlines = []
    for line in deflines:
        if line.strip().startswith('#'):
            # it's only a comment line. ignore
            continue
        line = line.replace("\#","[[[ESCAPED_POUND]]]")
        line = line.split('#')[0].rstrip()
        line = line.replace("[[[ESCAPED_POUND]]]","#")
        #note that we PRESERVE empty lines: they are significant
        contentlines.append(line.rstrip())

    # SECOND PASS: PARSE CONTENT INTO NAMED BLOCKS
    defblocks = {}      # dictionary: keys are block titles
    parse_order = []    # list: record order in which blocks were found
    current_blockname = None

    for line in contentlines:
        if line.strip().endswith('--------'):
            # transform block title in MARCout to lowercase with underscore
            line = line.strip()
            current_blockname = line[:line.find('----')]
            current_blockname = current_blockname.lower().replace(' ', '_')
            defblocks[current_blockname] = []
            parse_order.append(current_blockname)

        else:
            if current_blockname:
                defblocks[current_blockname].append(line.strip())

    # now evaluate marcexport define DATASTRUCTURE content as required.
    # do it block by block.
    marcdefs = {}
    marcdefs['parse_order'] = parse_order

    # KNOWN PARAMETERS:
    # what needs to be passed in for some things to work --
    # in codebase, some are environment variables;
    # at command line, they must be explicitly passed.
    paramnames = []
    for line in defblocks['known_parameters']:
        if line.strip():
            paramnames.append(line.strip())

    marcdefs['known_parameters'] = paramnames

    # FUNCTIONS:
    # function names and expressions
    marcdefs['functions'] = {}
    for line in defblocks['functions']:
        line = line.strip()
        if not line:
            continue

        # extract the function name
        funcname = line.split('(')[0]
        marcdefs['functions'][funcname] = line

    # EXTRACTORS:
    # expressions for pulling data out of JSON instances
    marcdefs['json_extracted_properties'] = {}
    for line in defblocks['json_extracted_properties']:
        line = line.strip()
        if not line:
            continue

        parts = line.split('=')
        # someone might put some equals signs in the expr - condition or something
        marcdefs['json_extracted_properties'][parts[0].strip()] = ('='.join(parts[1:])).strip()

    # FIELD TEMPLATES:
    # ordered sequence of templates for MARC fields
    marcdefs['marc_field_templates'] = None

    field_data = [] # list of MARC field data assembled according to definitions
    current_field = None

    # using a while loop to have control over indx for readaheads
    indx = -1
    while indx < len(defblocks['marc_field_templates']) - 1:

        indx += 1
        line = defblocks['marc_field_templates'][indx]

        # indented_line is for processing indents. Otherwise, just strip
        # the line completely.
        indented_line = line.rstrip()
        line = line.strip()

        if line.endswith('----') or line.split('#')[0].rstrip().endswith('----'):
            # just a header
            continue

        if not line:
            # blank line --> field is done
            if current_field:
                # supply default properties
                if 'terminator' not in current_field:
                    current_field['terminator'] = ''
                # data structures need a copy
                field_data.append(copy.copy(current_field))
                current_field = None

        if line.startswith('LDR:'):
            # this is the ISO 2709 LDR, but used for all forms
            current_field = {}
            fieldtag = 'LDR'
            current_field['tag'] = fieldtag

        elif line.startswith('LDR POS:'):
            line = line.split(':')[1].split()

            # safety: make sure there's a home for this without
            # an intervening blank line that erased current_field
            if not current_field:
                current_field = {}
                fieldtag = 'LDR'
                current_field['tag'] = fieldtag

            for segment in line:
                if segment.isdigit():
                    # this is the position tag. Get any declared override value:
                    nextline = defblocks['marc_field_templates'][indx + 1].strip()
                    if nextline.startswith('OVERRIDE:'):
                        value = nextline.split(':')[1].strip()
                    if value:
                        current_field[segment] = value
                    break

        elif line.startswith('FIELD:'):
            # new field
            current_field = {}
            fieldtag = line.split(':')[1].strip()
            current_field['tag'] = fieldtag

        elif line.startswith('EXPORT UNLESS:'):
            expr = ':'.join(line.split(':')[1:])
            # perform initial prep for tokenization
            expr = rewrite_keyword_expr(expr)
            current_field['export_if_not'] = expr

        elif line.startswith('EXPORT WHEN:'):
            expr = ':'.join(line.split(':')[1:])
            # perform initial prep for tokenization
            expr = rewrite_keyword_expr(expr)
            current_field['export_if'] = expr

        elif line.startswith('INDC1:'):
            indc1 = line.split(':')[1].strip()
            if indc1 == 'blank':
                indc1 = ' '
            current_field['indicator_1'] = indc1

        elif line.startswith('INDC2:'):
            indc2 = line.split(':')[1].strip()
            if indc2 == 'blank':
                indc2 = ' '
            current_field['indicator_2'] = indc2

        elif line.startswith('CONTENT:'):
            content = ':'.join(line.split(':')[1:]).strip()
            # perform initial prep for tokenization
            content = rewrite_keyword_expr(content)
            current_field['content'] = content

        elif line.startswith('FOR EACH:'):
            # more complicated
            foreachexpr = line.split(':')[1].split(' in ')
            current_field['foreach'] = {}
            current_field['foreach']['eachitem'] = foreachexpr[0].strip()
            current_field['foreach']['itemsource'] = foreachexpr[1].strip()

        elif line.startswith('EACH-SUBFIELD:'):
            if 'subfields' not in current_field['foreach']:
                current_field['foreach']['subfields'] = []
            eachsub_code = line.split(':')[1].strip()
            eachsub_expr = defblocks['marc_field_templates'][indx + 1].strip()
            # perform initial prep for tokenization
            eachsub_expr = rewrite_keyword_expr(eachsub_expr)
            current_field['foreach']['subfields'].append({eachsub_code: eachsub_expr})

        elif line.startswith('SORT BY:'):
            # we may one day want to support "sort by a, b" expressions...
            # so make this an array, also
            if 'sortby' not in current_field['foreach']:
                current_field['foreach']['sortby'] = []
            sortby_expr = value_after_first(line, ':')
            current_field['foreach']['sortby'].append(sortby_expr)

        # TODO This is DEPRECATED.
        elif line.startswith('DEMARC WITH:'):
            demarc_expr = value_after_first(line, ':')
            current_field['foreach']['demarcator'] = demarc_expr

        elif line.startswith('EACH-PREFIX:'):
            prefix_expr = value_after_first(line, ':')
            current_field['foreach']['prefix'] = prefix_expr

        elif line.startswith('EACH-SUFFIX:'):
            suffix_expr = value_after_first(line, ':')
            current_field['foreach']['suffix'] = suffix_expr

        # "we do not want to grab subfields that are within a" ...
        # ("within a " what? guess I got distracted.) TODO figure this out
        elif line.startswith('SUBFIELD:'):
            if 'subfields' not in current_field:
                current_field['subfields'] = []
            subfield_code = line.split(':')[1].strip()
            subfield_expr = defblocks['marc_field_templates'][indx + 1].strip()
            # perform initial prep for tokenization
            subfield_expr = rewrite_keyword_expr(subfield_expr)
            current_field['subfields'].append({subfield_code: subfield_expr})

        # A "data" output line is CONTENT, SUBFIELDS, or FOREACH.
        # the DEFAULT is "."
        elif line.startswith('TERMINATE DATA WITH:'):
            terminator_expr = value_after_first(line, ':')
            if terminator_expr in ('', 'NONE', 'NOTHING'):
                terminator_expr = None
            current_field['terminator'] = terminator_expr

    # the LDR field needs to be represented as 24 chars. Might as well
    # do it here -- no further changes until len() and offset computations.
    LDR_template = None
    for indx, template in enumerate(field_data):
        if template['tag'] == 'LDR':
            LDR_template = template
            new_ldr_template = {}
            new_ldr_template['tag'] = 'LDR'
            new_ldr_template['fixed'] = render_ldr(LDR_template)
            new_ldr_template['terminator'] = None
            # replace old messy LDR template with new one
            field_data[indx] = new_ldr_template
            break
    # do this as 'fixed' so it won't get evaluated...
    LDR_template['fixed'] = render_ldr(LDR_template)
    LDR_template['terminator'] = None

    # assign all of this to the MARC FIELD TEMPLATES block
    marcdefs['marc_field_templates'] = field_data

    return marcdefs


#
# ================== MARCout EXPRESSION PARSING FUNCTIONS =====================

# In MARC fields, the "tag", "indicator 1", and "indicator 2" values are
# fixed; their values are defined in the MARCout export definition.
#
# Subfield content, on the other hand, often includes values extracted from
# the album JSON

# This is a simplistic stack-based recursive descent parse with implicit
# grammar for subfield expressions in marcexport.define.
# The "delims" structure is a stack which grows as new opening delimiters
# occur, and shrinks as corresponding closing delimiters occur.
#
# In a subfield expression, quoted string literals are opaque objects: it
# doesn't matter what characters they contain, except the occurrence of
# the same quote character that begain the literal.
#
# The other kind of delimiter is the nestable structure token: (, [, {
# that open a nested sequence, and the corresponding ), ], } delimiters.
# As the name suggests, these kinds of delimiters can be meaningfully
# nested
#
# The parse separates the expression into syntactically significant
# character sequences, as noted in the `tokenize` function string.


def closes_delim(delims, char):
    '''Returns True if char closes LAST value in delims'''
    if not delims:
        # Nothing to close
        return False

    # the last character in a delim sequence is looking for its closure
    openchar = delims[-1]

    if openchar in opaques:
        # We are in a string literal. Nothing but the corresponding
        # close quote will have any effect.
        return (char == opaques[openchar])
    if openchar in nestables:
        # We're in a nestable expression
        if char == nestables[openchar]:
            # It's the right one
            return True
        elif char in nestables.values():
            # It's a wrong one. Invalid nesting!
            errmsg = 'BAD SUBFIELD EXPR: closing character `' + char
            errmsg += '` does not match opening character `' + openchar + '`.'
            raise Exception(errmsg)
    else:
        # Neither opaque nor nestable. Fix the tokenize script
        errmsg = 'CODE ERROR: invalid delimiter `' + delims[-1] + '`.'
        errmsg += ' Probably in tokenize function.'
        raise Exception(errmsg)

    return False


def opens_delim(delims, char):
    if not delims:
        # any opening delim will start a block
        return (char in opaques) or (char in nestables)

    if delims[-1] in opaques:
        # We are in a string literal, so no delimiter can open a nested block.
        # This is what "opaque" means. A quoted literal can contain anything;
        # opening delimiters are insignificant.
        return False
    elif delims[-1] in nestables:
        # We're in a nested block. We can open either a string literal
        # or a nested block here.
        return char in opaques or char in nestables
    else:
        # Neither opaque nor nestable. Fix the tokenize script
        errmsg = 'CODE ERROR: invalid delimiter `' + delims[-1] + '`.'
        errmsg += ' Probably in tokenize function.'
        raise Exception(errmsg)


def append_normalized_block(block, blocks):
    '''Strips leading & trailing whitespace; will not append a whitespace-only block.'''
    if block.strip():
        blocks.append(block.strip())


def tokenize(expr):

    '''This function returns the `expr` argument divided into a sequence of
    syntactically significant blocks of characters.

    Block types are:
     - string literals, explicitly quoted (treated as "opaque" to further parsing)
     - opening and closing nestable structure tokens: (, [, {, ), ], }
     - concatenation symbol: + with adjacent whitespace preserved
     - function names, invoked at JSON --> MARC export time
     - extracted property names, resolved at JSON --> MARC export time

    Concatenating the blocks in this return value recreates the `expr`
    parameter. This is a lossless transformation.
    '''
    token_blocks = []     # sequence of blocks
    current_block = ''
    current_delims = []

    for char in expr:

        if closes_delim(current_delims, char):
            # we are matching an earlier opening. If quote, no thing.
            # if nestable... a little more involved.
            if char in opaques.values():
                # append it. Quotes don't get their own block like nestables do
                current_block += char
                append_normalized_block(current_block, token_blocks)

            elif char in nestables.values():
                append_normalized_block(current_block, token_blocks)
                # closing char gets its own block
                token_blocks.append(char)

            # reset
            current_block = ''
            current_delims.pop()

        elif opens_delim(current_delims, char):

            if char in nestables:
                append_normalized_block(current_block, token_blocks)
                # it gets its own block
                token_blocks.append(char)
                # reset
                current_block = ''
                current_delims.append(char)

            elif char in opaques:
                append_normalized_block(current_block, token_blocks)
                # put the char at the start of the new block
                current_block = ''
                current_block += char
                current_delims.append(char)

        elif char == '+':
            # give this a block of its own, but make no delim entry
            # because this is an operator
            append_normalized_block(current_block, token_blocks)
            # normalize whitespace for operator
            token_blocks.append(' + ')
            current_block = ''

        else:
            # non-delim, non-operator: content only:
            # neither opens nor closes
            current_block += char

    # flush accumulated content to return value
    append_normalized_block(current_block, token_blocks)

    return token_blocks



