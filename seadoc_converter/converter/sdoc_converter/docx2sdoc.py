import uuid
import requests
import json
import logging
import xml.etree.ElementTree as ET

from io import BytesIO, StringIO
from xml.etree import ElementTree

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

from seadoc_converter.config import SEAHUB_SERVICE_URL
from seadoc_converter.converter.utils import gen_jwt_auth_header


# Global
doc = None
g_doc_uuid = None


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


def parse_block_contents(items):
    empty_elem = {'id': get_random_id(), 'text': ''}
    sdoc_children = []
    for item in items:
        if isinstance(item, Run):
            xmlstr = str(item.element.xml)
            if 'pic:pic' in xmlstr:
                my_namespaces = dict([node for _, node in ElementTree.iterparse(StringIO(xmlstr), events=['start-ns'])])
                root = ET.fromstring(xmlstr)
                for pic in root.findall('.//pic:pic', my_namespaces):
                    cNvPr_elem = pic.find("pic:nvPicPr/pic:cNvPr", my_namespaces)
                    name_attr = cNvPr_elem.get("name")
                    blip_elem = pic.find("pic:blipFill/a:blip", my_namespaces)
                    embed_attr = blip_elem.get('{http://schemas.openxmlformats.org/officeDocument/2006/relationships}embed')
                document_part = doc.part
                image_part = document_part.related_parts[embed_attr]

                upload_link = f"{SEAHUB_SERVICE_URL}/api/v2.1/seadoc/upload-image/{g_doc_uuid}/"
                headers = gen_jwt_auth_header({
                    'file_uuid': g_doc_uuid,
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
                    sdoc_children.extend([empty_elem, img_struct, empty_elem])
                else:
                    logger.error(upload_link)
                    logger.error(headers)
                    logger.error(resp.__dict__)

            if text := item.text:
                sdoc_children.append(
                    {
                        'id': get_random_id(),
                        'text': text,
                        'bold': getattr(item, 'bold', False),
                        'italic': getattr(item, 'italic', False),
                        'underline': getattr(item, 'underline', False),
                    }
                )
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


def parse_heading(content_items, header_level):
    sdoc_children = parse_block_contents(content_items)
    return {
        'type': header_level,
        'children': sdoc_children,
        'id': get_random_id()
    }


def parse_paragraph(content_items):
    sdoc_children = parse_block_contents(content_items)
    return {
        'type': 'paragraph',
        'children': sdoc_children,
        'id': get_random_id()
    }


def parse_list(content_items, list_type):
    children_list = [
        {
            'id': get_random_id(),
            'type': 'list_item',
            'children': 
                [{
                'id': get_random_id(),
                'type': 'paragraph',
                'children': parse_block_contents(content_items)
            }]
        }
    ]
    return {'type': list_type, 'id': get_random_id(), 'children': children_list}


def parse_table(table):
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
            cell_content = parse_block_contents(para.iter_inner_content())
            table_cell = {
                'id': get_random_id(),
                'type': 'table_cell',
                'children': cell_content
            }
            table_row_body['children'].append(table_cell)

        children_list.append(table_row_body)
    return table_sdoc


def parse_quote(content_items):
    children_sdoc = [{
        'id': get_random_id(),
        'type': 'paragraph',
        'children': parse_block_contents(content_items)
    }]
    return {'id': get_random_id(), 'type': 'blockquote', 'children': children_sdoc}


def merge_ordered_lists(children_list):
    merged_list = []
    current_child = None

    for child in children_list:
        if child['type'] == 'unordered_list':
            if current_child and current_child['type'] == 'unordered_list':
                current_child['children'].extend(child['children'])
            else:
                if current_child:
                    merged_list.append(current_child)
                current_child = child
        elif child['type'] == 'ordered_list':
            if current_child and current_child['type'] == 'ordered_list':
                current_child['children'].extend(child['children'])
            else:
                if current_child:
                    merged_list.append(current_child)
                current_child = child
        else:
            if current_child:
                merged_list.append(current_child)
                current_child = None
            merged_list.append(child)

    if current_child:
        merged_list.append(current_child)

    return merged_list


def docx2sdoc(docx, username, doc_uuid, **kwargs):
    children_list = []
    # Fix according to: https://github.com/python-openxml/python-docx/issues/1105s
    _SerializedRelationships.load_from_xml = load_from_xml_v2

    global doc
    global g_doc_uuid
    g_doc_uuid = doc_uuid
    doc = Document(BytesIO(docx))

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
    for block in iter_block_items(doc):
        style = block.style.name
        if style in styles_map:
            children_list.append(parse_heading(block.iter_inner_content(), styles_map[style]))
        elif style == 'Normal':
            children_list.append(parse_paragraph(block.iter_inner_content()))
        elif style == 'List Bullet':
            children_list.append(parse_list(block.iter_inner_content(), 'unordered_list'))
        elif style == 'List Number':
            children_list.append(parse_list(block.iter_inner_content(), 'ordered_list'))        
        elif style == 'Normal Table':
            children_list.append(parse_table(block))
        elif style == 'Quote':
            children_list.append(parse_quote(block.iter_inner_content()))

    children_list = merge_ordered_lists(children_list)
    sdoc_json = {
        'cursors': {},
        'last_modify_user': username,
        'children': children_list,
        'version': 1,
        'format_version': 2,
    }
    return sdoc_json
