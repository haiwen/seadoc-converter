import uuid
import xml.etree.ElementTree as ET
import requests
import time
from bs4 import BeautifulSoup
from markdown_it import MarkdownIt
from markdown_it.tree import SyntaxTreeNode
from mdit_py_plugins.tasklists import tasklists_plugin
from mdit_py_plugins.dollarmath import dollarmath_plugin
from seadoc_converter.config import SEAHUB_SERVICE_URL


def trans_image_url_to_path(doc_uuid, image_name_url_map):
    from seadoc_converter.converter.utils import gen_jwt_auth_header
    headers = gen_jwt_auth_header({
        'file_uuid': doc_uuid,
        'exp': int(time.time()) + 300,
        'is_internal': True
    })
    url = f"{SEAHUB_SERVICE_URL}/api/v2.1/internal/convert-seadoc-image/{doc_uuid}/"
    data = {'image_name_url_map': image_name_url_map}
    resp = requests.post(url, json=data, headers=headers)
    
    if not resp.ok:
        return False, resp.text
    
    return True, None

def get_random_id():
    return uuid.uuid4().hex[:22]


def parse_tokens(token_stream, **kwargs):
    empty_elem = {'id': get_random_id(), 'text': ''}
    sdoc_children = []
    for token in token_stream:
        if token.type == 'text':
            text = token.content
            sdoc_children.append({'id': get_random_id(), 'text': text, **kwargs})
        elif token.type == 'code_inline':
            text = token.content
            sdoc_children.append({'id': get_random_id(), 'text': text, 'code': True, **kwargs})
        elif token.type == 'em':
            sdoc_children.extend(parse_tokens(token.children, italic=True, **kwargs))
        elif token.type == 'strong':
            if 'bold' not in kwargs:
                sdoc_children.extend(parse_tokens(token.children, bold=True, **kwargs))
            else:
                sdoc_children.extend(parse_tokens(token.children, **kwargs))
        elif token.type == 'link':
            link_struct = {
                'id': get_random_id(),
                'type': 'link',
                'href': token.attrs.get('href'),
                'title': token.attrs.get('title'),
                'children': parse_tokens(token.children, **kwargs)
            }
            sdoc_children.extend([empty_elem, link_struct, empty_elem])
        elif token.type == 'image':
            image_name_url_map = kwargs.get('image_name_url_map')
            image_name = f'{uuid.uuid4().hex[:8]}.png'
            image_src = token.attrs.get('src')
            image_name_url_map[image_name] = image_src
            img_struct = {
                'id': get_random_id(),
                'type': 'image',
                'children': [{'id': get_random_id(), 'text': ''}],
                'data': {'src': f'/{image_name}'}
            }
            width = token.attrs.get('width')
            height = token.attrs.get('height')
            if width:
                img_struct['data']['width'] = float(width)
            if height:
                img_struct['data']['height'] = float(height)
            sdoc_children.extend([empty_elem, img_struct, empty_elem])
        elif token.type in {'html_block', 'html_inline'}:
            image_name_url_map = kwargs.get('image_name_url_map')
            sdoc_children.extend(parse_html_inline_block(token.content, image_name_url_map))
        else:
            sdoc_children.append({'id': get_random_id(), 'text': token.content, **kwargs})
    return sdoc_children


def parse_header(node, image_name_url_map):
    level_number = node.tag[1]
    inline_elem = node.children[0]
    sdoc_children = parse_tokens(inline_elem.children, image_name_url_map=image_name_url_map)
    return {
        'type': f'header{level_number}',
        'children': sdoc_children,
        'id': get_random_id()
    }


def parse_paragraph(node, image_name_url_map):
    inline_elem = node.children[0]
    sdoc_children = parse_tokens(inline_elem.children, image_name_url_map=image_name_url_map)
    return {
        'type': 'paragraph',
        'children': sdoc_children,
        'id': get_random_id()
    }


def parse_math(node):
    sdoc_children = [{'id': get_random_id(), 'text': node.content}]
    return {'type': 'paragraph', 'children': sdoc_children, 'id': get_random_id()}


def parse_list(node, list_type, image_name_url_map):
    item_list = node.children
    children_list = []
    for item in item_list:
        parsed_item = {
            'id': get_random_id(),
            'type': 'list_item',
            'children': []
        }
        for child in item.children:
            if child.type == 'paragraph':
                inline_elem = child.children[0]
                parsed_item['children'].append({
                    'id': get_random_id(),
                    'type': 'paragraph',
                    'children': parse_tokens(inline_elem.children, image_name_url_map=image_name_url_map)
                })
            elif child.type in {'bullet_list', 'ordered_list'}:
                list_type_map = {'bullet_list': 'unordered_list'}.get(child.type, child.type)
                parsed_item['children'].append(parse_list(child, list_type_map, image_name_url_map))
        children_list.append(parsed_item)
    return {'type': list_type, 'id': get_random_id(), 'children': children_list}


def parse_check_list(node, image_name_url_map):
    children_list = []
    checked_status = False
    para_node = node.children[0].children[0]
    inline_node_list = para_node.children[0].children
    for inline in inline_node_list:
        # Get is checked
        if inline.type == 'html_inline':
            html = inline.content
            soup = BeautifulSoup(html, 'html.parser')
            input_tag = soup.find('input')
            if input_tag and input_tag.get('checked'):
                checked_status = True
        else:
            children_list.extend(parse_tokens([inline], image_name_url_map=image_name_url_map))
    return {
        'type': 'check_list_item',
        'id': get_random_id(),
        'children': children_list,
        'checked': checked_status,
    }


def parse_html_inline_block(html, image_name_url_map):
    empty_elem = {'id': get_random_id(), 'text': ''}
    try:
        element = ET.fromstring(html)
    except Exception as e:
        return [empty_elem]

    imgsrc = element.get('src')
    width = element.get('width')
    if imgsrc and width:
        image_name = f'{uuid.uuid4().hex[:8]}.png'
        image_name_url_map[image_name] = imgsrc
        img_struct = {
            'id': get_random_id(),
            'type': 'image',
            'children': [{'id': get_random_id(), 'text': ''}],
            'data': {'src': f'/{image_name}', 'width': float(width)}
        }
        return [empty_elem, img_struct, empty_elem]
    else:
        return [empty_elem]


def parse_table(node, image_name_url_map):
    children_list = []
    if len(node.children) != 2:
        thead = node.children[0]
        table_rows = thead.children
    else:
        thead, tbody = node.children
        table_rows = thead.children + tbody.children

    column_count = len(thead.children[0].children)
    column_width = int(672 / column_count)

    table_sdoc = {
        'type': 'table',
        'id': get_random_id(),
        'children': children_list,
        'columns': [{'width': column_width}] * column_count
    }

    for row in table_rows:
        row_children = row.children
        table_row_body = {
            'type': 'table_row',
            'id': get_random_id(),
            'children': [],
            'style': {'min_height': 43}
        }

        for cell in row_children:
            cell_content = parse_tokens(cell.children[0].children, image_name_url_map=image_name_url_map)
            table_cell = {
                'id': get_random_id(),
                'type': 'table_cell',
                'children': cell_content
            }
            table_row_body['children'].append(table_cell)

        children_list.append(table_row_body)

    return table_sdoc


def parse_codeblock(node):
    code_lines = node.content.strip().split('\n')
    children_list = []
    for line in code_lines:
        children_list.append({
            'id': get_random_id(),
            'type': 'code_line',
            'children': [{'id': get_random_id(), 'text': line}]
        })
    return {
        'id': get_random_id(),
        'type': 'code_block',
        'style': {'white_space': 'nowrap'},
        'language': node.info,
        'children': children_list,
    }


def md2sdoc(md_txt, username='', image_name_url_map=None):
    md = MarkdownIt("gfm-like").use(tasklists_plugin).use(dollarmath_plugin)
    tokens = md.parse(md_txt)
    root = SyntaxTreeNode(tokens).children

    def _parse_node(root, image_name_url_map):
        children_list = []
        for node in root:
            if node.type == 'heading':
                children_list.append(parse_header(node, image_name_url_map=image_name_url_map))
            elif node.type == 'paragraph':
                children_list.append(parse_paragraph(node, image_name_url_map=image_name_url_map ))
            elif node.type == 'math_block':
                children_list.append(parse_math(node))
            elif node.type == 'bullet_list':
                if node.attrs.get('class') == 'contains-task-list':
                    children_list.append(parse_check_list(node, image_name_url_map=image_name_url_map))
                else:
                    children_list.append(parse_list(node, 'unordered_list', image_name_url_map=image_name_url_map))
            elif node.type == 'ordered_list':
                children_list.append(parse_list(node, 'ordered_list', image_name_url_map=image_name_url_map))
            elif node.type == 'table':
                children_list.append(parse_table(node, image_name_url_map=image_name_url_map))
            elif node.type == 'fence':
                children_list.append(parse_codeblock(node))
            elif node.type == 'blockquote':
                children_list.extend(
                    [
                        {
                            'id': get_random_id(),
                            'type': 'blockquote',
                            'children': _parse_node(node, image_name_url_map=image_name_url_map),
                        }
                    ]
                )
            elif node.type == 'html_block':
                children_list.append(
                    {
                        'type': 'paragraph',
                        'children': parse_html_inline_block(node.content, image_name_url_map=image_name_url_map),
                        'id': get_random_id(),
                    }
                )
        return children_list

    children_list = _parse_node(root, image_name_url_map=image_name_url_map)
    sdoc_json = {
        'cursors': {},
        'last_modify_user': username,
        'elements': children_list,
        'version': 1,
        'format_version': 4,
    }
    
    return sdoc_json
