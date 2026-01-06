"""
Flacfetch VM resources.

Manages the VM instance for the flacfetch audio download service,
including static IP and firewall rules.
"""

import pulumi
from pulumi_gcp import compute, storage, serviceaccount

from config import REGION, ZONE, MachineTypes, DiskSizes
from .startup_scripts import read_script


def create_flacfetch_ip() -> compute.Address:
    """
    Create static IP for flacfetch.

    This IP is whitelisted on private trackers, so it must remain stable.

    Returns:
        compute.Address: The static IP resource.
    """
    return compute.Address(
        "flacfetch-ip",
        name="flacfetch-static-ip",
        region=REGION,
        address_type="EXTERNAL",
        description="Static IP for flacfetch service (torrent downloads)",
    )


def create_flacfetch_vm(
    ip: compute.Address,
    service_account: serviceaccount.Account,
    bucket: storage.Bucket,
) -> compute.Instance:
    """
    Create the flacfetch VM instance.

    Args:
        ip: The static IP address for the VM.
        service_account: The flacfetch service account.
        bucket: The GCS bucket for storing downloaded files.

    Returns:
        compute.Instance: The VM instance resource.
    """
    startup_script = read_script("flacfetch.sh")

    return compute.Instance(
        "flacfetch-service",
        name="flacfetch-service",
        machine_type=MachineTypes.FLACFETCH,
        zone=ZONE,
        boot_disk=compute.InstanceBootDiskArgs(
            initialize_params=compute.InstanceBootDiskInitializeParamsArgs(
                image="debian-cloud/debian-12",
                size=DiskSizes.FLACFETCH,
                type="pd-ssd",
            ),
        ),
        network_interfaces=[compute.InstanceNetworkInterfaceArgs(
            network="default",
            access_configs=[compute.InstanceNetworkInterfaceAccessConfigArgs(
                nat_ip=ip.address,
            )],
        )],
        service_account=compute.InstanceServiceAccountArgs(
            email=service_account.email,
            scopes=["cloud-platform"],
        ),
        metadata_startup_script=startup_script,
        metadata={
            "gcs-bucket": bucket.name,
        },
        tags=["flacfetch-service"],
        allow_stopping_for_update=True,
    )


def create_flacfetch_firewall() -> compute.Firewall:
    """
    Create firewall rules for flacfetch.

    Opens ports for:
    - 51413 TCP/UDP: BitTorrent peer connections
    - 8080 TCP: HTTP API

    Returns:
        compute.Firewall: The firewall resource.
    """
    return compute.Firewall(
        "flacfetch-firewall",
        name="flacfetch-firewall",
        network="default",
        allows=[
            compute.FirewallAllowArgs(protocol="tcp", ports=["51413"]),
            compute.FirewallAllowArgs(protocol="udp", ports=["51413"]),
            compute.FirewallAllowArgs(protocol="tcp", ports=["8080"]),
        ],
        source_ranges=["0.0.0.0/0"],
        target_tags=["flacfetch-service"],
        description="Firewall rules for flacfetch torrent/API service",
    )
