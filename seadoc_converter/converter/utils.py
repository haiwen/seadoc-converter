import re
import os
import json
import requests
from seadoc_converter.config import SEAHUB_SERVER, FILE_SERVER


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
        'server_url': SEAHUB_SERVER.rstrip('/'),
        'tag': 'api/v2.1/seadoc/download-image',
        'doc_uuid': doc_uuid,
        'image_path': image_path.strip('/')
    })


def gen_file_get_url(token, filename):
    from urllib.parse import quote as urlquote
    return '%s/files/%s/%s' % (FILE_SERVER, token, urlquote(filename))


def gen_file_upload_url(op, token):
    return '%s/%s/%s' % (FILE_SERVER, op, token)


def get_file_by_token(path, token):
    filename = os.path.basename(path)
    url = gen_file_get_url(token, filename)
    content = requests.get(url, timeout=30).content
    return content


def upload_file_by_token(parent_dir, file_name, token, content):
    new_file_name = file_name
    upload_link = gen_file_upload_url('upload-api', token)
    new_file_path = os.path.join(parent_dir, new_file_name)

    if isinstance(content, dict):
        content = json.dumps(content)

    resp = requests.post(upload_link,
                         data={'target_file': new_file_path, 'parent_dir': parent_dir},
                         files={'file': (new_file_name, content.encode())},
                         timeout=30
                         )
    return resp
