import io
import os
import unittest

from docx import Document
from docx.oxml.ns import qn

os.environ.setdefault(
    'SDOC_SERVER_DIR',
    os.path.abspath(os.path.join(os.path.dirname(__file__), '..')),
)

from seadoc_converter.converter.docx_converter import sdoc2docx


class TestSdocToDocxColors(unittest.TestCase):

    def export(self, elements):
        return Document(io.BytesIO(sdoc2docx({'elements': elements}, 'test-doc', 'test-user')))

    def test_text_colors(self):
        cases = [
            ('#123456', '123456'),
            ('ABCDEF', 'ABCDEF'),
            ('#f00', 'FF0000'),
            ('rgb(12, 34, 56)', '0C2238'),
            (' RGBA(12, 34, 56, 0.5) ', '0C2238'),
            ('invalid', None),
            ('rgb(256, 0, 0)', None),
            ('rgb(1, 2)', None),
            ('rgba(1, 2, 3, 2)', None),
            (123, None),
        ]
        for node_type in ('paragraph', 'callout'):
            for color, expected in cases:
                with self.subTest(node_type=node_type, color=color):
                    document = self.export([{
                        'type': node_type,
                        'children': [{'text': 'colored text', 'color': color}],
                    }])
                    run = document.paragraphs[0].runs[0]
                    self.assertEqual(run.text, 'colored text')
                    actual = run.font.color.rgb
                    self.assertEqual(str(actual) if actual is not None else None, expected)

    def test_table_colors(self):
        document = self.export([{
            'type': 'table',
            'children': [{
                'type': 'table_row',
                'children': [{
                    'type': 'table_cell',
                    'children': [
                        {'text': 'RGB', 'color': 'rgb(12, 34, 56)'},
                        {'text': 'invalid', 'color': 'invalid'},
                    ],
                }],
            }],
        }])
        runs = document.tables[0].cell(0, 0).paragraphs[0].runs
        self.assertEqual(str(runs[0].font.color.rgb), '0C2238')
        self.assertEqual(runs[1].text, 'invalid')
        self.assertIsNone(runs[1].font.color.rgb)

    def test_callout_background(self):
        for style, expected in [
            ({'background_color': 'rgb(12, 34, 56)'}, '0C2238'),
            ({'background_color': '#abc'}, 'AABBCC'),
            ({'background_color': 'invalid'}, 'FEF7E0'),
            ({'background_color': None}, 'FEF7E0'),
            ({'text_align': 'center'}, 'FEF7E0'),
        ]:
            with self.subTest(style=style):
                document = self.export([{
                    'type': 'callout',
                    'style': style,
                    'children': [{'text': 'callout'}],
                }])
                shading = document.paragraphs[0]._p.pPr.find(qn('w:shd'))
                self.assertEqual(shading.get(qn('w:fill')).upper(), expected)
