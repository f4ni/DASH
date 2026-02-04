## run active instance:
# sudo make run-pymodel HAVE_DPAPP=y PY_ARGS='--port 9559 --role active'

## run standby instance:
# sudo make run-pymodel HAVE_DPAPP=y IFACE0=veth7 IFACE1=veth8 DPAPP_LINK=veth10 DPAPP_LINK_PEER=veth11 CONTAINER_NAME=dash-pymodel-standby PY_ARGS='--port 9560 --role standby'





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
        docker rm -f "${container}-${USER}" >/dev/null 2>&1 || true
    fi
}

case "$1" in

    sai-clean)
        clear
        echo "Cleaning SAI headers..."
        # chown -R "${USER}:${USER}" .
        make sai-clean HOST_USER=$(id -u) HOST_GROUP=$(id -g)
        ;;

    sai-server-clean)
        clear
        echo "Cleaning SAI headers..."
        # chown -R "${USER}:${USER}" .
        make saithrift-server-clean HOST_USER=$(id -u) HOST_GROUP=$(id -g)
        ;;

    py-clean)
        clear
        echo "Cleaning Python model artifacts..."
        make py-artifacts-clean
        ;;

    py-build)
        clear
        echo "Building Python model DASH..."
        chown -R "${USER}:${USER}" .
        make py-artifacts docker-saithrift-bldr
        make docker-pymodel-bldr
        make sai TARGET=pymodel
        make docker-dash-dpapp dpapp TARGET=pymodel
        # make check-sai-spec
        make saithrift-server HOST_USER=$(id -u) HOST_GROUP=$(id -g)
        make docker-saithrift-client
        ;;

    pymodel)
        clear
        echo "Running Python Model with DPAPP..."
        remove_container "pymodel_dash"
        make run-pymodel HAVE_DPAPP=y
        ;;

    py-dpapp)
        clear
        echo "Running DPAPP for pymodel..."
        make run-dpapp TARGET=pymodel
        ;;

    py-saiserver)
        clear
        echo "Running SAI Thrift Server for pymodel..."
        remove_container "dash-saithrift-server"
        make run-saithrift-server TARGET=pymodel
        ;;


    bmv2)
        clear
        echo "Running BMv2 model with DPAPP..."
        make network HAVE_DPAPP=y
        remove_container "simple_switch"
        make run-switch HAVE_DPAPP=y
        ;;

    bmv2-saiserver)
        clear
        echo "Running SAI Thrift Server for bmv2..."
        remove_container "dash-saithrift-server"
        make run-saithrift-server
        ;;

    bmv2-dpapp)
        clear
        echo "Running DPAPP for bmv2..."
        make run-dpapp
        ;;

    ptf)
        clear
        echo "Running PTF Tests..."
        make docker-saithrift-client
        make run-saithrift-ptftests
        ;;

    pytests)
        clear
        echo "Running Pytests..."
        make docker-saithrift-client
        make run-saithrift-pytests
        ;;

    bmv2-build)
        clear
        echo "Building BMv2 DASH..."
        #git submodule update --init
        # chown -R "${USER}:${USER}" .
        make docker-dash-p4c p4-clean p4
        make docker-saithrift-bldr docker-bmv2-bldr sai
        make docker-dash-dpapp dpapp
        make check-sai-spec
        make saithrift-server
        make docker-saithrift-client
        ;;

    kill)
        clear
        echo "Killing all containers and processes..."
        make kill-all
        make kill-dpapp || true
        make kill-pymodel || true
        ;;

    *)
        echo "Invalid option: '$1'"
        usage
        ;;
esac
