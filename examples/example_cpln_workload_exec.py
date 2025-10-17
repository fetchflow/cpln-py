#!/usr/bin/env python3
"""
Example script demonstrating how to list and inspect workloads using the CPLN Python client.
"""

import sys

import cpln
from cpln.exceptions import CPLNError
from cpln.models.workloads import Workload


def get_cpln_client() -> cpln.CPLNClient:
    """
    Initialize and return a CPLN client using environment variables.

    Returns:
        cpln.CPLNClient: An authenticated CPLN client instance

    Raises:
        cpln.exceptions.CPLNError: If client initialization fails
    """
    try:
        # First create client from environment variables
        client = cpln.CPLNClient.from_env()
        # print(client.api.config.token)
        print(client.api.config.org)

        # Then create a new client with explicit configuration
        client = cpln.CPLNClient(
            token=client.api.config.token,
            org=client.api.config.org,
        )
        return client
    except CPLNError as e:
        print(f"Failed to initialize CPLN client: {e}", file=sys.stderr)
        raise


def list_workloads(client: cpln.CPLNClient, gvc: str) -> list[Workload]:
    """
    List all workloads in a specified GVC.

    Args:
        client: Authenticated CPLN client
        gvc: GVC name to list workloads from

    Returns:
        List[Workload]: List of workload objects

    Raises:
        cpln.exceptions.CPLNError: If workload listing fails
    """
    try:
        return client.workloads.list(gvc=gvc)
    except CPLNError as e:
        print(f"Failed to list workloads: {e}", file=sys.stderr)
        raise


def main() -> None:
    """Main function to demonstrate workload operations."""
    try:
        # Initialize client
        client = get_cpln_client()
        print("CPLN Client initialized successfully")

        # List workloads
        gvc_name = "david"  # You might want to make this configurable

        # Check if the user provided a GVC name as command line argument
        if len(sys.argv) > 1:
            gvc_name = sys.argv[1]
        else:
            print(f"\nUsing default GVC name: {gvc_name}")
            print(f"You can specify a different GVC: python {sys.argv[0]} <gvc-name>")

        workloads = list_workloads(client, gvc_name)

        # Print workload information
        print(f"\nFound {len(workloads)} workloads in GVC '{gvc_name}':")
        for workload in workloads:
            print(f"  - {workload.name}")
        # for workload in workloads:
        #     print(f"\nWorkload: {workload.name}")

        #     # Get workload spec and containers using the proper API
        #     try:
        #         spec = workload.get_spec()
        #         print(f"Type: {spec.type}")

        #         containers = workload.get_containers()
        #         print(f"Containers: {len(containers)}")

        #         for i, container in enumerate(containers):
        #             print(f"  Container {i+1}: {container.name}")
        #             print(f"    Image: {container.image}")
        #             print(f"    CPU: {container.cpu}")
        #             print(f"    Memory: {container.memory}")
        #             if container.ports:
        #                 print(f"    Ports: {len(container.ports)}")
        #                 for port in container.ports:
        #                     print(f"      {port.number}/{port.protocol}")
        #             print(f"    Inherit Env: {container.inherit_env}")

        #     except Exception as e:
        #         print(f"Error getting spec/containers: {e}")
        #         # Fallback to raw data if parsing fails
        #         if "spec" in workload.attrs:
        #             spec_data = workload.attrs["spec"]
        #             print(f"Type: {spec_data.get('type', 'Unknown')}")
        #             if "containers" in spec_data:
        #                 print(f"Containers: {len(spec_data['containers'])} (raw data)")

        #     # Try to get status information if available in attrs
        #     if "status" in workload.attrs:
        #         status = workload.attrs["status"]
        #         if isinstance(status, dict):
        #             print(f"Status: {status.get('phase', 'Unknown')}")
        #         else:
        #             print(f"Status: {status}")
        #     else:
        #         print("Status: Not available (use deployment status for live status)")
            
        if workloads:
            workload_to_ping = workloads[-1]
            print(f"\nTesting ping on workload: {workload_to_ping.name}")
            result = workload_to_ping.ping(
                location = "aws-us-east-1",
                container="job-match-ai-api",
                replica_selector=0
            )
            print(f"Ping result: {result}")
        else:
            print("No workloads found to test ping")

    except CPLNError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    except KeyboardInterrupt:
        print("\nOperation cancelled by user", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
