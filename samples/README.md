# samples/

実案件の設備図 PDF（給排水・空調・ガス／消火）をここに置きます。

- **mock 実行**は入力 PDF が無くても動きます（`GOPIPE_LLM_PROVIDER=mock`）。疎通確認・デモ用。
- **本番（Claude）で精度検証**する際は、ここへ設備図 PDF を置いて実行します:

  ```bash
  make run-takeoff PROVIDER=claude INPUT=samples/あなたの設備図.pdf
  ```

精度を上げるコツ: 平面図だけでなく**系統図・機器表・仕様書**を含む PDF を渡すと、
立管・隠蔽配管の延長や機器台数の確定精度が上がります。
