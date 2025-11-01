
import logging
from py_model.libs.__id_map import *
# from py_model.libs.__packet_in import *
# from py_model.libs.__packet_out import *
# from py_model.libs.__standard_metadata import *
# from py_model.data_plane.dash_headers import *
# from py_model.data_plane.dash_metadata import *

# target definition
TARGET_DPDK_PNA             = 0
TARGET_BMV2_V1MODEL         = 1
TARGET_PYTHON_V1MODEL       = 2

TARGET = TARGET_PYTHON_V1MODEL

STATEFUL_P4                 = 0
PNA_CONNTRACK               = 0
DISABLE_128BIT_ARITHMETIC   = 0


# iface_list = []

# # hdr = headers_t()
# # meta = metadata_t()
# standard_metadata = standard_metadata_t()
# pkt_in = packet_in()
# pkt_out = packet_out()


# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s [%(levelname)s] %(filename)s:%(lineno)d - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)

def py_log(level=None, *args, **kwargs):
    msg_parts = [str(arg) for arg in args]
    if kwargs:
        msg_parts.append(str(kwargs))
    message = " ".join(msg_parts)

    if not level:
        print(message)
        return

    level = level.lower()
    if level == "debug":
        logging.debug(message, stacklevel=2)
    elif level == "info":
        logging.info(message, stacklevel=2)
    elif level == "warning":
        logging.warning(message, stacklevel=2)
    elif level == "error":
        logging.error(message, stacklevel=2)
    elif level == "critical":
        logging.critical(message, stacklevel=2)
    else:
        print(message)

