# Neck Posture Detection With Ideal Screen-to-Eye Distance

Aplikasi desktop yang memantau postur leher dan jarak mata ke layar secara real-time lewat webcam, lalu memberi peringatan suara saat salah satunya menyimpang dari kondisi baik. Sangat dibutuhkan untuk pelajar dan pekerja yang lama duduk di depan layar.

## Fitur

- **Kalibrasi satu kali**: user duduk dengan postur baik pada jarak layar yang diinginkan, lalu menekan `C` untuk menjadikannya baseline. Semua deteksi berikutnya dibandingkan relatif terhadap baseline ini.
- **Deteksi postur leher**: menghitung rasio jarak telinga-ke-bahu dan sudut kemiringan kepala terhadap garis vertikal dari titik bahu, dibandingkan dengan baseline kalibrasi (lihat `engine.py`).
- **Estimasi jarak mata ke layar**: memanfaatkan lebar jarak antar-mata pada gambar (berbanding terbalik dengan jarak fisik) untuk memperkirakan jarak dalam cm, lalu mengkategorikannya sebagai ideal, terlalu dekat, atau terlalu jauh.
- **Smoothing & anti flip-flop**: rata-rata bergerak atas beberapa frame terakhir plus ambang jumlah frame beruntun (`flip_frames`) sebelum status postur/jarak benar-benar dianggap berubah, supaya status tidak berkedip karena noise satu frame.
- **Peringatan suara**: memainkan file mp3 berbeda saat status gabungan (postur + jarak) berubah dari baik menjadi buruk atau sebaliknya, dengan pilihan mematikan suara dari panel setting.
- **Panel setting interaktif**: slider untuk toleransi penurunan kepala, toleransi kemiringan kepala, jumlah frame respons, durasi sebelum peringatan, jarak ideal saat kalibrasi, serta ambang batas jarak terlalu dekat/terlalu jauh — semua berlaku langsung tanpa restart sesi.
- **Overlay visual pada video**: titik dan garis landmark wajah/bahu/telinga/mata, garis leher berwarna sesuai status, serta garis dan label jarak ke titik tengah layar.
- **Ringkasan sesi**: setelah menekan `Q` (finish), halaman statistik menampilkan donut chart persentase postur baik, durasi baik/buruk, jumlah & durasi episode postur buruk, rasio waktu jarak ideal/dekat/jauh, serta timeline postur sepanjang sesi.
- **Pengunduhan model otomatis**: model `pose_landmarker_lite.task` (MediaPipe BlazePose) otomatis diunduh ke folder `assets/` pada first run jika belum ada.

## Struktur project

```
.
├── main.py       # entry point, App shell, home page, argument CLI
├── engine.py     # PostureEngine: landmark, aturan postur leher, estimasi jarak, overlay
├── detection.py  # halaman live detection: loop kamera, video, chip status, panel setting
├── stats.py      # Settings, SessionStats, halaman ringkasan sesi
├── system.py     # pencarian aset, pengunduhan model, pemutar suara (SoundPlayer)
├── theme.py      # warna, font, dan widget kustom (DonutChart, SegmentBar, dll.)
├── assets/       # correct.mp3, windows-error.mp3, pose_landmarker_lite.task
├── pyproject.toml / uv.lock
└── requirements.txt
```

## Kebutuhan

- Python >= 3.13.5 (lihat `.python-version` / `pyproject.toml`)
- Webcam
- Dependency: `customtkinter`, `mediapipe`, `opencv-contrib-python` (lihat `pyproject.toml` / `requirements.txt`)

## Instalasi

### Cara utama: uv

```bash
uv sync
```

`uv` akan membuat virtual environment dan menginstal dependency sesuai `pyproject.toml` dan `uv.lock`.

### Fallback: pip + requirements.txt

Jika tidak menggunakan `uv`, buat virtual environment biasa lalu:

```bash
python -m venv .venv
.venv\Scripts\activate      # Windows
pip install -r requirements.txt
```

## Cara menjalankan

```bash
uv run main.py
```

Atau (setelah environment pip aktif):

```bash
python main.py
```

Opsi CLI yang tersedia:

```bash
uv run main.py --camera 1 --good-sound correct.mp3 --bad-sound windows-error.mp3
```

- `--camera` ialah indeks kamera (default `0`)
- `--good-sound` ialah path mp3 yang dimainkan saat status kembali baik (default `assets/correct.mp3`)
- `--bad-sound` ialah path mp3 yang dimainkan saat postur leher atau jarak menjadi buruk (default `assets/windows-error.mp3`)

Model pose landmarker akan otomatis diunduh ke `assets/pose_landmarker_lite.task` pada run pertama jika belum ada.

### Kontrol pada halaman deteksi

- `C` ialah kalibrasi (jadikan posisi saat ini sebagai baseline, mulai pencatatan statistik)
- `Q` ialah selesai (hentikan sesi, tampilkan halaman ringkasan)

## Hasil Pengujian

Berdasarkan pengujian akhir yang dilakukan tim:

- **7 dari 7 skenario uji** dinyatakan "Sesuai", mencakup: postur baik, postur buruk/menunduk, jarak terlalu dekat, jarak terlalu jauh, sesi pemantauan berkelanjutan, dan kalibrasi ulang pada jarak 60 cm.
- **Akurasi deteksi skenario: 100% (7/7)**.
- **Rata-rata galat estimasi jarak: ±1,7%** (contoh: estimasi vs jarak aktual meleset sekitar ±1 cm pada jarak kalibrasi 60 cm).
- Pada sesi monitoring 37 detik yang didemokan tim, tercatat **100% waktu terlacak sebagai postur baik** dengan **0 episode postur buruk**.

## Keterbatasan yang diketahui

- Kalibrasi awal masih bisa menghasilkan false-positive jika posisi badan user berubah signifikan dari saat kalibrasi dilakukan. User perlu menekan `C` lagi (kalibrasi ulang) setelah pindah posisi duduk secara signifikan.
