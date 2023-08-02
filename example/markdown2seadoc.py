import json
from converter.sdoc_converter import md2sdoc

usnername = "jiwei.ran@seafile.com"


with open("./markdown/text.md", 'r', encoding='utf-8') as f:
    md_txt = f.read()


sdoc_json = md2sdoc(md_txt, usnername)


with open("./output/output.sdoc", 'w') as f:
    f.write(json.dumps(sdoc_json))

