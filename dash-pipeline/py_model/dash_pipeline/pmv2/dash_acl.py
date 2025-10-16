from lib.__vars import *
from lib.__table import *
from lib.__utils import *
from lib.__counters import *


class acl:
    @staticmethod
    def permit():
        pass

    @staticmethod
    def permit_and_continue():
        pass

    @staticmethod
    def deny():
        meta.dropped = True

    @staticmethod
    def deny_and_continue():
        meta.dropped = True

    @classmethod
    def _get_namespace(cls):
        """Get ACL namespace based on the caller stage class."""
        import inspect
        frame = inspect.currentframe().f_back
        caller_cls = frame.f_locals.get('cls', None)
        if caller_cls is not None:
            return get_acl_namespace(caller_cls.__name__, cls)
        # default to inbound
        return get_acl_namespace("inbound", cls)

    @classmethod
    def apply_acl(cls, direction: str, stages: list):
        ns = cls._get_namespace()  # dynamically get namespace

        for stage_num, acl_obj, group_id in stages:
            if group_id != 0:
                py_log("info", f"Lookup in '{direction}_acl_stage{stage_num}'")
                result = acl_obj.apply()
                action = result["action_run"]
                print(f"------- ACL action: {action}\n")
                # if action in (ns.acl.deny, ns.acl.permit):
                if action in (acl.deny, acl.permit):
                    return

    @classmethod
    def inbound_apply(cls):
        stages = [
            (1, inbound_acl_stage1, meta.stage1_dash_acl_group_id),
            (2, inbound_acl_stage2, meta.stage2_dash_acl_group_id),
            (3, inbound_acl_stage3, meta.stage3_dash_acl_group_id),
        ]
        cls.apply_acl("inbound", stages)

    @classmethod
    def outbound_apply(cls):
        stages = [
            (1, outbound_acl_stage1, meta.stage1_dash_acl_group_id),
            (2, outbound_acl_stage2, meta.stage2_dash_acl_group_id),
            (3, outbound_acl_stage3, meta.stage3_dash_acl_group_id),
        ]
        cls.apply_acl("outbound", stages)


def get_acl_namespace(caller_cls_name: str, acl_cls):
    """Return a dynamic ACL namespace based on caller class name."""
    direction = "inbound" if caller_cls_name == "inbound" else "outbound"

    class _Namespace:
        dir = direction

        def __init__(self):
            def wrap(func, name):
                def wrapped(*args, **kwargs):
                    py_log("info", f"{direction}.{name} called")
                    return func(*args, **kwargs)
                wrapped.__name__ = f"{direction}.acl.{name}"
                wrapped.__qualname__ = f"{direction}.acl.{name}"
                return staticmethod(wrapped)

            # Use the acl_cls passed as argument to avoid forward reference issue
            self.acl = type('acl_ns', (), {
                'permit': wrap(acl_cls.permit, "permit"),
                'permit_and_continue': wrap(acl_cls.permit_and_continue, "permit_and_continue"),
                'deny': wrap(acl_cls.deny, "deny"),
                'deny_and_continue': wrap(acl_cls.deny_and_continue, "deny_and_continue"),
            })()

    return _Namespace()


def make_acl_stage(cls, stage_num, direction, caller_cls_name=None):
    """
    Creates an ACL stage table. Dynamically determines ACL namespace
    based on caller_cls_name (inbound/outbound stage class)
    """
    DEFINE_TABLE_COUNTER(f"{direction}_stage{stage_num}_counter", CounterType.PACKETS_AND_BYTES)
    ATTACH_TABLE_COUNTER(f"{direction}_stage{stage_num}_counter", f"{direction}_acl_stage{stage_num}")

    # Dynamically get ACL namespace if caller_cls_name is provided
    if caller_cls_name:
        ns = get_acl_namespace(caller_cls_name, acl)
    else:
        ns = get_acl_namespace(direction, acl)

    return Table(
        key={
            f"meta.stage{stage_num}_dash_acl_group_id":
                (EXACT, {"name": "dash_acl_group_id", "type": "sai_object_id_t",
                         "isresourcetype": "true", "objects": "SAI_OBJECT_TYPE_DASH_ACL_GROUP"}),
            "meta.dst_ip_addr": (LIST, {"name": "dip", "type": "sai_ip_prefix_list_t", "match_type": "list"}),
            "meta.src_ip_addr": (LIST, {"name": "sip", "type": "sai_ip_prefix_list_t", "match_type": "list"}),
            "meta.ip_protocol": (LIST, {"name": "protocol", "type": "sai_u8_list_t", "match_type": "list"}),
            "meta.src_l4_port": (RANGE_LIST, {"name": "src_port", "type": "sai_u16_range_list_t", "match_type": "range_list"}),
            "meta.dst_l4_port": (RANGE_LIST, {"name": "dst_port", "type": "sai_u16_range_list_t", "match_type": "range_list"})
        },
        actions=[
            ns.acl.permit,
            ns.acl.permit_and_continue,
            ns.acl.deny,
            ns.acl.deny_and_continue,
        ],
        default_action=ns.acl.deny,
        tname=f"{direction}_acl_stage{stage_num}",

        sai_table=SaiTable(
            name="dash_acl_rule",
            api="dash_acl",
            stage=f"acl.stage{stage_num}",
            order=1,
            isobject="true",
        ),
    )


# Example ACL stage creation
outbound_acl_stage1 = make_acl_stage(acl, 1, "outbound")
outbound_acl_stage2 = make_acl_stage(acl, 2, "outbound")
outbound_acl_stage3 = make_acl_stage(acl, 3, "outbound")

inbound_acl_stage1 = make_acl_stage(acl, 1, "inbound")
inbound_acl_stage2 = make_acl_stage(acl, 2, "inbound")
inbound_acl_stage3 = make_acl_stage(acl, 3, "inbound")
