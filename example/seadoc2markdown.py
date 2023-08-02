import json
from converter.markdown_converter import sdoc2md


with open("./sdoc/text.sdoc", 'r', encoding='utf-8') as f:
    json_file = json.load(f)

doc_uuid = "e9acd5b2-3ac9-4215-8242-6a6e888cc21e"

markdown_text = sdoc2md(json_file, doc_uuid)


with open("./output/output.md", 'w') as f:
    f.write(markdown_text)

