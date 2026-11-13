
import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from scipy.optimize import linprog, minimize
from io import BytesIO
import json
from pathlib import Path

# ==========================================
# KONFIGURASI APLIKASI
# ==========================================

st.set_page_config(
    page_title="GradaMix",
    page_icon="📊",
    layout="wide"
)

# Ukuran saringan awal berdasarkan contoh PDF
DEFAULT_SIEVES = [
    63.0, 37.5, 19.0, 9.5, 4.75,
    2.36, 1.18, 0.425, 0.075
]

# ==========================================
# PENYIMPANAN DATA PERMANEN
# ==========================================

# Data disimpan di folder "data" yang otomatis dibuat
# di dalam folder proyek GradaMix.
DATA_DIR = Path(__file__).resolve().parent / "data"
DATA_FILE = DATA_DIR / "gradamix_data.json"


def save_data_permanently(dataframe, number_of_fractions):
    """Menyimpan data gradasi agar tetap tersedia setelah aplikasi ditutup."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    payload = {
        "number_of_fractions": int(number_of_fractions),
        "data": dataframe.to_json(
            orient="records",
            force_ascii=False
        )
    }

    # Tulis ke file sementara terlebih dahulu agar file utama
    # tidak rusak jika proses penyimpanan terhenti.
    temp_file = DATA_FILE.with_suffix(".tmp")
    temp_file.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )
    temp_file.replace(DATA_FILE)


def load_data_permanently():
    """Membaca kembali data gradasi yang pernah disimpan."""
    if not DATA_FILE.exists():
        return None, None

    try:
        payload = json.loads(DATA_FILE.read_text(encoding="utf-8"))
        dataframe = pd.read_json(
            BytesIO(payload["data"].encode("utf-8")),
            orient="records"
        )
        number_of_fractions = int(payload["number_of_fractions"])
        return dataframe, number_of_fractions
    except Exception:
        return None, None


# ==========================================
# FUNGSI MEMBUAT DATA AWAL
# ==========================================

def create_template(number_of_fractions):

    data = {
        "Ukuran Saringan (mm)": DEFAULT_SIEVES,
        "Agregat A (%)": [None] * len(DEFAULT_SIEVES),
        "Agregat B (%)": [None] * len(DEFAULT_SIEVES)
    }

    if number_of_fractions == 3:
        data["Agregat C (%)"] = [None] * len(DEFAULT_SIEVES)

    data["Batas Bawah (%)"] = [None] * len(DEFAULT_SIEVES)
    data["Batas Atas (%)"] = [None] * len(DEFAULT_SIEVES)

    return pd.DataFrame(data)


# ==========================================
# TEMPLATE EXCEL
# ==========================================

def create_excel_template(number_of_fractions):

    df = create_template(number_of_fractions)

    output = BytesIO()

    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df.to_excel(
            writer,
            index=False,
            sheet_name="Data Gradasi"
        )

    output.seek(0)

    return output.getvalue()


# ==========================================
# VALIDASI DATA
# ==========================================

def validate_data(df, number_of_fractions):

    errors = []

    required_columns = [
        "Ukuran Saringan (mm)",
        "Agregat A (%)",
        "Agregat B (%)"
    ]

    if number_of_fractions == 3:
        required_columns.append("Agregat C (%)")

    required_columns += [
        "Batas Bawah (%)",
        "Batas Atas (%)"
    ]

    missing_columns = [
        col for col in required_columns
        if col not in df.columns
    ]

    if missing_columns:
        errors.append(
            "Kolom tidak ditemukan: "
            + ", ".join(missing_columns)
        )
        return errors, None

    data = df[required_columns].copy()

    # Mengubah data menjadi numerik
    for col in required_columns:
        data[col] = pd.to_numeric(
            data[col],
            errors="coerce"
        )

    # Memeriksa data kosong
    if data.isna().any().any():
        errors.append(
            "Masih terdapat data kosong atau bukan angka."
        )

    # Memeriksa ukuran saringan
    sieve = data["Ukuran Saringan (mm)"]

    if (sieve <= 0).any():
        errors.append(
            "Ukuran saringan harus lebih besar dari 0."
        )

    if sieve.duplicated().any():
        errors.append(
            "Ukuran saringan tidak boleh duplikat."
        )

    if not sieve.is_monotonic_decreasing:
        errors.append(
            "Urutan ukuran saringan harus dari terbesar ke terkecil."
        )

    # Memeriksa persentase
    percentage_columns = [
        col for col in required_columns
        if col != "Ukuran Saringan (mm)"
    ]

    for col in percentage_columns:
        if (
            (data[col] < 0) |
            (data[col] > 100)
        ).any():
            errors.append(
                f"{col} harus berada pada rentang 0 sampai 100."
            )

    # Batas bawah tidak boleh melebihi batas atas
    if (
        data["Batas Bawah (%)"] >
        data["Batas Atas (%)"]
    ).any():
        errors.append(
            "Batas bawah spesifikasi tidak boleh melebihi batas atas."
        )

    return errors, data


# ==========================================
# MEMUAT DATA TERSIMPAN SAAT APLIKASI DIBUKA
# ==========================================

if "gradamix_data" not in st.session_state:
    saved_data, saved_fractions = load_data_permanently()

    if saved_data is not None:
        st.session_state["gradamix_data"] = saved_data
        st.session_state["gradamix_fractions"] = saved_fractions


# ==========================================
# SIDEBAR
# ==========================================

with st.sidebar:

    st.title("GradaMix")

    st.caption(
        "Aggregate Gradation Mixing & Optimization"
    )

    st.divider()

    menu = st.radio(
        "MENU UTAMA",
        [
            "Dashboard",
            "Input Data",
            "Hasil Pencampuran",
            "Grafik Gradasi",
            "Analisis Grafis"
        ]
    )

    st.divider()

    st.caption("GradaMix Version 1.0")


# ==========================================
# DASHBOARD
# ==========================================

if menu == "Dashboard":

    st.title("GradaMix")

    st.subheader(
        "Aggregate Gradation Mixing & Optimization"
    )

    st.write(
        "Software analisis dan optimasi pencampuran "
        "gradasi agregat 2 dan 3 fraksi."
    )

    st.divider()

    st.header("Modul Pencampuran Agregat")

    col1, col2 = st.columns(2)

    with col1:
        st.subheader("2 Fraksi")
        st.write("Agregat kasar dan agregat halus.")

    with col2:
        st.subheader("3 Fraksi")
        st.write(
            "Agregat kasar, sedang, dan halus."
        )

    st.divider()

    st.success(
        "Silakan pilih menu Input Data untuk memulai."
    )


# ==========================================
# INPUT DATA
# ==========================================

elif menu == "Input Data":

    st.title("Input Data Gradasi Agregat")

    st.write(
        "Masukkan data hasil analisis saringan "
        "dan spesifikasi gradasi campuran."
    )

    st.divider()

    # Pilihan jumlah fraksi
    st.subheader("1. Pengaturan Pencampuran")

    saved_fraction_choice = st.session_state.get("gradamix_fractions", 2)
    fraction_index = 1 if saved_fraction_choice == 3 else 0

    number_of_fractions = st.radio(
        "Pilih jumlah fraksi agregat:",
        [2, 3],
        index=fraction_index,
        horizontal=True,
        key="number_of_fractions_choice"
    )

    if number_of_fractions == 2:
        st.info(
            "2 Fraksi: Agregat A (kasar) dan "
            "Agregat B (halus)."
        )
    else:
        st.info(
            "3 Fraksi: Agregat A (kasar), "
            "Agregat B (sedang), dan "
            "Agregat C (halus)."
        )

    st.divider()

    # Pilihan sumber data
    st.subheader("2. Metode Input Data")

    input_method = st.radio(
        "Pilih cara memasukkan data:",
        [
            "Input Manual",
            "Upload Excel"
        ],
        horizontal=True
    )

    st.divider()

    # ======================================
    # INPUT MANUAL
    # ======================================

    if input_method == "Input Manual":

        st.subheader("3. Data Analisis Saringan")

        st.write(
            "Masukkan persen lolos setiap fraksi berdasarkan hasil pengujian "
            "analisis saringan. Kamu juga bisa menyalin beberapa sel dari Excel "
            "lalu menempelkannya langsung ke tabel."
        )
        st.info(
            "Tips input: salin data dari Excel tanpa judul kolom, klik sel pertama "
            "pada tabel, lalu tekan Ctrl+V. Pastikan urutan saringan dari terbesar "
            "ke terkecil dan semua kolom persentase diisi angka 0–100."
        )

        # Jika sebelumnya sudah pernah menyimpan data dengan jumlah
        # fraksi yang sama, tampilkan kembali data tersebut di tabel.
        if (
            "gradamix_data" in st.session_state
            and st.session_state.get("gradamix_fractions") == number_of_fractions
        ):
            initial_df = st.session_state["gradamix_data"].copy()
        else:
            initial_df = create_template(number_of_fractions)

        edited_df = st.data_editor(
            initial_df,
            use_container_width=True,
            num_rows="dynamic",
            key=f"manual_data_{number_of_fractions}",
            column_config={
                "Ukuran Saringan (mm)": st.column_config.NumberColumn(
                    "Ukuran Saringan (mm)",
                    help="Diameter bukaan saringan dalam mm.",
                    min_value=0.001,
                    format="%.3f",
                    step=0.001
                ),
                **{
                    col: st.column_config.NumberColumn(
                        col,
                        help="Masukkan persentase lolos antara 0 sampai 100.",
                        min_value=0.0,
                        max_value=100.0,
                        step=0.1,
                        format="%.2f"
                    )
                    for col in initial_df.columns
                    if col != "Ukuran Saringan (mm)"
                }
            }
        )

        source_df = edited_df

        # AUTO-SAVE DRAFT:
        # Simpan perubahan tabel setiap kali Streamlit menjalankan ulang aplikasi.
        # Draft boleh belum lengkap agar isian tidak hilang saat browser di-refresh.
        has_input_values = edited_df.drop(
            columns=["Ukuran Saringan (mm)"], errors="ignore"
        ).notna().any().any()

        if has_input_values:
            try:
                save_data_permanently(edited_df, number_of_fractions)
                st.session_state["gradamix_data"] = edited_df.copy()
                st.session_state["gradamix_fractions"] = number_of_fractions
                st.caption("Auto-save aktif: perubahan data tersimpan sebagai draft.")
            except Exception as e:
                st.warning(f"Draft belum berhasil disimpan otomatis: {e}")

    # ======================================
    # UPLOAD EXCEL
    # ======================================

    else:

        st.subheader("3. Upload Data Excel")

        st.write(
            "Unduh template Excel, isi data analisis "
            "saringan, kemudian unggah kembali."
        )

        excel_template = create_excel_template(
            number_of_fractions
        )

        st.download_button(
            label="Download Template Excel",
            data=excel_template,
            file_name="Template_GradaMix.xlsx",
            mime=(
                "application/vnd.openxmlformats-officedocument."
                "spreadsheetml.sheet"
            )
        )

        uploaded_file = st.file_uploader(
            "Pilih file Excel",
            type=["xlsx"]
        )

        source_df = None

        if uploaded_file is not None:

            try:

                source_df = pd.read_excel(
                    uploaded_file,
                    sheet_name="Data Gradasi"
                )

                st.success(
                    "File Excel berhasil dibaca."
                )

                st.write("Pratinjau data:")

                st.dataframe(
                    source_df,
                    use_container_width=True
                )

                # Simpan juga file Excel yang berhasil diunggah sebagai draft.
                save_data_permanently(source_df, number_of_fractions)
                st.session_state["gradamix_data"] = source_df.copy()
                st.session_state["gradamix_fractions"] = number_of_fractions
                st.caption("File Excel tersimpan otomatis sebagai draft lokal.")

            except Exception as e:

                st.error(
                    f"Gagal membaca file Excel: {e}"
                )

    # ======================================
    # VALIDASI DAN SIMPAN
    # ======================================

    st.divider()

    st.subheader("4. Validasi dan Penyimpanan Data")
    st.caption(
        "Data draft disimpan otomatis saat tabel berubah. Tekan tombol di bawah "
        "untuk memvalidasi data sebelum digunakan dalam proses pencampuran."
    )

    if source_df is not None:

        if st.button(
            "Periksa dan Simpan Data",
            type="primary"
        ):

            errors, clean_data = validate_data(
                source_df,
                number_of_fractions
            )

            if errors:

                for error in errors:
                    st.error(error)

            else:

                st.session_state["gradamix_data"] = (
                    clean_data
                )

                st.session_state["gradamix_fractions"] = (
                    number_of_fractions
                )

                try:
                    save_data_permanently(
                        clean_data,
                        number_of_fractions
                    )
                    st.success(
                        "Data berhasil divalidasi dan disimpan permanen!"
                    )
                    st.caption(
                        "Data tersimpan di folder proyek GradaMix/data."
                    )
                except Exception as e:
                    st.error(
                        f"Data tersimpan selama sesi ini, tetapi gagal "
                        f"disimpan ke file lokal: {e}"
                    )

                st.write("Data siap untuk proses pencampuran:")

                st.dataframe(
                    clean_data,
                    use_container_width=True
                )

    else:

        st.info(
            "Masukkan data terlebih dahulu untuk "
            "melakukan validasi."
        )

    # Menampilkan data tersimpan
    if "gradamix_data" in st.session_state:

        st.divider()

        st.subheader("Data Tersimpan")

        st.dataframe(
            st.session_state["gradamix_data"],
            use_container_width=True
        )

        st.caption(
            "Jumlah fraksi tersimpan: "
            + str(st.session_state["gradamix_fractions"])
        )


# ==========================================
# HALAMAN HASIL PENCAMPURAN
# ==========================================


elif menu == "Hasil Pencampuran":

    st.title("Hasil Pencampuran")
    st.write("Perhitungan dan optimasi proporsi gradasi agregat.")

    # Mengambil data yang sudah tersimpan
    if "gradamix_data" not in st.session_state:
        st.warning("Silakan masukkan data agregat terlebih dahulu.")
        st.stop()

    df = st.session_state["gradamix_data"].copy()
    n = st.session_state["gradamix_fractions"]

    # Menentukan kolom berdasarkan jumlah fraksi
    fraction_cols = ["Agregat A (%)", "Agregat B (%)"]

    if n == 3:
        fraction_cols.append("Agregat C (%)")

    required_cols = (
        ["Ukuran Saringan (mm)"]
        + fraction_cols
        + ["Batas Bawah (%)", "Batas Atas (%)"]
    )

    missing_cols = [
        col for col in required_cols if col not in df.columns
    ]

    if missing_cols:
        st.error(f"Kolom data tidak ditemukan: {missing_cols}")
        st.stop()

    # Mengubah data menjadi numerik
    for col in required_cols:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    if df[required_cols].isna().any().any():
        st.warning("Masih terdapat data kosong atau tidak valid.")
        st.stop()

    X = df[fraction_cols].to_numpy(dtype=float)
    lower = df["Batas Bawah (%)"].to_numpy(dtype=float)
    upper = df["Batas Atas (%)"].to_numpy(dtype=float)
    sieves = df["Ukuran Saringan (mm)"].to_numpy(dtype=float)

    if (
        not np.isfinite(X).all()
        or not np.isfinite(lower).all()
        or not np.isfinite(upper).all()
        or not np.isfinite(sieves).all()
    ):
        st.error("Data mengandung angka yang tidak valid.")
        st.stop()

    if (
        np.any(X < 0) or np.any(X > 100)
        or np.any(lower < 0) or np.any(upper > 100)
        or np.any(lower > upper)
    ):
        st.error("Periksa kembali nilai persen dan batas spesifikasi.")
        st.stop()

    st.divider()

    # =====================================
    # PILIH METODE PERHITUNGAN
    # =====================================

    st.subheader("1. Metode Penentuan Proporsi")

    mode = st.radio(
        "Pilih metode pencampuran:",
        ["Otomatis oleh Software", "Manual oleh Pengguna"],
        horizontal=True
    )

    proportions = None
    optimization_objective = None
    optimization_success = False
    target = (lower + upper) / 2
    width = np.maximum(upper - lower, 1.0)

    if mode == "Otomatis oleh Software":

        st.info(
            "GradaMix mencari proporsi yang memenuhi seluruh batas spesifikasi "
            "dan meminimalkan penyimpangan terhadap target gradasi tengah."
        )

        # Tahap 1: mencari satu solusi awal yang memenuhi semua batas.
        A_ub = np.vstack([X / 100.0, -X / 100.0])
        b_ub = np.concatenate([upper, -lower])

        feasibility = linprog(
            c=np.zeros(n),
            A_ub=A_ub,
            b_ub=b_ub,
            A_eq=np.ones((1, n)),
            b_eq=[100.0],
            bounds=[(0.0, 100.0)] * n,
            method="highs"
        )

        if not feasibility.success:
            st.error(
                "Tidak ditemukan kombinasi proporsi yang memenuhi seluruh "
                "batas spesifikasi. Periksa kembali data agregat dan batas gradasi."
            )
            if feasibility.message:
                st.caption(f"Keterangan solver: {feasibility.message}")

        else:
            # Tahap 2: optimasi kuadratik dengan beberapa titik awal.
            def objective(p):
                blend_candidate = X @ p / 100.0
                normalized_deviation = (blend_candidate - target) / width
                return float(np.sum(normalized_deviation ** 2))

            def objective_gradient(p):
                blend_candidate = X @ p / 100.0
                return (2.0 / 100.0) * (
                    X.T @ ((blend_candidate - target) / (width ** 2))
                )

            constraints = [
                {
                    "type": "eq",
                    "fun": lambda p: np.sum(p) - 100.0,
                    "jac": lambda p: np.ones(n)
                },
                {
                    "type": "ineq",
                    "fun": lambda p: (X @ p / 100.0) - lower,
                    "jac": lambda p: X / 100.0
                },
                {
                    "type": "ineq",
                    "fun": lambda p: upper - (X @ p / 100.0),
                    "jac": lambda p: -X / 100.0
                }
            ]

            # Beberapa titik awal diuji untuk mengurangi ketergantungan
            # terhadap satu tebakan awal.
            start_points = [feasibility.x, np.full(n, 100.0 / n)]
            for j in range(n):
                vertex = np.zeros(n)
                vertex[j] = 100.0
                start_points.append(vertex)

            valid_candidates = []
            solver_messages = []

            for start_point in start_points:
                trial = minimize(
                    objective,
                    start_point,
                    jac=objective_gradient,
                    method="SLSQP",
                    bounds=[(0.0, 100.0)] * n,
                    constraints=constraints,
                    options={"maxiter": 3000, "ftol": 1e-12, "disp": False}
                )
                solver_messages.append(trial.message)

                if trial.success and np.isfinite(trial.x).all():
                    trial_p = np.clip(trial.x, 0.0, 100.0)
                    trial_blend = X @ trial_p / 100.0
                    trial_feasible = (
                        abs(trial_p.sum() - 100.0) <= 1e-5
                        and np.all(trial_blend >= lower - 1e-5)
                        and np.all(trial_blend <= upper + 1e-5)
                    )
                    if trial_feasible:
                        valid_candidates.append(trial_p)

            if valid_candidates:
                candidate = min(valid_candidates, key=objective)
                proportions = candidate
                optimization_objective = objective(candidate)
                initial_objective = objective(feasibility.x)
                n_starts_tested = len(start_points)

                # Hessian fungsi kuadratik semidefinit positif
                # menunjukkan fungsi tujuan bersifat konveks.
                hessian = (2.0 / 10000.0) * (
                    X.T @ (X / (width ** 2)[:, None])
                )
                eigenvalues = np.linalg.eigvalsh(
                    (hessian + hessian.T) / 2.0
                )
                convex_model = bool(np.min(eigenvalues) >= -1e-9)

                candidate_blend = X @ candidate / 100.0
                final_feasible = (
                    abs(candidate.sum() - 100.0) <= 1e-5
                    and np.all(candidate_blend >= lower - 1e-5)
                    and np.all(candidate_blend <= upper + 1e-5)
                )
                optimization_success = final_feasible and convex_model

                if optimization_success:
                    st.success(
                        "Solver konvergen pada model optimasi konveks. "
                        "Solusi terpilih merupakan optimum numerik untuk "
                        "fungsi tujuan dan kendala yang digunakan."
                    )
                    st.caption(
                        "Pemeriksaan: beberapa titik awal diuji, solusi terpilih "
                        "memenuhi kendala, dan Hessian fungsi tujuan semidefinit positif."
                    )
                else:
                    st.warning(
                        "Kandidat ditemukan, tetapi pemeriksaan konveksitas atau "
                        "kendala belum lolos. Hasil belum dinyatakan optimum."
                    )
            else:
                proportions = feasibility.x
                st.warning(
                    "Belum ditemukan hasil optimasi yang lolos seluruh pemeriksaan. "
                    "Ditampilkan solusi layak awal; hasil ini belum dapat dinyatakan optimum."
                )
                st.caption("Pesan solver terakhir: " + str(solver_messages[-1]))

    else:

        st.info("Masukkan proporsi masing-masing agregat. Total harus 100%.")

        manual_values = []
        cols = st.columns(n)

        for i in range(n):
            with cols[i]:
                value = st.number_input(
                    fraction_cols[i],
                    min_value=0.0,
                    max_value=100.0,
                    value=100.0 / n,
                    step=1.0,
                    key=f"manual_proporsi_{i}"
                )
                manual_values.append(value)

        total = sum(manual_values)
        st.metric("Total Proporsi", f"{total:.2f}%")

        if abs(total - 100.0) <= 1e-6:
            proportions = np.array(manual_values, dtype=float)
        else:
            st.warning("Total proporsi harus tepat 100%.")

    # =====================================
    # HASIL PERHITUNGAN
    # =====================================

    if proportions is not None:

        st.divider()
        st.subheader("2. Hasil Proporsi Agregat")

        proportion_data = pd.DataFrame({
            "Nama Fraksi": [
                f"Agregat {chr(65 + i)}" for i in range(n)
            ],
            "Proporsi (%)": proportions
        })

        st.dataframe(
            proportion_data,
            use_container_width=True,
            hide_index=True
        )

        st.metric("Total Proporsi", f"{proportions.sum():.4f}%")

        # Menghitung persen lolos campuran.
        blend = X @ proportions / 100.0
        deviation = blend - target

        result_df = pd.DataFrame({
            "Ukuran Saringan (mm)": sieves,
            "Batas Bawah (%)": lower,
            "Target Tengah (%)": target,
            "Hasil Campuran (%)": blend,
            "Batas Atas (%)": upper,
            "Deviasi dari Target (%)": deviation
        })

        result_df["Status"] = np.where(
            (blend >= lower - 1e-6) & (blend <= upper + 1e-6),
            "Memenuhi",
            "Tidak Memenuhi"
        )

        st.divider()
        st.subheader("3. Hasil Gradasi Campuran")

        st.dataframe(
            result_df.round(4),
            use_container_width=True,
            hide_index=True
        )

        # =====================================
        # EVALUASI KESESUAIAN DAN OPTIMALITAS
        # =====================================

        st.divider()
        st.subheader("4. Evaluasi Kesesuaian")

        passed = (
            (blend >= lower - 1e-6)
            & (blend <= upper + 1e-6)
        )

        if passed.all():
            st.success("Seluruh ukuran saringan memenuhi spesifikasi.")
        else:
            st.error(
                f"{np.sum(~passed)} ukuran saringan belum memenuhi spesifikasi."
            )

        st.subheader("5. Grafik Bukti Kesesuaian Gradasi")
        fig, ax = plt.subplots(figsize=(10, 5))
        ax.fill_between(sieves, lower, upper, alpha=0.16,
                        label="Rentang spesifikasi")
        ax.plot(sieves, lower, marker=".", linestyle="--",
                label="Batas bawah")
        ax.plot(sieves, upper, marker=".", linestyle="--",
                label="Batas atas")
        ax.plot(sieves, target, marker="o", linewidth=2,
                label="Target tengah")
        ax.plot(sieves, blend, marker="s", linewidth=2,
                label="Hasil campuran")
        ax.set_xscale("log")
        ax.invert_xaxis()
        ax.set_ylim(0, 100)
        ax.set_xlabel("Ukuran saringan (mm)")
        ax.set_ylabel("Persen lolos (%)")
        ax.set_title("Kurva Gradasi Campuran terhadap Spesifikasi")
        ax.grid(True, which="both", alpha=0.25)
        ax.legend()
        fig.tight_layout()
        st.pyplot(fig, use_container_width=True)
        plt.close(fig)

        st.caption(
            "Kurva hasil campuran harus berada di antara batas bawah dan batas "
            "atas. Kedekatan terhadap target tengah menjadi dasar fungsi tujuan."
        )

        if mode == "Otomatis oleh Software" and optimization_success:
            st.subheader("6. Bukti dan Evaluasi Hasil Optimasi")

            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Nilai fungsi tujuan akhir",
                          f"{optimization_objective:.8f}")
            with col2:
                max_deviation = np.max(np.abs((blend - target) / width))
                st.metric("Deviasi ternormalisasi maksimum",
                          f"{max_deviation:.6f}")
            with col3:
                st.metric("Titik awal yang diuji", str(n_starts_tested))

            improvement = initial_objective - optimization_objective
            if initial_objective > 1e-12:
                improvement_pct = improvement / initial_objective * 100.0
                st.metric("Penurunan fungsi tujuan dari solusi awal",
                          f"{improvement_pct:.2f}%")
            else:
                st.caption(
                    "Solusi awal sudah memiliki nilai fungsi tujuan mendekati nol."
                )

            st.markdown("**Bagaimana GradaMix menentukan solusi optimum?**")
            st.write(
                "GradaMix meminimalkan jumlah kuadrat deviasi ternormalisasi "
                "antara persen lolos campuran dan target tengah spesifikasi, dengan ""D_i = max(U_i - L_i, 1) sebagai faktor normalisasi."
            )
            st.latex(
                r"\min Z=\sum_{i=1}^{n}"
                r"\left(\frac{P_i-T_i}{U_i-L_i}\right)^2"
            )
            st.write(
                "Kendalanya adalah hasil campuran berada di antara batas "
                "spesifikasi, total proporsi 100%, dan setiap proporsi berada "
                "pada rentang 0% sampai 100%."
            )
            st.success(
                "Kesimpulan: solusi terpilih memenuhi seluruh kendala dan "
                "merupakan optimum numerik pada model konveks yang digunakan."
            )
            st.caption(
                "Catatan: status ini merupakan bukti numerik komputasional "
                "berdasarkan konvergensi solver, pemeriksaan kelayakan, uji "
                "beberapa titik awal, dan sifat konveks model; bukan sertifikat "
                "eksak berbasis aritmetika simbolik."
            )

        elif mode == "Manual oleh Pengguna":
            st.caption(
                "Proporsi dimasukkan secara manual. Status di atas hanya "
                "menunjukkan kesesuaian terhadap spesifikasi, bukan hasil optimasi."
            )

        st.caption(
            "Hasil perhitungan bergantung pada data persen lolos agregat "
            "dan spesifikasi yang dimasukkan pengguna."
        )


# ==========================================
# HALAMAN GRAFIK
# ==========================================

elif menu == "Grafik Gradasi":

    st.title("Grafik Gradasi")
    st.write(
        "Simulasikan dan bandingkan beberapa kombinasi proporsi agregat "
        "dalam satu grafik."
    )

    if "gradamix_data" not in st.session_state:
        st.warning("Silakan masukkan dan simpan data gradasi terlebih dahulu.")
        st.stop()

    plot_df = st.session_state["gradamix_data"].copy()
    plot_n = int(st.session_state.get("gradamix_fractions", 2))
    fraction_cols_plot = ["Agregat A (%)", "Agregat B (%)"]
    if plot_n == 3:
        fraction_cols_plot.append("Agregat C (%)")

    plot_required = (
        ["Ukuran Saringan (mm)"] + fraction_cols_plot
        + ["Batas Bawah (%)", "Batas Atas (%)"]
    )
    missing_plot = [c for c in plot_required if c not in plot_df.columns]
    if missing_plot:
        st.error("Kolom data tidak ditemukan: " + ", ".join(missing_plot))
        st.stop()

    for col in plot_required:
        plot_df[col] = pd.to_numeric(plot_df[col], errors="coerce")
    plot_df = plot_df[plot_required].dropna().copy()
    if plot_df.empty:
        st.warning("Data gradasi belum lengkap. Lengkapi dan simpan data di menu Input Data.")
        st.stop()

    if (
        not np.isfinite(plot_df.to_numpy(dtype=float)).all()
        or (plot_df["Ukuran Saringan (mm)"] <= 0).any()
        or (plot_df[fraction_cols_plot + ["Batas Bawah (%)", "Batas Atas (%)"]] < 0).any().any()
        or (plot_df[fraction_cols_plot + ["Batas Bawah (%)", "Batas Atas (%)"]] > 100).any().any()
        or (plot_df["Batas Bawah (%)"] > plot_df["Batas Atas (%)"]).any()
    ):
        st.error("Periksa kembali data. Ukuran saringan harus positif, persentase 0–100, dan batas bawah tidak melebihi batas atas.")
        st.stop()

    plot_df = plot_df.sort_values("Ukuran Saringan (mm)", ascending=False)
    sieve_plot = plot_df["Ukuran Saringan (mm)"].to_numpy(dtype=float)
    aggregate_matrix = plot_df[fraction_cols_plot].to_numpy(dtype=float)
    lower_plot = plot_df["Batas Bawah (%)"].to_numpy(dtype=float)
    upper_plot = plot_df["Batas Atas (%)"].to_numpy(dtype=float)
    middle_plot = (lower_plot + upper_plot) / 2.0

    st.subheader(f"Simulasi Pencampuran {plot_n} Fraksi")
    st.caption(
        "Masukkan beberapa kombinasi proporsi. Setiap baris harus berjumlah "
        "100%. Kurva campuran dihitung dari rata-rata tertimbang persen lolos "
        "setiap fraksi."
    )

    # Template kombinasi awal: proporsi sama rata.
    combo_key = f"gradation_combinations_{plot_n}"
    if combo_key not in st.session_state:
        equal_share = round(100.0 / plot_n, 2)
        initial = {f"Agregat {chr(65+i)} (%)": equal_share for i in range(plot_n)}
        initial["Nama Kombinasi"] = "Kombinasi 1"
        st.session_state[combo_key] = pd.DataFrame([initial])

    combo_df = st.session_state[combo_key].copy()
    # Pastikan kolom mengikuti jumlah fraksi aktif.
    for col in [f"Agregat {chr(65+i)} (%)" for i in range(plot_n)]:
        if col not in combo_df.columns:
            combo_df[col] = 0.0
    combo_columns = ["Nama Kombinasi"] + [f"Agregat {chr(65+i)} (%)" for i in range(plot_n)]
    combo_df = combo_df[combo_columns]

    edited_combos = st.data_editor(
        combo_df,
        num_rows="dynamic",
        use_container_width=True,
        hide_index=True,
        key=f"gradation_editor_{plot_n}",
        column_config={
            "Nama Kombinasi": st.column_config.TextColumn("Nama Kombinasi", required=True),
            **{
                col: st.column_config.NumberColumn(
                    col, min_value=0.0, max_value=100.0, step=1.0, format="%.2f"
                )
                for col in combo_columns[1:]
            },
        },
    )

    st.caption("Tambahkan baris untuk mencoba kombinasi lain. Hapus baris yang tidak ingin dibandingkan.")
    show_aggregate_curves = st.checkbox("Tampilkan kurva masing-masing agregat", value=True)
    show_specification = st.checkbox("Tampilkan batas spesifikasi dan gradasi tengah", value=True)

    valid_combos = []
    invalid_rows = []
    for idx, row in edited_combos.iterrows():
        values = np.array([row[c] for c in combo_columns[1:]], dtype=float)
        total = float(np.sum(values))
        name = str(row["Nama Kombinasi"]).strip() or f"Kombinasi {idx+1}"
        if not np.isfinite(values).all() or np.any(values < 0) or np.any(values > 100):
            invalid_rows.append((idx, "Proporsi harus berupa angka 0–100%."))
        elif abs(total - 100.0) > 1e-6:
            invalid_rows.append((idx, f"Total proporsi {total:.2f}%, harus 100%."))
        else:
            blend_values = aggregate_matrix @ values / 100.0
            passed_rows = (blend_values >= lower_plot - 1e-6) & (blend_values <= upper_plot + 1e-6)
            valid_combos.append({
                "name": name,
                "values": values,
                "blend": blend_values,
                "passed": passed_rows,
                "pass_count": int(np.sum(passed_rows)),
                "all_pass": bool(np.all(passed_rows)),
                "mean_abs_deviation": float(np.mean(np.abs(blend_values - middle_plot))),
            })

    if invalid_rows:
        for idx, message in invalid_rows:
            st.warning(f"Baris {idx+1}: {message}")

    if not valid_combos:
        st.info("Belum ada kombinasi proporsi yang valid. Atur setiap baris hingga totalnya tepat 100%.")
        st.stop()

    st.subheader("Perbandingan Kurva Gradasi")
    fig, ax = plt.subplots(figsize=(11, 6))

    if show_specification:
        ax.fill_between(
            sieve_plot, lower_plot, upper_plot,
            alpha=0.12, color="gray", label="Rentang spesifikasi"
        )
        ax.plot(sieve_plot, lower_plot, linestyle="--", linewidth=1.2, label="Batas bawah")
        ax.plot(sieve_plot, upper_plot, linestyle="--", linewidth=1.2, label="Batas atas")
        ax.plot(sieve_plot, middle_plot, linestyle=":", linewidth=1.8, label="Gradasi tengah")

    if show_aggregate_curves:
        for j, col in enumerate(fraction_cols_plot):
            ax.plot(
                sieve_plot, aggregate_matrix[:, j],
                marker=".", linestyle="-", alpha=0.65,
                label=col.replace(" (%)", "")
            )

    for combo in valid_combos:
        prop_label = " / ".join(
            f"{chr(65+i)} {value:.1f}%"
            for i, value in enumerate(combo["values"])
        )
        ax.plot(
            sieve_plot, combo["blend"], marker="o", linewidth=2,
            label=f"{combo['name']} ({prop_label})"
        )

    ax.set_xscale("log")
    ax.invert_xaxis()
    ax.set_ylim(0, 100)
    ax.set_xlabel("Ukuran Saringan (mm) — skala logaritmik")
    ax.set_ylabel("Persen Lolos (%)")
    ax.set_title(f"Perbandingan Gradasi Campuran — {plot_n} Fraksi")
    ax.grid(True, which="both", alpha=0.25)
    ax.legend(loc="best", fontsize=8)
    fig.tight_layout()
    st.pyplot(fig, use_container_width=True)
    plt.close(fig)

    st.subheader("Ringkasan Hasil Simulasi")
    summary_rows = []
    detail_frames = []
    for combo in valid_combos:
        prop_text = ", ".join(
            f"{chr(65+i)}={v:.2f}%"
            for i, v in enumerate(combo["values"])
        )
        summary_rows.append({
            "Kombinasi": combo["name"],
            "Proporsi": prop_text,
            "Saringan Memenuhi": f"{combo['pass_count']} dari {len(sieve_plot)}",
            "Status": "Memenuhi seluruh spesifikasi" if combo["all_pass"] else "Belum memenuhi seluruh spesifikasi",
            "Rata-rata |deviasi| dari tengah (%)": combo["mean_abs_deviation"],
        })
        detail = pd.DataFrame({
            "Kombinasi": combo["name"],
            "Ukuran Saringan (mm)": sieve_plot,
            "Hasil Campuran (%)": combo["blend"],
            "Batas Bawah (%)": lower_plot,
            "Batas Atas (%)": upper_plot,
            "Gradasi Tengah (%)": middle_plot,
            "Status": np.where(combo["passed"], "Memenuhi", "Tidak Memenuhi"),
        })
        detail_frames.append(detail)

    summary_df = pd.DataFrame(summary_rows)
    st.dataframe(summary_df.round(3), use_container_width=True, hide_index=True)

    with st.expander("Lihat detail persen lolos setiap kombinasi"):
        st.dataframe(
            pd.concat(detail_frames, ignore_index=True).round(3),
            use_container_width=True,
            hide_index=True
        )

    st.caption(
        "Rumus campuran: persen lolos campuran = jumlah (persen lolos tiap fraksi × proporsi fraksi) / 100. "
        "Modul ini untuk simulasi dan perbandingan proporsi; penentuan proporsi dengan metode grafis "
        "tetap tersedia pada menu Analisis Grafis."
    )


# ==========================================
# ANALISIS GRAFIS
# ==========================================

elif menu == "Analisis Grafis":

    st.title("Analisis Metode Grafis")
    st.write(
        "Penentuan proporsi pencampuran agregat menggunakan metode grafis "
        "sesuai materi perkuliahan."
    )

    if "gradamix_data" not in st.session_state:
        st.warning("Silakan masukkan dan simpan data gradasi terlebih dahulu.")
        st.stop()

    graph_df = st.session_state["gradamix_data"].copy()
    graph_n = st.session_state.get("gradamix_fractions", 2)

    if graph_n not in (2, 3):
        st.error("Jumlah fraksi tidak dikenali. Pilih 2 atau 3 fraksi pada Input Data.")
        st.stop()

    graph_fraction_cols = ["Agregat A (%)", "Agregat B (%)"]
    if graph_n == 3:
        graph_fraction_cols.append("Agregat C (%)")

    graph_required = (
        ["Ukuran Saringan (mm)"] + graph_fraction_cols
        + ["Batas Bawah (%)", "Batas Atas (%)"]
    )
    graph_missing = [c for c in graph_required if c not in graph_df.columns]
    if graph_missing:
        st.error("Kolom data tidak ditemukan: " + ", ".join(graph_missing))
        st.stop()

    for col in graph_required:
        graph_df[col] = pd.to_numeric(graph_df[col], errors="coerce")
    graph_df = graph_df[graph_required].dropna().copy()

    if len(graph_df) == 0:
        st.warning("Belum ada data lengkap untuk dibuat grafik.")
        st.stop()

    if (
        not np.isfinite(graph_df.to_numpy(dtype=float)).all()
        or (graph_df["Ukuran Saringan (mm)"] <= 0).any()
        or (graph_df[["Agregat A (%)", "Agregat B (%)", "Batas Bawah (%)", "Batas Atas (%)"]] < 0).any().any()
        or (graph_df[["Agregat A (%)", "Agregat B (%)", "Batas Bawah (%)", "Batas Atas (%)"]] > 100).any().any()
        or (graph_df["Batas Bawah (%)"] > graph_df["Batas Atas (%)"]).any()
    ):
        st.error("Periksa kembali data. Persentase harus 0–100 dan batas bawah tidak boleh melebihi batas atas.")
        st.stop()

    graph_df = graph_df.sort_values("Ukuran Saringan (mm)", ascending=False)
    sieves_g = graph_df["Ukuran Saringan (mm)"].to_numpy(dtype=float)
    aggregate_graph = graph_df[graph_fraction_cols].to_numpy(dtype=float)
    lower_g = graph_df["Batas Bawah (%)"].to_numpy(dtype=float)
    upper_g = graph_df["Batas Atas (%)"].to_numpy(dtype=float)

    if graph_n == 3:
        st.subheader("Metode Rothfuchs Pencampuran 3 Fraksi")
        st.info(
            "Pilih Rothfuchs Tipe A atau Rothfuchs Tipe B. Grafik Tipe A "
            "mengikuti diagram konstruksi vertikal pada materi: sumbu horizontal "
            "menunjukkan urutan/nomor saringan, sumbu vertikal menunjukkan persen "
            "lolos, dan garis diagonal menjadi garis gradasi tengah acuan."
        )

        method_3 = st.radio(
            "Pilih metode grafis:",
            ["Rothfuchs Tipe A — Konstruksi garis vertikal",
             "Rothfuchs Tipe B — Pendekatan luas daerah"],
            horizontal=False,
            key="graph_3_method"
        )

        middle_g = (lower_g + upper_g) / 2.0

        # Untuk diagram Rothfuchs, urutan saringan ditampilkan dari halus
        # (kiri) ke kasar (kanan), seperti contoh pada materi.
        order = np.argsort(sieves_g)
        sieve_plot = sieves_g[order]
        agg_plot = aggregate_graph[order, :]
        middle_plot = middle_g[order]
        lower_plot = lower_g[order]
        upper_plot = upper_g[order]
        x_plot = np.linspace(0.0, 1.0, len(sieve_plot))

        def crossing_position(values, target=100.0):
            """Cari posisi x saat kurva interpolasi memotong nilai target."""
            values = np.asarray(values, dtype=float)
            diff = values - target
            for k in range(len(diff) - 1):
                if abs(diff[k]) <= 1e-10:
                    return float(x_plot[k])
                if diff[k] * diff[k + 1] < 0:
                    ratio = -diff[k] / (diff[k + 1] - diff[k])
                    return float(x_plot[k] + ratio * (x_plot[k + 1] - x_plot[k]))
            if abs(diff[-1]) <= 1e-10:
                return float(x_plot[-1])
            return None

        # Interpretasi konstruksi Tipe A berdasarkan uraian materi:
        # kasar: jarak bawah-ke-kurva A = jarak atas-ke-kurva B
        #        -> A + B = 100.
        # halus: jarak atas-ke-kurva C = jarak bawah-ke-A + bawah-ke-B
        #        -> A + B + C = 100.
        # Nilai proporsi dibaca pada garis diagonal acuan y = 100*x.
        x_coarse = crossing_position(agg_plot[:, 0] + agg_plot[:, 1])
        x_fine = crossing_position(agg_plot[:, 0] + agg_plot[:, 1] + agg_plot[:, 2])
        p_a_graph = 100.0 * x_coarse if x_coarse is not None else None
        p_c_graph = 100.0 * x_fine if x_fine is not None else None
        p_b_graph = (100.0 - p_a_graph - p_c_graph
                     if p_a_graph is not None and p_c_graph is not None else None)
        auto_a_valid = (p_b_graph is not None and p_b_graph >= 0
                        and p_a_graph >= 0 and p_c_graph >= 0)

        fig, ax = plt.subplots(figsize=(12, 6.5))
        if method_3.startswith("Rothfuchs Tipe A"):
            ax.fill_between(x_plot, lower_plot, upper_plot, color="gray", alpha=0.12,
                            label="Rentang spesifikasi")
            ax.plot(x_plot, lower_plot, "--", linewidth=1.0, label="Batas bawah")
            ax.plot(x_plot, upper_plot, "--", linewidth=1.0, label="Batas atas")
            ax.plot(x_plot, middle_plot, color="green", linestyle=":", linewidth=2.2,
                    label="Gradasi tengah spesifikasi")
            colors = ["#d95f02", "#7570b3", "#1b9e77"]
            names = ["Agregat A — Kasar", "Agregat B — Sedang", "Agregat C — Halus"]
            for j in range(3):
                ax.plot(x_plot, agg_plot[:, j], marker="o", linewidth=1.8,
                        color=colors[j], label=names[j])
            # Garis diagonal konstruksi dari sudut kiri bawah ke kanan atas.
            ax.plot([0, 1], [0, 100], color="#1684c7", linewidth=2.0,
                    label="Garis diagonal acuan Rothfuchs")
            if x_coarse is not None:
                ax.axvline(x_coarse, color="#d95f02", linestyle="--", linewidth=1.8)
                ax.scatter([x_coarse], [100*x_coarse], color="#d95f02", zorder=6)
                ax.annotate(f"A kasar = {p_a_graph:.1f}%", (x_coarse, 100*x_coarse),
                            xytext=(8, 12), textcoords="offset points", fontsize=9)
            if x_fine is not None:
                ax.axvline(x_fine, color="#1b9e77", linestyle="--", linewidth=1.8)
                ax.scatter([x_fine], [100*x_fine], color="#1b9e77", zorder=6)
                ax.annotate(f"C halus = {p_c_graph:.1f}%", (x_fine, 100*x_fine),
                            xytext=(8, -18), textcoords="offset points", fontsize=9)
            ax.set_title("Rothfuchs Tipe A — Diagram Pencampuran 3 Fraksi",
                         fontsize=14, fontweight="bold")
            ax.set_xlabel("Nomor / urutan saringan (halus → kasar)")
            ax.set_xticks(x_plot)
            ax.set_xticklabels([f"{v:g}" for v in sieve_plot], rotation=0)
            ax.set_xlim(0, 1)
            ax.set_ylim(0, 100)
            ax.text(1.01, 0.98, "Proporsi kasar", transform=ax.transAxes,
                    ha="left", va="top", fontsize=8)
            ax.grid(True, alpha=0.25)
            ax.legend(fontsize=8, loc="upper left")
        else:
            # Tipe B tetap memakai sumbu urutan saringan yang sama. Garis
            # konstruksi luas-area dijelaskan dan proporsinya dibaca pengguna.
            ax.fill_between(x_plot, lower_plot, upper_plot, color="gray", alpha=0.12,
                            label="Rentang spesifikasi")
            ax.plot(x_plot, lower_plot, "--", label="Batas bawah")
            ax.plot(x_plot, upper_plot, "--", label="Batas atas")
            ax.plot(x_plot, middle_plot, "g:", linewidth=2.2,
                    label="Gradasi tengah spesifikasi")
            colors = ["#d95f02", "#7570b3", "#1b9e77"]
            names = ["Agregat A — Kasar", "Agregat B — Sedang", "Agregat C — Halus"]
            for j in range(3):
                ax.plot(x_plot, agg_plot[:, j], marker="o", linewidth=1.8,
                        color=colors[j], label=names[j])
            ax.set_title("Rothfuchs Tipe B — Diagram Pencampuran 3 Fraksi",
                         fontsize=14, fontweight="bold")
            ax.set_xlabel("Nomor / urutan saringan (halus → kasar)")
            ax.set_xticks(x_plot)
            ax.set_xticklabels([f"{v:g}" for v in sieve_plot])
            ax.set_xlim(0, 1)
            ax.set_ylim(0, 100)
            ax.grid(True, alpha=0.25)
            ax.legend(fontsize=8, loc="upper left")

        ax.set_ylabel("Persen lolos (%)")
        fig.tight_layout()
        st.pyplot(fig, use_container_width=True)
        plt.close(fig)

        if method_3.startswith("Rothfuchs Tipe A"):
            st.markdown("### Langkah konstruksi Rothfuchs Tipe A")
            st.markdown(
                "1. Buat bidang diagram dengan perbandingan tinggi dan lebar 2:1.\n"
                "2. Sumbu horizontal menunjukkan nomor/ukuran saringan, sedangkan "
                "sumbu vertikal menunjukkan persen lolos 0–100%.\n"
                "3. Tarik garis diagonal dari sudut kiri bawah ke sudut kanan atas "
                "sebagai garis acuan proporsi.\n"
                "4. Tentukan garis vertikal agregat kasar dari kesetaraan jarak "
                "bawah-ke-kurva A dan atas-ke-kurva B.\n"
                "5. Tentukan garis vertikal agregat halus dari kesetaraan jarak "
                "atas-ke-kurva C dan jumlah jarak bawah-ke-kurva A serta B.\n"
                "6. Baca proporsi A dan C pada garis diagonal; proporsi B adalah "
                "100% dikurangi A dan C."
            )
            if auto_a_valid:
                st.success(
                    f"Pembacaan konstruksi Tipe A (interpolasi antar titik saringan): "
                    f"Agregat A/kasar = {p_a_graph:.2f}%, "
                    f"Agregat B/sedang = {p_b_graph:.2f}%, "
                    f"Agregat C/halus = {p_c_graph:.2f}%."
                )
                st.caption(
                    "Angka merupakan pembacaan numerik dari konstruksi pada data "
                    "yang dimasukkan; hasil gambar manual dapat sedikit berbeda "
                    "karena pembulatan dan skala gambar."
                )
            else:
                st.warning(
                    "Persilangan konstruksi Tipe A tidak ditemukan atau menghasilkan "
                    "proporsi negatif. Periksa urutan/karakteristik kurva agregat; "
                    "proporsi perlu dibaca manual dari diagram."
                )
        else:
            st.markdown("### Langkah konstruksi Rothfuchs Tipe B")
            st.markdown(
                "1. Tarik garis lurus untuk kurva gradasi setiap fraksi.\n"
                "2. Atur garis sehingga luas daerah di kiri dan kanan garis terhadap "
                "kurva fraksi kurang lebih sama.\n"
                "3. Hubungkan titik awal dan akhir garis-garis tersebut secara "
                "berurutan.\n"
                "4. Baca proporsi pada perpotongan garis penghubung dengan garis "
                "gradasi tengah spesifikasi."
            )
            st.warning(
                "Konstruksi keseimbangan luas Tipe B pada grafik ini masih perlu "
                "ditarik/dibaca secara grafis. Masukkan hasil pembacaan proporsi "
                "di bawah; jangan gunakan angka Tipe A sebagai hasil Tipe B."
            )

        st.subheader("Proporsi Hasil Pembacaan Rothfuchs")
        default_a = float(p_a_graph) if method_3.startswith("Rothfuchs Tipe A") and auto_a_valid else 33.0
        default_c = float(p_c_graph) if method_3.startswith("Rothfuchs Tipe A") and auto_a_valid else 33.0
        default_b = max(0.0, 100.0 - default_a - default_c) if method_3.startswith("Rothfuchs Tipe A") and auto_a_valid else 34.0
        pcols = st.columns(3)
        with pcols[0]:
            p_a = st.number_input("Agregat A / kasar (%)", 0.0, 100.0, value=default_a,
                                  step=0.1, key="graph3_prop_a_revised")
        with pcols[1]:
            p_b = st.number_input("Agregat B / sedang (%)", 0.0, 100.0, value=default_b,
                                  step=0.1, key="graph3_prop_b_revised")
        with pcols[2]:
            p_c = st.number_input("Agregat C / halus (%)", 0.0, 100.0, value=default_c,
                                  step=0.1, key="graph3_prop_c_revised")

        p3 = np.array([p_a, p_b, p_c], dtype=float)
        total3 = float(p3.sum())
        st.metric("Total proporsi", f"{total3:.2f}%")
        if abs(total3 - 100.0) > 1e-6:
            st.warning("Jumlah proporsi harus tepat 100% sebelum hasil campuran dihitung.")
        else:
            blend3 = aggregate_graph @ p3 / 100.0
            pass3 = (blend3 >= lower_g - 1e-6) & (blend3 <= upper_g + 1e-6)
            result3 = pd.DataFrame({
                "Ukuran Saringan (mm)": sieves_g,
                "Agregat A (%)": aggregate_graph[:, 0],
                "Agregat B (%)": aggregate_graph[:, 1],
                "Agregat C (%)": aggregate_graph[:, 2],
                "Hasil Campuran (%)": blend3,
                "Batas Bawah (%)": lower_g,
                "Batas Atas (%)": upper_g,
                "Status": np.where(pass3, "Memenuhi", "Tidak Memenuhi")
            })
            st.dataframe(result3.round(3), use_container_width=True, hide_index=True)
            if pass3.all():
                st.success("Proporsi hasil pembacaan grafis memenuhi seluruh batas spesifikasi.")
            else:
                st.warning(f"{int((~pass3).sum())} ukuran saringan belum memenuhi spesifikasi.")
            fig2, ax2 = plt.subplots(figsize=(10, 5))
            ax2.fill_between(sieves_g, lower_g, upper_g, alpha=0.12,
                             color="gray", label="Rentang spesifikasi")
            ax2.plot(sieves_g, middle_g, ":", linewidth=1.8, label="Gradasi tengah")
            ax2.plot(sieves_g, blend3, marker="s", linewidth=2.2,
                     label=f"Hasil campuran A={p_a:.1f}%, B={p_b:.1f}%, C={p_c:.1f}%")
            ax2.set_xscale("log")
            ax2.invert_xaxis()
            ax2.set_ylim(0, 100)
            ax2.set_xlabel("Ukuran saringan (mm)")
            ax2.set_ylabel("Persen lolos (%)")
            ax2.set_title("Hasil Campuran 3 Fraksi — Rothfuchs")
            ax2.grid(True, which="both", alpha=0.25)
            ax2.legend(fontsize=8)
            fig2.tight_layout()
            st.pyplot(fig2, use_container_width=True)
            plt.close(fig2)
        st.stop()

    agg_a = graph_df["Agregat A (%)"].to_numpy(dtype=float)
    agg_b = graph_df["Agregat B (%)"].to_numpy(dtype=float)

    st.subheader("Diagram Pencampuran 2 Fraksi")
    st.caption(
        "Sumbu bawah menunjukkan proporsi Agregat A (0–100%), sumbu atas "
        "menunjukkan proporsi Agregat B (100–0%). Sisi kiri menunjukkan "
        "% lolos Agregat B dan sisi kanan menunjukkan % lolos Agregat A."
    )

    # Setiap garis saringan menghubungkan % lolos Agregat B (kiri)
    # dengan % lolos Agregat A (kanan), sesuai konstruksi diagram pada materi.
    proportion_low = 0.0
    proportion_high = 100.0
    sieve_intervals = []
    intersection_points = []

    for sieve, a, b, lo, hi in zip(sieves_g, agg_a, agg_b, lower_g, upper_g):
        delta = a - b
        if abs(delta) < 1e-12:
            if not (lo - 1e-9 <= b <= hi + 1e-9):
                proportion_low, proportion_high = 1.0, 0.0
            p_lo, p_hi = 0.0, 100.0
        else:
            p1 = 100.0 * (lo - b) / delta
            p2 = 100.0 * (hi - b) / delta
            p_lo = max(0.0, min(p1, p2))
            p_hi = min(100.0, max(p1, p2))
            if max(p1, p2) < 0 or min(p1, p2) > 100:
                proportion_low, proportion_high = 1.0, 0.0
            else:
                proportion_low = max(proportion_low, p_lo)
                proportion_high = min(proportion_high, p_hi)

        sieve_intervals.append((sieve, p_lo, p_hi))
        for bound_name, bound in (("Batas bawah", lo), ("Batas atas", hi)):
            if abs(delta) >= 1e-12:
                p_cross = 100.0 * (bound - b) / delta
                if -1e-9 <= p_cross <= 100.0 + 1e-9:
                    intersection_points.append((p_cross, bound, sieve, bound_name))

    fig, ax = plt.subplots(figsize=(8, 8))
    ax.set_xlim(0, 100)
    ax.set_ylim(0, 100)
    ax.set_aspect("equal", adjustable="box")
    ax.set_xticks(np.arange(0, 101, 10))
    ax.set_yticks(np.arange(0, 101, 10))
    ax.grid(True, color="0.82", linewidth=0.7)

    # Rentang proporsi bersama seluruh ukuran saringan.
    feasible = proportion_low <= proportion_high
    if feasible:
        ax.axvspan(proportion_low, proportion_high, color="0.75", alpha=0.45,
                   label="Rentang proporsi yang memenuhi spesifikasi")
        ax.axvline(proportion_low, color="black", linestyle="--", linewidth=1.4)
        ax.axvline(proportion_high, color="black", linestyle="--", linewidth=1.4)
        midpoint = (proportion_low + proportion_high) / 2.0
        ax.axvline(midpoint, color="black", linestyle="-", linewidth=1.8,
                   label=f"Garis tengah = {midpoint:.2f}% A")
    else:
        midpoint = None

    for sieve, a, b in zip(sieves_g, agg_a, agg_b):
        ax.plot([0, 100], [b, a], linewidth=1.15, alpha=0.85)
        # Label ukuran saringan diletakkan di dekat titik tengah garis.
        ax.annotate(
            f"{sieve:g} mm", (50, (a + b) / 2), xytext=(3, 3),
            textcoords="offset points", fontsize=7, rotation=0
        )

    if intersection_points:
        px = [item[0] for item in intersection_points]
        py = [item[1] for item in intersection_points]
        ax.scatter(px, py, marker="x", s=38, color="black", linewidths=1.2,
                   label="Titik potong batas spesifikasi", zorder=5)

    ax.set_xlabel("Proporsi Agregat A (%)  →", labelpad=10)
    ax.set_ylabel("Persen lolos Agregat B (%)", labelpad=10)
    ax.set_title("Metode Grafis Pencampuran 2 Fraksi")

    # Skala atas untuk Agregat B dibaca dari 100% di kiri ke 0% di kanan.
    top_ax = ax.secondary_xaxis("top", functions=(lambda x: 100 - x, lambda x: 100 - x))
    top_ax.set_xlabel("Proporsi Agregat B (%)  (100% → 0%)", labelpad=9)
    top_ax.set_xticks(np.arange(0, 101, 10))

    # Skala kanan menunjukkan % lolos Agregat A.
    right_ax = ax.secondary_yaxis("right", functions=(lambda y: y, lambda y: y))
    right_ax.set_ylabel("Persen lolos Agregat A (%)", labelpad=10)
    right_ax.set_yticks(np.arange(0, 101, 10))

    ax.legend(loc="best", fontsize=8)
    fig.tight_layout()
    st.pyplot(fig, use_container_width=True)
    plt.close(fig)

    st.subheader("Pembacaan Proporsi dari Diagram")
    if feasible:
        st.success(
            f"Rentang proporsi yang memenuhi seluruh batas spesifikasi: "
            f"Agregat A = {proportion_low:.2f}–{proportion_high:.2f}% dan "
            f"Agregat B = {100-proportion_high:.2f}–{100-proportion_low:.2f}%."
        )
        st.metric("Garis tengah rentang proporsi", f"{midpoint:.2f}% A")
        st.caption(
            "Nilai garis tengah adalah titik tengah rentang proporsi bersama "
            "yang memenuhi semua ukuran saringan. Ini merupakan pembacaan "
            "geometris dari diagram, bukan hasil optimasi kuadratik pada menu Hasil Pencampuran."
        )
    else:
        st.error(
            "Tidak ditemukan rentang proporsi bersama yang memenuhi seluruh "
            "batas spesifikasi berdasarkan data yang dimasukkan. Periksa kembali "
            "data gradasi agregat dan batas spesifikasi."
        )

    with st.expander("Lihat rentang proporsi untuk setiap ukuran saringan"):
        interval_df = pd.DataFrame(
            sieve_intervals,
            columns=["Ukuran Saringan (mm)", "Batas proporsi A minimum (%)", "Batas proporsi A maksimum (%)"]
        )
        st.dataframe(interval_df.round(3), use_container_width=True, hide_index=True)


# ==========================================
# FOOTER
# ==========================================

st.divider()

st.caption(
    "GradaMix | Aggregate Gradation Mixing & Optimization Software"
)
