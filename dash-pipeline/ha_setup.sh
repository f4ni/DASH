#!/bin/bash
set -e

# Define interfaces for Standby DPU
STBY_IFACE0="veth6"
STBY_IFACE1="veth8"
STBY_DPAPP="veth10"

# Peers
STBY_IFACE0_PEER="veth7"
STBY_IFACE1_PEER="veth9"
STBY_DPAPP_PEER="veth11"

create_veth() {
    local name=$1
    local peer=$2
    if ip link show $name >/dev/null 2>&1; then
        echo "Interface $name already exists."
    else
        echo "Creating $name <-> $peer"
        sudo ip link add name $name type veth peer name $peer
        sudo ip link set dev $name up
        sudo ip link set dev $peer up
        sudo ip link set $name mtu 9500
        sudo ip link set $peer mtu 9500
        # Disable IPv6 to match main Makefile behavior
        sudo sysctl -w net.ipv6.conf.$name.disable_ipv6=1 >/dev/null
        sudo sysctl -w net.ipv6.conf.$peer.disable_ipv6=1 >/dev/null
    fi
}

echo "Setting up Standby Interfaces..."
create_veth $STBY_IFACE0 $STBY_IFACE0_PEER
create_veth $STBY_IFACE1 $STBY_IFACE1_PEER
create_veth $STBY_DPAPP  $STBY_DPAPP_PEER

echo ""
echo "Setup Complete."
echo ""
echo "To run ACTIVE DPU (Terminal 1) [TEST MODE]:"
echo "  make run-pymodel HAVE_DPAPP=y PY_ARGS='--port 9559 --role active'"
echo ""
echo "To run STANDBY DPU (Terminal 2) [TEST MODE]:"
echo "  make run-pymodel HAVE_DPAPP=y IFACE0=$STBY_IFACE0 IFACE1=$STBY_IFACE1 DPAPP_LINK=$STBY_DPAPP DPAPP_LINK_PEER=$STBY_DPAPP_PEER CONTAINER_NAME=dash-pymodel-standby PY_ARGS='--port 9560 --role standby'"
echo ""
echo "Then Run Test (Terminal 3):"
echo "  sudo python3 ha_test.py"
