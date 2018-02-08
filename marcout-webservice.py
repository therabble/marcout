# import for marcout.py -- a file in the same directory as this file.
# marcout is the module that does the export work. Its
# entry point is the "export_records" function.
import marcout

# import app and request modules from the flask package
from flask import Flask, request
# instantiate our flask container app
app = Flask(__name__)

verbose_in_export = False

# t\This decorator is the Flask pattern matcher for this path and
# these methods. If GET is defined, HEAD will be provided for
# free. The decorator applies to the "marcout_export" view function.
# ("views" are Flask's simple interface to the WSGI engine.)
@app.route('/api/marcout/1.0/',  methods=['GET', 'POST'])
def marcout_export():

    if request.method == 'GET':

        # return
        hlomsg = 'Welcome to the MARCout Export Service!\n\n'
        hlomsg += 'To use the service:\n'
        hlomsg += 'You need POST not GET;\n'
        hlomsg += 'Your messagebody needs to be serialized JSON;\n'
        hlomsg += 'The JSON has to be wellformed and carry all needed information.\n'

        return hlomsg

    elif request.method == 'POST':
        print('POST! It is a POST!')
        print('HEADERS:')
        print(request.headers)
        print()
        # we need the JSON unified parameter. Force=True will get JSON whether
        # the HTTP Content-Type is application/json or not.
        json_param = request.get_json(force=True)
        print('JSON:')
        print(json_param)
        # use the marcout module to return the desired serialization
        serialized_records = ''
        try:
            serialized_records = marcout.export_records(json_param, as_string=True, verbose=verbose_in_export)
            # For a string return, HTTP 200 is automatically provided from inner WSGI
            print()
            print(serialized_records)

            return serialized_records
        except Exception as ex:
            print(ex)
            print(type(ex))
            # for a tuple return, the second element is the HTTP status code
            return str(ex), 400

