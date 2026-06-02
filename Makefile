PROVIDER ?= mock
INPUT ?= samples/dummy_設備図.pdf
OUT ?= out/
SYMPTOM ?= トイレが流れない 水位が上がる
YEAR ?= 2008

.PHONY: setup run-takeoff run-estimate run-application run-emergency run-maintenance test lint

setup:
	python3 -m venv .venv && . .venv/bin/activate && pip install -e ".[dev]"

# mock で一気通貫（APIキー・実PDF不要）。本番は PROVIDER=claude INPUT=... を指定。
#   例: make run-takeoff
#       make run-takeoff PROVIDER=claude INPUT=samples/setsubi.pdf
run-takeoff:
	GOPIPE_LLM_PROVIDER=$(PROVIDER) python scripts/run_takeoff.py --input "$(INPUT)" --out "$(OUT)"

# 見積（F-12）: 拾い出し → 見積書・材料発注書
run-estimate:
	GOPIPE_LLM_PROVIDER=$(PROVIDER) python scripts/run_estimate.py --input "$(INPUT)" --out "$(OUT)"

# 申請（F-16）: 拾い出し → 給水装置工事申込書ドラフト
run-application:
	GOPIPE_LLM_PROVIDER=$(PROVIDER) python scripts/run_application.py --input "$(INPUT)" --out "$(OUT)"

# 透明見積（F-15）: 症状 → 明朗料金カード（PDF不要）。例: make run-emergency SYMPTOM="蛇口から水漏れ"
run-emergency:
	python scripts/run_emergency.py --symptom "$(SYMPTOM)" --out "$(OUT)"

# 予防保全（F-17）: 拾い出し → 配管台帳 → 更新予測 → プラン提案。例: make run-maintenance YEAR=2008
run-maintenance:
	GOPIPE_LLM_PROVIDER=$(PROVIDER) python scripts/run_maintenance.py --input "$(INPUT)" --out "$(OUT)" --installed-year $(YEAR)

test:
	pytest

lint:
	ruff check .
