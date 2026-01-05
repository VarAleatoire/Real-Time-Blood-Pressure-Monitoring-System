import json
import os
from datetime import datetime
from kafka import KafkaConsumer
from elasticsearch import Elasticsearch
import joblib
import os

MODEL_PATH = os.getenv("BP_MODEL_PATH", "bp_logreg.pkl")

try:
    ml_model = joblib.load(MODEL_PATH)
    print(f"✅ Modèle ML chargé: {MODEL_PATH}")
except Exception as e:
    ml_model = None
    print(f"⚠️ Modèle ML non chargé ({MODEL_PATH}) -> {e}")


TOPIC = "blood-pressure"
BOOTSTRAP_SERVERS = ["localhost:9092"]

ES_URL = "http://localhost:9200"
ES_INDEX = "bp-anomalies"

NORMAL_DIR = "normal_cases"
os.makedirs(NORMAL_DIR, exist_ok=True)

def ml_anomaly_probability(systolic: int | None, diastolic: int | None) -> float | None:
    """
    Retourne la probabilité 'anormal' (classe 1) selon la régression logistique.
    None si modèle non chargé ou données invalides.
    """
    if ml_model is None:
        return None
    if systolic is None or diastolic is None:
        return None

    proba = ml_model.predict_proba([[systolic, diastolic]])[0][1]
    return float(proba)


def extract_bp(fhir_obs: dict) -> tuple[int | None, int | None]:
    """Extrait systolic/diastolic depuis Observation.component."""
    systolic = None
    diastolic = None

    for comp in fhir_obs.get("component", []):
        coding = comp.get("code", {}).get("coding", []) or []
        code = coding[0].get("code") if coding else None
        value = comp.get("valueQuantity", {}).get("value")

        if code == "8480-6":  # systolic
            systolic = int(value) if value is not None else None
        elif code == "8462-4":  # diastolic
            diastolic = int(value) if value is not None else None

    return systolic, diastolic


def detect_anomaly(systolic: int | None, diastolic: int | None) -> tuple[bool, list[str]]:
    """
    Seuils du sujet :
    - systolique > 140 ou < 90
    - diastolique > 90 ou < 60
    """
    reasons = []

    if systolic is None or diastolic is None:
        return True, ["missing_values"]

    if systolic > 140:
        reasons.append("hypertension_systolic")
    if systolic < 90:
        reasons.append("hypotension_systolic")
    if diastolic > 90:
        reasons.append("hypertension_diastolic")
    if diastolic < 60:
        reasons.append("hypotension_diastolic")

    return (len(reasons) > 0), reasons


def classify_bp_category(systolic: int | None, diastolic: int | None) -> str:
    """
    Classification selon le tableau :
    - Normal: sys < 120 ET dia < 80
    - Elevated: sys 120-129 ET dia < 80
    - HTN Stage 1: sys 130-139 OU dia 80-89
    - HTN Stage 2: sys >= 140 OU dia >= 90
    - Hypertensive Crisis: sys > 180 OU dia > 120
    """
    if systolic is None or diastolic is None:
        return "unknown"

    # Crisis d'abord (priorité)
    if systolic > 180 or diastolic > 120:
        return "hypertensive_crisis"

    # Stage 2
    if systolic >= 140 or diastolic >= 90:
        return "hypertension_stage_2"

    # Stage 1
    if (130 <= systolic <= 139) or (80 <= diastolic <= 89):
        return "hypertension_stage_1"

    # Elevated
    if (120 <= systolic <= 129) and diastolic < 80:
        return "elevated"

    # Normal
    if systolic < 120 and diastolic < 80:
        return "normal"

    # Cas limites (rare), on garde une valeur sûre
    return "unknown"



def save_normal_locally(patient_id: str, obs: dict):
    ts = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
    path = os.path.join(NORMAL_DIR, f"patient_{patient_id}_{ts}.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obs, f, ensure_ascii=False, indent=2)
    print(f"[NORMAL] -> {path}")


def index_anomaly(es: Elasticsearch, patient_id: str, systolic: int, diastolic: int, reasons: list[str], obs: dict):
    bp_category = classify_bp_category(systolic, diastolic)
    ml_proba = ml_anomaly_probability(systolic, diastolic)



    doc = {
        "patient_id": patient_id,
        "bp_category": bp_category,
        "systolic_pressure": systolic,
        "diastolic_pressure": diastolic,
        "ml_anomaly_probability": ml_proba,
        "anomaly_type": reasons,
        "timestamp": obs.get("effectiveDateTime"),
        "raw_fhir": obs,
    }
    es.index(index=ES_INDEX, document=doc)
    print(f"[ANOMALY] -> patient={patient_id} SYS={systolic} DIA={diastolic} reasons={reasons}")


def main():
    es = Elasticsearch(ES_URL)

    consumer = KafkaConsumer(
        TOPIC,
        bootstrap_servers=BOOTSTRAP_SERVERS,
        value_deserializer=lambda v: json.loads(v.decode("utf-8")),
        key_deserializer=lambda k: k.decode("utf-8") if k else None,
        auto_offset_reset="latest",
        enable_auto_commit=True,
        group_id="bp-consumer",
    )

    print(f"Consumer démarré -> topic: {TOPIC}")
    for msg in consumer:
        obs = msg.value

        subj_ref = (obs.get("subject", {}) or {}).get("reference", "")
        patient_id = subj_ref.replace("Patient/", "") if subj_ref.startswith("Patient/") else (msg.key or "unknown")

        systolic, diastolic = extract_bp(obs)
        is_anomaly, reasons = detect_anomaly(systolic, diastolic)

        if is_anomaly:
            # si valeurs manquantes, on indexe quand même
            if systolic is None or diastolic is None:
                es.index(index=ES_INDEX, document={"patient_id": patient_id, "anomaly_type": reasons, "raw_fhir": obs})
                print(f"[ANOMALY] -> patient={patient_id} reasons={reasons}")
            else:
                index_anomaly(es, patient_id, systolic, diastolic, reasons, obs)
        else:
            save_normal_locally(patient_id, obs)


if __name__ == "__main__":
    main()
