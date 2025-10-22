from pmv1.dash_headers import *
from pmv1.dash_metadata import *
from libs.__standard_metadata import *
from libs.__packet_in import *
from libs.__packet_out import *

hdr = headers_t()
meta = metadata_t()
standard_metadata = standard_metadata_t()

iface_list = []

pkt_in = packet_in()
pkt_out = packet_out()

def drop():
    meta.dropped = True

def deny():
    meta.dropped = True
