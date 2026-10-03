"""Elin の異名生成 (Plugins.NameGen.dll / ``AliasGen``) の Python 移植。

乱数の消費順・float の丸めまで本家に合わせてあるので、同じシードを使えば
ゲーム内と同じ結果が得られる(例: アーティファクトの銘)。
"""

from __future__ import annotations

import struct
import unicodedata
from typing import Callable, Iterator

from .data import AliasData, Mix
from .netrandom import NetRandom, to_int32

_FAIL_TRIES = 10000


def _f32(x: float) -> float:
    """C# の float (単精度) に丸める。"""
    return struct.unpack("<f", struct.pack("<f", x))[0]


class AliasGenerator:
    """Elin の異名ジェネレータ。

    >>> gen = AliasGenerator.from_game_dir("/path/to/Elin")   # doctest: +SKIP
    >>> gen.random_alias()                                     # doctest: +SKIP
    '終焉を呼ぶ魔王'
    """

    def __init__(self, data: AliasData, seed: int | None = None, rng: NetRandom | None = None) -> None:
        if not data.rows:
            raise ValueError("alias data has no rows")
        self.data = data
        self.rows = data.rows
        self.mix: list[Mix] = data.mix
        self.rng = rng if rng is not None else NetRandom(seed)
        self.last_item: dict[str, str] = self.rows[0]

    # ------------------------------------------------------------------ 構築
    @classmethod
    def from_game_dir(cls, game_dir, lang: str = "JP", seed: int | None = None) -> "AliasGenerator":
        return cls(AliasData.from_game_dir(game_dir, lang), seed=seed)

    @classmethod
    def bundled(cls, lang: str = "JP", seed: int | None = None) -> "AliasGenerator":
        return cls(AliasData.bundled(lang), seed=seed)

    # ------------------------------------------------------------------ 乱数 (Rand)
    def seed(self, seed: int | None) -> None:
        """``Rand.SetSeed`` 相当。乱数生成器を作り直す。"""
        self.rng = NetRandom(seed)

    def _range(self, lo: int, hi: int) -> int:  # Rand.Range(int, int)
        return self.rng.next(hi - lo) + lo

    def _rangef(self, lo: float, hi: float) -> float:  # Rand.Range(float, float)
        return _f32(self.rng.next_double() * (hi - lo) + lo)

    def _rnd(self, a: int) -> int:  # AliasGen.rnd → Rand.Range(0, a)
        return self._range(0, a)

    # ------------------------------------------------------------------ 部品 (N / N2 / A / A2)
    def _pick_row(self) -> dict[str, str] | None:
        d = self.rows[self._range(1, len(self.rows))]
        last = self.last_item
        if d is last or d.get("k", "") == last.get("k", ""):
            return None
        return d

    def _pick_pair(self, k1: str, k2: str, fail: str) -> str:
        for _ in range(_FAIL_TRIES):
            d = self._pick_row()
            if d is None:
                continue
            first, second = (k1, k2) if self._range(0, 2) == 0 else (k2, k1)
            for key in (first, second):
                if d.get(key, "") != "":
                    self.last_item = d
                    return d[key]
        return fail

    def N(self) -> str:
        """名詞 (n1 / n2)。例: 剣、王国"""
        return self._pick_pair("n1", "n2", "(N)")

    def N2(self) -> str:
        """カタカナ名詞 (n3 / n4)。例: ソード、キングダム"""
        return self._pick_pair("n3", "n4", "(N2)")

    def A2(self) -> str:
        """カタカナ形容 (a9 / a10)。例: エンドレス"""
        return self._pick_pair("a9", "a10", "(A2)")

    def A(self) -> str:
        """形容 (a1〜a8)。例: 剣に生きる"""
        for _ in range(_FAIL_TRIES):
            d = self.rows[self._range(1, len(self.rows))]
            last = self.last_item
            if d is not last and d.get("k", "") != last.get("k", ""):
                key = "a%d" % self._range(1, 9)
                if d.get(key, "") != "":
                    self.last_item = d
                    return d[key]
        return "(A)"

    def _token(self, s: str) -> str:
        if s == "N":
            return self.N()
        if s == "N2":
            return self.N2()
        if s == "A":
            return self.A()
        if s == "A2":
            return self.A2()
        return s

    # ------------------------------------------------------------------ 組み立て
    def _mix_alias(self, builtin: bool) -> str:
        if builtin:
            # 上から順に 1/chance で判定し、当たった型を採用
            for m in self.mix:
                if self._rnd(m.chance) == 0:
                    return "".join(self._token(t) for t in m.texts)
        # 重み 1/chance の重み付き抽選
        # LINQ の Sum(float) は double で足して最後に float へ丸める
        total = 0.0
        for m in self.mix:
            total += self._inv(m.chance)
        mx = _f32(total)
        num = self._rangef(0.0, mx)
        acc = 0.0
        for m in self.mix:
            acc = _f32(acc + self._inv(m.chance))
            if num <= acc:
                return "".join(self._token(t) for t in m.texts)
        return self.N()

    @staticmethod
    def _inv(chance: int) -> float:
        if chance == 0:
            return float("inf")
        return _f32(1.0 / _f32(float(chance)))

    def random_alias(self, builtin: bool = False) -> str:
        """``AliasGen.GetRandomAlias()`` 相当。

        builtin=False: キャラクターの異名(ゲーム内の通常の生成)
        builtin=True : アーティファクトの銘などで使われるモード
        """
        self.last_item = self.rows[0]
        return title_case(self._mix_alias(builtin))

    __call__ = random_alias

    def generate(self, n: int, builtin: bool = False) -> list[str]:
        return [self.random_alias(builtin) for _ in range(n)]

    def stream(self, builtin: bool = False) -> Iterator[str]:
        while True:
            yield self.random_alias(builtin)

    # ------------------------------------------------------------------ ゲーム内再現
    def artifact_alias(self, uid: int, game_seed: int) -> str:
        """伝説/神話級装備の銘 (Thing.cs) を再現する。

        ゲーム内では ``Rand.UseSeed(uid + game.seed, () => GetRandomAlias(builtin: true))``
        で生成され、その後 Bracket(2 or 3) で括弧が付く。ここでは括弧なしの文字列を返す。
        生成後もこのインスタンスの乱数状態は元に戻る。
        """
        saved = self.rng
        try:
            seed = to_int32(uid + game_seed)
            # Rand.SetSeed(-1) は「シード無し」扱いになるので本家でも結果はランダム
            self.rng = NetRandom(None if seed == -1 else seed)
            return self.random_alias(builtin=True)
        finally:
            self.rng = saved

    # ------------------------------------------------------------------ 情報
    def pattern_probabilities(self, builtin: bool = False) -> list[tuple[str, float]]:
        """各型が選ばれる確率(理論値)。"""
        inv = [1.0 / m.chance if m.chance else float("inf") for m in self.mix]
        total = sum(inv)
        weighted = [w / total for w in inv]
        if not builtin:
            return [("+".join(m.texts), p) for m, p in zip(self.mix, weighted)]
        remain = 1.0
        probs = []
        for m in self.mix:
            p = remain * (1.0 / m.chance if m.chance else 1.0)
            probs.append(p)
            remain -= p
        return [("+".join(m.texts), p + remain * w) for m, p, w in zip(self.mix, probs, weighted)]


# ---------------------------------------------------------------------- TitleCase
_SEPARATOR_CATEGORIES = {
    "Zs", "Zl", "Zp", "Cc", "Cf", "Pc", "Pd", "Ps", "Pe", "Pi", "Pf", "Po", "Sm", "Sc", "Sk", "So",
}


def _is_letter(ch: str) -> bool:
    return unicodedata.category(ch) in ("Lu", "Ll", "Lt", "Lm", "Lo")


def title_case(s: str) -> str:
    """.NET ``TextInfo.ToTitleCase`` 相当(全部大文字の単語はそのまま残る)。

    日本語・中国語では実質的に何も変わらない。英語版のための処理。
    """
    out: list[str] = []
    i, n = 0, len(s)
    while i < n:
        ch = s[i]
        if not _is_letter(ch):
            out.append(ch)
            i += 1
            continue
        out.append(ch.title() if len(ch.title()) == 1 else ch.upper())
        has_lower = unicodedata.category(ch) == "Ll"
        i += 1
        seg_start = i
        while i < n:
            c = s[i]
            if _is_letter(c):
                if unicodedata.category(c) == "Ll":
                    has_lower = True
                i += 1
            elif c == "'":
                i += 1
                seg = s[seg_start:i]
                out.append(seg.lower() if has_lower else seg)
                seg_start = i
                has_lower = True
            elif unicodedata.category(c) not in _SEPARATOR_CATEGORIES:
                i += 1
            else:
                break
        seg = s[seg_start:i]
        out.append(seg.lower() if has_lower else seg)
    return "".join(out)


_default: AliasGenerator | None = None


def random_alias(lang: str = "JP", builtin: bool = False) -> str:
    """同梱データを使って異名を 1 つ作る簡易関数。"""
    global _default
    if _default is None or _default.data.lang != lang.upper():
        _default = AliasGenerator.bundled(lang)
    return _default.random_alias(builtin)
