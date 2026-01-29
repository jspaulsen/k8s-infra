# Local Infrastructure

These are instructions for setting up a local Kubernetes cluster using k3s, installing ArgoCD and configuring access for non-root users.


## Steps

1. [Installing k3s](#installing-k3s)
2. [Setup Cloudflare Kubernetes Gateway](#setup-cloudflare-kubernetes-gateway)


## Installing k3s

(Likely) as the root user, run the following command to install k3s:

```bash
curl -sfL https://get.k3s.io | sh -
```

Once installed, it's recommended to contend with UFW (Uncomplicated Firewall) to allow necessary ports for k3s operation. Here are the basic commands to set up UFW for k3s:

```bash
ufw allow 6443/tcp # apiserver
ufw allow from 10.42.0.0/16 to any # pods
ufw allow from 10.43.0.0/16 to any # services
```

## Setup Cloudflare Kubernetes Gateway

Install Gateway API CRDs and Cloudflare Kubernetes Gateway. See the documentation for more details:

- [Gateway API](https://gateway-api.sigs.k8s.io/)
- [Cloudflare Kubernetes Gateway](https://github.com/pl4nty/cloudflare-kubernetes-gateway)

```bash
kubectl apply -k github.com/kubernetes-sigs/gateway-api//config/crd?ref=v1.0.0
kubectl apply -k github.com/pl4nty/cloudflare-kubernetes-gateway//config/default?ref=v0.8.1
```

Find your Cloudflare account ID and create a cloudflare API token with the necessary permissions. Then, create a Kubernetes secret to store your Cloudflare credentials:

```bash
kubectl create namespace cloudflare-gateway
kubectl create secret generic cloudflare \
  -n cloudflare-gateway \
  --from-literal=ACCOUNT_ID=your-account-id \
  --from-literal=TOKEN=your-api-token
```

and finally, apply the Cloudflare Tunnel and Gateway configuration:

```bash
kubectl apply -f infrastructure/gateway/gateway-class.yaml
kubectl apply -f infrastructure/gateway/gateway.yaml
```

## Installing ArgoCD

```bash
kubectl create namespace argocd
kubectl apply -n argocd -f https://raw.githubusercontent.com/argoproj/argo-cd/stable/manifests/install.yaml

```

### Installing the ArgoCD CLI
[Documentation](https://argo-cd.readthedocs.io/en/stable/cli_installation/)

```bash
VERSION=$(curl -L -s https://raw.githubusercontent.com/argoproj/argo-cd/stable/VERSION)
curl -sSL -o argocd-linux-amd64 https://github.com/argoproj/argo-cd/releases/download/v$VERSION/argocd-linux-amd64
sudo install -m 555 argocd-linux-amd64 /usr/local/bin/argocd
rm argocd-linux-amd64
```

Login to argocd:

```bash
# Use argocd login --core to configure CLI access and skip steps 3-5.
argocd login --core
```

and finally, apply the bootstrap configuration:

```bash
kubectl patch deployment argocd-server -n argocd --type='json' -p='[{"op": "add", "path": "/spec/template/spec/containers/0/args/-", "value": "--insecure"}]'
kubectl apply -f bootstrap/root.yaml
```

This will create an application for `applications` folder in the repo.

### Configure HTTPRoute Health Checks

The Cloudflare Kubernetes Gateway controller doesn't populate HTTPRoute status, which causes ArgoCD to show applications using HTTPRoutes as "Progressing" indefinitely. To fix this, patch the ArgoCD ConfigMap to always consider HTTPRoutes healthy:

```bash
kubectl patch configmap argocd-cm -n argocd --type merge -p '{"data":{"resource.customizations.health.gateway.networking.k8s.io_HTTPRoute":"hs = {}\nhs.status = \"Healthy\"\nreturn hs\n"}}'
```

## Cluster Access for Non-Root Users

See the documentation [here](https://docs.k3s.io/cluster-access) for more information.  There are a few approaches that will work.

### Group Access

```bash
# Create a new group named 'k3s-users'
sudo groupadd k3s

# Add your current user to this group
sudo usermod -aG k3s $USER

# APPLY THE GROUP CHANGE:
# You must log out and log back in for this to take effect.
# Or, for the current shell session only, run:
newgrp k3s
```

Next, configure the kubeconfig file to be readable by the group.

```bash
# Now, configure k3s to use the group.
sudo nano /etc/systemd/system/k3s.service.env

# Add the following line to the file:
K3S_KUBECONFIG_MODE="640"
K3S_KUBECONFIG_GROUP="k3s"
```

Then, reload the systemd configuration and restart k3s:

```bash
sudo systemctl daemon-reload
sudo systemctl restart k3s
```
