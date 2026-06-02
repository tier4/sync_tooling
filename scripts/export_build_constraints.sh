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

set -euo pipefail

if [[ $# -lt 1 ]]; then
  echo "Usage: $0 <output-path>" >&2
  exit 1
fi

out="$1"
pattern='^(protobuf|mypy-protobuf|hatch-protobuf|types-protobuf)=='

strip_constraints() {
  grep -E "$pattern" | sed -E 's/\s*\\?\s*$//' | awk '{print $1}'
}

tmp="$(mktemp)"
trap 'rm -f "$tmp"' EXIT

uv export --frozen --package sync-tooling-msgs --only-group dev 2>/dev/null | strip_constraints >"$tmp"

if ! grep -q '^types-protobuf==' "$tmp"; then
  uv export --frozen --package sync-tooling-msgs 2>/dev/null | strip_constraints >>"$tmp"
fi

sort -u "$tmp" >"$out"

# Keep [tool.uv] build-constraint-dependencies in pyproject.toml aligned with this output.
