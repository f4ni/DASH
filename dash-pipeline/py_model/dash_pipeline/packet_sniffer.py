
import time
import dash_py_model
import lib.__vars as vars
import lib.__id_map as ids
from lib.__utils import py_log
from scapy.all import sniff, sendp, Ether, hexdump

def pretty_print_packet(pkt_bytes):
    pkt = Ether(pkt_bytes) if isinstance(pkt_bytes, (bytes, bytearray)) else pkt_bytes

    print("\n" + "="*80)
    print("Hex Dump")
    print("="*80)
    hexdump(pkt)
    print("="*80 + "\n")

def sniff_packet():
    def process_packet(pkt):
        raw_bytes = bytes(pkt)
        py_log("info", "Packet received on", pkt.sniffed_on, raw_bytes.hex())

        result = dash_py_model.dash_py_model(raw_bytes)
        if result:
            ether_frame = Ether(result)
            pretty_print_packet(ether_frame)
            egress_port = vars.iface_list[vars.standard_metadata.egress_spec]
            py_log("info", "Transmitting packet of size", len(ether_frame), "out of port", egress_port)
            sendp(ether_frame, iface=egress_port, verbose=False)

    sniff(
        iface=[vars.iface_list[0], vars.iface_list[1], vars.iface_list[2]],
        prn=process_packet,
        store=False,
        filter="inbound"
    )
