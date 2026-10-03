"""Alias.xlsx を標準ライブラリだけで読むための最小限の xlsx リーダー。

Elin の ``ExcelData.BuildList()`` (NPOI) と同じ規則で行を取り出す:

* 1 行目をヘッダ(列名)とする。ヘッダが空の列に当たったらそこで列の読み取りを打ち切る。
* データは ``startIndex - 1`` 行目(0 始まり)から。Alias では startIndex = 5 なので
  Excel 上の 5 行目から読む(4 行目以前は使われない)。
* 物理的に存在しない行(<row> 要素が無い行)に当たったら読み取り終了(maxEmptyRows = 0)。
* 存在するが空の行は、全列 "" の行としてそのまま含める。
"""

from __future__ import annotations

import re
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path

_NS = {
    "m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main",
    "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
}
_REL_NS = "http://schemas.openxmlformats.org/package/2006/relationships"
_M = "{%s}" % _NS["m"]


def _col_index(ref: str) -> int:
    letters = re.match(r"[A-Z]+", ref).group(0)
    n = 0
    for ch in letters:
        n = n * 26 + (ord(ch) - 64)
    return n - 1


def _si_text(si: ET.Element) -> str:
    # ふりがな(<rPh>)は NPOI の文字列に含まれないので除外する
    parts = []
    for child in si:
        if child.tag == _M + "t":
            parts.append(child.text or "")
        elif child.tag == _M + "r":
            t = child.find(_M + "t")
            if t is not None:
                parts.append(t.text or "")
    return "".join(parts)


def _num_to_str(v: str) -> str:
    try:
        f = float(v)
    except ValueError:
        return v
    return str(int(f)) if f.is_integer() else repr(f)


def _first_sheet_path(z: zipfile.ZipFile) -> str:
    wb = ET.fromstring(z.read("xl/workbook.xml"))
    sheet = wb.find("m:sheets/m:sheet", _NS)
    rid = sheet.get("{%s}id" % _NS["r"])
    rels = ET.fromstring(z.read("xl/_rels/workbook.xml.rels"))
    for rel in rels.findall("{%s}Relationship" % _REL_NS):
        if rel.get("Id") == rid:
            target = rel.get("Target")
            if target.startswith("/"):
                return target.lstrip("/")
            return "xl/" + target
    return "xl/worksheets/sheet1.xml"


def read_rows(path: str | Path) -> dict[int, dict[int, str]]:
    """{行番号(0始まり): {列番号: 文字列}} を返す。存在しない行は含まれない。"""
    with zipfile.ZipFile(path) as z:
        shared: list[str] = []
        if "xl/sharedStrings.xml" in z.namelist():
            sst = ET.fromstring(z.read("xl/sharedStrings.xml"))
            shared = [_si_text(si) for si in sst.findall("m:si", _NS)]
        sheet = ET.fromstring(z.read(_first_sheet_path(z)))

    rows: dict[int, dict[int, str]] = {}
    for row in sheet.iterfind("m:sheetData/m:row", _NS):
        r = int(row.get("r")) - 1
        cells: dict[int, str] = {}
        for c in row.findall("m:c", _NS):
            col = _col_index(c.get("r"))
            t = c.get("t", "n")
            if t == "inlineStr":
                is_ = c.find("m:is", _NS)
                val = _si_text(is_) if is_ is not None else ""
            else:
                v = c.find("m:v", _NS)
                raw = v.text if v is not None and v.text is not None else ""
                if t == "s":
                    val = shared[int(raw)] if raw else ""
                elif t == "b":
                    val = "TRUE" if raw == "1" else ("FALSE" if raw else "")
                elif t in ("str", "e"):
                    val = raw
                else:
                    val = _num_to_str(raw) if raw else ""
            cells[col] = val
        rows[r] = cells
    return rows


def build_list(path: str | Path, start_index: int = 5, max_empty_rows: int = 0) -> list[dict[str, str]]:
    """``ExcelData.BuildList()`` 相当。"""
    rows = read_rows(path)
    header_cells = rows.get(0, {})
    last_cell_num = (max(header_cells) + 1) if header_cells else 0
    header: list[str] = []
    for j in range(last_cell_num):
        name = header_cells.get(j, "")
        if name == "":
            break
        header.append(name)

    last_row_num = max(rows) if rows else -1
    result: list[dict[str, str]] = []
    empty = 0
    for i in range(start_index - 1, last_row_num + 1):
        cells = rows.get(i)
        if cells is None:
            if i >= 5:
                empty += 1
                if empty > max_empty_rows:
                    break
            continue
        empty = 0
        d: dict[str, str] = {}
        for j, name in enumerate(header):
            if name not in d:
                d[name] = cells.get(j, "")
        result.append(d)
    return result
