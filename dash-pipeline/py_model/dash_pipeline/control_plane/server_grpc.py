# import json
# import google.protobuf.json_format as json_format
# from p4.v1 import p4runtime_pb2
# from p4.v1 import p4runtime_pb2_grpc
# import control_plane.control_plane as cp

# # Define the gRPC service for P4Runtime
# class P4RuntimeServicer(p4runtime_pb2_grpc.P4RuntimeServicer):
#     def __init__(self):
#         self.p4_pipeline_config = None  # Placeholder for pipeline config

#     # Handles pipeline configuration setup
#     def SetForwardingPipelineConfig(self, request, context):
#         print("Received SetForwardingPipelineConfig request")
#         self.p4_pipeline_config = request.config
#         return p4runtime_pb2.SetForwardingPipelineConfigResponse()

#     # Handles write requests (e.g., inserting table entries)
#     def Write(self, request, context):
#         # print("[Write] Full Request:\n", request)

#         for idx, update in enumerate(request.updates):
#             try:
#                 # Convert Protobuf message to JSON
#                 update_dict = json.loads(json_format.MessageToJson(update))
#                 # Convert JSON object to insert request format
#                 insert_request = cp.parse_insert_request(update_dict)
#                 json_obj_type = update_dict.get("type", {})
#                 # Insert entry using the control plane's API
#                 cp.table_insert_api(insert_request, json_obj_type)
#             except Exception as e:
#                 print(f"[Write] Error processing update [{idx}]: {e}")

#         # Send back an empty WriteResponse
#         response = p4runtime_pb2.WriteResponse()
#         # print("\n[Write] Sending Response:\n", response)
#         # print("=" * 80)
#         return response

#     # Handles read requests (not fully implemented)
#     def Read(self, request, context):
#         print("Received Read request")
#         for entity in request.entities:
#             print(f"Reading table {entity.table_entry.tableId}")
#         return p4runtime_pb2.ReadResponse()

#     # Handles bi-directional communication (StreamChannel)
#     def StreamChannel(self, request_iterator, context):
#         print("Opened StreamChannel")
#         for request in request_iterator:
#             print(f"Received message on StreamChannel: {request}")
#             if request.HasField("arbitration"):
#                 print(f"Received arbitration request from controller")
#                 print(f"Device ID: {request.arbitration.device_id}")
#                 print(f"Election ID: {request.arbitration.election_id.low}")
                
#                 # Build arbitration response
#                 response = p4runtime_pb2.StreamMessageResponse()
#                 response.arbitration.election_id.low = request.arbitration.election_id.low
#                 response.arbitration.election_id.high = 0
#                 response.arbitration.status.code = 0  # OK
#                 print(f"Sending arbitration response with election_id={response.arbitration.election_id.low}")
#                 yield response  # Respond to the controller
#         return iter([])

# # # Start the gRPC server and sniffer
# # def serve():
# #     # Initialize gRPC server with a thread pool
# #     server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))

# #     # Register the P4Runtime service
# #     p4runtime_pb2_grpc.add_P4RuntimeServicer_to_server(P4RuntimeServicer(), server)

# #     # Listen on port 9559 (you can change this as needed)
# #     server.add_insecure_port("[::]:9559")
# #     server.start()
# #     print("P4Runtime gRPC server started on port 9559")

# #     # Run the packet sniffer in a separate background thread
# #     sniff_thread = threading.Thread(target=sniff_and_process, daemon=True)
# #     sniff_thread.start()

# #     try:
# #         while True:
# #             time.sleep(86400)  # Keep the server alive
# #     except KeyboardInterrupt:
# #         print("Shutting down gRPC server.")
# #         server.stop(0)

# # # Entry point
# # if __name__ == "__main__":
# #     serve()
