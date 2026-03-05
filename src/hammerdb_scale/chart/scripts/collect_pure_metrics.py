#!/usr/bin/env python3
"""
Pure Storage FlashArray Metrics Collector
Collects array-level performance metrics using REST API 2.x

Usage:
    python3 collect_pure_metrics.py --host 10.21.158.110 --token YOUR_TOKEN --duration 60
"""

import argparse
import json
import logging
import os
import signal
import sys
import time
import urllib3
from datetime import datetime, timezone
from typing import Dict, List, Optional

try:
    import requests
except ImportError:
    print("ERROR: 'requests' module not found. Install with: pip install requests")
    sys.exit(1)

# Disable SSL warnings if needed
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


class PureStorageCollector:
    """Simple Pure Storage FlashArray performance metrics collector."""

    def __init__(
        self,
        array_host: str,
        api_token: str,
        poll_interval: int = 5,
        verify_ssl: bool = False,
        api_version: str = "2.4",
    ):
        """
        Initialize the collector.

        Args:
            array_host: FlashArray management IP or hostname
            api_token: API token for authentication
            poll_interval: Seconds between polls (default: 5)
            verify_ssl: Verify SSL certificates (default: False)
            api_version: REST API version (default: 2.4)
        """
        self.array_host = array_host.strip()
        self.api_token = api_token.strip()
        self.poll_interval = poll_interval
        self.verify_ssl = verify_ssl
        self.api_version = api_version

        # Build base URL
        self.base_url = f"https://{self.array_host}/api/{self.api_version}"

        # Storage for metrics
        self.metrics_data: List[Dict] = []
        self.running = False
        self.session_token = None

        logger.info(f"Initialized Pure Storage collector for {self.array_host}")
        logger.info(f"API Version: {self.api_version}")
        logger.info(f"Poll Interval: {self.poll_interval}s")

        if not self.verify_ssl:
            logger.warning(
                "SSL certificate verification is DISABLED - not recommended for production"
            )

    def login(self) -> bool:
        """
        Login to Pure Storage array and get session token.

        Returns:
            True if successful, False otherwise
        """
        logger.info("Logging in to Pure Storage array...")

        try:
            response = requests.post(
                f"{self.base_url}/login",
                headers={
                    "api-token": self.api_token,
                    "Content-Type": "application/json",
                },
                verify=self.verify_ssl,
                timeout=10,
            )

            if response.status_code == 200:
                self.session_token = response.headers.get("x-auth-token")
                if self.session_token:
                    logger.info("Login successful")
                    return True
                else:
                    logger.error("No x-auth-token in login response")
                    return False
            else:
                logger.error(
                    f"Login failed - HTTP {response.status_code}: {response.text}"
                )
                return False

        except requests.exceptions.RequestException as e:
            logger.error(f"Login request error: {e}")
            return False

    def _make_request(self, endpoint: str, method: str = "GET") -> Optional[Dict]:
        """
        Make HTTP request to Pure Storage API.

        Args:
            endpoint: API endpoint (e.g., "/arrays/performance")
            method: HTTP method (default: GET)

        Returns:
            JSON response as dict, or None on error
        """
        if not self.session_token:
            logger.error("No session token. Call login() first.")
            return None

        url = f"{self.base_url}{endpoint}"
        headers = {
            "x-auth-token": self.session_token,
            "Content-Type": "application/json",
        }

        try:
            response = requests.request(
                method=method,
                url=url,
                headers=headers,
                verify=self.verify_ssl,
                timeout=10,
            )
            response.raise_for_status()
            return response.json()

        except requests.exceptions.HTTPError as e:
            logger.error(f"HTTP error for {endpoint}: {e}")
            if hasattr(e.response, "text"):
                logger.error(f"Response: {e.response.text}")
            return None
        except requests.exceptions.RequestException as e:
            logger.error(f"Request error for {endpoint}: {e}")
            return None
        except json.JSONDecodeError as e:
            logger.error(f"JSON decode error for {endpoint}: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error for {endpoint}: {e}")
            return None

    def test_connection(self) -> bool:
        """
        Test connection and authentication to the array.

        Returns:
            True if successful, False otherwise
        """
        logger.info("Testing connection to Pure Storage array...")

        # First login
        if not self.login():
            logger.error("Failed to login to Pure Storage array")
            return False

        # Then test with a simple API call
        result = self._make_request("/arrays")

        if result and "items" in result and len(result["items"]) > 0:
            array_info = result["items"][0]
            logger.info(
                f"Successfully connected to array: {array_info.get('name', 'Unknown')}"
            )
            logger.info(f"Array ID: {array_info.get('id', 'Unknown')}")
            return True
        else:
            logger.error("Failed to get array information")
            return False

    def collect_array_performance(self) -> Optional[Dict]:
        """
        Collect array-level performance metrics.

        Returns:
            Dict with performance metrics or None if failed
        """
        result = self._make_request("/arrays/performance")

        if not result or "items" not in result or len(result["items"]) == 0:
            logger.error("No performance data returned from array")
            return None

        perf = result["items"][0]

        # Extract and calculate metrics
        read_iops = perf.get("reads_per_sec", 0)
        write_iops = perf.get("writes_per_sec", 0)
        read_bw_bytes = perf.get("read_bytes_per_sec", 0)
        write_bw_bytes = perf.get("write_bytes_per_sec", 0)

        # Calculate average block sizes (avoid division by zero)
        avg_read_block_kb = (read_bw_bytes / read_iops / 1024) if read_iops > 0 else 0
        avg_write_block_kb = (
            (write_bw_bytes / write_iops / 1024) if write_iops > 0 else 0
        )

        metrics = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "read_latency_us": perf.get("usec_per_read_op", 0),
            "write_latency_us": perf.get("usec_per_write_op", 0),
            "read_iops": read_iops,
            "write_iops": write_iops,
            "read_bandwidth_mbps": read_bw_bytes / (1024 * 1024),
            "write_bandwidth_mbps": write_bw_bytes / (1024 * 1024),
            "avg_read_block_size_kb": avg_read_block_kb,
            "avg_write_block_size_kb": avg_write_block_kb,
            "queue_depth": perf.get("queue_depth", 0),
        }

        return metrics

    def start_collection(self, duration: int):
        """
        Start collecting metrics for specified duration.

        Args:
            duration: Collection duration in seconds
        """
        logger.info(f"Starting metrics collection for {duration} seconds...")

        if not self.test_connection():
            logger.error("Connection test failed. Exiting.")
            sys.exit(1)

        self.running = True
        start_time = time.time()
        end_time = start_time + duration
        collection_count = 0

        # Handle SIGTERM for graceful early stop (sent by entrypoint when benchmark finishes)
        def _handle_sigterm(signum, frame):
            logger.info("Received SIGTERM — finishing collection")
            self.running = False

        signal.signal(signal.SIGTERM, _handle_sigterm)

        try:
            while self.running and time.time() < end_time:
                metrics = self.collect_array_performance()

                if metrics:
                    self.metrics_data.append(metrics)
                    collection_count += 1
                    logger.info(
                        f"Sample #{collection_count}: "
                        f"R:{metrics['read_iops']:.0f} IOPS "
                        f"W:{metrics['write_iops']:.0f} IOPS "
                        f"R_lat:{metrics['read_latency_us']:.0f}µs "
                        f"W_lat:{metrics['write_latency_us']:.0f}µs"
                    )
                else:
                    logger.warning(
                        f"Failed to collect metrics (attempt {collection_count + 1})"
                    )

                # Sleep until next collection
                remaining = end_time - time.time()
                if remaining <= 0:
                    break
                sleep_time = min(self.poll_interval, remaining)
                time.sleep(sleep_time)

        except KeyboardInterrupt:
            logger.info("Collection interrupted by user")
        finally:
            self.running = False
            actual_duration = time.time() - start_time
            logger.info(
                f"Collection complete. Gathered {collection_count} samples "
                f"over {actual_duration:.1f} seconds"
            )

    def get_summary_statistics(self) -> Dict:
        """
        Calculate summary statistics from collected metrics.

        Returns:
            Dict with min, max, average, and percentile statistics
        """
        if not self.metrics_data:
            return {}

        def calc_stats(values: List[float]) -> Dict:
            """Calculate statistics for a list of values."""
            if not values:
                return {"min": 0, "max": 0, "avg": 0, "p95": 0, "p99": 0}

            sorted_vals = sorted(values)
            count = len(sorted_vals)

            # Calculate percentile indices
            p95_idx = int(count * 0.95)
            p99_idx = int(count * 0.99)

            return {
                "min": sorted_vals[0],
                "max": sorted_vals[-1],
                "avg": sum(sorted_vals) / count,
                "p95": sorted_vals[p95_idx] if p95_idx < count else sorted_vals[-1],
                "p99": sorted_vals[p99_idx] if p99_idx < count else sorted_vals[-1],
            }

        # Extract metric lists
        read_lat = [m["read_latency_us"] for m in self.metrics_data]
        write_lat = [m["write_latency_us"] for m in self.metrics_data]
        read_iops = [m["read_iops"] for m in self.metrics_data]
        write_iops = [m["write_iops"] for m in self.metrics_data]
        read_bw = [m["read_bandwidth_mbps"] for m in self.metrics_data]
        write_bw = [m["write_bandwidth_mbps"] for m in self.metrics_data]
        read_block = [m["avg_read_block_size_kb"] for m in self.metrics_data]
        write_block = [m["avg_write_block_size_kb"] for m in self.metrics_data]

        # Calculate statistics
        read_lat_stats = calc_stats(read_lat)
        write_lat_stats = calc_stats(write_lat)
        read_iops_stats = calc_stats(read_iops)
        write_iops_stats = calc_stats(write_iops)
        read_bw_stats = calc_stats(read_bw)
        write_bw_stats = calc_stats(write_bw)
        read_block_stats = calc_stats(read_block)
        write_block_stats = calc_stats(write_block)

        return {
            "source": "array",
            "source_name": self.array_host,
            "sample_count": len(self.metrics_data),
            "read_latency_us_min": read_lat_stats["min"],
            "read_latency_us_max": read_lat_stats["max"],
            "read_latency_us_avg": read_lat_stats["avg"],
            "read_latency_us_p95": read_lat_stats["p95"],
            "read_latency_us_p99": read_lat_stats["p99"],
            "write_latency_us_min": write_lat_stats["min"],
            "write_latency_us_max": write_lat_stats["max"],
            "write_latency_us_avg": write_lat_stats["avg"],
            "write_latency_us_p95": write_lat_stats["p95"],
            "write_latency_us_p99": write_lat_stats["p99"],
            "read_iops_min": read_iops_stats["min"],
            "read_iops_max": read_iops_stats["max"],
            "read_iops_avg": read_iops_stats["avg"],
            "write_iops_min": write_iops_stats["min"],
            "write_iops_max": write_iops_stats["max"],
            "write_iops_avg": write_iops_stats["avg"],
            "read_bandwidth_mbps_min": read_bw_stats["min"],
            "read_bandwidth_mbps_max": read_bw_stats["max"],
            "read_bandwidth_mbps_avg": read_bw_stats["avg"],
            "write_bandwidth_mbps_min": write_bw_stats["min"],
            "write_bandwidth_mbps_max": write_bw_stats["max"],
            "write_bandwidth_mbps_avg": write_bw_stats["avg"],
            "avg_read_block_size_kb_min": read_block_stats["min"],
            "avg_read_block_size_kb_max": read_block_stats["max"],
            "avg_read_block_size_kb_avg": read_block_stats["avg"],
            "avg_write_block_size_kb_min": write_block_stats["min"],
            "avg_write_block_size_kb_max": write_block_stats["max"],
            "avg_write_block_size_kb_avg": write_block_stats["avg"],
        }

    def save_results(self, output_file: str):
        """
        Save collected metrics and summary to JSON file.

        Args:
            output_file: Path to output JSON file
        """
        results = {
            "metadata": {
                "array_host": self.array_host,
                "poll_interval_sec": self.poll_interval,
                "api_version": self.api_version,
            },
            "summary": self.get_summary_statistics(),
            "raw_metrics": self.metrics_data,
        }

        try:
            output_dir = os.path.dirname(output_file)
            if output_dir:
                os.makedirs(output_dir, exist_ok=True)

            with open(output_file, "w") as f:
                json.dump(results, f, indent=2)
            logger.info(f"Results saved to {output_file}")
        except Exception as e:
            logger.error(f"Failed to save results: {e}")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Collect Pure Storage FlashArray performance metrics",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Collect array-level metrics for 60 seconds
  %(prog)s --host 10.21.158.110 --token abc123 --duration 60

  # Use environment variables for credentials
  export PURE_HOST=10.21.158.110
  export PURE_API_TOKEN=abc123
  %(prog)s --duration 60 --output /tmp/metrics.json
        """,
    )

    parser.add_argument(
        "--host",
        default=os.getenv("PURE_HOST"),
        help="FlashArray management IP or hostname (or set PURE_HOST env var)",
    )
    parser.add_argument(
        "--token",
        default=os.getenv("PURE_API_TOKEN"),
        help="API token for authentication (or set PURE_API_TOKEN env var)",
    )
    parser.add_argument(
        "--duration",
        type=int,
        default=int(os.getenv("PURE_DURATION", "60")),
        help="Collection duration in seconds (default: 60)",
    )
    parser.add_argument(
        "--interval",
        type=int,
        default=int(os.getenv("PURE_INTERVAL", "5")),
        help="Polling interval in seconds (default: 5)",
    )
    parser.add_argument(
        "--output",
        default=os.getenv("PURE_OUTPUT", "pure_metrics.json"),
        help="Output JSON file path (default: pure_metrics.json)",
    )
    parser.add_argument(
        "--no-verify-ssl",
        action="store_true",
        default=os.getenv("PURE_NO_VERIFY_SSL", "").lower() in ("true", "1", "yes"),
        help="Disable SSL certificate verification",
    )
    parser.add_argument(
        "--api-version",
        default=os.getenv("PURE_API_VERSION", "2.4"),
        help="Pure Storage REST API version (default: 2.4)",
    )
    parser.add_argument("--verbose", action="store_true", help="Enable verbose logging")

    args = parser.parse_args()

    # Validate required arguments
    if not args.host:
        parser.error("--host is required (or set PURE_HOST environment variable)")
    if not args.token:
        parser.error("--token is required (or set PURE_API_TOKEN environment variable)")

    # Set log level
    if args.verbose:
        logger.setLevel(logging.DEBUG)

    # Create collector
    collector = PureStorageCollector(
        array_host=args.host,
        api_token=args.token,
        poll_interval=args.interval,
        verify_ssl=not args.no_verify_ssl,
        api_version=args.api_version,
    )

    # Start collection
    try:
        collector.start_collection(args.duration)
        collector.save_results(args.output)

        # Print summary
        summary = collector.get_summary_statistics()
        if summary:
            print("\n" + "=" * 60)
            print("PURE STORAGE PERFORMANCE SUMMARY")
            print("=" * 60)
            print(f"Source: {summary['source']} - {summary['source_name']}")
            print(f"Samples: {summary['sample_count']}")
            print(
                f"\nRead Latency (µs):  avg={summary.get('read_latency_us_avg', 0):.0f} "
                f"p95={summary.get('read_latency_us_p95', 0):.0f} "
                f"p99={summary.get('read_latency_us_p99', 0):.0f}"
            )
            print(
                f"Write Latency (µs): avg={summary.get('write_latency_us_avg', 0):.0f} "
                f"p95={summary.get('write_latency_us_p95', 0):.0f} "
                f"p99={summary.get('write_latency_us_p99', 0):.0f}"
            )
            print(
                f"\nRead IOPS:  avg={summary.get('read_iops_avg', 0):.0f} "
                f"max={summary.get('read_iops_max', 0):.0f}"
            )
            print(
                f"Write IOPS: avg={summary.get('write_iops_avg', 0):.0f} "
                f"max={summary.get('write_iops_max', 0):.0f}"
            )
            print(
                f"\nRead BW (MB/s):  avg={summary.get('read_bandwidth_mbps_avg', 0):.1f} "
                f"max={summary.get('read_bandwidth_mbps_max', 0):.1f}"
            )
            print(
                f"Write BW (MB/s): avg={summary.get('write_bandwidth_mbps_avg', 0):.1f} "
                f"max={summary.get('write_bandwidth_mbps_max', 0):.1f}"
            )
            print(
                f"\nAvg Read Block (KB):  {summary.get('avg_read_block_size_kb_avg', 0):.1f}"
            )
            print(
                f"Avg Write Block (KB): {summary.get('avg_write_block_size_kb_avg', 0):.1f}"
            )
            print("=" * 60)
        else:
            logger.warning("No metrics collected")
            sys.exit(1)

    except Exception as e:
        logger.error(f"Collection failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
