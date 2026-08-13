#!/usr/bin/env python3
"""Package the host-verified Raspberry Pi 5 nvme_pcie payload."""

import argparse
import datetime
import hashlib
import os
import pathlib
import sys
import tempfile


VERSION = "1.2.4.15-2vmw.803.0.55.24449057"
PAYLOAD_SHA256 = "3124752b5e65d323fa6912cb9c6c796e98d05fdf9627cca00d1b3070843333aa"


def sha256(path):
    digest = hashlib.sha256()
    with open(path, "rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--esximage", required=True)
    parser.add_argument("--payload", required=True)
    parser.add_argument("--output-dir", required=True)
    args = parser.parse_args()

    if sha256(args.payload) != PAYLOAD_SHA256:
        raise RuntimeError("refusing unexpected nvme_pci.v00 payload")

    sys.path.insert(0, args.esximage)
    from vmware.esximage import OfflineBundle, Version, Vib

    output_dir = os.path.abspath(args.output_dir)
    os.makedirs(output_dir, exist_ok=True)
    stem = f"nvme-pcie-rpi5-{VERSION}"
    vib_path = os.path.join(output_dir, stem + "-community.vib")
    bundle_path = os.path.join(output_dir, stem + "-offline-bundle.zip")
    descriptor_path = os.path.join(output_dir, "descriptor.xml")

    vib = Vib.ArFileVib(
        name="nvme-pcie",
        version=Version.VibVersion.fromstring(VERSION),
        vendor="Soulveig",
        summary="NVMe completion-path adaptation for Raspberry Pi 5",
        description=(
            "Build-specific adaptation of the ESXi-Arm nvme_pcie transport "
            "for Raspberry Pi 5 external PCIe. Uses bounded completion "
            "processing because MSI-X and legacy INTx delivery are unavailable "
            "on the validated ACPI/firmware path. Targets ESXi-Arm 8.0U3c "
            "build 24449057 only."
        ),
        releasedate=datetime.datetime.now(datetime.timezone.utc),
        depends=[Vib.VibRelation("vmkapi_3_0_0_0")],
        swtags=["RestrictStickyFiles", "module", "driver", "sdkversion:8.0.3-24449057"],
        acceptancelevel=Vib.ArFileVib.ACCEPTANCE_COMMUNITY,
        maintenancemode=Vib.MaintenanceMode(remove=True, install=True),
        swplatforms=[("8.0", "", Vib.SoftwarePlatform.PRODUCT_EMBEDDEDESX)],
        liveinstallok=False,
        liveremoveok=False,
        cimomrestart=False,
        statelessready=True,
        overlay=False,
    )
    payload = Vib.Payload("nvme_pci.vgz", Vib.Payload.TYPE_VGZ, vfatname="nvme_pci.v00")
    vib.AddPayload(payload, args.payload)
    vib.packedsize = os.path.getsize(args.payload)
    vib.WriteVibFile(vib_path)
    pathlib.Path(descriptor_path).write_text(vib.GetDescriptorText() + "\n", encoding="utf-8")

    if os.path.exists(bundle_path):
        os.unlink(bundle_path)
    vib.relativepath = os.path.basename(vib_path)
    vib.remotelocations = [pathlib.Path(vib_path).resolve().as_uri()]
    OfflineBundle.WriteOfflineBundle(
        bundle_path,
        vendorName="Soulveig Raspberry Pi 5 Native Drivers",
        vendorCode="SOULVEIG",
        baseimages={}, addons={}, manifests={}, solutions={}, profiles=[], components={},
        vibs={vib.id: vib}, versions=["8.0.3-24449057"], checkAcceptance=False,
        products=[Vib.SoftwarePlatform.PRODUCT_EMBEDDEDESX],
    )

    with tempfile.TemporaryDirectory(prefix="nvme-vib-check-") as workdir:
        extracted = os.path.join(workdir, "nvme_pci.vgz")
        import subprocess
        with open(extracted, "wb") as output:
            subprocess.run(["ar", "-p", vib_path, "nvme_pci.vgz"], check=True, stdout=output)
        if sha256(extracted) != PAYLOAD_SHA256:
            raise RuntimeError("repacked VIB changed nvme_pci.vgz")

    print(vib_path)
    print(bundle_path)
    print("vib_sha256=" + sha256(vib_path))
    print("bundle_sha256=" + sha256(bundle_path))


if __name__ == "__main__":
    main()
