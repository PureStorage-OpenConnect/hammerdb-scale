# HammerDB Scale - Base Image
# Supports: SQL Server, PostgreSQL, MySQL (Oracle requires extension image)
#
# This is the public base image containing HammerDB 5.0 and open-source database drivers.
# For Oracle support, build the extension image using Dockerfile.oracle
#
# BUILD:
#   docker build -t sillidata/hammerdb-scale:latest .
#
# ORACLE USERS:
#   docker build -f Dockerfile.oracle -t myregistry/hammerdb-scale-oracle:latest .

FROM ubuntu:24.04

LABEL maintainer="hammerdb-scale"
LABEL description="HammerDB Scale Test Runner - Multi-Database Performance Testing"
LABEL hammerdb.version="5.0"
LABEL database.support="mssql,postgresql,mysql (oracle via extension)"

# Set environment variables
ENV DEBIAN_FRONTEND=noninteractive

# Install base packages and SQL Server drivers (Microsoft - permissive license)
RUN apt-get update && \
    apt-get install -y \
        apt-transport-https \
        curl \
        gnupg2 \
        wget \
        python3 \
        python3-pip \
        vim && \
    # Add Microsoft repository for SQL Server tools
    curl -sSL -O https://packages.microsoft.com/config/ubuntu/24.04/packages-microsoft-prod.deb && \
    dpkg -i packages-microsoft-prod.deb && \
    rm packages-microsoft-prod.deb && \
    apt-get update && \
    ACCEPT_EULA=Y apt-get install -y mssql-tools18 msodbcsql18 unixodbc unixodbc-dev && \
    echo 'export PATH="$PATH:/opt/mssql-tools18/bin"' >> ~/.bashrc && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/* /var/apt/cache/* /tmp/* /var/tmp/*

# Install Python dependencies for Pure Storage metrics collection
RUN python3 -m pip install --no-cache-dir --break-system-packages requests urllib3

# Install HammerDB 5.0
WORKDIR /opt
RUN wget https://github.com/TPC-Council/HammerDB/releases/download/v5.0/HammerDB-5.0-Prod-Lin-UBU24.tar.gz && \
    tar -xzf HammerDB-5.0-Prod-Lin-UBU24.tar.gz && \
    rm HammerDB-5.0-Prod-Lin-UBU24.tar.gz && \
    echo 'export LD_LIBRARY_PATH=/usr/lib/x86_64-linux-gnu/:$LD_LIBRARY_PATH' >> ~/.bashrc

# Configure HammerDB
WORKDIR /opt/HammerDB-5.0
RUN chmod +x ./hammerdbcli && \
    ln -sf /opt/mssql-tools18/bin/bcp /opt/HammerDB-5.0/bcp && \
    ln -sf /opt/mssql-tools18/bin/bcp /usr/local/bin/bcp

# Add entrypoint script
COPY entrypoint.sh /opt/HammerDB-5.0/entrypoint.sh
RUN chmod +x /opt/HammerDB-5.0/entrypoint.sh

# Add Pure Storage metrics collection script
COPY scripts/collect_pure_metrics.py /opt/HammerDB-5.0/scripts/collect_pure_metrics.py
RUN chmod +x /opt/HammerDB-5.0/scripts/collect_pure_metrics.py

WORKDIR /opt/HammerDB-5.0

ENTRYPOINT ["/opt/HammerDB-5.0/entrypoint.sh"]
