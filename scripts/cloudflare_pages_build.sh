#!/usr/bin/env bash

set -e

apt download graphviz
mkdir graphviz
dpkg --fsys-tarfile graphviz*.deb |  tar -xf - -C graphviz/
graphviz_dir="$(realpath graphviz)"
export PATH="$PATH:$graphviz_dir/usr/bin"
uv sync --all-packages --all-extras
uv build --all-packages
uv run mkdocs build --strict