import numpy as np
import pandas as pd


OBSERVEN = ["data_quality_score", "tax_gap", "revenue", "de_ratio"]

WEIGHTS = {
    "data_quality_score": 0.15,
    "tax_gap":            0.40,
    "revenue":            0.20,
    "de_ratio":           0.25,
}

STEP_RECOMMENDATION = {
    0: {
        "label": "Aman",
        "step": "Tidak diperlukan tindakan khusus. Lanjutkan pemantauan rutin tahunan."
    },
    1: {
        "label": "Perhatian",
        "step": "Lakukan review dokumen laporan keuangan. Bandingkan tren 2 tahun terakhir."
    },
    2: {
        "label": "Waspada",
        "step": "Lakukan analisis mendalam pada komponen pajak dan struktur utang. "
                "Jadwalkan pemeriksaan dokumen pendukung."
    },
    3: {
        "label": "Critical - Perlu Investigasi",
        "step": "Eskalasi segera ke tim investigasi. Audit menyeluruh pada laporan pajak, "
                "tax gap, dan struktur DE ratio. Verifikasi keabsahan data sumber PDF."
    },
}



def load_data(filepath: str) -> pd.DataFrame:
    df = pd.read_csv(filepath)

    df["tax_gap"] = np.abs(
        pd.to_numeric(df["pajak_terutang"], errors="coerce") -
        pd.to_numeric(df["pajak_dibayar"],  errors="coerce")
    )

    for col in OBSERVEN:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    for col in OBSERVEN:
        median_val = df[col].median()
        df[col] = df[col].fillna(median_val)

    return df


def compute_zscore(df: pd.DataFrame) -> pd.DataFrame:
    """
    Z-score = (nilai - mean) / std
    Pakai absolute z-score — makin jauh dari mean = makin anomali
    """
    for col in OBSERVEN:
        mean = df[col].mean()
        std  = df[col].std()
        if std == 0:
            df[f"z_{col}"] = 0.0
        else:
            df[f"z_{col}"] = np.abs((df[col] - mean) / std)

    df["composite_score"] = sum(
        WEIGHTS[col] * df[f"z_{col}"] for col in OBSERVEN
    )

    return df

def assign_label_rbs(score: float, p25: float, p50: float, p75: float) -> int:
    """
    Label berdasarkan posisi composite score terhadap distribusi dataset:
      0 — Aman      : score < P25
      1 — Perhatian : P25 <= score < P50
      2 — Waspada   : P50 <= score < P75
      3 — Critical  : score >= P75
    """
    if score < p25:
        return 0
    elif score < p50:
        return 1
    elif score < p75:
        return 2
    else:
        return 3


def label_data(df: pd.DataFrame) -> tuple:
    p25 = df["composite_score"].quantile(0.25)
    p50 = df["composite_score"].quantile(0.50)
    p75 = df["composite_score"].quantile(0.75)

    df["risk_label"] = df["composite_score"].apply(
        lambda s: assign_label_rbs(s, p25, p50, p75)
    )

    return df, (p25, p50, p75)

def gaussian_pdf(x: float, mean: float, std: float) -> float:
    if std == 0:
        return 1.0 if x == mean else 1e-9
    exponent = -0.5 * ((x - mean) / std) ** 2
    return (1 / (std * np.sqrt(2 * np.pi))) * np.exp(exponent)


def train_naive_bayes(df: pd.DataFrame) -> dict:
    """
    Hitung prior dan likelihood per label dari data training.
    Return model berupa dict of stats per label.
    """
    z_cols = [f"z_{col}" for col in OBSERVEN]
    model = {}
    total = len(df)

    for label in sorted(df["risk_label"].unique()):
        subset = df[df["risk_label"] == label]
        model[label] = {
            "prior": len(subset) / total,
            "stats": {
                col: {
                    "mean": subset[col].mean(),
                    "std":  subset[col].std() if subset[col].std() > 0 else 1e-9
                }
                for col in z_cols
            }
        }

    return model


def predict_naive_bayes(model: dict, z_values: dict) -> int:
    """
    Prediksi label untuk satu observasi baru.
    z_values = {"z_data_quality_score": ..., "z_tax_gap": ..., dst}
    """
    best_label = -1
    best_score = -np.inf

    for label, params in model.items():
        # Log probability untuk hindari underflow
        log_prob = np.log(params["prior"])
        for col, val in z_values.items():
            mean = params["stats"][col]["mean"]
            std  = params["stats"][col]["std"]
            log_prob += np.log(gaussian_pdf(val, mean, std) + 1e-300)

        if log_prob > best_score:
            best_score = log_prob
            best_label = label

    return best_label

def get_recommendation(row: pd.Series, model: dict) -> dict:
    z_values = {f"z_{col}": row[f"z_{col}"] for col in OBSERVEN}
 
    label_rbs = int(row["risk_label"])
    label_nb  = predict_naive_bayes(model, z_values)
 
    final_label = max(label_rbs, label_nb)
 
    rec = STEP_RECOMMENDATION[final_label]
 
    return {
        "code":            str(row["code"]),
        "name":            str(row["name"]),
        "year":            int(row["year"]),
        "composite_score": float(round(row["composite_score"], 4)),
        "label_rbs":       int(label_rbs),
        "label_nb":        int(label_nb),
        "final_label":     int(final_label),
        "status":          rec["label"],
        "recommendation":  rec["step"],
    }
