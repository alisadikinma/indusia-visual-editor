# Operator Onboarding — First Inspection in 60 Minutes

Audience: an MI-division operator or supervisor who has never used the
visual editor before. Goal: take a new PCB from "BOM + golden photo" to
"production inspection running on the edge" in under an hour.

The interface is in Bahasa Indonesia. Technical terms (designator,
fiducial, train, deploy) stay in English because the existing factory
floor already uses them.

## 0. Apa yang Anda butuhkan sebelum mulai

- Akses ke `https://indusia.<your-domain>` (admin sudah memberikan akun)
- File BOM Excel (XLSX) atau CSV — kolom designator, value, package, qty
- 2 foto golden sample PCB: top dan bottom, fokus tajam, pencahayaan rata
- Opsional: gambar layout PCB (JPG/PNG)

Login pertama kali: pakai email + password yang admin kasih. Setelah
masuk, browser akan menyimpan sesi 1 jam; setelah itu refresh otomatis.

## 1. Buat project baru (5 menit)

1. Klik **+ Project Baru** di dashboard
2. Isi:
   - **Nama**: contoh `MainBoard-Rev3`
   - **Slug**: auto-generated, edit kalau perlu
3. Klik **Simpan** → masuk ke wizard upload

## 2. Upload BOM + golden + drawing (10 menit)

Di halaman wizard:

1. **BOM** — drag file XLSX/CSV. Parser akan auto-detect kolom (sinonim
   "designator/ref/comp", "value/val", dst). Multi-designator dalam satu
   baris (e.g. `R1, R2, R3`) akan otomatis di-expand jadi 3 row.
2. **Golden top** — foto PCB sisi atas
3. **Golden bottom** — foto PCB sisi bawah
4. **Drawing** (opsional) — gambar layout
5. Klik **Lanjut** ke labeling

Kalau parser gagal (BOM format tidak ketebak), wizard akan tampilkan
pesan 422 dalam bahasa Indonesia. Edit kolom header BOM dan re-upload.

## 3. Tentukan scope inspeksi (10 menit)

Halaman labeling:

1. Daftar BOM muncul di kiri. Default semua component status `pending`
2. Pilih komponen yang **mau diinspeksi**:
   - Click row → toggle `inspected`
   - Untuk komponen yang tidak perlu (test points, dummy, holes), set
     `skipped`
3. Untuk tiap row `inspected`, pilih:
   - **Defect criteria** (multi-select): missing component, orientation,
     polarity flip, dst. Default heuristic berdasarkan component type.
   - **Scope mode**: `per_component` (default, paling akurat) atau
     `whole_side` (untuk solder bridge yang lintas komponen)
4. Klik **🤖 Build inspection pipeline** → Gemma akan generate pipeline
   plan (15-30 detik)
5. Review plan di drawer kanan. Kalau OK, klik **Setujui rencana**

## 4. Anotasi region di canvas (15 menit)

Halaman LSF canvas (Label Studio Frontend):

1. Untuk tiap designator `inspected`, gambar bounding box di golden image
2. Letakkan 3 fiducial keypoints di sudut PCB (alignment marker)
3. Sistem akan auto-suggest bounding box untuk designator yang punya
   pre-label dari Gemma — review dan adjust kalau perlu
4. Klik **Simpan label**

## 5. Gate 1 — Mulai training (5 menit + waktu training)

1. Halaman Gate 1 menunjukkan ringkasan dataset:
   - Total component inspected
   - Component per defect criterion
   - AI-suggested epochs + augmentation intensity
2. Review angka — kalau dataset terlalu kecil (< 30 per kriteria),
   tambah anotasi dulu
3. Klik **Mulai Training** → API memanggil `auto-inspect-service`
4. Halaman training progress: live SSE stream dari training service.
   Tunggu sampai status `succeeded` (durasi tergantung dataset, biasanya
   20-60 menit)

⚠️ Jangan tutup browser tab — kalau terlanjur, balik ke halaman dengan
`/projects/<id>/training/<run-id>` dan SSE akan reconnect.

## 6. Evaluasi hasil (10 menit)

Halaman eval (otomatis muncul setelah training selesai):

1. Global metrics: mAP, F1 per komponen
2. Worst-FP grid: gambar prediksi yang salah-positive (component bagus
   dideteksi defect)
3. Worst-FN grid: yang salah-negative (defect terlewat)
4. Klik gambar untuk lihat detail bounding box + score

Kalau metric jelek (F1 < 0.7), kembali ke labeling, tambah anotasi pada
component yang sering salah, retrain.

## 7. Gate 2 — Promote ke produksi (5 menit)

Kalau metric sudah OK:

1. Halaman Gate 2 — review final metrics + sampel prediksi
2. Klik **Promote to Production** → API memanggil `ais model push`,
   weights di-push ke registry, edge nodes dapat webhook notify
3. Tunggu ~30 detik. Edge nodes akan auto-pull pada cycle berikutnya
   (max 60 detik).

## 8. Verifikasi di lantai produksi

1. Operator edge box jalankan satu PCB golden — harus inspeksi clean
2. Jalankan satu PCB known-bad (kalau ada) — harus catch defect
3. Kalau ada false fail, kembali ke step 6 dan analisis FP grid

## Bantuan saat stuck

- Klik tombol **?** di pojok kanan bawah → chat advisor (Gemma) yang
  paham state project Anda
- Pesan error muncul dalam bahasa Indonesia di toast — screenshot dan
  kirim ke `indusiaai@gmail.com` kalau perlu bantuan

## Yang TIDAK perlu Anda lakukan

- Edit YAML / config file — semua via UI
- SSH ke server — operator tidak butuh shell access
- Tulis kode Python / training script — itu dikelola backend
- Set up Git LFS / model registry — ops team yang handle

## Update password

Klik foto profil (kanan atas) → **Pengaturan akun** → **Ganti password**.
Logout dari semua device kalau ganti password karena curiga kebocoran.
