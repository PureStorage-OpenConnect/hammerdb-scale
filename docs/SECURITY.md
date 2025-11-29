[← Back to README](../README.md) | [Configuration](CONFIGURATION.md) | [Usage Guide](USAGE-GUIDE.md)

# Security Best Practices

Guidelines for securely deploying HammerDB Scale in production environments.

## Credentials Management

### Never Commit Real Passwords

- **Never commit real passwords to version control**
- Use separate values files for each environment (dev, staging, prod)
- Add `values-local.yaml` to `.gitignore`

### Use Kubernetes Secrets

```bash
kubectl create secret generic db-credentials \
  --from-literal=username=sa \
  --from-literal=password='YourSecurePassword' \
  -n hammerdb-scale
```

### External Secret Management

Consider using:
- HashiCorp Vault
- AWS Secrets Manager
- Azure Key Vault
- Google Secret Manager

## Network Security

### Network Policies

Restrict traffic between namespaces:

```yaml
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: hammerdb-scale-policy
  namespace: hammerdb-scale
spec:
  podSelector: {}
  policyTypes:
  - Egress
  egress:
  - to:
    - ipBlock:
        cidr: 10.0.0.0/8  # Allow only internal network
    ports:
    - protocol: TCP
      port: 1433  # SQL Server
    - protocol: TCP
      port: 1521  # Oracle
```

### TLS/SSL Encryption

Enable encrypted database connections where possible:

```yaml
hammerdb:
  connection:
    encrypt_connection: true
    trust_server_cert: false  # Use proper certificates in production
```

### Private Container Registries

Use private registries for custom images:

```yaml
global:
  image:
    repository: myregistry.azurecr.io/hammerdb-scale-oracle
  imagePullSecrets:
    - name: registry-credentials
```

### RBAC

Restrict access to Kubernetes API and namespaces:

```yaml
apiVersion: rbac.authorization.k8s.io/v1
kind: Role
metadata:
  namespace: hammerdb-scale
  name: hammerdb-operator
rules:
- apiGroups: ["batch"]
  resources: ["jobs"]
  verbs: ["get", "list", "watch", "create", "delete"]
- apiGroups: [""]
  resources: ["pods", "pods/log"]
  verbs: ["get", "list", "watch"]
```

## Pure Storage API Tokens

- **Treat API tokens as passwords** - never commit to git
- Rotate API tokens regularly
- Use read-only API tokens if write access is not needed
- Store tokens in Kubernetes Secrets:

```bash
kubectl create secret generic pure-api \
  --from-literal=token='your-api-token' \
  -n hammerdb-scale
```

## Container Security

### Image Scanning

Scan container images for vulnerabilities regularly:

```bash
# Using Trivy
trivy image sillidata/hammerdb-scale:latest

# Using Snyk
snyk container test sillidata/hammerdb-scale:latest
```

### Use Specific Tags

Avoid `latest` tag in production:

```yaml
global:
  image:
    repository: sillidata/hammerdb-scale
    tag: "1.1.0"  # Use specific version
```

### Non-Root User

The container runs processes as a non-root user where possible. For additional security:

```yaml
spec:
  securityContext:
    runAsNonRoot: true
    runAsUser: 1000
```

### Keep Images Updated

Regularly update base images to get security patches.

## Example Secure Deployment

```bash
# Create namespace
kubectl create namespace hammerdb-scale

# Create secrets
kubectl create secret generic db-credentials \
  --from-literal=password='YourSecurePassword' \
  -n hammerdb-scale

kubectl create secret generic pure-api \
  --from-literal=token='your-api-token' \
  -n hammerdb-scale

# Deploy with production values
helm install test-001 . -n hammerdb-scale \
  -f values-prod.yaml \
  --set targets[0].password=\$DB_PASSWORD
```

## Audit and Compliance

### Enable Kubernetes Audit Logging

Configure your cluster to log all API access:

```yaml
apiVersion: audit.k8s.io/v1
kind: Policy
rules:
- level: Metadata
  resources:
  - group: "batch"
    resources: ["jobs"]
```

### Review Logs

Regularly review logs for unauthorized access attempts:

```bash
kubectl logs -n hammerdb-scale -l app.kubernetes.io/name=hammerdb-scale --since=24h
```

### Document Test Runs

Maintain records of:
- Test configurations used
- Test results and timestamps
- Who ran each test
- Any anomalies observed

### Change Control

- Use version control for all configuration changes
- Review changes before applying to production
- Maintain a changelog of infrastructure modifications

## Checklist

Before deploying to production:

- [ ] Database credentials stored in Kubernetes Secrets
- [ ] API tokens stored in Kubernetes Secrets
- [ ] Network policies configured
- [ ] TLS/SSL enabled for database connections
- [ ] Private container registry configured (if applicable)
- [ ] RBAC roles defined
- [ ] Container images scanned for vulnerabilities
- [ ] Specific image tags used (not `latest`)
- [ ] Audit logging enabled
- [ ] values-local.yaml added to .gitignore
