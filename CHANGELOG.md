# Changelog

All notable changes to the hammerdb-scale project will be documented in this file.

## [1.1.0] - 2025-11-27

Oracle Database support and storage testing optimizations.

### Added
- Oracle Database support (TPC-C and TPC-H benchmarks)
- Dockerfile.oracle for building Oracle-enabled images
- Oracle-specific TCL scripts for schema build, load test, and result parsing
- Helpful error message when Oracle client is missing from container
- Input validation for phase and benchmark values in Helm templates

### Changed
- SQL Server TPC-C now uses `keyandthink false` for maximum storage stress testing
- ConfigMaps are now conditional based on target database types
- deploy-test.sh now properly checks helm install exit codes

### Fixed
- deploy-test.sh variable quoting for test IDs with special characters
- Added SSL warning when Pure Storage metrics collector runs without verification

---

## [1.0.0] - 2024-12-01

Initial release of HammerDB Scale - Kubernetes orchestrator for parallel database performance testing.

### Features

**Core Capabilities**
- Parallel execution of HammerDB tests across multiple SQL Server instances
- Support for TPC-C (OLTP) and TPC-H (OLAP) benchmarks
- Helm chart deployment with simple configuration
- Separate build and load test phases for flexibility
- Results output to stdout (no PVC required)
- Automatic result parsing and aggregation

**Testing & Monitoring**
- Configurable virtual users for build vs load phases
- BCP support for faster data loading
- Per-query timing analysis for TPC-H workloads
- Optional Pure Storage FlashArray performance metrics collection
- Result aggregation with JSON and text summary output

**Usability**
- Named and positional argument support in CLI scripts
- Comprehensive documentation with examples
- Multiple configuration examples for different scenarios
- Database extension guide for adding PostgreSQL, Oracle, MySQL support

### Documentation
- Quick start guide with prerequisites and verification steps
- Security best practices for credential management
- Complete configuration reference
- Troubleshooting guide
- Release checklist

### Technical Details
- Docker container based on Ubuntu 24.04 with HammerDB 5.0
- Helm 3.x chart with configurable resources
- Python-based Pure Storage metrics collector
- Modular TCL scripts for different database types and benchmarks

---

**Note**: Built on [HammerDB](https://www.hammerdb.com) by Steve Shaw.
