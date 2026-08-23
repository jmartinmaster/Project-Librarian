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
"""Smoke tests for C and C++ symbol indexing."""

from __future__ import annotations

from pathlib import Path
from app.indexer.c_indexer import index_c_symbols


def test_index_c_symbols_finds_struct_and_function(sample_repo):
    symbols = index_c_symbols(sample_repo)
    kinds = {(item["kind"], item["name"]) for item in symbols}
    assert ("c_struct", "person") in kinds
    assert ("c_function", "sum") in kinds


def test_index_c_and_cpp_comprehensive(tmp_path: Path):
    # Create C header
    header = tmp_path / "hardware_api.h"
    header.write_text("""
#define GPIO_MAX_PINS 32
#define READ_PIN(p) ((p) & 0x01)

typedef struct {
    uint32_t baud_rate;
    uint8_t pin;
} uart_port_t;

enum PowerMode {
    PWR_SLEEP = 0,
    PWR_ACTIVE,
    PWR_DEEP_SLEEP
};

int init_hardware_port(uart_port_t *port);
""", encoding="utf-8")

    # Create C++ source
    cpp_source = tmp_path / "motor_driver.cpp"
    cpp_source.write_text("""
#include "hardware_api.h"

class MotorDriver : public IDriver {
public:
    MotorDriver(int id);
    void set_speed(float rpm);
    float get_current();
};

void MotorDriver::set_speed(float rpm) {
    // rpm logic
}
""", encoding="utf-8")

    symbols = index_c_symbols(tmp_path)
    kinds = {(item["kind"], item["name"]) for item in symbols}

    assert ("c_macro", "GPIO_MAX_PINS") in kinds
    assert ("c_macro", "READ_PIN") in kinds
    assert ("c_typedef", "uart_port_t") in kinds
    assert ("c_enum", "PowerMode") in kinds
    assert ("c_function", "init_hardware_port") in kinds
    assert ("cpp_class", "MotorDriver") in kinds
    assert ("cpp_method", "set_speed") in kinds
