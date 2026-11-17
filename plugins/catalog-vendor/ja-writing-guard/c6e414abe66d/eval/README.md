# 精度の測り方

```bash
python eval/run_eval.py                       # このプラグインだけ
# 他の製品の規則とも比べる（各製品を clone しておく）
git clone https://github.com/nanaism/yomiyasu ../yomiyasu
git clone https://github.com/coji/natural-japanese ../natural-japanese
uv venv ../njenv && VIRTUAL_ENV=../njenv uv pip install "sudachipy>=0.6.8" "sudachidict-core>=20240409"
python eval/run_eval.py --yomiyasu ../yomiyasu --natural-japanese ../natural-japanese \
    --nj-python ../njenv/bin/python --baselines eval/baselines --json eval/results.json
```

## データと経緯

- データ: `eval/data/`（出典とライセンスは [data/README.md](data/README.md)）。
- 規則は `dev` の60本（AI っぽい文20・既定の AI 出力20・人20）を見て作りました。
- 1回目の test（今の `tune`）では、検出率50%・誤検知18%で不合格でした。取りこぼしと誤検知を分析して規則を直したため、このデータは測定には使えなくなり、閾値合わせ用の `tune` に回しました。
- そのあと、規則を見ていない書き手と収集役に新しい120本を作らせ、規則を固めてから測ったのが今の `test` です。第三者のレビューで見つかった規則の不具合3件を直したあとにも測り直しましたが、数字は変わっていません。

## 出す数字

- 製品自身の判定基準: それぞれが公開している判定（このプラグインは場面の基準、yomiyasu は指摘1件以上、natural-japanese は diagnose.md の機械スコア70未満、抜き出した規則は1か所以上の一致）。
- dev-tuned: `dev` と `tune` の120本で人の文の誤検知が10%以下になる閾値を選び、そのまま test に当てた値。
- AUC: AI の文と人の文を点数で並べたとき、正しく上下が付く割合。
- det@FP<=10%: test の上で閾値を選んだときの検出率。どの製品にとっても上限の目安で、参考値です。
- `eval/results.json` に、test の各文の点数と混同行列が入っています。

## 比較の対象

`eval/baselines/rules_*.py` は、MIT の各製品の規則を正規表現と語のリストに抜き出したもの（各ファイルの先頭に出典とライセンス）。形態素解析が要る規則は近似で、ID の末尾に `-APPROX` が付いています。yomiyasu と natural-japanese は同梱の検査スクリプトをそのまま呼びます。
