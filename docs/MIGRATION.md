# Migration Guide: v1.x to v2

## Install

```bash
pip install hammerdb-scale
```

## Migrate Config

```bash
# Option 1: Auto-migration (detects v1 format and migrates)
hammerdb-scale validate -f old-values.yaml

# Option 2: Generate fresh config (recommended)
hammerdb-scale init
# Answer prompts with same values as your old config.
```

## Command Mapping

| v1.x | v2 |
|------|--------|
| `./deploy-test.sh build test-001 tprocc` | `hammerdb-scale build --benchmark tprocc --id test-001` |
| `./deploy-test.sh load test-001 tprocc` | `hammerdb-scale run --benchmark tprocc --id test-001` |
| `./aggregate-results.sh load test-001 tprocc` | `hammerdb-scale results --benchmark tprocc --id test-001` |
| `helm uninstall load-test-001 -n ns` | `hammerdb-scale clean --resources --id test-001` |
| (manual SQL to drop tables) | `hammerdb-scale clean --database --benchmark tprocc` |

## What's Different

- Phase and benchmark are now CLI named parameters (`--benchmark tprocc`), not in the YAML file.
- `--benchmark` is optional if `default_benchmark` is set in config (set automatically by `init`).
- All arguments after the command verb are named (`--benchmark`, `--id`, `--namespace`). No positional arguments.
- `run` replaces `load` as the user-facing term (Helm still sees `load` internally).
- `run --build` combines schema creation and benchmark execution in one step.
- `clean --database` replaces manual SQL for cleaning benchmark tables.
- `clean --resources` warns if results haven't been aggregated.
- `validate` does actual database login checks, not just TCP socket tests.
- Test IDs are auto-generated if not specified.
- Results go to `./results/{test-id}/` instead of `./results/{test-id}/{phase}/`.
- HTML scorecard is new: `hammerdb-scale report`.

## Config Field Changes

| v1.x Field | v2 Field |
|------------|----------|
| `testRun.phase` | CLI `--phase` argument |
| `testRun.benchmark` | CLI `--benchmark` or `default_benchmark` in config |
| `testRun.id` | CLI `--id` or auto-generated |
| `global.image` | `targets.defaults.image` |
| `global.resources` | `resources` (top-level) |
| `hammerdb.tprocc.build_num_vu` | `hammerdb.tprocc.build_virtual_users` |
| `hammerdb.tprocc.allwarehouse` | `hammerdb.tprocc.all_warehouses` |
| `hammerdb.tprocc.timeprofile` | `hammerdb.tprocc.time_profile` |
| `hammerdb.tproch.scaleFactor` | `hammerdb.tproch.scale_factor` |
| `hammerdb.tproch.buildThreads` | `hammerdb.tproch.build_threads` |
| `hammerdb.tproch.totalQuerysets` | `hammerdb.tproch.total_querysets` |
| `databases.oracle.tempTablespace` | `targets.defaults.oracle.temp_tablespace` |
| `databases.oracle.tproch.degreeOfParallel` | `targets.defaults.oracle.tproch.degree_of_parallel` |
| `hammerdb.connection.odbc_driver` | `targets.defaults.mssql.connection.odbc_driver` |
| `pureStorage.apiToken` | `storage_metrics.pure.api_token` |
| `pureStorage.pollInterval` | `storage_metrics.pure.poll_interval` |
| `pureStorage.verifySSL` | `storage_metrics.pure.verify_ssl` |
| `pureStorage.apiVersion` | `storage_metrics.pure.api_version` |

## YAML Rationalization Summary

| v1.x Problem | v2 Fix |
|--------------|--------|
| `type`/`username`/`password` repeated per target | `targets.defaults` inheritance |
| `databaseName` repeated per MSSQL target | `targets.defaults.mssql.tprocc/tproch.database_name` |
| MSSQL connection boilerplate (9 lines per file) | `targets.defaults.mssql.connection` |
| `databases.oracle.driver: oracle` boilerplate | Auto-resolved from `type` |
| MSSQL params in Oracle configs | Scoped under `targets.defaults.mssql` |
| `testRun` in config file | CLI arguments only |
| Mixed camelCase/snake_case | Consistent snake_case |
