# ctrader-ibkr-copybot

Robot de **copy trading semi-autonome** avec architecture multi-agents et exécution
sécurisée sur API broker (cTrader / Pepperstone et Interactive Brokers).

> Mission forfaitaire — réception des signaux, filtre de confirmation technique,
> moteur d'exécution. Stack : Python `asyncio`, FastAPI, Docker.

## Architecture

Trois modules découplés communiquant via un bus d'événements asynchrone, ce qui permet
de tester, déployer et faire évoluer chaque étage indépendamment.

```
                 ┌──────────────┐     ┌────────────────────┐     ┌────────────────┐
  signaux  ───▶  │ 1. Réception │ ──▶ │ 2. Filtre technique│ ──▶ │ 3. Exécution   │ ──▶ broker
  (webhook,      │   (signals)  │     │   (confirmation)   │     │  (execution)   │
   flux, TG)     └──────────────┘     └────────────────────┘     └────────────────┘
                        │                      │                        │
                        └──────────── bus d'événements (async) ─────────┘
                                              │
                                       journalisation des ordres
```

| Module | Rôle | Dossier |
| --- | --- | --- |
| **1. Réception des signaux** | Ingestion des signaux (webhook FastAPI, flux, Telegram), normalisation. | [`src/copybot/signals/`](src/copybot/signals/) |
| **2. Filtre de confirmation** | Validation technique avant exécution (tendance, volatilité, risque). | [`src/copybot/filters/`](src/copybot/filters/) |
| **3. Moteur d'exécution** | Passage d'ordre asynchrone, reconnexion auto, journalisation complète. | [`src/copybot/execution/`](src/copybot/execution/) |

Les connecteurs broker implémentent une interface commune ([`brokers/base.py`](src/copybot/execution/brokers/base.py)) :
- **cTrader** (Open API / Pepperstone) — [`ctrader.py`](src/copybot/execution/brokers/ctrader.py)
- **IBKR** (TWS / Gateway) — [`ibkr.py`](src/copybot/execution/brokers/ibkr.py)

## Points clés

- Gestion robuste des erreurs et **reconnexion automatique** aux flux broker.
- **Journalisation complète** des ordres (audit, replay).
- Découplage par bus async → résilience et testabilité.
- Configuration par variables d'environnement (voir [`.env.example`](.env.example)).

## Démarrage rapide

```bash
# 1. Configuration
cp .env.example .env        # renseigner les identifiants broker

# 2. Local (Python 3.11+)
pip install -r requirements.txt
uvicorn copybot.main:app --reload --app-dir src

# 3. Docker
docker compose up --build
```

L'API expose un endpoint de réception de signaux et un endpoint de santé
(voir [`src/copybot/api/routes.py`](src/copybot/api/routes.py)).

## Tests

```bash
pip install -r requirements.txt
pytest
```

## Avertissement

Le trading sur marchés financiers comporte un risque de perte en capital. Ce logiciel
est fourni à des fins d'outillage ; testez exhaustivement en environnement *demo*
avant tout usage en compte réel.

## Licence

MIT — voir [`LICENSE`](LICENSE).
