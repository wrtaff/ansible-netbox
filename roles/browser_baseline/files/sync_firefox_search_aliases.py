#!/usr/bin/env python3
# ==============================================================================
# Filename:       sync_firefox_search_aliases.py
# Purpose:        Synchronize Firefox search keywords/aliases in search.json.mozlz4
#                 across named profiles so keywords ('nb', 'ww', 'trac', 'wik')
#                 work directly in the location bar without manual configuration.
# Context:        Trac #4408, #2783
# ==============================================================================

import os
import sys
import glob
import json
import struct
import ctypes
import ctypes.util

ALIAS_MAP = {
    "netbox": "nb",
    "wwos": "ww",
    "wikiwikioldschool (en)": "ww",
    "trac": "trac",
    "wikipedia": "wik",
    "wikipedia (en)": "wik",
    "google drive": "gdr",
}

def get_lz4():
    lib_name = ctypes.util.find_library("lz4") or "liblz4.so.1"
    try:
        return ctypes.CDLL(lib_name)
    except Exception as e:
        sys.stderr.write(f"Could not load lz4 library: {e}\n")
        return None

def decompress_mozlz4(lz4, data):
    if not data.startswith(b"mozLz40\0"):
        return None
    uncompressed_size = struct.unpack("<I", data[8:12])[0]
    dest = ctypes.create_string_buffer(uncompressed_size)
    src = data[12:]
    res = lz4.LZ4_decompress_safe(src, dest, len(src), uncompressed_size)
    if res < 0:
        return None
    return dest.raw.decode("utf-8", errors="replace")

def compress_mozlz4(lz4, text):
    src = text.encode("utf-8")
    uncompressed_size = len(src)
    max_dest_size = lz4.LZ4_compressBound(uncompressed_size)
    dest = ctypes.create_string_buffer(max_dest_size)
    compressed_size = lz4.LZ4_compress_default(src, dest, uncompressed_size, max_dest_size)
    if compressed_size <= 0:
        raise ValueError("Compression failed")
    header = b"mozLz40\0" + struct.pack("<I", uncompressed_size)
    return header + dest.raw[:compressed_size]

def sync_profile(lz4, path):
    try:
        with open(path, "rb") as f:
            data = f.read()
    except Exception as e:
        sys.stderr.write(f"Cannot read {path}: {e}\n")
        return False

    raw = decompress_mozlz4(lz4, data)
    if not raw:
        return False

    try:
        j = json.loads(raw)
    except Exception as e:
        sys.stderr.write(f"JSON decode error in {path}: {e}\n")
        return False

    changed = False
    for e in j.get("engines", []):
        name = (e.get("_name") or e.get("name") or "").lower()
        if name in ALIAS_MAP:
            target_alias = ALIAS_MAP[name]
            meta = e.setdefault("_metaData", {})
            if meta.get("alias") != target_alias:
                meta["alias"] = target_alias
                changed = True

    if changed:
        comp = compress_mozlz4(lz4, json.dumps(j))
        try:
            with open(path, "wb") as f:
                f.write(comp)
            print(f"Updated search aliases in {path}")
            return True
        except Exception as e:
            sys.stderr.write(f"Cannot write {path}: {e}\n")
            return False
    return False

def main():
    base_dir = sys.argv[1] if len(sys.argv) > 1 else os.path.expanduser("~/.mozilla/firefox")
    lz4 = get_lz4()
    if not lz4:
        sys.exit(0)

    pattern = os.path.join(base_dir, "*", "search.json.mozlz4")
    any_changed = False
    for p in glob.glob(pattern):
        if sync_profile(lz4, p):
            any_changed = True

    sys.exit(0)

if __name__ == "__main__":
    main()
