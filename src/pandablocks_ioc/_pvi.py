from dataclasses import dataclass
from enum import Enum
from os import remove
from pathlib import Path
from typing import Callable, Dict, List, Optional

from epicsdbbuilder import RecordName
from pvi._format.dls import DLSFormatter
from pvi.device import (
    LED,
    ButtonPanel,
    ComboBox,
    Component,
    Device,
    DeviceRef,
    Grid,
    Group,
    Row,
    SignalR,
    SignalRW,
    SignalX,
    TextFormat,
    TextRead,
    TextWrite,
    Tree,
)
from softioc import builder
from softioc.pythonSoftIoc import RecordWrapper

from ._types import OUT_RECORD_FUNCTIONS, EpicsName, epics_to_pvi_name


class PviGroup(Enum):
    """Categories to group record display widgets"""

    NONE = None  # This marks a top-level group
    INPUTS = "Inputs"
    PARAMETERS = "Parameters"
    READBACKS = "Readbacks"
    OUTPUTS = "Outputs"
    CAPTURE = "Capture"
    HDF = "HDF"
    TABLE = "Table"  # TODO: May not need this anymore


@dataclass
class PviInfo:
    """A container for PVI related information for a record

    `group`: The group that this info is a part of
    `component`: The PVI Component used for rendering"""

    group: PviGroup
    component: Component


def add_pvi_info_to_record(
    record: RecordWrapper,
    record_name: EpicsName,
    access: str,
):
    block, field = record_name.split(":", maxsplit=1)
    block_name_suffixed = f"pvi.{field.lower().replace(':', '_')}.{access}"
    record.add_info(
        "Q:group",
        {
            RecordName(f"{block}:PVI"): {
                block_name_suffixed: {
                    "+channel": "NAME",
                    "+type": "plain",
                    "+trigger": block_name_suffixed,
                }
            }
        },
    )


def add_data_capture_pvi_info(
    group: PviGroup,
    data_capture_record_name: EpicsName,
    data_capture_pvi_record: RecordWrapper,
):
    component = SignalRW(
        name=epics_to_pvi_name(data_capture_record_name),
        pv=data_capture_record_name,
        widget=ButtonPanel(actions={"Start": "1", "Stop": "0"}),
        read_widget=LED(),
    )
    add_pvi_info_to_record(data_capture_pvi_record, data_capture_record_name, "rw")
    Pvi.add_pvi_info(
        record_name=data_capture_record_name, group=group, component=component
    )


def add_pcap_arm_pvi_info(group: PviGroup, pcap_arm_pvi_record: RecordWrapper):
    pcap_arm_record_name = EpicsName("PCAP:ARM")
    component = SignalRW(
        name=epics_to_pvi_name(pcap_arm_record_name),
        pv=pcap_arm_record_name,
        widget=ButtonPanel(actions={"Arm": "1", "Disarm": "0"}),
        read_widget=LED(),
    )
    add_pvi_info_to_record(pcap_arm_pvi_record, pcap_arm_record_name, "rw")
    Pvi.add_pvi_info(record_name=pcap_arm_record_name, group=group, component=component)


def add_automatic_pvi_info(
    group: PviGroup,
    record: RecordWrapper,
    record_name: EpicsName,
    record_creation_func: Callable,
) -> None:
    """Create the most common forms of the `PviInfo` structure.
    Generates generic components from"""
    component: Component
    writeable: bool = record_creation_func in OUT_RECORD_FUNCTIONS
    useComboBox: bool = record_creation_func == builder.mbbOut

    pvi_name = epics_to_pvi_name(record_name)

    if record_creation_func == builder.Action:
        if record_name == "PCAP:ARM":
            component = SignalRW(
                name=pvi_name,
                pv=record_name,
                widget=ButtonPanel(actions={"Arm": "1", "Disarm": "0"}),
                read_widget=LED(),
            )
            access = "rw"

        else:
            component = SignalX(name=pvi_name, pv=record_name, value="")
            access = "x"
    elif writeable:
        if useComboBox:
            widget = ComboBox()
        else:
            if record_creation_func in (
                builder.longStringOut,
                builder.stringOut,
            ):
                widget = TextWrite(format=TextFormat.string)
            else:
                widget = TextWrite(format=None)

        component = SignalRW(name=pvi_name, pv=record_name, widget=widget)
        access = "rw"
    else:
        if record_creation_func in (
            builder.longStringIn,
            builder.stringIn,
        ):
            widget = TextRead(format=TextFormat.string)
        else:
            widget = TextRead(format=None)

        component = SignalR(name=pvi_name, pv=record_name, widget=widget)
        access = "r"

    add_pvi_info_to_record(record, record_name, access)
    Pvi.add_pvi_info(record_name=record_name, group=group, component=component)


_positions_table_group = Group(
    name="PositionsTable", layout=Grid(labelled=True), children=[]
)
_positions_table_headers = ["VALUE", "UNITS", "SCALE", "OFFSET", "DATASET", "CAPTURE"]


# TODO: Replicate this for the BITS table
def add_positions_table_row(
    record_name: EpicsName,
    value_record_name: EpicsName,
    units_record_name: EpicsName,
    scale_record_name: EpicsName,
    offset_record_name: EpicsName,
    dataset_record_name: EpicsName,
    capture_record_name: EpicsName,
) -> None:
    """Add a Row to the Positions table"""
    # TODO: Use the Components defined in _positions_columns_defs to
    # create the children, which will make it more obvious which
    # component is for which column
    children = [
        SignalR(
            name=epics_to_pvi_name(value_record_name),
            label=value_record_name,
            pv=value_record_name,
            widget=TextRead(),
        ),
        SignalRW(
            name=epics_to_pvi_name(units_record_name),
            label=units_record_name,
            pv=units_record_name,
            widget=TextWrite(),
        ),
        SignalRW(
            name=epics_to_pvi_name(scale_record_name),
            label=scale_record_name,
            pv=scale_record_name,
            widget=TextWrite(),
        ),
        SignalRW(
            name=epics_to_pvi_name(offset_record_name),
            label=offset_record_name,
            pv=offset_record_name,
            widget=TextWrite(),
        ),
        SignalRW(
            name=epics_to_pvi_name(dataset_record_name),
            label=dataset_record_name,
            pv=dataset_record_name,
            widget=TextWrite(),
        ),
        SignalRW(
            name=epics_to_pvi_name(capture_record_name),
            label=capture_record_name,
            pv=capture_record_name,
            widget=ComboBox(),
        ),
    ]

    row = Row()
    if len(_positions_table_group.children) == 0:
        row.header = _positions_table_headers

    row_group = Group(
        name=epics_to_pvi_name(record_name),
        label=record_name,
        layout=row,
        children=children,
    )

    _positions_table_group.children.append(row_group)


class Pvi:
    """TODO: Docs"""

    _screens_dir: Optional[Path] = None
    _clear_bobfiles: bool = False

    # We may want general device refs, e.g every CAPTURE group having a reference
    # to the positions table
    _general_device_refs = {
        "CAPTURE": DeviceRef(
            name="AllPostionCaptureParameters",
            pv="CAPTURE",
            ui="PandA_PositionsTable",
        )
    }

    pvi_info_dict: Dict[str, Dict[PviGroup, List[Component]]] = {}

    @staticmethod
    def configure_pvi(screens_dir: Optional[str], clear_bobfiles: bool):
        if screens_dir:
            Pvi._screens_dir = Path(screens_dir)
            assert Pvi._screens_dir.is_dir(), "Screens directory must exist"

        Pvi._clear_bobfiles = clear_bobfiles

    @staticmethod
    def add_pvi_info(record_name: EpicsName, group: PviGroup, component: Component):
        """Add PVI Info to the global collection"""

        record_base, _ = record_name.split(":", 1)

        if record_base in Pvi.pvi_info_dict:
            if group in Pvi.pvi_info_dict[record_base]:
                Pvi.pvi_info_dict[record_base][group].append(component)
            else:
                Pvi.pvi_info_dict[record_base][group] = [component]
        else:
            Pvi.pvi_info_dict[record_base] = {group: [component]}

    @staticmethod
    def add_general_device_refs_to_groups(device: Device):
        for group in device.children:
            if group.name in Pvi._general_device_refs:
                group.children.append(Pvi._general_device_refs[group.name])

    @staticmethod
    def create_pvi_records(record_prefix: str):
        """Create the :PVI records, one for each block and one at the top level"""

        devices: List[Device] = []
        pvi_records: List[str] = []
        for block_name, v in Pvi.pvi_info_dict.items():
            children: Tree = []

            # Item in the NONE group should be rendered outside of any Group box
            if PviGroup.NONE in v:
                children.extend(v.pop(PviGroup.NONE))
            for group, components in v.items():
                children.append(
                    Group(name=group.name, layout=Grid(), children=components)
                )

            device = Device(label=block_name, children=children)
            devices.append(device)

            # Add PVI structure. Unfortunately we need something in the database
            # that holds the PVI PV, and the QSRV records we have made so far aren't
            # in the database, so have to make an extra record here just to hold the
            # PVI PV name
            pvi_record_name = block_name + ":PVI"
            block_pvi = builder.longStringIn(
                pvi_record_name + "_PV",
                initial_value=RecordName(pvi_record_name),
            )
            block_name_suffixed = f"pvi.{block_name.lower()}.d"
            block_pvi.add_info(
                "Q:group",
                {
                    RecordName("PVI"): {
                        block_name_suffixed: {
                            "+channel": "VAL",
                            "+type": "plain",
                            "+trigger": block_name_suffixed,
                        }
                    }
                },
            )

            pvi_records.append(pvi_record_name)

        # TODO: Properly add this to list of screens, add a PV, maybe roll into
        # the "PLACEHOLDER" Device?
        # Add Tables to a new top level screen
        top_device = Device(label="PandA", children=[_positions_table_group])
        devices.append(top_device)

        # Create top level Device, with references to all child Devices
        index_device_refs = []
        for pvi_record in pvi_records:
            record_with_no_suffix = EpicsName(pvi_record.replace(":PVI", ""))
            name = epics_to_pvi_name(record_with_no_suffix)
            index_device_refs.append(
                DeviceRef(
                    name=name,
                    label=record_with_no_suffix,
                    pv=pvi_record,
                    ui=record_with_no_suffix,
                )
            )

        # # TODO: What should the label be?
        device = Device(label="index", children=index_device_refs)
        devices.append(device)

        # TODO: label widths need some tweaking - some are pretty long right now
        formatter = DLSFormatter(label_width=250)

        if Pvi._screens_dir:
            screens_dir_current_bobfiles = [
                file
                for file in Pvi._screens_dir.iterdir()
                if file.suffix == ".bob" and file.is_file()
            ]

            if screens_dir_current_bobfiles:
                if Pvi._clear_bobfiles:
                    for file in screens_dir_current_bobfiles:
                        remove(file)
                else:
                    raise FileExistsError(
                        "Screens directory is not empty, if you want to run the ioc "
                        "generating bobfiles, use --clear-bobfiles to delete the "
                        "bobfiles from the existing --screens-dir."
                    )

            for device in devices:
                bobfile_path = Pvi._screens_dir / Path(f"{device.label}.bob")

                Pvi.add_general_device_refs_to_groups(device)

                formatter.format(device, record_prefix + ":", bobfile_path)
