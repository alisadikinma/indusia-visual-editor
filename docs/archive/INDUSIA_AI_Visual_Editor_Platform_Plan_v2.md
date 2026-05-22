# INDUSIA AI — AI Visual Editor Platform
## Rencana Realisasi Komprehensif

> Label Studio Fork · Auto-Labelling · Training Pipeline · Self-Improving AI
>
> _Sistem terpisah dari INDUSIA HMI — berjalan di Engineer / Lab PC_

| Aspek | Detail |
|-------|--------|
| Dokumen | INDUSIA AI Visual Editor Platform — Rencana Realisasi |
| Versi | 2.0 (Revisi: arsitektur Label Studio fork, sistem terpisah dari HMI) |
| Tanggal | 14 Maret 2026 |
| Dibuat oleh | Tim INDUSIA AI |
| Status | Draft — Review Internal |
| Klasifikasi | CONFIDENTIAL |

---

## Daftar Isi

1. [Ringkasan Eksekutif](#1-ringkasan-eksekutif)
2. [Arsitektur Sistem](#2-arsitektur-sistem)
3. [Label Studio Fork Strategy](#3-label-studio-fork-strategy)
4. [Alur Kerja Lengkap](#4-alur-kerja-lengkap)
5. [Technology Stack](#5-technology-stack)
6. [Rencana Implementasi](#6-rencana-implementasi)
7. [Database Schema](#7-database-schema)
8. [Hardware & Infrastruktur](#8-hardware--infrastruktur)
9. [Security & Compliance](#9-security--compliance)
10. [Estimasi Biaya & Timeline](#10-estimasi-biaya--timeline)
11. [Risiko & Mitigasi](#11-risiko--mitigasi)
12. [Success Metrics](#12-success-metrics)

---

## 1. Ringkasan Eksekutif

> **🎯 VISI PLATFORM**
>
> INDUSIA AI Visual Editor Platform adalah sistem **"Zero-Touch Board Onboarding"** yang berjalan **TERPISAH** dari INDUSIA HMI. Engineer customer mendaftarkan board PCB baru — upload BOM List, PCB Drawing, dan Golden Sample — hingga model AI siap produksi. Model yang dihasilkan di-export dan di-import ke INDUSIA HMI di factory floor, **tanpa memerlukan bantuan IT atau data scientist**.

### 1.1 Konsep Dua Sistem

| | AI Visual Editor Platform | INDUSIA HMI (Production) |
|--|--------------------------|--------------------------|
| **Lokasi** | Engineer / Lab PC (office) | Factory floor PC |
| **Pengguna** | Engineer customer, Data labeller | Operator, Manager, Engineer |
| **Fungsi** | Labelling, training, model management | Inspeksi real-time, operator decision |
| **Database** | Label Studio DB (terpisah) | PostgreSQL + PostgREST lokal |
| **Koneksi** | Tidak perlu terhubung ke factory | Tidak perlu terhubung ke lab |
| **Titik integrasi** | Export model package (.zip) | Import model package → deploy |

### 1.2 Masalah yang Diselesaikan

| Masalah Saat Ini | Solusi Platform |
|------------------|-----------------|
| Onboarding board baru butuh 2–4 minggu dengan bantuan engineer AI | Otomatis dalam 1–2 hari via upload + AI auto-labelling |
| Labelling manual per komponen memakan waktu 40–80 jam | GroundingDINO + SAM auto-generate bbox dari foto golden sample |
| Training hanya bisa dilakukan via CLI (terminal) | UI visual satu klik di Label Studio yang sudah di-fork & customize |
| False call → retrain butuh intervensi developer | Self-improving loop: false call images → review di Visual Editor → retrain otomatis |
| Deploy model baru butuh restart manual + copy file | Export package → import di HMI → 1-click deploy |
| Tidak ada visibilitas progress training untuk customer | Real-time training progress via SSE streaming di Training Manager tab |

### 1.3 Manfaat Bisnis

| Metrik | Tanpa Platform | Dengan Platform | Improvement |
|--------|---------------|-----------------|-------------|
| Waktu onboarding board baru | 2–4 minggu | 1–2 hari | **90% lebih cepat** |
| Jam labelling per board | 40–80 jam | 2–4 jam (dengan AI pre-label) | **95% lebih cepat** |
| Ketergantungan IT/Developer | Tinggi | Nol (self-service) | **Full independen** |
| Siklus improvement model | Mingguan/bulanan | Harian (otomatis) | **Real-time learning** |
| False call rate | 5–10% | <2% setelah 1 bulan | **80% lebih rendah** |
| Jumlah board yang bisa di-support | Terbatas | Unlimited (scalable) | **No bottleneck** |

---

## 2. Arsitektur Sistem

### 2.1 Dua Sistem yang Terpisah

> **⚠️ PENTING: Dua Sistem Independen**
>
> AI Visual Editor Platform dan INDUSIA HMI adalah dua sistem yang **SEPENUHNYA TERPISAH**. Tidak ada koneksi jaringan real-time antara keduanya. Satu-satunya titik integrasi adalah file export/import model package (`.zip`). Engineer bekerja di lab/office PC dengan Visual Editor Platform. Model yang sudah jadi di-transfer ke factory floor PC yang menjalankan INDUSIA HMI.

```
┌──────────────────────────────────────┐     ┌──────────────────────────────┐
│   VISUAL EDITOR PLATFORM             │     │   INDUSIA HMI                │
│   (Engineer / Lab PC)                │     │   (Factory Floor PC)         │
│                                      │     │                              │
│  Label Studio fork+custom  :8080     │     │  Next.js HMI        :3000    │
│  Auto-Label Service        :8003     │     │  PostgREST          :3001    │
│  BOM Parser Service        :8004     │     │  AI Service         :8001    │
│  Training Runner           :8005     │     │  AI Edge            :8002    │
│                                      │     │                              │
│           ↓ Export                   │     │        ↑ Import              │
│    model_package_{board}.zip  ───────┼─────┼──→  /engineering/            │
│                                      │     │       model-registry         │
└──────────────────────────────────────┘     └──────────────────────────────┘
       Tidak ada koneksi real-time                Restart AI Edge → aktif
```

### 2.2 Service Map

| Service | Port | Platform | Keterangan |
|---------|------|----------|------------|
| Label Studio (fork + custom) | 8080 | Visual Editor Platform | Base labelling tool, di-fork dari GitHub HumanSignal/label-studio (Apache 2.0) |
| Auto-Label Service (baru) | 8003 | Visual Editor Platform | Python FastAPI: GroundingDINO + SAM 2.1 untuk auto-bbox generation |
| BOM Parser Service (baru) | 8004 | Visual Editor Platform | Gemini Flash API wrapper untuk parse Excel BOM + PCB Drawing |
| Training Runner (baru) | 8005 | Visual Editor Platform | Python FastAPI: wrapper ais CLI tools, expose training API + SSE progress |
| ─────────────── | ───── | ──────────────── | ─────────────────────────────────────────── |
| Next.js HMI | 3000 | INDUSIA HMI | Web UI, API routes, SSE consumer |
| PostgREST | 3001 | INDUSIA HMI | RESTful API over PostgreSQL lokal |
| AI Edge | 8002 | INDUSIA HMI | Camera + PLC bridge, SSE server |
| AI Service | 8001 | INDUSIA HMI | AI inference engine (DAG pipeline) |

### 2.3 Flow Export → Import Model

| Step | Lokasi | Aksi | Output |
|------|--------|------|--------|
| 1 | Visual Editor Platform | Labelling selesai, engineer approve semua bbox | Label session finalized di Label Studio DB |
| 2 | Visual Editor Platform | Klik "Start Training" di Training Manager tab | `ais train batch` berjalan di background |
| 3 | Visual Editor Platform | Training selesai, eval metrics tampil | F1, precision, recall per komponen tersimpan |
| 4 | Visual Editor Platform | Engineer review metrics, klik "Export Model" | `model_package_{board}_{version}.zip` dibuat |
| 5 | Transfer | Engineer copy `.zip` via USB / shared folder / cloud | File tersedia di factory floor PC |
| 6 | INDUSIA HMI | Engineer upload `.zip` via `/engineering/model-registry` | Package di-extract ke `autoinspectai-weights/` |
| 7 | INDUSIA HMI | Klik "Deploy" di Model Registry | AI Edge restart, model baru aktif |
| 8 | INDUSIA HMI | Verifikasi dengan beberapa sample inspeksi | Board baru **AKTIF** di production line ✅ |

### 2.4 Isi Model Package (.zip)

```
model_package_{board}_{version}.zip
├── weights/                    ← OpenVINO IR files (.xml + .bin) per komponen
├── config.yaml                 ← Pipeline DAG definition (graphflow)
├── components/
│   ├── comp-01.yaml            ← Sub-pipeline per komponen
│   ├── comp-02.yaml
│   └── ...
├── settings.yaml               ← Camera params (exposure, gain, luminance)
├── locations.yaml              ← Frame ID mapping per posisi kamera
├── assets/
│   └── templates/              ← Fiducial template images untuk YOLO OBB
└── manifest.json               ← Version, board ID, checksums, metrics summary
```

| File / Folder | Dipakai oleh |
|---------------|--------------|
| `weights/` | AI Service (port 8001) |
| `config.yaml`, `components/*.yaml` | AI Service |
| `settings.yaml`, `locations.yaml` | AI Edge (port 8002) |
| `assets/templates/` | AI Edge |
| `manifest.json` | HMI (validation + checksum) |

---

## 3. Label Studio Fork Strategy

### 3.1 Kenapa Fork, Bukan Pakai As-Is

| Pendekatan | Effort | Kelebihan | Kekurangan |
|------------|--------|-----------|------------|
| Pakai Label Studio as-is | Nol | Tidak ada development | Tidak bisa tambah BOM panel, training trigger, custom workflow |
| Embed via iframe di HMI | Rendah | Cepat | Tidak seamless, auth berbeda, sulit custom |
| **Fork + Customize (DIPILIH)** | Medium | UI sepenuhnya bisa disesuaikan, BOM workflow terintegrasi, training trigger langsung | Perlu maintain fork saat Label Studio update |

> **✅ Kenapa Fork Tepat untuk Kasus Ini**
>
> Visual Editor Platform berjalan TERPISAH dari HMI — tidak ada masalah integrasi auth atau database. Label Studio Apache 2.0 bebas di-fork dan dimodifikasi untuk tujuan komersial. Development effort jauh lebih rendah dibanding membangun canvas labelling dari scratch (Konva.js dll). Label Studio sudah mature dengan fitur bbox, polygon, review workflow, dan multi-annotator.

### 3.2 Yang Tidak Diubah dari Label Studio

- Core annotation engine (bbox, polygon, keypoint, classification)
- Multi-annotator + review workflow
- Export format (YOLO, COCO, Pascal VOC) — tinggal tambah format ais-compatible
- ML Backend API — dipakai untuk connect GroundingDINO pre-labeler
- Storage backend (SQLite / PostgreSQL)
- Python Django backend structure

### 3.3 Yang Ditambahkan di Atas Label Studio

| Komponen Baru | Lokasi di Codebase | Fungsi |
|---------------|--------------------|--------|
| BOM Upload Panel | Frontend: React component baru di sidebar kanan | Upload + parse BOM Excel, tampilkan component list, warna bbox per ref designator |
| Confidence Color Overlay | Frontend: extend existing bbox renderer | Hijau (>85%) / Kuning (60–85%) / Merah (<60%) berdasarkan GroundingDINO confidence score |
| PCB Drawing Viewer | Frontend: tab baru di annotation view | Tampilkan PCB Drawing/Gerber layout, highlight posisi komponen dari BOM |
| Training Manager Tab | Frontend: halaman baru di project view | Trigger `ais train`, lihat progress SSE real-time, log output |
| Eval Metrics Dashboard | Frontend: tab di Training Manager | F1, precision, recall per komponen, confusion matrix, compare vs versi sebelumnya |
| Model Registry | Frontend: halaman di project settings | List semua model version per board, export package, rollback |
| Export ais-compatible | Backend: custom export format | Generate `config.yaml` + `components/*.yaml` + `manifest.json` sesuai format ais pipeline |
| Auto-Label Trigger | Frontend + Backend | Tombol "Auto Label" → call Auto-Label Service (port 8003) → pre-populate bbox |

---

## 4. Alur Kerja Lengkap

### 4.1 Zero-Touch Board Onboarding (12 Step)

| Step | Aktor | Aksi | Teknologi | Output |
|------|-------|------|-----------|--------|
| 1 | Engineer | Buat project baru di Visual Editor, input board ID + nama | Label Studio fork | Project dibuat di database lokal |
| 2 | Engineer | Upload BOM Excel | BOM Parser Service (Gemini Flash API + openpyxl) | JSON: list ref designator (R1, C5, U3, Q2...) |
| 3 | Engineer | Upload PCB Drawing (PDF/Gerber) | pygerber + Gemini Vision API | Koordinat XY per ref designator (opsional, untuk reference) |
| 4 | Engineer | Upload Golden Sample Photos (ZIP, 20–50 foto) | Label Studio storage | Foto full-board GOOD tersimpan, siap di-annotate |
| 5 | AI | Klik "Auto Label" — AI detect semua komponen | GroundingDINO + SAM 2.1 (Auto-Label Service port 8003) | Bbox per komponen + confidence score per foto |
| 6 | AI | Match deteksi vs BOM list | Algoritma Hungarian matching | Label per bbox: "C5", "U3", confidence, status (hijau/kuning/merah) |
| 7 | Engineer | Review & koreksi di Label Studio annotation view | Label Studio fork (BOM panel + confidence overlay) | Semua bbox di-approve, dataset final |
| 8 | System | Auto-crop per komponen dari annotated images | `ais data crop config.yaml` | Folder: `comp-01/`, `comp-02/`, ... di local filesystem |
| 9 | System | Diversity filtering | `ais data filter -n 5` | Subset representatif per komponen (5 most diverse) |
| 10 | System | Training anomaly models | `ais train batch -m dino` (dan/atau `patchcore`) | Model weights di `runs/models/` (OpenVINO IR format) |
| 11 | System | Evaluasi + threshold tuning | `ais eval fit --apply` | F1, precision, recall per komponen; threshold di-update di YAML |
| 12 | Engineer | Review eval metrics, approve, export model package | Training Manager tab + Model Registry | `model_package_{board}_{version}.zip` siap di-transfer ke HMI |

### 4.2 Self-Improving False Call Loop

```
Operator klik NG (false call di HMI)
        ↓
HMI auto-detect false call
(AI PASS + operator NG, atau AI FAIL + operator GOOD)
        ↓
Image tersimpan di storage/false-calls/ lokal HMI
        ↓
Cloud sync (background) → Supabase Storage
        ↓
Manager review & approve via OverrideReviewModal
        ↓
Threshold tercapai (N=10 false calls ATAU FCR > 5%)
        ↓
Notifikasi ke engineer di Visual Editor Platform
        ↓
Engineer download false call batch dari Supabase Storage
        ↓
Engineer klik "Start Retraining" di Training Manager
        ↓
ais train batch (background) → eval → threshold fit
        ↓
Engineer review metrics (compare vs model sebelumnya)
        ↓
Approve → Export .zip → Transfer ke HMI → Deploy
        ↓
Model baru aktif → FCR turun ✅
```

| Step | Trigger | Aksi | Output |
|------|---------|------|--------|
| 1 | Operator klik NG di HMI (false call) | HMI auto-detect false call | Image tersimpan di `storage/false-calls/` lokal HMI |
| 2 | Cloud sync (background) | False call images sync ke Supabase Storage | Images tersedia di cloud dengan metadata inspection ID |
| 3 | Engineer di Visual Editor | Download false call image batch dari Supabase Storage | Images tersedia lokal di Visual Editor untuk review |
| 4 | Manager review di HMI | Approve/reject false call via OverrideReviewModal | Override status = approved, siap masuk training pool |
| 5 | Threshold tercapai (N=10 atau FCR>5%) | Sistem kirim notifikasi ke engineer | Notifikasi di Training Manager tab + optional email |
| 6 | Engineer approve retrain | Klik "Start Retraining" di Training Manager | Training job created, ais pipeline berjalan background |
| 7 | Training selesai | Eval metrics ditampilkan, bandingkan vs model sebelumnya | Model baru v(N+1) siap di-review |
| 8 | Engineer approve deploy | Klik "Export Model" → transfer ke HMI → import + deploy | Model baru aktif di production, false call rate turun |

---

## 5. Technology Stack

### 5.1 Visual Editor Platform — Frontend (Label Studio Fork)

| Komponen | Teknologi Existing di Label Studio | Customization yang Ditambahkan |
|----------|------------------------------------|-------------------------------|
| Annotation Canvas | React + custom canvas renderer (bbox, polygon) | Tambah confidence color overlay, BOM label panel kanan |
| UI Framework | Django templates + React (LSF - Label Studio Frontend) | Tambah Training Manager tab, Model Registry page, BOM Upload wizard |
| State Management | Redux (sudah ada di Label Studio) | Extend untuk BOM data, training job state, model version state |
| File Upload | Built-in Label Studio upload | Extend untuk ZIP batch + Excel + PDF/Gerber |
| Progress Stream | Tidak ada (tambah baru) | SSE consumer untuk training progress dari Training Runner (port 8005) |
| Charts (Eval Metrics) | Tidak ada (tambah baru) | Recharts atau Chart.js untuk F1/precision/recall chart |
| Export Format | YOLO, COCO, Pascal VOC (sudah ada) | Tambah format ais-compatible: `config.yaml` + `components/*.yaml` + `manifest.json` |

### 5.2 Auto-Label Service (Baru, Port 8003)

| Komponen | Teknologi | Keterangan |
|----------|-----------|------------|
| Framework | Python FastAPI | REST API + SSE streaming, konsisten dengan AI Edge/Service existing |
| Component Detection | GroundingDINO (`IDEA-Research/grounding-dino-base`, 21.9M downloads, Apache 2.0) | Zero-shot detection dari text prompt tanpa training. Prompt: `"capacitor C5"`, `"IC chip U3"` |
| Precise Segmentation | SAM 2.1 (`facebook/sam2.1-hiera-large`, 224M params, Apache 2.0) | Pixel-accurate bounding box dari point/box prompt GroundingDINO |
| BOM Matching | SciPy Hungarian algorithm (`scipy.optimize.linear_sum_assignment`) | Optimal assignment: cocokkan N deteksi vs M ref designator dari BOM |
| Confidence Scoring | Custom logic berbasis GroundingDINO score + area ratio | Hijau >85% / Kuning 60–85% / Merah <60% |
| Inference Runtime | PyTorch + CUDA (GPU), dengan fallback ke CPU via OpenVINO | Sama dengan AI Service existing (reuse conda env `ais` atau buat env baru) |
| Image Processing | OpenCV + Pillow | Pre-processing: resize, normalize. Post-processing: bbox to Label Studio format |

### 5.3 BOM Parser Service (Baru, Port 8004)

| Input Format | Parser Utama | Fallback | Output |
|--------------|-------------|----------|--------|
| Excel BOM (`.xlsx`/`.xls`) | openpyxl → extract ref designator + value + package | Gemini Flash API untuk handle format tidak standar (merged cells, dll) | `JSON: [{ref:"R1", value:"10k", package:"0402"}, ...]` |
| PDF Schematic / Layout | Gemini Vision API (multimodal) | Manual input via UI | JSON: approximate koordinat + ref designator dari gambar layout |
| Gerber File (`.gbr`) | pygerber library (open source Python) | Tidak ada (Gerber adalah format paling akurat) | JSON: XY footprint per ref designator (koordinat presisi) |
| PCB Screenshot/Photo | Gemini Vision API | Manual crop + label di Visual Editor | Approximate koordinat — hanya untuk reference, bukan training data |

### 5.4 Training Runner Service (Baru, Port 8005)

| Endpoint | Method | Fungsi |
|----------|--------|--------|
| `/api/training/start` | POST | Terima `board_id` + `model_type`, spawn `ais train batch` subprocess, return `job_id` |
| `/api/training/progress/{job_id}` | GET (SSE) | Stream stdout/stderr dari `ais train` ke client — persentase, fase, log line per line |
| `/api/training/status/{job_id}` | GET | Status job: `queued` / `running` / `completed` / `failed` + progress persen |
| `/api/training/cancel/{job_id}` | POST | Graceful kill subprocess, cleanup temp files |
| `/api/training/eval` | POST | Run `ais eval -c config.yaml -d ./test-data --cropped`, return metrics JSON |
| `/api/training/threshold-fit` | POST | Run `ais eval fit config.yaml --apply`, update threshold di YAML config |
| `/api/models/export` | POST | Package weights + configs + manifest → `.zip`, return download URL |
| `/api/models/history/{board_id}` | GET | List semua training job + metrics per board, sorted by date |

### 5.5 INDUSIA HMI — Model Import Endpoint (Tambahan)

| Endpoint | Method | Fungsi |
|----------|--------|--------|
| `/api/model-import/upload` | POST | Upload `model_package.zip`, validasi `manifest.json`, extract ke staging area |
| `/api/model-import/validate/{import_id}` | GET | Cek checksum, validasi semua file tersedia, preview metrics sebelum deploy |
| `/api/model-import/deploy/{import_id}` | POST | Copy dari staging ke `prod/configs/{board}/`, update manifest, trigger AI Edge restart |
| `/api/model-import/rollback/{board_id}` | POST | Restore dari `backup/{board}-{version}/`, restart AI Edge |
| `/api/model-import/history/{board_id}` | GET | List semua versi model yang pernah di-deploy beserta metrics |

---

## 6. Rencana Implementasi

### 6.1 Ringkasan Fase

| Fase | Nama | Durasi | Prioritas | Hasil Akhir |
|------|------|--------|-----------|-------------|
| 1 | Label Studio Fork Setup | Minggu 1–2 | 🔴 CRITICAL | Repo fork berjalan lokal, custom branding, BOM upload panel dasar |
| 2 | BOM Parser + Auto-Label Engine | Minggu 3–5 | 🔴 CRITICAL | GroundingDINO + SAM berjalan, auto-bbox dari golden sample foto |
| 3 | Label Studio Custom UI | Minggu 5–7 | 🔴 CRITICAL | BOM panel terintegrasi, confidence overlay, PCB Drawing viewer |
| 4 | Training Runner + Pipeline UI | Minggu 8–9 | 🟠 HIGH | One-click training + SSE progress real-time di Training Manager tab |
| 5 | Eval Dashboard + Export Package | Minggu 10–11 | 🟠 HIGH | Metrics dashboard, export `.zip` format ais-compatible |
| 6 | HMI Model Import + Deploy | Minggu 12 | 🟠 HIGH | Upload `.zip` di HMI, validate, 1-click deploy ke AI Edge |
| 7 | Self-Improving Loop | Minggu 13–14 | 🟡 MEDIUM | False call download → retrain pipeline fully integrated |
| 8 | Gerber Parser + Polish | Minggu 15–16 | 🟢 NICE | Gerber parser akurat, UX polish, documentation |
| 9 | Production Hardening | Minggu 17–18 | 🟠 HIGH | Security audit, performance, multi-customer, backup strategy |

### 6.2 Detail per Fase

---

#### FASE 1 — Fork Setup (Minggu 1–2) 🔴 CRITICAL

**Deliverables:**
- [ ] Fork repo: `git clone https://github.com/HumanSignal/label-studio.git` → `indusia-visual-editor`
- [ ] Setup development environment: `conda create -n ils python=3.10`, install dependencies
- [ ] Custom branding: ganti logo, warna, nama "INDUSIA AI Visual Editor" (Apache 2.0 boleh)
- [ ] Buat database schema tambahan: tabel `bom_sessions`, `component_annotations`, `training_jobs`, `model_versions`
- [ ] Setup BOM Parser Service skeleton (port 8004): FastAPI + openpyxl, endpoint `/api/bom/parse`
- [ ] Test BOM parser dengan file BOM `NV80-023027-0101.xls` sebagai test case pertama
- [ ] Dokumentasi: README setup, cara run semua service, troubleshooting

**Acceptance Criteria:** Label Studio fork berjalan lokal. BOM Excel `NV80-023027-0101.xls` ter-parse dengan akurasi >95%.

---

#### FASE 2 — Auto-Label Engine (Minggu 3–5) 🔴 CRITICAL

**Deliverables:**
- [ ] Setup conda environment baru: `conda create -n als python=3.10` (terpisah dari `ais` dan `aie`)
- [ ] Install GroundingDINO: `pip install groundingdino-py`, download weights `grounding_dino_base.pth` (~700MB)
- [ ] Install SAM 2.1: `pip install sam2`, download checkpoint `sam2.1_hiera_large.pt` (~800MB)
- [ ] Build Auto-Label Service (port 8003): FastAPI, endpoint `POST /api/autolabel/detect`
- [ ] Pipeline: GroundingDINO detect dari BOM ref designator → SAM 2.1 refine bbox → Hungarian matching
- [ ] Confidence scoring + output format: `JSON [{ref_designator, bbox_x, bbox_y, bbox_w, bbox_h, confidence, status}]`
- [ ] Batch processing: handle ZIP 20–50 foto, aggregate bbox dari multiple foto per komponen
- [ ] GPU memory management: sequential mode jika VRAM < 14GB (GroundingDINO lalu SAM, bukan parallel)
- [ ] Test dengan golden sample foto PCB NV80-023027, target **>70% bbox correct** tanpa koreksi manual

**Acceptance Criteria:** Auto-label menghasilkan >70% bbox correct pada test board NV80-023027 dengan 30 golden sample foto, tanpa koreksi manual.

---

#### FASE 3 — Label Studio Custom UI (Minggu 5–7) 🔴 CRITICAL

**Deliverables:**
- [ ] BOM Panel: React component di sidebar kanan annotation view, list semua ref designator dari BOM
- [ ] BOM Panel: status per komponen (✅ labelled / ⚠️ review needed / ❌ missing)
- [ ] Confidence overlay: extend bbox renderer — warna border sesuai confidence (hijau/kuning/merah)
- [ ] Confidence overlay: tooltip saat hover bbox menampilkan ref designator + confidence % + auto/manual
- [ ] "Auto Label" button di toolbar: trigger call ke Auto-Label Service, populate bbox dengan pre-label
- [ ] PCB Drawing Viewer: tab baru di annotation view, tampil PDF/gambar drawing, highlight posisi dari BOM
- [ ] Bulk actions: "Approve all green" (>85% confident), "Flag all yellow for review"
- [ ] Auto-save: simpan progress review kapan saja, bisa resume sesi berikutnya
- [ ] Export ais-compatible: tambah export format baru yang generate `config.yaml` + `components/*.yaml`

**Acceptance Criteria:** Engineer bisa complete full labelling session (upload BOM + auto-label + review semua bbox) dalam < 4 jam untuk board dengan 50+ komponen.

---

#### FASE 4 — Training Pipeline UI (Minggu 8–9) 🟠 HIGH

**Deliverables:**
- [ ] Training Runner Service (port 8005): FastAPI wrapper di atas `ais` CLI tools
- [ ] Endpoint `POST /api/training/start`: spawn `ais data crop` → `ais data filter` → `ais train batch` sebagai subprocess
- [ ] SSE endpoint `GET /api/training/progress/{job_id}`: stream stdout `ais` tools real-time ke browser
- [ ] Training Manager tab di Label Studio fork: progress stepper 5 fase (Crop → Filter → Train → Eval → Threshold)
- [ ] Log console: tampilkan raw output dari `ais` tools, auto-scroll, bisa di-copy
- [ ] Resource monitor: CPU/GPU usage (psutil + nvidia-smi wrapper), estimated time remaining
- [ ] Cancel training: graceful kill subprocess dengan cleanup temp files
- [ ] Training history: list semua job per board dengan status, duration, dan quick metrics

**Acceptance Criteria:** Training job berjalan tanpa error dari UI. SSE progress stream tampil real-time. Training selesai dalam waktu yang diestimasi (<45 menit dengan GPU).

---

#### FASE 5 — Eval Dashboard + Export Package (Minggu 10–11) 🟠 HIGH

**Deliverables:**
- [ ] Eval dashboard: tabel precision / recall / F1 per komponen dengan color coding (hijau/kuning/merah)
- [ ] Confusion matrix visualization per komponen (TP, FP, FN, TN)
- [ ] Side-by-side comparison: model baru vs model versi sebelumnya (diff metrics)
- [ ] Threshold visualization: anomaly score distribution per komponen + current threshold line
- [ ] Approval workflow: engineer harus klik "Approve & Export" — tidak bisa export jika F1 < model sebelumnya (auto-block)
- [ ] Export Package builder: zip `weights/` + `config.yaml` + `components/*.yaml` + `settings.yaml` + `locations.yaml` + `assets/templates/` + `manifest.json`
- [ ] `manifest.json` berisi: `board_id`, `version`, `training_date`, `metrics_summary`, `file_checksums`
- [ ] Model Registry page: list semua versi, download `.zip`, tandai versi yang sedang aktif di HMI

**Acceptance Criteria:** Model package `.zip` di-generate dengan benar. Semua file ada. `manifest.json` lengkap dengan checksum. Metrics akurasi minimal setara dengan model yang di-setup manual via CLI.

---

#### FASE 6 — HMI Model Import (Minggu 12) 🟠 HIGH

**Deliverables:**
- [ ] Endpoint `POST /api/model-import/upload` di INDUSIA HMI: upload `.zip`, validasi `manifest.json`
- [ ] Validasi: cek checksum semua file, verifikasi `board_id` match dengan board yang ada di DB
- [ ] Staging area: extract ke `D:\autoinspectai-weights\staging\{import_id}\` sebelum deploy
- [ ] Preview halaman di `/engineering/model-registry/import/{import_id}`: tampil metrics dari `manifest.json`
- [ ] Endpoint `POST /api/model-import/deploy`: copy staging → `prod/configs/{board}/`, update manifest, trigger AI Edge restart
- [ ] Backup otomatis: sebelum deploy, copy prod config ke `prod/backup/{board}-{old_version}/`
- [ ] Post-deploy verification: auto-run `ais inspect` inference pada sample images untuk konfirmasi model loaded
- [ ] Rollback endpoint: restore dari backup folder + restart AI Edge

**Acceptance Criteria:** Upload `.zip` di HMI berhasil. Validasi checksum pass. Deploy ke AI Edge berhasil. Board baru bisa inspect setelah deploy tanpa restart manual.

---

#### FASE 7 — Self-Improving Loop (Minggu 13–14) 🟡 MEDIUM

**Deliverables:**
- [ ] False call export dari HMI: endpoint `GET /api/overrides/export` → download approved false call images sebagai ZIP
- [ ] Atau sync via Supabase Storage: engineer download batch false call images dari cloud ke Visual Editor Platform
- [ ] Import false call images ke Label Studio project sebagai "NG" labeled samples
- [ ] FCR tracker di Training Manager: tampil false call rate per board dari data Supabase Cloud
- [ ] Threshold engine: alert ke engineer saat FCR > 5% atau >10 false calls terkumpul
- [ ] One-click retrain: merge false call images + existing good samples → training pipeline otomatis
- [ ] A/B tracking: catat FCR before/after setiap retraining cycle untuk validasi improvement
- [ ] Weekly learning report: summary otomatis per board (model version, FCR trend, total false calls processed)

**Acceptance Criteria:** False call loop berjalan end-to-end tanpa intervensi developer. FCR turun >20% dalam 2 minggu setelah retraining pertama.

---

#### FASE 8 — Gerber Parser + Polish (Minggu 15–16) 🟢 NICE

**Deliverables:**
- [ ] Gerber parser via pygerber: extract footprint koordinat XY per ref designator dari `.gbr` files
- [ ] Auto-match Gerber koordinat → BOM ref designator → auto pre-position bbox di annotation view
- [ ] UX polish: keyboard shortcuts (A = approve, R = reject, N = next, P = previous)
- [ ] Onboarding tutorial: walkthrough pertama kali pakai Visual Editor Platform
- [ ] Docker Compose setup: `docker-compose up` jalankan semua service sekaligus
- [ ] Documentation: user guide untuk engineer customer, admin guide untuk setup

---

#### FASE 9 — Production Hardening (Minggu 17–18) 🟠 HIGH

**Deliverables:**
- [ ] Security audit: review semua endpoint, input validation, auth
- [ ] Multi-customer isolation: setiap customer punya project space terpisah, data tidak bercampur
- [ ] Performance testing: load test dengan 3 customer simultaneous, 50+ foto per board
- [ ] Backup strategy: automated daily backup Label Studio DB + model artifacts
- [ ] Monitoring: health check endpoint semua service, alerting jika service down
- [ ] Docker Compose production setup dengan resource limits

**Acceptance Criteria:** Platform support 3 customer simultan tanpa performance degradation. Security audit passed. Docker Compose setup berjalan dalam 1 command.

---

## 7. Database Schema

### 7.1 Visual Editor Platform — Tabel Tambahan (di Label Studio DB)

| Tabel | Fungsi | Kolom Utama |
|-------|--------|-------------|
| `bom_sessions` | Setiap sesi upload + parse BOM per project/board | `id`, `project_id`, `board_id`, `file_path`, `parsed_data` (JSONB), `status`, `created_by`, `created_at` |
| `component_annotations` | Per-bbox annotation dengan metadata BOM | `id`, `task_id`, `ref_designator`, `confidence`, `source` (auto/manual), `status` (approved/review/rejected), `created_at` |
| `training_jobs` | Setiap training run per board | `id`, `board_id`, `model_type` (dino/patchcore), `status`, `started_at`, `finished_at`, `output_path`, `triggered_by` |
| `training_metrics` | Hasil eval per training job per komponen | `id`, `job_id`, `component_ref`, `precision`, `recall`, `f1`, `threshold`, `confusion_matrix` (JSONB) |
| `model_versions` | Registry semua model yang pernah dibuat | `id`, `board_id`, `version`, `job_id`, `package_path`, `deployed_at`, `deployed_by`, `is_active`, `metrics_summary` (JSONB) |
| `false_call_imports` | Batch import false call images dari HMI | `id`, `board_id`, `import_date`, `image_count`, `source_url` (Supabase), `status`, `processed_by` |
| `retrain_triggers` | Log kapan retrain di-trigger dan alasannya | `id`, `board_id`, `trigger_type` (manual/fcr_threshold/count_threshold), `fcr_value`, `false_call_count`, `triggered_by` |

### 7.2 INDUSIA HMI — Tabel Tambahan

| Tabel Existing / Baru | Perubahan / Fungsi |
|-----------------------|-------------------|
| `boards` (existing) | Tambah kolom: `active_model_version TEXT`, `last_import_at TIMESTAMPTZ`, `has_trained_model BOOLEAN` |
| `model_imports` (baru) | Track setiap import: `id`, `board_id`, `package_path`, `manifest_data` (JSONB), `imported_by`, `import_at`, `status` |
| `model_deployments` (baru) | Log setiap deploy: `id`, `import_id`, `board_id`, `deployed_by`, `deployed_at`, `previous_version`, `notes` |
| `inspection_results` (existing) | Tambah kolom: `model_version TEXT` — track model version yang dipakai saat inspeksi berlangsung |
| `overrides` (existing) | Tambah kolom: `exported_at TIMESTAMPTZ`, `export_batch_id TEXT` — track apakah sudah di-export ke Visual Editor |

---

## 8. Hardware & Infrastruktur

### 8.1 Visual Editor Platform — PC Requirements

| Komponen | Minimum | Rekomendasi | Keterangan |
|----------|---------|-------------|------------|
| GPU | RTX 3060 12GB | RTX 4070 12GB | GroundingDINO (~6–8GB VRAM) + SAM 2.1 (~8–10GB VRAM). Total butuh >14GB jika parallel, atau >8GB jika sequential |
| RAM | 16GB | 32GB | Label Studio + Auto-Label Service + Training Runner + Django bisa makan 8–12GB total |
| Storage | 500GB SSD | 1TB NVMe SSD | Model weights GroundingDINO + SAM (~2GB) + golden sample dataset + training artifacts per board (~1–5GB/board) |
| CPU | i7 gen 10+ | i9 gen 12+ / Ryzen 9 5900X | Preprocessing images + Django server + PostgREST (jika pakai PostgreSQL backend Label Studio) |
| OS | Windows 10/11 atau Ubuntu 20.04+ | Ubuntu 22.04 LTS | Ubuntu lebih stabil untuk PyTorch + CUDA stack. Windows juga bisa dengan conda. |

> **💡 Opsi Jika VRAM Tidak Cukup**
>
> Jika hanya ada GPU dengan <12GB VRAM (misalnya RTX 3060 8GB atau laptop GPU): Gunakan `GroundingDINO-tiny` (172M params, ~3GB VRAM) + `SAM 2.1 Small` (~4GB VRAM). Akurasi auto-label sedikit lebih rendah (~65–70% vs ~75–80%) tapi development dan review tetap feasible. Atau: jalankan GroundingDINO dan SAM secara sequential (bukan parallel) — lebih lambat (~2x) tapi hemat VRAM.

### 8.2 Estimasi Waktu Proses Per Board (Visual Editor Platform)

| Proses | Hardware | Estimasi Waktu | Keterangan |
|--------|----------|----------------|------------|
| BOM Parsing (Excel) | CPU + Gemini API | 5–10 detik | Tergantung jumlah rows + format BOM |
| Auto-label 30 foto golden | RTX 3060 12GB (sequential) | 5–8 menit | GroundingDINO per foto ~3–5 detik + SAM ~2–4 detik |
| Auto-label 30 foto golden | RTX 4070 12GB (parallel) | 2–4 menit | GroundingDINO + SAM parallel per foto ~4–8 detik total |
| Auto-label 30 foto golden | CPU only (i9-13900H) | 20–35 menit | Feasible untuk onboarding tidak urgent, tidak perlu GPU |
| `ais data crop` + filter | CPU | 2–5 menit | Tergantung resolusi foto (20MP = lebih lama) |
| Training DINOv2 (5 komponen) | RTX 3060 12GB | 10–20 menit | Build feature bank dari good images, bukan full training backprop |
| Training PatchCore (1 komponen) | RTX 3060 12GB | 5–10 menit | Coreset selection dari patch features |
| Training CPU only (5 komponen) | i9-13900H | 1.5–3 jam | Acceptable untuk setup one-time, tidak perlu GPU |
| `ais eval` + threshold-fit | CPU | 5–10 menit | Run inference pada test set, hitung optimal threshold |
| Export model package (.zip) | CPU | <1 menit | Copy + zip files, checksum calculation |
| **TOTAL end-to-end (GPU)** | RTX 3060 + i9 | **~30–50 menit** | Dari upload BOM sampai `model_package.zip` siap |
| **TOTAL end-to-end (CPU only)** | i9-13900H | **~3–5 jam** | Feasible untuk penggunaan tidak urgent |

---

## 9. Security & Compliance

### 9.1 Access Control — Visual Editor Platform

| Role | Board Manager | Labelling | Training Manager | Model Export |
|------|--------------|-----------|------------------|--------------|
| Labeller | ❌ | ✅ Annotate only | ❌ | ❌ |
| Engineer | ✅ Full | ✅ Full + approve | ✅ Full | ✅ Approve & export |
| SuperAdmin | ✅ Full | ✅ Full | ✅ Full | ✅ Full |

### 9.2 Access Control — INDUSIA HMI (Model Import)

| Role | Model Import Upload | Validate & Preview | Deploy ke Production | Rollback |
|------|--------------------|--------------------|---------------------|----------|
| Operator | ❌ | ❌ | ❌ | ❌ |
| Manager | ❌ | ✅ View only | ❌ | ❌ |
| Engineer | ✅ | ✅ | ⚠️ Approve only | ⚠️ Approve only |
| SuperAdmin | ✅ | ✅ | ✅ | ✅ |

### 9.3 Perlindungan Data & IP Customer

> **⚠️ PENTING: IP Customer**
>
> BOM List, PCB Drawing, dan Golden Sample Photos adalah dokumen rahasia customer. Sistem wajib memastikan:
> 1. Semua file customer tersimpan **LOKAL** di Visual Editor Platform PC — tidak pernah dikirim ke cloud tanpa persetujuan eksplisit.
> 2. Gemini API hanya menerima **TEKS** dari BOM (bukan foto PCB atau drawing).
> 3. **Mode offline-only** tersedia: customer bisa pilih tidak pakai Gemini API, gunakan parser lokal saja.
> 4. Model package (`.zip`) yang di-export **tidak mengandung** foto original customer — hanya weights dan config.
> 5. Setiap aksi tercatat di **audit log**.

- Label Studio fork: ganti default domain/email di settings agar tidak kirim data ke HumanSignal servers
- Label Studio: disable analytics telemetry (`LABEL_STUDIO_DISABLE_SEND_ANALYTICS=true`)
- Gemini API calls: log semua request/response untuk audit, mask sensitive BOM data
- Model package (`.zip`): tidak ada foto PCB customer di dalamnya — hanya weights + YAML configs
- Backup otomatis: sebelum setiap deploy di HMI, backup model lama ke `prod/backup/`

---

## 10. Estimasi Biaya & Timeline

### 10.1 Biaya Infrastruktur

| Komponen | Biaya | Frekuensi | Keterangan |
|----------|-------|-----------|------------|
| Label Studio (fork) | $0 | One-time | Apache 2.0 — bebas fork, modifikasi, dan pakai komersial |
| GroundingDINO + SAM 2.1 | $0 | One-time download | Open source Apache 2.0, weights ~1.5GB total |
| Gemini Flash API (BOM parsing) | ~$0.001–0.005 per board onboarding | Per event | Sangat murah. Hanya teks BOM yang dikirim, bukan foto |
| GPU untuk Visual Editor PC | ~$300–600 one-time | Sekali beli | RTX 3060 12GB (~$300) atau RTX 4070 12GB (~$600) |
| Storage tambahan | ~$50–100/tahun | Annual | Dataset golden samples + model history + backup per customer |
| Supabase Storage (false call sync) | ~$0–25/bulan | Monthly | Tier gratis sudah cukup untuk awal (1GB storage) |
| Development effort | Internal | 16–18 minggu | Tim developer INDUSIA AI — tidak ada biaya vendor external |

### 10.2 Timeline Keseluruhan (18 Minggu)

| Minggu | Fase | Milestone Kunci | Status HMI |
|--------|------|-----------------|------------|
| 1–2 | Fase 1: Fork Setup | Label Studio fork berjalan, custom branding, BOM parser dasar | Tidak ada perubahan |
| 3–5 | Fase 2: Auto-Label Engine | GroundingDINO + SAM berjalan, auto-bbox dari golden sample foto | Tidak ada perubahan |
| 5–7 | Fase 3: Custom UI | BOM panel, confidence overlay, auto-label workflow di Label Studio | Tidak ada perubahan |
| 8–9 | Fase 4: Training UI | One-click training + SSE progress real-time | Tidak ada perubahan |
| 10–11 | Fase 5: Eval + Export | Metrics dashboard + export `model_package.zip` | Tidak ada perubahan |
| 12 | Fase 6: HMI Import | Upload `.zip` di HMI + validate + 1-click deploy ke AI Edge | **Tambah model import endpoint** |
| 13–14 | Fase 7: Self-Improving | False call download + retrain loop integrated | **Tambah override export endpoint** |
| 15–16 | Fase 8: Gerber + Polish | Gerber parser + UX polish + documentation lengkap | Minor updates |
| 17–18 | Fase 9: Hardening | Security audit, performance, multi-customer support, backup | Security hardening |

> **📅 Target MVP (Minimum Viable Product)**
>
> **Fase 1–6 (Minggu 1–12):** Platform sudah bisa digunakan untuk full onboarding end-to-end. Engineer upload BOM + golden sample → auto-label → review di Label Studio → train → export `.zip` → import di HMI → deploy ke production line. **Tanpa bantuan developer.** Fase 7–9 adalah enhancement untuk production-grade reliability.

---

## 11. Risiko & Mitigasi

| Risiko | Prob. | Impact | Mitigasi |
|--------|-------|--------|----------|
| GroundingDINO akurasi rendah untuk komponen SMD kecil (0402, 0201 resistor/capacitor) | Tinggi | Medium | Auto-label hanya sebagai starting point. Engineer WAJIB review semua bbox di Label Studio. Target >70% benar — sisanya koreksi manual. Ini tetap 70% lebih cepat dari labelling penuh dari awal. |
| Gemini API tidak bisa parse BOM Excel dengan format tidak standar (merged cells, multi-row header) | Medium | Low | Fallback: parser rule-based dengan template mapping kolom. UI untuk manual column mapping. Test dengan 5+ format BOM customer berbeda sebelum launch. |
| VRAM tidak cukup untuk GroundingDINO + SAM bersamaan | Medium | Medium | Gunakan mode sequential (bukan parallel). Atau downgrade ke GroundingDINO-tiny + SAM Small. GPU upgrade RTX 3060 12GB hanya ~$300. |
| Label Studio update besar mempersulit merge ke fork | Medium | Medium | Maintain changelog modifikasi. Prioritaskan modifikasi di frontend (React) bukan backend Django agar lebih mudah di-merge. Pin versi Label Studio hingga ada alasan kuat untuk upgrade. |
| Model package `.zip` corrupt atau checksum mismatch saat transfer ke HMI | Low | High | `manifest.json` berisi SHA256 checksum per file. HMI validasi sebelum deploy. Jika gagal validasi, deploy di-block. |
| Training gagal karena golden sample foto kurang diverse | Medium | High | Diversity score calculator sebelum training (`ais data filter` sudah ada). Panduan minimum: 20 foto, berbagai sudut cahaya, berbagai unit board. |
| Model baru lebih buruk setelah retrain — FCR naik | Low | High | Mandatory comparison dashboard. Auto-block deploy jika F1 < model sebelumnya. Engineer harus approve secara eksplisit. |
| Customer tidak nyaman menginstall Visual Editor Platform di PC mereka | Medium | Low | Provide Docker Compose setup: satu command untuk run semua service. Atau: INDUSIA team yang onboarding, customer hanya perlu provide BOM + golden sample. |

---

## 12. Success Metrics

### 12.1 KPI Platform

| Metrik | Baseline | Target 3 Bulan | Target 6 Bulan |
|--------|----------|----------------|----------------|
| Waktu onboarding board baru | 2–4 minggu | < 3 hari | < 1 hari |
| Akurasi auto-labelling GroundingDINO | N/A (manual) | > 70% bbox correct | > 80% bbox correct |
| Waktu review engineer per board | N/A | < 4 jam (50+ komponen) | < 1.5 jam |
| False call rate setelah 1 bulan deploy | 5–10% | < 5% | < 2% |
| Jumlah board aktif ter-support | 4 board | 10 board | 20+ board |
| Waktu training per board (GPU) | Manual CLI ~1 jam | < 45 menit (UI) | < 20 menit |
| Waktu import + deploy model ke HMI | Manual ~30 menit | < 5 menit | < 2 menit |
| NPS engineer customer | N/A | > 7/10 | > 8.5/10 |

### 12.2 Acceptance Criteria per Fase

| Fase | Acceptance Criteria |
|------|---------------------|
| Fase 1 | Label Studio fork berjalan lokal. BOM Excel `NV80-023027-0101.xls` ter-parse dengan akurasi >95%. |
| Fase 2 | Auto-label menghasilkan >70% bbox correct pada test board NV80-023027 dengan 30 golden sample foto, tanpa koreksi manual. |
| Fase 3 | Engineer bisa complete full labelling session (upload BOM + auto-label + review semua bbox) dalam < 4 jam untuk board dengan 50+ komponen. |
| Fase 4 | Training job berjalan tanpa error dari UI. SSE progress stream tampil real-time. Training selesai dalam waktu yang diestimasi (<45 menit dengan GPU). |
| Fase 5 | Model package `.zip` di-generate dengan benar. Semua file ada. `manifest.json` lengkap dengan checksum. Metrics akurasi minimal setara dengan model yang di-setup manual via CLI. |
| Fase 6 | Upload `.zip` di HMI berhasil. Validasi checksum pass. Deploy ke AI Edge berhasil. Board baru bisa inspect setelah deploy tanpa restart manual. |
| Fase 7 | False call loop berjalan end-to-end tanpa intervensi developer. FCR turun >20% dalam 2 minggu setelah retraining pertama. |
| Fase 9 | Platform support 3 customer simultan tanpa performance degradation. Security audit passed. Docker Compose setup berjalan dalam 1 command. |

---

## Next Steps

1. Review & finalisasi dokumen ini dengan tim
2. Kickoff Fase 1: fork Label Studio, setup dev environment, test BOM parser
3. Setup conda env `als`: install GroundingDINO + SAM 2.1
4. Test Auto-Label dengan BOM `NV80-023027` + golden sample PCB
5. Kick-off meeting dengan engineer customer Evident Scientific

---

*─── INDUSIA AI · Building the Future of PCB Inspection ───*
