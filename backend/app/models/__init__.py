# Importing every model here registers it with Base.metadata (needed for create_all).
from app.models.user import User
from app.models.goal import Goal
from app.models.task import Task
from app.models.preference import Preference
from app.models.behavior_observation import BehaviorObservation
from app.models.twin_trait import TwinTrait
from app.models.scenario_run import ScenarioRun
from app.models.feedback import Feedback
from app.models.twin_snapshot import TwinSnapshot
from app.models.permission import Permission
from app.models.access_log import AccessLog

__all__ = [
    "User", "Goal", "Task", "Preference", "BehaviorObservation", "TwinTrait",
    "ScenarioRun", "Feedback", "TwinSnapshot", "Permission", "AccessLog",
]
