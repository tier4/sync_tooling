#!/usr/bin/env bash

# Copyright 2025 TIER IV, Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

set -e

apt download graphviz libgvc6
mkdir graphviz
dpkg --fsys-tarfile graphviz*.deb |  tar -xf - -C graphviz/
dpkg --fsys-tarfile libgvc6*.deb |  tar -xf - -C graphviz/
graphviz_dir="$(realpath graphviz)"
export PATH="$PATH:$graphviz_dir/usr/bin"
uv sync --all-packages --all-extras
uv build --all-packages
uv run mkdocs build --strict