#!/usr/bin/python

import os.path
import errno


# =============================================================================
#
# ================== CONSTANTS ================================================




# =============================================================================
#
# ================== FUNCTIONS ================================================

def get_param_content(param):
    '''This function accepts a string that is either a filepath or raw content.
    If it is the form of a filepath, this attempts to read and return that
    content; otherwise it treats the param as literal content.
    OSErrors, EXCEPT the obvious discriminator errno.ENAMETOOLONG which is taken
    to mean a raw file,
    '''
    content = None
    filepath = None
    contentfile = None

    # distinguish between filepath and raw content
    if os.path.isfile(param):
        filepath = param

        with open(filepath, 'r') as contentfile:
            content = contentfile.read()
    else:
        content = param

    return content


def truncate_msg(message, length):
    retval = message
    if retval and (len(retval) > length):
        retval = retval[:length] + '...'
    return retval


def prettyblock(structure, indentlevel=0):
    '''Returns a pretty-formatted string representation of a simple
    (not very nested or complicated) datastructure.
    '''
    retval = []
    indent = '  ' * indentlevel

    if isinstance(structure, (list, tuple)):
        for item in structure:
            line = indent + str(item)
            retval.append(line.rstrip())

    elif isinstance(structure, dict):
        for key in sorted(list(structure.keys())):
            line = indent + key + ': ' + str(structure[key])
            retval.append(line.rstrip())

    elif isinstance(structure, set):
        for item in sorted(list(structure)):
            line = indent + str(item)
            retval.append(line.rstrip())

    else:
        retval.append(indent + str(structure).rstrip())

    return '\n'.join(retval) + '\n'


def pretty_marc_field(marc_field, indentlevel=0):
    '''Returns a pretty-formatted string representation
    of a MARC field template or populated field
    '''
    retval = []
    indent = ' ' * indentlevel

    for key in ('tag', 'fixed', 'content', 'indicator_1', 'indicator_2'):
        if key in marc_field:
            line = indent + key + ': ' + str(marc_field[key])
            retval.append(line.rstrip())

    if 'subfields' in marc_field:
        line = indent + 'subfields:'
        retval.append(line)
        for subfield in marc_field['subfields']:
            line = (indent + '  ' + str(subfield))
            retval.append(line)

    if 'foreach' in marc_field:
        line = indent + 'foreach:'
        retval.append(line)
        for item in ('itemsource', 'eachitem', 'prefix'):
            if item in marc_field['foreach']:
                line = (indent + '  ' + item + ': ' + str(marc_field['foreach'][item]))
                retval.append(line)

        if 'subfields' in marc_field['foreach']:
            line = indent + '  ' + 'subfields:'
            retval.append(line)
            for subfield in marc_field['foreach']['subfields']:
                line = (indent + '    ' + str(subfield))
                retval.append(line)

        for item in ('suffix', 'sortby'):
            if item in marc_field['foreach']:
                line = (indent + '  ' + item + ': ' + str(marc_field['foreach'][item]))
                retval.append(line)

    if 'terminator' in marc_field:
        line = indent + 'terminator: ' + str(marc_field['terminator'])
        retval.append(line)

    return '\n'.join(retval) + '\n'


#only called if verbose
def prettyprint_marcout_engine(engine):
    print_order = engine['parse_order']
    for blockname in print_order:
        if blockname in engine:
            print(blockname)
            if blockname == 'marc_field_templates':
                for marc_field in engine['marc_field_templates']:
                    print(pretty_marc_field(marc_field, 1))
            else:
                print(prettyblock(engine[blockname], 1))
            print()



