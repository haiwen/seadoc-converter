# -*- coding: utf-8 -*-
import json
import html as html_module
import re
from io import BytesIO

import matplotlib
import matplotlib.pyplot as plt
from pygments import highlight
from pygments.formatters import HtmlFormatter
from pygments.lexers import get_lexer_by_name
from pygments.util import ClassNotFound
from seadoc_converter.converter.utils import trans_img_path_to_url, \
        trans_video_path_to_url, trans_wiki_page_id_to_url

matplotlib.use('Agg')


HEADER_CLASS_DICT = {
    'header1': 'sdoc-header-1',
    'header2': 'sdoc-header-2',
    'header3': 'sdoc-header-3',
    'header4': 'sdoc-header-4',
    'header5': 'sdoc-header-5',
    'header6': 'sdoc-header-6',
    'toggle_header1': 'sdoc-header-1',
    'toggle_header2': 'sdoc-header-2',
    'toggle_header3': 'sdoc-header-3',
    'toggle_header4': 'sdoc-header-4',
    'toggle_header5': 'sdoc-header-5',
    'toggle_header6': 'sdoc-header-6',
}


PYGMENTS_LANGUAGE_MAP = {
    'plaintext': 'text',
    'bash': 'bash',
    'css': 'css',
    'c': 'c',
    'cpp': 'cpp',
    'csharp': 'csharp',
    'go': 'go',
    'html': 'html',
    'javascript': 'javascript',
    'java': 'java',
    'json': 'json',
    'php': 'php',
    'python': 'python',
    'ruby': 'ruby',
    'sql': 'sql',
    'swift': 'swift',
    'typescript': 'typescript',
    'xml': 'xml',
    'yaml': 'yaml',
}


# util function
def escape_html(value):
    return html_module.escape(str(value), quote=True)


def indent_html(value, indent=' ' * 4):
    return ''.join(
        f'{indent}{line}' if line.strip() else line
        for line in value.splitlines(True)
    )


def normalize_formula(formula):
    return ' '.join(str(formula).replace('\u200b', ' ').split())


def get_code_line_text(sdoc_json):
    return ''.join(
        str(child.get('text', ''))
        for child in sdoc_json.get('children', [])
        if isinstance(child, dict)
    )


def preserve_code_line_indentation(code_line, highlighted_line):
    leading_whitespace = re.match(r'^[ \t]+', code_line)
    if not leading_whitespace:
        return highlighted_line

    prefix = leading_whitespace.group(0)
    return prefix.replace(' ', '&nbsp;').replace('\t', '&nbsp;' * 4) + highlighted_line.lstrip()


def highlight_code_block_lines(sdoc_json):
    language = sdoc_json.get('language', '')
    lexer_name = PYGMENTS_LANGUAGE_MAP.get(language)
    if not lexer_name:
        return None

    code_lines = [
        get_code_line_text(child)
        for child in sdoc_json.get('children', [])
        if child.get('type') == 'code_line'
    ]

    if not code_lines:
        return []

    leading_blank_lines = 0
    for code_line in code_lines:
        if code_line:
            break
        leading_blank_lines += 1

    trailing_blank_lines = 0
    for code_line in reversed(code_lines):
        if code_line:
            break
        trailing_blank_lines += 1

    trimmed_code_lines = code_lines[leading_blank_lines:len(code_lines) - trailing_blank_lines or None]
    if not trimmed_code_lines:
        return code_lines

    try:
        lexer = get_lexer_by_name(lexer_name)
        formatter = HtmlFormatter(nowrap=True, classprefix='pg-')
        highlighted_html = highlight('\n'.join(trimmed_code_lines), lexer, formatter)
    except ClassNotFound:
        return None

    highlighted_lines = highlighted_html.split('\n')
    highlighted_lines = ([''] * leading_blank_lines) + highlighted_lines + ([''] * trailing_blank_lines)
    if len(highlighted_lines) < len(code_lines):
        highlighted_lines.extend([''] * (len(code_lines) - len(highlighted_lines)))

    return [
        preserve_code_line_indentation(code_line, highlighted_lines[index])
        for index, code_line in enumerate(code_lines)
    ]


def formula_to_svg(formula):
    formula = normalize_formula(formula)
    if formula.startswith('$') and formula.endswith('$'):
        latex_formula = formula
    else:
        latex_formula = f'${formula}$'

    fig = plt.figure(figsize=(0.01, 0.01))
    fig.patch.set_alpha(0)
    fig.text(
        0,
        0,
        latex_formula,
        fontsize=18,
        color='black',
        ha='left',
        va='bottom',
    )

    buffer = BytesIO()
    try:
        fig.savefig(
            buffer,
            format='svg',
            bbox_inches='tight',
            pad_inches=0.1,
            transparent=True,
        )
    finally:
        plt.close(fig)

    svg = buffer.getvalue().decode('utf-8')
    buffer.close()
    return svg[svg.find('<svg'):].strip()


# render function
def render_blockquote(sdoc_json, doc_uuid='', parent_id='', publish_url=''):
    """
    sdoc:
    {
        "id": "FF_7ptGzQcKA3AoRqxKAyQ",
        "type": "blockquote",
        "children": []
    }

    html:
    <blockquote
        data-id="FF_7ptGzQcKA3AoRqxKAyQ"
        data-slate-node="element"
        class="sdoc-drag-cover"
        data-root="true"
    >
    </blockquote>
    """

    ele_id = escape_html(sdoc_json['id'])

    children_html = indent_html("".join(
        render_node(child, doc_uuid=doc_uuid, parent_id=ele_id, publish_url=publish_url)
        for child in sdoc_json.get('children', [])
    ))

    html = f"""
    <blockquote
        data-id="{ele_id}"
        data-slate-node="element"
        class="sdoc-drag-cover"
        data-root="true"
    >
        {children_html}
    </blockquote>
    """

    return html


def render_table_cell(sdoc_json, doc_uuid='', parent_id='', publish_url=''):
    """
    sdoc:
    {
        "id": "bfmP84cjQpifBDAC9tKGaQ",
        "type": "table_cell",
        "children": [
            {
                "text": "123",
                "id": "Ww-91tMXRtS7HsBrY7o_Pg"
            }
        ],
        "style": {
            "background_color": "#FF0000",
            "text_align": "center",
            "alignItems": "center"
        },
        "inherit_style": {},
        "rowspan": 1,
        "colspan": 1
    },

    html:
    <div
        data-slate-node="element"
        class="table-cell"
        data-id="bfmP84cjQpifBDAC9tKGaQ"
        style="align-items: center; text-align: center; background-color: #FF0000; border-top: 1px solid rgb(221, 221, 221); border-left: 1px solid rgb(221, 221, 221); grid-area: 1 / 1 / span 1 / span 1;"
    >
        <div class="sdoc-cell-container">
        </div>
    </div>
    """

    ele_id = escape_html(sdoc_json['id'])
    row_index = escape_html(sdoc_json.get('_row_index', 1))
    col_index = escape_html(sdoc_json.get('_col_index', 1))
    rowspan = escape_html(sdoc_json.get('rowspan', 1))
    colspan = escape_html(sdoc_json.get('colspan', 1))
    style = sdoc_json.get('style', {})

    style_parts = []
    align_items = style.get('alignItems')
    if align_items:
        style_parts.append(f'align-items: {escape_html(align_items)};')

    text_align = style.get('text_align')
    if text_align:
        style_parts.append(f'text-align: {escape_html(text_align)};')

    background_color = style.get('background_color')
    if background_color:
        style_parts.append(f'background-color: {escape_html(background_color)};')

    if sdoc_json.get('is_combined'):
        style_parts.append('display: none;')

    if row_index == '1' and col_index == '1':
        style_parts.append('border-top-width: 1px;')
        style_parts.append('border-top-style: solid;')
        style_parts.append('border-left-width: 1px;')
        style_parts.append('border-left-style: solid;')
    elif row_index == '1':
        style_parts.append('border-top-width: 1px;')
        style_parts.append('border-top-style: solid;')
    elif col_index == '1':
        style_parts.append('border-left-width: 1px;')
        style_parts.append('border-left-style: solid;')

    style_parts.append(
        f'grid-area: {escape_html(row_index)} / {escape_html(col_index)} / span {rowspan} / span {colspan};'
    )

    inline_style = ' '.join(style_parts)

    if sdoc_json.get('is_combined'):
        text_id = escape_html(sdoc_json.get('children', [{}])[0].get('id', ''))
        children_html = """
        <span data-slate-node="text">
            <span
                data-id="{text_id}"
                data-slate-leaf="true"
                class="id"
                style="padding-left: 0.1px;"
            >
                <span data-slate-zero-width="n" data-slate-length="0">
                    <br>
                </span>
            </span>
        </span>
        """.format(text_id=text_id)
    else:
        children_html = indent_html(''.join(
            render_node(child, doc_uuid=doc_uuid, parent_id=ele_id, publish_url=publish_url)
            for child in sdoc_json.get('children', [])
        ))

    html = f"""
    <div
        data-slate-node="element"
        class="table-cell"
        data-id="{ele_id}"
        style="{inline_style}"
    >
        <div class="sdoc-cell-container">
            {children_html}
        </div>
    </div>
    """

    return html


def render_table_row(sdoc_json, doc_uuid='', parent_id='', publish_url=''):
    """
    sdoc:
    {
        "id": "A7_SdVe0QTyu1kKKiQ96WQ",
        "type": "table_row",
        "children": [
            {
                "id": "bfmP84cjQpifBDAC9tKGaQ",
                "type": "table_cell",
                "children": [
                    {
                        "text": "123",
                        "id": "Ww-91tMXRtS7HsBrY7o_Pg"
                    }
                ],
                "style": {},
                "inherit_style": {}
            }
        ],
        "style": {
            "min_height": 43
        }
    },

    html:
    <div hidden="" data-id="A7_SdVe0QTyu1kKKiQ96WQ"></div>
    <div
        data-slate-node="element"
        class="table-cell"
        data-id="bfmP84cjQpifBDAC9tKGaQ"
        style="border-top: 1px solid rgb(221, 221, 221); border-left: 1px solid rgb(221, 221, 221); grid-area: 1 / 1 / span 1 / span 1;"
    >
        <div class="sdoc-cell-container">
        </div>
    </div>
    """

    ele_id = escape_html(sdoc_json['id'])
    row_index = escape_html(sdoc_json.get('_row_index', 1))

    cell_html = []
    for index, child in enumerate(sdoc_json.get('children', []), start=1):
        if child.get('type') == 'table_cell':
            cell_html.append(render_table_cell(
                {**child, '_row_index': row_index, '_col_index': index},
                doc_uuid=doc_uuid,
                parent_id=ele_id,
                publish_url=publish_url,
            ))
        else:
            cell_html.append(render_node(child, doc_uuid=doc_uuid, parent_id=ele_id, publish_url=publish_url))

    children_html = indent_html(''.join(cell_html))

    html = f"""
    <div hidden="" data-id="{ele_id}"></div>
    {children_html}
    """

    return html


def render_table(sdoc_json, doc_uuid='', parent_id='', publish_url=''):
    """
    sdoc:
    {
        "id": "J8Kc6OPLTP-tXKdF0XbVPg",
        "type": "table",
        "children": [],
        "columns": [
            {
                "width": 279
            },
            {
                "width": 279
            },
            {
                "width": 279
            }
        ],
        "ui": {
            "alternate_highlight": false
        },
        "style": {
            "gridTemplateColumns": "repeat(3, 279px)",
            "gridAutoRows": "minmax(42px, auto)"
        }
    },

    html:
    <div
        data-slate-node="element"
        class="sdoc-table-wrapper position-relative sdoc-drag-cover scroll"
        data-root="true"
        style="max-width: 837px;"
    >
        <div class="sdoc-table-scroll-wrapper scroll-at-left">
            <div
                class="sdoc-table-container sdoc-drag-cover"
                data-id="J8Kc6OPLTP-tXKdF0XbVPg"
                style="grid-template-columns: 279px 279px 279px;
                       grid-auto-rows: minmax(44px, auto) minmax(124px, auto);"
            >
            </div>
        </div>
    </div>
    """

    ele_id = escape_html(sdoc_json['id'])

    column_width_total = sum(
        column.get('width', 0) for column in sdoc_json.get('columns', [])
    )
    wrapper_style = f"max-width: {column_width_total}px;"

    grid_template_columns = ' '.join(
        f"{escape_html(column['width'])}px"
        for column in sdoc_json.get('columns', [])
    )
    grid_auto_rows = ' '.join(
        f"minmax({escape_html(child.get('style', {}).get('min_height', 42))}px, auto)"
        for child in sdoc_json.get('children', [])
        if child.get('type') == 'table_row'
    )
    container_style = (
        f"grid-template-columns: {grid_template_columns}; "
        f"grid-auto-rows: {grid_auto_rows};"
    )

    row_html = []
    for index, child in enumerate(sdoc_json.get('children', []), start=1):
        if child.get('type') == 'table_row':
            row_html.append(render_table_row(
                {**child, '_row_index': index},
                doc_uuid=doc_uuid,
                parent_id=ele_id,
            ))
        else:
            row_html.append(render_node(child, doc_uuid=doc_uuid, parent_id=ele_id, publish_url=publish_url))

    children_html = indent_html(''.join(row_html))

    html = f"""
    <div
        data-slate-node="element"
        class="sdoc-table-wrapper position-relative sdoc-drag-cover scroll"
        data-root="true"
        style="{wrapper_style}"
    >
        <div class="sdoc-table-scroll-wrapper scroll-at-left">
            <div
                class="sdoc-table-container sdoc-drag-cover"
                data-id="{ele_id}"
                style="{container_style}"
            >
                {children_html}
            </div>
        </div>
    </div>
    """

    return html


def render_column(sdoc_json, doc_uuid='', parent_id='', publish_url=''):
    """
    sdoc:
    {
        "id": "NxICr-lzQrCXqWOIWCajgg",
        "type": "column",
        "width": 444,
        "children": []
    },

    html:
    <div
        data-slate-node="element"
        class="column"
        data-id="NxICr-lzQrCXqWOIWCajgg"
        style="width: 443.992px;"
    >
        <div class="sdoc-column-container">
        </div>
    </div>
    """

    ele_id = escape_html(sdoc_json['id'])
    width = escape_html(sdoc_json['width'])

    children_html = indent_html("".join(
        render_node(child, doc_uuid=doc_uuid, parent_id=ele_id, publish_url=publish_url)
        for child in sdoc_json.get('children', [])
    ))

    html = f"""
    <div
        data-slate-node="element"
        class="column"
        data-id="{ele_id}"
        style="width: {width}px;"
    >
        <div class="sdoc-column-container">
            {children_html}
        </div>
    </div>
    """

    return html


def render_multi_column(sdoc_json, doc_uuid='', parent_id='', publish_url=''):
    """
    sdoc:
    {
        "id": "Q8bYTVIxS32QcnHW5LBPmg",
        "type": "multi_column",
        "children": [],
        "column": [
            {
                "key": "NxICr-lzQrCXqWOIWCajgg",
                "width": 443.9960982468474
            },
            {
                "key": "As2UnNDBSbqxDXuc60TVgw",
                "width": 443.9960982468474
            }
        ],
        "style": {
            "gridTemplateColumns": "443.9960982468474px 443.9960982468474px"
        }
    },

    html:
    <div
        data-slate-node="element"
        data-root="true"
        class="sdoc-multicolumn-wrapper position-relative"
        style="max-width: 100%;"
    >
        <div
            class="sdoc-multicolumn-container"
            data-id="Q8bYTVIxS32QcnHW5LBPmg"
            style="grid-template-columns: 443.992px 443.992px;"
        >
        </div>
    </div>
    """

    ele_id = escape_html(sdoc_json['id'])
    grid_template_columns = escape_html(sdoc_json['style']['gridTemplateColumns'])

    children_html = indent_html("".join(
        render_node(child, doc_uuid=doc_uuid, parent_id=ele_id, publish_url=publish_url)
        for child in sdoc_json.get('children', [])
    ))

    html = f"""
    <div
        data-slate-node="element"
        data-root="true"
        class="sdoc-multicolumn-wrapper position-relative"
        style="max-width: 100%;"
    >
        <div
            class="sdoc-multicolumn-container"
            data-id="{ele_id}"
            style="grid-template-columns: {grid_template_columns};"
        >
            {children_html}
        </div>
    </div>
    """

    return html


def render_formula(sdoc_json, doc_uuid='', parent_id='', publish_url=''):
    """
    sdoc:
    {
        "id": "BlP7_PYxTV2WAnRTeWZlEQ",
        "type": "formula",
        "data": {
            "formula": "gongshi"
        },
        "children": []
    },

    html:
    <div
        data-slate-node="element"
        data-slate-void="true"
        class="sdoc-block-formula"
        data-root="true"
        data-id="BlP7_PYxTV2WAnRTeWZlEQ"
    >
        <div>
            <div class="python-math-jax" contenteditable="false">
            </div>
        </div>
    </div>
    """

    ele_id = escape_html(sdoc_json['id'])

    formula = sdoc_json.get('data', {}).get('formula', '')
    normalized_formula = normalize_formula(formula)
    try:
        formula_html = indent_html(formula_to_svg(normalized_formula))
    except ValueError:
        fallback_formula = escape_html(normalized_formula)
        formula_html = f'<span>{fallback_formula}</span>'

    html = f"""
    <div
        data-slate-node="element"
        data-slate-void="true"
        class="sdoc-block-formula"
        data-root="true"
        data-id="{ele_id}"
    >
        <div>
            <div class="python-math-jax" contenteditable="false">
                {formula_html}
            </div>
        </div>
    </div>
    """

    return html


def render_callout(sdoc_json, doc_uuid='', parent_id='', publish_url=''):
    """
    sdoc:
    {
        "id": "M3oI_sXsQP2vXmEtNZvBwA",
        "type": "callout",
        "style": {
            "background_color": "#fef7e0"
        },
        "children": []
    }

    html:
    <div
        data-slate-node="element"
        class="sdoc-callout-white-wrapper"
        data-root="true"
        data-id="M3oI_sXsQP2vXmEtNZvBwA"
    >
        <div
            class="sdoc-callout-container"
            style="background-color: rgb(254, 247, 224); border-color: rgb(250, 236, 179);">
            <div class="callout-content">
            </div>
        </div>
    </div>
    """

    ele_id = escape_html(sdoc_json['id'])
    background_color = escape_html(sdoc_json['style']['background_color'])
    inline_style = f"background-color: {background_color}; border-color: transparent;"

    children_html = indent_html("".join(
        render_node(child, doc_uuid=doc_uuid, parent_id=ele_id, publish_url=publish_url)
        for child in sdoc_json.get('children', [])
    ))

    html = f"""
    <div
        data-slate-node="element"
        class="sdoc-callout-white-wrapper"
        data-root="true"
        data-id="{ele_id}"
    >
        <div
            class="sdoc-callout-container"
            style="{inline_style}">
            <div class="callout-content">
                {children_html}
            </div>
        </div>
    </div>
    """

    return html


def render_code_block(sdoc_json, doc_uuid='', parent_id='', publish_url=''):
    """
    sdoc:
    {
        "id": "NXSA3lufS9ep7ZVcvoE9LA",
        "type": "code_block",
        "language": "plaintext",
        "style": {
            "white_space": "nowrap"
        },
        "children": []
    },

    html:
    <div
        data-id="NXSA3lufS9ep7ZVcvoE9LA"
        data-slate-node="element"
        class="sdoc-code-block-container sdoc-drag-cover"
        data-root="true"
    >
        <pre class="sdoc-code-block-pre">
            <code class="sdoc-code-block-code sdoc-code-no-wrap hide-code">
            </code>
        </pre>
    </div>
    """

    ele_id = escape_html(sdoc_json['id'])
    language = sdoc_json.get('language')
    highlighted_lines = highlight_code_block_lines(sdoc_json)

    rendered_children = []
    code_line_index = 0
    for child in sdoc_json.get('children', []):
        if child.get('type') == 'code_line':
            code_line_id = escape_html(child['id'])
            language_class = f' language-{escape_html(language)}' if language else ''
            if highlighted_lines is not None and code_line_index < len(highlighted_lines):
                code_line_html = indent_html(highlighted_lines[code_line_index])
            else:
                code_line_html = indent_html("".join(
                    render_node(grandchild, doc_uuid=doc_uuid, parent_id=code_line_id, publish_url=publish_url)
                    for grandchild in child.get('children', [])
                ))
            if not code_line_html.strip():
                code_line_html = indent_html('<br>')
            code_line_index += 1
            rendered_children.append(f"""
            <div
                data-id="{code_line_id}"
                data-slate-node="element"
                class="sdoc-code-line{language_class}"
            >
                {code_line_html}
            </div>
            """)
        else:
            rendered_children.append(render_node(child, doc_uuid=doc_uuid, parent_id=ele_id, publish_url=publish_url))

    children_html = indent_html("".join(rendered_children))

    html = f"""
    <div
        data-id="{ele_id}"
        data-slate-node="element"
        class="sdoc-code-block-container sdoc-drag-cover"
        data-root="true"
    >
        <pre class="sdoc-code-block-pre">
            <code class="sdoc-code-block-code sdoc-code-no-wrap">
                {children_html}
            </code>
        </pre>
    </div>
    """

    return html


def render_video(sdoc_json, doc_uuid='', parent_id='', publish_url=''):
    """
    sdoc:
    {
        "id": "F0Ygq5mzStmszuJsMk4ZFg",
        "type": "video",
        "children": [],
        "data": {
            "src": "/video-ZiIyRhNgTjCaLobAURsCog.mov",
            "name": "Screen Recording 2026-05-14 at 14.46.08.mov",
            "size": 2061760,
            "is_embeddable_link": false
        }
    },

    {
        "id": "a6gropsUSWOHG9D9ZZSfxQ",
        "type": "video",
        "children": [
            {
                "text": "",
                "id": "cokyl7fdSeaBtoqSF_rdVA"
            }
        ],
        "data": {
            "src": "https://player.bilibili.com/player.html?bvid=BV13QV76BEsi&autoplay=0",
            "name": "https://www.bilibili.com/video/BV13QV76BEsi/",
            "size": null,
            "is_embeddable_link": true
        }
    },

    html:
    <div
        class="sdoc-drag-cover"
        data-slate-node="element"
        data-slate-void="true"
        data-root="true"
        contenteditable="true"
    >
        <div
           class="sdoc-video-children-wrapper"
           contenteditable="false"
           style="user-select: none; pointer-events: none;"
        >
            <div data-slate-spacer="true" style="height: 0px; color: transparent; outline: none; position: absolute;">
                <span data-slate-node="text">
                    <span data-slate-leaf="true">
                        <span data-slate-zero-width="z" data-slate-length="0"></span>
                    </span>
                </span>
            </div>
        </div>
        <div
           data-id="F0Ygq5mzStmszuJsMk4ZFg"
           class="sdoc-video-wrapper"
           contenteditable="false"
           style="display: flex;"
        >
            <div class="sdoc-video-inner" style="visibility: visible; width: 100%;">
                <video
                    class="sdoc-video-element"
                    src="https://dev.seafile.com/..."
                    controls=""
                    controlslist="nofullscreen"
                    draggable="false"
                    style="box-shadow: none; pointer-events: auto;">
                </video>
                <div
                    class="sdoc-video-play sdocfont sdoc-play"
                    contenteditable="false"
                    style="visibility: visible;">
                </div>
            </div>
        </div>
    </div>

    <div
        class="sdoc-drag-cover"
        data-slate-node="element"
        data-slate-void="true"
        data-root="true"
        contenteditable="true"
    >
        <div
           class="sdoc-video-children-wrapper"
           contenteditable="false"
           style="user-select: none; pointer-events: none;"
        >
            <div data-slate-spacer="true" style="height: 0px; color: transparent; outline: none; position: absolute;">
                <span data-slate-node="text">
                    <span data-slate-leaf="true">
                        <span data-slate-zero-width="z" data-slate-length="0"></span>
                    </span>
                </span>
            </div>
        </div>
        <div
           data-id="a6gropsUSWOHG9D9ZZSfxQ"
           class="sdoc-video-wrapper"
           contenteditable="false"
           style="display: flex;"
        >
            <div class="sdoc-video-inner" style="visibility: visible; width: 100%;">
                <iframe
                    class="sdoc-video-element"
                    title="https://player.bilibili.com/player.html?bvid=BV13QV76BEsi&amp;autoplay=0"
                    allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture" allowfullscreen=""
                    src="https://player.bilibili.com/player.html?bvid=BV13QV76BEsi&amp;autoplay=0"
                    style="height: 100%; border-width: medium; border-style: none; border-color: currentcolor; border-image: initial; box-shadow: none; pointer-events: auto;">
                </iframe>
            </div>
        </div>
    </div>
    """

    ele_id = escape_html(sdoc_json['id'])
    is_embeddable_link = sdoc_json['data']['is_embeddable_link']
    video_src = sdoc_json['data']['src']
    if not is_embeddable_link:
        video_src = trans_video_path_to_url(video_src, doc_uuid)
    video_src = escape_html(video_src)

    video_html = f"""
    <video
        class="sdoc-video-element"
        src="{video_src}"
        controls=""
        controlslist="nofullscreen"
        draggable="false"
        style="box-shadow: none; pointer-events: auto;">
    </video>
    """

    iframe_html = f"""
    <iframe
        class="sdoc-video-element"
        title="{video_src}"
        allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture" allowfullscreen=""
        src="{video_src}"
        style="height: 100%; border-width: medium; border-style: none; border-color: currentcolor; border-image: initial; box-shadow: none; pointer-events: auto;">
    </iframe>
    """

    html = f"""
    <div
        class="sdoc-drag-cover"
        data-slate-node="element"
        data-slate-void="true"
        data-root="true"
        contenteditable="true"
    >
        <div
           class="sdoc-video-children-wrapper"
           contenteditable="false"
           style="user-select: none; pointer-events: none;"
        >
            <div data-slate-spacer="true" style="height: 0px; color: transparent; outline: none; position: absolute;">
                <span data-slate-node="text">
                    <span data-slate-leaf="true">
                        <span data-slate-zero-width="z" data-slate-length="0"></span>
                    </span>
               </span>
           </div>
       </div>
       <div
           data-id="{ele_id}"
           class="sdoc-video-wrapper"
           contenteditable="false"
           style="display: flex;"
        >
           <div class="sdoc-video-inner" style="visibility: visible; width: 100%;">
            {iframe_html if is_embeddable_link else video_html}
            </div>
        </div>
    </div>
    """

    return html


def render_check_list(sdoc_json, doc_uuid='', parent_id='', publish_url=''):
    """
    sdoc:
    {
        "id": "ICSFIthGSnK5H22syGSY1A",
        "type": "check_list_item",
        "children": [
            {
                "text": "123",
                "id": "ejv7D2GbTCGzig0qJ58rUA"
            }
        ],
        "checked": true
    },
    {
        "id": "ZyYJY282SYmTbqyImMXjNw",
        "type": "check_list_item",
        "children": [
            {
                "id": "Xw7iRPsPT5upZ9JH7a_-hA",
                "text": "456"
            }
        ],
        "checked": false
    }

    html:
    <div
        data-id="ICSFIthGSnK5H22syGSY1A"
        data-slate-node="element"
        class="sdoc-checkbox-container"
        data-root="true"
    >
       <div class="sdoc-checkbox-input-wrapper">
          <input contenteditable="false"
                 class="sdoc-checkbox-input"
                 type="checkbox"
                 checked=""
          >
          <p class="sdoc-checkbox-content-container">
          </p>
       </div>
    </div>
    """

    ele_id = escape_html(sdoc_json['id'])
    checked = sdoc_json.get('checked', False)

    children_html = indent_html("".join(
        render_node(child, doc_uuid=doc_uuid, parent_id=ele_id, publish_url=publish_url)
        for child in sdoc_json.get('children', [])
    ))

    html = f"""
    <div
        data-id="{ele_id}"
        data-slate-node="element"
        class="sdoc-checkbox-container"
        data-root="true"
    >
        <div class="sdoc-checkbox-input-wrapper">
            <input contenteditable="false"
                class="sdoc-checkbox-input"
                type="checkbox"
                {'checked' if checked else ''}
                disabled
            >
            <p class="sdoc-checkbox-content-container">
                {children_html}
            </p>
        </div>
    </div>
    """

    return html


def render_ordered_list(sdoc_json, doc_uuid='', parent_id='', publish_url=''):
    """
    sdoc:
    {
        "id": "Qy7nlvGiTw6IHKdp953lLA",
        "type": "ordered_list",
        "children": []
    }

    html:
    <ol
        data-id="Qy7nlvGiTw6IHKdp953lLA"
        data-slate-node="element"
        data-root="true"
        class="list-container d-flex flex-column"
    >
    </ol>
    """

    ele_id = escape_html(sdoc_json['id'])

    children_html = indent_html("".join(
        render_node(child, doc_uuid=doc_uuid, parent_id=ele_id, publish_url=publish_url)
        for child in sdoc_json.get('children', [])
    ))

    html = f"""
    <ol
        data-id="{ele_id}"
        data-slate-node="element"
        data-root="true"
        class="list-container d-flex flex-column"
    >
        {children_html}
    </ol>
    """

    return html


def render_unordered_list(sdoc_json, doc_uuid='', parent_id='', publish_url=''):
    """
    sdoc:
    {
        "id": "SqgJrMDLQTiBX9gE_EORWw",
        "type": "unordered_list",
        "children": []
    }

    html:
    <ul
        data-id="SqgJrMDLQTiBX9gE_EORWw"
        data-slate-node="element"
        data-root="true"
        class="list-container d-flex flex-column"
    >
    </ul>
    """

    ele_id = escape_html(sdoc_json['id'])

    children_html = indent_html("".join(
        render_node(child, doc_uuid=doc_uuid, parent_id=ele_id, publish_url=publish_url)
        for child in sdoc_json.get('children', [])
    ))

    html = f"""
    <ul
        data-id="{ele_id}"
        data-slate-node="element"
        data-root="true"
        class="list-container d-flex flex-column"
    >
        {children_html}
    </ul>
    """

    return html


def render_list_item(sdoc_json, doc_uuid='', parent_id='', publish_url=''):
    """
    sdoc:
    {
        "id": "Blh6tlFITl6CuIK1-A9Unw",
        "type": "list_item",
        "children": []
    },

    html:
    <li
        data-id="Blh6tlFITl6CuIK1-A9Unw"
        data-slate-node="element"
        class=""
    >
        <span class="sdoc-li-control" contenteditable="false">
             <span class="sdoc-li-prefix sdocfont sdoc-arrow-down"></span>
             <span class="sdoc-li-divider"></span>
        </span>
        <span class="sdoc-li-content">
        </span>
    </li>
    """

    ele_id = escape_html(sdoc_json['id'])

    children_html = indent_html("".join(
        render_node(child, doc_uuid=doc_uuid, parent_id=ele_id, publish_url=publish_url)
        for child in sdoc_json.get('children', [])
    ))

    children_len = len(sdoc_json.get('children', []))

    if children_len == 1:
        html = f"""
        <li
            data-id="{ele_id}"
            data-slate-node="element"
            class=""
        >
            <span class="sdoc-li-content">
                {children_html}
            </span>
        </li>
        """
    else:
        html = f"""
        <li
            data-id="{ele_id}"
            data-slate-node="element"
            class=""
        >
            <span class="sdoc-li-control" contenteditable="false">
                <span class="sdoc-li-prefix sdocfont sdoc-arrow-down"></span>
                <span class="sdoc-li-divider"></span>
            </span>
            <span class="sdoc-li-content">
                {children_html}
            </span>
        </li>
        """

    return html


def render_toggle_header(sdoc_json, doc_uuid='', parent_id='', publish_url=''):
    """
    sdoc:
    {
        "id": "OFxmOVI3RbOFUjl5axk8Bw",
        "type": "toggle_header",
        "collapsed": false,
        "children": []
    },

    html:
    <div
      data-id="OFxmOVI3RbOFUjl5axk8Bw"
      id="OFxmOVI3RbOFUjl5axk8Bw"
      data-slate-node="element"
      class="sdoc-toggle-header-container"
      data-root="true"
    >
    </div>
    """

    ele_id = escape_html(sdoc_json['id'])

    children_html = indent_html("".join(
        render_node(child, doc_uuid=doc_uuid, parent_id=ele_id, publish_url=publish_url)
        for child in sdoc_json.get('children', [])
    ))

    html = f"""
    <div
        data-id="{ele_id}"
        id="{ele_id}"
        data-slate-node="element"
        class="sdoc-toggle-header-container"
        data-root="true"
    >
        {children_html}
    </div>
    """

    return html


def render_toggle_header_row(sdoc_json, doc_uuid='', parent_id='', publish_url=''):
    """
    sdoc:
    {
        "id": "QX1EzawRT2KVOgbGMkDmKg",
        "type": "toggle_header1",
        "children": []
    },

    html:
    <div class="sdoc-toggle-header-row">
      <span class="sdoc-toggle-header-prefix" contenteditable="false">
        <span class="sdocfont sdoc-big-drop-down"></span>
      </span>
      <div class="sdoc-toggle-header-title-wrap">
        <div
          data-id="QX1EzawRT2KVOgbGMkDmKg"
          data-slate-node="element"
          class="sdoc-toggle-header-title sdoc-header-1"
          style="font-size: 20pt;"
        >
        </div>
      </div>
    </div>
    """
    ele_id = escape_html(sdoc_json['id'])
    ele_type = sdoc_json['type']
    html_class = HEADER_CLASS_DICT[ele_type]
    inline_style = "font-size: 20pt;"

    children_html = indent_html("".join(
        render_node(child, doc_uuid=doc_uuid, parent_id=ele_id, publish_url=publish_url)
        for child in sdoc_json.get('children', [])
    ))

    html = f"""
    <div class="sdoc-toggle-header-row">
        <span class="sdoc-toggle-header-prefix" contenteditable="false">
            <span class="sdocfont sdoc-big-drop-down"></span>
        </span>
        <div class="sdoc-toggle-header-title-wrap">
            <div
                data-id="{ele_id}"
                data-slate-node="element"
                class="sdoc-toggle-header-title {html_class}"
                style="{inline_style}"
            >
                {children_html}
            </div>
        </div>
    </div>
    """

    return html


def render_toggle_content(sdoc_json, doc_uuid='', parent_id='', publish_url=''):
    """
    sdoc:
    {
        "id": "Ni-pqG4kTW2HY-SspIMrgQ",
        "type": "toggle_content",
        "children": []
    }

    html:
    <div class="sdoc-toggle-header-content-wrap">
      <div
        data-id="Ni-pqG4kTW2HY-SspIMrgQ"
        data-slate-node="element"
        class="sdoc-toggle-header-content"
      >
      </div>
    </div>
    """

    ele_id = escape_html(sdoc_json['id'])

    children_html = indent_html("".join(
        render_node(child, doc_uuid=doc_uuid, parent_id=ele_id, publish_url=publish_url)
        for child in sdoc_json.get('children', [])
    ))

    html = f"""
    <div class="sdoc-toggle-header-content-wrap">
        <div
            data-id="{ele_id}"
            data-slate-node="element"
            class="sdoc-toggle-header-content"
        >
            {children_html}
        </div>
    </div>
    """

    return html


def render_paragraph(sdoc_json, doc_uuid='', parent_id='', publish_url=''):
    """
    sdoc:
    {
        "id": "XwF8hvknTaSua2ns29oezA",
        "type": "paragraph",
        "children": []
    }

    html:
    <div
        data-id="XwF8hvknTaSua2ns29oezA"
        data-slate-node="element"
        data-root="true"
        style="padding-top: 5px; padding-bottom: 5px;"
    >
    </div>
    """

    ele_id = escape_html(sdoc_json['id'])
    inline_style = "padding-top: 5px; padding-bottom: 5px;"

    children_html = indent_html("".join(
        render_node(child, doc_uuid=doc_uuid, parent_id=ele_id, publish_url=publish_url)
        for child in sdoc_json.get('children', [])
    ))

    html = f"""
    <div
        data-id="{ele_id}"
        data-slate-node="element"
        data-root="true"
        style="{inline_style}"
    >
        {children_html}
    </div>
    """

    return html


def render_header(sdoc_json, doc_uuid='', parent_id='', publish_url=''):
    """
    sdoc:
    {
        "id": "046ae9d4-0538-4bfd-973a-d8506687ae2e",
        "type": "header1",
        "children": []
    },

    html:
    <div
        data-id="046ae9d4-0538-4bfd-973a-d8506687ae2e"
        id="046ae9d4-0538-4bfd-973a-d8506687ae2e"
        data-slate-node="element"
        class="sdoc-header-1"
        data-root="true"
        style="font-size: 20pt;"
    >
        <div class="sdoc-header-row">
            <span class="sdoc-header-collapse-prefix" contenteditable="false">
                <span class="sdocfont sdoc-big-drop-down">
                </span>
            </span>
            <div class="sdoc-header-content">
            </div>
        </div>
    </div>
    """

    ele_id = escape_html(sdoc_json['id'])
    ele_type = sdoc_json['type']
    html_class = HEADER_CLASS_DICT[ele_type]
    inline_style = "font-size: 20pt;"

    children_html = indent_html("".join(
        render_node(child, doc_uuid=doc_uuid, parent_id=ele_id, publish_url=publish_url)
        for child in sdoc_json.get('children', [])
    ))

    html = f"""
    <div
        data-id="{ele_id}"
        id="{ele_id}"
        data-slate-node="element"
        class="{html_class}"
        data-root="true"
        style="{inline_style}"
    >
        <div class="sdoc-header-row">
            <span class="sdoc-header-collapse-prefix" contenteditable="false">
                <span class="sdocfont sdoc-big-drop-down">
                </span>
            </span>
            <div class="sdoc-header-content">
                {children_html}
            </div>
        </div>
    </div>
    """

    return html


def render_embed_link(sdoc_json, doc_uuid='', parent_id='', publish_url=''):
    """
    sdoc:
    {
        "id": "P7cL3EfXQV29XVdXKGl86Q",
        "type": "embed_link",
        "link": "https://dev.seatable.cn/workspace/...",
        "link_type": "seatable",
        "children": []
    },

    html:
    <div
        data-slate-node="element"
        data-slate-void="true"
        class="sdoc-drag-cover"
        data-root="true"
        contenteditable="false"
    >
       <div class="sdoc-embed-link-container" scrolling="no" style="height: 300px; max-height: 550px;">
          <iframe class="sdoc-embed-link-element seatable" title="..." src="..."></iframe>
          <div class="iframe-overlay"></div>
       </div>
    </div>
    """

    link = escape_html(sdoc_json['link'])
    link_type = escape_html(sdoc_json['link_type'])

    html = f"""
    <div
        data-slate-node="element"
        data-slate-void="true"
        class="sdoc-drag-cover"
        data-root="true"
        contenteditable="false"
    >
        <div class="sdoc-embed-link-container" scrolling="no">
            <iframe class="sdoc-embed-link-element {link_type}" title="{link}" src="{link}"></iframe>
            <div class="iframe-overlay"></div>
        </div>
    </div>
    """

    return html


def render_link(sdoc_json, doc_uuid='', parent_id='', publish_url=''):
    """
    sdoc:
    {
        "id": "DVY_tKqpRPuM66HgH-Vx8A",
        "type": "link",
        "href": "https://seafile.com",
        "title": "link title",
        "linked_id": "",
        "linked_wiki_page_id": "",
        "children": []
    },
    {
        "id": "SHlFqBypQvmzG7ReMGpLvw",
        "type": "link",
        "href": "",
        "title": "link page",
        "linked_id": "",
        "linked_wiki_page_id": "YdoF",
        "children": []
    },
    {
        "id": "Qd0HhtJPQXqTJp_EpOExhA",
        "type": "link",
        "href": "",
        "title": "link block",
        "linked_id": "IUa95Se1QPmAceRUJvxogw",
        "linked_wiki_page_id": "",
        "children": []
    },

    html:
    <span
        class="virtual-link"
        data-slate-node="element"
        data-slate-inline="true"
    >
        <a href="https://seafile.com" title="link title" target="_blank" rel="noreferrer">
            <span data-slate-node="text">
                <span data-id="JnNHkKR_SUmy5AQeYWpXRQ" data-slate-leaf="true" class="id">
                    <span data-slate-string="true">
                        link title
                    </span>
                </span>
            </span>
        </a>
    </span>

    <span
        class="virtual-link"
        data-slate-node="element"
        data-slate-inline="true"
    >
        <a title="link page" target="_blank" rel="noreferrer">
            <span data-slate-node="text">
                <span data-id="T4xAFeFOQiKuiNGfzC_C6A" data-slate-leaf="true" class="id">
                    <span data-slate-string="true">
                        link page
                    </span>
                </span>
            </span>
        </a>
    </span>

    <span
        class="virtual-link"
        data-slate-node="element"
        data-slate-inline="true"
    >
        <a title="link block" target="_blank" rel="noreferrer">
            <span data-slate-node="text">
                <span data-id="MhzuDquxTOeSGr9hdUvevQ" data-slate-leaf="true" class="id">
                    <span data-slate-string="true">
                        link block
                    </span>
                </span>
            </span>
        </a>
    </span>
    """
    title = escape_html(sdoc_json['title'])

    href = escape_html(sdoc_json.get('href', ''))
    if not href:
        href = escape_html(sdoc_json.get('src', ''))
    if not href:
        href = escape_html(sdoc_json.get('url', ''))

    linked_id = escape_html(sdoc_json.get('linked_id', ''))
    linked_wiki_page_id = escape_html(sdoc_json.get('linked_wiki_page_id', ''))

    children_html = indent_html("".join(
        render_node(child, doc_uuid=doc_uuid, parent_id=parent_id, publish_url=publish_url)
        for child in sdoc_json.get('children', [])
    ))

    if href:
        html = f"""
        <span
            class="virtual-link"
            data-slate-node="element"
            data-slate-inline="true"
        >
            <a href="{href}" title="{title}" target="_blank" rel="noreferrer">
                {children_html}
            </a>
        </span>
        """
    elif linked_id:
        html = f"""
        <span
            class="virtual-link"
            data-slate-node="element"
            data-slate-inline="true"
        >
            <a class="sdoc-link-block" data-link-block-id="{linked_id}" title="{title}" target="_blank" rel="noreferrer">
                {children_html}
            </a>
        </span>
        """
    elif linked_wiki_page_id:
        href = trans_wiki_page_id_to_url(publish_url, linked_wiki_page_id)
        html = f"""
        <span
            class="virtual-link"
            data-slate-node="element"
            data-slate-inline="true"
        >
            <a class="sdoc-link-page" href="{href}" title="{title}" target="_blank" rel="noreferrer">
                {children_html}
            </a>
        </span>
        """

    return html


def render_file_link(sdoc_json, doc_uuid='', parent_id='', publish_url=''):
    """
    {
        "id": "U1q38n7sRpmp4SyPt7xdoA",
        "type": "file_link",
        "doc_uuid": "910affba-213c-4e32-a26b-d01b8f0f8560",
        "title": "1.txt",
        "display_type": "icon_link",
        "children": []
    },

    html:
    <span
        data-slate-node="element"
        data-slate-inline="true"
        data-slate-void="true"
        data-id="U1q38n7sRpmp4SyPt7xdoA"
        contenteditable="false"
        class="sdoc-file-link-render"
    >
       <span>
          <span class="sdoc-file-link-icon">
             <img class="file-link-img" src="https://dev.seafile.com/seahub/media/img/file/256/txt.png" alt="">
          </span>
          <span class="sdoc-file-text-link">
             <a href="..." title="1.txt">1.txt</a>
          </span>
       </span>
    </span>

    """

    ele_id = escape_html(sdoc_json['id'])
    title = escape_html(sdoc_json['title'])

    doc_uuid = sdoc_json['doc_uuid']
    icon_src = "/media/img/file/256/sdoc.png"
    file_src = f"/api/v2.1/seadoc/file/{doc_uuid}/?doc_uuid={doc_uuid}"

    html = f"""
    <span
        data-slate-node="element"
        data-slate-inline="true"
        data-slate-void="true"
        data-id="{ele_id}"
        contenteditable="false"
        class="sdoc-file-link-render"
    >
        <span>
            <span class="sdoc-file-link-icon">
                <img class="file-link-img" src="{icon_src}" alt="">
            </span>
            <span class="sdoc-file-text-link">
                <a href="{file_src}" title="{title}">{title}</a>
            </span>
        </span>
    </span>
    """

    return html


def render_wiki_link(sdoc_json, doc_uuid='', parent_id='', publish_url=''):
    """
    {
        "id": "K4-R9_yuSgmjVL7M42zbLg",
        "type": "wiki_link",
        "wiki_repo_id": "cc3fd57e-1c6b-4300-9625-d7eea65837a4",
        "page_id": "YdoF",
        "title": "New page",
        "icon": "",
        "isDir": false,
        "display_type": "icon_link",
        "children": []
    },
    """

    ele_id = escape_html(sdoc_json['id'])
    title = escape_html(sdoc_json['title'])
    page_id = sdoc_json['page_id']
    wiki_src = f"/wiki/publish/{publish_url}/{page_id}/"

    html = f"""
    <span
        data-slate-node="element"
        data-slate-inline="true"
        data-slate-void="true"
        data-id="{ele_id}"
        contenteditable="false"
        class="sdoc-file-render"
    >
        <span>
            <span class="sdoc-file-link-icon">
                <span class="sf3-font sf3-font-file"></span>
            </span>
            <span class="sdoc-file-text-link">
                <a class="sdoc-wiki-link" href="{wiki_src}" title="{title}">{title}</a>
            </span>
        </span>
    </span>
    """

    return html


def render_image(sdoc_json, doc_uuid='', parent_id='', publish_url=''):
    """
    {
        "id": "CAcDgxD-RtScHXjFhii-Mw",
        "type": "image",
        "children": [],
        "data": {
            "src": "/image-aFPg3kqiSbud1nvRsQLunw.webp"
        }
    },
    """

    # 不处理行内元素image中的children
    ele_id = escape_html(sdoc_json['id'])
    image_src = sdoc_json['data']['src']
    image_src = escape_html(trans_img_path_to_url(image_src, doc_uuid))
    parent_id = escape_html(parent_id)

    html = f"""
    <span
        data-id="{ele_id}"
        data-parent-id="{parent_id}"
        class="sdoc-image-wrapper"
        data-slate-node="element"
        data-slate-inline="true"
        data-slate-void="true"
        contenteditable="false"
    >
        <span class="sdoc-image-inner">
            <span class="sdoc-image-content">
                <span>
                    <img
                        class=""
                        src="{image_src}"
                        draggable="false"
                        alt=""
                    >
                </span>
            </span>
        </span>
    </span>
    """

    return html


def render_text(sdoc_json, doc_uuid='', parent_id='', publish_url=''):
    """
    sdoc:
    {
        "id": "GRUSC3auSAihSO7DE0iIKQ",
        "text": "text"
    }

    html:
    <span data-slate-node="text">
       <span
           data-id="GRUSC3auSAihSO7DE0iIKQ"
           data-slate-leaf="true"
           class="id"
        >
          <span data-slate-string="true">text</span>
       </span>
    </span>
    """

    ele_id = escape_html(sdoc_json['id'])
    text = escape_html(sdoc_json['text'])

    html = f"""
    <span data-slate-node="text">
        <span data-id="{ele_id}"
            data-slate-leaf="true"
            class="id"
        >
            <span data-slate-string="true">{text}</span>
        </span>
    </span>
    """

    return html


# recursive
def render_node(node, doc_uuid='', parent_id='', publish_url=''):

    if 'text' in node:
        return render_text(node, doc_uuid=doc_uuid, parent_id=parent_id, publish_url=publish_url)

    node_type = node.get('type')

    if node_type == 'table':
        return render_table(node, doc_uuid=doc_uuid, parent_id=parent_id, publish_url=publish_url)

    if node_type == 'table_row':
        return render_table_row(node, doc_uuid=doc_uuid, parent_id=parent_id, publish_url=publish_url)

    if node_type == 'table_cell':
        return render_table_cell(node, doc_uuid=doc_uuid, parent_id=parent_id, publish_url=publish_url)

    if node_type == 'link':
        return render_link(node, doc_uuid=doc_uuid, parent_id=parent_id, publish_url=publish_url)

    if node_type == 'file_link':
        return render_file_link(node, doc_uuid=doc_uuid, parent_id=parent_id, publish_url=publish_url)

    if node_type == 'wiki_link':
        return render_wiki_link(node, doc_uuid=doc_uuid, parent_id=parent_id, publish_url=publish_url)

    if node_type == 'image':
        return render_image(node, doc_uuid=doc_uuid, parent_id=parent_id, publish_url=publish_url)

    if node_type == 'column':
        return render_column(node, doc_uuid=doc_uuid, parent_id=parent_id, publish_url=publish_url)

    if node_type == 'multi_column':
        return render_multi_column(node, doc_uuid=doc_uuid, parent_id=parent_id, publish_url=publish_url)

    if node_type == 'callout':
        return render_callout(node, doc_uuid=doc_uuid, parent_id=parent_id, publish_url=publish_url)

    if node_type == 'code_block':
        return render_code_block(node, doc_uuid=doc_uuid, parent_id=parent_id, publish_url=publish_url)

    if node_type == 'video':
        return render_video(node, doc_uuid=doc_uuid, parent_id=parent_id, publish_url=publish_url)

    if node_type == 'check_list_item':
        return render_check_list(node, doc_uuid=doc_uuid, parent_id=parent_id, publish_url=publish_url)

    if node_type == 'ordered_list':
        return render_ordered_list(node, doc_uuid=doc_uuid, parent_id=parent_id, publish_url=publish_url)

    if node_type == 'unordered_list':
        return render_unordered_list(node, doc_uuid=doc_uuid, parent_id=parent_id, publish_url=publish_url)

    if node_type == 'list_item':
        return render_list_item(node, doc_uuid=doc_uuid, parent_id=parent_id, publish_url=publish_url)

    if node_type in ['header1', 'header2', 'header3', 'header4', 'header5', 'header6']:
        return render_header(node, doc_uuid=doc_uuid, parent_id=parent_id, publish_url=publish_url)

    if node_type == 'toggle_header':
        return render_toggle_header(node, doc_uuid=doc_uuid, parent_id=parent_id, publish_url=publish_url)

    if node_type in ['toggle_header1', 'toggle_header2', 'toggle_header3',
                     'toggle_header4', 'toggle_header5', 'toggle_header6']:
        return render_toggle_header_row(node, doc_uuid=doc_uuid, parent_id=parent_id, publish_url=publish_url)

    if node_type == 'toggle_content':
        return render_toggle_content(node, doc_uuid=doc_uuid, parent_id=parent_id, publish_url=publish_url)

    if node_type == 'paragraph':
        return render_paragraph(node, doc_uuid=doc_uuid, parent_id=parent_id, publish_url=publish_url)

    if node_type == 'embed_link':
        return render_embed_link(node, doc_uuid=doc_uuid, parent_id=parent_id, publish_url=publish_url)

    if node_type == 'formula':
        return render_formula(node, doc_uuid=doc_uuid, parent_id=parent_id, publish_url=publish_url)

    if node_type == 'blockquote':
        return render_blockquote(node, doc_uuid=doc_uuid, parent_id=parent_id, publish_url=publish_url)

    # TODO
    children = node.get('children', [])
    return ''.join(
        render_node(child, doc_uuid=doc_uuid, parent_id=node.get('id', ''), publish_url=publish_url)
        for child in children
    )


def sdoc2html(sdoc_str, doc_uuid='', publish_url=''):

    if isinstance(sdoc_str, dict):
        doc = sdoc_str
    else:
        doc = json.loads(sdoc_str)

    elements = doc.get('elements', [])
    if not elements:
        elements = doc.get('children', [])

    html = "".join(render_node(element, doc_uuid=doc_uuid, publish_url=publish_url) for element in elements)
    return html
