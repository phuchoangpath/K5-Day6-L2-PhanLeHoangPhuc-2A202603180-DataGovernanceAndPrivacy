Baseline: `baseline` (git b0ce8bf, seed 42) · PoC: `poc` (git b0ce8bf, seed 42)

| Metric (unit) | Slice | Baseline | PoC | Δ abs | Δ rel | Better | N |
|---|---|---|---|---|---|---|---|
| **Defect Recall@B** (GT defects in top-B / GT defects) | all | 0.4500 | 0.7500 | 0.3000 | +66.7% | higher | 40 |
| Precision@B (GT defects in top-B / B) | all | 0.4500 | 0.7500 | 0.3000 | +66.7% | higher | 40 |
| Defect-type accuracy (GT defects) (fraction) | all | 0.2222 | 0.9333 | 0.7111 | +320.0% | higher | 15 |
| False alarm in top-B (clean images in top-B / clean images) | all | 0.5500 | 0.2500 | -0.3000 | -54.5% | lower | 40 |
| False alarm in top-B (clean images in top-B / clean images) | light=day | 0.5833 | 0.2500 | -0.3333 | -57.1% | lower | 24 |
| False alarm in top-B (clean images in top-B / clean images) | light=dusk | 0.5000 | 0.2500 | -0.2500 | -50.0% | lower | 8 |
| False alarm in top-B (clean images in top-B / clean images) | light=night | 0.5000 | 0.2500 | -0.2500 | -50.0% | lower | 8 |
| Runtime / 100 items (s) | all | 0.3356 | 2.6467 | | | lower | |
