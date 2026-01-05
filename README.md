# Real-Time-Blood-Pressure-Monitoring-System

#### Kafka · Python · FHIR · Elasticsearch · Kibana · Machine Learning

## 1. Problématique & Vision système

La surveillance continue de la pression artérielle est un cas d’usage critique en santé, caractérisé par :

- Des données événementielles à faible latence,

- Des règles médicales strictes,

- Une forte exigence de traçabilité,

- Un besoin de priorisation des cas à risque.

Ce projet implémente un pipeline de streaming temps réel pour la surveillance de la pression artérielle de patients.
Les données médicales sont produites au format FHIR, transmises via Kafka, analysées en temps réel, puis stockées selon leur criticité.

Les cas anormaux sont indexés dans Elasticsearch pour analyse et visualisation dans Kibana, tandis que les cas normaux sont archivés localement.

## 2. Architecture globale : 

<p align="center" width="100%">
    <img width="795" height="424" alt="Screenshot 2026-01-05 at 13 34 36" src="https://github.com/user-attachments/assets/c1a48647-2419-4d4d-a52b-4c2d058bdda8" />
</p>



Architecture de streaming temps réel basée sur Kafka, où des observations médicales FHIR sont produites, transmises et analysées en continu. Le consumer centralise le traitement en combinant parsing FHIR, règles cliniques et machine learning, puis oriente les données selon leur criticité. Les cas normaux sont archivés localement, tandis que les anomalies sont indexées dans Elasticsearch et visualisées dans Kibana pour le suivi et l’analyse.

## 3. Choix techniques :
|Composant        | Justification         
| ------------- |:-------------:| 
| FHIR Observation     | Standard médical réaliste pour le domaine healthcare | 
| Kafka      | Streaming scalable, découplage producer/consumer      |
| Python | Rapidité de prototypage + écosystème data      |
|Règles + ML         |Robustesse (seuils) + adaptabilité (probabilité) |
|Elasticsearch|Indexation rapide, analytics temps réel|
|Kibana|Observabilité, dashboards métier|


## 4. Structure de projet :

```
.
├── producer.py
├── consumer.py
├── train_model.py
├── kafka-docker-compose.yml
├── elastic-kibana-docker-compose.yml
├── normal_cases/
└── README.md
```

### 4.1. Ingestion des données (Producer Kafka) :

Responsabilités :

- Génération de mesures réalistes de pression artérielle via Faker

- Encapsulation dans une ressource FHIR Observation

- Publication continue sur Kafka (blood-pressure)

Caractéristiques clés :

- Respect strict des codes LOINC

- Clé Kafka = patient_id (partitionnement cohérent)

- Cadence maîtrisée (1 message / seconde)

Exemple de composant FHIR :
```
{
  "code": { "coding": [{ "code": "8480-6" }] },
  "valueQuantity": { "value": 135, "unit": "mmHg" }
}

```
### 4.2. Traitement en temps réel (Consumer Kafka) :
Le consumer est le cœur du pipeline.

### Étapes de traitement: 

#### 4.2.1. Désérialisation & Parsing FHIR :

- Extraction robuste de systolic / diastolic

- Tolérance aux données manquantes

#### 4.2.2. Détection par règles cliniques et classifications médicale

##### Règles cliniques : 

Seuils imposés :

- Systolique > 140 ou < 90

- Diastolique > 90 ou < 60

```
if systolic > 140:
    reasons.append("hypertension_systolic")
if diastolic < 60:
    reasons.append("hypotension_diastolic")
```

##### Classification médicale : 

```
if systolic >= 140 or diastolic >= 90:
    return "hypertension_stage_2"

```


### 4.3. Modèle Machine Learning (Régression logistique) :

Le modèle utilisé est une régression logistique, choisie pour sa simplicité, sa rapidité d’exécution et son interprétabilité, qualités essentielles dans un contexte médical. Les seules variables d’entrée sont la pression systolique et diastolique, ce qui garantit une latence minimale lors de l’inférence en temps réel.

Les labels d’entraînement sont générés à partir des seuils cliniques définis précédemment, assurant une parfaite cohérence entre la logique métier et l’apprentissage du modèle. Le jeu de données est synthétique et volontairement déséquilibré, avec une majorité de cas normaux, afin de refléter un scénario réaliste de surveillance médicale.

Une fois entraîné, le modèle est sérialisé dans un fichier ```bp_logreg.pkl```. Il est chargé dynamiquement par le consumer Kafka au démarrage et utilisé pour calculer, pour chaque observation, une probabilité d’anomalie. En cas d’absence du modèle, le pipeline continue de fonctionner uniquement sur la base des règles cliniques, garantissant la robustesse du système.

#### Entraînement :
```
model = LogisticRegression(max_iter=200)
model.fit(X, y)
joblib.dump(model, "bp_logreg.pkl")
```
#### Utilisation en temps réel :

``` proba = ml_model.predict_proba([[systolic, diastolic]])[0][1]```

##### NB : Le pipeline fonctionne même si le modèle est absent.


## 5. Routage et stockage :

##### Cas normaux : 

Stockage local JSON

```
json.dump(obs, f, indent=2)
```

##### Cas anormaux : 

Index Elasticsearch enrichi
```
es.index(
    index="bp-anomalies",
    document={
        "patient_id": patient_id,
        "bp_category": bp_category,
        "ml_anomaly_probability": ml_proba
    }
)
```

## 6. Visualisation Kibana : 

Les observations de pression artérielle identifiées comme anormales par le consumer Kafka sont indexées en temps réel dans Elasticsearch au sein d’un index dédié ```bp_anomalie*```. Cet index contient à la fois les mesures brutes, les catégories cliniques calculées et la probabilité d’anomalie issue du modèle de machine learning. Kibana est ensuite configuré pour se connecter à cet index et exploiter ces champs afin de construire des visualisations temporelles et agrégées, sans transformation supplémentaire des données.

<img width="1746" height="931" alt="Screenshot 2026-01-05 at 14 24 20" src="https://github.com/user-attachments/assets/676ee0f2-a98e-42f4-a419-6cca180c6653" />



_Le tableau de bord permet de suivre en continu la répartition des catégories cliniques, d’observer l’évolution temporelle des anomalies et d’analyser le niveau de risque estimé par le modèle de machine learning. Il offre une vision synthétique de la charge clinique et met en évidence les périodes ou profils de patients nécessitant une attention médicale renforcée._


## 7. Déploiement :

Kafka :
``` docker-compose -f kafka-docker-compose.yml up -d ```

Elasticsearch + Kibana :
``` docker-compose -f elastic-kibana-docker-compose.yml up -d ```

Pipeline :

```
python train_model.py
python consumer.py
python producer.py
```

## 8. Conclusion

Ce projet démontre la mise en place complète d’un pipeline de streaming médical, combinant :

- Ingestion temps réel.

- Standard FHIR.

- Détection explicable.

- Machine learning embarqué.

- Observabilité via Elasticsearch et Kibana.


