from seadoc_converter.server.seadoc_converter_server import SeadocConverterServer


class SeadocConverterApp(object):
    def __init__(self, config):
        self.config = config
        self.seadoc_converter_server = SeadocConverterServer(self)

    def serve_forever(self):
        self.seadoc_converter_server.start()
