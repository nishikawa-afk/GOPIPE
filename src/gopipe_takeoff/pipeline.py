from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from utils import get_logger

from .classifier import classify
from .dictionary import TakeoffDictionary
from .excel_writer import write_excel
from .extractor import extract
from .locale import resolve as resolve_knowledge
from .marker import write_marker_pdf
from .models import TakeoffItem
from .pdf_loader import load_pdf

logger = get_logger("gopipe.track_a")

DICTIONARY_PATH = Path(__file__).resolve().parents[2] / "prompts" / "dictionary.yaml"


@dataclass
class TakeoffResult:
    items: list[TakeoffItem]
    excel_path: Path
    marker_pdf_path: Path | None


class TakeoffPipeline:
    def __init__(self, *, dictionary_path: str | Path | None = None) -> None:
        self.dictionary = TakeoffDictionary.from_yaml(
            dictionary_path or resolve_knowledge("dictionary.yaml")
        )

    def run(
        self,
        input_pdf: str | Path,
        out_dir: str | Path,
        *,
        grid: int = 1,
        two_pass: bool = False,
        use_text_table: bool = True,
    ) -> TakeoffResult:
        """PDF → 拾い出し Excel + マーカー PDF を出力する。

        grid > 1 のときは PDF 各ページを grid×grid タイルに分割して LLM 抽出
        （API call 数 grid^2 倍、精度向上を狙う）。bbox 情報はタイル化時には
        棄てるため、マーカー PDF は出力されない。

        two_pass=True のとき:
          Pass1: 通常の拾い出し
          Pass2: 漏れ確認 (verification) パス — Pass1 の結果を見せた上で追加項目を抽出
          API call 数は +1/ページ（grid=1 時は計 2 call/ページ）。
        """
        input_pdf = Path(input_pdf)
        out_dir = Path(out_dir)
        out_dir.mkdir(parents=True, exist_ok=True)

        logger.info("loading PDF: %s (grid=%d, two_pass=%s)", input_pdf, grid, two_pass)
        drawing = load_pdf(input_pdf, grid=grid)
        logger.info("pages=%d", len(drawing.pages))

        logger.info("extracting items via LLM (use_text_table=%s) ...", use_text_table)
        raw_items = extract(drawing, two_pass=two_pass, use_text_table=use_text_table)
        logger.info("extracted=%d items", len(raw_items))

        # その会社が育てた別名を辞書に混ぜてから分類する。これを忘れると、
        # 現場がいくら直しても次回の結果が変わらない（＝堀が効かない）。
        from .learned import current_org, load_aliases

        try:
            learned = load_aliases()
            if learned:
                n = self.dictionary.add_learned(learned)
                logger.info("learned aliases merged: %d (org=%s)", n, current_org())
        except Exception as e:  # noqa: BLE001  堀が引けなくても拾い出し自体は続ける
            logger.warning("learned aliases unavailable: %s", e)

        logger.info("classifying ...")
        items = classify(raw_items, self.dictionary)

        excel_path = out_dir / "拾い出し表.xlsx"
        logger.info("writing excel: %s", excel_path)
        write_excel(items, excel_path)

        marker_path: Path | None = None
        if input_pdf.exists() and any(it.bbox for it in items):
            marker_path = out_dir / "AIマーカー付き図面.pdf"
            try:
                logger.info("writing marker pdf: %s", marker_path)
                write_marker_pdf(input_pdf, items, marker_path)
            except Exception as e:
                logger.warning("marker pdf failed: %s", e)
                marker_path = None

        return TakeoffResult(items=items, excel_path=excel_path, marker_pdf_path=marker_path)


def run_takeoff(
    input_pdf: str | Path,
    out_dir: str | Path,
    *,
    grid: int = 1,
    two_pass: bool = False,
    use_text_table: bool = True,
) -> TakeoffResult:
    return TakeoffPipeline().run(
        input_pdf, out_dir, grid=grid, two_pass=two_pass, use_text_table=use_text_table
    )
