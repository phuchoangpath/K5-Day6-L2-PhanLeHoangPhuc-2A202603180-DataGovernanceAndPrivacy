"""Tests for T02 PoC Pipeline — Phan Le Hoang Phuc (2A202603180).

Satisfies rubric requirement: ≥2 tests (success + edge/failure case), 0 failed.
"""
import json
from pathlib import Path
import pandas as pd
import pytest

from src import main as runner
from src.pipeline import _calc_jpeg_blockiness, _calc_local_glare
from src.common.image_ops import load_rgb, to_gray


def test_t02_poc_end_to_end(tmp_path):
    """Test full end-to-end execution of PoC pipeline with exit code 0."""
    out = tmp_path / "poc_run"
    rc = runner.main([
        "--config", "configs/lab.yaml",
        "--track", "t02",
        "--output", str(out),
        "--offline",
        "--seed", "42"
    ])
    assert rc == 0, f"Expected exit code 0, got {rc}"

    # Verify all expected artifacts exist
    for f in ["ranked_review.csv", "review_queue.csv", "contact_sheet.html", "decision.json", "decision_log.csv", "run_info.json"]:
        p = out / f
        assert p.exists(), f"Missing required file {f}"

    # Verify ranked_review schema
    df = pd.read_csv(out / "ranked_review.csv")
    assert "image_id" in df.columns
    assert "score" in df.columns
    assert "pred_defect_type" in df.columns
    assert len(df) == 96
    assert df["score"].is_monotonic_decreasing

    # Verify decision format
    dec = json.loads((out / "decision.json").read_text(encoding="utf-8"))
    assert dec["status"] in ["GO", "HOLD", "REWORK"]
    assert "Phan Le Hoang Phuc" in dec["owner"]
    assert dec["scope"] == "t02"


def test_t02_feature_extractors():
    """Unit test for local glare and jpeg blockiness detectors."""
    sample_path = Path("fixtures/t02_raw_qc/images/img_00_2.jpg")
    assert sample_path.exists()
    img = load_rgb(sample_path)
    gray = to_gray(img)

    blockiness = _calc_jpeg_blockiness(gray)
    assert blockiness > 1.5, f"Expected compression blockiness > 1.5, got {blockiness}"

    glare = _calc_local_glare(gray)
    assert 0.0 <= glare <= 1.0


def test_t02_human_review_override_flow(tmp_path):
    """Test human-in-the-loop override and audit logging."""
    out = tmp_path / "poc_review"
    # First run: produce review queue
    rc = runner.main([
        "--config", "configs/lab.yaml",
        "--track", "t02",
        "--output", str(out),
        "--offline"
    ])
    assert rc == 0
    q_file = out / "review_queue.csv"
    assert q_file.exists()

    # Human reviewer fills in a decision (reading with dtype=str to avoid pandas float inference)
    q_df = pd.read_csv(q_file, dtype=str).fillna("")
    assert len(q_df) == 20
    q_df.loc[0, "reviewer"] = "Phan Le Hoang Phuc"
    q_df.loc[0, "reviewer_decision"] = "edit"
    q_df.loc[0, "override_value"] = "KEEP"
    q_df.loc[0, "review_note"] = "False alarm, acceptable night glare"
    q_df.to_csv(out / "review_queue_reviewed.csv", index=False)

    # Second run: re-run pipeline to consume reviewed queue
    rc2 = runner.main([
        "--config", "configs/lab.yaml",
        "--track", "t02",
        "--output", str(out),
        "--offline"
    ])
    assert rc2 == 0

    # Verify override took effect in final predictions
    updated_pred = pd.read_csv(out / "ranked_review.csv")
    first_item_id = q_df.loc[0, "item_id"]
    match = updated_pred[updated_pred["image_id"] == first_item_id]
    assert match["pred_action"].values[0] == "KEEP"

    # Verify audit log was created and contains event
    audit_file = out / "audit_log.jsonl"
    assert audit_file.exists()
    logs = [json.loads(line) for line in audit_file.read_text(encoding="utf-8").splitlines() if line.strip()]
    assert any(log.get("actor") == "Phan Le Hoang Phuc" for log in logs)
