"""Core deterministic simulation modules."""

from .drone import DroneRecoveryReport, run_drone_recovery
from .engine import (
    ChoiceResolution,
    EventInstance,
    EventOptionInstance,
    advance_to_next_event,
    apply_choice,
    apply_choice_with_state_rng,
    apply_choice_with_state_rng_detailed,
    create_initial_state,
    run_simulation,
    step,
)
from .loader import ContentBundle, ContentValidationError, load_content
from .models import GameState, SaveData, VaultState
from .outcomes import OutcomeReport
from .persistence import (
    create_default_save_data,
    draft_citizen_from_claw,
    load_save_data,
    refill_citizen_queue,
    save_save_data,
    store_item,
    take_item,
)

__all__ = [
    "ContentBundle",
    "ContentValidationError",
    "ChoiceResolution",
    "DroneRecoveryReport",
    "EventInstance",
    "EventOptionInstance",
    "GameState",
    "OutcomeReport",
    "SaveData",
    "VaultState",
    "advance_to_next_event",
    "apply_choice",
    "apply_choice_with_state_rng",
    "apply_choice_with_state_rng_detailed",
    "create_default_save_data",
    "create_initial_state",
    "draft_citizen_from_claw",
    "load_content",
    "load_save_data",
    "refill_citizen_queue",
    "run_drone_recovery",
    "run_simulation",
    "save_save_data",
    "store_item",
    "step",
    "take_item",
]
