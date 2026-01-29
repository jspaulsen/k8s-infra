# TTS Application Deployment

## Prerequisites

- k3s cluster running
- ArgoCD installed and configured
- Cloudflare Gateway configured
- `.env` file with required secrets

## Required Environment Variables

Your `.env` file must contain:

```
AWS_ACCESS_KEY_ID=
AWS_SECRET_ACCESS_KEY=
ADMIN_API_TOKEN=
API_TOKEN=
LOGFIRE_TOKEN=
DB_USERNAME=
DB_PASSWORD=
```

## Initial Deployment

1. Create the namespace and secrets:

```bash
kubectl create namespace tts
kubectl create secret generic tts-secrets -n tts --from-env-file=.env
```

2. Push the changes to git (if not already):

```bash
git add applications/tts/
git commit -m "Add TTS application"
git push
```

3. ArgoCD will automatically sync and deploy the application. You can monitor progress:

```bash
kubectl get pods -n tts -w
```

4. Verify the HTTPRoute is working:

```bash
kubectl get httproute -n tts
```

The application will be available at https://tts-alt.yeebs.dev once DNS propagates through Cloudflare.

## Migrating Data from Docker Compose

If you have an existing PostgreSQL database running in Docker Compose, follow these steps to migrate the data.

### 1. Export data from Docker

```bash
docker exec postgres pg_dump -U $DB_USERNAME -d postgres > backup.sql
```

### 2. Wait for the k8s postgres pod to be ready

```bash
kubectl get pods -n tts -l app=postgres -w
```

### 3. Copy and restore the backup

```bash
# Get the postgres pod name
POSTGRES_POD=$(kubectl get pods -n tts -l app=postgres -o jsonpath='{.items[0].metadata.name}')

# Copy backup to pod
kubectl cp backup.sql tts/$POSTGRES_POD:/tmp/backup.sql

# Restore the backup
kubectl exec -n tts $POSTGRES_POD -- psql -U $DB_USERNAME -d postgres -f /tmp/backup.sql
```

### Alternative: Direct pipe (if both are accessible)

```bash
POSTGRES_POD=$(kubectl get pods -n tts -l app=postgres -o jsonpath='{.items[0].metadata.name}')

docker exec postgres pg_dump -U $DB_USERNAME -d postgres | \
  kubectl exec -i -n tts $POSTGRES_POD -- psql -U $DB_USERNAME -d postgres
```

### 4. Verify the migration

```bash
kubectl exec -n tts $POSTGRES_POD -- psql -U $DB_USERNAME -d postgres -c "\dt"
```

### 5. Restart the TTS app to reconnect

```bash
kubectl rollout restart deployment/tts -n tts
```

## Updating Secrets

If you need to update secrets:

```bash
kubectl delete secret tts-secrets -n tts
kubectl create secret generic tts-secrets -n tts --from-env-file=.env
kubectl rollout restart deployment/tts -n tts
kubectl rollout restart deployment/postgres -n tts
```

## Troubleshooting

Check pod logs:

```bash
kubectl logs -n tts -l app=tts
kubectl logs -n tts -l app=postgres
```

Check pod status:

```bash
kubectl describe pod -n tts -l app=tts
```
