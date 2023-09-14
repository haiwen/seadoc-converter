from threading import Thread
from gevent.pywsgi import WSGIServer
from seadoc_converter.server.apis import flask_app
from seadoc_converter.config import SERVER_HOST, SERVER_PORT


class SeadocConverterServer(Thread):

    def __init__(self, app):
        Thread.__init__(self)
        flask_app.app = app

        self.server = WSGIServer((SERVER_HOST, int(SERVER_PORT)), flask_app)

    def run(self):
        self.server.serve_forever()
