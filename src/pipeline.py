"""PoC PIPELINE — Track T02: Raw QC Triage (Solo: Phan Le Hoang Phuc - 2A202603180).

Automated 5-step data governance pipeline:
    01 load      input + provenance check (manifest.csv) & images.csv
    02 process   multi-feature QC (Laplacian blur, local glare, severe dark, JPEG blockiness)
                 with camera-optics and lighting normalization
    03 rank      prioritise top-B review queue + generate interactive HTML contact sheet
    04 review    human-in-the-loop: load review_queue_reviewed.csv, apply overrides, audit log
    05 decide    GO / HOLD / REWORK policy gate with reason_code & owner signature
"""
from __future__ import annotations

from pathlib import Path
import numpy as np
import pandas as pd

from .common.contact_sheet import render_contact_sheet
from .common.context import RunContext
from .common.decision import Decision, write_decision
from .common.image_ops import brightness_stats, laplacian_variance, load_rgb, to_gray
from .common.manifest import verify_manifest
from .common.review import apply_overrides, load_review_decisions, make_review_queue, write_review_queue
from .metrics.tracks import get_track


# ---------------------------------------------------------------- 01 load
def load(ctx: RunContext) -> dict:
    if ctx.track != "t02":
        spec = get_track(ctx.track)
        raise NotImplementedError(
            f"Implement load() for {spec.track} ({spec.title}). See docs/tracks/{spec.track.upper()}.md"
        )

    manifest = ctx.input_dir / "manifest.csv"
    problems = verify_manifest(manifest) if manifest.exists() else [{"problem": "no_manifest"}]
    if problems:
        ctx.audit.log(actor="pipeline", action="provenance_problems", item_id=str(manifest), after=problems[:20])
        if ctx.config.get("strict_provenance", True):
            raise ValueError(f"provenance check failed ({len(problems)} problems), first: {problems[:3]}")
    
    images_csv = ctx.input_dir / "images.csv"
    if not images_csv.exists():
        raise FileNotFoundError(f"Missing required images.csv at {images_csv}")
    
    df_images = pd.read_csv(images_csv)
    return {
        "manifest": pd.read_csv(manifest) if manifest.exists() else None,
        "images": df_images,
    }


# ---------------------------------------------------------------- Helper QC Metrics
def _calc_local_glare(gray: np.ndarray, grid: tuple[int, int] = (4, 6)) -> float:
    """Calculate maximum saturation fraction across localized grid patches."""
    H, W = gray.shape
    gh, gw = grid
    ch, cw = max(1, H // gh), max(1, W // gw)
    max_sat = 0.0
    for r in range(gh):
        for c in range(gw):
            patch = gray[r * ch : (r + 1) * ch, c * cw : (c + 1) * cw]
            sat = float((patch > 240).mean())
            if sat > max_sat:
                max_sat = sat
    return max_sat


def _calc_jpeg_blockiness(gray: np.ndarray) -> float:
    """Estimate 8x8 JPEG boundary discontinuity ratio."""
    H, W = gray.shape
    if H < 16 or W < 16:
        return 1.0

    # Horizontal boundary difference
    diff_h = np.abs(gray[:, 1:] - gray[:, :-1])
    cols = np.arange(W - 1)
    boundary_cols = (cols % 8 == 7)
    within_cols = ~boundary_cols
    b_mean_h = float(diff_h[:, boundary_cols].mean()) if np.any(boundary_cols) else 0.0
    w_mean_h = float(diff_h[:, within_cols].mean()) if np.any(within_cols) else 1e-4

    # Vertical boundary difference
    diff_v = np.abs(gray[1:, :] - gray[:-1, :])
    rows = np.arange(H - 1)
    boundary_rows = (rows % 8 == 7)
    within_rows = ~boundary_rows
    b_mean_v = float(diff_v[boundary_rows, :].mean()) if np.any(boundary_rows) else 0.0
    w_mean_v = float(diff_v[within_rows, :].mean()) if np.any(within_rows) else 1e-4

    ratio = (b_mean_h / (w_mean_h + 1e-4) + b_mean_v / (w_mean_v + 1e-4)) / 2.0
    return float(ratio)


# ---------------------------------------------------------------- 02 process
def process(ctx: RunContext, data: dict) -> pd.DataFrame:
    if ctx.track != "t02":
        spec = get_track(ctx.track)
        raise NotImplementedError(
            f"Implement process() for {spec.track} ({spec.title}). See docs/tracks/{spec.track.upper()}.md"
        )

    images_df = data["images"]
    rows = []

    for r in images_df.itertuples(index=False):
        img_path = ctx.input_dir / r.path
        img = load_rgb(img_path)
        gray = to_gray(img)

        # Raw features
        lap = laplacian_variance(img)
        bri = brightness_stats(img)
        max_sat = _calc_local_glare(gray)
        blockiness = _calc_jpeg_blockiness(gray)

        # Domain normalizations (camera optics and lighting condition)
        cam_factor = 0.50 if getattr(r, "camera_id", "cam_A") == "cam_B" else 1.0
        light = getattr(r, "light", "day")
        light_factor = 0.70 if light == "night" else (0.85 if light == "dusk" else 1.0)
        expected_lap = 800.0 * cam_factor * light_factor

        # Component defect scores
        # 1. Blur: sharpness severely below expectation
        s_blur = max(0.0, float(1.0 - lap / (expected_lap * 0.25))) * 3.5 if lap < expected_lap * 0.25 else 0.0
        
        # 2. Glare: localized saturation > 4% of patch
        s_glare = max(0.0, float(max_sat - 0.04) / 0.12) * 5.0
        
        # 3. Dark: severe underexposure (crushed darks + low mean intensity)
        s_dark = (max(0.0, float(bri["frac_dark"] - 0.75) / 0.20) * 3.0 + 
                  max(0.0, float(18.0 - bri["mean"]) / 10.0) * 3.0)
        
        # 4. Compression: 8x8 block boundary ratio > 1.8
        s_comp = max(0.0, float(blockiness - 1.8) / 0.8) * 4.0

        scores = {
            "blur": s_blur,
            "glare": s_glare,
            "dark": s_dark,
            "compression": s_comp,
        }
        best_defect = max(scores, key=scores.get)
        max_s = scores[best_defect]
        
        # Overall suspiciousness score
        total_score = max_s + 0.1 * sum(scores.values())
        is_defect = total_score > 0.50

        rows.append({
            "image_id": r.image_id,
            "score": round(float(total_score), 6),
            "pred_defect_type": best_defect if is_defect else "none",
            "pred_action": "RECAPTURE" if is_defect else "KEEP",
            "reason": f"detected_{best_defect}" if is_defect else "quality_ok",
            "path": r.path,
            "camera_id": getattr(r, "camera_id", ""),
            "light": getattr(r, "light", ""),
            "split": getattr(r, "split", ""),
            "laplacian_var": round(lap, 2),
            "mean_brightness": round(bri["mean"], 2),
            "max_local_sat": round(max_sat, 4),
            "blockiness": round(blockiness, 4),
        })

    return pd.DataFrame(rows)


# ---------------------------------------------------------------- 03 rank
def rank(ctx: RunContext, scored: pd.DataFrame) -> pd.DataFrame:
    budget = int(ctx.param("budget", 20))
    if "score" not in scored.columns:
        raise ValueError("rank(): process() output needs a numeric `score` column")

    q = make_review_queue(
        scored,
        id_col="image_id",
        score_col="score",
        budget=budget,
        reason_col="reason",
        action_col="pred_action",
        slice_col="light",
        evidence_col="path",
    )
    write_review_queue(q, ctx.out("review_queue.csv"))

    # Render interactive contact sheet for human reviewer
    contact_sheet_path = ctx.out("contact_sheet.html")
    render_contact_sheet(
        q,
        contact_sheet_path,
        image_col="evidence_path",
        image_root=ctx.input_dir,
        title=f"T02 Review Queue (Top {budget} Suspicious Items) - Phan Le Hoang Phuc",
    )

    return q


# ---------------------------------------------------------------- 04 review
def review(ctx: RunContext, scored: pd.DataFrame, queue: pd.DataFrame) -> pd.DataFrame:
    reviewed_path = ctx.output_dir / "review_queue_reviewed.csv"
    if reviewed_path.exists():
        reviewed = load_review_decisions(reviewed_path)
        ctx.stats["n_reviewed"] = len(reviewed)
        # Apply overrides if reviewer modified action or score
        if "override_value" in reviewed.columns and "pred_action" in scored.columns:
            scored = apply_overrides(scored, reviewed, id_col="image_id", value_col="pred_action", audit=ctx.audit)
    return scored


# ---------------------------------------------------------------- 05 decide
def decide(ctx: RunContext, final: pd.DataFrame) -> Decision:
    budget = int(ctx.param("budget", 20))
    top_items = final.sort_values("score", ascending=False).head(budget)
    top_defects = (top_items["pred_action"] == "RECAPTURE").sum()
    defect_fraction = top_defects / max(1, len(top_items))

    owner = ctx.config.get("owner", "Phan Le Hoang Phuc (2A202603180) - Solo Lead & Reviewer")

    if defect_fraction >= 0.40:
        status = "REWORK"
        reason_code = "HIGH_DEFECT_RATE"
        reason = f"High defect concentration: {top_defects}/{len(top_items)} items in top review queue flagged for recapture."
    elif defect_fraction >= 0.15:
        status = "HOLD"
        reason_code = "SUSPICIOUS_BATCH"
        reason = f"Moderate defect rate: {top_defects}/{len(top_items)} items require manual audit and reinspection."
    else:
        status = "GO"
        reason_code = "QUALITY_GATE_PASSED"
        reason = f"Batch quality acceptable: only {top_defects}/{len(top_items)} items in review queue require recapture."

    return Decision(
        status=status,
        reason_code=reason_code,
        reason=reason,
        owner=owner,
        scope=ctx.track,
        evidence=[str(ctx.out("ranked_review.csv")), str(ctx.out("review_queue.csv"))],
    )


def run(ctx: RunContext) -> None:
    spec = get_track(ctx.track)
    data = load(ctx)
    scored = process(ctx, data)
    ctx.stats["n_items"] = len(scored)
    queue = rank(ctx, scored)
    final = review(ctx, scored, queue)
    
    # Sort by score descending for ranked_review.csv contract
    final = final.sort_values("score", ascending=False, kind="mergesort").reset_index(drop=True)

    # Write out/ranked_review.csv ensuring required contract columns
    output_cols = spec.pred_columns + [c for c in final.columns if c not in spec.pred_columns]
    final[output_cols].to_csv(ctx.out(spec.pred_file), index=False)
    
    # Save decision
    write_decision(decide(ctx, final), ctx.out("decision.json"), ctx.out("decision_log.csv"))
