import os
import unittest
from unittest.mock import patch

os.environ.setdefault('SDOC_SERVER_DIR', os.path.dirname(os.path.dirname(__file__)))

from seadoc_converter import config, seahub_api


class SeahubFileAPITests(unittest.TestCase):
    @patch('seadoc_converter.seahub_api.file_requests.request')
    def test_source_uses_only_configured_api(self, send):
        send.return_value.content = b'source content'
        with patch.object(config, 'SEAHUB_SERVICE_URL', 'https://seahub.example/'):
            self.assertEqual(seahub_api.get_file_content('file-grant'), b'source content')
        send.assert_called_once_with(
            'GET', 'https://seahub.example/api/v2.1/internal/converter-file/',
            headers={'Authorization': 'Token file-grant'}, params=None, timeout=30)

    @patch('seadoc_converter.seahub_api.file_requests.request')
    def test_image_name_is_a_query_parameter_not_a_target_url(self, send):
        image_name = 'https://untrusted.example/image.png'
        with patch.object(config, 'SEAHUB_SERVICE_URL', 'https://seahub.example'):
            seahub_api.get_file_content('file-grant', image_name=image_name)
        self.assertEqual(send.call_args.args[1],
                         'https://seahub.example/api/v2.1/internal/converter-file/')
        self.assertEqual(send.call_args.kwargs['params'], {'image_name': image_name})

    @patch('seadoc_converter.seahub_api.file_requests.request')
    def test_upload_transmits_content_without_caller_destination(self, send):
        with patch.object(config, 'SEAHUB_SERVICE_URL', 'https://seahub.example'):
            seahub_api.upload_file('file-grant', 'result.sdoc', b'result')
        send.assert_called_once_with(
            'POST', 'https://seahub.example/api/v2.1/internal/converter-file/',
            headers={'Authorization': 'Token file-grant'},
            files={'file': ('result.sdoc', b'result')}, timeout=30)


if __name__ == '__main__':
    unittest.main()
