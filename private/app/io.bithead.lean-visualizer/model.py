"""Lean Visualizer shapes."""

from datetime import date
from enum import Enum
from typing import Any, Dict, List

from pydantic import BaseModel


class Role(str, Enum):
    ADMIN = "Admin"
    EMPLOYEE = "Employee"


class Me(BaseModel):
    role: str


class JiraWorkUnit(BaseModel):
    issueKey: str
    name: str
    totalUnits: int
    completedUnits: int
    issueType: str
    releaseVersion: str = ""
    countsFresh: bool = False
    pillars: List[str] = []


class JiraSyncResponse(BaseModel):
    boardId: int
    jiraRootUrl: str
    issues: List[JiraWorkUnit]
    virtualFeaturesUpdated: int = 0


class ScheduleBar(BaseModel):
    featureId: str
    issueKey: str
    name: str
    color: str
    startOn: str
    finishOn: str


class ScheduleTrack(BaseModel):
    id: str
    name: str
    enabled: bool
    capacity: float
    bars: List[ScheduleBar]


class ScheduleRelease(BaseModel):
    id: str
    version: str
    date: str


class ScheduleResponse(BaseModel):
    horizonDays: int
    tracks: List[ScheduleTrack]
    releases: List[ScheduleRelease]


class RateOperator(BaseModel):
    operatorName: str
    plannedTotal: int
    unplannedTotal: int
    plannedPerWeek: float
    unplannedPerWeek: float
    weeksCounted: int


class HistoryOperator(BaseModel):
    operatorName: str
    planned: int
    unplanned: int


class HistoryWeek(BaseModel):
    weekStart: str
    weekEnd: str
    operators: List[HistoryOperator]


class ReportRates(BaseModel):
    windowStart: str
    windowEnd: str
    operators: List[RateOperator]
    history: List[HistoryWeek]


class PillarOpen(BaseModel):
    pillar: str
    remainingUnits: int
    featureCount: int
    share: float = 0


class PillarFinished(BaseModel):
    pillar: str
    featureCount: int


class MaterialChange(BaseModel):
    featureId: str
    name: str
    color: str
    previousFinishOn: str
    finishOn: str
    movedDays: int


class ReportPillars(BaseModel):
    open: List[PillarOpen]
    finished: List[PillarFinished]


class ReportResponse(BaseModel):
    asOf: str
    rates: ReportRates
    pillars: ReportPillars
    changes: List[MaterialChange]


class CheckpointResponse(BaseModel):
    releaseId: str
    releaseVersion: str
    releaseDate: str
    windowStart: str
    windowEnd: str
    savedAt: str
    issueCount: int


class CheckpointIssue(BaseModel):
    operatorName: str
    issueKey: str
    planned: bool


class ConfigResponse(BaseModel):
    jiraRootUrl: str


class ModelResponse(BaseModel):
    schemaVersion: int
    revision: int
    state: Dict[str, Any]
    config: ConfigResponse


class SaveModelRequest(BaseModel):
    revision: int | None = None
    state: Dict[str, Any]


class OperatorMetricsSummary(BaseModel):
    operatorName: str
    unitsDay: int
    unplannedWorkDay: int
    unitsWeek: int
    unplannedWorkWeek: int
    plannedWorkWeek: int
    metricYear: int | None = None
    metricWeekNumber: int | None = None
    weekStart: str | None = None
    weekEnd: str | None = None
    latestMetricDate: str | None = None
    latestSyncedAt: str | None = None


class MetricsSummaryResponse(BaseModel):
    metricYear: int
    metricWeekNumber: int
    weekStart: str
    weekEnd: str
    currentDate: str
    operators: List[OperatorMetricsSummary]


class MetricsSyncStats(BaseModel):
    metricDate: str
    metricYear: int
    metricWeekNumber: int
    weekStart: str
    weekEnd: str
    syncedAt: str
    completedIssues: int
    operatorCredits: int
    plannedCredits: int
    unplannedCredits: int
    unknownDeveloperAssociations: int
    unknownDeveloperNames: List[str]
    operatorRowsUpdated: int
    issuesScanned: int


class MetricsSyncResponse(BaseModel):
    summary: MetricsSummaryResponse
    stats: MetricsSyncStats


class MetricsWindowResponse(BaseModel):
    windowSize: int
    currentWeekStart: str
    currentWeekEnd: str
    weeks: List[MetricsSummaryResponse]


class OperatorMetricTask(BaseModel):
    issueKey: str
    description: str | None = None
    parentTask: str | None = None
    planned: bool
    releaseVersion: str = ""


class OperatorMetricTasks(BaseModel):
    operatorName: str
    tasks: List[OperatorMetricTask]


class MetricsTasksResponse(BaseModel):
    metricYear: int
    metricWeekNumber: int
    weekStart: str
    weekEnd: str
    currentDate: str
    jiraRootUrl: str
    jiraQuery: str
    operators: List[OperatorMetricTasks]


class FinishedWorkItem(BaseModel):
    issueKey: str
    description: str | None = None
    completedWeek: str
    operatorName: str


class FinishedWorkResponse(BaseModel):
    jiraRootUrl: str
    year: int
    operatorName: str
    items: List[FinishedWorkItem]


class MaterialLogEntry(BaseModel):
    kind: str
    featureId: str
    name: str
    color: str
    issueKey: str = ""
    aheadFeatureId: str = ""
    aheadName: str = ""
    unitsAdded: int = 0
    blockageId: str = ""
    createdOn: str = ""
    endedOn: str = ""
    note: str = ""
    days: int = 0
    previousRate: float = 0
    rate: float = 0


class MaterialLogFeature(BaseModel):
    featureId: str
    name: str
    color: str
    issueKey: str = ""
    entries: List[MaterialLogEntry] = []


class FinishedFeature(BaseModel):
    featureId: str
    name: str
    color: str


class MaterialLog(BaseModel):
    savedAt: str = ""
    previousSavedAt: str = ""
    features: List[MaterialLogFeature] = []
    finished: List[FinishedFeature] = []
