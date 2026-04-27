from __future__ import annotations

import ctypes
from ctypes import wintypes
from pathlib import Path


def read_pe_summary(path: Path) -> dict[str, str]:
    """Return inexpensive PE facts without loading the executable."""
    info: dict[str, str] = {}
    try:
        with path.open("rb") as handle:
            if handle.read(2) != b"MZ":
                return info
            handle.seek(0x3C)
            pe_offset = int.from_bytes(handle.read(4), "little")
            handle.seek(pe_offset)
            if handle.read(4) != b"PE\x00\x00":
                return info
            machine = int.from_bytes(handle.read(2), "little")
            info["Machine"] = {
                0x014C: "x86",
                0x8664: "x64",
                0x01C4: "ARM",
                0xAA64: "ARM64",
            }.get(machine, hex(machine))
            handle.seek(pe_offset + 24)
            magic = int.from_bytes(handle.read(2), "little")
            optional_header_base = pe_offset + 24
            subsystem_offset = optional_header_base + (92 if magic == 0x10B else 108)
            handle.seek(subsystem_offset)
            subsystem = int.from_bytes(handle.read(2), "little")
            info["Subsystem"] = {
                2: "Windows GUI",
                3: "Windows console",
                9: "Windows CE",
                10: "EFI application",
            }.get(subsystem, str(subsystem))
    except Exception:
        return info
    return info


def read_version_info(path: Path) -> dict[str, str]:
    """Read Windows VERSIONINFO string fields using version.dll.

    This is best-effort and intentionally quiet: many games omit file metadata.
    """
    result: dict[str, str] = {}
    try:
        version = ctypes.WinDLL("version", use_last_error=True)
    except Exception:
        return result

    file_name = str(path)
    size = version.GetFileVersionInfoSizeW(wintypes.LPCWSTR(file_name), None)
    if not size:
        return result

    buffer = ctypes.create_string_buffer(size)
    ok = version.GetFileVersionInfoW(wintypes.LPCWSTR(file_name), 0, size, buffer)
    if not ok:
        return result

    class LANGANDCODEPAGE(ctypes.Structure):
        _fields_ = [("wLanguage", wintypes.WORD), ("wCodePage", wintypes.WORD)]

    translate_ptr = ctypes.c_void_p()
    translate_len = wintypes.UINT()
    ok = version.VerQueryValueW(
        buffer,
        wintypes.LPCWSTR(r"\VarFileInfo\Translation"),
        ctypes.byref(translate_ptr),
        ctypes.byref(translate_len),
    )
    translations: list[tuple[int, int]] = []
    if ok and translate_len.value >= ctypes.sizeof(LANGANDCODEPAGE):
        count = translate_len.value // ctypes.sizeof(LANGANDCODEPAGE)
        array_type = LANGANDCODEPAGE * count
        translations = [
            (item.wLanguage, item.wCodePage)
            for item in ctypes.cast(translate_ptr, ctypes.POINTER(array_type)).contents
        ]
    if not translations:
        translations = [(0x0409, 0x04B0), (0x0409, 0x04E4)]

    fields = [
        "ProductName",
        "FileDescription",
        "CompanyName",
        "OriginalFilename",
        "ProductVersion",
        "FileVersion",
    ]
    for language, codepage in translations[:4]:
        for field in fields:
            if field in result:
                continue
            query = rf"\StringFileInfo\{language:04x}{codepage:04x}\{field}"
            value_ptr = ctypes.c_void_p()
            value_len = wintypes.UINT()
            ok = version.VerQueryValueW(
                buffer,
                wintypes.LPCWSTR(query),
                ctypes.byref(value_ptr),
                ctypes.byref(value_len),
            )
            if ok and value_ptr.value and value_len.value:
                value = ctypes.wstring_at(value_ptr.value, value_len.value).rstrip("\x00")
                if value:
                    result[field] = value
    result.update(read_pe_summary(path))
    return result
