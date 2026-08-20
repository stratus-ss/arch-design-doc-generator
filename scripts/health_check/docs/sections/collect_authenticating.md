### Option A — Kubeconfig file (preferred)

If you have a kubeconfig, pass it directly:

```bash
make hc-collect KUBECONFIG=/path/to/kubeconfig
```

Or with the script directly:

```bash
bash hc_collect.sh --kubeconfig /path/to/kubeconfig --output-dir ./hc_results
```

If `KUBECONFIG` is already set in your shell environment, you can omit the flag entirely:

```bash
make hc-collect
```

### Option B — Username and password

If you were given credentials instead of a kubeconfig, log in first to generate one. You need the cluster API server URL — your contact at the customer should be able to provide it.

```bash
# Log in — this creates/updates ~/.kube/config
oc login https://api.<cluster-name>.<domain>:6443 \
  --username=<username> \
  --password=<password>
```

If the cluster uses a self-signed certificate, add `--insecure-skip-tls-verify`:

```bash
oc login https://api.<cluster-name>.<domain>:6443 \
  --username=<username> \
  --password=<password> \
  --insecure-skip-tls-verify
```

After a successful login, your kubeconfig is populated at `~/.kube/config`. Run collection normally:

```bash
make hc-collect
# or explicitly:
make hc-collect KUBECONFIG=~/.kube/config
```

### Option C — Username and password with an isolated kubeconfig

If you do not want to overwrite your existing `~/.kube/config` (e.g. you manage multiple clusters), create a separate file:

```bash
KUBECONFIG=./customer-kubeconfig \
  oc login https://api.<cluster-name>.<domain>:6443 \
  --username=<username> \
  --password=<password>

make hc-collect KUBECONFIG=./customer-kubeconfig
```

### Option D — API token

If you have a service account token or a user token (retrieved from the OpenShift web console under your user profile → **Copy login command**):

```bash
oc login https://api.<cluster-name>.<domain>:6443 \
  --token=<token>

make hc-collect
```
