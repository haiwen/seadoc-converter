import logging

import jwt

from seadoc_converter import config

logger = logging.getLogger(__name__)


def check_auth_token(req):
    auth = req.headers.get('Authorization', '').split()
    if len(auth) != 2 or auth[0].lower() != 'token':
        return False

    try:
        jwt.decode(auth[1], config.SEADOC_PRIVATE_KEY, algorithms=['HS256'])
    except jwt.InvalidTokenError:
        logger.warning('Invalid converter token')
        return False

    return True
