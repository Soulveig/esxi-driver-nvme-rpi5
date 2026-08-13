#!/usr/bin/env python3
"""Inline-poll admin CQ and asynchronously timer-poll active IO CQs.

Build-specific experiment for ESXi ARM 8.0U3c build 24449057. Early admin
commands must complete inline because the controller timer does not exist until
after vmk_NvmeRegisterController returns. IO submissions return without inline
CQ processing and are completed by the driver's lifecycle-managed periodic
timer, avoiding the upper-layer lost-wakeup path.
"""

from __future__ import annotations

import argparse
import hashlib
import struct
from pathlib import Path

from patch_admin_polling import elf_sections, symbol_maps
from patch_intx_one_shot import EXPECTED_INPUT_SHA256


INLINE_STUB = bytes.fromhex(
    "f353bea9fe0b00f9f30303aa600240b9"
    "0001003514488852f401a072e00313aa"
    "00000094600000359406007181ffff54"
    "6322009100008052fe0b40f9f353c2a8"
    "c0035fd6"
)

TIMER_STUB = bytes.fromhex(
    "f353bda9f55b01a9fe1300f9145c40f9"
    "154040b9550200349442019133008052"
    "800640b91f08007121010054801240f9"
    "000040f900000094e00314aa00000094"
    "801240f9000040f90000009494420191"
    "730600117f02156b49feff54fe1340f9"
    "f55b41a9f353c3a8c0035fd6"
)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("input", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--timer-us", type=int, default=50)
    args = parser.parse_args()
    if not 1 <= args.timer_us <= 0xFFFF:
        raise SystemExit("--timer-us must fit one MOVZ immediate")

    original = args.input.read_bytes()
    digest = hashlib.sha256(original).hexdigest()
    if digest != EXPECTED_INPUT_SHA256:
        raise SystemExit(f"refusing unexpected input SHA-256: {digest}")
    sections, _ = elf_sections(original)
    text = next(sec for sec in sections if sec["name"] == ".text")
    rela = next(sec for sec in sections if sec["name"] == ".rela.text")
    by_name, by_index = symbol_maps(original, sections)
    patched = bytearray(original)

    instruction_patches = {
        0x1558: (bytes.fromhex("bf3b03d5"), bytes.fromhex("e30313aa")),
        0x155C: (bytes.fromhex("20008052"), bytes.fromhex("450e0094")),
        0x1560: (bytes.fromhex("63220091"), bytes.fromhex("20008052")),
        0x18B0: (bytes.fromhex("e3031aaa"), bytes.fromhex("e30313aa")),
        0x18C0: (bytes.fromhex("00000094"), bytes.fromhex("6c0d0094")),
        0x5BD4: (bytes.fromhex("034888d2"), struct.pack("<I", 0xD2800003 | (args.timer_us << 5))),
        0x5BE4: (bytes.fromhex("e301a0f2"), bytes.fromhex("1f2003d5")),
        0x8DCC: (bytes.fromhex("200040b9"), bytes.fromhex("02000014")),
    }
    for off, (expected, replacement) in instruction_patches.items():
        pos = text["offset"] + off
        actual = original[pos : pos + 4]
        if actual != expected:
            raise SystemExit(f"unexpected instruction at .text+0x{off:x}: {actual.hex()}")
        patched[pos : pos + 4] = replacement

    if original[text["offset"] + 0x4840 : text["offset"] + 0x4844] != bytes.fromhex("f353bba9"):
        raise SystemExit("unexpected timer handler prefix")
    if original[text["offset"] + 0x4E70 : text["offset"] + 0x4E74] != bytes.fromhex("f353bda9"):
        raise SystemExit("unexpected PollHandler prefix")
    patched[text["offset"] + 0x4840 : text["offset"] + 0x4840 + len(TIMER_STUB)] = TIMER_STUB
    patched[text["offset"] + 0x4E70 : text["offset"] + 0x4E70 + len(INLINE_STUB)] = INLINE_STUB

    moves = {
        0x4E7C: (0x4E90, "vmk_NvmeGetControllerDriverData", "NVMEPCIEProcessCq"),
        0x4EA8: (0x4874, "vmk_SpinlockLock", "vmk_SpinlockLock"),
        0x4EB0: (0x487C, "NVMEPCIEProcessCq", "NVMEPCIEProcessCq"),
        0x4EBC: (0x4888, "vmk_SpinlockUnlock", "vmk_SpinlockUnlock"),
    }
    found: set[int] = set()
    cleared_data: set[int] = set()
    cleared_wait = False
    count = rela["size"] // rela["entsize"]
    for index in range(count):
        pos = rela["offset"] + index * rela["entsize"]
        target, info = struct.unpack_from("<QQ", original, pos)
        old_index = info >> 32
        rel_type = info & 0xFFFFFFFF
        if target == 0x18C0:
            if by_index.get(old_index, "") != "vmk_WorldWait" or rel_type != 283:
                raise SystemExit("unexpected WorldWait relocation")
            struct.pack_into("<Q", patched, pos + 8, 0)
            cleared_wait = True
            continue
        if target in (0x485C, 0x4860):
            struct.pack_into("<Q", patched, pos + 8, 0)
            cleared_data.add(target)
            continue
        if target not in moves:
            continue
        new_target, old_name, new_name = moves[target]
        if by_index.get(old_index, "") != old_name or rel_type != 283:
            raise SystemExit(f"unexpected relocation at 0x{target:x}")
        struct.pack_into("<Q", patched, pos, new_target)
        struct.pack_into("<Q", patched, pos + 8, (by_name[new_name] << 32) | rel_type)
        found.add(target)

    if found != set(moves):
        raise SystemExit(f"missing moved relocations: {set(moves) - found}")
    if cleared_data != {0x485C, 0x4860} or not cleared_wait:
        raise SystemExit("missing overwritten relocation cleanup")

    args.output.write_bytes(patched)
    print(f"input_sha256={digest}")
    print(f"timer_us={args.timer_us}")
    print(f"output_sha256={hashlib.sha256(patched).hexdigest()}")


if __name__ == "__main__":
    main()
