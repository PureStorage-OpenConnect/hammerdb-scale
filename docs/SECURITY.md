# Security Considerations

## Credentials

HammerDB-Scale v2.0.0 stores database credentials in plaintext YAML config files. This is consistent with Helm values.yaml patterns but should be handled carefully.

**Recommendations:**

- Do not commit config files containing passwords to version control
- Use file permissions to restrict access to config files (`chmod 600`)
- Consider using environment variable substitution in CI/CD pipelines

## Database Connectivity

- MSSQL connections use encrypted connections by default (`encrypt_connection: true`)
- Oracle connections use `oracledb` thin mode (no Oracle client required)
- The `validate` command tests connectivity as the admin user only, not schema users

## Container Images

- Default images are pulled from `sillidata/hammerdb-scale` (MSSQL) and `sillidata/hammerdb-scale-oracle` (Oracle)
- Images embed HammerDB 5.0 and database client libraries
- Use `pull_policy: Always` in production to ensure latest patches

## Kubernetes

- Jobs run in the configured namespace (default: `hammerdb`)
- Resource limits are enforced via the `resources` config section
- Jobs have a configurable TTL (`job_ttl`) after which K8s garbage-collects them

## Network

- The CLI communicates with databases directly during `validate --connectivity`
- Helm and kubectl commands use the current kubeconfig context
- Pure Storage API calls (if enabled) use the configured API token and endpoint
