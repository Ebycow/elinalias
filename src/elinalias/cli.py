"""コマンドライン: ``elinalias`` / ``python -m elinalias``"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .data import LANG_DIRS, AliasData, extract
from .generator import AliasGenerator


def _load(args) -> AliasGenerator:
    if args.game_dir:
        data = AliasData.from_game_dir(args.game_dir, args.lang)
    else:
        data = AliasData.bundled(args.lang)
    return AliasGenerator(data, seed=args.seed)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="elinalias", description="Elin の異名ジェネレータ")
    sub = p.add_subparsers(dest="cmd")

    def common(sp):
        sp.add_argument("--lang", default="JP", choices=sorted(LANG_DIRS), help="言語 (既定: JP)")
        sp.add_argument("--game-dir", help="Elin のフォルダ。省略時は同梱 JSON を使う")
        sp.add_argument("--seed", type=int, default=None, help="乱数シード (System.Random 互換)")

    g = sub.add_parser("gen", help="異名を生成する(既定のコマンド)")
    common(g)
    g.add_argument("-n", "--count", type=int, default=10)
    g.add_argument("--builtin", action="store_true", help="builtin モード(アーティファクト銘と同じ)")

    a = sub.add_parser("artifact", help="アーティファクトの銘を uid とゲームシードから再現")
    common(a)
    a.add_argument("uid", type=int)
    a.add_argument("game_seed", type=int)

    s = sub.add_parser("stats", help="各型の出現確率を表示")
    common(s)
    s.add_argument("--builtin", action="store_true")

    e = sub.add_parser("extract", help="ゲームフォルダからデータを JSON に書き出す")
    e.add_argument("game_dir")
    e.add_argument("--out", default=str(Path(__file__).parent / "data"), help="出力先 (既定: パッケージ内 data/)")
    e.add_argument("--lang", action="append", choices=sorted(LANG_DIRS))

    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv or argv[0] not in {"gen", "artifact", "stats", "extract", "-h", "--help"}:
        argv.insert(0, "gen")
    args = p.parse_args(argv)

    if args.cmd == "extract":
        for path in extract(args.game_dir, args.out, args.lang):
            print(f"wrote {path}")
        return 0

    gen = _load(args)
    if args.cmd == "gen":
        for _ in range(args.count):
            print(gen.random_alias(builtin=args.builtin))
    elif args.cmd == "artifact":
        print(gen.artifact_alias(args.uid, args.game_seed))
    elif args.cmd == "stats":
        for pattern, prob in sorted(gen.pattern_probabilities(args.builtin), key=lambda x: -x[1]):
            print(f"{prob * 100:6.2f}%  {pattern}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
