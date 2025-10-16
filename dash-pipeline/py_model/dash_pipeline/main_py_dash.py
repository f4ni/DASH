import sys
import lib.__vars as vars
from grpc_server import serve

from packet_sniffer import sniff_packet
import threading

if __name__ == "__main__":
    if len(sys.argv) < 4:
        print("\nUsage: python3 main_py_dash.py "'<IFACE0>'" "'<IFACE1>'" "'<IFACE2>'"")
        sys.exit(1)

    vars.iface_list.append(sys.argv[1])
    vars.iface_list.append(sys.argv[2])
    vars.iface_list.append(sys.argv[3])

    print(f"\nAdding interface {vars.iface_list[0]} as port 0")
    print(f"Adding interface {vars.iface_list[1]} as port 1")
    print(f"Adding interface {vars.iface_list[2]} as port 2\n")

    # Start gRPC server in background thread
    server_thread = threading.Thread(target=serve, daemon=True)
    server_thread.start()

    # Run packet sniffer in parallel
    sniff_thread = threading.Thread(target=sniff_packet, daemon=True)
    sniff_thread.start()

    # Keep main thread alive
    server_thread.join()
    sniff_thread.join()