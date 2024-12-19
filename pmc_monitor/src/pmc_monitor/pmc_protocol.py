from dataclasses import dataclass
from typing import List


def multiline_regex_from_keys(keys: List[str]) -> str:
    separator_re = r"\s*\n\s*"
    lines = [
        # Python and RegEx groups do not allow `.` in their names
        # Thus, define names in Python with `__` instead of `.` and
        # convert back only for matching the key we get from PMC
        rf"{k.replace('__', '.')}\s+(?P<{k}>.*?)"
        for k in keys
    ]

    return separator_re.join([""] + lines) + r"\s*\n"


def add_fields_to_regex(cls):
    if not hasattr(cls, "regex"):
        raise KeyError("Class has no `regex` attribute")

    cls.regex += multiline_regex_from_keys(cls.__dataclass_fields__.keys())
    return cls


@add_fields_to_regex
@dataclass
class ClockDescription:
    regex = r"CLOCK_DESCRIPTION"
    clockType: int
    physicalLayerProtocol: str
    physicalAddress: str
    protocolAddress: str  # really Tuple[int, str], but for now let's keep parsing easy
    manufacturerId: str
    productDescription: str
    revisionData: str
    userDescription: str
    profileId: str


@add_fields_to_regex
@dataclass
class UserDescription:
    regex = r"USER_DESCRIPTION"
    userDescription: str


@add_fields_to_regex
@dataclass
class DefaultDataSet:
    regex = r"DEFAULT_DATA_SET"
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


@add_fields_to_regex
@dataclass
class CurrentDataSet:
    regex = r"CURRENT_DATA_SET"
    stepsRemoved: int
    offsetFromMaster: float
    meanPathDelay: float


@add_fields_to_regex
@dataclass
class ParentDataSet:
    regex = r"PARENT_DATA_SET"
    parentPortIdentity: str
    parentStats: int
    observedParentOffsetScaledLogVariance: int
    observedParentClockPhaseChangeRate: int
    grandmasterPriority1: int
    gm__ClockClass: int
    gm__ClockAccuracy: int
    gm__OffsetScaledLogVariance: int
    grandmasterPriority2: int
    grandmasterIdentity: str


@add_fields_to_regex
@dataclass
class TimePropertiesDataSet:
    regex = r"TIME_PROPERTIES_DATA_SET"
    currentUtcOffset: int
    leap61: int
    leap59: int
    currentUtcOffsetValid: int
    ptpTimescale: int
    timeTraceable: int
    frequencyTraceable: int
    timeSource: int


@add_fields_to_regex
@dataclass
class Priority1:
    regex = r"PRIORITY1"
    priority1: int


@add_fields_to_regex
@dataclass
class Priority2:
    regex = r"PRIORITY2"
    priority2: int


@add_fields_to_regex
@dataclass
class Domain:
    regex = r"DOMAIN"
    domainNumber: int


@add_fields_to_regex
@dataclass
class SlaveOnly:
    regex = r"SLAVE_ONLY"
    slaveOnly: int


@add_fields_to_regex
@dataclass
class ClockAccuracy:
    regex = r"CLOCK_ACCURACY"
    clockAccuracy: int


@add_fields_to_regex
@dataclass
class TraceabilityProperties:
    regex = r"TRACEABILITY_PROPERTIES"
    timeTraceable: int
    frequencyTraceable: int


@add_fields_to_regex
@dataclass
class TimescaleProperties:
    regex = r"TIMESCALE_PROPERTIES"
    ptpTimescale: int


@add_fields_to_regex
@dataclass
class AlternateTimeOffsetEnable:
    regex = r"ALTERNATE_TIME_OFFSET_ENABLE"
    keyField: int
    enable: int


@add_fields_to_regex
@dataclass
class AlternateTimeOffsetName:
    regex = r"ALTERNATE_TIME_OFFSET_NAME"
    keyField: int
    displayName: str


@add_fields_to_regex
@dataclass
class AlternateTimeOffsetProperties:
    regex = r"ALTERNATE_TIME_OFFSET_PROPERTIES"
    keyField: int
    currentOffset: int
    jumpSeconds: int
    timeOfNextJump: int


@add_fields_to_regex
@dataclass
class MasterOnly:
    regex = r"MASTER_ONLY"
    masterOnly: int


@add_fields_to_regex
@dataclass
class TimeStatusNp:
    regex = r"TIME_STATUS_NP"
    master_offset: int
    ingress_time: int
    cumulativeScaledRateOffset: float
    scaledLastGmPhaseChange: int
    gmTimeBaseIndicator: int
    lastGmPhaseChange: float
    gmPresent: str
    gmIdentity: str


@add_fields_to_regex
@dataclass
class GrandmasterSettingsNp:
    regex = r"GRANDMASTER_SETTINGS_NP"
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


@add_fields_to_regex
@dataclass
class SubscribeEventsNp:
    regex = r"SUBSCRIBE_EVENTS_NP"
    duration: int
    NOTIFY_PORT_STATE: str
    NOTIFY_TIME_SYNC: str
    NOTIFY_PARENT_DATA_SET: str
    NOTIFY_CMLDS: str


@add_fields_to_regex
@dataclass
class SynchronizationUncertainNp:
    regex = r"SYNCHRONIZATION_UNCERTAIN_NP"
    uncertain: int


@add_fields_to_regex
@dataclass
class PortDataSet:
    regex = r"PORT_DATA_SET"
    portIdentity: str
    portState: str
    logMinDelayReqInterval: int
    peerMeanPathDelay: int
    logAnnounceInterval: int
    announceReceiptTimeout: int
    logSyncInterval: int
    delayMechanism: int
    logMinPdelayReqInterval: int
    versionNumber: int


@add_fields_to_regex
@dataclass
class PortDataSetNp:
    regex = r"PORT_DATA_SET_NP"
    neighborPropDelayThresh: int
    asCapable: int


@add_fields_to_regex
@dataclass
class PortPropertiesNp:
    regex = r"PORT_PROPERTIES_NP"
    portIdentity: str
    portState: str
    timestamping: str
    interface: str


@add_fields_to_regex
@dataclass
class PortStatsNp:
    regex = r"PORT_STATS_NP"
    portIdentity: str
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


@add_fields_to_regex
@dataclass
class PortServiceStatsNp:
    regex = r"PORT_SERVICE_STATS_NP"
    portIdentity: str
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


@add_fields_to_regex
@dataclass
class PortHwclockNp:
    regex = r"PORT_HWCLOCK_NP"
    portIdentity: str
    phcIndex: int
    flags: int


@add_fields_to_regex
@dataclass
class PowerProfileSettingsNp:
    regex = r"POWER_PROFILE_SETTINGS_NP"
    version: int
    grandmasterID: int
    grandmasterTimeInaccuracy: int
    networkTimeInaccuracy: int
    totalTimeInaccuracy: int


@add_fields_to_regex
@dataclass
class CmldsInfoNp:
    regex = r"CMLDS_INFO_NP"
    meanLinkDelay: int
    scaledNeighborRateRatio: int
    as_capable: int


@add_fields_to_regex
@dataclass
class LogAnnounceInterval:
    regex = r"LOG_ANNOUNCE_INTERVAL"
    logAnnounceInterval: int


@add_fields_to_regex
@dataclass
class AnnounceReceiptTimeout:
    regex = r"ANNOUNCE_RECEIPT_TIMEOUT"
    announceReceiptTimeout: int


@add_fields_to_regex
@dataclass
class LogSyncInterval:
    regex = r"LOG_SYNC_INTERVAL"
    logSyncInterval: int


@add_fields_to_regex
@dataclass
class VersionNumber:
    regex = r"VERSION_NUMBER"
    versionNumber: int


@add_fields_to_regex
@dataclass
class DelayMechanism:
    regex = r"DELAY_MECHANISM"
    delayMechanism: int


@add_fields_to_regex
@dataclass
class LogMinPdelayReqInterval:
    regex = r"LOG_MIN_PDELAY_REQ_INTERVAL"
    logMinPdelayReqInterval: int


@dataclass
class Empty:
    regex = r"empty-tlv\s*"


@dataclass
class NullManagement:
    regex = r"\s*"


@dataclass
class ManagementTlv:
    regex = r"MANAGEMENT\s+(?P<payload>(?:.|\n)*)"
    payload: (
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
class ManagementErrorStatusTlv:
    regex = r"MANAGEMENT_ERROR_STATUS\s*"


@dataclass
class UnknownTlv:
    regex = r"unknown-tlv\s*"


@dataclass
class Response:
    regex = r"\s+(?P<source_port>[\da-fA-F.-]+)\s+seq\s+(?P<seq>\d+)\s+(?P<action>\w+)\s+(?P<tlv>(?:.|\n)*)"

    source_port: str
    seq: int
    action: str
    tlv: ManagementTlv | ManagementErrorStatusTlv | UnknownTlv


@dataclass
class Request:
    regex = r"\s*sending: (?P<action>\w+)\s+(?P<tlv_type>\w+)\s*\n"
    action: str
    tlv_type: str


Message = Request | Response
