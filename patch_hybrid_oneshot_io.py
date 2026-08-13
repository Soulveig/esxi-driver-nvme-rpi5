#!/usr/bin/env python3
"""Add one serialized IO-CQ pass after each async submission.

The input is the verified hybrid admin-inline/IO-timer image.  Admin polling
is retained.  For an IO queue, the patched handler takes the existing queue
lock, calls the stock CQ processor once, unlocks, and returns.  The periodic
timer remains the fallback; there is no retry or busy-poll loop for IO.

This experiment requires vmknvme_compl_world_type=1 so an early completion is
queued to NVMECompletionWorld instead of relying on a waiter already sleeping.
"""

from __future__ import annotations

import argparse
import hashlib
import struct
from pathlib import Path

from patch_admin_polling import elf_sections, symbol_maps


EXPECTED_SHA256 = "1af83a9c794f270554b802c8641b82ab90fb26ca1bd8625aece807389b412c73"
STUB = bytes.fromhex(
    "f353bea9fe0b00f9f30303aa600240b940010034"
    "601240f9000040f900000094e00313aa00000094"
    "601240f9000040f90000009408000014"
    "14488852f401a072e00313aa0000009460000035"
    "9406007181ffff546322009100008052fe0b40f9"
    "f353c2a8c0035fd6"
)


def direct_bl(source: int, target: int) -> bytes:
    delta = target - source
    if delta % 4 or not -(1 << 27) <= delta < (1 << 27):
        raise ValueError("BL target out of range")
    return struct.pack("<I", 0x94000000 | ((delta // 4) & 0x03FFFFFF))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("input", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()

    original = args.input.read_bytes()
    digest = hashlib.sha256(original).hexdigest()
    if digest != EXPECTED_SHA256:
        raise SystemExit(f"refusing unexpected input SHA-256: {digest}")

    sections, _ = elf_sections(original)
    text = next(s for s in sections if s["name"] == ".text")
    rela = next(s for s in sections if s["name"] == ".rela.text")
    by_name, by_index = symbol_maps(original, sections)
    patched = bytearray(original)

    stub_pos = text["offset"] + 0x4E70
    if original[stub_pos : stub_pos + 4] != bytes.fromhex("f353bea9"):
        raise SystemExit("unexpected hybrid PollHandler prefix")
    patched[stub_pos : stub_pos + len(STUB)] = STUB
    # Local calls are position-relative and remain valid when the module loads.
    patched[text["offset"] + 0x4E94 : text["offset"] + 0x4E98] = direct_bl(0x4E94, 0x2E10)
    patched[text["offset"] + 0x4EB4 : text["offset"] + 0x4EB8] = direct_bl(0x4EB4, 0x2E10)

    moved_lock = False
    restored_wait_slot = False
    count = rela["size"] // rela["entsize"]
    for index in range(count):
        pos = rela["offset"] + index * rela["entsize"]
        target, info = struct.unpack_from("<QQ", original, pos)
        sym_index = info >> 32
        rel_type = info & 0xFFFFFFFF
        name = by_index.get(sym_index, "")
        if target == 0x4E90 and name == "NVMEPCIEProcessCq" and rel_type == 283:
            struct.pack_into("<Q", patched, pos, 0x4E8C)
            struct.pack_into("<Q", patched, pos + 8, (by_name["vmk_SpinlockLock"] << 32) | 283)
            moved_lock = True
        elif target == 0x18C0 and info == 0:
            struct.pack_into("<Q", patched, pos, 0x4EA0)
            struct.pack_into("<Q", patched, pos + 8, (by_name["vmk_SpinlockUnlock"] << 32) | 283)
            restored_wait_slot = True

    if not moved_lock or not restored_wait_slot:
        raise SystemExit("required relocation slots were not found")

    args.output.write_bytes(patched)
    print(f"input_sha256={digest}")
    print(f"output_sha256={hashlib.sha256(patched).hexdigest()}")


if __name__ == "__main__":
    main()
