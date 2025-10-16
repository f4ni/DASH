from lib.__vars import *
from lib.__utils import *
from lib.__table import *

from pmv2.dash_acl import *
from pmv2.dash_conntrack import *
from pmv2.stages.outbound_mapping import *
from pmv2.stages.outbound_routing import *
from pmv2.stages.outbound_pre_routing_action_apply import *

class outbound:
    @classmethod
    def apply(cls):
        if STATEFUL_P4:
            ConntrackOut.apply()
        if PNA_CONNTRACK:
            ConntrackOut.apply()

        # ACL
        if not meta.conntrack_data.allow_out:
            # acl.apply()
            acl.outbound_apply()

        if STATEFUL_P4:
            ConntrackIn.apply()
        if PNA_CONNTRACK:
            ConntrackIn.apply()

        meta.lkup_dst_ip_addr = meta.dst_ip_addr
        meta.is_lkup_dst_ip_v6 = meta.is_overlay_ip_v6

        outbound_routing_stage.apply()
        outbound_mapping_stage.apply()
        outbound_pre_routing_action_apply_stage.apply()

