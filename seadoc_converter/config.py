import os
import sys
import logging

logger = logging.getLogger(__name__)

basedir = os.path.abspath(os.path.dirname(os.path.dirname(__file__)))
sys.path.insert(0, basedir)

SERVER_HOST = '127.0.0.1'
SERVER_PORT = '8888'

SEAHUB_SECRET_KEY = ''
SEAHUB_SERVER = ''

FILE_SERVER = ''

LOG_FILE = None
LOG_LEVEL = 'info'
ENABLE_SYS_LOG = False


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