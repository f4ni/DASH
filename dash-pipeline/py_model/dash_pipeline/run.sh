#!/bin/bash

# Define usage function
usage() {
    echo "Usage: $0 [pymodel|bmv2|saiserver|ptftest|dpapp|build|kill]"
    echo
    echo "Options:"
    echo "  genjson     Generate json file(s)"
    echo "  pymodel     Run Python model"
    echo "  bmv2        Run BMv2 switch"
    echo "  saiserver   Run SAI thrift server"
    echo "  ptftest     Run PTF tests"
    echo "  dpapp       Run DPApp"
    echo "  build       Build all required targets"
    echo "  kill        Kill all consoles/processes"
    exit 1
}

# Check if argument is provided
if [ -z "$1" ]; then
    usage
fi

# Execute commands based on the argument
case "$1" in
    pymodel)
        echo "Running Python Model..."
        echo ""
        cd ../../DASH/dash-pipeline || exit 1
        make network HAVE_DPAPP=y
        cd py_model/dash_pipeline || exit 1
        python3 main_py_dash.py "veth0" "veth2" "veth4" "veth5"
        ;;
    bmv2)
        echo "Running bmv2..."
        cd ../../DASH/dash-pipeline || exit 1
        make network HAVE_DPAPP=y
        docker rm -f simple_switch-"${USER}"
        make run-switch HAVE_DPAPP=y
        ;;
    saiserver)
        echo "Running saiserver..."
        cd ../../DASH/dash-pipeline || exit 1
        # make saithrift-server
        docker rm -f dash-saithrift-server-"${USER}"
        make run-saithrift-server
        ;;
    ptftest)
        echo "Running ptftests..."
        cd ../../DASH/dash-pipeline || exit 1
        make docker-saithrift-client
        make run-saithrift-ptftests
        ;;
    dpapp)
        echo "Running dpapp..."
        cd ../../DASH/dash-pipeline || exit 1
        make run-dpapp
        ;;
    kill)
        echo "Killing all consoles..."
        cd ../../DASH/dash-pipeline || exit 1
        make kill-all
        make kill-dpapp
        pkill -f main_py_dash.py
        ;;
    build)
        echo "Building DASH..."
        cd ../../DASH/dash-pipeline || exit 1
        git submodule update --init
        make docker-dash-p4c
        make p4
        make docker-saithrift-bldr
        make docker-bmv2-bldr
        make sai
        make docker-dash-dpapp
        make dpapp
        make check-sai-spec
        make saithrift-server
        make docker-saithrift-client
        ;;
    genjson)
        echo "Generating JSON files for Python Model..."
        python3 p4info_gen.py
        ;;
    *)
        echo "Invalid option. Please retry."
        usage
        ;;
esac
