#!/usr/bin/env python3
"""Disable INTx delivery and poll NVMe completion queues after submission.

Build-specific diagnostic patch for ESXi ARM 8.0U3c build 24449057.
It inserts bounded polling into both async and synchronous command paths. The
stub sleeps for 50 us, runs the stock NVMEPCIEProcessCq routine, and repeats up
to 2000 times. ELF relocations are changed explicitly. This is specific to the
ESXi ARM 8.0U3c build 24449057 nvme_pcie binary.
"""

from __future__ import annotations

import argparse
import hashlib
import struct
from pathlib import Path

from patch_intx_one_shot import EXPECTED_INPUT_SHA256


def elf_sections(blob: bytes) -> tuple[list[dict[str, int]], bytes]:
    shoff = struct.unpack_from("<Q", blob, 0x28)[0]
    shentsize = struct.unpack_from("<H", blob, 0x3A)[0]
    shnum = struct.unpack_from("<H", blob, 0x3C)[0]
    shstrndx = struct.unpack_from("<H", blob, 0x3E)[0]
    if blob[:6] != b"\x7fELF\x02\x01" or shentsize != 64:
        raise ValueError("expected ELF64 little-endian input")
    raw: list[dict[str, int]] = []
    for index in range(shnum):
        off = shoff + index * shentsize
        raw.append(
            {
                "index": index,
                "name_off": struct.unpack_from("<I", blob, off)[0],
                "type": struct.unpack_from("<I", blob, off + 4)[0],
                "offset": struct.unpack_from("<Q", blob, off + 0x18)[0],
                "size": struct.unpack_from("<Q", blob, off + 0x20)[0],
                "link": struct.unpack_from("<I", blob, off + 0x28)[0],
                "entsize": struct.unpack_from("<Q", blob, off + 0x38)[0],
            }
        )
    names_sec = raw[shstrndx]
    names = blob[names_sec["offset"] : names_sec["offset"] + names_sec["size"]]
    for sec in raw:
        start = sec["name_off"]
        end = names.find(b"\0", start)
        sec["name"] = names[start:end].decode()  # type: ignore[assignment]
    return raw, names


def symbol_maps(blob: bytes, sections: list[dict[str, int]]) -> tuple[dict[str, int], dict[int, str]]:
    symtab = next(sec for sec in sections if sec["name"] == ".symtab")
    strtab = sections[symtab["link"]]
    strings = blob[strtab["offset"] : strtab["offset"] + strtab["size"]]
    by_name: dict[str, int] = {}
    by_index: dict[int, str] = {}
    count = symtab["size"] // symtab["entsize"]
    for index in range(count):
        off = symtab["offset"] + index * symtab["entsize"]
        name_off = struct.unpack_from("<I", blob, off)[0]
        end = strings.find(b"\0", name_off)
        name = strings[name_off:end].decode()
        if name:
            by_name[name] = index
            by_index[index] = name
    return by_name, by_index


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("input", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--sleep-us", type=int, default=50,
                        help="0 selects bounded busy polling")
    parser.add_argument("--attempts", type=int, default=2000)
    args = parser.parse_args()
    if not 0 <= args.sleep_us <= 0xFFFF:
        raise SystemExit("--sleep-us must be in 0..65535")
    if not 1 <= args.attempts <= 0xFFFFFFFF:
        raise SystemExit("--attempts must fit a 32-bit AArch64 MOVZ/MOVK pair")

    original = args.input.read_bytes()
    digest = hashlib.sha256(original).hexdigest()
    if digest != EXPECTED_INPUT_SHA256:
        raise SystemExit(f"refusing unexpected input SHA-256: {digest}")
    sections, _ = elf_sections(original)
    text_sec = next(sec for sec in sections if sec["name"] == ".text")
    rela_sec = next(sec for sec in sections if sec["name"] == ".rela.text")
    by_name, by_index = symbol_maps(original, sections)
    patched = bytearray(original)

    instruction_patches = {
        0x1558: (bytes.fromhex("bf3b03d5"), bytes.fromhex("e30313aa")),  # queue in x3
        0x155C: (bytes.fromhex("20008052"), bytes.fromhex("450e0094")),  # BL PollHandler
        0x1560: (bytes.fromhex("63220091"), bytes.fromhex("20008052")),  # restore w0=1
        0x18B0: (bytes.fromhex("e3031aaa"), bytes.fromhex("e30313aa")),  # queue in x3
        0x18C0: (bytes.fromhex("00000094"), bytes.fromhex("6c0d0094")),  # BL PollHandler
        0x8DCC: (bytes.fromhex("200040b9"), bytes.fromhex("02000014")),  # skip IntrEnable
    }
    for text_off, (expected, replacement) in instruction_patches.items():
        file_off = text_sec["offset"] + text_off
        actual = original[file_off : file_off + 4]
        if actual != expected:
            raise SystemExit(f"unexpected instruction at .text+0x{text_off:x}: {actual.hex()}")
        patched[file_off : file_off + 4] = replacement

    stub_expected = bytes.fromhex(
        "f353bda9f55b01a9fe1300f900000094f50300aa004040b92002003434008052"
        "160a8052b35e40f9934e369b94060011601240f9000040f900000094e00313aa"
    )
    stub_replacement = bytes.fromhex(
        "f353bea9fe0b00f9f30303aa14fa8052400680d200000094e00313aa00000094"
        "600000359406007141ffff546322009100008052fe0b40f9f353c2a8c0035fd6"
    )
    # MOV W20,#attempts and MOV X0,#sleep_us in the replacement stub. In busy
    # mode the latter slot becomes MOVK W20 and the WorldSleep call becomes NOP.
    stub_replacement = bytearray(stub_replacement)
    struct.pack_into("<I", stub_replacement, 0x0C,
                     0x52800014 | ((args.attempts & 0xFFFF) << 5))
    if args.sleep_us:
        struct.pack_into("<I", stub_replacement, 0x10,
                         0xD2800000 | (args.sleep_us << 5))
    else:
        struct.pack_into("<I", stub_replacement, 0x10,
                         0x72A00014 | (((args.attempts >> 16) & 0xFFFF) << 5))
        struct.pack_into("<I", stub_replacement, 0x14, 0xD503201F)
        # Loop directly to NVMEPCIEProcessCq, not through the MOVK initializer.
        struct.pack_into("<I", stub_replacement, 0x28, 0x54FFFF81)
    stub_replacement = bytes(stub_replacement)
    stub_off = text_sec["offset"] + 0x4E70
    if original[stub_off : stub_off + len(stub_expected)] != stub_expected:
        raise SystemExit("unexpected original PollHandler prefix")
    patched[stub_off : stub_off + len(stub_replacement)] = stub_replacement

    relocation_changes = {
        0x4EA8: (0x4E8C, "vmk_SpinlockLock", "NVMEPCIEProcessCq"),
    }
    if args.sleep_us:
        relocation_changes[0x4E7C] = (
            0x4E84, "vmk_NvmeGetControllerDriverData", "vmk_WorldSleep"
        )
    found: set[int] = set()
    count = rela_sec["size"] // rela_sec["entsize"]
    for index in range(count):
        off = rela_sec["offset"] + index * rela_sec["entsize"]
        target, info = struct.unpack_from("<QQ", original, off)
        if target == 0x18C0:
            old_index = info >> 32
            rel_type = info & 0xFFFFFFFF
            if by_index.get(old_index, "") != "vmk_WorldWait" or rel_type != 283:
                raise SystemExit("unexpected WorldWait relocation")
            struct.pack_into("<Q", patched, off + 8, 0)
            continue
        if target == 0x4E7C and not args.sleep_us:
            old_index = info >> 32
            rel_type = info & 0xFFFFFFFF
            if by_index.get(old_index, "") != "vmk_NvmeGetControllerDriverData" or rel_type != 283:
                raise SystemExit("unexpected PollHandler relocation for busy mode")
            struct.pack_into("<Q", patched, off + 8, 0)
            continue
        if target not in relocation_changes:
            continue
        new_target, old_name, new_name = relocation_changes[target]
        old_index = info >> 32
        rel_type = info & 0xFFFFFFFF
        actual_name = by_index.get(old_index, "")
        if actual_name != old_name or rel_type != 283:  # R_AARCH64_CALL26
            raise SystemExit(
                f"unexpected relocation at 0x{target:x}: {actual_name} type={rel_type}"
            )
        struct.pack_into("<Q", patched, off, new_target)
        new_info = (by_name[new_name] << 32) | rel_type
        struct.pack_into("<Q", patched, off + 8, new_info)
        found.add(target)
    if found != set(relocation_changes):
        raise SystemExit(f"missing relocations: {set(relocation_changes) - found}")

    args.output.write_bytes(patched)
    print(f"input_sha256={digest}")
    for target, names in relocation_changes.items():
        print(f"relocation=0x{target:x}->0x{names[0]:x} {names[1]} -> {names[2]}")
    print(f"output_sha256={hashlib.sha256(patched).hexdigest()}")


if __name__ == "__main__":
    main()
