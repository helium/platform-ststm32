# SPDX-License-Identifier: Apache-2.0

cmake_minimum_required(VERSION 3.13.1)

set(ZEPHYR_MODULES ${ZEPHYR_MODULES} "${CMAKE_CURRENT_SOURCE_DIR}/modules/custom-module" "${CMAKE_CURRENT_SOURCE_DIR}/modules/fatfs")

include($ENV{ZEPHYR_BASE}/cmake/app/boilerplate.cmake NO_POLICY_SCOPE)
project(zephyr-modules)
target_sources(app PRIVATE ../src/main.c)
