# Vikunja Deployment

Single-user task tracker. LAN-only: exposed at `http://vikunja.lan` through k3s's
bundled Traefik (`192.168.2.254`), not the Cloudflare tunnel. SQLite on a
`local-path` PVC (`db/` and `files/` subPaths).

## Prerequisites

`vikunja.lan` must resolve to `192.168.2.254` — add it to your router's local DNS
or `/etc/hosts`:

```
192.168.2.254 vikunja.lan
```

## Initial Deployment

1. Create the namespace and JWT secret (kept out of git; the repo is public):

```bash
kubectl create namespace vikunja
kubectl create secret generic vikunja-secrets -n vikunja \
  --from-literal=VIKUNJA_SERVICE_JWTSECRET="$(openssl rand -hex 32)"
```

2. Push `applications/vikunja/`; the `applications` ApplicationSet picks it up.

## Registration

`VIKUNJA_SERVICE_ENABLEREGISTRATION` is `"true"` only until the first account
exists. Set it to `"false"` in `applications/vikunja/vikunja.yaml` afterwards.

## Upgrading

Bump the pinned tag in `vikunja.yaml`. The Deployment uses `strategy: Recreate`
because SQLite can't be shared between pods.
