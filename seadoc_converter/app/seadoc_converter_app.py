from seadoc_converter.server.seadoc_converter_server import SeadocConverterServer
from seadoc_converter.tasks.sdoc_operation_log_cleaner import SdocOperationLogCleaner


class SeadocConverterApp(object):
    def __init__(self, config):
        self.config = config
        self.seadoc_converter_server = SeadocConverterServer(self)
        self.sdoc_operation_log_cleaner = SdocOperationLogCleaner()

    def serve_forever(self):
        self.seadoc_converter_server.start()
        self.sdoc_operation_log_cleaner.start()
