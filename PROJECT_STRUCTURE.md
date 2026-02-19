# Running Performance Analyzer - Structure du Projet

## Vue d'ensemble

Ce document décrit l'organisation complète du projet. Chaque dossier a un rôle spécifique dans l'architecture.

## Arborescence complète

```
running-performance-analyzer/
│
├── README.md                          # Documentation principale du projet
├── docker-compose.yml                 # Orchestration des services (Airflow, DuckDB)
├── .env.example                       # Variables d'environnement (à copier en .env)
├── .gitignore                         # Fichiers à exclure de Git
├── requirements.txt                   # Dépendances Python globales
│
├── airflow/                           # Orchestration des pipelines
│   ├── dags/                          # DAGs Airflow
│   │   ├── garmin_ingestion.py        # DAG ingestion Garmin
│   │   ├── strava_ingestion.py        # DAG ingestion Strava (optionnel)
│   │   └── dbt_orchestration.py       # DAG exécution dbt
│   ├── plugins/                       # Plugins custom Airflow
│   ├── logs/                          # Logs Airflow (généré auto)
│   └── requirements.txt               # Dépendances Airflow spécifiques
│
├── dbt_project/                       # Projet dbt (transformations SQL)
│   ├── dbt_project.yml                # Config dbt
│   ├── profiles.yml                   # Connexion DuckDB
│   ├── packages.yml                   # Packages dbt externes
│   ├── models/                        # Modèles SQL
│   │   ├── staging/                   # Silver layer - données nettoyées
│   │   │   ├── schema.yml             # Tests et documentation staging
│   │   │   ├── stg_garmin_activities.sql
│   │   │   └── stg_garmin_health.sql
│   │   ├── intermediate/              # Couche intermédiaire
│   │   │   ├── schema.yml
│   │   │   └── int_unified_activities.sql
│   │   └── marts/                     # Gold layer - données analytics
│   │       ├── schema.yml
│   │       ├── mart_training_analysis.sql
│   │       ├── mart_race_performance.sql
│   │       └── mart_health_trends.sql
│   ├── macros/                        # Fonctions SQL réutilisables
│   │   └── pace_conversion.sql
│   ├── tests/                         # Tests custom dbt
│   ├── seeds/                         # Données de référence (CSV)
│   │   └── race_goals.csv
│   └── target/                        # Compiled SQL (généré auto, git ignored)
│
├── ingestion/                         # Scripts d'ingestion API
│   ├── __init__.py
│   ├── garmin_connector.py            # Connecteur API Garmin
│   ├── strava_connector.py            # Connecteur API Strava (optionnel)
│   ├── apple_health_parser.py         # Parser Apple Health export (optionnel)
│   └── utils.py                       # Fonctions utilitaires communes
│
├── ai_engine/                         # Moteur IA / LLM
│   ├── __init__.py
│   ├── llm_analyzer.py                # Analyseur LLM principal
│   ├── prompts/                       # Prompts LLM
│   │   ├── training_recommendations.txt
│   │   ├── injury_prevention.txt
│   │   └── race_strategy.txt
│   └── rag/                           # RAG (optionnel, phase avancée)
│       ├── vector_store.py
│       └── running_knowledge_base/
│
├── streamlit_app/                     # Application web Streamlit
│   ├── 0_📊_Dashboard.py              # Page d'accueil (entry point)
│   ├── pages/                         # Pages multi-pages Streamlit
│   │   ├── 1_📊_Dashboard.py          # Vue d'ensemble performances
│   │   ├── 2_📈_Training_Analysis.py  # Analyses entraînements
│   │   ├── 3_🏃_Race_Performance.py   # Analyses courses
│   │   └── 4_🤖_AI_Coach.py           # Recommandations IA
│   ├── components/                    # Composants réutilisables
│   │   ├── __init__.py
│   │   ├── charts.py                  # Graphiques Plotly
│   │   ├── metrics.py                 # Cartes métriques
│   │   └── data_loader.py             # Chargement données DuckDB
│   ├── utils/                         # Utilitaires Streamlit
│   │   ├── __init__.py
│   │   ├── formatting.py              # Formatage allure, temps, etc.
│   │   └── constants.py               # Constantes (zones FC, etc.)
│   ├── .streamlit/                    # Config Streamlit
│   │   └── config.toml
│   └── requirements.txt               # Dépendances Streamlit
│
├── data/                              # Données locales
│   ├── duckdb/                        # Base de données DuckDB
│   │   └── running_analytics.duckdb   # Fichier DuckDB principal
│   ├── raw/                           # Données brutes temporaires (git ignored)
│   └── exports/                       # Exports CSV/Excel (git ignored)
│
├── notebooks/                         # Notebooks Jupyter exploration
│   ├── 01_data_exploration.ipynb
│   ├── 02_garmin_api_testing.ipynb
│   └── 03_ml_experiments.ipynb        # Phase ML future
│
├── tests/                             # Tests unitaires et intégration
│   ├── __init__.py
│   ├── test_ingestion.py              # Tests connecteurs API
│   ├── test_transformations.py        # Tests logique métier
│   └── test_ai_engine.py              # Tests LLM
│
└── docs/                              # Documentation projet
    ├── architecture.md                # Architecture détaillée
    ├── setup.md                       # Guide installation
    ├── api_garmin.md                  # Doc API Garmin
    └── deployment.md                  # Guide déploiement

```

## Rôle de chaque dossier

### `/airflow` - Orchestration

- **Objectif** : Automatiser l'ingestion quotidienne et l'exécution dbt
- **Technos** : Apache Airflow
- **Déploiement** : Docker container

### `/dbt_project` - Transformations données

- **Objectif** : Transformer données brutes (bronze) → analytics (gold)
- **Technos** : dbt-core, SQL
- **Connexion** : DuckDB

### `/ingestion` - Récupération données

- **Objectif** : Connecteurs API Garmin/Strava/Apple Health
- **Technos** : Python, requests, garminconnect library
- **Output** : Données brutes dans DuckDB

### `/ai_engine` - Intelligence artificielle

- **Objectif** : Analyse LLM, recommandations personnalisées
- **Technos** : LangChain, Claude API, embeddings
- **Input** : Données marts dbt

### `/streamlit_app` - Interface utilisateur

- **Objectif** : Dashboard web interactif
- **Technos** : Streamlit, Plotly, Pandas
- **Connexion** : Lecture DuckDB

### `/data` - Stockage local

- **Objectif** : Base de données DuckDB, fichiers temporaires
- **Important** : `.duckdb` versionné, `/raw` et `/exports` ignorés

### `/notebooks` - Exploration

- **Objectif** : Analyses exploratoires, tests API, expérimentations ML
- **Technos** : Jupyter, Pandas, Plotly

### `/tests` - Qualité code

- **Objectif** : Tests automatisés (pytest)
- **Coverage** : Ingestion, transformations, AI

## Fichiers racine importants

| Fichier              | Rôle                                        |
| -------------------- | ------------------------------------------- |
| `docker-compose.yml` | Définition services (Airflow, volumes)      |
| `requirements.txt`   | Dépendances Python globales                 |
| `.env`               | Variables d'environnement (credentials API) |
| `.gitignore`         | Exclusions Git (credentials, data brute)    |
| `README.md`          | Documentation principale du projet          |

## Flux de données

```
1. INGESTION (Airflow)
   Garmin API → garmin_connector.py → DuckDB (raw_garmin_activities)

2. TRANSFORMATION (dbt)
   raw_* → staging → intermediate → marts

3. ANALYTICS (Streamlit)
   marts → Pandas → Plotly charts

4. AI (LLM)
   marts → llm_analyzer.py → Recommandations
```

## Prochaines étapes

1. ✅ Créer cette structure de dossiers
2. ⏳ Configurer `docker-compose.yml`
3. ⏳ Setup `.env` et `.gitignore`
4. ⏳ Créer `requirements.txt`
5. ⏳ Initialiser DuckDB
6. ⏳ Développer `garmin_connector.py`
7. ⏳ Créer premiers modèles dbt
8. ⏳ Développer dashboard Streamlit
9. ⏳ Configurer Airflow DAGs
10. ⏳ Intégrer LLM

---

**Note** : Cette structure est évolutive. On commence par le MVP (Garmin + dbt + Streamlit), puis on enrichit (Strava, ML, RAG, etc.).
