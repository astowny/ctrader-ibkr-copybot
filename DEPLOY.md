# Déploiement

Ce service est un **worker long-running** (FastAPI + connexion broker permanente via
`asyncio`). Il doit tourner **24/7 sur un hôte persistant** — **pas** sur du serverless
(Vercel/Lambda) : voir la note plus bas.

## Où le déployer

| Cible | Convient ? | Pourquoi |
|---|---|---|
| **VPS / serveur (Docker)** | ✅ | Process persistant, socket broker maintenu, `restart: unless-stopped`. |
| **Dokploy** (sur ton VPS) | ✅ | PaaS auto-hébergé : déploie depuis GitHub via **Nixpacks** ou **Dockerfile**. |
| Railway / Render / Fly.io | ✅ | Mêmes raisons (services persistants). |
| **Vercel / Netlify / Lambda** | ❌ | Serverless éphémère et sans état : ne peut pas tenir une connexion broker ni des tâches `asyncio` de fond. |

## Dokploy — depuis le repo GitHub

1. **Dokploy → Create → Application**, source = ce repo GitHub (branche `main`).
2. **Build Type** :
   - **Dockerfile** (recommandé) → Dokploy utilise [`Dockerfile`](Dockerfile) tel quel.
   - **Nixpacks** → Dokploy utilise [`nixpacks.toml`](nixpacks.toml) (start cmd déjà fournie).
3. **Port** applicatif : `8000` (Traefik route le domaine vers ce port). Le `${PORT}` est
   géré automatiquement si la plateforme l'injecte, sinon fallback `8000`.
4. **Variables d'environnement** (onglet Environment) — voir [`.env.example`](.env.example) :
   ```
   BROKER=ctrader            # ou ibkr / paper
   SIGNAL_WEBHOOK_SECRET=<secret-fort>
   CTRADER_CLIENT_ID=...
   CTRADER_CLIENT_SECRET=...
   CTRADER_ACCESS_TOKEN=...
   CTRADER_ACCOUNT_ID=...
   MAX_OPEN_POSITIONS=5
   MAX_RISK_PER_TRADE=0.01
   ```
5. **Health check** : `GET /health` (déjà exposé).
6. **Domaine** : ajoute un domaine dans Dokploy → TLS auto (Let's Encrypt via Traefik).
   Le webhook de signaux sera `POST https://<domaine>/signals` avec l'en-tête
   `x-webhook-secret: <SIGNAL_WEBHOOK_SECRET>`.
7. Active **Auto Deploy** (webhook GitHub) pour redéployer à chaque push.

## ⚠️ Cas IBKR (Interactive Brokers)

IBKR n'expose pas d'API cloud : il faut **TWS** ou **IB Gateway** qui tourne en
permanence et auquel le bot se connecte en socket (port 7497/4001). En conteneur,
prévoir un **service séparé** (image IB Gateway headless, ex. `ib-gateway` + IBC) et
faire pointer `IBKR_HOST`/`IBKR_PORT` vers ce service (réseau Docker interne Dokploy).
cTrader (Open API) est cloud-natif et ne demande pas ce composant.

## Local (Docker Compose)

```bash
cp .env.example .env     # renseigner les identifiants
docker compose up --build
```

## Pourquoi pas Vercel

L'app démarre, dans le `lifespan` FastAPI, un `ExecutionEngine` qui **ouvre et maintient
une connexion broker** (boucle de reconnexion infinie) et réagit en continu aux events
d'exécution. Une fonction serverless est tuée après chaque requête (10–60 s max, pas de
socket persistant, pas de tâche de fond) → incompatible. Seul le *webhook de réception*
pourrait théoriquement être serverless, mais le séparer du moteur d'exécution n'apporte
rien ici.
