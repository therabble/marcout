#!/usr/bin/python3



# =============================================================================
#
# ================== MARC21 ISO 2709 CONSTANTS ================================


field_delimiter = chr(0x1E)
subfield_delimiter = chr(0x1F)
record_terminator = chr(0x1D)

dir_entry_size = 12



# =============================================================================
#
# ================== FUNCTIONS: ISO 2709 TO RAW DATASTRUCTURE =================


def entries_in_iso_directory(directory_string):
    '''returns the list of 12-character substrings if:
    all characters are digits;
    there are at least 12 characters;
    and the length of
    the string is evenly divisible by 12 (because a directory entry
    is exactly 12 characters long).
    Otherwise raises a ValueError.
    '''

    print('DIRECTORY STRING:')
    print(directory_string)
    print()
    print()

    if not len(directory_string) >= dir_entry_size:
        raise ValueError('Directory string parameter requires a minimum of '
            + str(dir_entry_size) + 'chars.')
    if not directory_string.isdigit():
        raise ValueError('Directory string parameter contains non-numeric characters.')
    if len(directory_string) % 12:
        raise ValueError('Directory string parameter length is not an integer multiple of 12.')

    # get the right 12-char string from the right starting pos
    # (list comprehension on a dir_entry_size (== 12) range,
    # with slicing syntax applied to directory_string)
    return [ directory_string[i:i+dir_entry_size] for i in range(0, len(directory_string), dir_entry_size) ]


def read_iso_field_content(dir_entry, fields_text):
    '''Accepts a single directory entry and the content text
    that the directory indexes. Returns a tuple:
    - the field's tag (embedded in the dir_entry), and
    - the content to which the directory points.

    Raises ValueError if dir_entry is not a 12-character string.
    Raises ValueError if dir_entry points beyond end of fields_text.
    Raises ValueError if the content does not begin with a field delimiter.
    '''
    if len(dir_entry) != dir_entry_size:
        raise ValueError('The dir_entry param "' + dir_entry + '" is not 12 characters long.')

    tag = dir_entry[:3]
    length = int(dir_entry[3:7])
    startpos = int(dir_entry[7:])

    if len(fields_text) <= startpos + length:
        raise ValueError('Inconsistent parameters: dir_entry points beyond fields_text.')

    content = fields_text[startpos:startpos + length]

    if not content.startswith(field_delimiter):
        # this is a problem
        raise ValueError('ISO 2709 field with tag "' + tag + '" should begin with ' + field_delimiter)

    return tag, content


#TODO do we even need this? thinking not.
def remove_demarcators(field_content):
    removals = (field_delimiter, subfield_delimiter, record_terminator)
    return field_content.translate({ord(c): None for c in removals})


def make_raw_field(tag_content_pair):
    '''This function accepts a 2-tuple: (a 3 digit tag string, and an
    ISO 2709 representation of a single MARC field). It returns the
    field in raw form, as a dict with "tag", "indicator_1", "indicator_2",
    "content", and "subfields" mappings as needed.
    '''
    retval = {'tag': tag_content_pair[0]}
    content = tag_content_pair[1].split(subfield_delimiter)

    # the leading field delimiter (if present) is not useful at this point.
    content[0] = content[0].lstrip(field_delimiter)

    if len(content) == 1:
        # this field does not have subfields, nor (by MARC field
        # definition) indicators
        retval['content'] = content[0]

    else:
        # the first two characters should be indicators 1 & 2 respectively
        retval['indicator_1'] = content[0][0]
        retval['indicator_2'] = content[0][1]

        # the rest should be subfields
        # TODO fix premature serialization of FOREACH tho
        retval['subfields'] = []
        for subfield_expr in content[1:]:
            retval['subfields'].append({subfield_expr[0]: subfield_expr[1:]})

    return retval



def iso_record_2_raw(iso_record):
    '''Parses an ISO 2709 record into MARCout raw datastructures.
    '''
    LDR = iso_record[:24]
    print('LDR:')
    print(LDR)
    print()
    rest = iso_record[24:]
    first_delim_pos = rest.find(field_delimiter)
    print('first_delim_pos:')
    print(first_delim_pos)
    print()
    directory = rest[:first_delim_pos]
    dir_entries = entries_in_iso_directory(directory)
    fields = rest[first_delim_pos:]

    retval = []
    # begin with LDR
    retval.append({'tag': 'LDR', 'fixed': LDR})

    for entry in dir_entries:
        pair = read_iso_field_content(entry, fields)
        # print()
        # print('tag: ' + pair[0])
        # print(pair[1])
        # print(remove_demarcators(pair[1]))
        raw = make_raw_field(pair)
        # print(raw)
        retval.append(raw)

    return retval


# =============================================================================
#
# ================== FUNCTIONS: RAW DATASTRUCTURE TO ISO 2709 =================


def raw_field_2_iso(raw_field):
    '''This function accepts a raw datastructure(dict) representation
    of a record; splits that into tag and content; and returns
    a 2-tuple of (tag, content) where content is flattened into a string,
    is properly formatted and delimited for ISO 2709.
    '''
    # tag
    tag = raw_field['tag']

    # field content
    retval = field_delimiter
    if 'indicator_1' in raw_field:
        retval += raw_field['indicator_1']
    if 'indicator_2' in raw_field:
        retval += raw_field['indicator_2']

    if 'content' in raw_field:
        # no preceding subfield delimiter
        retval += raw_field['content']
    else:
        # 'content' is incompatible with 'subfields' or 'foreach'
        if 'subfields' in raw_field:
            for subfield in raw_field['subfields']:
                retval += subfield_delimiter
                # dict with only one mapping; key is subfield code
                if len(subfield.keys()) > 1:
                    raise ValueError('subfield dict with multiple mappings: "'
                        + str(subfield) + '".')
                for sub_key in subfield.keys():
                    retval += sub_key
                    retval += subfield[sub_key]

        if 'foreach' in raw_field:
            # this is another level of complexity: a pattern of subfields,
            # repeated in "groups" corresponding to each item in the foreach.
            # There are also group-level items such as demarcators.
            # foreach is a list of lists:
            #
            # 'foreach': [
            #         [{
            #             't': 'Pillow'
            #         }, {
            #             'g': '(8:30)'
            #         }, {
            #             'group_suffix': ' --'
            #         }],
            #         etc.

            # The outer list preserves sort order imposed on the groups.
            # The inner list preserves the pattern (including all demarcators).
            # Each dict contains a single entry.
            #   - Normal subfields get rendered as subfields.
            #   - Demarcators exist at the group level, and are to be rendered as
            #       string literal values (not subfields) when encountered. NO
            #       SUPPLEMENTAL SORTING is required - demarcators were sorted
            #       when data was injected into the Raw form.

            for group_listing in raw_field['foreach']:

                for item in group_listing:
                    # item is a dict. Should only ever have one key &
                    # one associated value.
                    key = list(item.keys())[0]
                    if key.startswith('group_'):
                        # demarcator
                        retval += item[key]

                    else:
                        # it's a subfield
                        retval += subfield_delimiter
                        subfield_code = key
                        subfield_val = item[subfield_code]
                        retval += subfield_code
                        retval += subfield_val


    return tag, retval


def make_iso_directory(field_defs):
    '''Accepts a list of 2-tuples of the form (tag, iso_content)
    and returns a directory listing
    '''
    retval = ''
    cur_startpos = 0

    # print()
    # print('MAKING ISO DIRECTORY----------------------------------')
    for field in field_defs:
        # print()
        # print('field: ' + str(field))
        # tag
        retval += field[0]
        # print('tag:' + field[0])

        # 20190312 fix per issue from Kady Ferris
        # OLD, counts letters as a default string literal in Python3 (unicode string?), maybe undercounts bytes –>  field_len = len(field[1]) # see https://www.linuxjournal.com/content/bytes-characters-and-python-2 for wisdom
        field_len = len(field[1].encode('utf-8'))  # <– NEW forces an encode into a byte string before counting
                                                   #    should always count bytes properly like Python before
                                                   #    version 3 would have

        # length of field content, zeropadded to 4 chars
        length = ('0000' + str(field_len))[-4:]
        # print('length: ' + length)
        retval += length
        # start position for this field
        start_pos = ('00000' + str(cur_startpos))[-5:]
        # print('start_pos: ' + start_pos)
        retval += start_pos
        # move the counter
        cur_startpos = cur_startpos + field_len

    # print('DONE MAKING DIRECTORY---------------------------------')
    # print()
    return retval


def raw_record_2_iso(raw_record):
    # raw_record is a list of field dicts, OPTIONALLY beginning with the
    # 24-charcter LDR code.

    # print()
    # print()
    # print('RAW RECORD:')
    # print(raw_record)
    # print()
    # print()

    LDR = None

    fields = []

    for raw_field in raw_record:
        if raw_field['tag'] == 'LDR':
            LDR = raw_field['fixed']
        else:
            # it's a normal field. Add (tag, content) to field list
            fields.append(raw_field_2_iso(raw_field))

    if not LDR:
        LDR =  ''.join(['0','0','0','0','0',' ',' ',' ',' ','a','2','2',
        ' ',' ',' ',' ',' ',' ',' ','#','4','5','0','0'])

    directory = make_iso_directory(fields)

    field_text = ''.join([field_def[1] for field_def in fields])


    # this is a BINARY format. Take these strings of characters and
    # turn them into byte arrays that encode the characters as utf-8.
    # these byte arrays are string-like, with string methods.
    directory = directory.encode('utf-8')
    field_text = field_text.encode('utf-8')
    field_delimiter = chr(0x1E).encode('utf-8')
    record_terminator = chr(0x1D).encode('utf-8')

    # put these arrays together as the iso record.
    iso_record = directory
    iso_record += field_text
    iso_record += field_delimiter
    iso_record += record_terminator

    # Finish the LDR
    # First, this needs to be modified with string operations
    record_length = 24 + len(iso_record)

    # the length must be zeropadded for a total length of 5 digits
    record_length = ('00000' + str(record_length))[-5:]
    LDR = record_length + LDR[5:]

    # start position of record data is written to LDR positions 12:16.
    # it's computed by len(LDR) (always 24) + len(directory)
    fields_startpos = 24 + len(directory)
    # fields_startpos converted to string, zeropadded to length 5 digits
    fields_startpos = ('00000' + str(fields_startpos))[-5:]

    # insert fields_startpos where it belongs
    LDR = LDR[:12] + fields_startpos + LDR[17:]

    # convert the LDR to byte array, again using UTF-8
    LDR = LDR.encode('UTF-8')

    # prepend the LDR to the record
    iso_record = LDR + iso_record

    # and now, we have the correct binary content, with the correct lengths
    # and offsets computed... but we need to convert it BACK to UTF-8
    # for travel. Not sure this is necessary, but this is the cautious approach
    iso_record = iso_record.decode('utf-8')

    return iso_record

