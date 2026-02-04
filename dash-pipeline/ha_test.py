import sys
import os
import time
import threading
from scapy.all import *

# Interfaces
ACTIVE_IN = "veth1"      # Connects to veth0 (Active Port 0)
ACTIVE_OUT = "veth3"     # Connects to veth2 (Active Port 1 - HA Link)
STANDBY_IN = "veth7"     # Connects to veth6 (Standby Port 0 - HA Link?) 
                         # Note: Setup script used veth6 as Port 0, veth8 as Port 1.
                         # If Active sends on Port 1, we assume it goes to Standby Port 0?
                         # Usually HA link is dedicated. Let's assume Port 0 on Standby is connected to Port 1 on Active.
STANDBY_OUT = "veth9"    # Connects to veth8 (Standby Port 1)

DASH_ETHTYPE = 0x876d

def test_ha():
    print("Starting HA Test...")
    print("1. Sending TCP SYN to Active DPU (veth0 via veth1)...")
    
    # original packet
    pkt = Ether(src="00:00:00:00:00:11", dst="00:11:22:33:44:55") / IP(src="1.1.1.1", dst="2.2.2.2") / TCP(sport=100, dport=200, flags="S")
    
    # We need a listener for the Sync Req
    # Store captured pkt in list
    captured_req = []
    
    def capture_req(p):
        if p.type == DASH_ETHTYPE:
            print("   [Active->] Captured DASH packet (Likely FLOW_SYNC_REQ)")
            captured_req.append(p)
            return True
        return False

    # Start sniffer on ACTIVE_OUT
    t = AsyncSniffer(iface=ACTIVE_OUT, prn=capture_req, count=1, timeout=5)
    t.start()
    time.sleep(1) # wait for sniffer start
    
    sendp(pkt, iface=ACTIVE_IN, verbose=False)
    t.join()
    
    if not captured_req:
        print("FAIL: Did not receive FLOW_SYNC_REQ from Active DPU.")
        return
    
    req_pkt = captured_req[0]
    # Check if it is indeed Sync Req? 
    # We assume yes for now.
    
    print("2. Forwarding FLOW_SYNC_REQ to Standby DPU (veth6 via veth7)...")
    
    captured_ack = []
    def capture_ack(p):
        if p.type == DASH_ETHTYPE:
            print("   [Standby->] Captured DASH packet (Likely FLOW_SYNC_ACK)")
            captured_ack.append(p)
            return True
        return False
        
    t2 = AsyncSniffer(iface=STANDBY_IN, prn=capture_ack, count=1, timeout=5) # Wait, egress is veth9?
    # Py model egresses based on egress_spec. 
    # ha.py sets egress_spec=1.
    # Standby Port 0 is veth6. Port 1 is veth8.
    # If egress_spec=1, it goes out veth8 (connected to veth9).
    t2 = AsyncSniffer(iface=STANDBY_OUT, prn=capture_ack, count=1, timeout=5) 
    t2.start()
    time.sleep(1)
    
    # Send REQ to Standby
    sendp(req_pkt, iface=STANDBY_IN, verbose=False)
    t2.join()
    
    if not captured_ack:
        print("FAIL: Did not receive FLOW_SYNC_ACK from Standby DPU.")
        return

    ack_pkt = captured_ack[0]
    
    print("3. Forwarding FLOW_SYNC_ACK back to Active DPU (veth2 via veth3)...")
    
    # When Active receives ACK, it updates flow and potentially releases original packet?
    # Or just updates state.
    # ha.py says: "if packet_source == DPAPP ... forward original packet".
    # But the ACK comes from Peer.
    # Logic in ha.py: 
    #   if (meta.ha.ha_role == ACTIVE ... and packet_source == DPAPP) -> forward original.
    #   Wait, when Active receives ACK from PEER (Source=PEER), 
    #   it traps to DPAPP (conntrack_flow_handle).
    #   DPAPP updates flow to SYNCED.
    #   Does DPAPP recirculate?
    #   flow.c: dash_flow_update -> dash_sai_update_flow_entry.
    #   It returns 0.
    #   It does NOT seem to reinject the packet. 
    #   So the ACK is consumed. 
    #   The ORIGINAL packet that triggered the flow create was recirculated once?
    #   Actually the original packet from pipeline (Packet Source EXTERNAL) -> Miss -> DPAPP.
    #   DPAPP -> Create -> Recirculate (Source DPAPP).
    #   HA Stage (Active) -> Transform to SYNC_REQ -> Send to Peer.
    #   Use `meta.to_dpapp = False`. 
    #   So the original packet is *transformed* into SYNC_REQ. It is gone.
    #   Unless we clone it? HLd says:
    #   "Active DPU: Upon receiving the return packet (ACK) ... the flow is updated to SYNCED state."
    #   "Traffic can now flow."
    #   So the first packet (SYN) is sacrificed for Sync? Or is the payload carried?
    #   `sync_req` logic has: `hdr.flow_data = ...`. It carries flow key/data.
    #   It does NOT carry the original payload usually, unless we encap it?
    #   DASH HA HLD might imply the first packet is lost or the Req carries it.
    #   Looking at `py_model`: It builds a NEW DASH header. It does not seem to preserve inner payload if it constructs from scratch.
    #   `conntrack_build_dash_header` resets headers?
    #   It sets `hdr.packet_meta`.
    #   But `dash_parser` extracts.
    #   If `py_model` implementation just modifies headers and keeps payload, then payload exists.
    #   `conntrack_build_dash_header` creates new `hdr.packet_meta`.
    #   It doesn't touch `hdr.customer_ipv4` etc?
    #   Wait, `deparser` emits `hdr.customer_ipv4`.
    #   If they are still valid in `hdr`, they are emitted.
    #   So the SYNC REQ might carry the TCP SYN inside it.
    #   Let's check `ha_test.py` behavior.
    
    sendp(ack_pkt, iface=ACTIVE_OUT, verbose=False) # Inject into veth3 -> veth2 (Active Port 1)
    
    print("Test Complete. Check logs for Success.")

if __name__ == "__main__":
    if os.geteuid() != 0:
        print("Run as root (needed for scapy/sniffing).")
        sys.exit(1)
    test_ha()
