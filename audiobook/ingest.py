"""Turns an EPUB or a plain-text file into book.json: title, author and Chapters of paragraphs."""
import re
from pathlib import Path

from bs4 import BeautifulSoup

TXT_HEADING = re.compile(r"^\s*(第[零〇一二两三四五六七八九十百千万0-9]+[章回节卷].*|序[章言]?|楔子|尾声|后记)\s*$")
BLOCKS = ["p", "div", "li", "blockquote"]


CJK = r"[　-〿一-鿿＀-￯“”‘’]"


def _clean(text):
    """Collapses whitespace, dropping it next to Chinese but keeping it between English words."""
    text = re.sub(r"\s+", " ", text.replace("　", " ")).strip()
    return re.sub(rf"(?<={CJK}) | (?={CJK})", "", text)


def _title(text):
    return re.sub(r"\s+", " ", text.replace("\u3000", " ")).strip()


def _paragraphs(soup):
    blocks = soup.find_all("p") or [b for b in soup.find_all(BLOCKS) if not b.find(BLOCKS)]
    return [t for t in (_clean(b.get_text()) for b in blocks) if t]


def from_epub(path):
    from ebooklib import ITEM_COVER, ITEM_DOCUMENT, ITEM_IMAGE, epub

    book = epub.read_epub(str(path), options={"ignore_ncx": False})
    meta = lambda key: (book.get_metadata("DC", key) or [[""]])[0][0]  # noqa: E731
    toc_titles = {}

    def walk(entries):
        for e in entries:
            if isinstance(e, tuple):
                walk([e[0]] + list(e[1]))
            elif hasattr(e, "href"):
                toc_titles.setdefault(e.href.split("#")[0], e.title)

    walk(book.toc)

    chapters = []
    for idref, _ in book.spine:
        item = book.get_item_with_id(idref)
        if item is None or item.get_type() != ITEM_DOCUMENT or isinstance(item, epub.EpubNav):
            continue
        soup = BeautifulSoup(item.get_content(), "html.parser")
        heading = soup.find(["h1", "h2", "h3"])
        title = _title(heading.get_text()) if heading else ""
        if heading:
            heading.decompose()
        paragraphs = _paragraphs(soup)
        if not paragraphs:
            continue
        title = title or toc_titles.get(item.get_name(), "") or f"第{len(chapters) + 1}节"
        chapters.append({"title": title, "paragraphs": paragraphs})

    cover = next(iter(book.get_items_of_type(ITEM_COVER)), None) or next(
        (i for i in book.get_items_of_type(ITEM_IMAGE) if "cover" in i.get_name().lower()), None)
    return {"title": meta("title") or path.stem, "author": meta("creator"), "chapters": chapters}, (
        cover.get_content() if cover else None)


def from_txt(path):
    chapters, current = [], {"title": "开头", "paragraphs": []}
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        if TXT_HEADING.match(line):
            if current["paragraphs"]:
                chapters.append(current)
            current = {"title": _title(line), "paragraphs": []}
        else:
            current["paragraphs"].append(_clean(line))
    if current["paragraphs"]:
        chapters.append(current)
    return {"title": path.stem, "author": "", "chapters": chapters}, None


def ingest(path):
    path = Path(path)
    return from_epub(path) if path.suffix.lower() == ".epub" else from_txt(path)
