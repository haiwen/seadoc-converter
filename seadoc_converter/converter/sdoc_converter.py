import os
import re
import json
import time
import random
import string
import logging
import requests
import pypandoc
from seadoc_converter.converter.utils import IMAGE_PATTERN, gen_jwt_auth_header
from seadoc_converter.config import PANDOC_MEDIA_ROOT, SEAHUB_SERVICE_URL

logger = logging.getLogger(__name__)


def get_random_id():
    ran_str = ''.join(random.sample(string.ascii_letters + string.digits, 22))
    return ran_str


def parse_italic(italic_json, json_doc={}):
    json_doc['italic'] = True
    children = italic_json['c']
    for item in children:
        if item['t'] == 'Strong':
            parse_strong(item, json_doc)
        if item['t'] == 'Str':
            json_doc['text'] = item['c']
            json_doc['id'] = get_random_id()
    return json_doc


def parse_strong(strong_json, json_doc={}):
    json_doc['bold'] = True
    children = strong_json['c']
    for item in children:
        if item['t'] == 'Emph':
            parse_italic(item, json_doc)
        if item['t'] == 'Str':
            json_doc['text'] = item['c']
            json_doc['id'] = get_random_id()

    return json_doc


def parse_plain(plain):
    children_list = []
    for item in plain['c']:
        if item['t'] == 'Str':
            children_list.append({'text': item['c'], 'id': get_random_id()})
        if item['t'] == 'Space':
            children_list.append({'text': ' ', 'id': get_random_id()})
        if item['t'] == 'Link':
            children_list.append(parse_link(item))
        if item['t'] == 'Code':
            children_list.append(parse_inline_code(item))
    return children_list


def parse_link(link_json):
    link_url = link_json['c'][2][0]
    link_main = link_json['c'][1]
    sdoc_json = {
        'type': 'link',
        'href': link_url,
        'children': [],
        'id': get_random_id(),
    }
    for item in link_main:
        if item['t'] == 'Str':
            sdoc_json['children'].append({'text': item['c'], 'id': get_random_id()})
            sdoc_json['title'] = item['c']

    return sdoc_json


def parse_header(header_json):
    header_level = header_json['c'][0]
    sdoc_json = {
        'type': 'header%s' % header_level,
        'children': [],
        'id': get_random_id()
    }
    header_structure = header_json['c'][2]
    for item in header_structure:
        if item['t'] == 'Str':
            sdoc_json['children'].append({'text': item['c'], "id": get_random_id()})
        if item['t'] == 'Space':
            sdoc_json['children'].append({'text': ' ', 'id': get_random_id()})
        if item['t'] == 'Link':
            sdoc_json['children'].append(parse_link(item))
        if item['t'] == 'Strong':
            sdoc_json['children'].append(parse_strong(item, {}))

    return sdoc_json


def parse_image(image_json):
    image_link = image_json['c'][2][0]
    sdoc_json = {
        'type': 'image',
        'children': [{'id': get_random_id(), 'text': ''}],
        'id': get_random_id(),
        'data': {'src': image_link},
    }
    return sdoc_json


def parse_raw_inline(inline_json):
    try:
        txt_type = inline_json['c'][0]
        if txt_type == 'html':
            img_html = inline_json['c'][1]
            image_link_res = re.findall(IMAGE_PATTERN, img_html)
            if image_link_res:
                image_link = image_link_res[0]
                sdoc_json = image_link and {
                    'type': 'image',
                    'children': [{'id': get_random_id(), 'text': ''}],
                    'id': get_random_id(),
                    'data': {'src': image_link},
                }
                return sdoc_json
    except Exception:
        return None
    return None


def parse_inline_code(code_json):
    code_text = code_json['c'][-1]
    sdoc_json = {
        'text': code_text,
        'id': get_random_id()
    }
    return sdoc_json


def parse_unordered_list(list_json):
    sdoc_json = {'type': 'unordered_list', 'id': get_random_id(), 'children': []}
    for items in list_json['c']:
        list_item = {'type': 'list_item', 'id': get_random_id(), 'children': []}
        for item in items:
            if item['t'] in ['Plain', 'Para']:
                list_item['children'].append({'type': 'paragraph',
                                              'children': parse_plain(item),
                                              'id': get_random_id()})
            if item['t'] == 'BulletList':
                list_item['children'].append(parse_unordered_list(item))
            if item['t'] == 'OrderedList':
                list_item['children'].append(parse_ordered_list(item))
        sdoc_json['children'].append(list_item)
    return sdoc_json


def parse_ordered_list(list_json):
    sdoc_json = {'type': 'ordered_list', 'id': get_random_id(), 'children': []}
    for items in list_json['c'][1]:
        list_item = {'type': 'list_item', 'id': get_random_id(), 'children': []}
        for item in items:
            if item['t'] in ['Plain', 'Para']:
                list_item['children'].append({'type': 'paragraph',
                                              'children': parse_plain(item),
                                              'id': get_random_id()})
            if item['t'] == 'BulletList':
                list_item['children'].append(parse_unordered_list(item))
            if item['t'] == 'OrderedList':
                list_item['children'].append(parse_ordered_list(item))
        sdoc_json['children'].append(list_item)
    return sdoc_json


def parse_codeblock(code_json):
    try:
        lang = code_json['c'][0][1][0]
    except Exception:
        lang = ''

    sdoc_json = {
        'type': 'code_block',
        'children': [],
        'id': get_random_id(),
        'language': lang or 'plaintext',
        'style': {'white_space': "nowrap"}
    }
    main_code = code_json['c'][1]
    for code in main_code.split('\n'):
        sdoc_json['children'].append({
            'type': 'code_line',
            'id': get_random_id(),
            'children': [{'text': code}]
        })
    return sdoc_json


def parse_paragragh(para_json):
    sdoc_json = {
        'type': 'paragraph',
        'children': [],
        'id': get_random_id()
    }
    for item in para_json['c']:
        if item['t'] == 'Str':
            sdoc_json['children'].append({'text': item['c'], "id": get_random_id()})
        if item['t'] == 'Space':
            sdoc_json['children'].append({'text': ' ', "id": get_random_id()})
        if item['t'] == 'Link':
            sdoc_json['children'].append(parse_link(item))
        if item['t'] == 'Strong':
            sdoc_json['children'].append(parse_strong(item, {}))
        if item['t'] == 'Image':
            sdoc_json['children'].append(parse_image(item))
        if item['t'] == 'Emph':
            sdoc_json['children'].append(parse_italic(item, {}))
        if item['t'] == 'RawInline':
            res = parse_raw_inline(item)
            if res:
                sdoc_json['children'].append(parse_raw_inline(item))

    return sdoc_json


def parse_blockquote(block_json):
    sdoc_json = {
        'type': 'blockquote',
        'children': [],
        'id': get_random_id()
    }
    for item in block_json['c']:
        if item['t'] == 'Para':
            sdoc_json['children'].append(parse_paragragh(item))
        if item['t'] == 'BulletList':
            sdoc_json['children'].append(parse_unordered_list(item))
        if item['t'] == 'OrderedList':
            sdoc_json['children'].append(parse_ordered_list(item))

    return sdoc_json


def parse_table(table_json):
    table_sdoc = {
        'type': 'table',
        'id': get_random_id(),
        'children': [],
        'columns': []
    }
    table_head = table_json['c'][3]
    column_num = len(table_head)
    column_length = int(672 / column_num)
    for i in range(column_num):
        table_sdoc['columns'].append({'width': column_length})

    table_row_head = {
        'type': 'table_row',
        'id': get_random_id(),
        'children': [],
        'style': {'min_height': 43}
    }
    for row in table_head:
        table_cell = {
            'id': get_random_id(),
            'children': [],
            'type': 'table_cell'
        }
        if not row:
            row = [{'t': 'Plain', 'c': [{'t': 'Str', 'c': ''}]}]
        for c in row[0]['c']:
            if c['t'] == 'Str':
                table_cell['children'].append({'text': c['c'], 'id': get_random_id(), })
            if c['t'] == 'Space':
                table_cell['children'].append({'text': ' ', 'id': get_random_id(), })
            if c['t'] == 'Code':
                table_cell['children'].append(parse_inline_code(c))
            if c['t'] == 'Strong':
                table_cell['children'].append(parse_strong(c, {}))
            if c['t'] == 'Emph':
                table_cell['children'].append(parse_italic(c, {}))
            if c['t'] == 'Link':
                table_cell['children'].append(parse_link(c))
        table_row_head['children'].append(table_cell)

    table_sdoc['children'].append(table_row_head)

    table_body = table_json['c'][4]

    for row in table_body:
        table_row_body = {
            'type': 'table_row',
            'id': get_random_id(),
            'children': [],
            'style': {'min_height': 43}
        }
        for v in row:
            table_cell = {
                'id': get_random_id(),
                'children': [],
                'type': 'table_cell'
            }

            if not v:
                v = [{'t': 'Plain', 'c': [{'t': 'Str', 'c': ''}]}]

            for c in v[-1]['c']:
                if c['t'] == 'Str':
                    table_cell['children'].append({'text': c['c'], 'id': get_random_id(), })
                if c['t'] == 'Space':
                    table_cell['children'].append({'text': ' ', 'id': get_random_id(), })
                if c['t'] == 'Strong':
                    table_cell['children'].append(parse_strong(c, {}))
                if c['t'] == 'Emph':
                    table_cell['children'].append(parse_italic(c, {}))
                if c['t'] == 'Link':
                    table_cell['children'].append(parse_link(c))
                if c['t'] == 'Code':
                    table_cell['children'].append(parse_inline_code(c))

            table_row_body['children'].append(table_cell)

        table_sdoc['children'].append(table_row_body)
    return table_sdoc


def md2sdoc(md_txt, username=''):
    md_ast = pypandoc.convert_text(md_txt, 'json', 'markdown')
    json_ast = json.loads(md_ast)
    blocks = json_ast['blocks']

    children_list = []
    for item in blocks:
        if item['t'] == 'Header':
            children_list.append(parse_header(item))

        if item['t'] == 'Para':
            children_list.append(parse_paragragh(item))

        if item['t'] == 'CodeBlock':
            children_list.append(parse_codeblock(item))

        if item['t'] == 'BulletList':
            children_list.append(parse_unordered_list(item))

        if item['t'] == 'OrderedList':
            children_list.append(parse_ordered_list(item))

        if item['t'] == 'BlockQuote':
            children_list.append(parse_blockquote(item))

        if item['t'] == 'Table':
            children_list.append(parse_table(item))

    sdoc_json = {
        'cursors': {},
        'last_modify_user': username,
        'children': children_list,
        'version': 1,
        'format_version': 2,
    }

    return sdoc_json


def parse_image_in_docx(image_json, pandoc_media_root, data):

    """
    {'c': [{'c': [['',
                   [],
                   [['width', '5.768055555555556in'],
                    ['height', '2.9382163167104114in']]],
                  [{'c': 'C:\\Users\\hep\\AppData\\Local\\Temp\\1553481246(1).png',
                    't': 'Str'}],
                  ['media/image2.png', '']],
            't': 'Image'}],
     't': 'Para'}
    """

    def find_image_path(data, pandoc_media_root):

        if isinstance(data, dict):
            # If the current item is a dictionary, recursively process its values
            for key, value in data.items():
                result = find_image_path(value, pandoc_media_root)
                if result:
                    return result
        elif isinstance(data, list):
            # If the current item is a list, recursively process each element in the list
            for item in data:
                result = find_image_path(item, pandoc_media_root)
                if result:
                    return result
        elif isinstance(data, str) and data.startswith(pandoc_media_root):
            # If the current item is a string
            # and starts with '/tmp/pandoc/1705741332.2522938/media/image1.png',
            # then it's the target path
            return data

    # /tmp/pandoc/1705741662.112317/media/image3.png
    image_path = find_image_path(image_json, pandoc_media_root)

    # tmp-pandoc-1705741662.112317-media-image3.png
    image_name = image_path.strip('/').replace('/', '-')

    doc_uuid = data.get('doc_uuid')
    with open(image_path, 'rb') as file:

        file_content = file.read()
        upload_link = f"{SEAHUB_SERVICE_URL}/api/v2.1/seadoc/upload-image/{doc_uuid}/"
        headers = gen_jwt_auth_header({
            'file_uuid': doc_uuid,
        })
        resp = requests.post(upload_link, headers=headers,
                             files={'file': (image_name, file_content)})

        if resp.status_code == 200:
            os.remove(image_path)
        else:
            logger.error(upload_link)
            logger.error(headers)
            logger.error(resp.__dict__)

    image_element = {
        'type': 'image',
        'children': [{'id': get_random_id(), 'text': ''}],
        'id': get_random_id(),
        'data': {'src': f'/{image_name}'},
    }
    sdoc_json = {
        'type': 'paragraph',
        'children': [image_element],
        'id': get_random_id()
    }
    return sdoc_json


def docx2sdoc(docx_content, data):

    pandoc_media_root = f'{PANDOC_MEDIA_ROOT}/{time.time()}'

    docx_json_str = pypandoc.convert_text(docx_content, 'json', 'docx',
                                          extra_args=[f'--extract-media={pandoc_media_root}',
                                                      '--from', 'docx+empty_paragraphs'])

    docx_json_obj = json.loads(docx_json_str)
    blocks = docx_json_obj['blocks']

    def is_image(data):

        if isinstance(data, dict):
            if data.get('t').lower() == 'image':
                return True
            else:
                # If the current item is a dictionary, recursively process its values
                for key, value in data.items():
                    result = is_image(value)
                    if result:
                        return result
        elif isinstance(data, list):
            # If the current item is a list, recursively process each element in the list
            for item in data:
                result = is_image(item)
                if result:
                    return result

    children_list = []
    for item in blocks:

        if is_image(item):
            children_list.append(parse_image_in_docx(item, pandoc_media_root, data))

        if item['t'] == 'Header':
            children_list.append(parse_header(item))

        if item['t'] == 'Para' and not is_image(item):
            children_list.append(parse_paragragh(item))

        if item['t'] == 'CodeBlock':
            children_list.append(parse_codeblock(item))

        if item['t'] == 'BulletList':
            children_list.append(parse_unordered_list(item))

        if item['t'] == 'OrderedList':
            children_list.append(parse_ordered_list(item))

        if item['t'] == 'BlockQuote':
            children_list.append(parse_blockquote(item))

        if item['t'] == 'Table':
            children_list.append(parse_table(item))

    sdoc_json = {
        'cursors': {},
        'last_modify_user': data.get('username'),
        'children': children_list,
        'version': 1,
        'format_version': 2,
    }

    return sdoc_json
