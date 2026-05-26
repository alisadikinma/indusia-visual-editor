# ML Training Workflow + Dual-Mode UX — Spec

> Authoritative spec untuk semua screen ML (Persiapan pelatihan, Training, Setup Eval, Eval, Konfirmasi pasang model). Hasil diskusi 2026-05-26 setelah review Figma v1 ditolak karena jargon-heavy + workflow gak konsisten.
>
> **Status**: DRAFT — menunggu approval user sebelum Figma rebuild.

## 0. Naming — UI vs Internal (LOCKED 2026-05-26)

"Gate 1" dan "Gate 2" adalah istilah internal ML (Human-in-the-Loop checkpoint), tidak meaningful untuk operator pabrik. **UI labels diganti, internal naming tetap.**

| Internal (code, API, CLAUDE.md, this spec headings) | UI label EN | UI label ID |
|---|---|---|
| Gate 1 / pre-train review | **"Training preparation"** | **"Persiapan pelatihan"** |
| Gate 2 / pre-deploy review | **"Confirm model deployment"** | **"Konfirmasi pasang model"** |
| Promote to production | "Deploy model to production" | "Pasang model ke produksi" |
| Rollback to previous version | "Revert to previous model" | "Pakai model sebelumnya lagi" |
| HITL checkpoint | "Human approval" | "Persetujuan manusia" |

**Mengapa dual layer**: code paths (`/api/projects/{id}/gate1/approve`), DB columns (`gate1_approved_at`), engineer docs (CLAUDE.md), dan engineer-mode dialog tetap pakai "Gate 1/2" untuk konsistensi dengan kode. UI-facing strings (apa yang user lihat) pakai naming meaningful per locale.

### Affected UI strings — daftar rename (bilingual)

Saat Figma rebuild, ganti string-string berikut. Kolom EN untuk EN screens (e.g. 47:2), kolom ID untuk ID variant screens (e.g. 37:2):

| Screen / context | EN (lama → baru) | ID (lama → baru) |
|---|---|---|
| Gate 1 breadcrumb | `... / Gate 1` → `... / Training preparation` | `... / Gate 1` → `... / Persiapan pelatihan` |
| Gate 1 title | `Gate 1 — Pre-train review` → `Training preparation` | `Gate 1 — Pre-train review` → `Persiapan pelatihan` |
| Gate 1 banner | `Human-in-the-loop Gate 1` → `Human approval before training starts` | (kalau ada) → `Persetujuan manusia sebelum pelatihan dimulai` |
| Gate 1 CTA | `Approve & Start Training` → `Approve & start training` | → `Setujui & mulai pelatihan` |
| Gate 2 breadcrumb | `... / Gate 2` → `... / Confirm deployment` | `... / Gate 2` → `... / Konfirmasi pasang model` |
| Gate 2 title | `Promote to production` → `Confirm model deployment` | `Promote ke produksi` → `Konfirmasi pasang model` |
| Gate 2 CTA | `Promote to production →` → `Deploy model →` | `Promote ke produksi →` → `Pasang model ke produksi →` |
| Gate 2 cancel | `← Back` → `← Cancel` | `← Kembali` → `← Batal` |
| Eval bottom action | `Continue to Gate 2 →` → `Continue to deployment →` | `Lanjut ke Gate 2 →` → `Lanjut ke konfirmasi pasang model →` |
| Eval threshold blocker | `not ready to promote to production` → `not ready to deploy yet` | `belum siap di-promote ke produksi` → `belum siap dipasang ke produksi` |
| Sidebar process labels | `Gate 1 / Gate 2` → `Training preparation / Confirm deployment` | → `Persiapan pelatihan / Konfirmasi pasang model` |

Heading di spec ini tetap pakai "Gate 1 / Gate 2" sebagai internal anchor — supaya engineer mode + code reference cocok.

## 0b. i18n bilingual strategy (LOCKED 2026-05-26)

**Setiap screen ML baru WAJIB punya 2 variant: EN + ID.** Pattern konsisten dengan Bundle A (Login/Dashboard) dan Bundle B (Wizard/Labeling/Gate 1) yang sudah pakai screen variants terpisah.

### Approach: Screen variants terpisah (LOCKED)

| Screen (semantic) | EN variant id | ID variant id |
|---|---|---|
| Dashboard populated | 8:2 | 37:177 |
| Login | 6:2 | 37:2 |
| Gate 1 (= Persiapan pelatihan) | 47:2 (existing) | **(buat baru)** |
| Training (= Pelatihan model) | 89:2 (existing) | **(buat baru)** |
| Setup Eval | (buat baru) | (buat baru) |
| Eval (= Hasil evaluasi) | 92:2 (existing) | **(buat baru)** |
| Gate 2 (= Konfirmasi pasang model) | 95:2 (existing) | **(buat baru)** |
| Models | 99:2 (existing) | **(buat baru)** |
| Edges | 99:441 (existing) | **(buat baru)** |
| Datasets | 99:852 (existing) | **(buat baru)** |
| Team | 105:2 (existing) | **(buat baru)** |
| Preferences | 105:324 (existing) | **(buat baru)** |
| Bundle D overlays showcase | 107:2 (existing) | **(buat baru)** |

EN/ID toggle di topbar `right` frame (sudah ada di semua screen) wire ke variant terkait. **Locale + Engineer mode persists ke `user_preferences` table di DB** (LOCKED 2026-05-26) — bukan localStorage. Setiap user bawa preference cross-browser/device.

### Translation policy

- **Technical identifiers tidak diterjemahkan**: designator (`R1`, `C4`, `U7`), component types (`electrolytic_cap`, `dip_ic`, `connector`, `tht_resistor`), defect criteria (`polarity_flip`, `lifted_pin`, `missing_component`), detector names (`YOLOv8n`, `Anomalib PaDiM`, `OCR`).
- **Plain-language metric labels diterjemahkan**:
  - EN: "Predicted defect, actually OK" / "Defect missed by model" / "Model is learning" / "Confidence"
  - ID: "Alarm palsu" / "Defect terlewat" / "Model sedang belajar" / "Keyakinan model"
- **Operator-mode plain language**: full translation, no English fallback
- **Engineer-mode jargon**: keep English (`Loss`, `mAP@0.5`, `F1 macro`, `Epoch`) di kedua locale, karena ML engineer global memang pakai EN terms

### Plain-language mapping bilingual

(Section §2 di-update untuk include kolom EN — lihat §2 di bawah.)

---

## 1. Persona target (LOCKED dari CLAUDE.md)

| Persona | Role | Tahu apa | Butuh apa |
|---|---|---|---|
| **Operator MI** (default) | Manual Insertion line supervisor | Tahu PCB, tahu defect umum, **tidak tahu ML jargon** | Status singkat, plain language, action button yang jelas, error message yang actionable |
| **Engineer** (advanced toggle) | Internal ML/data team Indusia | Tahu YOLO, Anomalib, metric ML, hyperparam | Loss curve, F1/Precision/Recall, hyperparam tuning, log debug, service job ID |

**Default mode = Operator.** Engineer mode di-enable via toggle "Detail teknis" (kecil, di pojok kanan atas main panel). Toggle ini ngga ganti screen, cuma reveal/hide section + ganti label.

**Persistence (LOCKED 2026-05-26)**: toggle state disimpan di **`user_preferences` table di DB** (per-user, cross-device). Default false. Diakses via `GET/PUT /api/users/me/preferences`.

## 2. Plain-language mapping (bilingual)

Jargon ML → operator-friendly. Engineer-mode tetap pakai jargon EN di kedua locale (ML engineer pakai istilah EN global).

| Jargon (Engineer mode, both locales) | Operator EN | Operator ID |
|---|---|---|
| Training | "Model is learning" | "Model sedang belajar" |
| Loss (box_loss + cls_loss) | "Learning indicator" (down = smarter) | "Indikator belajar" (turun = makin pintar) |
| mAP@0.5 = 0.812 | "Current accuracy: 81%" | "Akurasi sementara: 81%" |
| Precision 0.871 | "On-target rate: 87%" | "Tepat sasaran: 87%" |
| Recall 0.819 | "Detection rate: 82%" | "Berhasil deteksi: 82%" |
| F1 score | "Balanced score" | "Skor seimbang" |
| Epoch 32/100 | "Step 32 of 100" | "Langkah 32 dari 100" |
| Validation set | "Practice exam set" | "Set ujian" |
| Hold-out / test set | "Final exam set" | "Set sampel ujian" |
| Support (sample count) | "Sample count" | "Jumlah contoh" |
| Δ vs last run | "Better / Worse than last" | "Lebih baik / Lebih buruk dari terakhir" |
| TP (True Positive) | "Defect correctly caught" | "Defect terdeteksi benar" |
| TN (True Negative) | "Pass correctly identified" | "Pass terdeteksi benar" |
| FP (False Positive) | "False alarm" | "Alarm palsu" |
| FN (False Negative) | "Defect missed" | "Defect terlewat" |
| Confidence score 0.78 | "Model confidence: 78%" | "Keyakinan model: 78%" |
| Hyperparameter | "Training settings" | "Pengaturan pelatihan" |
| Learning rate | "Learning speed" | "Kecepatan belajar" |
| Batch size | "Samples per step" | "Ukuran sekali belajar" |
| Augmentation | "Data variation" | "Variasi data" |
| Fine-tune dari checkpoint | "Continue from previous model" | "Lanjut dari model sebelumnya" |
| Early stopping | "Stop early when good enough" | "Berhenti otomatis kalau sudah cukup pintar" |
| Class imbalance | "Some components have fewer examples" | "Beberapa komponen contohnya lebih sedikit" |
| Threshold | "Minimum passing bar" | "Batas minimal kelulusan" |
| Promote ke produksi | "Deploy to production line" | "Pasang ke mesin produksi" |
| Rollback | "Use previous model again" | "Pakai model sebelumnya lagi" |
| SSE stream / live log | (hidden in operator mode) | (sembunyikan di operator mode) |
| Service job ID | (hidden in operator mode) | (sembunyikan di operator mode) |
| GPU 0 (RTX A6000) | (hidden in operator mode) | (sembunyikan di operator mode) |

## 3. ML training cycle — 7 stages

```
[1] Labeling          → User anotasi golden + defect samples
       ↓
[2] Gate 1            → Pre-train review (HITL hard stop)
   (dataset ready?)     - Dataset readiness check
                        - Hyperparams (heuristic-grounded, NOT raw Gemma)
                        - Training mode: From scratch | Fine-tune dari run #X
                        - Class imbalance warning + auto-balance toggle
                        - Early stopping config
       ↓ Approve & Start
[3] Training          → Model belajar
                        - Operator view: progress bar + "belajar makin pintar" trend
                        - Engineer view: loss curve + box_loss/cls_loss split
                        - Cancel kapan saja
       ↓ Training selesai
[4] Setup Eval        → User MANUAL trigger eval (per Q&A 2026-05-26)
   (Optional screen)    - Pilih test set: hold-out default | upload custom | bookmark previous
                        - "Mulai evaluasi"
       ↓
[5] Eval              → Hasil evaluasi pada test set
                        - Operator view: lulus/perlu-perhatian/lemah per komponen
                        - Engineer view: F1/Precision/Recall + per-tile TP/FP/FN/TN
                        - Hard threshold gate untuk Gate 2 button
       ↓ Decide branch
       ├─ [6a] Koreksi loop → buka Labeling dengan filter pada FP/FN sample
       │      ↓ Save corrections
       │      → Gate 1 (mode: fine-tune dari run #X)
       │      → Training
       │      → Eval ulang
       │
       └─ [6b] Gate 2 → Promote ke produksi (ONLY kalau threshold lulus)
              - Side-by-side prod vs candidate
              - Hard threshold pre-check (mAP ≥ 0.80, F1 macro ≥ 0.80, all per-komponen F1 ≥ 0.70)
              - Edge target picker
              - Double-confirm (typed project name)
              ↓
[7] Production        → Edge pull model baru, runtime inference
```

## 4. Gate 1 — Pre-train review (FULL REBUILD)

### Apa yang harus muncul

**Operator view:**
- Dataset readiness card — "Kamu sudah siapkan {N} anotasi untuk {M} komponen"
- Coverage warning yang ramah — "Komponen {X, Y, Z} contohnya kurang. Tambah anotasi atau skip dari inspect-list."
- Mode pelatihan toggle: **"Mulai dari nol"** vs **"Lanjut dari model terakhir (run #X)"** ← per Q&A retrain loop. **Opsi "Lanjut dari model terakhir" DISABLED (grayed out) kalau project belum punya completed run sebelumnya** (LOCKED 2026-05-26) — bukan tooltip. Tooltip muncul saat hover atas opsi disabled: "Belum ada model yang bisa dilanjutkan. Mulai dari nol untuk pelatihan pertama."
- Estimated waktu: "Sekitar 12 menit"
- 2 button: "← Kembali ke Labeling" + "Mulai pelatihan →"

**Engineer toggle reveals:**
- Hyperparameter table: Epochs / Batch size / Learning rate / Cosine decay / Anchor preset
- Hyperparam **grounding source**: "Heuristic dari past runs project ini" / "Default YOLOv8n" / "User override"
- **Early stopping config**: patience epochs, min delta — DEFAULT enabled
- **Class imbalance handling**: auto-weighted loss toggle (untuk komponen dengan support < 5)
- **Random seed**: input field (default: 42)
- **Validation strategy**: dropdown — single split 80/20 (default) | k-fold k=5 (untuk dataset < 50 anotasi)
- **Pretrained checkpoint source**:
  - Train from scratch: COCO weights default (YOLOv8n)
  - Fine-tune: select previous run from dropdown
- **Hardware target**: dari `IVE_INSPECT_SERVICE_URL` config — bukan hardcoded label

### Apa yang HARUS dihapus dari v1

- Fake "F1 projection 93%, 88%, 42%" angka pseudo-presisi → ganti bucket label: **Cukup / Sedang / Kurang / Berisiko** (4 level berdasar example count)
- "Suggested by Gemma" tanpa basis → ganti **"Heuristic + saran Gemma"** dengan disclosure source
- "RTX-4090" hardcoded → ambil dari config

## 5. Training screen — DUAL MODE

### Operator view (default)

```
┌─────────────────────────────────────────────────────────────────┐
│ Pelatihan model — Konektor X-200                                 │
│ ┌─────────────────────────────────────────────────────────────┐ │
│ │ Model sedang belajar...                                      │ │
│ │ [████████████░░░░░░░░░░░░░░] 32%                            │ │
│ │ Langkah 32 dari 100 · Sisa waktu sekitar 8 menit             │ │
│ │ Indikator belajar: ↑ Makin pintar (akurasi sementara 81%)    │ │
│ └─────────────────────────────────────────────────────────────┘ │
│                                                                  │
│ Komponen yang model sudah pintar (5)                             │
│ ✓ Kapasitor elektrolit (C1, C4) — Bagus                          │
│ ✓ Connector J2 — Bagus                                           │
│ ✓ Resistor R12 — Bagus                                           │
│                                                                  │
│ Komponen yang model masih sulit (2)                              │
│ ⚠ DIP IC U1, U7 — Cukup, perlu observasi                         │
│ ⚠ Connector J5 — Lemah, mungkin perlu data tambahan              │
│                                                                  │
│ [Detail teknis ▾]  [Batalkan]                                    │
└─────────────────────────────────────────────────────────────────┘
```

### Engineer view (toggle ON)

Tambahan reveal:
- Loss curve grafik (box_loss + cls_loss split, smoothed)
- mAP@0.5 grafik per-epoch
- F1 / Precision / Recall numerical table (yang sekarang)
- SSE stream log strip
- Service job ID, GPU hardware
- "Δ vs run lalu" numerical
- "Support" column

### State machine

```
Idle → Berjalan → Eval otomatis (singkat, on val set) → Selesai → 
  ↓                                                         ↓
  Batal                                              "Setup evaluasi →"
                                                     (manual trigger ke screen Setup Eval)
```

## 6. Setup Eval (new screen)

Screen pemilihan test set sebelum Eval jalan (manual trigger per Q&A).

**Operator view:**
- "Pilih sampel untuk ujian model"
- 3 opsi card:
  - **Hold-out set default (78 sampel)** — sudah disiapkan saat anotasi
  - **Upload sampel baru** — drag & drop foto PCB baru untuk diuji
  - **Pakai test set sebelumnya** — bookmark dari eval run sebelumnya
- "Mulai evaluasi →"

**Engineer toggle reveals:**
- Test set split detail (number per class, augmentation off, etc.)
- "Reuse weights from run #X" pilihan
- Inference batch size

## 7. Eval — DUAL MODE + LOGIC

### Operator view

```
┌─────────────────────────────────────────────────────────────────┐
│ Hasil evaluasi — Run #47 · diuji 78 sampel                       │
│                                                                  │
│ ⚠ MODEL BELUM LULUS UNTUK PRODUKSI                                │
│   Connector J5 masih lemah (di bawah batas minimal kelulusan).   │
│   Perlu koreksi atau pelatihan ulang sebelum bisa di-promote.    │
│                                                                  │
│ Ringkasan:                                                       │
│  ✓ 64 sampel: defect benar terdeteksi                            │
│  ✓ 0 sampel: pass benar terdeteksi                               │
│  ⚠ 5 sampel: ALARM PALSU (model bilang defect, sebenarnya OK)    │
│  ✗ 9 sampel: DEFECT TERLEWAT (model bilang OK, sebenarnya defect)│
│                                                                  │
│ [Detail teknis ▾]                                                │
│                                                                  │
│ Sampel yang model salah (14):                                    │
│ [Card 1] TEST-003 · ALARM PALSU · C4 polaritas                   │
│          "Model bilang defect tapi inspector setuju ini OK"      │
│          [Koreksi anotasi →]                                     │
│ [Card 2] TEST-012 · DEFECT TERLEWAT · J5 pin bengkok              │
│          "Model tidak deteksi padahal pin J5 jelas bengkok"      │
│          [Koreksi anotasi →]                                     │
│ ...                                                              │
│                                                                  │
│ Langkah berikut:                                                 │
│ [Koreksi 14 anotasi →] [Mulai pelatihan ulang]  🔒 Pasang model  │
│   (PRIMARY, amber)      (secondary)              (DISABLED)      │
└─────────────────────────────────────────────────────────────────┘
```

### Engineer toggle reveals (yang sekarang sudah ada di v2 Figma)

- TP/FP/FN/TN per-tile verdict
- mAP / Precision / Recall / F1 numerical cards dengan threshold indicator
- Detector chip per tile (YOLOv8n / Anomalib / OCR)
- Confusion matrix 2x2
- "Hipotesis penyebab" panel
- Per-komponen F1 drill-down

### Hard threshold (LOCKED per Q&A)

Gate 2 button DISABLED kalau salah satu:
- mAP@0.5 < 0.80
- F1 macro < 0.80
- Ada per-komponen F1 < 0.70

**Threshold disimpan di `project_thresholds` table di DB** (LOCKED 2026-05-26) — bukan env var. Per-project override didukung dari v1. Diakses via `GET/PUT /api/projects/{id}/thresholds`.

Default seed values saat project create:
```
mAP@0.5 ≥ 0.80
F1 macro ≥ 0.80
per-component F1 ≥ 0.70
```

Admin role bisa override per-project di Engineer mode (Persiapan pelatihan screen → tab "Pengaturan threshold"). Operator role: read-only.

## 8. Gate 2 — minor updates

Sudah cukup baik di v1. Tambahan:
- Pre-check sama dengan Eval threshold — kalau user lompat ke Gate 2 lewat URL/breadcrumb, tampilkan blocker "Run ini belum lulus threshold, kembali ke Eval".
- Tambah dual-mode toggle (operator: "pasang model" language; engineer: technical promote terminology).

## 9. Retrain workflow — full loop

User klik "Koreksi anotasi" pada tile FP/FN di Eval:
1. **Bukak Labeling screen** dengan query param `?correction_mode=1&sample_ids=TEST-003,TEST-005,...`
2. **Labeling screen tampilkan banner**: "Mode koreksi: 14 sampel dari Eval run #47. Perbaiki anotasi yang salah lalu Simpan."
3. **User scroll/swipe** sampel-sampel itu satu per satu, koreksi bbox / label
4. **Tombol "Simpan & lanjut ke pelatihan ulang"** → buka Gate 1 dengan mode pre-filled:
   - Mode pelatihan: "Lanjut dari model terakhir (run #47)"
   - Dataset stats sudah update dengan koreksi
   - Estimasi waktu lebih singkat (fine-tune = ~30-40 epoch tambahan, bukan 100)
5. User klik "Mulai pelatihan ulang →" → Training (run #48 dimulai)
6. Training selesai → Setup Eval → Eval ulang
7. Kalau lulus threshold → Gate 2 enabled

## 10. Screen list — final after rebuild

| Screen | id (existing) | Status |
|---|---|---|
| Gate 1 | 47:2 | **Rebuild full** dengan dual-mode + fine-tune toggle |
| Training | 89:2 | **Rebuild full** dengan dual-mode |
| Setup Eval | (new) | **Buat baru** |
| Eval | 92:2 | **Restructure** dengan dual-mode + threshold + retrain action |
| Gate 2 | 95:2 | **Minor update** — threshold pre-check + dual-mode toggle |
| Labeling | 46:2 | **Minor update** — koreksi mode banner |

## 11. Estimasi waktu Figma rebuild (bilingual)

Setiap screen = 2 variant (EN + ID), wired ke EN/ID toggle di topbar.

- Gate 1 rebuild dual-mode EN + ID variants: ~45 menit
- Training rebuild dual-mode EN + ID variants: ~40 menit
- Setup Eval new screen EN + ID: ~25 menit
- Eval restructure dual-mode EN + ID: ~40 menit
- Gate 2 minor + threshold pre-check + ID rename: ~20 menit
- Labeling koreksi mode banner EN + ID: ~15 menit
- Wire ulang flow lengkap (EN paths + ID paths + EN/ID toggle handoff): ~30 menit
- Engineer mode toggle component (reused di semua screen): ~15 menit
- **Total: ~3 jam 50 menit** (bisa dipecah ke 2-3 session)

### Strategi efisiensi
- Build EN variant lengkap dulu, verify visual + threshold logic OK, baru clone → text replace ke ID variant
- Engineer mode toggle dibikin sekali sebagai re-usable component frame, di-copy ke setiap screen
- Plain-language strings + jargon strings disimpan sebagai dict di plugin script supaya tinggal swap saat build ID variant

## 12. Yang TIDAK diubah strukturnya, tapi WAJIB tambah ID variant

Bundle ini sudah operator-friendly secara konten, tapi belum semua punya ID variant. Untuk requirement bilingual:

- **Bundle A** (Login, Signup, Dashboard) — sudah ada ID variants ✓
- **Bundle B** (Wizard, Labeling, Gate 1) — sudah ada ID variants ✓ kecuali Gate 1 yang ID-nya belum dibuat (mostly EN). Gate 1 ID variant akan dibuat sebagai bagian dari §11.
- **Bundle E** (Models, Edges, Datasets) — **belum ada ID variants**. WAJIB tambah ID variant masing-masing. ~30 menit total batch clone.
- **Bundle F** (Team, Preferences) — **belum ada ID variants**. WAJIB tambah ID variant + tambah "Engineer mode" toggle setting di Preferences. ~25 menit.
- **Bundle D** (overlays showcase) — **belum ada ID variant**. Tambah ID variant + translate chat bubble copy, toast strings, modal text. ~15 menit.

**Total tambahan ID variants untuk Bundle existing: ~70 menit** (di luar §11).

### Grand total Figma rebuild bilingual
- §11 ML screens (new + redesigned, EN+ID): ~3 jam 50 menit
- §12 existing screens ID variants tambahan: ~70 menit
- **Grand total: ~5 jam** (dipecah ke 3-4 session)

## 13. Open decisions — RESOLVED 2026-05-26

- [x] **Engineer mode toggle persistence**: **`user_preferences` DB table** (cross-device per-user).
- [x] **Threshold values**: **`project_thresholds` DB table** (per-project override dari v1).
- [x] **"Lanjut dari model terakhir" kalau belum ada prior run**: **DISABLED** (grayed out) + tooltip "Belum ada model yang bisa dilanjutkan. Mulai dari nol untuk pelatihan pertama."

## 14. Backend implications dari 3 decisions

### 14.1 Migration baru — `0012_user_preferences_and_thresholds`

```sql
-- New: user_preferences (per-user)
CREATE TABLE user_preferences (
  user_id UUID PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
  locale TEXT CHECK (locale IN ('en','id')) DEFAULT 'id',
  advanced_mode BOOL DEFAULT FALSE,
  theme TEXT CHECK (theme IN ('auto','light','dark')) DEFAULT 'auto',
  updated_at TIMESTAMPTZ DEFAULT now()
);

-- Seed: 1 row per existing user (default operator mode, id locale)
INSERT INTO user_preferences (user_id)
SELECT id FROM users
ON CONFLICT (user_id) DO NOTHING;

-- New: project_thresholds (per-project, gateable)
CREATE TABLE project_thresholds (
  project_id UUID PRIMARY KEY REFERENCES projects(id) ON DELETE CASCADE,
  map_min NUMERIC(4,3) DEFAULT 0.800,
  f1_macro_min NUMERIC(4,3) DEFAULT 0.800,
  f1_per_component_min NUMERIC(4,3) DEFAULT 0.700,
  updated_by UUID REFERENCES users(id),
  updated_at TIMESTAMPTZ DEFAULT now(),
  CHECK (map_min BETWEEN 0 AND 1),
  CHECK (f1_macro_min BETWEEN 0 AND 1),
  CHECK (f1_per_component_min BETWEEN 0 AND 1)
);

-- Seed: 1 row per existing project with defaults
INSERT INTO project_thresholds (project_id)
SELECT id FROM projects
ON CONFLICT (project_id) DO NOTHING;
```

### 14.2 New endpoints

| Method | Path | Role | Returns |
|---|---|---|---|
| GET | `/api/users/me/preferences` | any authenticated | `UserPreferences {locale, advanced_mode, theme}` |
| PUT | `/api/users/me/preferences` | any authenticated | updated `UserPreferences` |
| GET | `/api/projects/{id}/thresholds` | any authenticated | `ProjectThresholds {map_min, f1_macro_min, f1_per_component_min}` |
| PUT | `/api/projects/{id}/thresholds` | admin only | updated `ProjectThresholds` |
| GET | `/api/projects/{id}/promote-readiness` | any authenticated | `{ready: bool, blockers: [{metric, current, threshold, message}]}` — pre-check untuk Gate 2 button enable/disable |

### 14.3 Frontend impact

- `useAuthStore` di-extend dengan `preferences: UserPreferences` field, loaded saat login + saat `/api/users/me`.
- `useProjectsStore` per-project: load thresholds saat enter project.
- Engineer mode toggle component reads/writes via `useAuthStore.updatePreferences({advanced_mode: true})` → debounced PUT call.
- EN/ID toggle reads/writes via `useAuthStore.updatePreferences({locale: 'en'})` → causes route reload + i18n re-bind.
- Gate 2 button (di Eval + di Gate 2 screen) reads `useProjectsStore.promoteReadiness.ready` reactively — disabled kalau false.

### 14.4 Default seeding behavior

- User baru signup → `user_preferences` row otomatis insert dengan defaults (locale=id, advanced=false, theme=auto).
- Project baru create → `project_thresholds` row otomatis insert dengan defaults (0.80/0.80/0.70).
- Migration 0012 backfill semua existing users + projects.

### 14.5 Phase planning

Backend changes ini bukan blocker untuk Figma rebuild (Figma cuma visual + variant). Tapi WAJIB dikerjakan sebelum Vue dev mulai:

- Phase 14.A: migration 0012 + ORM models + crud services (~30 min backend code + tests)
- Phase 14.B: 5 endpoints + envelope + role gates (~45 min + tests)
- Phase 14.C: Vue store integration + Engineer mode toggle component wiring (~60 min)

Total backend prep: ~2 jam 15 menit. Cocok untuk M15 (post-prototype, pre-Vue dev).

---

**Approval status**: ✓ Spec + 3 decisions LOCKED 2026-05-26

**Eksekusi sequence**:
1. Figma rebuild §11 + §12 — total ~5 jam dipecah 3-4 session
2. (saat Figma done + user playtest approve) Backend M15 §14 — total ~2 jam 15 menit
3. Vue dev (i18n + Pinia + tokens + screens) — separate workstream

**Start dari Engineer mode toggle component** karena foundation reusable untuk semua ML screens berikutnya.
