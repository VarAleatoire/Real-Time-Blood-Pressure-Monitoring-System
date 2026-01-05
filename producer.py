import json
import time
import uuid
from datetime import datetime, timezone

from faker import Faker
from kafka import KafkaProducer

fake = Faker()

TOPIC = "blood-pressure"
BOOTSTRAP_SERVERS = ["localhost:9092"]

def build_fhir_observation(patient_id: str, systolic: int, diastolic: int) -> dict:
    now = datetime.now(timezone.utc).isoformat()
    obs_id = str(uuid.uuid4())

    return {
        "resourceType": "Observation",
        "id": obs_id,
        "status": "final",
        "category": [
            {
                "coding": [
                    {
                        "system": "http://terminology.hl7.org/CodeSystem/observation-category",
                        "code": "vital-signs",
                        "display": "Vital Signs",
                    }
                ]
            }
        ],
        "code": {
            "coding": [
                {
                    "system": "http://loinc.org",
                    "code": "85354-9",
                    "display": "Blood pressure panel",
                }
            ],
            "text": "Blood Pressure",
        },
        "subject": {"reference": f"Patient/{patient_id}"},
        "effectiveDateTime": now,
        "component": [
            {
                "code": {
                    "coding": [
                        {
                            "system": "http://loinc.org",
                            "code": "8480-6",
                            "display": "Systolic blood pressure",
                        }
                    ]
                },
                "valueQuantity": {
                    "value": systolic,
                    "unit": "mmHg",
                    "system": "http://unitsofmeasure.org",
                    "code": "mm[Hg]",
                },
            },
            {
                "code": {
                    "coding": [
                        {
                            "system": "http://loinc.org",
                            "code": "8462-4",
                            "display": "Diastolic blood pressure",
                        }
                    ]
                },
                "valueQuantity": {
                    "value": diastolic,
                    "unit": "mmHg",
                    "system": "http://unitsofmeasure.org",
                    "code": "mm[Hg]",
                },
            },
        ],
    }

def random_bp():
    systolic = fake.random_int(min=80, max=170)
    diastolic = fake.random_int(min=50, max=110)
    return systolic, diastolic

def main():
    producer = KafkaProducer(
        bootstrap_servers=BOOTSTRAP_SERVERS,
        value_serializer=lambda v: json.dumps(v).encode("utf-8"),
        key_serializer=lambda k: k.encode("utf-8"),
    )

    print("Producer démarré (topic: blood-pressure)")

    try:
        while True:
            patient_id = str(fake.random_int(min=1, max=50))
            systolic, diastolic = random_bp()

            message = build_fhir_observation(patient_id, systolic, diastolic)
            producer.send(TOPIC, key=patient_id, value=message)

            print(f"Envoyé -> Patient/{patient_id} | SYS={systolic} DIA={diastolic}")
            time.sleep(1)
    except KeyboardInterrupt:
        print("Arrêt du producer")
    finally:
        producer.flush()
        producer.close()

if __name__ == "__main__":
    main()
