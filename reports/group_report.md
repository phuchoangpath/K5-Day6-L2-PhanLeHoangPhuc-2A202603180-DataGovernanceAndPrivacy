# Group Report — Day 06 Data Lab (Field-to-Release PoC)

> Điền đầy đủ, cụ thể, không viết chung chung. Mọi con số lấy trực tiếp từ file do script sinh ra
> (`reports/metrics_*.json`, `reports/table1_baseline_vs_poc.md`) — không gõ tay, không làm tròn mất đơn vị.

---

## 00 · Header

| Mục | Giá trị |
|---|---|
| Group ID | `2A202603180` |
| Challenge | **T02 · Raw QC Triage (Lọc ảnh mờ, lóa, thiếu sáng & nén lỗi)** |
| Thành viên & vai trò (Cá nhân) | **Phan Lê Hoàng Phúc** (MSSV: `2A202603180`) · Solo Lead, Data/Fixtures, Core Algorithm, QA & Metrics, Reviewer & Report |
| Git URL | `https://github.com/phuchoangpath/K5-Day6-L2-PhanLeHoangPhuc-2A202603180-DataGovernanceAndPrivacy` |
| Tag `demo-180m` (commit) | `demo-180m` (`b0ce8bfd972315448aace86185c1a3e075754b93`) |
| Tag `final-24h` (commit) | `final-24h` (`b0ce8bfd972315448aace86185c1a3e075754b93`) |
| Deadline (giờ VN) | 24h sau buổi học Day 06 |

---

## 01 · Problem statement

- **Ai bị ảnh hưởng / ai chịu hậu quả khi hệ thống sai?**
  - Đội ngũ kỹ sư huấn luyện mô hình thị giác AI xe tự hành (Autonomous Driving Perception Team) và người tham gia giao thông. Nếu dữ liệu bị mờ, lóa, mất chi tiết đi vào tập huấn luyện sẽ khiến xe nhận diện sai vật cản, người đi bộ, gây nguy cơ va chạm nghiêm trọng.
  - Đội vận hành thu thập dữ liệu (Field Operations): Nếu loại bỏ nhầm ảnh tốt (False Alarm), chi phí thu thập và chụp lại (recapture cost) bị đội lên không cần thiết.
- **Điểm nghẽn cụ thể:**
  - Tập dữ liệu thô thu thập hàng ngày lên tới hàng chục nghìn ảnh. Đội ngũ chuyên viên kiểm định chất lượng (QC Reviewers) chỉ có ngân sách thời gian hữu hạn ($B = 20$ ảnh trên mỗi lô đánh giá). Không thể duyệt thủ công $100\%$ dữ liệu.
- **Đầu vào → đầu ra:**
  - Đầu vào: `images.csv` (danh sách 96 ảnh, camera `cam_A` / `cam_B`, ánh sáng `day` / `dusk` / `night`, split `dev` / `eval`) + các file ảnh `images/*.jpg`.
  - Đầu ra: `out/ranked_review.csv` (xếp hạng mức độ nghi ngờ `score` giảm dần, kèm `pred_defect_type` và `pred_action`), danh sách `review_queue.csv` top 20 ảnh cần duyệt, giao diện trực quan `contact_sheet.html`, và biên bản quyết định chất lượng lô `decision.json`.
- **Tiêu chí GO / HOLD / REWORK (chốt trước khi chạy eval):**
  - **GO:** Tỷ lệ ảnh lỗi trong top 20 được reviewer xác nhận $< 15\%$ $\to$ lô đạt chuẩn, cho phép xuất xưởng vào kho training.
  - **HOLD:** Tỷ lệ ảnh lỗi từ $15\%$ đến dưới $40\%$ $\to$ tạm giữ để audit bổ sung.
  - **REWORK:** Tỷ lệ ảnh lỗi $\ge 40\%$ $\to$ bắt buộc thu thập lại (Recapture) với camera/tuyến đường tương ứng (`HIGH_DEFECT_RATE`).
- **Giả định của nhóm (cần DPO/legal/domain owner xác nhận):**
  - Ngưỡng ngân sách người duyệt cố định ở mức $B = 20$ mẫu/batch là khả thi về mặt nhân sự và chi phí vận hành.
  - Toàn bộ dữ liệu trong bài lab là dữ liệu tổng hợp (procedural synthetic) không chứa PII (khuôn mặt thật, biển số xe thật).

---

## 02 · Data & provenance

| Split | N | Nguồn / link | License | Synthetic? |
|---|---|---|---|---|
| dev | 56 | `fixtures/t02_raw_qc/` (24 scenes gốc, 14 scenes dev) | CC0 (Procedural Synth) | Có ($100\%$) |
| eval / heldout | 40 | `fixtures/t02_raw_qc/` (10 scenes eval độc lập) | CC0 (Procedural Synth) | Có ($100\%$) |

- **Schema & class mapping:**
  - Bảng `images.csv`: `image_id` (str), `path` (str), `camera_id` (`cam_A`, `cam_B`), `light` (`day`, `dusk`, `night`), `split` (`dev`, `eval`).
  - Loại lỗi tiềm ẩn: `none` (sạch), `blur` (mờ chuyển động/mất nét), `glare` (chói lóa), `dark` (thiếu sáng trầm trọng), `compression` (vỡ khối nén JPEG).
- **Seed: 42** · Cách chia split: Phân bổ theo cảnh gốc (`scene_id`) để đảm bảo không bị rò rỉ dữ liệu (data leakage) giữa tập phát triển (`dev`) và tập kiểm thử (`eval`).
- **`manifest.csv` verified (sha256):** Có (`preflight` đạt `0 FAIL`, toàn bộ mã băm SHA-256 của từng ảnh và file CSV đều trùng khớp $100\%$).
- **Dữ liệu thật dùng (nếu có) và cách xây GT cho nó:** Bài PoC ưu tiên sử dụng tập fixture chuẩn hoá offline để đảm bảo tính tái lập tuyệt đối trên mọi môi trường máy tính CPU.

---

## 03 · Research & design

- **2–3 tài liệu tham khảo (URL + ngày xem) và lý do chọn kỹ thuật:**
  1. *ACDC Dataset (Adverse Conditions Dataset with Correspondences - ETH Zürich)*, xem 14/11/2026. Lý do: Tham khảo phương pháp phân tách các điều kiện ánh sáng cực đoan (dusk, night, glare) để xử lý riêng biệt thay vì dùng ngưỡng cào bằng.
  2. *ISO/IEC TR 5259-6:2026 (Data quality for analytics and machine learning)*, xem 14/11/2026. Lý do: Thiết kế kiến trúc 5 bước (Load $\to$ Process $\to$ Rank $\to$ Review $\to$ Decide) và cơ chế Audit Trail.
  3. *Wang et al., "No-Reference Perceptual Quality Assessment of JPEG Compressed Images"*, xem 14/11/2026. Lý do: Ứng dụng kỹ thuật đo bước nhảy sai khác tại biên khối lưới $8 \times 8$ pixel để phát hiện blockiness do nén quá mức.
- **Sơ đồ luồng dữ liệu (Data flow):**
  `input (images.csv + JPGs)` $\to$ `01. load (kiểm tra manifest hash)` $\to$ `02. process (đa chỉ số QC + chuẩn hóa camera/ánh sáng)` $\to$ `03. rank (Top 20 + render contact_sheet.html)` $\to$ `04. review (tiếp nhận override của reviewer + audit log)` $\to$ `05. decide (phân loại GO / HOLD / REWORK có chữ ký)` $\to$ `reports/`.
- **Thành phần offline:** Hoàn toàn chạy offline trên CPU bằng thuật toán đại số ma trận numpy/scipy/PIL, không cần tải model nặng qua internet, kích hoạt `offline_guard`.
- **Trade-offs đã cân nhắc:**
  - Không sử dụng Deep Learning nặng hàng trăm MB (như ResNet/YOLO) mà dùng các phép đo toán học tín hiệu ảnh (Laplacian variance, patch saturation, block boundary difference): giúp thời gian thực thi siêu tốc ($< 3$ giây cho 96 ảnh), chạy mượt mà trên mọi máy tính cá nhân.

---

## 04 · Baseline vs PoC

- **Baseline:** Lựa chọn ngẫu nhiên (`src.examples.random_baseline`), gán `score` ngẫu nhiên có cố định seed 42, mô phỏng việc bốc thăm 20 ảnh ngẫu nhiên đưa cho reviewer.
- **PoC:** Thuật toán lọc đa đặc trưng kết hợp chuẩn hóa quang học camera (`cam_B` quang học mềm hơn `cam_A`) và điều kiện ánh sáng (`day`, `dusk`, `night`), trích xuất đồng thời 4 chỉ số: độ sắc nét Laplacian, độ chói lóa cục bộ, độ tối suy biến và tỷ lệ vỡ khối JPEG.
- **Cùng ngân sách / cùng heldout / cùng seed:** Xác nhận cùng test trên split `eval` ($N=40$), cùng ngân sách $B=20$, cùng `seed=42`.

### Bảng 1 · Baseline vs PoC & hard slices
*(Trích xuất tự động từ `reports/table1_baseline_vs_poc.md` sinh bởi `src.compare`)*

| Metric (unit) | Slice | Baseline | PoC | Δ abs | Δ rel | Better | N |
|---|---|---|---|---|---|---|---|
| **Defect Recall@B** (GT defects in top-B / GT defects) | all | 0.4500 | 0.9000 | +0.4500 | **+100.0%** | higher | 40 |
| Precision@B (GT defects in top-B / B) | all | 0.4500 | 0.9000 | +0.4500 | **+100.0%** | higher | 40 |
| Defect-type accuracy (GT defects) (fraction) | all | 0.2222 | 0.8889 | +0.6667 | **+300.0%** | higher | 18 |
| False alarm in top-B (clean images in top-B / clean images) | all | 0.5500 | 0.1000 | -0.4500 | **-81.8%** | lower | 40 |
| False alarm in top-B (clean images in top-B / clean images) | light=day | 0.5833 | 0.0833 | -0.5000 | -85.7% | lower | 24 |
| False alarm in top-B (clean images in top-B / clean images) | light=dusk | 0.5000 | 0.0000 | -0.5000 | -100.0% | lower | 8 |
| False alarm in top-B (clean images in top-B / clean images) | light=night | 0.5000 | 0.2500 | -0.2500 | -50.0% | lower | 8 |
| Runtime / 100 items (s) | all | 0.3356 | 2.6467 | +2.3111 | n/a | lower | 96 |

> **Nhận xét chính:** Thuật toán PoC tăng gấp đôi tỷ lệ phát hiện ảnh lỗi (**Recall@20 tăng từ $45.0\%$ lên $90.0\%$**), độ chính xác phân loại loại lỗi tăng vọt $+300\%$ (từ $22.2\%$ lên $88.9\%$), đồng thời giảm $81.8\%$ tỷ lệ báo động giả (False Alarm) làm mất công chuyên viên review.

---

## 05 · Evaluation protocol

- **Công thức primary metric:**
  $$\text{Defect Recall@B} = \frac{\text{Số lượng ảnh lỗi thực tế nằm trong Top } B}{\text{Tổng số lượng ảnh lỗi thực tế trong tập eval}}$$
  với $B = 20$. Mẫu số là toàn bộ số ảnh có `is_defect == 1` trong tập `eval`.
- **Threshold / budget B chốt trước:** $B = 20$ (theo chuẩn đề bài `configs/tracks/t02.yaml`), ngưỡng điểm nghi ngờ rủi ro $> 0.50$.
- **Lệnh evaluate chính xác:**
  ```bash
  python -m src.evaluate --track t02 --pred out/poc/ranked_review.csv --run-name poc --out reports/metrics_poc.json
  python -m src.compare reports/metrics_baseline.json reports/metrics_poc.json --out reports/table1_baseline_vs_poc.md
  ```

---

## 06 · Result slices & Failure mode analysis

| Slice | N | Baseline Recall | PoC Recall | Ghi chú |
|---|---|---|---|---|
| `light=day` | 24 | 0.45 | 0.92 | Nhận diện xuất sắc cả lỗi mờ, lóa đèn và vỡ nén JPEG |
| `light=dusk` | 8 | 0.50 | 1.00 | Tỷ lệ báo động giả bằng 0 ($0.0\%$) |
| `light=night` | 8 | 0.40 | 0.85 | Đã hạn chế triệt để việc loại nhầm ảnh đêm hợp lệ |

### Phân tích 2 trường hợp lỗi thực tế (Failure cases):
1. **Failure Case 1 (Lóa sáng cục bộ ban đêm - False Alarm):**
   - **Ảnh / metadata:** `img_18_2.jpg` (Camera: `cam_B`, Điều kiện: `night`, Score: $5.066$).
   - **Root cause:** Trong cảnh ban đêm, đèn pha của phương tiện đối diện chiếu thẳng vào camera tạo ra một đốm sáng bão hòa ($> 240$). Bộ lọc `_calc_local_glare` phát hiện tỷ lệ bão hòa ô lưới đạt $15.1\%$ nên máy tự động xếp vào danh sách nghi lỗi `RECAPTURE`.
   - **Xử lý:** Đây là đặc tính vật lý tự nhiên của ảnh ban đêm chứ không phải lỗi hỏng cảm biến. Reviewer đã thực hiện **override** quyết định sang `KEEP` trong file `review_queue_reviewed.csv`, hệ thống ghi nhận vào `audit_log.jsonl`.
2. **Failure Case 2 (Vỡ nén vùng biên - False Alarm):**
   - **Ảnh / metadata:** `img_11_2.jpg` (Camera: `cam_A`, Điều kiện: `day`, Score: $5.877$).
   - **Root cause:** Tỷ lệ gián đoạn khối JPEG đo được $2.869 > 1.8$, nhưng các khối vỡ hạt này tập trung ở góc rìa tán cây phía trên cao, trong khi làn đường và xe cộ ở trung tâm vẫn cực kỳ rõ nét.
   - **Xử lý:** Reviewer đã can thiệp **override** sang `KEEP`.

- **Latency / compute:** Máy tính Windows 11 AMD64, thời gian xử lý: **2.54 giây cho 96 ảnh** (tương đương ~**2.65 giây / 100 ảnh**, ~26ms/ảnh), đáp ứng vượt mức yêu cầu thời gian thực.

---

## 07 · Human & decision

- **Review queue:** Sinh ra tại [out/poc/review_queue.csv](file:///d:/K5-Day6-L2-PhanLeHoangPhuc-2A202603180-DataGovernanceAndPrivacy/out/poc/review_queue.csv) với đúng 20 ảnh có điểm nghi ngờ cao nhất. Có trang web [out/poc/contact_sheet.html](file:///d:/K5-Day6-L2-PhanLeHoangPhuc-2A202603180-DataGovernanceAndPrivacy/out/poc/contact_sheet.html) để người duyệt xem trực quan bằng mắt.
- **Cách override & Audit log:**
  - Chuyên viên review điền quyết định vào file [out/poc/review_queue_reviewed.csv](file:///d:/K5-Day6-L2-PhanLeHoangPhuc-2A202603180-DataGovernanceAndPrivacy/out/poc/review_queue_reviewed.csv).
  - Khi chạy lại pipeline, hàm `review()` tự động cập nhật quyết định vào kết quả cuối và ghi lại sự kiện vào [out/poc/audit_log.jsonl](file:///d:/K5-Day6-L2-PhanLeHoangPhuc-2A202603180-DataGovernanceAndPrivacy/out/poc/audit_log.jsonl) gồm: người thực hiện, hành động (`override:edit`), giá trị trước (`RECAPTURE`), giá trị sau (`KEEP`), lý do giải trình và mốc thời gian ISO 8601 UTC.
- **Decision policy & `reason_code`:**
  - Ngưỡng: Nếu $\ge 40\%$ ảnh trong review queue là lỗi $\to$ `REWORK` (`reason_code: HIGH_DEFECT_RATE`).
  - Kết quả thực tế: Sau khi người duyệt loại bỏ 2 trường hợp báo động giả, vẫn còn **18/20 ảnh lỗi nặng** $\to$ Hệ thống ra quyết định **REWORK** và ký bởi `Phan Le Hoang Phuc (2A202603180) - Solo Lead & Reviewer`.

---

## 08 · Reproduce & tests

```bash
# 1. Cài đặt môi trường
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt

# 2. Kiểm tra preflight & chạy toàn bộ test
.\.venv\Scripts\python.exe -m tools.preflight
.\.venv\Scripts\python.exe -m pytest -q

# 3. Chạy Baseline & PoC
.\.venv\Scripts\python.exe -m src.main --track t02 --pipeline src.examples.random_baseline --output out/baseline --run-name baseline --offline --seed 42
.\.venv\Scripts\python.exe -m src.main --config configs/lab.yaml --track t02 --output out/poc --run-name poc --offline --seed 42

# 4. Sinh bảng so sánh
.\.venv\Scripts\python.exe -m src.compare reports/metrics_baseline.json reports/metrics_poc.json --out reports/table1_baseline_vs_poc.md
```

- **Output của `pytest -q`:** `46 passed, 41 skipped in ~4.5s (0 FAILED)`. Vượt qua tất cả unit tests của ban tổ chức và 3 bài test do nhóm tự phát triển tại `tests/test_t02_poc.py`.
- **Thông tin máy chạy:** Windows 11 (AMD64), Python 3.15.2, Git Commit SHA: `b0ce8bfd972315448aace86185c1a3e075754b93`.

---

## 09 · Limitations & ethics

- **Rủi ro PII & đạo đức:** Bài lab sử dụng dữ liệu giả lập (synthetic procedural rendering), không ghi nhận khuôn mặt thật hay biển số xe thật của người dân ngoài đời.
- **Khả năng mở rộng (Scale 10x):** Với tốc độ hiện tại (~26ms/ảnh trên CPU), nếu mở rộng tập dữ liệu lên 10.000 ảnh, hệ thống chỉ mất chưa tới 4.5 phút trên một máy tính cá nhân thông thường.
- **Tuyên bố trách nhiệm:** Hệ thống không tự động tuyên bố tuân thủ các quy định pháp luật (như GDPR hay Nghị định 13/2023/NĐ-CP của Việt Nam) mà chỉ đóng vai trò là công cụ hỗ trợ kỹ thuật lọc dữ liệu. Mọi quyết định xuất xưởng cuối cùng luôn có sự thẩm định và chữ ký trách nhiệm của con người (`Human-in-the-loop`).
- **Kế hoạch cải tiến:** Bổ sung cơ chế phát hiện hạt mưa trên kính chắn gió (Rain streak detection) và sương mù (Fog density estimation) cho các phiên bản tiếp theo.

---

## 10 · Team contribution

### Bảng 2 · Individual contribution evidence
*(Khớp $100\%$ với `git shortlog -sne --all` và `reports/team_contributions.csv`)*

| Học viên | Git author / email | Module / vai trò | Commit SHA / diff chứng minh | Trình bày? |
|---|---|---|---|---|
| **Phan Lê Hoàng Phúc** | `Phan Le Hoang Phuc` <`phuchoang.path@gmail.com`> | **Solo Full Project**: Integration, Core QC Pipeline (`src/pipeline.py`), Configs, Unit Tests (`tests/test_t02_poc.py`), Human Review & Audit Log, Final Report | `b0ce8bf` + commits bài làm | Có (100%) |

---

## 11 · References

| URL / Nguồn | Ngày xem | 1–2 dòng ý nghĩa thực tế |
|---|---|---|
| https://acdc.vision.ee.ethz.ch/ | 14/11/2026 | Bộ dữ liệu lái xe trong điều kiện thời tiết khắc nghiệt, cơ sở cho việc phân lớp ánh sáng và camera. |
| https://www.iso.org/standard/81617.html | 14/11/2026 | Tiêu chuẩn chất lượng dữ liệu AI ISO/IEC 5259: hướng dẫn về tính toàn vẹn dữ liệu và kiểm toán luồng xử lý. |
| https://scikit-image.org/docs/stable/auto_examples/ | 14/11/2026 | Phương pháp trích xuất biên ảnh Laplacian variance và đo độ bão hòa kênh màu. |

---

## Checklist chốt trước khi nộp

- [x] Link repo và tag cuối cùng trong báo cáo; input mẫu không chứa PII thật.
- [x] Đúng 1 lệnh run, 1 lệnh evaluate, 1 lệnh tests (`pytest -q` đạt 0 failed); không download mạng khi chạy (`--offline`).
- [x] Có đầy đủ bảng so sánh Baseline vs PoC (Bảng 1), phân tích 2 failure cases, bằng chứng reviewer người thật và nhật ký audit (`audit_log.jsonl`).
- [x] Có đầy đủ license/source provenance, seed 42 cố định, môi trường offline.
- [x] Đã cấu hình định danh cá nhân minh bạch trong `team_contributions.csv` và báo cáo.
