# /// script
# requires-python = ">=3.11,<3.13"
# dependencies = ["ebooklib"]
# ///
"""Builds samples/回乡.epub, a two-Chapter original test book for the pipeline."""
from pathlib import Path

from ebooklib import epub

HERE = Path(__file__).resolve().parent
passage = (HERE.parents[1] / "bakeoff" / "texts" / "passage.txt").read_text(encoding="utf-8")
chapters = [("第一章 面馆", passage), ("第二章 老房子", (HERE / "chapter2.txt").read_text(encoding="utf-8"))]

book = epub.EpubBook()
book.set_identifier("tts-sample-huixiang")
book.set_title("回乡")
book.set_language("zh")
book.add_author("测试样书")
items = []
for i, (title, text) in enumerate(chapters, 1):
    body = "".join(f"<p>{p.strip()}</p>" for p in text.splitlines() if p.strip())
    c = epub.EpubHtml(title=title, file_name=f"ch{i}.xhtml", lang="zh")
    c.content = f"<h2>{title}</h2>{body}"
    book.add_item(c)
    items.append(c)
book.toc = items
book.spine = ["nav", *items]
book.add_item(epub.EpubNcx())
book.add_item(epub.EpubNav())
epub.write_epub(str(HERE / "回乡.epub"), book)
print(HERE / "回乡.epub")
