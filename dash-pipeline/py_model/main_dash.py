import sys
import threading
import signal
from scapy.all import sniff, sendp, Ether, hexdump
from py_model.libs import __vars as vars
from py_model.libs.__utils import py_log
from py_model.dash_py_v1model import dash_py_model
from py_model.control_plane.grpc_server import serve


def print_packet(pkt_bytes: bytes | Ether) -> None:
    """Pretty-print a packet as a hex dump."""
    pkt = Ether(pkt_bytes) if isinstance(pkt_bytes, (bytes, bytearray)) else pkt_bytes
    print("\n" + "=" * 80)
    print("Hex Dump")
    print("=" * 80)
    hexdump(pkt)
    print("=" * 80 + "\n")


def sniff_packet() -> None:
    """Capture packets on configured interfaces and process them."""
    def process_packet(pkt: Ether) -> None:
        raw_bytes = bytes(pkt)
        py_log("info", "Packet received on", pkt.sniffed_on, raw_bytes.hex())

        result = dash_py_model(raw_bytes)
        if not result:
            return

        ether_frame = Ether(result)
        print_packet(ether_frame)

        egress_idx = vars.standard_metadata.egress_spec
        if egress_idx < len(vars.iface_list):
            egress_port = vars.iface_list[egress_idx]
            py_log("info", f"Transmitting {len(ether_frame)} bytes out of port {egress_port}")
            sendp(ether_frame, iface=egress_port, verbose=False)
        else:
            py_log("warn", f"Egress port index {egress_idx} out of range — dropping packet.")

    iface_list = vars.iface_list
    # py_log("info", "Starting packet sniffing on interfaces:", iface_list)

    sniff(
        iface=iface_list,
        prn=process_packet,
        store=False,
        filter="inbound"
    )


def setup_interfaces(args: list[str]) -> None:
    """Parse command-line arguments and populate iface_list."""
    if len(args) < 3:
        print("\nUsage: python3 main_py_dash.py '<IFACE0>' '<IFACE1>' ['<IFACE2>']")
        sys.exit(1)

    vars.iface_list.extend(args[1:4])  # add 2 or 3 interfaces
    print("")  # blank line for readability

    for idx, iface in enumerate(vars.iface_list):
        role = "(DPAPP)" if idx == 2 else ""
        print(f"Adding interface {iface} as port {idx} {role}")
    print("")


def main() -> None:
    """Main entry point for running the DASH Python model."""
    setup_interfaces(sys.argv)

    # Start gRPC server
    server_thread = threading.Thread(target=serve, daemon=True)
    server_thread.start()

    # Start packet sniffer
    sniff_thread = threading.Thread(target=sniff_packet, daemon=True)
    sniff_thread.start()

    # Graceful shutdown handler
    def handle_exit(signum, frame):
        print("\nStopping Python DASH model...")
        sys.exit(0)

    signal.signal(signal.SIGINT, handle_exit)
    signal.signal(signal.SIGTERM, handle_exit)

    # Keep threads alive
    server_thread.join()
    sniff_thread.join()


if __name__ == "__main__":
    main()
