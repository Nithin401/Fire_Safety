# FireShield AI — Production & Cloud Deployment Guide

This document outlines the recommended production deployment target, environment variables, containerization, and security policies for FireShield AI.

---

## 1. Recommended Deployment Architecture: Google Cloud Run + Firebase

```text
  [ Edge Nodes (ESP32 / ESP8266) ]
                 │
            (HTTPS POST)
                 │
                 ▼
  [ Google Cloud Run (Docker Container) ]
  - Flask REST Ingestion API (/api/telemetry)
  - Preloaded ONNX Hybrid Risk Engine (ai/risk_engine_ml.py)
  - API Key & Token Verification (require_api_key)
  - Server-Side Rate-Limited Alert Dispatcher
                 │
         ┌───────┴───────┐
         ▼               ▼
  [ Cloud Firestore ]   [ Firebase Cloud Messaging (FCM) ]
  - devices/{id}        - High-priority push notifications
  - readings/           - Deep-link to device details
  - alerts/             - Telegram emergency bot fallback
         │
         ▼
  [ FireShield AI Mobile App (Flutter) ]
```

### Why Cloud Run?
1. **Serverless Auto-Scaling to Zero**: In prototype / pilot mode with 1–5 nodes, Cloud Run scales down to zero instances when idle, incurring near-zero hosting costs.
2. **Built-in HTTPS & Custom Domains**: Automated SSL certificate provisioning.
3. **Container-Native**: Built directly from the included `Dockerfile` and `docker-compose.yml`.
4. **Direct VPC / IAM Integration**: Cloud Run runs with a service account that has native IAM read/write permissions for Firestore and FCM without requiring long-lived JSON keys.

---

## 2. Environment Variables Configuration

Copy `.env.example` to `.env`. Ensure `.env` is never committed.

| Variable Name | Default / Example | Purpose |
|---|---|---|
| `SERVER_HOST` | `0.0.0.0` | Host IP binding. |
| `SERVER_PORT` | `5000` | Port listening for HTTP traffic. |
| `DEVICE_INGESTION_API_KEY` | `fireshield_local_dev_key_2026` | Shared secret header (`X-API-Key`) required for edge node telemetry. |
| `FIREBASE_SERVICE_ACCOUNT_PATH` | `serviceAccountKey.json` | Path to Google Cloud IAM Service Account JSON credentials. |
| `TELEGRAM_BOT_TOKEN` | *(Rotated Token)* | Secondary emergency operations channel token. |
| `TELEGRAM_CHAT_ID` | `6202108591` | Admin/Operations channel ID for alerts. |

---

## 3. Local Testing with Docker

To build and run the backend locally with Docker Compose:

```bash
# Build and start container in detached mode
docker-compose up -d --build

# View real-time streaming logs
docker-compose logs -f

# Check health endpoint
curl http://localhost:5000/health
```

---

## 4. Deploying to Google Cloud Run (CLI Command)

```bash
# 1. Build and push image to Google Artifact Registry
gcloud builds submit --tag gcr.io/fireshield-ai-prod/backend:v2.0

# 2. Deploy service to Cloud Run
gcloud run deploy fireshield-backend \
  --image gcr.io/fireshield-ai-prod/backend:v2.0 \
  --platform managed \
  --region us-central1 \
  --allow-unauthenticated \
  --set-env-vars DEVICE_INGESTION_API_KEY=fireshield_prod_secret_2026
```
