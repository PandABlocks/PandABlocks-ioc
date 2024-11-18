import re
from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum
from os import remove
from pathlib import Path
from typing import Literal, Optional, Union

from epicsdbbuilder import RecordName
from pvi._format.dls import DLSFormatter
from pvi.device import (
    LED,
    ButtonPanel,
    ComboBox,
    Component,
    ComponentUnion,
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
)
from softioc import builder
from softioc.pythonSoftIoc import RecordWrapper

from ._types import OUT_RECORD_FUNCTIONS, EpicsName, epics_to_pvi_name


def _extract_number_at_end_of_string(
    string: str,
) -> tuple[None, None] | tuple[str, int | None]:
    pattern = r"(\D+)(\d+)$"
    match = re.match(pattern, string)
    if match:
        return (match.group(1), int(match.group(2)))
    return string, None


def q_group_formatter(
    panda_field: str,
    access: str | None,
    channel: Literal["VAL", "NAME"],
    other_fields: dict[str, str] | None = None,
    vectorize: bool = True,
) -> dict:
    other_fields = other_fields or {}

    panda_field_lower = panda_field.lower().replace(":", "_")
    access_name = "" if access is None else f".{access}"

    # Backwards compatible `pvi.someblock1` field.
    pvi_field = f"pvi.{panda_field_lower}{access_name}"

    # New `value.someblock[1]` field.
    if vectorize:
        stripped_name, stripped_number = _extract_number_at_end_of_string(
            panda_field_lower
        )
        value_number = "" if stripped_number is None else f"[{stripped_number}]"
        value_field = f"value.{stripped_name}{value_number}{access_name}"
    else:
        value_field = f"value.{panda_field_lower}{access_name}"

    return {
        block_name_suffixed: {
            "+channel": channel,
            "+type": "plain",
            "+trigger": block_name_suffixed,
            **other_fields,
        }
        for block_name_suffixed in (pvi_field, value_field)
    }


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
    VERSIONS = "Versions"


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
    pvi_pv = RecordName(f"{block}:PVI")

    record.add_info(
        "Q:group",
        {pvi_pv: q_group_formatter(field, access, "NAME", vectorize=False)},
    )


def add_data_capture_pvi_info(
    group: PviGroup,
    data_capture_record_name: EpicsName,
    data_capture_pvi_record: RecordWrapper,
):
    component = SignalRW(
        name=epics_to_pvi_name(data_capture_record_name),
        read_pv=f"{Pvi.record_prefix}:{data_capture_record_name}",
        write_pv=f"{Pvi.record_prefix}:{data_capture_record_name}",
        write_widget=ButtonPanel(actions={"Start": "1", "Stop": "0"}),
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
        read_pv=f"{Pvi.record_prefix}:{pcap_arm_record_name}",
        write_pv=f"{Pvi.record_prefix}:{pcap_arm_record_name}",
        write_widget=ButtonPanel(actions={"Arm": "1", "Disarm": "0"}),
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
    component: ComponentUnion
    writeable: bool = record_creation_func in OUT_RECORD_FUNCTIONS
    useComboBox: bool = record_creation_func == builder.mbbOut

    pvi_name = epics_to_pvi_name(record_name)

    if record_creation_func == builder.Action:
        if record_name == "PCAP:ARM":
            component = SignalRW(
                name=pvi_name,
                write_pv=f"{Pvi.record_prefix}:{record_name}",
                write_widget=ButtonPanel(actions={"Arm": "1", "Disarm": "0"}),
                read_widget=LED(),
            )
            access = "rw"

        else:
            component = SignalX(
                name=pvi_name, write_pv=f"{Pvi.record_prefix}:{record_name}", value=""
            )
            access = "x"
    elif writeable:
        text_read_widget: Union[ComboBox, TextWrite]
        if useComboBox:
            text_read_widget = ComboBox()
        else:
            if record_creation_func in (
                builder.longStringOut,
                builder.stringOut,
            ):
                text_read_widget = TextWrite(format=TextFormat.string)
            else:
                text_read_widget = TextWrite(format=None)
        component = SignalRW(
            name=pvi_name,
            write_pv=f"{Pvi.record_prefix}:{record_name}",
            write_widget=text_read_widget,
        )
        access = "rw"
    else:
        readable_widget: Union[TextRead, LED]
        if record_creation_func in (
            builder.longStringIn,
            builder.stringIn,
        ):
            readable_widget = TextRead(format=TextFormat.string)
        elif record_creation_func == builder.boolIn:
            readable_widget = LED()
        else:
            readable_widget = TextRead(format=None)

        component = SignalR(
            name=pvi_name,
            read_pv=f"{Pvi.record_prefix}:{record_name}",
            read_widget=readable_widget,
        )
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
            read_pv=f"{Pvi.record_prefix}:{value_record_name}",
            read_widget=TextRead(),
        ),
        SignalRW(
            name=epics_to_pvi_name(units_record_name),
            label=units_record_name,
            write_pv=f"{Pvi.record_prefix}:{units_record_name}",
            write_widget=TextWrite(),
        ),
        SignalRW(
            name=epics_to_pvi_name(scale_record_name),
            label=scale_record_name,
            write_pv=f"{Pvi.record_prefix}:{scale_record_name}",
            write_widget=TextWrite(),
        ),
        SignalRW(
            name=epics_to_pvi_name(offset_record_name),
            label=offset_record_name,
            write_pv=f"{Pvi.record_prefix}:{offset_record_name}",
            write_widget=TextWrite(),
        ),
        SignalRW(
            name=epics_to_pvi_name(dataset_record_name),
            label=dataset_record_name,
            write_pv=f"{Pvi.record_prefix}:{dataset_record_name}",
            write_widget=TextWrite(),
        ),
        SignalRW(
            name=epics_to_pvi_name(capture_record_name),
            label=capture_record_name,
            write_pv=f"{Pvi.record_prefix}:{capture_record_name}",
            write_widget=ComboBox(),
        ),
    ]

    row = (
        Row(header=None)
        if _positions_table_group.children
        else Row(header=_positions_table_headers)
    )
    row_group = Group(
        name=epics_to_pvi_name(record_name),
        label=record_name,
        layout=row,
        children=children,
    )

    _positions_table_group.children.append(row_group)  # type: ignore


class Pvi:
    """TODO: Docs"""

    _screens_dir: Optional[Path] = None
    _clear_bobfiles: bool = False
    record_prefix: Optional[str] = None

    # We may want general device refs, e.g every CAPTURE group having a reference
    # to the positions table
    _general_device_refs = {
        "CAPTURE": DeviceRef(
            name="AllPostionCaptureParameters",
            pv="CAPTURE",
            ui="PandA_PositionsTable",
        )
    }

    pvi_info_dict: dict[str, dict[PviGroup, list[ComponentUnion]]] = {}

    @staticmethod
    def configure_pvi(screens_dir: Optional[str], clear_bobfiles: bool):
        if screens_dir:
            Pvi._screens_dir = Path(screens_dir)
            assert Pvi._screens_dir.is_dir(), "Screens directory must exist"

        Pvi._clear_bobfiles = clear_bobfiles

    @staticmethod
    def add_pvi_info(
        record_name: EpicsName, group: PviGroup, component: ComponentUnion
    ):
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
        for device_child in device.children:
            if device_child.name in Pvi._general_device_refs:
                if not isinstance(device_child, Group):
                    raise RuntimeError(f"Widget {device_child} should be a `Group`.")
                device_child.children = list(device_child.children) + [
                    Pvi._general_device_refs[device_child.name]
                ]

    @staticmethod
    def create_pvi_records(record_prefix: str):
        """Create the :PVI records, one for each block and one at the top level"""

        devices: list[Device] = []
        pvi_records: list[str] = []
        for block_name, v in Pvi.pvi_info_dict.items():
            children: list[ComponentUnion] = []

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
            description = builder.longStringIn(
                f"{pvi_record_name}:DESCRIPTION",
                initial_value=f"PVs making up Interface for {block_name}",
            )
            description.add_info(
                "Q:group",
                {
                    RecordName(pvi_record_name): {
                        "display.description": {"+type": "plain", "+channel": "VAL"},
                        "": {
                            "+type": "meta",
                            "+channel": "VAL",
                        },
                    }
                },
            )
            block_pvi = builder.longStringIn(
                pvi_record_name + "_PV",
                initial_value=RecordName(pvi_record_name),
            )
            block_pvi.add_info(
                "Q:group",
                {
                    RecordName("PVI"): q_group_formatter(
                        block_name,
                        "d",
                        "VAL",
                    )
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

                formatter.format(device, bobfile_path)
