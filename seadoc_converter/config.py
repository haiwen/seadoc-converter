import os
import sys
import logging

logger = logging.getLogger(__name__)

basedir = os.path.abspath(os.path.dirname(os.path.dirname(__file__)))
sys.path.insert(0, basedir)

SERVER_HOST = '127.0.0.1'
SERVER_PORT = '8888'

SEADOC_PRIVATE_KEY = ''
SEAHUB_SERVICE_URL = ''

LOG_FILE = None
LOG_LEVEL = 'info'
ENABLE_SYS_LOG = False


SDOC_DIR = os.environ.get('SDOC_DIR', '')
if not SDOC_DIR:
    logging.critical('SDOC_DIR is not set')
    raise RuntimeError('SDOC_DIR is not set')
if not os.path.exists(SDOC_DIR):
    logging.critical('SDOC_DIR %s does not exist' % SDOC_DIR)
    raise RuntimeError('SDOC_DIR does not exist.')
sys.path.insert(0, SDOC_DIR)

SDOC_OPERATION_CLEAN_LOG_FILE = 'sdoc_operation_log_clean.log'
SDOC_OPERATION_CLEAN_LOG_LEVEL = 'info'


# config in file
try:
    if os.path.exists('local_settings.py'):
        from local_settings import *
except:
    pass

try:
    conf_path = os.environ.get('CONF_PATH', '')
    if os.path.exists(conf_path):
        sys.path.insert(0, conf_path)
    from seadoc_converter_settings import *
except ImportError as e:
    pass


# config in env
SEADOC_PRIVATE_KEY = os.environ.get('JWT_PRIVATE_KEY', '') or SEADOC_PRIVATE_KEY
SEAHUB_SERVICE_URL = os.environ.get('SEAHUB_SERVICE_URL', '') or SEAHUB_SERVICE_URL
