import unittest
from io import BytesIO
from zipfile import ZipFile, ZIP_DEFLATED

from seadoc_converter.converter.docx_limits import check_docx_sizes, DocxSizeLimitError


class DocxLimitsTests(unittest.TestCase):
    def archive(self, sizes):
        content = BytesIO()
        with ZipFile(content, 'w', compression=ZIP_DEFLATED) as archive:
            for index, size in enumerate(sizes):
                archive.writestr('member-%s.xml' % index, b' ' * size)
        content.seek(0)
        return content

    def test_boundary_sizes_accepted(self):
        check_docx_sizes(self.archive([64, 64]), 64, 128)

    def test_compressed_member_exceeding_limit_rejected(self):
        with self.assertRaises(DocxSizeLimitError):
            check_docx_sizes(self.archive([1024 * 1024]), 1024, 2 * 1024 * 1024)

    def test_total_exceeding_limit_rejected(self):
        with self.assertRaises(DocxSizeLimitError):
            check_docx_sizes(self.archive([64, 64, 1]), 64, 128)


if __name__ == '__main__':
    unittest.main()
