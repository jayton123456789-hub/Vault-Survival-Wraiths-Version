from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Literal

import typer
from rich.console import Console
from rich.table import Table

from bit_life_survival.core.engine import create_initial_state, run_simulation
from bit_life_survival.core.loader import ContentValidationError, load_content

app = typer.Typer(add_completion=False, help="Run deterministic headless simulation for balancing and testing.")
console = Console()

AutopickPolicy = Literal["safe", "random", "greedy"]


def _normalize_seed(raw_seed: str) -> int | str:
    try:
        return int(raw_seed)
    except ValueError:
        return raw_seed


def _state_signature_payload(state, logs) -> dict:
    return {
        "seed": state.seed,
        "step": state.step,
        "distance": round(state.distance, 6),
        "time": state.time,
        "biome_id": state.biome_id,
        "meters": {
            "stamina": round(state.meters.stamina, 6),
            "hydration": round(state.meters.hydration, 6),
            "morale": round(state.meters.morale, 6),
        },
        "injury": round(state.injury, 6),
        "flags": sorted(state.flags),
        "inventory": dict(sorted(state.inventory.items())),
        "equipped": state.equipped.model_dump(mode="python"),
        "dead": state.dead,
        "death_reason": state.death_reason,
        "event_cooldowns": dict(sorted(state.event_cooldowns.items())),
        "rng_state": state.rng_state,
        "rng_calls": state.rng_calls,
        "timeline": [entry.to_dict() for entry in logs],
    }


@app.command()
def main(
    seed: str = typer.Option("123", "--seed", help="Seed value (int or string)."),
    steps: int = typer.Option(50, "--steps", min=1, help="Max number of simulation steps."),
    biome: str = typer.Option("suburbs", "--biome", help="Starting biome id."),
    autopick: AutopickPolicy = typer.Option("safe", "--autopick", help="Choice policy: safe|random|greedy."),
) -> None:
    content_dir = Path(__file__).resolve().parents[1] / "content"
    try:
        content = load_content(content_dir)
    except ContentValidationError as exc:
        console.print(f"[bold red]Content load failed:[/bold red] {exc}")
        raise typer.Exit(1) from exc

    if biome not in content.biome_by_id:
        console.print(f"[bold red]Unknown biome '{biome}'.[/bold red]")
        raise typer.Exit(1)

    state = create_initial_state(_normalize_seed(seed), biome)
    final_state, logs = run_simulation(state, content, steps=steps, policy=autopick)

    for entry in logs:
        console.print(entry.format(), markup=False)

    summary = Table(title="Simulation Summary")
    summary.add_column("Field", style="cyan", no_wrap=True)
    summary.add_column("Value", style="white")
    summary.add_row("Seed", str(final_state.seed))
    summary.add_row("Policy", autopick)
    summary.add_row("Steps", f"{final_state.step}/{steps}")
    summary.add_row("Distance", f"{final_state.distance:.2f}")
    summary.add_row("Time", str(final_state.time))
    summary.add_row(
        "Meters",
        (
            f"stamina={final_state.meters.stamina:.2f}, "
            f"hydration={final_state.meters.hydration:.2f}, "
            f"morale={final_state.meters.morale:.2f}"
        ),
    )
    summary.add_row("Injury", f"{final_state.injury:.2f}")
    summary.add_row("Dead", str(final_state.dead))
    summary.add_row("Death Reason", final_state.death_reason or "-")
    summary.add_row("Flags", ", ".join(sorted(final_state.flags)) or "-")
    summary.add_row(
        "Inventory",
        ", ".join(f"{item_id}x{qty}" for item_id, qty in sorted(final_state.inventory.items())) or "-",
    )
    console.print()
    console.print(summary)

    payload = _state_signature_payload(final_state, logs)
    signature = hashlib.sha256(json.dumps(payload, sort_keys=True).encode("utf-8")).hexdigest()[:16]
    console.print(f"\n[bold green]Deterministic signature:[/bold green] {signature}")


if __name__ == "__main__":
    app()
