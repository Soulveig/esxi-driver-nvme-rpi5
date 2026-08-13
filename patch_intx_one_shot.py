#!/usr/bin/env python3
"""Patch the stock ESXi nvme_pcie INTx handler to leave vector 0 masked.

This is a deliberately narrow diagnostic patch for build 24449057.  It replaces
the final legacy-INTx write to NVMe INTMC in NVMEPCIECtrlAdminqHandler with one
AArch64 NOP.  The ACK-side INTMS write and CQ processing remain unchanged.
"""

from __future__ import annotations

import argparse
import hashlib
import struct
from pathlib import Path


ELF_MAGIC = b"\x7fELF"
TARGET_TEXT_OFFSET = 0x3394
EXPECTED = bytes.fromhex("011000b9")  # str w1, [x0, #0x10]
REPLACEMENT = bytes.fromhex("1f2003d5")  # nop
EXPECTED_INPUT_SHA256 = (
    "b0eee6fde128c87ce651a528bedfa082a452141769e1caa6e0b345bf91d6a4d3"
)


def section_table(blob: bytes) -> dict[str, tuple[int, int]]:
    if blob[:4] != ELF_MAGIC or blob[4] != 2 or blob[5] != 1:
        raise ValueError("expected a 64-bit little-endian ELF")

    shoff = struct.unpack_from("<Q", blob, 0x28)[0]
    shentsize = struct.unpack_from("<H", blob, 0x3A)[0]
    shnum = struct.unpack_from("<H", blob, 0x3C)[0]
    shstrndx = struct.unpack_from("<H", blob, 0x3E)[0]
    if not shoff or shentsize != 64 or not shnum or shstrndx >= shnum:
        raise ValueError("invalid ELF section table")

    shstr = shoff + shstrndx * shentsize
    names_off = struct.unpack_from("<Q", blob, shstr + 0x18)[0]
    names_size = struct.unpack_from("<Q", blob, shstr + 0x20)[0]
    names = blob[names_off : names_off + names_size]

    result: dict[str, tuple[int, int]] = {}
    for index in range(shnum):
        header = shoff + index * shentsize
        name_index = struct.unpack_from("<I", blob, header)[0]
        file_offset = struct.unpack_from("<Q", blob, header + 0x18)[0]
        size = struct.unpack_from("<Q", blob, header + 0x20)[0]
        end = names.find(b"\0", name_index)
        if end < 0:
            raise ValueError("unterminated ELF section name")
        name = names[name_index:end].decode("ascii")
        result[name] = (file_offset, size)
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("input", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()

    original = args.input.read_bytes()
    digest = hashlib.sha256(original).hexdigest()
    if digest != EXPECTED_INPUT_SHA256:
        raise SystemExit(f"refusing unexpected input SHA-256: {digest}")

    sections = section_table(original)
    text_file_offset, text_size = sections[".text"]
    if TARGET_TEXT_OFFSET + len(EXPECTED) > text_size:
        raise SystemExit("target is outside .text")

    patch_at = text_file_offset + TARGET_TEXT_OFFSET
    actual = original[patch_at : patch_at + len(EXPECTED)]
    if actual != EXPECTED:
        raise SystemExit(
            f"refusing unexpected instruction at .text+0x{TARGET_TEXT_OFFSET:x}: "
            f"{actual.hex()}"
        )

    patched = bytearray(original)
    patched[patch_at : patch_at + len(REPLACEMENT)] = REPLACEMENT
    args.output.write_bytes(patched)

    changed = [i for i, (a, b) in enumerate(zip(original, patched)) if a != b]
    if changed != [patch_at, patch_at + 1, patch_at + 2, patch_at + 3]:
        raise SystemExit(f"unexpected changed offsets: {changed}")

    print(f"input_sha256={digest}")
    print(f"text_file_offset=0x{text_file_offset:x}")
    print(f"patch_file_offset=0x{patch_at:x}")
    print(f"old={EXPECTED.hex()} new={REPLACEMENT.hex()}")
    print(f"output_sha256={hashlib.sha256(patched).hexdigest()}")


if __name__ == "__main__":
    main()
