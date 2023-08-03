import re
from settings import SEAFILE_SERVER


IMAGE_PATTERN = r'<img.*?src="(.*?)".*?>'


def is_url_link(s):
    if re.match(r'^http[s]?://', s):
        return True
    else:
        return False

def trans_img_path_to_url(image_path, doc_uuid):
    if is_url_link(image_path):
        return image_path

    return "%(server_url)s/%(tag)s/%(doc_uuid)s/%(image_path)s" % ({
        'server_url': SEAFILE_SERVER.rstrip('/'),
        'tag': 'api/v2.1/seadoc/download-image',
        'doc_uuid': doc_uuid,
        'image_path': image_path.strip('/')
    })

