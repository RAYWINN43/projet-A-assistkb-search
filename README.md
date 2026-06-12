# projet-A-assistkb-search

> **MEMBRES DU GROUPE :**
> - **BLAIN Antoine**
> - **PECONTAL Corentin**
> - **MARTIN Evan**

Depot GitHub : https://github.com/RAYWINN43/projet-A-assistkb-search

---

## 1. Presentation du Projet

Angle : un assistant de recherche/reponse sur une base de connaissances, centre sur la qualite du retrieval. Vector store : Qdrant. L'enjeu : repondre juste, citer les bonnes sources, et refuser proprement quand la reponse n'est pas dans le corpus.

Contexte fil rouge : c'est la brique de recherche d'AssistKB-Neosoft. Un consultant pose une question, l'assistant retrouve les bons passages et repond en citant ses sources. Si l'info n'existe pas, il doit le dire, pas inventer.

## Docker

Copier la configuration d'environnement puis renseigner la cle Groq :

```bash
cp .env.example .env
```

Dans `.env`, renseigner `GROQ_API_KEY` et garder un modele Groq valide, par exemple `GROQ_MODEL=llama-3.3-70b-versatile`.

Demarrer Qdrant et l'API :

```bash
docker compose up --build
```

Apres un changement de dependances Python, reconstruire l'image API :

```bash
docker compose build --no-cache api
```

Indexer le corpus depuis les conteneurs :

```bash
docker compose up -d qdrant 
docker compose run --rm api python -m app.ingest
docker compose run --rm api python -m app.embed
docker compose up -d api
docker exec assistkb-api grep -A 3 "def root" /app/app/api.py
```
Verifier que l'API voit la configuration Groq :

```bash
curl http://localhost:8000/health
```

Test de L'api :

```bash
curl http://localhost:8000
```

En cas d'erreur API, lire les logs :

```bash
docker compose logs api --tail=80
```
