#!/usr/bin/env python3
"""Add bounded adaptive IO-CQ draining to the hybrid one-shot image.

The lifecycle timer scans every active IO completion queue once.  It repeats
the complete scan only when the preceding scan consumed at least one entry,
and stops after eight scans.  Thus an idle timer does one bounded pass and the
submission path never spins waiting for a completion.
"""

from __future__ import annotations

import argparse
import hashlib
import struct
from pathlib import Path

from patch_admin_polling import elf_sections, symbol_maps


EXPECTED_SHA256 = {
    # Hybrid admin-inline / IO timer baseline.
    "1af83a9c794f270554b802c8641b82ab90fb26ca1bd8625aece807389b412c73",
    # The same baseline with one post-submission IO-CQ pass.
    "a76bbe493ee8006ff09a3a7a02428101632c2188480f889df3922924073935b7",
}
STUB = bytes.fromhex(
    "f353bca9f55b01a9f76302a9f97b03a9"
    "f60300aad54240b93503003419018052"
    "18008052d45e40f99442019133008052"
    "800640b91f08007141010054801240f9"
    "000040f900000094e00314aa00000094"
    "1803000b801240f9000040f900000094"
    "94420191730600117f02156b29feff54"
    "780000343907007141fdff54f97b43a9"
    "f76342a9f55b41a9f353c4a8c0035fd6"
)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("input", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()

    original = args.input.read_bytes()
    digest = hashlib.sha256(original).hexdigest()
    if digest not in EXPECTED_SHA256:
        raise SystemExit(f"refusing unexpected input SHA-256: {digest}")

    sections, _ = elf_sections(original)
    text = next(sec for sec in sections if sec["name"] == ".text")
    rela = next(sec for sec in sections if sec["name"] == ".rela.text")
    by_name, by_index = symbol_maps(original, sections)
    patched = bytearray(original)

    stub_pos = text["offset"] + 0x4840
    if original[stub_pos : stub_pos + 4] != bytes.fromhex("f353bda9"):
        raise SystemExit("unexpected hybrid timer-handler prefix")
    patched[stub_pos : stub_pos + len(STUB)] = STUB

    moves = {
        0x4874: (0x4884, "vmk_SpinlockLock"),
        0x487C: (0x488C, "NVMEPCIEProcessCq"),
        0x4888: (0x489C, "vmk_SpinlockUnlock"),
    }
    found: set[int] = set()
    count = rela["size"] // rela["entsize"]
    for index in range(count):
        pos = rela["offset"] + index * rela["entsize"]
        target, info = struct.unpack_from("<QQ", original, pos)
        if target not in moves:
            continue
        new_target, expected_name = moves[target]
        sym_index = info >> 32
        rel_type = info & 0xFFFFFFFF
        if by_index.get(sym_index, "") != expected_name or rel_type != 283:
            raise SystemExit(f"unexpected relocation at 0x{target:x}")
        struct.pack_into("<Q", patched, pos, new_target)
        struct.pack_into("<Q", patched, pos + 8, (by_name[expected_name] << 32) | rel_type)
        found.add(target)

    if found != set(moves):
        raise SystemExit(f"missing moved relocations: {set(moves) - found}")

    args.output.write_bytes(patched)
    print(f"input_sha256={digest}")
    print("adaptive_round_limit=8")
    print(f"output_sha256={hashlib.sha256(patched).hexdigest()}")


if __name__ == "__main__":
    main()
