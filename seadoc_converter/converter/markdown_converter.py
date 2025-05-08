from html2text import HTML2Text
from seadoc_converter.converter.utils import trans_img_path_to_url

md_hander = HTML2Text(bodywidth=0) # no wrapping length


HEADER_LABEL = [
    'header1',
    'header2',
    'header3',
    'header4',
    'header5',
    'header6',
]

def _handle_text_style(json_data_text, return_null=False):
    text = json_data_text.get('text', '')
    pure_text = text
    bold = json_data_text.get('bold')
    italic = json_data_text.get('italic')

    if italic:
        text = "_%s_" % text
    if bold:
        text = "**%s**" % text

    if (not text) and return_null:
        text = '.'
    return text, pure_text

# sdoc 2 html dom
# 1. header
def _handle_header_dom(header_json, header_type):
    output = ''
    for child in header_json['children']:
        if 'text' in child:
            output += child.get('text')
        else:
            child_type = child.get('type')
            if child_type == 'link':
                output += _handle_link_dom(child)

    tag = {
        "header1": "<h1>%s</h1>",
        "header2": "<h2>%s</h2>",
        "header3": "<h3>%s</h3>",
        "header4": "<h4>%s</h4>",
        "header5": "<h5>%s</h5>",
        "header6": "<h6>%s</h6>",

    }.get(header_type)
    return tag % output

# 2 image
def _handle_img_dom(img_json, doc_uuid=''):

    output = ''
    url = img_json.get('data', {}).get('src')
    if doc_uuid:
        url = trans_img_path_to_url(url, doc_uuid)

    output += '<img src="%s">' % url
    return output


# 3 list including ordered / unordered list
def _handle_list_dom(list_json, indent_level=0, ordered=False):
    '''
    list_json: list json data
    indent_level: indent level
    ordered: whether the list is ordered
    '''
    result = []
    
    for index, list_item in enumerate(list_json['children'], 1):
        item_eles = list_item['children']
        current_line = '    ' * indent_level  # Use 4 Spaces as an indent
        
        # add mark according to list type
        if ordered:
            current_line += f"{index}. "
        else:
            current_line += "* "
            
        has_added_current_line = False
            
        # handle current line
        for lic in item_eles:
            if lic.get('type') == 'paragraph':
                for item in lic['children']:
                    if 'text' in item:
                        current_line += _handle_text_style(item)[0]
                    else:
                        item_type = item.get('type')
                        if item_type == 'link':
                            text_name = item['children'][0]['text']
                            text_url = item.get('href')
                            current_line += f"[{text_name}]({text_url})"
                
                if not has_added_current_line:
                    result.append(current_line)
                    has_added_current_line = True
                
            # handle sub list
            elif lic.get('type') in ['ordered_list', 'unordered_list']:
                if not has_added_current_line and current_line.strip() != ('* ' if not ordered else f"{index}. "):
                    result.append(current_line)
                    has_added_current_line = True
                    
                # recursive handle sub list
                sub_list = _handle_list_dom(
                    lic, 
                    indent_level + 1, 
                    ordered=(lic.get('type') == 'ordered_list')
                )
                result.extend(sub_list)
                
    return result

# 4 checkbox
def _handle_check_list_dom(check_list_json):
    output = ""
    checked = check_list_json.get('checked')
    for child in check_list_json['children']:
        if 'text' in child:
            output += _handle_text_style(child)[0]
        else:
            child_type = child.get('type')
            if child_type == 'link':
                output += _handle_link_dom(child)

    if checked:
        output = "<p><span>* [x] %s</span></p>" % output
    else:
        output = "<p><span>* [ ] %s</span></p>" % output

    return output

# 5 blockquote
def _handle_blockquote_dom(blockquote_json):
    output = ""
    for child in blockquote_json['children']:
        child_type = child.get('type')
        if child_type in ['ordered_list', 'unordered_list']:
            output += _handle_list_dom(child, '', child_type == 'ordered_list')

        if child_type == 'link':
            text_name = child['children'][0]['text']
            text_url = child.get('href')
            output += "<a href='%s'><span>%s</span></a>" % (text_url, text_name)

        if child_type == 'paragraph':
            output += '%s' % _handle_pagragh_dom(child)

        if child_type == 'check_list_item':
            output += '%s' % _handle_check_list_dom(child)

        if child_type == 'image':
            output += _handle_img_dom(child)

        if 'text' in child:
            text = child.get('text')
            text_list = text.split("\n")
            output += ''.join(['<p><span>%s</span></p>' % t for t in text_list if t.strip()])

    tag = "<blockquote>%s</blockquote>" % output
    return tag

# 6 url link
def _handle_link_dom(link_json):
    href = link_json.get('href')
    link_child = link_json['children'][0]

    res = "<a href='%s'><span>%s</span></a>" % (href, link_child.get('text'))
    return res


# 7 pagragh
def _handle_pagragh_dom(pagragh_json, doc_uuid=''):
    output = ''
    for child in pagragh_json['children']:
        if 'text' in child:
            output += _handle_text_style(child)[0]
        else:
            child_type = child.get('type')
            if child_type == 'link':
                output += _handle_link_dom(child)
            if child_type == 'image':
                output += _handle_img_dom(child, doc_uuid)


    result = "<p><span>%s</span></p>" % output
    return result.replace("\n", "")



def _handle_table_cell_dom(table_cell_json):
    output = ''
    for child in table_cell_json['children']:
        if 'text' in child:
            text, _ = _handle_text_style(child)
            # replace newline with space
            output += text.replace('\n', ' ')
        else:
            child_type = child.get('type')
            if child_type == 'link':
                text_name = child['children'][0]['text']
                text_url = child.get('href')
                output += f"[{text_name}]({text_url})"

    return output.strip()


#  html2markdown
def handle_header(header_json, header_type):
    dom = _handle_header_dom(header_json, header_type)
    return md_hander.handle(dom)


def handle_img(img_json):
    dom = _handle_img_dom(img_json)
    return dom


def handle_check_list(check_list_json):
    return md_hander.handle(_handle_check_list_dom(check_list_json))


def handle_paragraph(paragraph_json, doc_uuid=''):
    dom = _handle_pagragh_dom(paragraph_json, doc_uuid)
    return md_hander.handle(dom)


def handle_list(json_data, ordered=False):
    # return processed markdown text directly
    lines = _handle_list_dom(json_data, 0, ordered)
    return '\n'.join(lines)


def handle_codeblock(code_bloc_json):
    lang = code_bloc_json.get('language', '')
    output = ""
    for child in code_bloc_json.get('children'):
        if 'children' in child:
            output += "%s\n" % child.get('children', '')[0].get('text')
    return "```%s\n%s```" % (lang, output)


def handle_blockquote(json_data):
    html = _handle_blockquote_dom(json_data)
    md = md_hander.handle(html)
    return md


def handle_table(table_json):
    if not table_json['children']:
        return '\n'
        
    rows = []
    table_rows = table_json['children']
    
    # get all rows and actual column count
    max_cols = 0
    all_rows = []
    
    # first scan: determine actual column count and save all rows
    for row in table_rows:
        row_contents = []
        for cell in row['children']:
            content = _handle_table_cell_dom(cell).strip()
            if content.endswith('+'):
                content = content + ' '  # add space after "+"
            row_contents.append(content)
        # update max column count, no longer filter empty rows
        max_cols = max(max_cols, len(row_contents))
        all_rows.append(row_contents)
    
    # if column count is 0, return empty line
    if max_cols == 0:
        return '\n'
    
    # handle header
    header_row = all_rows[0]
    header_cells = []
    for i in range(max_cols):
        content = header_row[i] if i < len(header_row) else ' '
        header_cells.append(content or ' ')
    rows.append('| ' + ' | '.join(header_cells) + ' |')
    
    # add separator line
    rows.append('| ' + ' | '.join(['---'] * max_cols) + ' |')
    
    # handle all data rows, including empty rows
    for row_cells in all_rows[1:]:
        formatted_cells = []
        for i in range(max_cols):
            content = row_cells[i] if i < len(row_cells) else ' '
            formatted_cells.append(content or ' ')
        rows.append('| ' + ' | '.join(formatted_cells) + ' |')
    
    return '\n' + '\n'.join(rows) + '\n'


def handle_callout(json_data):
    children = json_data.get('children')
    callout = ''

    for child in children:
        output = handle_paragraph(child)
        callout += output
    return callout


def json2md(json_data, doc_uuid=''):
    doc_type = json_data.get('type')
    markdown_output = ''
    if doc_type in HEADER_LABEL:
        output = handle_header(json_data, doc_type)
        markdown_output += output

    if doc_type == 'check_list_item':
        output = handle_check_list(json_data)
        markdown_output += output

    if doc_type == 'paragraph':
        output = handle_paragraph(json_data, doc_uuid)
        markdown_output += output

    if doc_type == 'code_block':
        output = handle_codeblock(json_data)
        markdown_output += output

    if doc_type == 'table':
        output = handle_table(json_data)
        markdown_output += output

    if doc_type == 'unordered_list':
        output = handle_list(json_data)
        markdown_output += output

    if doc_type == 'ordered_list':
        output = handle_list(json_data, ordered=True)
        markdown_output += output

    if doc_type == 'blockquote':
        output = handle_blockquote(json_data)
        markdown_output += output

    if doc_type == 'callout':
        output = handle_callout(json_data)
        markdown_output += output

    return markdown_output

def sdoc2md(json_tree, doc_uuid=''):
    results = []
    for sub in json_tree.get('elements'):
        results.append(json2md(sub, doc_uuid))

    markdown_text = "\n".join(results)
    return markdown_text
