import os
import re
import jwt
import json
import logging
import requests

from zipfile import ZipFile
from pathlib import Path
from bs4 import BeautifulSoup
from html_to_markdown import convert_to_markdown

from seadoc_converter.converter.sdoc_converter.md2sdoc import md2sdoc
from seadoc_converter.config import SEAHUB_SERVICE_URL, SEADOC_PRIVATE_KEY


IMAGE_PATTERN = r'<img.*?src="(.*?)".*?>'


def is_url_link(s):
    if re.match(r'^http[s]?://', s):
        return True
    else:
        return False


def trans_img_path_to_url(image_path, doc_uuid):
    if is_url_link(image_path):
        return image_path

    return "%(server_url)s/%(tag)s/%(doc_uuid)s/%(image_path)s" % ({
        'server_url': SEAHUB_SERVICE_URL.rstrip('/'),
        'tag': 'api/v2.1/seadoc/download-image',
        'doc_uuid': doc_uuid,
        'image_path': image_path.strip('/')
    })


def gen_jwt_auth_header(payload):

    jwt_token = jwt.encode(payload, SEADOC_PRIVATE_KEY, algorithm='HS256')
    headers = {"authorization": "token %s" % jwt_token}
    return headers



def process_images_and_attachments(content_div, html_file, seafile_server_url):
    for a in content_div.find_all('a'):
        if 'confluence-userlink' in a.get('class', []):
            a.attrs['href'] = f""
            continue
        if 'confluence-embedded-file' in a.get('class', []):
            # If it is an attachment, delete the thumbnail corresponding to the attachment
            img = a.find('img')
            if img:
                img.decompose()

            alias = a.get('data-linked-resource-default-alias', 'Unknown attachment')
            # update attachment name
            if alias:
                a.clear()
                a.append(f'{alias} (attachment) \t')
        href = a.get('href', '')
        if href and not href.startswith(('http:', 'https:')):
            # page redirect processing
            if href.startswith('/wiki/spaces/'):
                last_slash_index = href.rfind('/')
                if last_slash_index == -1:
                    continue
                file_name = href[last_slash_index + 1:]
                # TODO: need to handle the click file to jump to wiki sidebar, not to sdoc file
                a.attrs['href'] = f""
            # TODO: if it is a link to other pages (Confluence page), then change to link to the other page in seafile file server
            elif href.endswith('.html'):
                # href = href.replace('.html', '.sdoc')
                a.attrs['href'] = f""
            # connect attachment:  currently only jump to the file
            else:
                a.attrs['href'] = f"{seafile_server_url}/{href}?dl=1"
        
    # process images
    for img in content_div.find_all('img'):
        src = img.get('src', '')
        # data:image/png;base64, remove data:base64 img
        if not src or src.startswith(('data:')):
            img.decompose()
            continue
        if src.startswith('images/'):
            pass
        alt = img.get('alt', '')
        title = img.get('title', '')
        width = img.get('width', '')
        height = img.get('height', '')
        img_name = src.split('/')[-1]
        if '?' in img_name:
            img_name = img_name.split('?')[0]
        # if it is a relative path image
        if not src.startswith(('http:', 'https:')):
            try:
                # calculate the full path of the image
                if '?' in src:
                    src = src.split('?')[0]
                # build new URL
                img['src'] = f"/{img_name}"
            except Exception as e:
                pass
        
        if width or height:
            width_attr = f' width="{width}"' if width else ''
            height_attr = f' height="{height}"' if height else ''
            alt_attr = f' alt="{alt}"' if alt else ' alt="undefined"'
            title_attr = f' title="{title}"' if title else ' title="undefined"'
            
            new_img_html = f'<img src="{img["src"]}"{alt_attr}{title_attr}{width_attr}{height_attr} />'
            img.replace_with(BeautifulSoup(new_img_html, 'html.parser'))

def convert_html_to_md(html_file, md_output_dir, seafile_server_url):
    html_file = Path(html_file).resolve()
    md_output_dir = Path(md_output_dir).resolve()
    
    with open(html_file, 'r', encoding='utf-8') as f:
        html_content = f.read()
    
    soup = BeautifulSoup(html_content, 'html.parser')
    
    title_element = soup.find('h1', id='title-heading')
    title = title_element.get_text().strip() if title_element else Path(html_file).stem
    
    if ":" in title:
        title = title.split(":", 1)[1].strip()
    
    content_div = soup.find('div', id='main-content')
    if not content_div:
        return False
    md_file = f'{md_output_dir}/{html_file.stem}.md'
    process_images_and_attachments(content_div, html_file, seafile_server_url)
    md_content = convert_to_markdown(content_div, keep_inline_images_in=['span','h2', 'p'])
    md_content = f"# {title}\n\n{md_content}"
    with open(md_file, 'w', encoding='utf-8') as f:
        f.write(md_content)
    try:
        os.remove(html_file)
    except Exception as e:
        pass
    return {html_file.stem: title}
        
def md_to_sdoc(md_file, sdoc_output_dir, username, upload_url):
    sdoc_file = f"{sdoc_output_dir}/{md_file.stem}.sdoc"
    md_file_path = f"{md_file.parent}/{md_file.name}"
    with open(md_file_path, 'r') as md:
        sdoc_content = md2sdoc(md.read(), username)
    with open(sdoc_file, 'w', encoding='utf-8') as f:
        f.write(json.dumps(sdoc_content))
    return sdoc_file

        
def process_zip_file(space_dir, seafile_server_url, username, upload_url):
    html_files = []
    dir_path = Path(space_dir).resolve()
    for root, _, files in os.walk(dir_path):
        for file in files:
            if file.endswith('.html') and file != 'index.html':
                html_files.append(Path(root) / file)
    
    md_output_dir = f'{space_dir}/md_output'
    sdoc_output_dir = f'{space_dir}/sdoc_output'
    if not os.path.exists(md_output_dir):
        os.mkdir(md_output_dir)
    if not os.path.exists(sdoc_output_dir):
        os.mkdir(sdoc_output_dir)

    # html to md
    cf_id_to_cf_title_map = {}
    for html_file in html_files:
        try:
            result = convert_html_to_md(html_file, md_output_dir, seafile_server_url)
            if result:
                cf_id_to_cf_title_map.update(result)
        except Exception as e:
            raise e
    # md to sdoc
    md_files = list(Path(md_output_dir).glob('*.md'))
    sdoc_files = []
    for md_file in md_files:
        try:
            sdoc_file = md_to_sdoc(md_file, sdoc_output_dir, username, upload_url)
            if sdoc_file:
                sdoc_files.append(sdoc_file)
        except Exception as e:
            logging.error(f"convert failed: {md_file} failed: {e}")
            continue
    
    # zip and upload sdoc files
    if sdoc_files:
        try:
            zip_and_upload_files(sdoc_files, f'{space_dir}/sdoc_archive.zip', upload_url)
        except Exception as e:
            raise e
    
    return cf_id_to_cf_title_map

def zip_and_upload_files(file_paths, output_zip_path, upload_url):
    # create zip file
    with ZipFile(output_zip_path, 'w') as zip_file:
        for file_path in file_paths:
            # use the file name as the path in the zip file
            file_name = os.path.basename(file_path)
            zip_file.write(file_path, file_name)
    
    # read the zip file content for upload
    with open(output_zip_path, 'rb') as f:
        zip_content = f.read()
    
    # upload the zip file
    archive_name = os.path.basename(output_zip_path)
    files = {
        'file': (archive_name, zip_content),
        'parent_dir': 'tmp/',
    }
    
    resp = requests.post(upload_url, files=files)
    if not resp.ok:
        raise Exception(f"upload zip file failed: {resp.text}")

