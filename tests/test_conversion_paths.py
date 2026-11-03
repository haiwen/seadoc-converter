import tempfile
import unittest
from pathlib import Path

from seadoc_converter.converter.paths import checked_path, copy_html_files


class ConversionPathTests(unittest.TestCase):
    def test_normal_and_parent_escape_paths(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.assertEqual(checked_path(root, root / 'page.html'), root.resolve() / 'page.html')
            for path in (root / '..' / 'outside', root.parent / (root.name + '-other')):
                with self.subTest(path=path), self.assertRaises(ValueError):
                    checked_path(root, path)

    def test_symlink_files_directories_and_root_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            target = root / 'target'
            target.mkdir()
            link = root / 'link'
            link.symlink_to(target, target_is_directory=True)
            for base, path in ((root, link), (root, link / 'page.html'), (link, link)):
                with self.subTest(path=path), self.assertRaises(ValueError):
                    checked_path(base, path)
            dangling = root / 'dangling.html'
            dangling.symlink_to(root / 'missing')
            with self.assertRaises(ValueError):
                checked_path(root, dangling)

    def test_shared_input_copied_without_deleting_originals(self):
        with tempfile.TemporaryDirectory() as source, tempfile.TemporaryDirectory() as target:
            root = Path(source)
            (root / 'nested').mkdir()
            original = root / 'nested' / 'page.html'
            original.write_text('<html>page</html>')
            (root / 'attachment.bin').write_bytes(b'attachment')
            copy_html_files(root.resolve(), Path(target))
            copied = Path(target) / 'nested' / 'page.html'
            self.assertEqual(copied.read_text(), original.read_text())
            copied.unlink()
            self.assertTrue(original.exists())
            self.assertFalse((Path(target) / 'attachment.bin').exists())

    def test_shared_input_symlink_rejected(self):
        with tempfile.TemporaryDirectory() as source, tempfile.TemporaryDirectory() as target:
            root = Path(source)
            (root / 'page.html').symlink_to(root / 'missing')
            with self.assertRaises(ValueError):
                copy_html_files(root.resolve(), Path(target))


if __name__ == '__main__':
    unittest.main()
