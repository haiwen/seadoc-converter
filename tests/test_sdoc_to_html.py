import os
import json
import unittest
from copy import deepcopy
from unittest.mock import patch

os.environ.setdefault(
    'SDOC_SERVER_DIR',
    os.path.abspath(os.path.join(os.path.dirname(__file__), '..')),
)

from seadoc_converter.converter import html_converter


FIXTURE_PATH = os.path.join(os.path.dirname(__file__), 'test.sdoc')
DOC_UUID = 'test-doc-uuid'
PUBLISH_URL = 'published-page'


class TestSdocToHtml(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        with open(FIXTURE_PATH, 'r', encoding='utf-8') as fp:
            cls.fixture = json.load(fp)

    @classmethod
    def _find_node(cls, matcher, nodes=None):
        nodes = cls.fixture['elements'] if nodes is None else nodes
        for node in nodes:
            if matcher(node):
                return node
            for child in node.get('children', []):
                if isinstance(child, dict):
                    matched = cls._find_node(matcher, [child])
                    if matched:
                        return matched
        return None

    def get_node_by_id(self, node_id):
        node = self._find_node(lambda current: current.get('id') == node_id)
        self.assertIsNotNone(node, node_id)
        return deepcopy(node)

    def get_node_by_type(self, node_type):
        node = self._find_node(lambda current: current.get('type') == node_type)
        self.assertIsNotNone(node, node_type)
        return deepcopy(node)

    def test_render_blockquote(self):
        blockquote = {
            'id': 'blockquote-id',
            'type': 'blockquote',
            'children': [self.get_node_by_type('paragraph')],
        }

        html = html_converter.render_blockquote(blockquote)

        self.assertIn('<blockquote', html)
        self.assertIn('data-id="blockquote-id"', html)
        self.assertIn('Heading 1 content', html)

    def test_render_table_cell(self):
        normal_cell = self.get_node_by_id('I6-Xd9rpRLCMFr5jB3rECA')
        combined_cell = self.get_node_by_id('DS9cUk4QRlWw9FZ25BUNSA')

        normal_html = html_converter.render_table_cell(
            {**normal_cell, '_row_index': 1, '_col_index': 1}
        )
        combined_html = html_converter.render_table_cell(
            {**combined_cell, '_row_index': 1, '_col_index': 2}
        )

        self.assertIn('data-id="I6-Xd9rpRLCMFr5jB3rECA"', normal_html)
        self.assertIn('grid-area: 1 / 1 / span 1 / span 2;', normal_html)
        self.assertIn('header 1', normal_html)
        self.assertIn('display: none;', combined_html)
        self.assertIn('data-slate-zero-width="n"', combined_html)

    def test_render_table_cell_style_and_inherit_style(self):
        align_html = html_converter.render_table_cell({
            'id': 'align-cell-id',
            'type': 'table_cell',
            'children': [{'id': 'align-text-id', 'text': '6'}],
            'style': {'align_items': 'center'},
            'inherit_style': {},
            '_row_index': 2,
            '_col_index': 2,
        })
        inherit_html = html_converter.render_table_cell({
            'id': 'inherit-cell-id',
            'type': 'table_cell',
            'children': [{'id': 'inherit-text-id', 'text': 'a'}],
            'style': {},
            'inherit_style': {
                'background_color': '#914545',
                'text_align': 'right',
                'align_items': 'flex-end',
            },
            '_row_index': 3,
            '_col_index': 1,
        })

        self.assertIn('align-items: center;', align_html)
        self.assertIn('background-color: #914545;', inherit_html)
        self.assertIn('text-align: right;', inherit_html)
        self.assertIn('align-items: flex-end;', inherit_html)

    def test_render_table_row(self):
        html = html_converter.render_table_row({**self.get_node_by_id('fMnaCyEBQgWp7ZqK-tVkZw'), '_row_index': 1})

        self.assertNotIn('hidden="" data-id="fMnaCyEBQgWp7ZqK-tVkZw"', html)
        self.assertIn('grid-area: 1 / 1 / span 1 / span 2;', html)
        self.assertIn('data-id="I6-Xd9rpRLCMFr5jB3rECA"', html)
        self.assertIn('data-id="GWu9Z5MmTs6ACBTTqIOorA"', html)

    def test_render_table(self):
        html = html_converter.render_table(self.get_node_by_type('table'))

        self.assertIn('data-id="XpTDKMV0RVuTxggfowKt7A"', html)
        self.assertIn('max-width: 836px;', html)
        self.assertIn('grid-template-columns: 209px 209px 209px 209px;', html)
        self.assertIn('grid-auto-rows: minmax(42px, auto) minmax(42px, auto);', html)

    def test_render_column_and_multi_column(self):
        column_html = html_converter.render_column(self.get_node_by_id('Y3_oAv3bTXiMf9yr1wbJ9g'))
        multi_column_html = html_converter.render_multi_column(self.get_node_by_id('c3bI4ot9T9aedqz4-Ns2Iw'))

        self.assertIn('style="width: 444px;"', column_html)
        self.assertIn('column 1', column_html)
        self.assertIn('data-id="c3bI4ot9T9aedqz4-Ns2Iw"', multi_column_html)
        self.assertIn('grid-template-columns: 443.9843794663879px 443.9843794663879px;', multi_column_html)

    @patch('seadoc_converter.converter.html_converter.formula_to_svg', return_value='<svg>formula</svg>')
    def test_render_formula(self, mock_formula_to_svg):
        html = html_converter.render_formula(self.get_node_by_type('formula'))

        self.assertIn('class="sdoc-block-formula"', html)
        self.assertIn('<svg>formula</svg>', html)
        mock_formula_to_svg.assert_called_once()

    def test_render_callout(self):
        html = html_converter.render_callout(self.get_node_by_type('callout'))

        self.assertIn('data-id="QyvTKJHeQL67jv7xfMFvPg"', html)
        self.assertIn('background-color: #fef7e0; border-color: transparent;', html)
        self.assertIn('callout 3', html)

    def test_render_code_block(self):
        html = html_converter.render_code_block(self.get_node_by_type('code_block'))

        self.assertIn('data-id="UI8drojaShi61wRaGV1qNg"', html)
        self.assertIn('class="sdoc-code-line language-plaintext"', html)
        self.assertIn('code 1', html)
        self.assertIn('code 3', html)

    @patch('seadoc_converter.converter.html_converter.trans_video_path_to_url', return_value='https://example.com/video.mov')
    def test_render_video(self, mock_trans_video_path_to_url):
        local_video_html = html_converter.render_video(
            self.get_node_by_id('PP4fv0YfSmqZNH9So-yJvA'),
            doc_uuid=DOC_UUID,
        )
        remote_video_html = html_converter.render_video(self.get_node_by_id('aQgyZHHyS3Kk39V7Gyq_jg'))

        self.assertIn('<video', local_video_html)
        self.assertIn('src="https://example.com/video.mov"', local_video_html)
        self.assertIn('<iframe', remote_video_html)
        self.assertIn('player.bilibili.com/player.html?bvid=BV1XY546vE1o&amp;autoplay=0', remote_video_html)
        mock_trans_video_path_to_url.assert_called_once_with('/video-IbjwV-N0Sxmim6R0qrNcKw.mov', DOC_UUID)

    def test_render_check_list(self):
        checked_html = html_converter.render_check_list(self.get_node_by_id('M57TxsgiR7KNDxQvQN1eEQ'))
        unchecked_html = html_converter.render_check_list(self.get_node_by_id('FZZdC-4PQeWoq7vethX8aw'))

        self.assertIn('checked', checked_html)
        self.assertIn('Check list, checked', checked_html)
        self.assertIn('type="checkbox"', unchecked_html)
        self.assertNotIn('checked\n                disabled', unchecked_html)

    def test_render_ordered_unordered_list_and_list_item(self):
        unordered_html = html_converter.render_unordered_list(self.get_node_by_type('unordered_list'))
        ordered_html = html_converter.render_ordered_list(self.get_node_by_type('ordered_list'))
        single_item_html = html_converter.render_list_item(self.get_node_by_id('MiEbniacRaiuDT4LVN3eBw'))

        nested_item = self.get_node_by_id('MiEbniacRaiuDT4LVN3eBw')
        nested_item['children'].append(self.get_node_by_type('unordered_list'))
        nested_item_html = html_converter.render_list_item(nested_item)

        self.assertIn('<ul', unordered_html)
        self.assertIn('Unordered list 3', unordered_html)
        self.assertIn('<ol', ordered_html)
        self.assertIn('Ordered list 2', ordered_html)
        self.assertIn('sdoc-li-content', single_item_html)
        self.assertNotIn('sdoc-li-control', single_item_html)
        self.assertIn('sdoc-li-control', nested_item_html)

    def test_render_toggle_header_related_nodes(self):
        toggle_html = html_converter.render_toggle_header(self.get_node_by_id('aR53oHViSpq_f8OpAXnrLg'))
        row_html = html_converter.render_toggle_header_row(self.get_node_by_id('fnquMNbRRZKHjjsHSc9pzA'))
        content_html = html_converter.render_toggle_content(self.get_node_by_id('FYJ88N1bQlCAOjnBHsGjLQ'))

        self.assertIn('class="sdoc-toggle-header-container"', toggle_html)
        self.assertIn('Toggle header 1', toggle_html)
        self.assertIn('class="sdoc-toggle-header-title sdoc-header-2"', row_html)
        self.assertIn('Toggle header 2', row_html)
        self.assertIn('class="sdoc-toggle-header-content"', content_html)
        self.assertIn('toggle header 3', content_html)

    def test_render_paragraph_and_header(self):
        paragraph_html = html_converter.render_paragraph(self.get_node_by_id('Nz91z964TcuTtrEh_OIQlQ'))
        header_html = html_converter.render_header(self.get_node_by_id('6412ad41-1c30-4164-827e-66c749e29fd1'))

        self.assertIn('padding-top: 5px; padding-bottom: 5px;', paragraph_html)
        self.assertIn('Heading 1 content', paragraph_html)
        self.assertIn('class="sdoc-header-1"', header_html)
        self.assertIn('Heading 1', header_html)

    def test_render_embed_link(self):
        html = html_converter.render_embed_link(self.get_node_by_type('embed_link'))

        self.assertIn('class="sdoc-embed-link-element seatable"', html)
        self.assertIn('https://dev.seatable.cn/workspace/', html)

    @patch('seadoc_converter.converter.html_converter.trans_wiki_page_id_to_url', return_value='https://example.com/wiki/YdoF')
    def test_render_link(self, mock_trans_wiki_page_id_to_url):
        link_node = self.get_node_by_id('JHp4EBztRNqxonur3_JtfA')
        linked_block_node = deepcopy(link_node)
        linked_block_node['href'] = ''
        linked_block_node['linked_id'] = 'linked-block-id'
        linked_wiki_node = deepcopy(link_node)
        linked_wiki_node['href'] = ''
        linked_wiki_node['linked_wiki_page_id'] = 'YdoF'

        href_html = html_converter.render_link(link_node)
        block_html = html_converter.render_link(linked_block_node)
        wiki_html = html_converter.render_link(linked_wiki_node, publish_url=PUBLISH_URL)

        self.assertIn('href="https://seafile.com"', href_html)
        self.assertIn('data-link-block-id="linked-block-id"', block_html)
        self.assertIn('class="sdoc-link-page" href="https://example.com/wiki/YdoF"', wiki_html)
        mock_trans_wiki_page_id_to_url.assert_called_once_with(PUBLISH_URL, 'YdoF')

    def test_render_file_link(self):
        html = html_converter.render_file_link({
            'id': 'file-link-id',
            'type': 'file_link',
            'doc_uuid': DOC_UUID,
            'title': 'fixture.sdoc',
            'display_type': 'icon_link',
            'children': [],
        })

        self.assertIn('data-id="file-link-id"', html)
        self.assertIn('/api/v2.1/seadoc/file/test-doc-uuid/?doc_uuid=test-doc-uuid', html)
        self.assertIn('fixture.sdoc', html)

    def test_render_wiki_link(self):
        html = html_converter.render_wiki_link({
            'id': 'wiki-link-id',
            'type': 'wiki_link',
            'wiki_repo_id': 'repo-id',
            'page_id': 'page-id',
            'title': 'Wiki page',
            'icon': '',
            'isDir': False,
            'display_type': 'icon_link',
            'children': [],
        }, publish_url=PUBLISH_URL)

        self.assertIn('data-id="wiki-link-id"', html)
        self.assertIn('/wiki/publish/published-page/page-id/', html)
        self.assertIn('Wiki page', html)

    @patch('seadoc_converter.converter.html_converter.trans_img_path_to_url', return_value='https://example.com/image.png')
    def test_render_image(self, mock_trans_img_path_to_url):
        html = html_converter.render_image(
            self.get_node_by_id('fV-_QGi4RwOmWiWNzsCLRQ'),
            doc_uuid=DOC_UUID,
            parent_id='image-block-id',
        )

        self.assertIn('data-id="fV-_QGi4RwOmWiWNzsCLRQ"', html)
        self.assertIn('data-parent-id="image-block-id"', html)
        self.assertIn('src="https://example.com/image.png"', html)
        mock_trans_img_path_to_url.assert_called_once_with('/image-J10ano3ZQV6R0cbAehCKKw.png', DOC_UUID)

    def test_render_text(self):
        html = html_converter.render_text(self.get_node_by_id('dncBr5o8RwiAaqd4uwfL1A'))

        self.assertIn('data-id="dncBr5o8RwiAaqd4uwfL1A"', html)
        self.assertIn('Heading 1', html)

    def test_render_text_with_styles(self):
        html = html_converter.render_text({
            'id': 'text-style-id',
            'text': 'styled text',
            'highlight_color': '#FF0000',
            'color': '#FFFF00',
            'bold': True,
            'underline': True,
            'italic': True,
            'font_size': 13,
            'superscript': True,
        })

        self.assertIn('class="id highlight_color color bold underline italic font_size superscript"', html)
        self.assertIn('background-color: #FF0000;', html)
        self.assertIn('color: #FFFF00;', html)
        self.assertIn('font-size: 13pt;', html)
        self.assertIn('<strong>', html)
        self.assertIn('text-decoration: underline;', html)
        self.assertIn('<i>', html)
        self.assertIn('<sup>', html)
        self.assertIn('styled text', html)

    def test_render_text_with_missing_optional_fields_and_empty_text(self):
        html = html_converter.render_text({
            'id': 'empty-text-id',
            'text': '',
        })

        self.assertIn('class="id"', html)
        self.assertNotIn('highlight_color', html)
        self.assertNotIn('font-size:', html)
        self.assertIn('data-slate-zero-width="z" data-slate-length="0"', html)

    @patch('seadoc_converter.converter.html_converter.trans_img_path_to_url', return_value='https://example.com/image.png')
    def test_render_node_and_sdoc2html(self, mock_trans_img_path_to_url):
        image_block = self.get_node_by_id('WChrKqM-QteLLjB6jxkdYg')
        image_block['align'] = 'center'

        fixture = deepcopy(self.fixture)
        fixture_image_block = self._find_node(
            lambda current: current.get('id') == 'WChrKqM-QteLLjB6jxkdYg',
            fixture['elements'],
        )
        self.assertIsNotNone(fixture_image_block)
        fixture_image_block['align'] = 'center'

        image_block_html = html_converter.render_node(
            image_block,
            doc_uuid=DOC_UUID,
            parent_id='root',
        )
        html = html_converter.sdoc2html(fixture, doc_uuid=DOC_UUID)

        self.assertIn('justify-content: center;', image_block_html)
        self.assertIn('class="sdoc-image-wrapper"', image_block_html)
        self.assertIn('src="https://example.com/image.png"', image_block_html)
        self.assertIn('class="sdoc-header-1"', html)
        self.assertIn('class="sdoc-code-block-container sdoc-drag-cover"', html)
        self.assertIn('class="sdoc-callout-white-wrapper"', html)
        self.assertIn('justify-content: center;', html)
        self.assertGreaterEqual(mock_trans_img_path_to_url.call_count, 2)


if __name__ == '__main__':
    unittest.main()
