import json
import time
import grpc
import google.protobuf.json_format as json_format
from concurrent import futures
from p4.v1 import p4runtime_pb2
from p4.v1 import p4runtime_pb2_grpc
from py_model.libs.__utils import *
from py_model.libs.__id_map import *
from py_model.control_plane.control_plane import *

slices = 3
table_entries = {}

def pretty_print_proto(proto_msg, title="Protobuf Message"):
    json_str = json_format.MessageToJson(proto_msg, indent=2, sort_keys=True)
    py_log(None, f"\n==== {title} ====")
    py_log(None, json_str)
    py_log(None, "=" * 60 + "\n")
    return json_str

def populate_tables_actions_ids(json_data: str):
    data = json.loads(json_data)
    p4info = data.get("config", {}).get("p4info", {})

    def shorten_name(full_name: str) -> str:
        parts = full_name.split(".")
        if len(parts) >= slices:
            return ".".join(parts[-slices:])
        return full_name

    def extract_items(items):
        mapping = {}
        for item in items:
            preamble = item.get("preamble", {})
            obj_id = preamble.get("id")
            name = preamble.get("name", "")
            if obj_id is not None and name:
                mapping[obj_id] = shorten_name(name)
        return mapping

    table_ids.update(extract_items(p4info.get("tables", [])))
    action_ids.update(extract_items(p4info.get("actions", [])))
    counter_ids.update(extract_items(p4info.get("counters", [])))
    direct_counter_ids.update(extract_items(p4info.get("directCounters", [])))

class P4RuntimeServicer(p4runtime_pb2_grpc.P4RuntimeServicer):
    def __init__(self):
        self.p4_pipeline_config = None
        self.master_election_id = None

    # Handles pipeline configuration setup
    def SetForwardingPipelineConfig(self, request, context):
        # pretty_print_proto(request, "SetForwardingPipelineConfig Request")

        if request.action not in (
            p4runtime_pb2.SetForwardingPipelineConfigRequest.VERIFY,
            p4runtime_pb2.SetForwardingPipelineConfigRequest.VERIFY_AND_COMMIT,
            p4runtime_pb2.SetForwardingPipelineConfigRequest.COMMIT
        ):
            py_log("error", f"[P4Runtime] Unsupported action: {request.action}")
            context.abort(
                grpc.StatusCode.INVALID_ARGUMENT,
                f"Unsupported action: {request.action}"
            )

        json_str = json_format.MessageToJson(request, indent=2, sort_keys=True)
        populate_tables_actions_ids(json_str)

        self.p4_pipeline_config = request.config
        return p4runtime_pb2.SetForwardingPipelineConfigResponse()

    def GetForwardingPipelineConfig(self, request, context):
        # pretty_print_proto(request, "GetForwardingPipelineConfig Request")
        resp = p4runtime_pb2.GetForwardingPipelineConfigResponse()

        if not self.p4_pipeline_config:
            py_log("error", f"[P4Runtime] Pipeline config not set")
            context.abort(grpc.StatusCode.NOT_FOUND, "Pipeline config not set")

        resp.config.CopyFrom(self.p4_pipeline_config)
        return resp

    def Write(self, request, context):
        # pretty_print_proto(request, "Write Request")
        for idx, update in enumerate(request.updates):
            try:
                # Convert Protobuf message to JSON
                update_dict = json.loads(json_format.MessageToJson(update))
                obj_type = update_dict.get("type", {})

                table_entry = update.entity.table_entry
                table_id = table_entry.table_id

                ins_req, hash = parse_write_request(update_dict, obj_type)
                if ins_req is None:
                    break

                ret = insert_entry(ins_req, obj_type, hash)
  
            except Exception as e:
                py_log("error", f"[P4Runtime] Error processing update [{idx}]: {e}")
                context.abort(
                    grpc.StatusCode.UNKNOWN,
                    f"Error processing update [{idx}]: {e}"
                )

            if ret == RETURN_FAILURE:
                py_log("error", f"[P4Runtime] Write Request [{idx}] failed, skipping write table: {table_id}")
                context.abort(
                    grpc.StatusCode.ABORTED,
                    f"Error processing update [{idx}]: {e}"
                )
            elif ret == ALREADY_EXISTS:
                py_log("error", f"[P4Runtime] Entry already exists, skipping update [{idx}]")
                context.abort(
                    grpc.StatusCode.ALREADY_EXISTS,
                    f"Entry [{idx}] already exists"
                )

        return p4runtime_pb2.WriteResponse()

    def Read(self, request, context):
        # pretty_print_proto(request, "Read Request")
        if not self.p4_pipeline_config:
            py_log("error", f"[P4Runtime] Pipeline config not set")
            context.abort(grpc.StatusCode.FAILED_PRECONDITION, "Pipeline config not set")

        for idx, entity in enumerate(request.entities):
            try:
                entity_dict = json.loads(json_format.MessageToJson(entity))

                table_id = entity.table_entry.table_id
                hash = parse_read_request(entity_dict)

                ret = read_entry(hash, table_id)
                if ret == RETURN_FAILURE:
                    py_log("error", f"[P4Runtime] Entry not found, skipping read table: {table_id}")
                else:
                    yield p4runtime_pb2.ReadResponse(
                        entities=[
                            p4runtime_pb2.Entity(
                                table_entry=entity.table_entry
                            )
                        ]
                    )
                    break
            except Exception as e:
                py_log("error", f"[P4Runtime] Error processing update [{idx}]: {e}")
                context.abort(
                    grpc.StatusCode.INVALID_ARGUMENT,
                    f"Error processing update [{idx}]: {e}"
                )

    # Handles bi-directional communication (StreamChannel)
    def StreamChannel(self, request_iterator, context):
        for request in request_iterator:
            # pretty_print_proto(request, "StreamChannel Message")

            if request.HasField("arbitration"):
                election_id = request.arbitration.election_id

                if (not self.master_election_id) or (
                    (election_id.high, election_id.low) > (self.master_election_id.high, self.master_election_id.low)
                ):
                    self.master_election_id = election_id

                response = p4runtime_pb2.StreamMessageResponse()
                response.arbitration.election_id.low = request.arbitration.election_id.low
                response.arbitration.election_id.high = 0
                response.arbitration.status.code = 0  # OK
                yield response

            elif request.HasField("packet"):
                packet_out = p4runtime_pb2.StreamMessageResponse()
                packet_out.packet.payload = request.packet.payload
                yield packet_out

        return iter([])


# Start the gRPC server
def serve():
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    p4runtime_pb2_grpc.add_P4RuntimeServicer_to_server(P4RuntimeServicer(), server)
    server.add_insecure_port("[::]:9559")
    server.start()
    py_log(None, "Server listening on 0.0.0.0:9559\n")

    try:
        while True:
            time.sleep(86400)  # Keep the server alive
    except KeyboardInterrupt:
        py_log(None, "Shutting down gRPC server.\n")
        server.stop(0)
