"""Transfer conversion files only through the configured Seahub API."""

from seadoc_converter import config, file_requests


def get_file_content(file_token, image_name=None):
    params = {'image_name': image_name} if image_name is not None else None
    return file_requests.request(
        'GET', config.SEAHUB_SERVICE_URL.rstrip('/') + '/api/v2.1/internal/converter-file/',
        headers={'Authorization': 'Token ' + file_token}, params=params, timeout=30).content


def upload_file(file_token, filename, content):
    return file_requests.request(
        'POST', config.SEAHUB_SERVICE_URL.rstrip('/') + '/api/v2.1/internal/converter-file/',
        headers={'Authorization': 'Token ' + file_token},
        files={'file': (filename, content)}, timeout=30)
