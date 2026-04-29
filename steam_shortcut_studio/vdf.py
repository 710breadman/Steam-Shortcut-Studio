from __future__ import annotations

import struct
from collections import OrderedDict
from pathlib import Path
from typing import Any, MutableMapping

TYPE_OBJECT = 0x00
TYPE_STRING = 0x01
TYPE_INT32 = 0x02
TYPE_UINT64 = 0x07
TYPE_END = 0x08


class VdfParseError(ValueError):
    pass


def _decode(raw: bytes) -> str:
    return raw.decode("utf-8", errors="replace")


def _encode(text: str) -> bytes:
    return text.encode("utf-8", errors="replace") + b"\x00"


class BinaryVdfReader:
    def __init__(self, data: bytes) -> None:
        self.data = data
        self.offset = 0

    def read(self) -> OrderedDict[str, Any]:
        root: OrderedDict[str, Any] = OrderedDict()
        while self.offset < len(self.data):
            item_type = self._read_byte()
            if item_type == TYPE_END:
                break
            key = self._read_c_string()
            root[key] = self._read_value(item_type)
        return root

    def _read_value(self, item_type: int) -> Any:
        if item_type == TYPE_OBJECT:
            return self._read_object()
        if item_type == TYPE_STRING:
            return self._read_c_string()
        if item_type == TYPE_INT32:
            self._require(4)
            value = struct.unpack_from("<i", self.data, self.offset)[0]
            self.offset += 4
            return value
        if item_type == TYPE_UINT64:
            self._require(8)
            value = struct.unpack_from("<Q", self.data, self.offset)[0]
            self.offset += 8
            return value
        raise VdfParseError(f"Unsupported VDF field type 0x{item_type:02x} at byte {self.offset - 1}")

    def _read_object(self) -> OrderedDict[str, Any]:
        mapping: OrderedDict[str, Any] = OrderedDict()
        while self.offset < len(self.data):
            item_type = self._read_byte()
            if item_type == TYPE_END:
                return mapping
            key = self._read_c_string()
            mapping[key] = self._read_value(item_type)
        raise VdfParseError("Unexpected end of file while reading object.")

    def _read_byte(self) -> int:
        self._require(1)
        value = self.data[self.offset]
        self.offset += 1
        return value

    def _read_c_string(self) -> str:
        end = self.data.find(b"\x00", self.offset)
        if end < 0:
            raise VdfParseError("Unterminated VDF string.")
        raw = self.data[self.offset:end]
        self.offset = end + 1
        return _decode(raw)

    def _require(self, size: int) -> None:
        if self.offset + size > len(self.data):
            raise VdfParseError("Unexpected end of VDF data.")


class BinaryVdfWriter:
    def __init__(self) -> None:
        self.parts: list[bytes] = []

    def write(self, mapping: MutableMapping[str, Any]) -> bytes:
        self._write_mapping(mapping)
        self.parts.append(bytes([TYPE_END]))
        return b"".join(self.parts)

    def _write_mapping(self, mapping: MutableMapping[str, Any]) -> None:
        for key, value in mapping.items():
            if isinstance(value, MutableMapping):
                self.parts.append(bytes([TYPE_OBJECT]))
                self.parts.append(_encode(str(key)))
                self._write_mapping(value)
                self.parts.append(bytes([TYPE_END]))
            elif isinstance(value, int):
                if value < -2147483648 or value > 0xFFFFFFFF:
                    self.parts.append(bytes([TYPE_UINT64]))
                    self.parts.append(_encode(str(key)))
                    self.parts.append(struct.pack("<Q", value & 0xFFFFFFFFFFFFFFFF))
                else:
                    self.parts.append(bytes([TYPE_INT32]))
                    self.parts.append(_encode(str(key)))
                    signed = value if value <= 2147483647 else value - 0x100000000
                    self.parts.append(struct.pack("<i", signed))
            else:
                self.parts.append(bytes([TYPE_STRING]))
                self.parts.append(_encode(str(key)))
                self.parts.append(_encode("" if value is None else str(value)))


def load_binary_vdf(path: Path) -> OrderedDict[str, Any]:
    return BinaryVdfReader(path.read_bytes()).read()


def dump_binary_vdf(mapping: MutableMapping[str, Any]) -> bytes:
    return BinaryVdfWriter().write(mapping)


def save_binary_vdf(path: Path, mapping: MutableMapping[str, Any]) -> None:
    path.write_bytes(dump_binary_vdf(mapping))


def _text_vdf_tokens(text: str) -> list[str]:
    tokens: list[str] = []
    index = 0
    length = len(text)
    while index < length:
        char = text[index]
        if char.isspace():
            index += 1
            continue
        if char == "/" and index + 1 < length and text[index + 1] == "/":
            index = text.find("\n", index)
            if index < 0:
                break
            continue
        if char in "{}":
            tokens.append(char)
            index += 1
            continue
        if char == '"':
            index += 1
            value: list[str] = []
            while index < length:
                char = text[index]
                if char == "\\" and index + 1 < length:
                    escape = text[index + 1]
                    value.append({"n": "\n", "r": "\r", "t": "\t"}.get(escape, escape))
                    index += 2
                    continue
                if char == '"':
                    index += 1
                    break
                value.append(char)
                index += 1
            else:
                raise VdfParseError("Unterminated quoted string in text VDF.")
            tokens.append("".join(value))
            continue
        start = index
        while index < length and not text[index].isspace() and text[index] not in "{}":
            index += 1
        tokens.append(text[start:index])
    return tokens


class TextVdfReader:
    def __init__(self, text: str) -> None:
        self.tokens = _text_vdf_tokens(text)
        self.index = 0

    def read(self) -> OrderedDict[str, Any]:
        mapping = self._read_mapping(root=True)
        if self.index != len(self.tokens):
            raise VdfParseError("Unexpected trailing token in text VDF.")
        return mapping

    def _next(self) -> str:
        if self.index >= len(self.tokens):
            raise VdfParseError("Unexpected end of text VDF.")
        token = self.tokens[self.index]
        self.index += 1
        return token

    def _read_mapping(self, root: bool = False) -> OrderedDict[str, Any]:
        mapping: OrderedDict[str, Any] = OrderedDict()
        while self.index < len(self.tokens):
            key = self._next()
            if key == "}":
                if root:
                    raise VdfParseError("Unexpected closing brace in text VDF.")
                return mapping
            if key == "{":
                raise VdfParseError("Unexpected opening brace in text VDF.")
            value = self._next()
            if value == "{":
                mapping[key] = self._read_mapping()
            elif value == "}":
                raise VdfParseError(f"Missing value for text VDF key {key!r}.")
            else:
                mapping[key] = value
        if not root:
            raise VdfParseError("Unexpected end of text VDF object.")
        return mapping


def _escape_text_vdf(value: object) -> str:
    return str(value).replace("\\", "\\\\").replace('"', '\\"')


def _write_text_mapping(lines: list[str], mapping: MutableMapping[str, Any], indent: int) -> None:
    prefix = "\t" * indent
    for key, value in mapping.items():
        escaped_key = _escape_text_vdf(key)
        if isinstance(value, MutableMapping):
            lines.append(f'{prefix}"{escaped_key}"')
            lines.append(f"{prefix}{{")
            _write_text_mapping(lines, value, indent + 1)
            lines.append(f"{prefix}}}")
        else:
            lines.append(f'{prefix}"{escaped_key}"\t\t"{_escape_text_vdf(value)}"')


def load_text_vdf(path: Path) -> OrderedDict[str, Any]:
    return TextVdfReader(path.read_text(encoding="utf-8", errors="replace")).read()


def dump_text_vdf(mapping: MutableMapping[str, Any]) -> str:
    lines: list[str] = []
    _write_text_mapping(lines, mapping, 0)
    return "\n".join(lines) + "\n"
