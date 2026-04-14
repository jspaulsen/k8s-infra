# Herald Application Deployment

## Prerequisites

- k3s cluster running
- ArgoCD installed and configured
- `.env` file with required secrets

## Required Environment Variables

Your `.env` file must contain:

```
DB_USERNAME=
DB_PASSWORD=
TWITCH_CLIENT_ID=
TWITCH_CLIENT_SECRET=
DISCORD_TOKEN=
```

## Initial Deployment

1. Create the namespace and secrets:

```bash
kubectl create namespace herald
kubectl create secret generic herald-secrets -n herald --from-env-file=.env
```

2. Push the changes to git (if not already):

```bash
git add applications/herald/
git commit -m "Add Herald application"
git push
```

3. ArgoCD will automatically sync and deploy the application. You can monitor progress:

```bash
kubectl get pods -n herald -w
```

## Updating Secrets

If you need to update secrets:

```bash
kubectl delete secret herald-secrets -n herald
kubectl create secret generic herald-secrets -n herald --from-env-file=.env
kubectl rollout restart deployment/herald -n herald
kubectl rollout restart deployment/postgres -n herald
```

## Troubleshooting

Check pod logs:

```bash
kubectl logs -n herald -l app=herald
kubectl logs -n herald -l app=postgres
```

Check pod status:

```bash
kubectl describe pod -n herald -l app=herald
```
