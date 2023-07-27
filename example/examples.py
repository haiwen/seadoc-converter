import json
from converter.converter import sdoc2md
with open("./json/text.json", 'r', encoding='utf-8') as f:
    json_file = json.load(f)

doc_uuid = "e9acd5b2-3ac9-4215-8242-6a6e888cc21e"

markdown_text = sdoc2md(json_file, doc_uuid)

if __name__ == '__main__':

    with open("./markdown/output.md", 'w') as f:
        f.write(markdown_text)