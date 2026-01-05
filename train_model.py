import random
from sklearn.linear_model import LogisticRegression
import joblib


def rule_label(sys: int, dia: int) -> int:
    """
    Label supervisé demandé par la consigne (normal/anormal) basé sur les seuils cliniques.
    Ici on reprend une règle simple et cohérente :
    - normal si sys < 120 ET dia < 80
    - sinon anormal
    """
    return 0 if (sys < 120 and dia < 80) else 1


def generate_dataset(n: int = 3000):
    """
    Génère un dataset synthétique (SYS, DIA) + label y.
    On crée volontairement des cas normaux fréquents + quelques cas élevés/HTA pour apprendre une frontière.
    """
    X, y = [], []

    for _ in range(n):
        r = random.random()

        if r < 0.55:
            # plutôt normal
            sys = random.randint(90, 119)
            dia = random.randint(55, 79)
        elif r < 0.75:
            # elevated / limite
            sys = random.randint(120, 129)
            dia = random.randint(55, 79)
        elif r < 0.92:
            # hypertension
            sys = random.randint(130, 170)
            dia = random.randint(80, 110)
        else:
            # hypotension ou extrêmes (un peu)
            sys = random.randint(70, 95)
            dia = random.randint(40, 65)

        X.append([sys, dia])
        y.append(rule_label(sys, dia))

    return X, y


def main():
    X, y = generate_dataset(n=4000)

    model = LogisticRegression(max_iter=200)
    model.fit(X, y)

    joblib.dump(model, "bp_logreg.pkl")
    print("✅ Modèle entraîné et sauvegardé: bp_logreg.pkl")

    # Petit test rapide
    tests = [(115, 75), (128, 78), (150, 95), (85, 55)]
    for sys, dia in tests:
        proba = model.predict_proba([[sys, dia]])[0][1]
        pred = int(proba >= 0.5)
        print(f"Test SYS={sys} DIA={dia} -> proba_anormal={proba:.2f} pred={pred}")


if __name__ == "__main__":
    main()
