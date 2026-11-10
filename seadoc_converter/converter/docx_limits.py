"""Check DOCX ZIP sizes before python-docx decompresses its members."""

from zipfile import ZipFile


class DocxSizeLimitError(ValueError):
    pass


def check_docx_sizes(source, max_member_size, max_total_size):
    total = 0
    with ZipFile(source) as archive:
        for member in archive.infolist():
            if member.file_size > max_member_size:
                raise DocxSizeLimitError(
                    'DOCX uncompressed member exceeds the size limit: '
                    '%s (%s bytes)' % (member.filename, member.file_size))
            total += member.file_size
            if total > max_total_size:
                raise DocxSizeLimitError(
                    'DOCX total uncompressed size exceeds the size limit (%s bytes)' % total)
