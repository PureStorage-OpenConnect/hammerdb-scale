#!/bin/tclsh
# Fetch environment variables for Oracle connection
set username $::env(USERNAME)
set password $::env(PASSWORD)
set host $::env(HOST)
set oracle_port $::env(ORACLE_PORT)
set oracle_service $::env(ORACLE_SERVICE)

# TPROC-C specific variables
set virtual_users $::env(VIRTUAL_USERS)
set tprocc_user $::env(TPROCC_USER)
set tprocc_password $::env(TPROCC_PASSWORD)
set tprocc_driver $::env(TPROCC_DRIVER)
set rampup $::env(RAMPUP)
set duration $::env(DURATION)
set total_iterations $::env(TOTAL_ITERATIONS)
set tmpdir $::env(TMPDIR)
set warehouses $::env(WAREHOUSES)
set tprocc_log_to_temp $::env(TPROCC_LOG_TO_TEMP)
set tprocc_use_transaction_counter $::env(TPROCC_USE_TRANSACTION_COUNTER)
set tprocc_checkpoint $::env(TPROCC_CHECKPOINT)
set tprocc_timeprofile $::env(TPROCC_TIMEPROFILE)

# Check if all required environment variables are set
if {![info exists username] || ![info exists password] || ![info exists host] || ![info exists oracle_port] || ![info exists oracle_service]} {
    puts "Error: Environment variables USERNAME, PASSWORD, HOST, ORACLE_PORT, and ORACLE_SERVICE must be set."
    exit 1
}

# Construct Oracle connection string
set oracle_connection "${host}:${oracle_port}/${oracle_service}"

# Initialize HammerDB
puts "SETTING UP TPROC-C LOAD TEST FOR ORACLE"
puts "Environment variables loaded:"
puts "  Connection: $oracle_connection"
puts "  TPCC User: $tprocc_user"
puts "  Virtual Users: $virtual_users"
puts "  Duration: $duration minutes"
puts "  Rampup: $rampup minutes"
puts "  Total Iterations: $total_iterations"

# Set up the database connection details for Oracle
dbset db $tprocc_driver

# Set the benchmark to TPC-C
dbset bm TPC-C

# Set up the database connection details for Oracle
diset connection instance $oracle_connection
diset connection system_user $username
diset connection system_password $password

# Configure TPC-C benchmark parameters
diset tpcc tpcc_user $tprocc_user
diset tpcc tpcc_pass $tprocc_password
diset tpcc count_ware $warehouses

# Oracle driver settings
diset tpcc ora_driver timed
diset tpcc total_iterations $total_iterations
diset tpcc rampup $rampup
diset tpcc duration $duration
diset tpcc allwarehouse true

# Set checkpoint and timeprofile if they are true
if {$tprocc_checkpoint eq "true"} {
    diset tpcc checkpoint true
}
if {$tprocc_timeprofile eq "true"} {
    diset tpcc ora_timeprofile true
}

# Disable keying and thinking time for consistent results
diset tpcc keyandthink false

# Configure test options and load scripts
vuset logtotemp $tprocc_log_to_temp
loadscript

puts "STARTING TPROC-C VIRTUAL USERS"
puts "Virtual Users: $virtual_users"
puts "Duration: $duration minutes"
puts "Output will be logged to: $tmpdir/oracle_tprocc"

vuset vu $virtual_users
vucreate
puts "TEST STARTED"

# Handle transaction counter based on environment variable
if {$tprocc_use_transaction_counter eq "true"} {
    puts "Starting transaction counter..."
    tcstart
    tcstatus
}

puts "About to run vurun command..."
set jobid [ vurun ]
puts "vurun completed with job ID: $jobid"
vudestroy

if {$tprocc_use_transaction_counter eq "true"} {
    puts "Stopping transaction counter..."
    tcstop
}

puts "Virtual users destroyed"
puts "TPROC-C LOAD TEST COMPLETE"

# Write job ID to output file for parsing
puts "Creating output file at: $tmpdir/oracle_tprocc"
set of [ open $tmpdir/oracle_tprocc w ]
puts $of $jobid
close $of
puts "Job ID $jobid written to $tmpdir/oracle_tprocc"
