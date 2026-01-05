"""PMC (PTP Management Client) protocol dataclasses for parsing PTP management messages.

This module defines dataclasses that correspond to PTP management TLV (Type-Length-Value) types.
Each dataclass uses the @regex_from_tlv decorator to automatically generate
a regex pattern for parsing PMC output.
"""

import dataclasses
import re
import typing
from dataclasses import dataclass
from types import UnionType
from typing import List, TypeVar

# ruff: noqa: N815 -- attribute naming is dictated by the PMC standard, silence such warnings


def multiline_regex_from_keys(keys: List[str]) -> str:
    """Generate a multiline regex pattern from dataclass field names."""
    separator_re = r"\s*\n\s*"
    lines = [
        # Python and RegEx groups do not allow `.` in their names
        # Thus, define names in Python with `__` instead of `.` and
        # convert back only for matching the key we get from PMC
        rf"{k.replace('__', '.')}\s+(?P<{k}>.*?)"
        for k in keys
    ]

    return separator_re.join(["", *lines]) + r"\s*(\n|$)"


T = TypeVar("T")


def regex_from_tlv(cls: T) -> T:
    """Decorator that adds a regex attribute to a TLV dataclass.

    The dataclass must have a `tlv_type` class attribute.

    Args:
        cls: The dataclass to decorate.

    Raises:
        TypeError: If cls is not a dataclass.
        KeyError: If cls has no tlv_type attribute.

    Returns:
        The decorated class with a regex attribute.

    """
    if not hasattr(cls, "__name__"):
        raise TypeError(f"{type(cls)} is not a class")

    if not dataclasses.is_dataclass(cls):
        raise TypeError(f"{cls.__name__} is not a dataclass")  # type: ignore

    if not hasattr(cls, "tlv_type"):
        raise KeyError(f"{cls.__name__} has no `tlv_type` attribute")  # type: ignore

    tlv_type: str = cls.tlv_type  # type: ignore

    fields = dataclasses.fields(cls)
    field_names = [f.name for f in fields]

    cls.regex = re.compile(tlv_type + multiline_regex_from_keys(field_names))  # type: ignore
    return cls


def regex_from_tlv_union(union: UnionType) -> str:
    """Combine regex patterns from a union of TLV types."""
    regexes: list[re.Pattern[str]] = []

    types = typing.get_args(union)
    for typ in types:
        if not hasattr(typ, "regex"):
            raise KeyError(f"Type {typ} does not have a regex attribute")
        regexes.append(typ.regex)

    combined_regex = "|".join(f"(?:{regex.pattern})" for regex in regexes)
    combined_regex = re.sub(r"\?P<[^>]+>", "?:", combined_regex)
    return combined_regex


@dataclass
class PortIdentity:
    """PTP port identity consisting of clock ID and port number.

    Attributes:
        clock_id: The clock identity string (e.g., '000000.fffe.000000').
        port_number: The port number.

    """

    regex = re.compile(r"(?P<clock_id>[\da-f\.]+)-(?P<port_number>\d+)")
    clock_id: str
    port_number: int


@regex_from_tlv
@dataclass
class ClockDescription:
    """PTP clock description TLV."""

    tlv_type = "CLOCK_DESCRIPTION"
    clockType: int
    physicalLayerProtocol: str
    physicalAddress: str
    protocolAddress: str  # really Tuple[int, str], but for now let's keep parsing easy
    manufacturerId: str
    productDescription: str
    revisionData: str
    userDescription: str
    profileId: str


@regex_from_tlv
@dataclass
class UserDescription:
    """PTP user description TLV."""

    tlv_type = "USER_DESCRIPTION"
    userDescription: str


@regex_from_tlv
@dataclass
class DefaultDataSet:
    """PTP default data set TLV."""

    tlv_type = "DEFAULT_DATA_SET"
    twoStepFlag: int
    slaveOnly: int
    numberPorts: int
    priority1: int
    clockClass: int
    clockAccuracy: int
    offsetScaledLogVariance: int
    priority2: int
    clockIdentity: str
    domainNumber: int


@regex_from_tlv
@dataclass
class CurrentDataSet:
    """PTP current data set TLV."""

    tlv_type = "CURRENT_DATA_SET"
    stepsRemoved: int
    offsetFromMaster: float
    meanPathDelay: float


@regex_from_tlv
@dataclass
class ParentDataSet:
    """PTP parent data set TLV."""

    tlv_type = "PARENT_DATA_SET"
    parentPortIdentity: PortIdentity
    parentStats: int
    observedParentOffsetScaledLogVariance: int
    observedParentClockPhaseChangeRate: int
    grandmasterPriority1: int
    gm__ClockClass: int
    gm__ClockAccuracy: int
    gm__OffsetScaledLogVariance: int
    grandmasterPriority2: int
    grandmasterIdentity: str


@regex_from_tlv
@dataclass
class TimePropertiesDataSet:
    """PTP time properties data set TLV."""

    tlv_type = "TIME_PROPERTIES_DATA_SET"
    currentUtcOffset: int
    leap61: int
    leap59: int
    currentUtcOffsetValid: int
    ptpTimescale: int
    timeTraceable: int
    frequencyTraceable: int
    timeSource: int


@regex_from_tlv
@dataclass
class Priority1:
    """PTP priority1 TLV."""

    tlv_type = "PRIORITY1"
    priority1: int


@regex_from_tlv
@dataclass
class Priority2:
    """PTP priority2 TLV."""

    tlv_type = "PRIORITY2"
    priority2: int


@regex_from_tlv
@dataclass
class Domain:
    """PTP domain TLV."""

    tlv_type = "DOMAIN"
    domainNumber: int


@regex_from_tlv
@dataclass
class SlaveOnly:
    """PTP slave-only TLV."""

    tlv_type = "SLAVE_ONLY"
    slaveOnly: int


@regex_from_tlv
@dataclass
class ClockAccuracy:
    """PTP clock accuracy TLV."""

    tlv_type = "CLOCK_ACCURACY"
    clockAccuracy: int


@regex_from_tlv
@dataclass
class TraceabilityProperties:
    """PTP traceability properties TLV."""

    tlv_type = "TRACEABILITY_PROPERTIES"
    timeTraceable: int
    frequencyTraceable: int


@regex_from_tlv
@dataclass
class TimescaleProperties:
    """PTP timescale properties TLV."""

    tlv_type = "TIMESCALE_PROPERTIES"
    ptpTimescale: int


@regex_from_tlv
@dataclass
class AlternateTimeOffsetEnable:
    """PTP alternate time offset enable TLV."""

    tlv_type = "ALTERNATE_TIME_OFFSET_ENABLE"
    keyField: int
    enable: int


@regex_from_tlv
@dataclass
class AlternateTimeOffsetName:
    """PTP alternate time offset name TLV."""

    tlv_type = "ALTERNATE_TIME_OFFSET_NAME"
    keyField: int
    displayName: str


@regex_from_tlv
@dataclass
class AlternateTimeOffsetProperties:
    """PTP alternate time offset properties TLV."""

    tlv_type = "ALTERNATE_TIME_OFFSET_PROPERTIES"
    keyField: int
    currentOffset: int
    jumpSeconds: int
    timeOfNextJump: int


@regex_from_tlv
@dataclass
class MasterOnly:
    """PTP master-only TLV."""

    tlv_type = "MASTER_ONLY"
    masterOnly: int


@regex_from_tlv
@dataclass
class TimeStatusNp:
    """LinuxPTP time status TLV."""

    tlv_type = "TIME_STATUS_NP"
    master_offset: int
    ingress_time: int
    cumulativeScaledRateOffset: float
    scaledLastGmPhaseChange: int
    gmTimeBaseIndicator: int
    lastGmPhaseChange: float
    gmPresent: str
    gmIdentity: str


@regex_from_tlv
@dataclass
class GrandmasterSettingsNp:
    """LinuxPTP grandmaster settings TLV."""

    tlv_type = "GRANDMASTER_SETTINGS_NP"
    clockClass: int
    clockAccuracy: int
    offsetScaledLogVariance: int
    currentUtcOffset: int
    leap61: int
    leap59: int
    currentUtcOffsetValid: int
    ptpTimescale: int
    timeTraceable: int
    frequencyTraceable: int
    timeSource: int


@regex_from_tlv
@dataclass
class SubscribeEventsNp:
    """LinuxPTP subscribe events TLV."""

    tlv_type = "SUBSCRIBE_EVENTS_NP"
    duration: int
    NOTIFY_PORT_STATE: str
    NOTIFY_TIME_SYNC: str
    NOTIFY_PARENT_DATA_SET: str
    NOTIFY_CMLDS: str


@regex_from_tlv
@dataclass
class SynchronizationUncertainNp:
    """LinuxPTP synchronization uncertain TLV."""

    tlv_type = "SYNCHRONIZATION_UNCERTAIN_NP"
    uncertain: int


@regex_from_tlv
@dataclass
class PortDataSet:
    """PTP port data set TLV."""

    tlv_type = "PORT_DATA_SET"
    portIdentity: PortIdentity
    portState: str
    logMinDelayReqInterval: int
    peerMeanPathDelay: int
    logAnnounceInterval: int
    announceReceiptTimeout: int
    logSyncInterval: int
    delayMechanism: int
    logMinPdelayReqInterval: int
    versionNumber: int


@regex_from_tlv
@dataclass
class PortDataSetNp:
    """LinuxPTP port data set TLV."""

    tlv_type = "PORT_DATA_SET_NP"
    neighborPropDelayThresh: int
    asCapable: int


@regex_from_tlv
@dataclass
class PortPropertiesNp:
    """LinuxPTP port properties TLV."""

    tlv_type = "PORT_PROPERTIES_NP"
    portIdentity: PortIdentity
    portState: str
    timestamping: str
    interface: str


@regex_from_tlv
@dataclass
class PortStatsNp:
    """LinuxPTP port statistics TLV."""

    tlv_type = "PORT_STATS_NP"
    portIdentity: PortIdentity
    rx_Sync: int
    rx_Delay_Req: int
    rx_Pdelay_Req: int
    rx_Pdelay_Resp: int
    rx_Follow_Up: int
    rx_Delay_Resp: int
    rx_Pdelay_Resp_Follow_Up: int
    rx_Announce: int
    rx_Signaling: int
    rx_Management: int
    tx_Sync: int
    tx_Delay_Req: int
    tx_Pdelay_Req: int
    tx_Pdelay_Resp: int
    tx_Follow_Up: int
    tx_Delay_Resp: int
    tx_Pdelay_Resp_Follow_Up: int
    tx_Announce: int
    tx_Signaling: int
    tx_Management: int


@regex_from_tlv
@dataclass
class PortServiceStatsNp:
    """LinuxPTP port service statistics TLV."""

    tlv_type = "PORT_SERVICE_STATS_NP"
    portIdentity: PortIdentity
    announce_timeout: int
    sync_timeout: int
    delay_timeout: int
    unicast_service_timeout: int
    unicast_request_timeout: int
    master_announce_timeout: int
    master_sync_timeout: int
    qualification_timeout: int
    sync_mismatch: int
    followup_mismatch: int


@regex_from_tlv
@dataclass
class PortHwclockNp:
    """LinuxPTP port hardware clock TLV."""

    tlv_type = "PORT_HWCLOCK_NP"
    portIdentity: PortIdentity
    phcIndex: int
    flags: int


@regex_from_tlv
@dataclass
class PowerProfileSettingsNp:
    """LinuxPTP power profile settings TLV."""

    tlv_type = "POWER_PROFILE_SETTINGS_NP"
    version: int
    grandmasterID: int
    grandmasterTimeInaccuracy: int
    networkTimeInaccuracy: int
    totalTimeInaccuracy: int


@regex_from_tlv
@dataclass
class CmldsInfoNp:
    """LinuxPTP CMLDS info TLV."""

    tlv_type = "CMLDS_INFO_NP"
    meanLinkDelay: int
    scaledNeighborRateRatio: int
    as_capable: int


@regex_from_tlv
@dataclass
class LogAnnounceInterval:
    """PTP log announce interval TLV."""

    tlv_type = "LOG_ANNOUNCE_INTERVAL"
    logAnnounceInterval: int


@regex_from_tlv
@dataclass
class AnnounceReceiptTimeout:
    """PTP announce receipt timeout TLV."""

    tlv_type = "ANNOUNCE_RECEIPT_TIMEOUT"
    announceReceiptTimeout: int


@regex_from_tlv
@dataclass
class LogSyncInterval:
    """PTP log sync interval TLV."""

    tlv_type = "LOG_SYNC_INTERVAL"
    logSyncInterval: int


@regex_from_tlv
@dataclass
class VersionNumber:
    """PTP version number TLV."""

    tlv_type = "VERSION_NUMBER"
    versionNumber: int


@regex_from_tlv
@dataclass
class DelayMechanism:
    """PTP delay mechanism TLV."""

    tlv_type = "DELAY_MECHANISM"
    delayMechanism: int


@regex_from_tlv
@dataclass
class LogMinPdelayReqInterval:
    """PTP log min pdelay request interval TLV."""

    tlv_type = "LOG_MIN_PDELAY_REQ_INTERVAL"
    logMinPdelayReqInterval: int


@dataclass
class Empty:
    """Empty TLV placeholder."""

    tlv_type = "EMPTY"
    regex = re.compile(r"empty-tlv\s*(\n|$)")


@dataclass
class NullManagement:
    """Null management TLV."""

    tlv_type = "NULL_MANAGEMENT"
    regex = re.compile(r"\s*(\n|$)")


ManagementTlvPayload = (
    ClockDescription
    | UserDescription
    | DefaultDataSet
    | CurrentDataSet
    | ParentDataSet
    | TimePropertiesDataSet
    | Priority1
    | Priority2
    | Domain
    | SlaveOnly
    | ClockAccuracy
    | TraceabilityProperties
    | TimescaleProperties
    | AlternateTimeOffsetEnable
    | AlternateTimeOffsetName
    | AlternateTimeOffsetProperties
    | MasterOnly
    | TimeStatusNp
    | GrandmasterSettingsNp
    | SubscribeEventsNp
    | SynchronizationUncertainNp
    | PortDataSet
    | PortDataSetNp
    | PortPropertiesNp
    | PortStatsNp
    | PortServiceStatsNp
    | PortHwclockNp
    | PowerProfileSettingsNp
    | CmldsInfoNp
    | LogAnnounceInterval
    | AnnounceReceiptTimeout
    | LogSyncInterval
    | VersionNumber
    | DelayMechanism
    | LogMinPdelayReqInterval
    | NullManagement
    | Empty
)


@dataclass
class ManagementTlv:
    """PMC management TLV wrapper."""

    regex = re.compile(
        r"MANAGEMENT\s+(?P<payload>" + regex_from_tlv_union(ManagementTlvPayload) + ")"
    )
    payload: ManagementTlvPayload


@dataclass
class ManagementErrorStatusTlv:
    """PMC management error status TLV."""

    regex = re.compile(r"MANAGEMENT_ERROR_STATUS\s*(\n|$)")


@dataclass
class UnknownTlv:
    """Unknown TLV placeholder."""

    regex = re.compile(r"unknown-tlv\s*(\n|$)")


ResponseTlvPayload = ManagementTlv | ManagementErrorStatusTlv | UnknownTlv


@dataclass
class Response:
    """A parsed PMC response message."""

    regex = re.compile(
        r"\s+(?P<source_port>[\da-f\.-]+)\s+seq\s+(?P<seq>\d+)\s+(?P<action>\w+)\s*?(?P<tlv>"
        + regex_from_tlv_union(ResponseTlvPayload)
        + r")"
    )

    source_port: PortIdentity
    seq: int
    action: str
    tlv: ResponseTlvPayload


@dataclass
class Request:
    """A parsed PMC request message."""

    regex = re.compile(r"\s*sending: (?P<action>\w+)\s+(?P<tlv_type>\w+)\s*\n")
    action: str
    tlv_type: str


Message = Request | Response
