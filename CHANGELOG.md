# Changelog

## [2.0.0] - 2026-03-01

### Added
- Python CLI (`hammerdb-scale`) replacing shell scripts
- 10 commands: `version`, `init`, `validate`, `build`, `run`, `status`, `logs`, `results`, `report`, `clean`
- Pydantic v2 config schema with validation and clear error messages
- v1 config auto-migration (detects `testRun` key)
- Target defaults inheritance (`targets.defaults` merged into each host)
- `hammerdb-scale init` interactive config generator
- `hammerdb-scale validate` with 6 validation layers including database connectivity
- `hammerdb-scale run --build` combined build+run workflow
- `hammerdb-scale report` self-contained HTML scorecard with Chart.js
- `hammerdb-scale clean --database` to drop benchmark tables
- `hammerdb-scale clean --resources` to remove K8s Helm releases
- Short, deterministic job naming (`hdb-{phase}-{idx}-{hash}`, 22 chars)
- K8s labels and annotations for job metadata
- Result aggregation with partial failure handling
- Per-target log storage in `results/{test-id}/`

### Changed
- Config format: consistent snake_case, `targets.defaults` inheritance
- `run` replaces `load` as user-facing term (Helm still uses `load` internally)
- `testRun` block removed from config (phase/benchmark/id are CLI arguments)
- Image config moved to `targets.defaults.image`
- Resources moved to top-level `resources` block
- Pure Storage config moved to `storage_metrics.pure`
- All database-specific settings consolidated under `targets.defaults.<type>`
- MSSQL connection, use_bcp, maxdop, columnstore all under `targets.defaults.mssql`
- Per-host overrides for all database-specific settings via deep merge

### Removed
- Shell scripts (`deploy-test.sh`, `aggregate-results.sh`) moved to `legacy/`
- Positional CLI arguments (all named parameters now)
- `databases.oracle.driver` boilerplate (auto-resolved)

## [1.1.0] - 2024-11-01

### Added
- Oracle database support
- TPC-H benchmark support
- Pure Storage metrics collection
- Multi-target configuration

## [1.0.0] - 2024-09-01

### Added
- Initial release
- SQL Server TPC-C support
- Helm chart for Kubernetes deployment
- Shell script orchestration
