from lib.__vars import *
from lib.__utils import *
from lib.__table import *

from pmv2.dash_tunnel import do_tunnel_encap
from pmv2.dash_acl import *
from pmv2.dash_conntrack import *
from pmv2.stages.inbound_routing import *
from pmv2.stages.outbound_mapping import *

class inbound:
    @classmethod
    def apply(cls):
        if STATEFUL_P4:
            ConntrackIn.apply()
        if PNA_CONNTRACK:
            ConntrackIn.apply()
            if meta.overlay_data.sip != 0:
                do_action_nat64.apply()

        # ACL
        if not meta.conntrack_data.allow_in:
            # acl.apply()
            acl.inbound_apply()

        if STATEFUL_P4:
            ConntrackOut.apply()
        elif PNA_CONNTRACK:
            ConntrackOut.apply()

        inbound_routing_stage.apply()

        meta.routing_actions = dash_routing_actions_t.ENCAP_U0

        do_tunnel_encap(
            meta.u0_encap_data.underlay_dmac,
            meta.u0_encap_data.underlay_smac,
            meta.u0_encap_data.underlay_dip,
            meta.u0_encap_data.underlay_sip,
            dash_encapsulation_t.VXLAN,
            meta.u0_encap_data.vni
        )
