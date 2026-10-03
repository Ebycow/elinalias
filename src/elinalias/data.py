"""異名データ(Alias.xlsx / Alias_mix.txt)の読み込みと JSON への書き出し。"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from importlib import resources
from pathlib import Path

from .xlsx import build_list

# Elin 本体の言語フォルダ(ゲームディレクトリからの相対パス)
LANG_DIRS: dict[str, str] = {
    "JP": "Package/_Elona/Lang/JP",
    "EN": "Package/_Elona/Lang/EN",
    "CN": "Package/_Lang_Chinese/Lang/CN",
}


@dataclass
class Mix:
    """Alias_mix.txt の 1 行。``chance`` が小さいほど出やすい(重み 1/chance)。"""

    chance: int
    texts: list[str]


@dataclass
class AliasData:
    lang: str
    rows: list[dict[str, str]]
    mix: list[Mix]
    source: str = ""
    extra: dict = field(default_factory=dict)

    # ---- 読み込み ----
    @classmethod
    def from_files(cls, xlsx_path: str | Path, mix_path: str | Path, lang: str = "") -> "AliasData":
        return cls(
            lang=lang,
            rows=build_list(xlsx_path, start_index=5),
            mix=parse_mix(Path(mix_path)),
            source=str(xlsx_path),
        )

    @classmethod
    def from_lang_dir(cls, lang_dir: str | Path, lang: str = "") -> "AliasData":
        """``.../Lang/JP`` のような言語フォルダから読む(Mod の言語フォルダにも使える)。"""
        d = Path(lang_dir) / "Data"
        return cls.from_files(d / "Alias.xlsx", d / "Alias_mix.txt", lang=lang or Path(lang_dir).name)

    @classmethod
    def from_game_dir(cls, game_dir: str | Path, lang: str = "JP") -> "AliasData":
        """Elin のインストールフォルダ(Elin.exe がある場所)から読む。"""
        lang = lang.upper()
        if lang not in LANG_DIRS:
            raise ValueError(f"unknown lang {lang!r}. known: {sorted(LANG_DIRS)}")
        return cls.from_lang_dir(Path(game_dir) / LANG_DIRS[lang], lang=lang)

    @classmethod
    def from_json(cls, path: str | Path) -> "AliasData":
        obj = json.loads(Path(path).read_text(encoding="utf-8"))
        return cls._from_obj(obj)

    @classmethod
    def bundled(cls, lang: str = "JP") -> "AliasData":
        """``elinalias extract`` で同梱した JSON を読む。"""
        lang = lang.upper()
        try:
            text = resources.files("elinalias").joinpath("data", f"alias_{lang}.json").read_text(encoding="utf-8")
        except FileNotFoundError:
            raise FileNotFoundError(
                f"bundled data for {lang} not found. "
                "Run `elinalias extract <Elinのフォルダ>` first, or use AliasData.from_game_dir()."
            ) from None
        return cls._from_obj(json.loads(text))

    @classmethod
    def _from_obj(cls, obj: dict) -> "AliasData":
        return cls(
            lang=obj.get("lang", ""),
            rows=obj["rows"],
            mix=[Mix(int(c), list(t)) for c, t in obj["mix"]],
            source=obj.get("source", ""),
        )

    # ---- 書き出し ----
    def to_obj(self) -> dict:
        return {
            "lang": self.lang,
            "source": self.source,
            "rows": self.rows,
            "mix": [[m.chance, m.texts] for m in self.mix],
        }

    def save_json(self, path: str | Path) -> None:
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        Path(path).write_text(json.dumps(self.to_obj(), ensure_ascii=False, indent=1), encoding="utf-8")


def _to_int(s: str) -> int:
    """C# の ``string.ToInt()`` (int.TryParse 失敗時 0)。"""
    try:
        return int(s.strip())
    except ValueError:
        return 0


def parse_mix(path: Path) -> list[Mix]:
    """``AliasGen.Init`` と同じ規則で Alias_mix.txt を読む。"""
    if not path.exists():
        alt = Path(str(path) + ".txt")
        if not alt.exists():
            return []
        path = alt
    # File.ReadAllLines 相当: BOM 除去、\r\n / \n / \r で分割
    text = path.read_text(encoding="utf-8-sig")
    lines = re.split(r"\r\n|\r|\n", text)
    if lines and lines[-1] == "":
        lines.pop()
    result: list[Mix] = []
    for line in lines:
        parts = line.split(",")
        if len(parts) >= 2:
            result.append(Mix(_to_int(parts[0]), parts[1].split("+")))
    return result


def extract(game_dir: str | Path, out_dir: str | Path, langs: list[str] | None = None) -> list[Path]:
    """ゲームフォルダから各言語のデータを JSON に書き出す。"""
    out: list[Path] = []
    for lang in langs or list(LANG_DIRS):
        lang_dir = Path(game_dir) / LANG_DIRS[lang]
        if not (lang_dir / "Data" / "Alias.xlsx").exists():
            continue
        data = AliasData.from_lang_dir(lang_dir, lang=lang)
        data.source = str(Path(LANG_DIRS[lang]) / "Data" / "Alias.xlsx")
        p = Path(out_dir) / f"alias_{lang}.json"
        data.save_json(p)
        out.append(p)
    return out
