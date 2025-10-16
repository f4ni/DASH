# import grpc
# import p4runtime_pb2
# import p4runtime_pb2_grpc

# # Connect to gRPC server
# channel = grpc.insecure_channel("localhost:50051")
# stub = p4runtime_pb2_grpc.P4RuntimeStub(channel)

# # Send pipeline configuration
# request = p4runtime_pb2.SetForwardingPipelineConfigRequest(
#     config=p4runtime_pb2.ForwardingPipelineConfig()
# )
# response = stub.SetForwardingPipelineConfig(request)

# print("Pipeline Config Set Response:", response)
