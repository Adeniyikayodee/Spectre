#!/usr/bin/env bash
# Deploy to Cloud Run. Keys live in Secret Manager, never in the image.
# Prereqs (one-time):
#   gcloud config set project "$GCP_PROJECT"
#   gcloud services enable run.googleapis.com aiplatform.googleapis.com \
#       bigquery.googleapis.com secretmanager.googleapis.com
#   printf '%s' "$ANTHROPIC_API_KEY"  | gcloud secrets create anthropic  --data-file=-
#   printf '%s' "$OPENROUTER_API_KEY" | gcloud secrets create openrouter --data-file=-
#   printf '%s' "$PERPLEXITY_API_KEY" | gcloud secrets create perplexity --data-file=-
#   printf '%s' "$NEO4J_PASSWORD"     | gcloud secrets create neo4j-pw   --data-file=-
# Cloud Run runtime SA also needs: roles/aiplatform.user, roles/bigquery.dataEditor
set -euo pipefail

: "${GCP_PROJECT:?set GCP_PROJECT}"
REGION="${GCP_REGION:-us-central1}"

gcloud run deploy litigation-engine \
  --source . \
  --project "$GCP_PROJECT" \
  --region "$REGION" \
  --allow-unauthenticated \
  --timeout 3600 \
  --set-env-vars "GCP_PROJECT=${GCP_PROJECT},GCP_REGION=${REGION},BQ_DATASET=${BQ_DATASET:-litigation},NEO4J_URI=${NEO4J_URI:-},NEO4J_USER=${NEO4J_USER:-neo4j}" \
  --update-secrets "ANTHROPIC_API_KEY=anthropic:latest,OPENROUTER_API_KEY=openrouter:latest,PERPLEXITY_API_KEY=perplexity:latest,NEO4J_PASSWORD=neo4j-pw:latest"
