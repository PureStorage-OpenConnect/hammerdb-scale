#!/bin/tclsh
# Procedure to get the job ID from the output file
proc getjobid {filename} {
    set fd [open $filename r]
    set jobid [lindex [split [gets $fd] =] 1]
    close $fd
    return $jobid
}

# Procedure to extract total elapsed time from result data
proc extract_elapsed_time {result_data} {
    # HammerDB result format: "Completed 1 query set(s) in 3812 seconds"
    # This is the most reliable way to get timing data

    # Try to match "Completed X query set(s) in Y seconds"
    if {[regexp {Completed\s+\d+\s+query set\(s\)\s+in\s+([0-9]+)\s+seconds} $result_data match elapsed]} {
        return $elapsed
    }

    # Alternative: Try to match "elapsed X seconds" or "X seconds elapsed"
    if {[regexp {elapsed\s+([0-9]+\.?[0-9]*)\s+seconds} $result_data match elapsed]} {
        return $elapsed
    }

    # Alternative: Try to match "Total elapsed: X" or similar
    if {[regexp {Total elapsed:\s+([0-9]+\.?[0-9]*)} $result_data match elapsed]} {
        return $elapsed
    }

    # If no pattern matched, return 0
    return 0
}

# Procedure to calculate QphH (Queries per Hour @ Scale Factor)
proc calculate_qphh {elapsed_seconds scale_factor} {
    if {$elapsed_seconds <= 0} {
        return 0
    }

    # TPC-H QphH = (22 queries / elapsed_seconds) * 3600 seconds/hour * scale_factor
    # Standard formula: QphH@SF = (3600 / elapsed_time) * scale_factor
    # For a single query set (22 queries), this represents queries per hour
    set qphh [expr {(3600.0 / $elapsed_seconds) * $scale_factor}]
    return [format "%.2f" $qphh]
}

# Procedure to extract per-query timing from result data
proc extract_query_times {result_data} {
    # HammerDB logs queries in format: "Vuser 1:query 14 completed in 61.676 seconds"
    # Return a dict mapping query number to elapsed time

    array set query_times {}

    # Match pattern: "query X completed in Y seconds"
    foreach line [split $result_data "\n"] {
        if {[regexp {query\s+(\d+)\s+completed in\s+([0-9]+\.?[0-9]*)\s+seconds} $line match query_num elapsed]} {
            set query_times($query_num) $elapsed
        }
    }

    return [array get query_times]
}

# Main script execution
set tmpdir $::env(TMPDIR)
set ::outputfile  $tmpdir/oracle_tproch
set filename $::outputfile

set jobid [getjobid $filename]

if {$jobid eq ""} {
    puts "ERROR: Job ID not found in the output file."
    exit 1
}

# Get scale factor from environment (default to 1 if not set)
if {[info exists ::env(TPROCH_SCALE_FACTOR)]} {
    set scale_factor $::env(TPROCH_SCALE_FACTOR)
} else {
    set scale_factor 1
}

set output_filename [file normalize "${filename}_${jobid}.out"]

# IMPORTANT: HammerDB prints job results to stdout before our script runs
# The job object itself is empty, so we need to read from the log file where stdout was captured

# Try to read the hammerdb log file which should contain the output
set log_file "/tmp/hammerdb.log"
set result_string ""

if {[file exists $log_file]} {
    set fd [open $log_file r]
    set result_string [read $fd]
    close $fd
} else {
    puts "WARNING: Log file not found at $log_file"
}

# Extract elapsed time from result data and calculate QphH
set elapsed_seconds [extract_elapsed_time $result_string]
set qphh [calculate_qphh $elapsed_seconds $scale_factor]

# Extract per-query timing data
array set query_times_array [extract_query_times $result_string]

# For reference - also get timing data (likely empty but shown for completeness)
set timing_data [job $jobid timing]

# Open the file for writing
set fileId [open $output_filename "w"]

# Write to the file
puts $fileId "TPC-H QUERY EXECUTION RESULTS FOR ORACLE"
puts $fileId "=========================================="
puts $fileId ""
puts $fileId "PERFORMANCE METRICS"
puts $fileId "-------------------"
puts $fileId "Total Elapsed Time: $elapsed_seconds seconds"
puts $fileId "Scale Factor: $scale_factor"
puts $fileId "QphH@$scale_factor: $qphh"
puts $fileId ""
puts $fileId "PER-QUERY TIMING (SECONDS)"
puts $fileId "-------------------------"

# Sort queries numerically and display
set query_nums [lsort -integer [array names query_times_array]]
if {[llength $query_nums] > 0} {
    foreach query_num $query_nums {
        set query_time $query_times_array($query_num)
        puts $fileId [format "Query %2d: %8.3f seconds" $query_num $query_time]
    }
} else {
    puts $fileId "No per-query timing data found in logs"
}

puts $fileId ""
puts $fileId "QUERY TIMING RESULTS (from job object)"
puts $fileId "---------------------------------------"
puts $fileId $timing_data
puts $fileId ""
puts $fileId "HAMMERDB RESULT SUMMARY"
puts $fileId "-----------------------"
puts $fileId $result_string

# Close the file
close $fileId

# Print the output to the console
set output [exec cat $output_filename]
puts $output

# Also output the QphH metric in a parseable format for aggregation
puts ""
puts "=== TPC-H PERFORMANCE SUMMARY ==="
puts "Elapsed Time: $elapsed_seconds seconds"
puts "QphH@$scale_factor: $qphh"
puts ""
puts "Per-Query Timing:"
if {[llength $query_nums] > 0} {
    foreach query_num $query_nums {
        set query_time $query_times_array($query_num)
        puts [format "  Query %2d: %8.3f seconds" $query_num $query_time]
    }
} else {
    puts "  No per-query data available"
}
puts "================================="
