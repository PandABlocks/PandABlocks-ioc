# flake8: noqa

import os

from fixtures.mocked_panda import *
from fixtures.panda_data import *


# Autouse fixture that will set all EPICS networking env vars to use lo interface
# to avoid false failures caused by things like firewalls blocking EPICS traffic.
@pytest.fixture(scope="session", autouse=True)
def configure_epics_environment():
    os.environ["EPICS_CAS_INTF_ADDR_LIST"] = "127.0.0.1"
    os.environ["EPICS_CAS_BEACON_ADDR_LIST"] = "127.0.0.1"
    os.environ["EPICS_CA_ADDR_LIST"] = "127.0.0.1"
    os.environ["EPICS_CAS_AUTO_ADDR_LIST"] = "NO"
    os.environ["EPICS_CA_AUTO_BEACON_ADDR_LIST"] = "NO"

    os.environ["EPICS_PVAS_INTF_ADDR_LIST"] = "127.0.0.1"
    os.environ["EPICS_PVAS_BEACON_ADDR_LIST"] = "127.0.0.1"
    os.environ["EPICS_PVA_ADDR_LIST"] = "127.0.0.1"
    os.environ["EPICS_PVAS_AUTO_BEACON_ADDR_LIST"] = "NO"
    os.environ["EPICS_PVA_AUTO_ADDR_LIST"] = "NO"
