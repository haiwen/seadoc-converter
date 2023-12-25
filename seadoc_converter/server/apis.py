import os
import jwt
import json
import logging
import requests
from pathlib import Path
from urllib.parse import quote

from flask import request, Flask, Response
from seadoc_converter import config

from seadoc_converter.converter.sdoc_converter import md2sdoc
from seadoc_converter.converter.markdown_converter import sdoc2md
from seadoc_converter.converter.docx_converter import sdoc2docx
from seadoc_converter.converter.utils import get_file_by_token, upload_file_by_token

logger = logging.getLogger(__name__)
flask_app = Flask(__name__)


def check_auth_token(req):
    auth = req.headers.get('Authorization', '').split()
    if not auth or auth[0].lower() != 'token' or len(auth) != 2:
        return False

    token = auth[1]
    if not token:
        return False

    private_key = config.SEADOC_PRIVATE_KEY
    try:
        jwt.decode(token, private_key, algorithms=['HS256'])
    except (jwt.ExpiredSignatureError, jwt.InvalidSignatureError) as e:
        logger.exception(e)
        return False

    return True


@flask_app.route('/api/v1/file-convert/', methods=['POST'])
def convert_markdown_to_sdoc():
    is_valid = check_auth_token(request)
    if not is_valid:
        return {'error_msg': 'Permission denied'}, 403
    try:
        data = json.loads(request.data)
    except Exception as e:
        logger.exception(e)
        return {'error_msg': 'Bad request.'}, 400

    path = data.get('path')
    username = data.get('username')
    doc_uuid = data.get('doc_uuid')
    src_type = data.get('src_type')
    dst_type = data.get('dst_type')

    extension = Path(path).suffix
    if extension not in ['.md', '.sdoc']:
        return {'error_msg': 'path invalid.'}, 400

    download_token = data.get('download_token')
    upload_token = data.get('upload_token')

    file_content = get_file_by_token(path, download_token).decode()

    parent_dir = os.path.dirname(path)
    file_name = os.path.basename(path)

    if extension == '.md' and src_type == 'markdown' and dst_type == 'sdoc':
        if file_content:
            file_content = md2sdoc(file_content, username=username)
        file_name = file_name[:-2] + 'sdoc'
    elif extension == '.sdoc' and src_type == 'sdoc' and dst_type == 'markdown':
        if file_content:
            file_content = json.loads(file_content)
            file_content = sdoc2md(file_content, doc_uuid=doc_uuid)
        file_name = file_name[:-4] + 'md'
    else:
        return {'error_msg': 'unsupported convert type.'}, 400

    try:
        resp = upload_file_by_token(parent_dir, file_name, upload_token, file_content)
        if not resp.ok:
            logger.error(resp.text)
            return {'error_msg': resp.text}, 500

    except Exception as e:
        logger.error(e)
        error_msg = 'Internal Server Error'
        return {'error_msg': error_msg}, 500

    return {'success': True}, 200


@flask_app.route('/api/v1/sdoc-convert-to-docx/', methods=['POST'])
def sdoc_convert_to_docx():

    is_valid = check_auth_token(request)
    if not is_valid:
        return {'error_msg': 'Permission denied'}, 403

    try:
        data = json.loads(request.data)
    except Exception as e:
        logger.exception(e)
        return {'error_msg': 'Bad request.'}, 400

    path = data.get('path')
    username = data.get('username')
    doc_uuid = data.get('doc_uuid')
    src_type = data.get('src_type')
    dst_type = data.get('dst_type')

    extension = Path(path).suffix
    if extension not in ['.sdoc']:
        return {'error_msg': 'path invalid.'}, 400

    download_token = data.get('download_token')
    upload_token = data.get('upload_token')

    sdoc_content = get_file_by_token(path, download_token).decode()

    parent_dir = os.path.dirname(path)
    filename = os.path.basename(path)
    new_filename = filename[:-4] + 'docx'

    docx_content = b''
    if extension == '.sdoc' and src_type == 'sdoc' and dst_type == 'docx':
        if sdoc_content:
            sdoc_content_json = json.loads(sdoc_content)
            docx_content = sdoc2docx(sdoc_content_json, doc_uuid, username)
    else:
        return {'error_msg': 'unsupported convert type.'}, 400

    # upload file
    from seadoc_converter.converter.utils import gen_file_upload_url
    upload_url = gen_file_upload_url('upload-api', upload_token)
    files = {
        'file': (new_filename, docx_content),
        'parent_dir': parent_dir,
    }
    try:
        resp = requests.post(upload_url, files=files)
        if not resp.ok:
            logger.error(resp.text)
            return {'error_msg': resp.text}, 500

    except Exception as e:
        logger.error(e)
        error_msg = 'Internal Server Error'
        return {'error_msg': error_msg}, 500

    return {'success': True}, 200


@flask_app.route('/api/v1/sdoc-export-to-docx/', methods=['POST'])
def sdoc_export_to_docx():

    is_valid = check_auth_token(request)
    if not is_valid:
        return {'error_msg': 'Permission denied'}, 403

    try:
        data = json.loads(request.data)
    except Exception as e:
        logger.exception(e)
        return {'error_msg': 'Bad request.'}, 400

    path = data.get('path')
    username = data.get('username')
    doc_uuid = data.get('doc_uuid')
    src_type = data.get('src_type')
    dst_type = data.get('dst_type')

    extension = Path(path).suffix
    if extension not in ['.sdoc']:
        return {'error_msg': 'path invalid.'}, 400

    download_token = data.get('download_token')
    sdoc_content = get_file_by_token(path, download_token).decode()

    docx_content = b''
    if extension == '.sdoc' and src_type == 'sdoc' and dst_type == 'docx':
        if sdoc_content:
            sdoc_content_json = json.loads(sdoc_content)
            docx_content = sdoc2docx(sdoc_content_json, doc_uuid, username)
    else:
        return {'error_msg': 'unsupported convert type.'}, 400

    filename = os.path.basename(path)
    new_filename = quote(filename[:-4] + 'docx')
    return Response(
        docx_content,
        mimetype='application/vnd.openxmlformats-officedocument.wordprocessingml.document',
        headers={'Content-disposition': f'attachment; filename={new_filename}'}
    )
