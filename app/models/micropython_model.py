# Copyright (C) 2026 The Librarian contributors
#
# This file is part of The Librarian.
#
# The Librarian is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# The Librarian is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with The Librarian. If not, see <https://www.gnu.org/licenses/>.
"""MicroPython module and language semantics registry."""

from __future__ import annotations

# Standard MicroPython built-in and hardware modules
MICROPYTHON_BUILTIN_MODULES: dict[str, dict[str, str]] = {
    # Core & Hardware
    "machine": {
        "description": "Hardware access: Pin, I2C, SPI, UART, PWM, ADC, Timer, RTC, WDT, etc.",
        "category": "hardware",
    },
    "micropython": {
        "description": "MicroPython internals: const, native, viper, asm_thumb, alloc_emergency_exception_buf, etc.",
        "category": "core",
    },
    "network": {
        "description": "Network configuration (WLAN, LAN, AP, PPP).",
        "category": "network",
    },
    "bluetooth": {
        "description": "Low-level BLE interface.",
        "category": "network",
    },
    "rp2": {
        "description": "Raspberry Pi RP2040 / RP2350 specific PIO and state machine features.",
        "category": "port-specific",
    },
    "esp": {
        "description": "ESP8266 / ESP32 vendor-specific functions.",
        "category": "port-specific",
    },
    "esp32": {
        "description": "ESP32-specific features: NVS, RMT, ULP, Hall sensor, Partition, etc.",
        "category": "port-specific",
    },
    "esp8266": {
        "description": "ESP8266-specific low-level functions.",
        "category": "port-specific",
    },
    "pyb": {
        "description": "Pyboard STM32-specific functions: LED, Switch, Accel, CAN, DAC, LCD, etc.",
        "category": "port-specific",
    },
    "stm": {
        "description": "Direct memory register access for STM32 microcontrollers.",
        "category": "port-specific",
    },
    "wipy": {
        "description": "WiPy-specific hardware control.",
        "category": "port-specific",
    },
    "lcd160cr": {
        "description": "LCD160CR display driver.",
        "category": "driver",
    },
    "framebuf": {
        "description": "Frame buffer manipulation for pixel displays.",
        "category": "graphics",
    },
    "neopixel": {
        "description": "WS2812 / NeoPixel addressable LED driver.",
        "category": "driver",
    },
    "dht": {
        "description": "DHT11 / DHT22 humidity and temperature sensor driver.",
        "category": "driver",
    },
    "onewire": {
        "description": "1-Wire bus protocol driver.",
        "category": "driver",
    },
    "ds18x20": {
        "description": "Dallas DS18B20 1-Wire temperature sensor driver.",
        "category": "driver",
    },
    "sdcard": {
        "description": "SD Card SPI driver for filesystem mounting.",
        "category": "driver",
    },
    "ssd1306": {
        "description": "OLED SSD1306 display driver via I2C / SPI.",
        "category": "driver",
    },

    # MicroPython Micro-subset modules (u-prefixed and standard aliases)
    "uasyncio": {
        "description": "Lightweight asynchronous I/O event loop.",
        "category": "async",
    },
    "asyncio": {
        "description": "Standard alias for uasyncio in MicroPython.",
        "category": "async",
    },
    "utime": {
        "description": "Time access and conversions: sleep, sleep_ms, sleep_us, ticks_ms, ticks_diff, etc.",
        "category": "core",
    },
    "uos": {
        "description": "Basic filesystem and operating system services: mount, umount, VfsFat, VfsLfs2, uname.",
        "category": "os",
    },
    "ure": {
        "description": "Lightweight regular expressions engine.",
        "category": "text",
    },
    "ujson": {
        "description": "Lightweight JSON encoding and decoding.",
        "category": "data",
    },
    "usocket": {
        "description": "Socket module for network communication.",
        "category": "network",
    },
    "ustruct": {
        "description": "Pack and unpack primitive data types according to format strings.",
        "category": "data",
    },
    "ubinascii": {
        "description": "Binary/ASCII conversions (hexlify, unhexlify, b2a_base64, etc.).",
        "category": "data",
    },
    "uhashlib": {
        "description": "Lightweight cryptographic hashing (sha256, md5, sha1).",
        "category": "crypto",
    },
    "uctypes": {
        "description": "Access binary data in a structured way (C struct memory mapping).",
        "category": "low-level",
    },
    "ucryptolib": {
        "description": "Cryptographic ciphers (AES).",
        "category": "crypto",
    },
    "uheapq": {
        "description": "Heap queue algorithm (priority queue).",
        "category": "data",
    },
    "uselect": {
        "description": "Wait for I/O completion on streams and sockets.",
        "category": "io",
    },
    "uzlib": {
        "description": "Zlib decompression module.",
        "category": "compression",
    },
    "uio": {
        "description": "Input/Output stream handling (StringIO, BytesIO).",
        "category": "io",
    },
    "uarray": {
        "description": "Efficient arrays of numeric values.",
        "category": "data",
    },
    "ucollections": {
        "description": "Collection types (namedtuple, deque, OrderedDict).",
        "category": "data",
    },
    "errno": {
        "description": "Standard errno system error codes.",
        "category": "core",
    },
    "gc": {
        "description": "Garbage collector control: collect, mem_alloc, mem_free, threshold, disable, enable.",
        "category": "memory",
    },
}

# Recognized MicroPython-specific function decorators
MICROPYTHON_DECORATORS: set[str] = {
    "micropython.native",
    "micropython.viper",
    "micropython.asm_thumb",
    "micropython.bytecode",
    "native",
    "viper",
    "asm_thumb",
    "bytecode",
}


def is_micropython_module(module_name: str) -> bool:
    """Return True if module_name is a known MicroPython built-in or micro-module."""
    if not module_name:
        return False
    normalized = module_name.split(".")[0].strip().lower()
    return normalized in MICROPYTHON_BUILTIN_MODULES


def get_micropython_module_info(module_name: str) -> dict[str, str] | None:
    """Return description and category metadata for a MicroPython module if recognized."""
    normalized = module_name.split(".")[0].strip().lower()
    return MICROPYTHON_BUILTIN_MODULES.get(normalized)


def is_micropython_decorator(decorator_name: str) -> bool:
    """Return True if decorator matches a MicroPython compilation/emitter decorator."""
    cleaned = decorator_name.strip().lstrip("@")
    return cleaned in MICROPYTHON_DECORATORS
