"""Keep Confluence conversion files inside their task directory."""

import os
import shutil
from pathlib import Path


def checked_path(root, path):
    root_path = Path(os.path.abspath(root))
    if root_path.is_symlink():
        raise ValueError('Symbolic links are not allowed in conversion paths.')
    root = root_path.resolve()
    path = Path(os.path.abspath(path))
    try:
        relative = path.relative_to(root_path)
    except ValueError:
        raise ValueError('Path is outside the conversion directory.') from None
    current = root
    for part in relative.parts:
        current = current / part
        if current.is_symlink():
            raise ValueError('Symbolic links are not allowed in conversion paths.')
    path = root / relative
    if not path.resolve().is_relative_to(root):
        raise ValueError('Path is outside the conversion directory.')
    return path


def copy_html_files(source, destination):
    """Copy shared-machine input without modifying the shared source directory."""
    for directory, subdirs, filenames in os.walk(source):
        for name in subdirs + filenames:
            checked_path(source, Path(directory) / name)
        for name in filenames:
            if not name.endswith('.html'):
                continue
            source_file = checked_path(source, Path(directory) / name)
            target = checked_path(destination, Path(destination) / source_file.relative_to(source))
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source_file, target)
