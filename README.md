# projet-A-assistkb-search

> **MEMBRES DU GROUPE :**
> - **BLAIN Antoine**
> - **PECONTAL Corentin** 
> - **MARTIN Evan**

Dépôt GitHub : https://github.com/RAYWINN43/projet-A-assistkb-search

---

## 1. Présentation du Projet
Angle : un assistant de recherche/reponse sur une base de connaissances, centre sur la qualite du retrieval. Vector store : Qdrant. L'enjeu : repondre juste, citer les bonnes sources, et refuser proprement quand la reponse n'est pas dans le corpus.

Contexte fil rouge : c'est la brique de recherche d'AssistKB-Neosoft. Un consultant pose une question, l'assistant retrouve les bons passages et repond en citant ses sources. Si l'info n'existe pas, il doit le dire — pas inventer (cf. incident hallucination dans le corpus seed).
