# MLflow Deployment

## Prerequisites

- k3s cluster running
- ArgoCD installed and configured
- Cloudflare Gateway configured
- `.env` file with required secrets

## Required Environment Variables

Your `.env` file must contain:

```
POSTGRES_USER=mlflow
POSTGRES_PASSWORD=mlflow
AWS_ACCESS_KEY_ID=s3admin
AWS_SECRET_ACCESS_KEY=s3admin
```

## Architecture

The deployment consists of three components:

- **PostgreSQL** — backend store for experiment metadata
- **RustFS** — S3-compatible object storage for artifacts
- **MLflow Server** — the tracking server (includes an init container that creates the S3 bucket)

## Initial Deployment

1. Create the namespace and secrets:

```bash
kubectl create namespace mlflow
kubectl create secret generic mlflow-secrets -n mlflow --from-env-file=applications/mlflow/.env
```

2. Push the changes to git (if not already):

```bash
git add applications/mlflow/
git commit -m "Add MLflow application"
git push
```

3. ArgoCD will automatically sync and deploy the application. Monitor progress:

```bash
kubectl get pods -n mlflow -w
```

4. Verify the HTTPRoute is working:

```bash
kubectl get httproute -n mlflow
```

The application will be available at https://mlflow.yeebs.dev once DNS propagates through Cloudflare.

## Local Access

To access MLflow locally before DNS is configured:

```bash
kubectl port-forward -n mlflow svc/mlflow-server 5000:80
```

Then open http://localhost:5000

A NodePort service is also available on port 30050.

## Migrating Data from Docker Compose

If you have an existing MLflow instance running in Docker Compose, follow these steps to migrate the data.

### 1. Export the PostgreSQL database

```bash
docker exec mlflow-postgres pg_dump -U mlflow mlflow > mlflow-backup.sql
```

### 2. Copy the S3 storage data

```bash
docker run --rm -v mlflow_storage-data:/data -v $(pwd):/backup alpine tar czf /backup/mlflow-storage-backup.tar.gz -C /data .
```

### 3. Wait for the k8s pods to be ready

```bash
kubectl get pods -n mlflow -w
```

### 4. Restore the PostgreSQL database

```bash
POSTGRES_POD=$(kubectl get pods -n mlflow -l app=mlflow-postgres -o jsonpath='{.items[0].metadata.name}')

kubectl cp mlflow-backup.sql mlflow/$POSTGRES_POD:/tmp/mlflow-backup.sql

kubectl exec -n mlflow $POSTGRES_POD -- psql -U mlflow -d mlflow -f /tmp/mlflow-backup.sql
```

### 5. Restore the S3 storage data

```bash
STORAGE_POD=$(kubectl get pods -n mlflow -l app=mlflow-storage -o jsonpath='{.items[0].metadata.name}')

kubectl cp mlflow-storage-backup.tar.gz mlflow/$STORAGE_POD:/tmp/mlflow-storage-backup.tar.gz

kubectl exec -n mlflow $STORAGE_POD -- tar xzf /tmp/mlflow-storage-backup.tar.gz -C /data
```

### 6. Restart the deployments to pick up restored data

```bash
kubectl rollout restart deployment/mlflow-postgres -n mlflow
kubectl rollout restart deployment/mlflow-storage -n mlflow
kubectl rollout restart deployment/mlflow-server -n mlflow
```

## Updating Secrets

If you need to update secrets:

```bash
kubectl delete secret mlflow-secrets -n mlflow
kubectl create secret generic mlflow-secrets -n mlflow --from-env-file=applications/mlflow/.env
kubectl rollout restart deployment/mlflow-server -n mlflow
kubectl rollout restart deployment/mlflow-postgres -n mlflow
```

## Troubleshooting

Check pod logs:

```bash
kubectl logs -n mlflow -l app=mlflow
kubectl logs -n mlflow -l app=mlflow-postgres
kubectl logs -n mlflow -l app=mlflow-storage
```

Check pod status:

```bash
kubectl describe pod -n mlflow -l app=mlflow
```

Check the init container (bucket creation) logs:

```bash
MLFLOW_POD=$(kubectl get pods -n mlflow -l app=mlflow -o jsonpath='{.items[0].metadata.name}')
kubectl logs -n mlflow $MLFLOW_POD -c create-bucket
```
