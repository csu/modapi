import argparse
from importlib import import_module

from flask import Flask, jsonify, request, send_from_directory
from werkzeug.exceptions import HTTPException, HTTP_STATUS_CODES

from common import require_secret
from modularity import modularity
import notify
import config

def inject(module, mod_conf):
    if config.MOD_CONFIG_INJECT_KEY in mod_conf:
        inject_config = mod_conf[config.MOD_CONFIG_INJECT_KEY]
        for k, v in config.INJECTABLE.iteritems():
            single_inject(k, v, module, inject_config)

def single_inject(key, value, module, inject_config):
    if key in inject_config:
        x = inject_config[key]
        setattr(module, x, value)

def handle_error(e):
    code = 500
    if isinstance(e, HTTPException):
        code = e.code
    notifier = notify.boxcar.BoxcarNotifier()
    notifier.quick_send('Error: %s' % e)
    return jsonify(error=str(e)), code

class ModApi:
    def __init__(self):
        self.app = Flask(__name__)
        self.load_modules()

        for code in HTTP_STATUS_CODES:
            self.app.register_error_handler(code, handle_error)

        @self.app.route('/robots.txt')
        def static_from_root():
            return send_from_directory(app.static_folder, request.path[1:])

        @self.app.route('/favicon.ico')
        def favicon():
            return send_from_directory(app.root_path, 'favicon.ico',
                    mimetype='image/vnd.microsoft.icon')

        @self.app.route('/')
        @require_secret
        def index():
            notifier = notify.boxcar.BoxcarNotifier()
            notifier.quick_send('Modapi running.')
            return jsonify({'status': 'ok'})

        def shutdown_server():
            func = request.environ.get('werkzeug.server.shutdown')
            if func is None:
                raise RuntimeError('Not running with the Werkzeug Server')
            func()

        @self.app.route('/shutdown')
        @require_secret
        def shutdown():
            shutdown_server()
            return 'Server shutting down...'

    def load_modules(self):
        for p in modularity.get_modules(config.MODULES_DIR):
            c = import_module(p + '.config')
            mc = c.config
            k = config.MOD_CONFIG_ROUTES_MOD_KEY
            rmod = mc[k] if k in mc else config.MOD_CONFIG_ROUTES_MOD_DEFAULT
            m = import_module(p + '.' + rmod)
            k = config.MOD_CONFIG_MOD_VAR_KEY
            mvar = mc[k] if k in mc else config.MOD_CONFIG_MOD_VAR_DEFAULT
            mod = getattr(m, mvar)
            inject(m, mc)
            k = config.MOD_CONFIG_URL_PREFIX_KEY
            pre = mc[k] if k in mc else None
            self.app.register_blueprint(mod, url_prefix=pre)

api = ModApi()
app = api.app

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("-d", "--debug", help="enable debug", action="store_true")
    args = parser.parse_args()

    api = ModApi()
    api.app.run(debug=args.debug, host=config.SERVER_HOST, port=config.SERVER_PORT)