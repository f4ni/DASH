from libs.__vars import *
from libs.__utils import *
from libs.__obj_classes import *
from pmv1.stages.tunnel_stage import *
from pmv1.stages.outbound_port_map import *


class outbound_pre_routing_action_apply_stage:
    @classmethod
    def apply(cls):
        py_log("info", "outbound_pre_routing_action_apply_stage")
        # Outbound pre-routing action apply stage is added here for certain pre-processing
        if meta.target_stage != dash_pipeline_stage_t.OUTBOUND_PRE_ROUTING_ACTION_APPLY:
            return

        outbound_port_map_stage.apply()

        tunnel_stage.apply()

        # Once done, move to routing action apply stage
        meta.target_stage = dash_pipeline_stage_t.ROUTING_ACTION_APPLY
