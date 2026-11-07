"""File transfers must not follow redirects to another target."""

import requests


def request(method, url, **kwargs):
    kwargs['allow_redirects'] = False
    response = requests.request(method, url, **kwargs)
    if 300 <= response.status_code < 400:
        raise requests.HTTPError('Unexpected file transfer redirect', response=response)
    response.raise_for_status()
    return response
