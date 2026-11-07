import os
import json
import logging
from io import BytesIO
from pathlib import Path
from tempfile import TemporaryDirectory
from urllib.parse import quote
from zipfile import ZipFile

from flask import request, Flask, Response
from seadoc_converter import seahub_api
from seadoc_converter.server.auth import check_auth_token, get_file_token_payload

from seadoc_converter.converter.sdoc_converter.docx2sdoc import docx2sdoc
from seadoc_converter.converter.sdoc_converter.md2sdoc import md2sdoc, trans_image_url_to_path
from seadoc_converter.converter.markdown_converter import sdoc2md
from seadoc_converter.converter.docx_converter import sdoc2docx
from seadoc_converter.converter.html_converter import sdoc2html
from seadoc_converter.converter.utils import process_zip_file

logger = logging.getLogger(__name__)
flask_app = Flask(__name__)


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
    doc_uuid = data.get('doc_uuid')
    src_type = data.get('src_type')
    dst_type = data.get('dst_type')

    extension = Path(path).suffix
    if extension not in ['.md', '.sdoc', '.docx']:
        return {'error_msg': 'path invalid.'}, 400

    file_token = data.get('file_token')
    if not isinstance(file_token, str) or not file_token:
        return {'error_msg': 'file_token invalid.'}, 400

    payload = get_file_token_payload(file_token)
    if (payload is None or not payload.get('output_path') or not payload.get('doc_uuid')
            or payload['doc_uuid'] != doc_uuid):
        return {'error_msg': 'Permission denied'}, 403
    doc_uuid = payload['doc_uuid']
    username = payload['username']

    if extension == '.docx':
        file_content = seahub_api.get_file_content(file_token)
    else:
        file_content = seahub_api.get_file_content(file_token).decode()
    file_name = os.path.basename(path)
    image_name_url_map = None
    if extension == '.md' and src_type == 'markdown' and dst_type == 'sdoc':
        if file_content:
            image_name_url_map = {}
            file_content = md2sdoc(file_content, username=username, image_name_url_map=image_name_url_map)
        file_name = file_name[:-2] + 'sdoc'
    elif extension == '.docx' and src_type == 'docx' and dst_type == 'sdoc':
        if file_content:
            file_content, error_msg = docx2sdoc(file_content, username, doc_uuid)
            if not file_content:
                return {'error_msg': error_msg}, 400
        file_name = file_name[:-4] + 'sdoc'
    elif extension == '.sdoc' and src_type == 'sdoc' and dst_type == 'markdown':
        if file_content:
            file_content = json.loads(file_content)
            file_content = sdoc2md(file_content, doc_uuid=doc_uuid)
        file_name = file_name[:-4] + 'md'
    else:
        return {'error_msg': 'unsupported convert type.'}, 400

    if isinstance(file_content, dict):
        file_content = json.dumps(file_content)

    try:
        resp = seahub_api.upload_file(file_token, file_name, file_content.encode())
        if not resp.ok:
            logger.error(resp.text)
            return {'error_msg': 'Failed to upload converted file.'}, 500

        if image_name_url_map:
            success, error_msg = trans_image_url_to_path(doc_uuid, image_name_url_map)
            if error_msg:
                logger.error(error_msg)

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

    file_token = data.get('file_token')
    if not isinstance(file_token, str) or not file_token:
        return {'error_msg': 'file_token invalid.'}, 400

    sdoc_content = seahub_api.get_file_content(file_token).decode()

    filename = os.path.basename(path)
    new_filename = filename[:-4] + 'docx'

    docx_content = b''
    if extension == '.sdoc' and src_type == 'sdoc' and dst_type == 'docx':
        if sdoc_content:
            sdoc_content_json = json.loads(sdoc_content)
            docx_content = sdoc2docx(sdoc_content_json, doc_uuid, username, file_token=file_token)
    else:
        return {'error_msg': 'unsupported convert type.'}, 400

    try:
        resp = seahub_api.upload_file(file_token, new_filename, docx_content)
        if not resp.ok:
            logger.error(resp.text)
            return {'error_msg': 'Failed to upload converted file.'}, 500

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
    file_token = data.get('file_token')

    extension = Path(path).suffix
    if extension not in ['.sdoc']:
        return {'error_msg': 'path invalid.'}, 400

    if not isinstance(file_token, str) or not file_token:
        return {'error_msg': 'file_token invalid.'}, 400

    sdoc_content = seahub_api.get_file_content(file_token).decode()

    docx_content = b''
    if extension == '.sdoc' and src_type == 'sdoc' and dst_type == 'docx':
        if sdoc_content:
            sdoc_content_json = json.loads(sdoc_content)
            docx_content = sdoc2docx(sdoc_content_json, doc_uuid, username, file_token=file_token)
    else:
        return {'error_msg': 'unsupported convert type.'}, 400

    filename = os.path.basename(path)
    new_filename = quote(filename[:-4] + 'docx')
    return Response(
        docx_content,
        mimetype='application/vnd.openxmlformats-officedocument.wordprocessingml.document',
        headers={'Content-disposition': f'attachment; filename={new_filename}'}
    )


@flask_app.route('/api/v1/sdoc-export-to-md/', methods=['POST'])
def sdoc_export_to_md():
    is_valid = check_auth_token(request)
    if not is_valid:
        return {'error_msg': 'Permission denied'}, 403

    try:
        data = json.loads(request.data)
    except Exception as e:
        logger.exception(e)
        return {'error_msg': 'Bad request.'}, 400

    path = data.get('path')
    doc_uuid = data.get('doc_uuid')
    src_type = data.get('src_type')
    dst_type = data.get('dst_type')
    file_token = data.get('file_token')

    extension = Path(path).suffix
    if extension not in ['.sdoc']:
        return {'error_msg': 'path invalid.'}, 400

    if not isinstance(file_token, str) or not file_token:
        return {'error_msg': 'file_token invalid.'}, 400

    sdoc_content = seahub_api.get_file_content(file_token).decode()
    md_content = ''
    if extension == '.sdoc' and src_type == 'sdoc' and dst_type == 'md':
        if sdoc_content:
            sdoc_content_json = json.loads(sdoc_content)
            md_content = sdoc2md(sdoc_content_json, doc_uuid)
    else:
        return {'error_msg': 'unsupported convert type.'}, 400

    if isinstance(md_content, dict):
        md_content = json.dumps(md_content)

    if isinstance(md_content, str):
        response_content = md_content.encode()  # str -> bytes
    else:
        response_content = md_content

    return Response(
        response_content,
        mimetype='application/octet-stream',
    )


@flask_app.route('/api/v1/sdoc-export-to-html/', methods=['POST'])
def sdoc_export_to_html():
    """Export an .sdoc file as an HTML response (direct download)."""
    is_valid = check_auth_token(request)
    if not is_valid:
        return {'error_msg': 'Permission denied'}, 403

    try:
        data = json.loads(request.data)
    except Exception as e:
        logger.exception(e)
        return {'error_msg': 'Bad request.'}, 400

    path = data.get('path')
    doc_uuid = data.get('doc_uuid')
    src_type = data.get('src_type')
    dst_type = data.get('dst_type')
    file_token = data.get('file_token')
    publish_url = data.get('publish_url')
    page_id_name_dict = data.get('page_id_name_dict')
    image_root_url = data.get('image_root_url')

    extension = Path(path).suffix
    if extension not in ['.sdoc']:
        return {'error_msg': 'path invalid.'}, 400

    if not isinstance(file_token, str) or not file_token:
        return {'error_msg': 'file_token invalid.'}, 400

    if not (extension == '.sdoc' and src_type == 'sdoc' and dst_type == 'html'):
        return {'error_msg': 'unsupported convert type.'}, 400

    sdoc_content = seahub_api.get_file_content(file_token).decode()
    if not sdoc_content:
        return {'error_msg': 'Empty sdoc content.'}, 400

    html_body = sdoc2html(sdoc_content,
                          doc_uuid=doc_uuid,
                          publish_url=publish_url,
                          page_id_name_dict=page_id_name_dict,
                          image_root_url=image_root_url)

    filename = os.path.basename(path)
    new_filename = quote(filename[:-5] + '.html')
    return Response(
        html_body.encode(),
        mimetype='text/html',
        headers={'Content-Disposition': f'attachment; filename={new_filename}'},
    )


@flask_app.route('/api/v1/confluence-to-wiki/', methods=['POST'])
def confluence_to_wiki():
    is_valid = check_auth_token(request)
    if not is_valid:
        return {'error_msg': 'Permission denied'}, 403
    try:
        data = json.loads(request.data)
    except Exception as e:
        logger.exception(e)
        return {'error_msg': 'Bad request.'}, 400

    filename = data.get('filename')
    file_token = data.get('file_token')
    username = data.get('username')
    seafile_server_url = data.get('seafile_server_url', '')

    if (not isinstance(filename, str)
            or not filename.endswith('.html.zip')
            or any(char in filename for char in ('/', '\\', '\x00'))):
        return {'error_msg': 'path invalid.'}, 400
    if not isinstance(file_token, str) or not file_token:
        return {'error_msg': 'file_token invalid.'}, 400
    if not username:
        return {'error_msg': 'username invalid.'}, 400

    payload = get_file_token_payload(file_token)
    if (payload is None or not payload.get('output_path')
            or payload['filename'] != filename):
        return {'error_msg': 'Permission denied'}, 403
    username = payload['username']

    with TemporaryDirectory(prefix='confluence-') as space_dir:
        try:
            content = seahub_api.get_file_content(file_token)
            with ZipFile(BytesIO(content), 'r') as zip_ref:
                zip_ref.extractall(space_dir)
        except Exception as e:
            logger.exception(e)
            return {'error_msg': 'Failed to download or extract confluence content.'}, 500
        try:
            cf_id_to_cf_title_map = process_zip_file(space_dir, seafile_server_url, username, file_token)
        except Exception as e:
            logger.exception(e)
            return {'error_msg': 'Failed to process confluence content.'}, 500
    return {'cf_id_to_cf_title_map': cf_id_to_cf_title_map}, 200
