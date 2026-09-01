#
# Scheduler — business rules.
#
# A package rather than a module: `lib.py` held every rule in the app, and a
# file that size is searched rather than read. Each subject has its own module
# now, and this imports them all and re-exports them, so a caller still reaches
# everything as `lib.<name>` — see `plan.md` § Stage 6.
#
# Two kinds of business live here, and one distinction separates them. Under
# `reserved`, a time is a resource: choosing one takes it from everyone else,
# and availability is computed from who is working and what they are already
# committed to. Under `unlimited`, a time is a preference: every increment the
# business is open is offered, always, and nobody is allocated. A café taking
# an order for 10:15 does not care that four other people also said 10:15.
#

from typing import Optional

from .. import db
from ..model import *

# Bottom of the package upward, each layer written on the one above it.
from .exception import *
from .time import *
from .code import *
from .notify import *
from .transform import *

from .availability import *
from .business import *
from .employee import *
from .job_type import *
from .money import *
from .platform import *

from .customer import *
from .kiosk import *
from .membership import *

from .appointment import *
from .booking import *
from .portal import *
from .schedule import *
