# from sai_thrift.sai_headers import *
# from sai_base_test import *
# from p4_dash_utils import *
# from thrift.transport import TSocket
# from thrift.transport import TTransport
# from thrift.protocol import TBinaryProtocol
# from sai_dash_utils import VnetAPI

# @use_flow
# class SaiThriftHaSanityTest(VnetAPI):
#     """ Test saithrift vnet outbound towards dpapp"""

#     def setUp(self):
#         super(SaiThriftHaSanityTest, self).setUp()
#         self.switch_id = 5
#         self.outbound_vni = 60
#         self.vnet_vni = 100
#         self.eni_mac = "00:cc:cc:cc:cc:cc"
#         self.our_mac = "00:00:02:03:04:05"
#         self.dst_ca_mac = "00:dd:dd:dd:dd:dd"
#         self.vip = "172.16.1.100"
#         self.ca_prefix_addr = "10.1.0.0"
#         self.ca_prefix_mask = "255.255.0.0"
#         self.dst_ca_ip = "10.1.2.50"
#         self.dst_pa_ip = "172.16.1.20"
#         self.src_vm_pa_ip = "172.16.1.1"

#         # SAI attribute name
#         self.ip_addr_family_attr = 'ip4'
#         # SAI address family
#         self.sai_ip_addr_family = SAI_IP_ADDR_FAMILY_IPV4

#         # Establish connection to Standby Instance (Port 9560)
#         self.client_stby = None
#         self.transport_stby = None
        
#         try:
#             self.transport_stby = TSocket.TSocket('localhost', 9560)
#             self.transport_stby = TTransport.TBufferedTransport(self.transport_stby)
#             self.protocol_stby = TBinaryProtocol.TBinaryProtocol(self.transport_stby)
#             self.transport_stby.open()
#             self.client_stby = self.client.__class__(self.protocol_stby)
#             print("Connected to Standby Client on port 9560")
#         except Exception as e:
#             print(f"Failed to connect to Standby instance: {e}")

#     def configureVnet(self, client, teardown_collector):
#         """Create VNET configuration on the specified client"""
#         orig_client = self.client
#         self.client = client
#         orig_add = self.add_teardown_obj
#         self.add_teardown_obj = teardown_collector
        
#         try:
#             self.vip_create(self.vip)
#             self.direction_lookup_create(self.outbound_vni)
            
#             gtve = sai_thrift_global_trusted_vni_entry_t(switch_id=self.switch_id,
#                     vni_range=sai_thrift_u32_range_t(min=self.outbound_vni, max=self.outbound_vni))
#             sai_thrift_create_global_trusted_vni_entry(self.client, gtve)
#             self.add_teardown_obj(sai_thrift_remove_global_trusted_vni_entry, self.client, gtve)

#             self.dash_acl_group_create()
#             out_acl_group_id = self.dash_acl_group_create()

#             vnet_id = self.vnet_create(self.vnet_vni)
#             if client == orig_client:
#                 self.vnet = vnet_id

#             outbound_routing_group_id = self.outbound_routing_group_create(disabled=False)

#             eni_id = self.eni_create(
#                 vm_underlay_dip=sai_ipaddress(self.src_vm_pa_ip),
#                 vm_vni=9,
#                 vnet_id=vnet_id,
#                 outbound_routing_group_id=outbound_routing_group_id)

#             flow_table = sai_thrift_create_flow_table(self.client,
#                         max_flow_count=128,
#                         dash_flow_enabled_key = SAI_DASH_FLOW_ENABLED_KEY_ENI_MAC
#                                                |SAI_DASH_FLOW_ENABLED_KEY_VNI
#                                                |SAI_DASH_FLOW_ENABLED_KEY_PROTOCOL
#                                                |SAI_DASH_FLOW_ENABLED_KEY_SRC_IP
#                                                |SAI_DASH_FLOW_ENABLED_KEY_DST_IP
#                                                |SAI_DASH_FLOW_ENABLED_KEY_SRC_PORT
#                                                |SAI_DASH_FLOW_ENABLED_KEY_DST_PORT,
#                         flow_ttl_in_milliseconds=5000)
#             assert (flow_table != SAI_NULL_OBJECT_ID)
#             self.add_teardown_obj(sai_thrift_remove_flow_table, self.client, flow_table)
#             sai_thrift_set_eni_attribute(self.client, eni_oid = eni_id, flow_table_id=flow_table)

#             self.eni_mac_map_create(eni_id, self.eni_mac)

#             if self.sai_ip_addr_family == SAI_IP_ADDR_FAMILY_IPV4:
#                 out_acl_rule_id = sai_thrift_create_dash_acl_rule(self.client, dash_acl_group_id=out_acl_group_id, priority=10,
#                                                                  action=SAI_DASH_ACL_RULE_ACTION_PERMIT)
#                 self.add_teardown_obj(sai_thrift_remove_dash_acl_rule, self.client, out_acl_rule_id)

#             ca_prefix = self.ca_prefix_addr + "/16"
#             self.outbound_routing_vnet_create(outbound_routing_group_id, ca_prefix, vnet_id)

#             self.outbound_ca_to_pa_create(vnet_id, self.dst_ca_ip, self.dst_pa_ip, overlay_dmac=self.dst_ca_mac)

#             print(f"configureVnet on client {client} - OK")
#         finally:
#             self.client = orig_client
#             self.add_teardown_obj = orig_add

#     def trafficUdpTest(self):
#         src_vm_ip = "10.1.1.10"
#         outer_smac = "00:00:05:06:06:06"

#         inner_pkt = simple_udp_packet(eth_dst="02:02:02:02:02:02",
#                                         eth_src=self.eni_mac,
#                                         ip_dst=self.dst_ca_ip,
#                                         ip_src=src_vm_ip)
#         vxlan_pkt = simple_vxlan_packet(eth_dst=self.our_mac,
#                                         eth_src=outer_smac,
#                                         ip_dst=self.vip,
#                                         ip_src=self.src_vm_pa_ip,
#                                         udp_sport=11638,
#                                         with_udp_chksum=False,
#                                         vxlan_vni=self.outbound_vni,
#                                         inner_frame=inner_pkt)

#         inner_exp_pkt = simple_udp_packet(eth_dst=self.dst_ca_mac,
#                                         eth_src=self.eni_mac,
#                                         ip_dst=self.dst_ca_ip,
#                                         ip_src=src_vm_ip)
#         vxlan_exp_pkt = simple_vxlan_packet(eth_dst="00:00:00:00:00:00",
#                                         eth_src="00:00:00:00:00:00",
#                                         ip_dst=self.dst_pa_ip,
#                                         ip_src=self.vip,
#                                         udp_sport=0,
#                                         with_udp_chksum=False,
#                                         vxlan_vni=self.vnet_vni,
#                                         inner_frame=inner_exp_pkt)

#         print("\tSending outbound udp packet...")
#         send_packet(self, 0, vxlan_pkt)
#         print("\tVerifying packet...")
#         verify_packet(self, vxlan_exp_pkt, 0)
#         print("\tVerifying flow created...")
#         verify_flow(self.eni_mac, self.vnet & 0xffff, inner_pkt)
#         print(f"{self.__class__.__name__} trafficUdpTest OK\n")

#     def runTest(self):
#         print("Configuring Active Instance...")
#         self.configureVnet(self.client, self.add_teardown_obj)
        
#         if self.client_stby:
#             print("Configuring Standby Instance...")
#             self.stby_teardown_stack = []
#             def stby_collector(func, *args):
#                 self.stby_teardown_stack.insert(0, (func, args))
#             self.configureVnet(self.client_stby, stby_collector)
            
#         self.trafficUdpTest()

#     def tearDown(self):
#         if self.client_stby:
#             print("Cleaning up Standby Client...")
#             for obj_func, obj_args in self.stby_teardown_stack:
#                 if isinstance(obj_args, (list, tuple)):
#                     obj_func(*obj_args)
#                 else:
#                     obj_func(obj_args)
#             try:
#                 self.transport_stby.close()
#             except:
#                 pass
#         super(SaiThriftHaSanityTest, self).tearDown()
