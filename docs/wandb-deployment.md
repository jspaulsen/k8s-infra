# W&B (Weights & Biases) Deployment

## Prerequisites

- k3s cluster running
- ArgoCD installed and configured
- Cloudflare Gateway configured
- `.env` file with required secrets

## Required Environment Variables

Your `.env` file must contain:

```
WANDB_LICENSE=your-license-key-here
```

## Initial Deployment

1. Create the namespace and secrets:

```bash
kubectl create namespace wandb
kubectl create secret generic wandb-secrets -n wandb --from-env-file=applications/wandb/.env
```

2. Push the changes to git (if not already):

```bash
git add applications/wandb/
git commit -m "Add W&B application"
git push
```

3. ArgoCD will automatically sync and deploy the application. Monitor progress:

```bash
kubectl get pods -n wandb -w
```

4. Verify the HTTPRoute is working:

```bash
kubectl get httproute -n wandb
```

The application will be available at https://wandb.yeebs.dev once DNS propagates through Cloudflare.

## Local Access

To access W&B locally before DNS is configured:

```bash
kubectl port-forward -n wandb svc/wandb-server 8080:80
```

Then open http://localhost:8080

## Migrating Data from Docker Compose

If you have an existing W&B instance running in Docker Compose, follow these steps to migrate the data.

### 1. Copy the volume data from Docker

```bash
# Find the Docker volume path
docker volume inspect wandb_wandb_data --format '{{ .Mountpoint }}'

# Create a tarball of the data
docker run --rm -v wandb_wandb_data:/vol -v $(pwd):/backup alpine tar czf /backup/wandb-backup.tar.gz -C /vol .
```

### 2. Wait for the k8s pod to be ready

```bash
kubectl get pods -n wandb -l app=wandb -w
```

### 3. Copy and restore the backup

```bash
# Get the wandb pod name
WANDB_POD=$(kubectl get pods -n wandb -l app=wandb -o jsonpath='{.items[0].metadata.name}')

# Copy backup to pod
kubectl cp wandb-backup.tar.gz wandb/$WANDB_POD:/tmp/wandb-backup.tar.gz

# Restore the backup
kubectl exec -n wandb $WANDB_POD -- tar xzf /tmp/wandb-backup.tar.gz -C /vol
```

### 4. Restart the deployment to pick up restored data

```bash
kubectl rollout restart deployment/wandb-server -n wandb
```

## Updating Secrets

If you need to update secrets:

```bash
kubectl delete secret wandb-secrets -n wandb
kubectl create secret generic wandb-secrets -n wandb --from-env-file=applications/wandb/.env
kubectl rollout restart deployment/wandb-server -n wandb
```

## Troubleshooting

Check pod logs:

```bash
kubectl logs -n wandb -l app=wandb
```

Check pod status:

```bash
kubectl describe pod -n wandb -l app=wandb
```
