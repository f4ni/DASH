from py_model.libs.__packet_in import *
from py_model.libs.__packet_out import *
from py_model.libs.__standard_metadata import *
from py_model.data_plane.dash_headers import *
from py_model.data_plane.dash_metadata import *

hdr = headers_t()
meta = metadata_t()
standard_metadata = standard_metadata_t()

iface_list = []

pkt_in = packet_in()
pkt_out = packet_out()

def deny():
    meta.dropped = True
