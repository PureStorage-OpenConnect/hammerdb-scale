# Changelog

All notable changes to the hammerdb-scale project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.0] - TBD

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
