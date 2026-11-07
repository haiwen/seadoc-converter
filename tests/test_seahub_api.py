import base64
from io import BytesIO
import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import time
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from zipfile import ZipFile

os.environ.setdefault('SDOC_SERVER_DIR', os.path.dirname(os.path.dirname(__file__)))

import jwt
from docx import Document

from seadoc_converter import config, seahub_api
from seadoc_converter.server import apis


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


class ConversionAuthorizationTests(unittest.TestCase):
    def setUp(self):
        self.key = 'converter-entry-authorization-test-key'
        self.enterContext(patch.object(config, 'SEADOC_PRIVATE_KEY', self.key))
        self.enterContext(patch('seadoc_converter.converter.utils.SEADOC_PRIVATE_KEY', self.key))
        self.client = apis.flask_app.test_client()
        self.claims = {
            'aud': 'seadoc-converter-file', 'exp': int(time.time()) + 300,
            'repo_id': 'repo-a', 'file_id': 'source-a', 'filename': 'source.docx',
            'username': 'authorized-user', 'doc_uuid': 'document-a',
            'output_path': '/source.sdoc',
        }
        auth = jwt.encode({'file_uuid': 'ordinary-document', 'exp': int(time.time()) + 300},
                          self.key, algorithm='HS256')
        self.headers = {'Authorization': 'Token ' + auth}
        self.source = self.enterContext(patch.object(seahub_api, 'get_file_content'))
        self.upload = self.enterContext(patch.object(
            seahub_api, 'upload_file', return_value=SimpleNamespace(ok=True)))
        self.images = self.enterContext(patch(
            'seadoc_converter.converter.sdoc_converter.docx2sdoc.requests.post',
            return_value=SimpleNamespace(status_code=200, content=b'{"relative_path": ["/image.png"]}')))
        self.process = self.enterContext(patch.object(apis, 'process_zip_file'))
        self.directory = self.enterContext(patch.object(
            apis, 'TemporaryDirectory', wraps=TemporaryDirectory))
        image = base64.b64decode(
            'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII=')
        document = Document()
        document.add_picture(BytesIO(image))
        output = BytesIO()
        document.save(output)
        self.source.return_value = output.getvalue()

    def file_token(self, **updates):
        claims = dict(self.claims)
        for key, value in updates.items():
            if value is None:
                claims.pop(key, None)
            else:
                claims[key] = value
        return jwt.encode(claims, self.key, algorithm='HS256')

    def invalid_grants(self):
        return {
            'readonly': self.file_token(output_path=None),
            'malformed': 'invalid-file-token',
            'signature': jwt.encode(self.claims, self.key + '-wrong', algorithm='HS256'),
            'expired': self.file_token(exp=int(time.time()) - 60),
            'audience': self.file_token(aud='ordinary-document'),
            'missing_expiry': self.file_token(exp=None),
            'missing_source': self.file_token(file_id=None),
        }

    def word_request(self, file_token, doc_uuid='document-a'):
        return self.client.post('/api/v1/file-convert/', headers=self.headers, json={
            'path': '/source.docx', 'username': 'request-user', 'doc_uuid': doc_uuid,
            'src_type': 'docx', 'dst_type': 'sdoc', 'file_token': file_token,
        })

    def confluence_data(self):
        self.claims.update(filename='Confluence_SPACE.html.zip', output_path='/tmp/sdoc_archive.zip')
        output = BytesIO()
        with ZipFile(output, 'w') as archive:
            archive.writestr('page.html', 'Authorized source')
        self.source.return_value = output.getvalue()
        return {'filename': self.claims['filename'], 'file_token': self.file_token(),
                'username': 'request-user', 'seafile_server_url': 'https://example.test'}

    def test_word_rejects_unauthorized_grants_before_file_operations(self):
        cases = [(name, token, 'document-a') for name, token in self.invalid_grants().items()]
        cases.extend([
            ('uuid_mismatch', self.file_token(), 'document-b'),
            ('missing_uuid', self.file_token(doc_uuid=None), 'document-a'),
        ])
        for name, token, doc_uuid in cases:
            with self.subTest(name=name):
                response = self.word_request(token, doc_uuid)
                self.assertEqual(response.status_code, 403)
                self.source.assert_not_called()
                self.images.assert_not_called()
                self.upload.assert_not_called()
                self.directory.assert_not_called()

    def test_word_accepts_authorized_conversion_with_image(self):
        token = self.file_token()
        response = self.word_request(token)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json(), {'success': True})
        self.source.assert_called_once_with(token)
        self.images.assert_called_once()
        self.assertTrue(self.images.call_args.args[0].endswith('/upload-image/document-a/'))
        headers = self.images.call_args.kwargs['headers']
        payload = jwt.decode(headers['authorization'].split()[1], self.key, algorithms=['HS256'])
        self.assertEqual(payload['file_uuid'], 'document-a')
        self.assertEqual(payload['permission'], 'rw')
        self.upload.assert_called_once()
        self.assertEqual(self.upload.call_args.args[:2], (token, 'source.sdoc'))
        self.assertEqual(json.loads(self.upload.call_args.args[2])['last_modify_user'], 'authorized-user')

    def test_confluence_rejects_unauthorized_grants_before_file_operations(self):
        data = self.confluence_data()
        cases = self.invalid_grants()
        cases['filename_mismatch'] = self.file_token(filename='Another_SPACE.html.zip')
        for name, token in cases.items():
            with self.subTest(name=name):
                response = self.client.post('/api/v1/confluence-to-wiki/', headers=self.headers,
                                            json=dict(data, file_token=token))
                self.assertEqual(response.status_code, 403)
                self.source.assert_not_called()
                self.images.assert_not_called()
                self.upload.assert_not_called()
                self.directory.assert_not_called()
                self.process.assert_not_called()

    def test_confluence_accepts_authorized_source_and_cleans_directory(self):
        data = self.confluence_data()
        directories = []

        def process(space_dir, server_url, username, file_token):
            directory = Path(space_dir)
            directories.append(directory)
            self.assertEqual((directory / 'page.html').read_text(), 'Authorized source')
            self.assertEqual(username, 'authorized-user')
            self.assertEqual(file_token, data['file_token'])
            return {'page': 'Authorized'}

        self.process.side_effect = process
        response = self.client.post('/api/v1/confluence-to-wiki/', headers=self.headers, json=data)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json(), {'cf_id_to_cf_title_map': {'page': 'Authorized'}})
        self.source.assert_called_once_with(data['file_token'])
        self.directory.assert_called_once()
        self.process.assert_called_once()
        self.assertFalse(directories[0].exists())


if __name__ == '__main__':
    unittest.main()
