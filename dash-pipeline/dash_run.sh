#!/bin/bash
set -euo pipefail

usage() {
    cat <<EOF
Usage: $0 [command]

Commands:
  # Core Runs
  pymodel             Run Python model (with DPAPP)
  bmv2                Run BMv2 model (with DPAPP)
  saiserver           Run SAI Thrift Server
  dpapp               Run DPAPP
  ptftest             Run PTF tests

  # Builds
  bmv2-build          Build BMv2 DASH environment
  pymodel-build       Build Python model DASH environment

  # Cleans
  py-clean            Clean Python artifacts
  sai-clean           Clean SAI headers
  sai-server-clean    Clean SAI server
  kill                Kill all containers and processes

Examples:
  $0 pymodel
  $0 bmv2-build
  $0 sai-clean
EOF
    exit 1
}

[[ $# -eq 0 ]] && usage

remove_container() {
    local container="$1"
    if command -v docker &>/dev/null; then
        sudo docker rm -f "${container}-${USER}" >/dev/null 2>&1 || true
    fi
}

case "$1" in

    sai-clean)
        clear
        echo "Cleaning SAI headers..."
        sudo chown -R "${USER}:${USER}" .
        sudo make sai-clean HOST_USER=$(id -u) HOST_GROUP=$(id -g)
        ;;

    sai-server-clean)
        clear
        echo "Cleaning SAI Thrift Server..."
        sudo chown -R "${USER}:${USER}" .
        sudo make saithrift-server-clean HOST_USER=$(id -u) HOST_GROUP=$(id -g)
        ;;

    py-clean)
        clear
        echo "Cleaning Python model artifacts..."
        make py-artifacts-clean
        ;;

    py-build)
        clear
        echo "Building Python model DASH..."
        sudo chown -R "${USER}:${USER}" .
        sudo make py-artifacts docker-saithrift-bldr
        sudo make docker-pymodel-bldr
        sudo make sai TARGET=pymodel
        sudo make docker-dash-dpapp dpapp TARGET=pymodel
        sudo make check-sai-spec
        sudo make saithrift-server HOST_USER=$(id -u) HOST_GROUP=$(id -g)
        sudo make docker-saithrift-client
        ;;

    pymodel)
        clear
        echo "Running Python Model with DPAPP..."
        remove_container "pymodel_dash"
        sudo make run-pymodel HAVE_DPAPP=y
        ;;

    py-dpapp)
        clear
        echo "Running DPAPP for pymodel..."
        sudo make run-dpapp TARGET=pymodel
        ;;

    py-saiserver)
        clear
        echo "Running SAI Thrift Server for pymodel..."
        remove_container "dash-saithrift-server"
        sudo make run-saithrift-server TARGET=pymodel
        ;;


    bmv2)
        clear
        echo "Running BMv2 model with DPAPP..."
        make network HAVE_DPAPP=y
        remove_container "simple_switch"
        sudo make run-switch HAVE_DPAPP=y
        ;;

    bmv2-saiserver)
        clear
        echo "Running SAI Thrift Server for bmv2..."
        remove_container "dash-saithrift-server"
        sudo make run-saithrift-server
        ;;

    bmv2-dpapp)
        clear
        echo "Running DPAPP for bmv2..."
        sudo make run-dpapp
        ;;

    ptftest)
        clear
        echo "Running PTF Tests..."
        sudo make docker-saithrift-client
        sudo make run-saithrift-ptftests
        ;;

    bmv2-build)
        clear
        echo "Building BMv2 DASH..."
        git submodule update --init
        sudo chown -R "${USER}:${USER}" .
        sudo make docker-dash-p4c p4
        sudo make docker-saithrift-bldr
        sudo make docker-bmv2-bldr
        sudo make sai
        sudo make docker-dash-dpapp dpapp check-sai-spec
        sudo make saithrift-server HOST_USER=$(id -u) HOST_GROUP=$(id -g)
        sudo make docker-saithrift-client
        ;;

    kill)
        clear
        echo "Killing all containers and processes..."
        sudo make kill-all
        sudo make kill-dpapp || true
        sudo make kill-pymodel || true
        ;;

    *)
        echo "Invalid option: '$1'"
        usage
        ;;
esac
