# 🚀 Quick Start Guide - Running Performance Analyzer

## 📦 Fichiers créés (Étape 1 complète)

Voici tous les fichiers de configuration que nous avons créés :

### Configuration principale
- ✅ `PROJECT_STRUCTURE.md` - Documentation de la structure
- ✅ `.gitignore` - Exclusions Git
- ✅ `.env.example` - Template variables d'environnement
- ✅ `requirements.txt` - Dépendances Python globales
- ✅ `requirements-dev.txt` - Dépendances développement
- ✅ `README.md` - Documentation projet (pour GitHub)
- ✅ `docker-compose.yml` - Orchestration Docker

### Streamlit
- ✅ `streamlit_app/Dockerfile` - Image Docker Streamlit
- ✅ `streamlit_app/requirements.txt` - Dépendances Streamlit
- ✅ `streamlit_app/.streamlit/config.toml` - Configuration Streamlit

### Airflow
- ✅ `airflow/requirements.txt` - Dépendances Airflow

---

## 🎯 Prochaines étapes

### Étape 1.2 : Créer la structure de dossiers

```bash
# Créer tous les dossiers nécessaires
mkdir -p airflow/dags
mkdir -p airflow/logs
mkdir -p airflow/plugins
mkdir -p dbt_project/models/{staging,intermediate,marts}
mkdir -p dbt_project/macros
mkdir -p dbt_project/tests
mkdir -p dbt_project/seeds
mkdir -p ingestion
mkdir -p ai_engine/prompts
mkdir -p ai_engine/rag
mkdir -p streamlit_app/pages
mkdir -p streamlit_app/components
mkdir -p streamlit_app/utils
mkdir -p data/duckdb
mkdir -p data/raw
mkdir -p data/exports
mkdir -p notebooks
mkdir -p tests
mkdir -p docs

# Créer des fichiers .gitkeep pour préserver les dossiers vides dans Git
touch airflow/logs/.gitkeep
touch data/raw/.gitkeep
touch data/exports/.gitkeep
```

### Étape 1.3 : Configurer l'environnement

```bash
# 1. Copier le template .env
cp .env.example .env

# 2. Éditer .env et remplir :
#    - GARMIN_EMAIL
#    - GARMIN_PASSWORD
#    - ANTHROPIC_API_KEY
#    - AIRFLOW_ADMIN_PASSWORD (changer "admin" par un vrai mot de passe)
nano .env  # ou vim .env, ou ton éditeur préféré

# 3. Générer une Fernet key pour Airflow
python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
# Copier le résultat dans .env → AIRFLOW_FERNET_KEY=...

# 4. Définir l'UID Airflow (Linux/Mac seulement)
echo -e "AIRFLOW_UID=$(id -u)" >> .env
```

### Étape 1.4 : Initialiser Git

```bash
# Initialiser le repo Git
git init

# Ajouter tous les fichiers de config
git add .
git commit -m "Initial commit: Project structure and configuration"

# (Optionnel) Créer le repo sur GitHub et pusher
# gh repo create running-performance-analyzer --public --source=. --remote=origin
# git push -u origin main
```

---

## 🐳 Étape 2 : Démarrer Docker (OPTIONNEL pour l'instant)

**Note** : On peut attendre d'avoir le code Python avant de démarrer Docker.
Mais si tu veux tester que tout fonctionne :

```bash
# Démarrer les services
docker-compose up -d

# Vérifier les logs d'initialisation
docker-compose logs -f airflow-init

# Attendre le message "Airflow initialization complete!"
# Puis Ctrl+C pour sortir des logs

# Vérifier que tous les services sont up
docker-compose ps

# Accéder aux UIs
# - Airflow : http://localhost:8080 (admin / ton_mot_de_passe)
# - Streamlit : http://localhost:8501 (va échouer car pas encore de code app.py)
```

**Si tu rencontres des problèmes Docker** :
```bash
# Arrêter tous les conteneurs
docker-compose down

# Nettoyer complètement (attention : supprime les données)
docker-compose down -v

# Redémarrer
docker-compose up -d
```

---

## 📝 Étape 3 : Développer le connecteur Garmin (NEXT!)

C'est ce qu'on va faire ensuite. On va créer :

1. `ingestion/garmin_connector.py` - Classe pour se connecter à l'API Garmin
2. `ingestion/utils.py` - Fonctions utilitaires
3. `tests/test_ingestion.py` - Tests du connecteur
4. `notebooks/01_garmin_api_testing.ipynb` - Notebook pour tester l'API

---

## 🗂️ Structure finale attendue

```
running-performance-analyzer/
├── .env                        # ✅ À créer (cp .env.example .env)
├── .env.example                # ✅ Créé
├── .gitignore                  # ✅ Créé
├── docker-compose.yml          # ✅ Créé
├── README.md                   # ✅ Créé
├── PROJECT_STRUCTURE.md        # ✅ Créé
├── requirements.txt            # ✅ Créé
├── requirements-dev.txt        # ✅ Créé
│
├── airflow/
│   ├── dags/                   # ⏳ À créer (vide pour l'instant)
│   ├── logs/                   # ⏳ À créer (.gitkeep)
│   ├── plugins/                # ⏳ À créer (vide)
│   └── requirements.txt        # ✅ Créé
│
├── dbt_project/
│   ├── models/
│   │   ├── staging/            # ⏳ À créer
│   │   ├── intermediate/       # ⏳ À créer
│   │   └── marts/              # ⏳ À créer
│   ├── macros/                 # ⏳ À créer
│   ├── tests/                  # ⏳ À créer
│   └── seeds/                  # ⏳ À créer
│
├── ingestion/                  # ⏳ PROCHAINE ÉTAPE
│   ├── __init__.py
│   ├── garmin_connector.py     # 🎯 Next!
│   └── utils.py
│
├── ai_engine/
│   ├── prompts/                # ⏳ À créer
│   └── rag/                    # ⏳ À créer
│
├── streamlit_app/
│   ├── .streamlit/
│   │   └── config.toml         # ✅ Créé
│   ├── Dockerfile              # ✅ Créé
│   ├── requirements.txt        # ✅ Créé
│   ├── pages/                  # ⏳ À créer
│   ├── components/             # ⏳ À créer
│   └── utils/                  # ⏳ À créer
│
├── data/
│   ├── duckdb/                 # ⏳ À créer
│   ├── raw/                    # ⏳ À créer (.gitkeep)
│   └── exports/                # ⏳ À créer (.gitkeep)
│
├── notebooks/                  # ⏳ À créer
├── tests/                      # ⏳ À créer
└── docs/                       # ⏳ À créer
```

---

## ✅ Checklist avant de continuer

- [ ] Tous les fichiers de config ont été téléchargés
- [ ] La structure de dossiers a été créée (`mkdir -p ...`)
- [ ] Le fichier `.env` a été créé et rempli
- [ ] Git a été initialisé et premier commit fait
- [ ] (Optionnel) Docker a été testé et fonctionne

---

## 🎓 Ce que ce setup démontre aux recruteurs

1. **Architecture moderne** : Docker, Airflow, dbt
2. **Bonnes pratiques** : 
   - Variables d'environnement sécurisées
   - .gitignore complet
   - Documentation exhaustive
   - Séparation dev/prod
3. **Reproductibilité** : N'importe qui peut cloner et lancer le projet
4. **Professionnalisme** : Structure claire, commentaires, README complet

---

## 🚀 Prêt pour l'étape 2 ?

Dis-moi quand tu as :
1. Créé la structure de dossiers
2. Configuré ton `.env`
3. (Optionnel) Testé Docker

Et on passera au **connecteur Garmin API** ! 🏃‍♂️

---

## 💡 Questions fréquentes

**Q: Dois-je obligatoirement utiliser Docker ?**
R: Pour l'instant non, tu peux développer en local. Docker est utile pour Airflow, mais on peut commencer par créer le code d'ingestion et le tester en Python pur.

**Q: Je n'ai pas de montre Garmin, puis-je quand même faire le projet ?**
R: Oui ! Tu peux :
- Utiliser des données Garmin de démonstration
- Te connecter à Strava (plus simple, OAuth)
- Importer un export Apple Health
- Générer des données fictives avec Faker

**Q: Je veux commencer par le code, pas Docker**
R: Parfait ! On va faire exactement ça. Prochaine étape = `garmin_connector.py`.

**Q: Combien de temps pour le MVP complet ?**
R: 
- MVP fonctionnel : 2-3 semaines (soirs/week-ends)
- Version "portfolio-ready" : 1-2 mois
- Version avancée (ML, RAG) : 3-6 mois
