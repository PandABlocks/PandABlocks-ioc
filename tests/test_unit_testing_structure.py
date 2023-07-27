from aioca import caget
from fixtures.mocked_panda import TEST_PREFIX


def test_conftest_loads_fixtures_from_other_files(table_fields):
    ...


async def test_fake_panda_and_ioc(mocked_panda_standard_responses):
    tmp_path, child_conn, responses = mocked_panda_standard_responses

    # PVs are broadcast
    gate_delay = await caget(f"{TEST_PREFIX}:PCAP1:GATE:DELAY")
    assert gate_delay == 1
