#!/bin/bash

# Helper script to run a second SAI Thrift Server for the Standby instance
# Maps SAI Thrift Port 9093 -> P4Runtime Port 9560 (Standby)

# Find the sai-thrift-builder image (local build)
IMAGE=$(docker images --format "{{.Repository}}:{{.Tag}}" | grep "dash-saithrift-bldr" | head -n 1)

if [ -z "$IMAGE" ]; then
    echo "Error: Could not find dash-saithrift-bldr image. Run 'make docker-saithrift-bldr' first."
    exit 1
fi

echo "Using image: $IMAGE"

# Run SAI Server in a new container
# - Mount SAI directory for libs
# - Use host networking to expose port 9093
# - Configure sai.profile to point to localhost:9560 (Standby P4Runtime)

docker run \
    --rm \
    --net=host \
    --name dash-saithrift-server-standby \
    -v $(pwd)/SAI:/SAI \
    -v $(pwd)/SAI/SAI/meta:/meta \
    -w /SAI/rpc/usr/sbin \
    -e LD_LIBRARY_PATH=/SAI/lib:/usr/local/lib \
    $IMAGE \
    bash -c "
        echo 'Creating Standby Profile...'
        mkdir -p /tmp/standby_conf
        echo 'SAI_DASH_GRPC_TARGET=localhost:9560' > /tmp/standby_conf/sai.profile
        
        echo 'Starting SAI Server on Port 9093...'
        ./saiserver -p 9093 -d /tmp/standby_conf -f /tmp/standby_conf/sai.profile
    "
