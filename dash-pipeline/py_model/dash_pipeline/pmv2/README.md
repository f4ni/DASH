
Flow:
=====

1. dash_lookup_stage
    * pre_pipeline_stage
        ** appliance.apply
        ** internal_config.apply
    * direction_lookup_stage
        ** direction_lookup.apply
    * eni_lookup_stage
        ** eni_ether_address_map.apply
    * dash_eni_stage
        ** eni.apply
    * do_tunnel_decap

2. conntrack_lookup_stage
    * flow_entry.apply
    * flow_entry_bulk_get_session_filter.apply
    * flow_entry_bulk_get_session.apply

3. ha_stage
    * ha_scope.apply
    * ha_set.apply

4. trusted_vni_stage
    * global_trusted_vni.apply
    * eni_trusted_vni.apply

5. dash_match_stage
    * acl_group.apply
    * outbound.apply
        ** ConntrackOut.apply
        ** acl.apply
        ** ConntrackIn.apply
        ** outbound_routing_stage.apply
        ** outbound_mapping_stage.apply
        ** outbound_pre_routing_action_apply_stage.apply
    * inbound.apply
        ** ConntrackIn.apply
        ** do_action_nat64.apply
        ** acl.apply
        ** ConntrackOut.apply
        ** inbound_routing_stage.apply
        ** do_tunnel_encap.apply

6. conntrack_flow_handle.apply

7. routing_action_apply.apply

8. underlay.apply

9. metering_update_stage.apply

