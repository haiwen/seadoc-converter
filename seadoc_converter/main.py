from gevent import monkey; monkey.patch_all()

import config
from seadoc_converter.app.log import LogConfigurator
from seadoc_converter.app.seadoc_converter_app import SeadocConverterApp

def main():
    app_logger = LogConfigurator(config.LOG_LEVEL, config.LOG_FILE)

    if config.ENABLE_SYS_LOG:
        app_logger.add_syslog_handler()

    app = SeadocConverterApp(config)
    app.serve_forever()


if __name__ == '__main__':
    main()
