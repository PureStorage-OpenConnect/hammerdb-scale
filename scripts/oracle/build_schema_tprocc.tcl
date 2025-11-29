#!/bin/tclsh
# Load environment variables
set username $::env(USERNAME)
set password $::env(PASSWORD)
set host $::env(HOST)
set oracle_port $::env(ORACLE_PORT)
set oracle_service $::env(ORACLE_SERVICE)

# TPROC-C variables
set tprocc_user $::env(TPROCC_USER)
set tprocc_password $::env(TPROCC_PASSWORD)
set tprocc_build_virtual_users $::env(TPROCC_BUILD_VIRTUAL_USERS)
set warehouses $::env(WAREHOUSES)
set tprocc_driver_type $::env(TPROCC_DRIVER_TYPE)
set tprocc_allwarehouse $::env(TPROCC_ALLWAREHOUSE)

# Oracle-specific variables
set oracle_tablespace $::env(ORACLE_TABLESPACE)
set oracle_temp_tablespace $::env(ORACLE_TEMP_TABLESPACE)

# Validate required environment variables
foreach var {USERNAME PASSWORD HOST ORACLE_PORT ORACLE_SERVICE TPROCC_USER WAREHOUSES TPROCC_BUILD_VIRTUAL_USERS} {
    if {![info exists ::env($var)] || $::env($var) eq ""} {
        puts "Error: Environment variable $var is not set or empty"
        exit 1
    }
}

# Construct Oracle connection string
set oracle_connection "${host}:${oracle_port}/${oracle_service}"

# Initialize HammerDB
puts "SETTING UP TPROC-C SCHEMA BUILD FOR ORACLE"
puts "Target connection: $oracle_connection"
puts "TPCC schema user: $tprocc_user"
puts "Warehouses: $warehouses"
puts "Build virtual users: $tprocc_build_virtual_users"

# Set database to Oracle
dbset db oracle

# Set benchmark to TPC-C
dbset bm TPC-C

# Configure connection
diset connection instance $oracle_connection
diset connection system_user $username
diset connection system_password $password

# Configure TPC-C Schema Build
diset tpcc tpcc_user $tprocc_user
diset tpcc tpcc_pass $tprocc_password
diset tpcc tpcc_def_tab $oracle_tablespace
diset tpcc tpcc_ol_tab $oracle_tablespace
diset tpcc tpcc_def_temp $oracle_temp_tablespace
diset tpcc count_ware $warehouses
diset tpcc num_vu $tprocc_build_virtual_users

# Oracle-specific features (disabled by default for compatibility)
diset tpcc partition false
diset tpcc hash_clusters false
diset tpcc tpcc_tt_compat false

# Handle allwarehouse setting
if {$tprocc_allwarehouse eq "true"} {
    diset tpcc allwarehouse true
} else {
    diset tpcc allwarehouse false
}

# Load the TPC-C script
loadscript

# Print current configuration
puts "Current TPROC-C configuration:"
print dict

# Build the schema
puts "Starting TPROC-C schema build..."
buildschema

puts "TPROC-C SCHEMA BUILD COMPLETE"
