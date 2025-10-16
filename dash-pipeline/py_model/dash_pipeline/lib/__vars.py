from pmv2.dash_headers import *
from pmv2.dash_metadata import *
from lib.__standard_metadata import *
from lib.__packet_in import *
from lib.__packet_out import *

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
