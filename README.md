# elinalias

Elin の異名(エイリアス)を Python で生成するライブラリです。
`Plugins.NameGen.dll` の `AliasGen` を逆コンパイルし、その処理をそのまま移植しています。
乱数(`System.Random`)と float の丸めも本家に合わせているので、同じシードならゲームと同じ文字列になります。

* 依存ライブラリなし(標準ライブラリのみ、Python 3.9+)
* JP / EN / CN に対応
* アーティファクト(伝説・神話級装備)の銘を `uid` とゲームシードから再現できる

## セットアップ

ゲームデータは同梱していません。最初に Elin のフォルダから JSON を書き出してください。

```sh
pip install -e .
elinalias extract /path/to/elin      # src/elinalias/data/alias_{JP,EN,CN}.json を作る
```

`extract` を使わずに、毎回ゲームフォルダから直接読むこともできます(`--game-dir` または `from_game_dir`)。

## 使い方

```python
from elinalias import AliasGenerator, random_alias

random_alias()                           # 同梱データで 1 つ生成
gen = AliasGenerator.bundled("JP", seed=42)
gen.generate(5)
# ['昨日を偲ぶボス', '地震の恋', '医師も砂', 'サッドクロック', 'やさしすぎた神聖']

gen = AliasGenerator.from_game_dir("/path/to/elin", lang="EN")
gen.random_alias()                       # 'Skeleton Of Sorrow' など

gen.artifact_alias(uid=0, game_seed=1000)  # 'ザ・調教'  (ゲーム内では《》などの括弧が付く)

gen.N(), gen.N2(), gen.A(), gen.A2()      # 部品単位で取り出す
gen.pattern_probabilities()               # 各型の出現確率
```

```sh
elinalias -n 10                 # 10 個生成 (gen は省略できる)
elinalias gen -n 5 --seed 42 --lang EN
elinalias artifact 12345 67890  # uid と game.seed からアーティファクトの銘を再現
elinalias stats                 # 型ごとの確率
```

## 生成アルゴリズム(Elin)

1. `Alias_mix.txt` の各行 `chance,型` から、重み `1/chance` で型を 1 つ選ぶ
   (JP では `A+N` が約 56%、`N+の+N` が約 19%、`A2+N2` が約 11%)。
   * `builtin=True`(アーティファクト銘)のときは、まず上の行から順に `rnd(chance)==0` で当たり判定をする。
     どれも当たらなかったときだけ上の重み付き抽選に入る。
2. 型の中の `N / N2 / A / A2` を `Alias.xlsx` から引いて埋める。
   * `N` = n1/n2(名詞)、`N2` = n3/n4(カタカナ名詞)、`A` = a1〜a8(形容)、`A2` = a9/a10(カタカナ形容)
   * 行は `Rand.Range(1, Count)` で選ぶので、先頭の行(list[0])は選ばれない
   * 直前に採用した語と同じ行、または同じカテゴリ `k` の行は弾く(「万能」も例外なし)
3. 最後に `TextInfo.ToTitleCase` をかける(英語版向け)。

Elona と違って 14 文字の長さ制限はありません。

### 細かい仕様

* `Alias.xlsx` は Excel の 5 行目から読まれます(`startIndex = 5`)。そのため JP では 4 行目の「王子」の行は使われません。
  5 行目の「皇女」の行も list[0] になるので選ばれません。
* `artifact_alias` で `uid + game_seed == -1` になる場合、本家の `Rand.SetSeed(-1)` は「シードなし」扱いになります。
  そのため本家でも結果はランダムです。
* 本家の重み付き抽選は単精度 float で計算されています。Mono の JIT が float を倍精度で計算した場合、
  境界ぎりぎりの値(確率はおよそ 1e-7 程度)では結果がずれる可能性があります。

## 検証

`tests/` の期待値は 2 つの方法で取りました。

* .NET 8 の `System.Random` の出力
* 逆コンパイルした `AliasGen.cs` を .NET 8 上で動かした出力

開発時には、JP/EN/CN × 13 シード × builtin 有無の 78 通りで比較しています。
各パターンで異名 1000 個とアーティファクト銘 50 個を出し、すべて一致しました。
`Alias.xlsx` の読み込み結果も、NPOI で読んだ結果と一致しています。

```sh
python -m unittest discover -s tests
```

## 解析について
ゲームデータ解析は、MacOSでclaude-opus-5.5を使用して行いました。