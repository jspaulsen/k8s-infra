# Open WebUI Deployment

## Prerequisites

- k3s cluster running
- ArgoCD installed and configured
- Cloudflare Gateway configured
- `.env` file with required secrets

## Required Environment Variables

Your `.env` file must contain:

```
WEBUI_SECRET_KEY=your-secret-key-here
```

## Initial Deployment

1. Create the namespace and secrets:

```bash
kubectl create namespace open-webui
kubectl create secret generic open-webui-secrets -n open-webui --from-env-file=applications/open-webui/.env
```

2. Push the changes to git (if not already):

```bash
git add applications/open-webui/
git commit -m "Add Open WebUI application"
git push
```

3. ArgoCD will automatically sync and deploy the application. Monitor progress:

```bash
kubectl get pods -n open-webui -w
```

4. Verify the HTTPRoute is working:

```bash
kubectl get httproute -n open-webui
```

The application will be available at https://owi.yeebs.dev once DNS propagates through Cloudflare.

## Local Access

To access Open WebUI locally before DNS is configured:

```bash
kubectl port-forward -n open-webui svc/open-webui 8080:80
```

Then open http://localhost:8080

## Connecting to Ollama

If you need to connect to an external Ollama instance, add this environment variable to the deployment:

```yaml
- name: OLLAMA_BASE_URL
  value: "http://your-ollama-host:11434"
```

## Updating Secrets

If you need to update secrets:

```bash
kubectl delete secret open-webui-secrets -n open-webui
kubectl create secret generic open-webui-secrets -n open-webui --from-env-file=applications/open-webui/.env
kubectl rollout restart deployment/open-webui -n open-webui
```

## Troubleshooting

Check pod logs:

```bash
kubectl logs -n open-webui -l app=open-webui
```

Check pod status:

```bash
kubectl describe pod -n open-webui -l app=open-webui
```
