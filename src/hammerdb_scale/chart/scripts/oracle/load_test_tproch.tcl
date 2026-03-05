#!/bin/tclsh
# Fetch environment variables for Oracle connection
set username $::env(USERNAME)
set password $::env(PASSWORD)
set host $::env(HOST)
set oracle_port $::env(ORACLE_PORT)
set oracle_service $::env(ORACLE_SERVICE)
set tmpdir $::env(TMPDIR)

# TPROC-H specific variables
set tproch_driver $::env(TPROCH_DRIVER)
set tproch_user $::env(TPROCH_USER)
set tproch_password $::env(TPROCH_PASSWORD)
set tproch_virtual_users $::env(TPROCH_VIRTUAL_USERS)
set tproch_scale_factor $::env(TPROCH_SCALE_FACTOR)
set tproch_build_threads $::env(TPROCH_BUILD_THREADS)
set tproch_total_querysets $::env(TPROCH_TOTAL_QUERYSETS)
set tproch_log_to_temp $::env(TPROCH_LOG_TO_TEMP)
set tproch_degree_of_parallel $::env(TPROCH_DEGREE_OF_PARALLEL)

# Validate required environment variables
foreach var {USERNAME PASSWORD HOST ORACLE_PORT ORACLE_SERVICE TPROCH_DRIVER TPROCH_USER} {
    if {![info exists ::env($var)] || $::env($var) eq ""} {
        puts "Error: Environment variable $var is not set or empty."
        exit 1
    }
}

# Construct Oracle connection string
set oracle_connection "${host}:${oracle_port}/${oracle_service}"

# Initialize HammerDB
puts "SETTING UP TPROC-H LOAD TEST FOR ORACLE"
puts "Environment variables loaded:"
puts "Connection: $oracle_connection"
puts "TPCH User: $tproch_user"
puts "Virtual Users: $tproch_virtual_users"
puts "Degree of Parallel: $tproch_degree_of_parallel"

# Set up the database connection details for Oracle
dbset db $tproch_driver

# Set the benchmark to TPC-H
dbset bm TPC-H

# Set up the database connection details for Oracle
diset connection instance $oracle_connection
diset connection system_user $username
diset connection system_password $password

# Configure TPC-H benchmark parameters
diset tpch tpch_user $tproch_user
diset tpch tpch_pass $tproch_password
diset tpch total_querysets $tproch_total_querysets
diset tpch scale_fact $tproch_scale_factor
diset tpch num_tpch_threads $tproch_build_threads

# Oracle-specific settings
diset tpch degree_of_parallel $tproch_degree_of_parallel
diset tpch verbose false
diset tpch refresh_on false
diset tpch raise_query_error false

# Test run parameters
set vuser_count $tproch_virtual_users

# Configure test options and load scripts
vuset logtotemp $tproch_log_to_temp
loadscript

puts "STARTING TPROC-H VIRTUAL USERS"
puts "Virtual Users: $vuser_count"
puts "Output will be logged to: $tmpdir/oracle_tproch"

vuset vu $vuser_count
vucreate
puts "TEST STARTED"
puts "About to run vurun command..."
set jobid [ vurun ]
puts "vurun completed with job ID: $jobid"
puts "Waiting for test completion..."
vucomplete
puts "Test completion confirmed"
vudestroy
puts "Virtual users destroyed"
puts "TPROC-H LOAD TEST COMPLETE"

# Write job ID to output file for parsing
puts "Creating output file at: $tmpdir/oracle_tproch"
set of [ open $tmpdir/oracle_tproch w ]
puts $of $jobid
close $of
puts "Job ID $jobid written to $tmpdir/oracle_tproch"
