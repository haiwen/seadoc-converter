import unittest
from unittest.mock import patch

import requests

from seadoc_converter import file_requests


class FileTransferTests(unittest.TestCase):
    def test_redirects_and_http_errors_rejected(self):
        for method in ('GET', 'POST'):
            for status in (301, 302, 303, 307, 308, 404, 500):
                with self.subTest(method=method, status=status):
                    response = requests.Response()
                    response.status_code = status
                    response.headers['Location'] = 'http://127.0.0.1/private'
                    with patch.object(file_requests.requests, 'request', return_value=response) as send:
                        with self.assertRaises(requests.HTTPError):
                            file_requests.request(method, 'https://files.example/source')
                        send.assert_called_once_with(
                            method, 'https://files.example/source', allow_redirects=False)

    def test_successful_upload_preserves_multipart_arguments(self):
        response = requests.Response()
        response.status_code = 200
        files = {'file': ('result.sdoc', b'content')}
        with patch.object(file_requests.requests, 'request', return_value=response) as send:
            self.assertIs(file_requests.request(
                'POST', 'https://files.example/upload', files=files), response)
            send.assert_called_once_with(
                'POST', 'https://files.example/upload', allow_redirects=False, files=files)


if __name__ == '__main__':
    unittest.main()
