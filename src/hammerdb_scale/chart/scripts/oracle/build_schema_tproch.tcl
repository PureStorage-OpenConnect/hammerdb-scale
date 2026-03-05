#!/bin/tclsh
set username $::env(USERNAME)
set password $::env(PASSWORD)
set host $::env(HOST)
set oracle_port $::env(ORACLE_PORT)
set oracle_service $::env(ORACLE_SERVICE)

# TPROC-H variables
set tproch_user $::env(TPROCH_USER)
set tproch_password $::env(TPROCH_PASSWORD)
set tproch_scale_factor $::env(TPROCH_SCALE_FACTOR)
set tproch_driver $::env(TPROCH_DRIVER)
set tproch_build_threads $::env(TPROCH_BUILD_THREADS)
set tproch_build_virtual_users $::env(TPROCH_BUILD_VIRTUAL_USERS)

# Oracle-specific variables
set oracle_tablespace $::env(ORACLE_TABLESPACE)
set oracle_temp_tablespace $::env(ORACLE_TEMP_TABLESPACE)

# Validate required environment variables
foreach var {USERNAME PASSWORD HOST ORACLE_PORT ORACLE_SERVICE TPROCH_USER TPROCH_SCALE_FACTOR TPROCH_DRIVER TPROCH_BUILD_THREADS TPROCH_BUILD_VIRTUAL_USERS} {
    if {![info exists ::env($var)] || $::env($var) eq ""} {
        puts "Error: Environment variable $var is not set or empty"
        exit 1
    }
}

# Construct Oracle connection string
set oracle_connection "${host}:${oracle_port}/${oracle_service}"

# Initialize HammerDB
puts "SETTING UP TPROC-H SCHEMA BUILD FOR ORACLE"
puts "Target connection: $oracle_connection"
puts "TPCH schema user: $tproch_user"
puts "Scale factor: $tproch_scale_factor"
puts "Build threads: $tproch_build_threads"
puts "Build virtual users: $tproch_build_virtual_users (for logging; build uses threads)"

# Set database to Oracle
dbset db $tproch_driver

# Set benchmark to TPC-H
dbset bm TPC-H

# Configure connection
diset connection instance $oracle_connection
diset connection system_user $username
diset connection system_password $password

# Configure TPC-H Schema Build
diset tpch tpch_user $tproch_user
diset tpch tpch_pass $tproch_password
diset tpch tpch_def_tab $oracle_tablespace
diset tpch tpch_def_temp $oracle_temp_tablespace
diset tpch scale_fact $tproch_scale_factor
diset tpch num_tpch_threads $tproch_build_threads

# Oracle-specific features (disabled by default for compatibility)
diset tpch tpch_tt_compat false

# Load the TPC-H script
loadscript

# Print current configuration
puts "Current TPROC-H configuration:"
print dict

# Build the schema
puts "Starting TPROC-H schema build..."
buildschema

puts "TPROC-H SCHEMA BUILD COMPLETE"
