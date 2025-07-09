import uuid
import requests
import json
import logging
import time
import xml.etree.ElementTree as ET

from io import BytesIO, StringIO

from docx import Document
from docx.opc.pkgreader import _SerializedRelationships, _SerializedRelationship
from docx.opc.oxml import parse_xml
from docx.document import Document as _Document
from docx.oxml.text.paragraph import CT_P
from docx.oxml.table import CT_Tbl
from docx.table import _Cell, Table
from docx.text.paragraph import Paragraph
from docx.text.run import Run
from docx.text.hyperlink import Hyperlink
from docx.enum.text import WD_ALIGN_PARAGRAPH

from seadoc_converter.config import SEAHUB_SERVICE_URL
from seadoc_converter.converter.utils import gen_jwt_auth_header


logger = logging.getLogger(__name__)


def get_random_id():
    return uuid.uuid4().hex[:22]


def get_image_name():
    return uuid.uuid4().hex[:8]


def load_from_xml_v2(baseURI, rels_item_xml):
    """
    Return |_SerializedRelationships| instance loaded with the
    relationships contained in *rels_item_xml*. Returns an empty
    collection if *rels_item_xml* is |None|.
    """
    srels = _SerializedRelationships()
    if rels_item_xml is not None:
        rels_elm = parse_xml(rels_item_xml)
        for rel_elm in rels_elm.Relationship_lst:
            if rel_elm.target_ref in ('../NULL', 'NULL'):
                continue
            srels._srels.append(_SerializedRelationship(baseURI, rel_elm))
    return srels


def iter_block_items(parent):
    """
    Generate a reference to each paragraph and table child within *parent*,
    in document order. Each returned value is an instance of either Table or
    Paragraph. *parent* would most commonly be a reference to a main
    Document object, but also works for a _Cell object, which itself can
    contain paragraphs and tables.
    """
    if isinstance(parent, _Document):
        parent_elm = parent.element.body
    elif isinstance(parent, _Cell):
        parent_elm = parent._tc

    for child in parent_elm.iterchildren():
        if isinstance(child, CT_P):
            yield Paragraph(child, parent)
        elif isinstance(child, CT_Tbl):
            yield Table(child, parent)


def parse_block_contents(items, docx, docx_uuid):
    empty_elem = {'id': get_random_id(), 'text': ''}
    sdoc_children = []
    for item in items:
        if isinstance(item, Run):
            xmlstr = str(item.element.xml)
            if 'pic:pic' in xmlstr:
                my_namespaces = dict([node for _, node in ET.iterparse(StringIO(xmlstr), events=['start-ns'])])
                root = ET.fromstring(xmlstr)
                for pic in root.findall('.//pic:pic', my_namespaces):
                    cNvPr_elem = pic.find("pic:nvPicPr/pic:cNvPr", my_namespaces)
                    name_attr = cNvPr_elem.get("name")
                    blip_elem = pic.find("pic:blipFill/a:blip", my_namespaces)
                    embed_attr = blip_elem.get('{http://schemas.openxmlformats.org/officeDocument/2006/relationships}embed')
                document_part = docx.part
                image_part = document_part.related_parts[embed_attr]

                upload_link = f"{SEAHUB_SERVICE_URL}/api/v2.1/seadoc/upload-image/{docx_uuid}/"
                headers = gen_jwt_auth_header({
                    'file_uuid': docx_uuid,
                    'exp': int(time.time()) + 300
                })
                resp = requests.post(upload_link, headers=headers,
                                        files={'file': (f'{get_image_name()}-{name_attr}.png', image_part._blob)})
                img_path = json.loads(resp.content.decode()).get('relative_path', [''])[0]
                if resp.status_code == 200:
                    img_struct = {
                        'id': get_random_id(),
                        'type': 'image',
                        'children': [{'id': get_random_id(), 'text': ''}],
                        'data': {'src': img_path}
                    }
                    if img := image_part.image:
                        # 9525 is English Metric Units 2 Pixel
                        img_struct['data']['width'] = int(img.width) / 9525
                    sdoc_children.extend([empty_elem, img_struct, empty_elem])
                else:
                    logger.error(upload_link)
                    logger.error(headers)
                    logger.error(resp.__dict__)

            if text := item.text:
                text_attr = {
                    'id': get_random_id(),
                    'text': text,
                    'bold': getattr(item, 'bold', False),
                    'italic': getattr(item, 'italic', False),
                    'underline': getattr(item, 'underline', False),
                }
                if hasattr(item, 'font'):
                    if item.font.name:
                        text_attr['font'] = item.font.name
                    if item.font.size:
                        text_attr['font_size'] = item.font.size.pt
                    if item.font.color.rgb:
                        rgb_color = item.font.color.rgb
                        hex_color = f'#{rgb_color[0]:02X}{rgb_color[1]:02X}{rgb_color[2]:02X}'
                        text_attr['color'] = hex_color
                sdoc_children.append(text_attr)
        elif isinstance(item, Hyperlink):
            run = item.runs[0]
            link_struct = {
                'id': get_random_id(),
                'type': 'link',
                'href': item.url,
                'title': item.text,
                'children': [
                    {
                        'id': get_random_id(),
                        'text': item.text,
                        'bold': getattr(run, 'bold', False),
                        'italic': getattr(run, 'italic', False),
                        'underline': getattr(run, 'underline', False),
                    }
                ]
            }
            sdoc_children.extend([empty_elem, link_struct, empty_elem])
    return sdoc_children


def parse_heading(block, header_level, docx, docx_uuid):
    align = parse_alignment(block)
    sdoc_children = parse_block_contents(block.iter_inner_content(), docx, docx_uuid)
    return {
        'type': header_level,
        'children': sdoc_children,
        'id': get_random_id(),
        **(align if align else {})
    }


def parse_paragraph(block, docx, docx_uuid):
    align = parse_alignment(block)
    sdoc_children = parse_block_contents(block.iter_inner_content(), docx, docx_uuid)
    return {
        'type': 'paragraph',
        'children': sdoc_children,
        'id': get_random_id(),
        **(align if align else {})
    }


def _get_numFmt(numbering_xml, num_id, ilvlid):
    # Parse the XML
    root = ET.fromstring(numbering_xml)
    namespace = {'w': 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'}

    # Find the <w:num> element with the given numId
    num_element = root.find(f".//w:num[@w:numId='{num_id}']", namespace)
    if num_element is None:
        return None

    # Get the abstractNumId value from the <w:num> element
    abstract_num_id = num_element.find("w:abstractNumId", namespace).get("{http://schemas.openxmlformats.org/wordprocessingml/2006/main}val")

    # Find the corresponding <w:abstractNum> element with the abstractNumId
    abstract_num_element = root.find(f".//w:abstractNum[@w:abstractNumId='{abstract_num_id}']", namespace)
    if abstract_num_element is None:
        return None

    # Find the <w:lvl> element with the given ilvlid
    lvl_element = abstract_num_element.find(f".//w:lvl[@w:ilvl='{ilvlid}']", namespace)
    if lvl_element is None:
        return None

    # Get the numFmt value from the <w:lvl> element
    num_fmt = lvl_element.find("w:numFmt", namespace)
    if num_fmt is not None:
        return num_fmt.get("{http://schemas.openxmlformats.org/wordprocessingml/2006/main}val")
    else:
        return None


def parse_list(block, numbering_xml, docx, docx_uuid):
    if block._element.pPr.numPr is not None:
        num_id = block._element.pPr.numPr.numId.val
    elif block.style._element.pPr.numPr is not None:
        num_id = block.style._element.pPr.numPr.numId.val
    else:
        return parse_paragraph(block, docx, docx_uuid)
    if block._element.pPr.numPr is not None and block._element.pPr.numPr.ilvl is not None:
        ilvl_id = block._element.pPr.numPr.ilvl.val
    elif block.style._element.pPr.numPr is not None:
        ilvl_id = block.style._element.pPr.numPr.ilvl.val
    else:
        return parse_paragraph(block, docx, docx_uuid)

    num_fmt = _get_numFmt(numbering_xml, num_id, ilvl_id)
    if num_fmt in {'decimal', 'lowerLetter', 'lowerRoman', 'upperLetter', 'upperRoman'}:
        list_type = 'ordered_list'
    else:
        list_type = 'unordered_list'
    align = parse_alignment(block)
    children_list = [
        {
            'id': get_random_id(),
            'type': 'list_item',
            'children':
                [{
                'id': get_random_id(),
                'type': 'paragraph',
                'children': parse_block_contents(block.iter_inner_content(), docx, docx_uuid)
            }]
        }
    ]
    return {
        'num_id': num_id,
        'ilvl_id': ilvl_id,
        'type': list_type,
        'id': get_random_id(),
        'children': children_list,
        **(align if align else {}),
    }


def parse_table(table, docx, docx_uuid):
    children_list = []
    column_count = len(table.columns)
    column_width = int(672 / column_count)

    table_sdoc = {
        'type': 'table',
        'id': get_random_id(),
        'children': children_list,
        'columns': [{'width': column_width}] * column_count
    }
    for row in table.rows:
        table_row_body = {
            'type': 'table_row',
            'id': get_random_id(),
            'children': [],
            'style': {'min_height': 43}
        }
        for cell in row.cells:
            para = cell.paragraphs[0]
            cell_content = parse_block_contents(para.iter_inner_content(), docx, docx_uuid)
            table_cell = {
                'id': get_random_id(),
                'type': 'table_cell',
                'children': cell_content
            }
            table_row_body['children'].append(table_cell)

        children_list.append(table_row_body)
    return table_sdoc


def parse_quote(block, docx, docx_uuid):
    align = parse_alignment(block)
    children_sdoc = [{
        'id': get_random_id(),
        'type': 'paragraph',
        'children': parse_block_contents(block.iter_inner_content(), docx, docx_uuid)
    }]
    return {
        'id': get_random_id(),
        'type': 'blockquote',
        'children': children_sdoc,
        **(align if align else {}),
    }


def build_nested_list(children_list):
    elements = []
    root = {'type': 'root', 'children': []}
    stack = []
    current_num_id = None
    ilvl_id_set = {-1, 0}
    for child in children_list:
        if child['type'] not in {'ordered_list', 'unordered_list'}:
            if current_num_id is not None:
                current_num_id = None
                ilvl_id_set = {-1, 0}
                elements.extend(root.get('children'))
            elements.append(child)
            continue
        else:
            num_id = child.pop('num_id')
            ilvl_id = child.pop('ilvl_id')
            if current_num_id != num_id:
                if current_num_id is not None:
                    current_num_id = None
                    ilvl_id_set = {-1, 0}
                    elements.extend(root.get('children'))
                root = {'type': 'root', 'children': []}
                root['children'].append(child)
                stack.append((root, -1))
                stack.append((child, ilvl_id))
                current_num_id = num_id
            else:
                while stack and stack[-1][1] >= ilvl_id:
                    stack.pop()
                parent_node, _ = stack[-1]
                if ilvl_id in ilvl_id_set:
                    if parent_node['type'] == 'root':
                        parent_node['children'][0]['children'].append(child['children'][0])
                    else:
                        parent_node['children'][0]['children'][-1]['children'].append(child['children'][0])
                else:
                     parent_node['children'][0]['children'].append(child)
                     ilvl_id_set.add(int(ilvl_id))
                stack.append((child, ilvl_id))
    if current_num_id is not None:
        elements.extend(root.get('children'))
    return elements


def parse_alignment(block):
    if not hasattr(block, 'alignment'):
        return None
    if block.alignment == WD_ALIGN_PARAGRAPH.LEFT:
        return {'align': 'left'}
    elif block.alignment == WD_ALIGN_PARAGRAPH.CENTER:
        return {'align': 'center'}
    elif block.alignment == WD_ALIGN_PARAGRAPH.RIGHT:
        return {'align': 'right'}
    else:
        return None


def docx2sdoc(docx, username, docx_uuid):
    children_list = []
    # Fix according to: https://github.com/python-openxml/python-docx/issues/1105s
    _SerializedRelationships.load_from_xml = load_from_xml_v2

    docx = Document(BytesIO(docx))
    try:
        numbering_xml = docx.part.numbering_part.element.xml
    except (KeyError, NotImplementedError):
        numbering_xml = None
    styles_map = {
        'Title': 'title',
        'Subtitle': 'subtitle',
        'Heading 1': 'header1',
        'Heading 2': 'header2',
        'Heading 3': 'header3',
        'Heading 4': 'header4',
        'Heading 5': 'header5',
        'Heading 6': 'header6',
        'Heading 7': 'header6',
        'Heading 8': 'header6',
        'Heading 9': 'header6',
    }
    for block in iter_block_items(docx):
        style = block.style
        style_name = block.style.name
        base_style = style.base_style
        is_normal_table = style_name == 'Normal Table' or (base_style.name if base_style else False)
        node = {}
        if style_name in styles_map:
            node = parse_heading(block, styles_map[style_name], docx, docx_uuid)
        elif style_name == 'Normal':
            node = parse_paragraph(block, docx, docx_uuid)
        elif style_name.startswith('List'):
            node = parse_list(block, numbering_xml, docx, docx_uuid)
        elif is_normal_table:
            is_paragraph = isinstance(block, Paragraph)
            if is_paragraph:
                node = parse_paragraph(block, docx, docx_uuid)
            else:
                node = parse_table(block, docx, docx_uuid)
        elif style_name == 'Quote':
            node = parse_quote(block, docx, docx_uuid)
        if node and node.get('children'):
            children_list.append(node)

    children_list = build_nested_list(children_list)
    sdoc_json = {
        'cursors': {},
        'last_modify_user': username,
        'elements': children_list,
        'version': 1,
        'format_version': 4,
    }
    return sdoc_json
