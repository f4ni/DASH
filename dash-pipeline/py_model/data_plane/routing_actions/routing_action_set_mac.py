from py_model.libs.__utils import *
from py_model.data_plane.dash_tunnel import *

def push_action_set_smac(overlay_smac: Annotated[int, EthernetAddress_size]):
    # not used by now
    py_log("info", "push_action_set_smac")
    pass

def push_action_set_dmac(overlay_dmac: Annotated[int, EthernetAddress_size]):
    py_log("info", "push_action_set_dmac called")
    meta.routing_actions = meta.routing_actions | dash_routing_actions_t.SET_DMAC
    meta.overlay_data.dmac = overlay_dmac

class do_action_set_smac:
    @classmethod
    def apply(cls):
        # not used by now
        py_log("info", "do_action_set_smac")

class do_action_set_dmac:
    @classmethod
    def apply(cls):
        py_log("info", "do_action_set_dmac")
        if (meta.routing_actions & dash_routing_actions_t.SET_DMAC == 0):
            return
        
        hdr.customer_ethernet.dst_addr = meta.overlay_data.dmac
