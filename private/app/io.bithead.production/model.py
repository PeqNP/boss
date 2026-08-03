#
# Production — domain models
#
# What the app reasons about, and what the client receives. There is no third
# family for the wire: a domain model's shape is already dictated by the screen
# that reads it, so `lib.py` returns these and routes hand them straight to
# FastAPI.
#
# camelCase throughout, which is our convention and does not bend to whatever
# an outside party uses. The storage shapes are `db.py`'s row models, and
# `lib.py` converts. A column rename is a storage decision and stops there; a
# count a dashboard wants is a presentation decision and never becomes a column.
#
# One table may feed several models — a list row and a detail view are read by
# different screens, so they are different shapes.
#

from pydantic import BaseModel
from typing import Any, Dict, List, Optional



# --- Records -------------------------------------------------------------
#
# What a rule reasons about. One per thing the app has, converted from `db.py`'s
# row models at the top of `lib.py`. Storage quirks are resolved here: an
# integer becomes a bool, and a column of JSON text becomes a dict.

class Pool(BaseModel):
    id: int
    name: str
    createdAt: str
    createdBy: int


class PoolResource(BaseModel):
    id: int
    poolId: int
    name: str
    value: str
    inService: bool
    # None means available. A resource is exclusive: one line at a time.
    heldByLineId: Optional[int]
    sortOrder: int


class ProductionLine(BaseModel):
    id: int
    name: str
    currentVersionId: Optional[int]
    createdAt: str
    createdBy: int


class ProductionLineVersion(BaseModel):
    id: int
    productionLineId: int
    version: int
    # A frozen version is immutable; the next edit deep-copies it.
    frozen: bool
    createdAt: str


class DeclaredColumn(BaseModel):
    id: int
    versionId: int
    name: str
    sortOrder: int


class RequiredPool(BaseModel):
    id: int
    versionId: int
    poolId: int
    # Denormalised so a historical version stays readable and its tokens stay
    # resolvable.
    poolName: str
    sortOrder: int


class Operation(BaseModel):
    id: int
    versionId: int
    name: str
    step: int


class OperationSection(BaseModel):
    id: int
    operationId: int
    sectionType: str
    sortOrder: int
    name: Optional[str]
    label: Optional[str]
    required: bool
    body: Optional[str]
    imagePath: Optional[str]


class SectionOption(BaseModel):
    id: int
    sectionId: int
    label: str
    sortOrder: int


class Job(BaseModel):
    id: int
    name: str
    productionLineId: int
    # Pinned when an admin starts the job, and the record that it has ever run.
    versionId: Optional[int]
    scheduledStart: str
    scheduledCompletion: str
    active: bool
    createdAt: str
    createdBy: int


class WorkUnit(BaseModel):
    id: int
    jobId: int
    rowOrder: int
    # The CSV row, parsed. Storage holds it as text; nothing above cares.
    input: Dict[str, Any]
    state: str
    lineId: Optional[int]
    currentStep: int
    startedAt: Optional[str]
    completedAt: Optional[str]
    failedAt: Optional[str]
    failedStep: Optional[int]
    requeuedAt: Optional[str]


class Line(BaseModel):
    """One operator's line on one job. Permanent — it carries their metrics."""
    id: int
    jobId: int
    userId: int
    state: str
    pauseOrigin: Optional[str]
    stopOrigin: Optional[str]
    stopReason: Optional[str]
    unitsCompleted: int
    unitsFailed: int
    joinedAt: str
    lastActiveAt: Optional[str]


class UnitOperation(BaseModel):
    """A step's progress on one work unit."""
    id: int
    workUnitId: int
    step: int
    state: str
    notes: Optional[str]
    startedAt: Optional[str]
    completedAt: Optional[str]
    completedBy: Optional[int]


class CapturedValue(BaseModel):
    step: int
    name: str
    value: Optional[str]


class UnitEdit(BaseModel):
    id: int
    workUnitId: int
    step: int
    name: str
    oldValue: Optional[str]
    newValue: Optional[str]
    editedBy: int
    editedAt: str
    stepsReset: int


class BlockingInterval(BaseModel):
    startedAt: str
    # None while the line is still blocked.
    endedAt: Optional[str]


class LineResource(BaseModel):
    """A resource a line holds, resolved to the names a token uses."""
    poolId: int
    resourceId: int
    poolName: str
    resourceName: str
    resourceValue: str


class PoolReference(BaseModel):
    """A production line version that requires a pool."""
    lineName: str
    version: int


class HeldResource(BaseModel):
    resourceName: str
    userId: int


class LiveLine(BaseModel):
    id: int
    jobName: str


class StateCount(BaseModel):
    state: str
    count: int


class CompletedUnit(BaseModel):
    """Only what a throughput calculation reads."""
    id: int
    startedAt: Optional[str]
    completedAt: str
    lineId: Optional[int]


# --- Screens -------------------------------------------------------------

# --- Pools ---------------------------------------------------------------

class ResourceHolder(BaseModel):
    """Who has a resource checked out. `None` on the resource means available."""
    lineId: int
    userId: int
    jobId: int


class Resource(BaseModel):
    id: int
    name: str
    value: str
    inService: bool
    heldBy: Optional[ResourceHolder] = None


class PoolDetail(BaseModel):
    id: int
    name: str
    resources: List[Resource]


class PoolSummary(BaseModel):
    """A row in the pool list. `availableCount` is what an operator can take."""
    id: int
    name: str
    resourceCount: int
    availableCount: int


# --- Production lines ----------------------------------------------------

class NamedRef(BaseModel):
    """A declared column or a required pool: an id and the name tokens use."""
    id: int
    name: str


class OperationSummary(BaseModel):
    id: int
    step: int
    name: str
    sectionCount: int


class ProductionLineDetail(BaseModel):
    id: int
    name: str
    versionId: Optional[int]
    version: int
    # A frozen version is history. Editing one forks, which is why every
    # mutating call reports `forked` and the client reloads when it is true.
    frozen: bool
    inUse: bool
    columns: List[NamedRef]
    pools: List[NamedRef]
    operations: List[OperationSummary]


class ProductionLineSummary(BaseModel):
    id: int
    name: str
    version: int
    operationCount: int
    inUse: bool


class Section(BaseModel):
    id: int
    type: str
    sortOrder: int
    # Input sections carry a name; a description or image does not, because
    # nothing can address one with a token.
    name: Optional[str]
    label: Optional[str]
    required: bool
    body: Optional[str]
    imagePath: Optional[str]
    options: List[str]


class OperationDetail(BaseModel):
    id: int
    step: int
    name: str
    versionId: int
    sections: List[Section]


# --- Jobs ----------------------------------------------------------------

class JobContract(BaseModel):
    """What a job's CSV must supply and what its operators must check out."""
    columns: List[str]
    pools: List[str]


class JobDetail(BaseModel):
    id: int
    name: str
    productionLineId: int
    scheduledStart: str
    scheduledCompletion: str
    active: bool
    # Pinning a version is what records that a job has ever run, and several
    # rules turn on it — a started job cannot change line or reimport its units.
    hasStarted: bool
    versionId: Optional[int]
    workUnitCount: int
    contract: JobContract
    # The product being built, and which version of its line this job pinned.
    # Every job list and dashboard header reads both.
    productionLineName: str = ""
    version: int = 0


# --- Work units ----------------------------------------------------------

class WorkUnitSummary(BaseModel):
    """A row in the work unit list."""
    id: int
    label: str
    rowOrder: int
    input: Dict[str, Any]
    state: str
    currentStep: int
    lineId: Optional[int]
    startedAt: Optional[str]
    completedAt: Optional[str]
    failedAt: Optional[str]
    failedStep: Optional[int]
    requeuedAt: Optional[str]
    # Who last worked it, by name. Resolved at the route, which is the only
    # layer that may ask BOSS who a user id belongs to.
    operator: str = ""


class UsedResource(BaseModel):
    """A resource a line holds, or that a finished unit was built with."""
    pool: str
    resource: str
    value: str


class OperationValue(BaseModel):
    """One thing a step captured, ready to read.

    A list rather than a map keyed by name, because the screen shows these in
    the order the operation declares them and titles each with the label the
    admin wrote — neither of which survives a dictionary.
    """
    name: str
    label: str
    value: Optional[str]


class WorkUnitOperation(BaseModel):
    step: int
    name: str
    state: str
    notes: Optional[str]
    startedAt: Optional[str]
    completedAt: Optional[str]
    # A name, not an id. This is read as-is on a screen that reviews a unit
    # after the fact, where "4" answers no question anyone was asking.
    completedBy: Optional[str]
    values: List[OperationValue]


class WorkUnitEdit(BaseModel):
    step: int
    name: str
    oldValue: Optional[str]
    newValue: Optional[str]
    # A name, for the same reason `WorkUnitOperation.completedBy` is one.
    editedBy: Optional[str]
    editedAt: str
    # How many later operations the correction invalidated.
    stepsReset: int


class WorkUnitDetail(BaseModel):
    id: int
    jobId: int
    label: str
    state: str
    input: Dict[str, Any]
    currentStep: int
    lineId: Optional[int]
    startedAt: Optional[str]
    completedAt: Optional[str]
    failedAt: Optional[str]
    failedStep: Optional[int]
    requeuedAt: Optional[str]
    resources: List[UsedResource]
    operations: List[WorkUnitOperation]
    edits: List[WorkUnitEdit]


# --- Lines ---------------------------------------------------------------

class LineBlock(BaseModel):
    """Why a line cannot work, and who may clear it."""
    kind: str           # paused | stopped
    origin: str         # operator | admin | window
    reason: Optional[str] = None


class LineDetail(BaseModel):
    lineId: int
    jobId: int
    userId: int
    state: str
    blocked: Optional[LineBlock]
    pauseOrigin: Optional[str]
    stopOrigin: Optional[str]
    stopReason: Optional[str]
    unitsCompleted: int
    unitsFailed: int
    workUnitId: Optional[int]
    resources: List[UsedResource]
    # What the dashboard shows about the unit in hand: which one, and how far
    # through the line it is.
    fullName: str = ""
    workUnitLabel: Optional[str] = None
    step: Optional[int] = None
    stepCount: int = 0
    # Closed intervals plus any interval still open, so a dashboard can show
    # how long a line has been down without waiting for it to come back.
    blockedSeconds: float


# --- Dashboard -----------------------------------------------------------

class Throughput(BaseModel):
    """Rate over a trailing window. Both rates are `None` when nothing finished."""
    unitsInWindow: int
    windowMinutes: int
    unitsPerHour: Optional[float]
    avgCycleSeconds: Optional[float]


class JobStats(Throughput):
    total: int
    pending: int
    inProgress: int
    complete: int
    failed: int
    operators: int
    paused: int
    stopped: int


class JobDashboard(BaseModel):
    job: JobDetail
    stats: JobStats
    lines: List[LineDetail]


# --- Results of an action ------------------------------------------------
#
# What a rule reports back after changing something. The client needs these to
# decide what to redraw — a fork means reload, a completed unit means advance.

class SavedProductionLine(BaseModel):
    lineId: int
    versionId: int
    # True when a frozen version was forked. Operation and section ids changed,
    # so a client holding the old ones reloads.
    forked: bool
    created: bool


class SavedOperation(BaseModel):
    operationId: int
    step: int
    versionId: int
    forked: bool


class VersionSummary(BaseModel):
    """A row in a production line's history."""
    versionId: int
    version: int
    frozen: bool
    createdAt: str
    # How many jobs pinned it. A version with jobs can never be edited again.
    jobCount: int


class DeletedFromLine(BaseModel):
    """The result of removing an operation or a section."""
    versionId: int
    forked: bool


class SavedSection(BaseModel):
    sectionId: int
    operationId: int
    versionId: int
    forked: bool


class SavedPool(BaseModel):
    poolId: int
    name: str
    created: bool = False


class SavedResource(BaseModel):
    resourceId: int
    created: bool


class SavedJob(BaseModel):
    jobId: int
    created: bool


class StartedJob(BaseModel):
    jobId: int
    versionId: int
    operatorsResumed: int


class StoppedJob(BaseModel):
    jobId: int
    operatorsPaused: int


class JoinedLine(BaseModel):
    lineId: int
    jobId: int
    rejoined: bool


class LeftLine(BaseModel):
    lineId: int
    jobId: int
    workUnitsReleased: int
    # Who was on the line. Needed to tell them: by the time the line is left it
    # is no longer live, so they are no longer in the job's audience.
    userId: int
    # What they were holding, read before it went back. The operator is walking
    # away from the bench and has to be told what to carry with them.
    resources: List[UsedResource] = []


class LineStateChange(BaseModel):
    lineId: int
    jobId: int
    state: str
    origin: str


class ReturnedResource(BaseModel):
    resourceId: int
    lineId: Optional[int]


class CompletedOperation(BaseModel):
    workUnitId: int
    jobId: int
    # `None` once the unit is finished — there is no next step to show.
    nextStep: Optional[int]
    unitComplete: bool


class FailedOperation(BaseModel):
    workUnitId: int
    jobId: int
    failedStep: int
    jobDeactivated: bool


class EditedOperation(BaseModel):
    workUnitId: int
    jobId: int
    stepsReset: int
    currentStep: int


class RequeuedWorkUnit(BaseModel):
    workUnitId: int
    jobId: int
    jobReactivated: bool


# --- CSV import ----------------------------------------------------------

class CsvError(BaseModel):
    """Something wrong with an uploaded file, placed at a line the admin can find."""
    line: int
    message: str


class CsvPreview(BaseModel):
    """A parsed file awaiting confirmation.

    `rows` is a sample for the admin to eyeball; `rowCount` is the true total.
    Sending thousands of rows would cost more than it tells them.
    """
    uploadId: str
    columns: List[str]
    rowCount: int
    rows: List[Dict[str, str]]
    errors: List[CsvError]


# --- The operator's screens ----------------------------------------------

class HeldLine(BaseModel):
    """The line the caller is on, so any screen can offer to return to it."""
    lineId: int
    jobId: int
    jobName: str


class Me(BaseModel):
    isAdmin: bool
    userId: int
    fullName: str
    activeLine: Optional[HeldLine] = None


class AvailableResource(BaseModel):
    id: int
    name: str
    value: str


class PoolChoice(BaseModel):
    """A pool a joining operator must pick from, and what is free to take."""
    poolId: int
    name: str
    resources: List[AvailableResource]


class JoinInfo(BaseModel):
    jobName: str
    product: str
    pools: List[PoolChoice]
    # Reasons the operator cannot join. Empty means they can.
    blocked: List[str]


class AvailableJob(BaseModel):
    jobId: int
    name: str
    product: str
    unitsRemaining: int
    joined: bool


class ActiveJobs(BaseModel):
    heldLine: Optional[HeldLine]
    jobs: List[AvailableJob]


class OperatorSection(BaseModel):
    """A section as the operator sees it, with every token already resolved."""
    id: int
    type: str
    name: Optional[str]
    label: Optional[str]
    required: bool
    body: Optional[str]
    imagePath: Optional[str]
    options: List[str]


class OperatorOperation(BaseModel):
    step: int
    name: str
    state: str
    notes: Optional[str]
    sections: List[OperatorSection]
    values: Dict[str, Any]


class LineState(BaseModel):
    """Everything the manufacturing screen draws."""
    lineId: int
    jobId: int
    jobName: str
    product: str
    state: str
    blocked: Optional[LineBlock]
    workUnit: Optional[WorkUnitSummary]
    operations: List[OperatorOperation]
    resources: List[UsedResource]


class PulledWorkUnit(BaseModel):
    """The result of asking for work. `empty` when the queue has run dry."""
    empty: bool
    workUnit: Optional[WorkUnitSummary] = None
    operations: List[OperatorOperation] = []
    resources: List[UsedResource] = []


# --- What a route answers when there is nothing to say -------------------

class OK(BaseModel):
    ok: bool = True


class TokenErrorDetail(BaseModel):
    """An unresolvable token, placed where the admin can find it."""
    step: int
    operationName: Optional[str]
    token: str
    reason: str


class LineValidation(BaseModel):
    valid: bool
    errors: List[TokenErrorDetail]


class CommittedUpload(BaseModel):
    workUnitCount: int


# --- Input models --------------------------------------------------------
#
# Request bodies. Domain models too: the client dictates their shape as surely
# as it dictates a response's, and a rule reads them as it reads any other.

class SavePoolInput(BaseModel):
    name: str


class SaveResourceInput(BaseModel):
    name: str
    value: str
    inService: bool = True


class SaveProductionLineInput(BaseModel):
    name: str
    columns: List[str]
    poolIds: List[int]


class SaveOperationInput(BaseModel):
    name: str


class SaveSectionInput(BaseModel):
    type: str
    name: Optional[str] = None
    label: Optional[str] = None
    required: bool = False
    body: Optional[str] = None
    options: List[str] = []


class SaveJobInput(BaseModel):
    name: str
    productionLineId: int
    scheduledStart: str
    scheduledCompletion: str


class ReorderOperationsInput(BaseModel):
    operationIds: List[int]


class ReorderSectionsInput(BaseModel):
    sectionIds: List[int]


class CommitUploadInput(BaseModel):
    uploadId: str


class ChosenResource(BaseModel):
    poolId: int
    resourceId: int


class JoinLineInput(BaseModel):
    resources: List[ChosenResource]


class StopLineInput(BaseModel):
    reason: Optional[str] = None


class OperationValuesInput(BaseModel):
    """Body for completing, failing, or editing a step.

    `values` is keyed by section name, which is what a token addresses, and
    holds whatever that section captures — text, a number, or a tick.
    """
    values: Dict[str, Any] = {}
    notes: str = ""
