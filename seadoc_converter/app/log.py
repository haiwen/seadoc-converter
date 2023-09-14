# -*- coding: utf-8 -*-
import sys
import logging
from logging import handlers


def _get_log_level(level):
    if level == 'debug':
        return logging.DEBUG
    elif level == 'info':
        return logging.INFO
    else:
        return logging.WARNING


class LogConfigurator(object):
    def __init__(self, level, logfile=None):
        self._level = _get_log_level(level)
        self._logfile = logfile

        if logfile is None:
            self._basic_config()
        else:
            self._rotating_config()

    def _rotating_config(self):
        # Rotating log
        handler = handlers.TimedRotatingFileHandler(self._logfile, when='W0', interval=1, backupCount=7)
        handler.setLevel(self._level)
        formatter = logging.Formatter('[%(asctime)s] [%(levelname)s] %(name)s:%(lineno)s %(funcName)s %(message)s')
        handler.setFormatter(formatter)

        logging.root.setLevel(self._level)
        logging.root.addHandler(handler)

    def _basic_config(self):
        # Log to stdout. Mainly for development.
        kw = {
            'format': '[%(asctime)s] [%(levelname)s] %(name)s:%(lineno)s %(funcName)s %(message)s',
            'datefmt': '%m/%d/%Y %H:%M:%S',
            'level': self._level,
            'stream': sys.stdout
        }

        logging.basicConfig(**kw)

    def add_syslog_handler(self):
        handler = handlers.SysLogHandler(address='/dev/log')
        handler.setLevel(self._level)
        formatter = logging.Formatter('seafconverter[%(process)d]: %(message)s')
        handler.setFormatter(formatter)
        logging.root.addHandler(handler)
