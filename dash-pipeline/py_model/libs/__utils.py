
import logging
from py_model.libs.__id_map import *

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s [%(levelname)s] %(filename)s:%(lineno)d - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)

def py_log(level=None, *args, **kwargs):
    # Format message (like print does)
    msg_parts = [str(arg) for arg in args]
    if kwargs:
        msg_parts.append(str(kwargs))
    message = " ".join(msg_parts)

    if not level:
        print(message)  # Default behavior
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
        print(message)  # default

def action(func, hints=None):
    aid = next(aid_gen)
    name = func.__name__
    action_ids[aid] = name
    action_objs[name] = func, hints or {}

    return func

# target definition
TARGET = 0
TARGET_DPDK_PNA         = 0
TARGET_BMV2_V1MODEL     = 1
TARGET_PYTHON_V1MODEL   = 2

TARGET = TARGET_PYTHON_V1MODEL


STATEFUL_P4 = 0
PNA_CONNTRACK = 0
DISABLE_128BIT_ARITHMETIC = 0
