"""期待値は .NET の System.Random と、逆コンパイルした AliasGen を .NET 上で動かした結果から取ったもの。

実行: python -m unittest discover -s tests
"""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from elinalias import AliasData, AliasGenerator, NetRandom, title_case  # noqa: E402

DATA_DIR = Path(__file__).resolve().parents[1] / "src" / "elinalias" / "data"


class TestNetRandom(unittest.TestCase):
    CASES = {
        0: ([726, 817, 768, 558, 206], 0.5588847946184151),
        42: ([668, 140, 125, 522, 168], 0.26259267528662117),
        -5: ([338, 284, 262, 625, 463], 0.9283738280312968),
        -2147483648: ([726, 817, 768, 558, 206], 0.5588847936870925),
        2147483647: ([726, 817, 768, 558, 206], 0.5588847936870925),
    }

    def test_matches_dotnet(self):
        for seed, (ints, dbl) in self.CASES.items():
            r = NetRandom(seed)
            self.assertEqual([r.next(1000) for _ in range(5)], ints, seed)
            self.assertEqual(r.next_double(), dbl, seed)


class TestTitleCase(unittest.TestCase):
    def test_basic(self):
        self.assertEqual(title_case("skeleton of sorrow"), "Skeleton Of Sorrow")
        self.assertEqual(title_case("the NASA hero"), "The NASA Hero")
        self.assertEqual(title_case("剣に生きる王子"), "剣に生きる王子")


@unittest.skipUnless((DATA_DIR / "alias_JP.json").exists(), "run `elinalias extract` first")
class TestGeneratorJP(unittest.TestCase):
    def setUp(self):
        self.data = AliasData.from_json(DATA_DIR / "alias_JP.json")

    def test_seeded_sequence(self):
        g = AliasGenerator(self.data, seed=42)
        self.assertEqual(
            g.generate(5),
            ["昨日を偲ぶボス", "地震の恋", "医師も砂", "サッドクロック", "やさしすぎた神聖"],
        )

    def test_artifact(self):
        g = AliasGenerator(self.data)
        self.assertEqual(
            [g.artifact_alias(uid, 1000) for uid in range(3)],
            ["ザ・調教", "笑えない敗者", "妖しい堕落"],
        )

    def test_probabilities_sum_to_one(self):
        g = AliasGenerator(self.data, seed=0)
        for builtin in (False, True):
            total = sum(p for _, p in g.pattern_probabilities(builtin))
            self.assertAlmostEqual(total, 1.0)


if __name__ == "__main__":
    unittest.main()
