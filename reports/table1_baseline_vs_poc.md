Baseline: `baseline` (git b0ce8bf, seed 42) · PoC: `poc` (git b0ce8bf, seed 42)

| Metric (unit) | Slice | Baseline | PoC | Δ abs | Δ rel | Better | N |
|---|---|---|---|---|---|---|---|
| **Defect Recall@B** (GT defects in top-B / GT defects) | all | 0.4500 | 0.9000 | 0.4500 | +100.0% | higher | 40 |
| Precision@B (GT defects in top-B / B) | all | 0.4500 | 0.9000 | 0.4500 | +100.0% | higher | 40 |
| Defect-type accuracy (GT defects) (fraction) | all | 0.2222 | 0.8889 | 0.6667 | +300.0% | higher | 18 |
| False alarm in top-B (clean images in top-B / clean images) | all | 0.5500 | 0.1000 | -0.4500 | -81.8% | lower | 40 |
| False alarm in top-B (clean images in top-B / clean images) | light=day | 0.5833 | 0.0833 | -0.5000 | -85.7% | lower | 24 |
| False alarm in top-B (clean images in top-B / clean images) | light=dusk | 0.5000 | 0.0000 | -0.5000 | -100.0% | lower | 8 |
| False alarm in top-B (clean images in top-B / clean images) | light=night | 0.5000 | 0.2500 | -0.2500 | -50.0% | lower | 8 |
| Runtime / 100 items (s) | all | 0.3356 | 2.6467 | | | lower | |
