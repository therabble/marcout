#!/usr/bin/python

#functions

def unescape_marcout(marcout_sourcecode):
    retval = marcout_sourcecode.replace('\\n', '\n')
    retval = retval.replace('\\"', '"')
    retval = retval.replace('\\t', '\t')
    return retval


def escape_marcout(marcout_sourcecode):
    retval = marcout_sourcecode.replace('\n', '\\n')
    retval = retval.replace('"', '\\"')
    retval = retval.replace('\t', '\\t')
    return retval


def unescape_json(json_text):
    retval = json_text.replace('\\n', '\n')
    retval = retval.replace('\\"', '"')
    retval = retval.replace("\\'", "'")
    retval = retval.replace('\\t', '\t')
    return retval


def escape_json(json_text):
    retval = json_text.replace('\n', '\\n')
    retval = retval.replace('"', '\\"')
    retval = retval.replace("'", "\\'")
    retval = retval.replace('\t', '\\t')
    return retval


# constants

usage = '''USAGE: 

    escape_unescape.py <sourcefilepath> --escape-json | --unescape-json [--verbose] [--help]

'''

import sys
import os.path

if '--help' in sys.argv:
    print(usage)
    exit(0)

call_options = [arg for arg in sys.argv[1:] if arg.startswith('-')]
call_params = [arg for arg in sys.argv[1:] if not arg.startswith('-')]

verbose = '--verbose' in call_options

sourcefilepath = call_params[0]
sourcefile = open(sourcefilepath)
sourcecontent = sourcefile.read()
sourcefile.close()

# doing what?

if '--escape-json' in call_options:
    print(escape_json(sourcecontent))

elif '--unescape-json' in call_options:
    print(unescape_json(sourcecontent))

else:
    print('unknown action.')

