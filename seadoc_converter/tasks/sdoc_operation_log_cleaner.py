import os
import logging
from threading import Thread, Event
from seadoc_converter.config import SDOC_DIR, SDOC_OPERATION_CLEAN_LOG_FILE, SDOC_OPERATION_CLEAN_LOG_LEVEL
from seadoc_converter.utils import get_python_executable, run


class SdocOperationLogCleaner(object):
    def __init__(self):
        self._enabled = True
        self._interval = 60 * 60 * 24  # 1day
        self._logfile = SDOC_OPERATION_CLEAN_LOG_FILE
        self._loglevel = SDOC_OPERATION_CLEAN_LOG_LEVEL

    def start(self):
        if not self.is_enabled():
            logging.warning('Can not scan repo old files auto del days: it is not enabled!')
            return

        logging.info('sdoc operation log cleaner is started, interval = %s sec', self._interval)
        SdocOperationLogCleanerTimer(self._interval, self._logfile, self._loglevel).start()

    def is_enabled(self):
        return self._enabled


class SdocOperationLogCleanerTimer(Thread):
    def __init__(self, interval, logfile, loglevel):
        Thread.__init__(self)
        self._interval = interval
        self._logfile = logfile
        self._loglevel = loglevel

        self.finished = Event()

    def run(self):
        while not self.finished.is_set():
            self.finished.wait(self._interval)
            if not self.finished.is_set():
                logging.info('start cleaning sdoc operation log.')
                try:
                    python_exec = get_python_executable()
                    operation_clean_py = os.path.join(SDOC_DIR, 'scripts', 'clean_operation_log.py')
                    cmd = [
                        python_exec,
                        operation_clean_py,
                        '--logfile', self._logfile,
                        '--loglevel', self._loglevel,
                    ]
                    with open(self._logfile, 'a') as fp:
                        run(cmd, cwd=SDOC_DIR, output=fp)
                except Exception as e:
                    logging.exception('error when clean sdoc operation log: %s', e)

    def cancel(self):
        self.finished.set()
