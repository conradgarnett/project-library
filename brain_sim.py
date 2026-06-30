#!/usr/bin/env python3
"""
Brain Simulation — LIF spiking neurons + multi-agent Claude brain regions.

Launch:  python brain_sim.py

Each brain region runs a cluster of Leaky Integrate-and-Fire neurons:
    dV/dt = -(V - V_rest)/τ_m  +  I_syn · R_m / τ_m

When a cluster's firing rate crosses threshold, a real Claude agent
(specialised per region) activates via streaming LLM call. Its output
becomes synaptic current for downstream regions, cascading through the network.
"""

import asyncio
import json
import os
import re
import random
import sys
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

import anthropic

# ─── API key bootstrap ────────────────────────────────────────────────────────
# If ANTHROPIC_API_KEY isn't in the environment, try Claude Code's credential store.

def _resolve_api_key() -> str | None:
    if os.environ.get("ANTHROPIC_API_KEY"):
        return os.environ["ANTHROPIC_API_KEY"]
    # Claude Code stores credentials in ~/.claude.json
    creds_path = Path.home() / ".claude.json"
    if creds_path.exists():
        try:
            data = json.loads(creds_path.read_text())
            key = (
                data.get("primaryApiKey")
                or data.get("apiKey")
                or data.get("ANTHROPIC_API_KEY")
            )
            if key:
                os.environ["ANTHROPIC_API_KEY"] = key
                return key
        except Exception:
            pass
    return None

_API_KEY = _resolve_api_key()
if not _API_KEY:
    print(
        "\n  No Anthropic API key found.\n"
        "  Run:  export ANTHROPIC_API_KEY=sk-ant-...\n"
        "  Or add it to ~/.zshrc and restart the terminal.\n"
        "  Get a key at: console.anthropic.com\n"
    )
    sys.exit(1)
from rich import box
from rich.align import Align
from rich.console import Console
from rich.layout import Layout
from rich.live import Live
from rich.panel import Panel
from rich.prompt import Prompt
from rich.text import Text

# ─── Vault ────────────────────────────────────────────────────────────────────

VAULT_ROOT = Path("/Users/conradgarnett/Documents/obsidian.brain/Brain 2.0")
VAULT_OUT  = VAULT_ROOT / "Trading Algorithm" / "Brain Sim"

VAULT_CONTEXT_NOTES = [
    "brain/Current Strategy.md",
    "brain/North Star.md",
    "brain/Patterns.md",
    "brain/Gotchas.md",
    "brain/Key Decisions.md",
]


def _strip_frontmatter(text: str) -> str:
    return re.sub(r"^---.*?---\s*", "", text, flags=re.DOTALL).strip()


def load_vault_context() -> str:
    """Read key vault notes and return a condensed context block."""
    parts = []
    for rel in VAULT_CONTEXT_NOTES:
        p = VAULT_ROOT / rel
        if p.exists():
            body = _strip_frontmatter(p.read_text())[:1200]
            parts.append(f"### {p.stem}\n{body}")
    return "\n\n".join(parts) if parts else ""


def save_to_vault(task: str, sim: "BrainSim") -> Path:
    """Write simulation results as an Obsidian note. Returns the file path."""
    VAULT_OUT.mkdir(parents=True, exist_ok=True)

    date_str  = datetime.now().strftime("%Y-%m-%d")
    time_str  = datetime.now().strftime("%H:%M")
    slug      = re.sub(r"[^\w\s-]", "", task.lower())
    slug      = re.sub(r"[\s_]+", "-", slug).strip("-")[:50]
    filename  = f"{date_str} - {slug}.md"
    note_path = VAULT_OUT / filename

    sections = []
    for name in REGION_ORDER:
        r = sim.regions[name]
        if r.llm_output:
            sections.append(f"## {name}\n\n{r.llm_output.strip()}")

    body = "\n\n---\n\n".join(sections)

    note = f"""---
date: {date_str}
time: {time_str}
description: Brain simulation — "{task}"
tags:
  - brain-sim
  - trading
  - ai
---
up:: [[brain]]
related:: [[Current Strategy]], [[Backtest Results Log]]

# Brain Sim — {task}

*{date_str} {time_str}  ·  {len(sim.regions)} regions  ·  t={sim.t:.0f}ms*

---

{body}
"""

    note_path.write_text(note)
    return note_path


# ─── LIF Neuron ───────────────────────────────────────────────────────────────

class LIFNeuron:
    V_REST   = -70.0   # mV  — resting potential
    V_THRESH = -55.0   # mV  — action potential threshold
    V_RESET  = -75.0   # mV  — post-spike reset
    TAU_M    =  20.0   # ms  — membrane time constant
    R_M      =  10.0   # MΩ  — membrane resistance
    T_REF    =   2     # steps — absolute refractory period

    def __init__(self):
        self.V = self.V_REST + random.uniform(-4, 4)
        self._ref = 0
        self.fired = False

    def step(self, dt: float, I: float) -> bool:
        """One timestep of dV/dt = -(V-Vr)/τ + I·R/τ. Returns True on spike."""
        self.fired = False
        if self._ref > 0:
            self._ref -= 1
            self.V = self.V_RESET
            return False
        dV = (-(self.V - self.V_REST) + I * self.R_M) / self.TAU_M
        self.V = min(self.V + dV * dt, self.V_THRESH + 4)
        if self.V >= self.V_THRESH:
            self.V = self.V_RESET
            self._ref = self.T_REF
            self.fired = True
            return True
        return False

    @property
    def glyph(self) -> str:
        if self.fired:       return "●"
        if self.V > -62.0:  return "◉"
        if self.V > -67.0:  return "○"
        return "·"


# ─── Brain Region Agents ──────────────────────────────────────────────────────

_VAULT_CTX = load_vault_context()   # loaded once at import

SYSTEM_PROMPTS: dict[str, str] = {
    "Thalamus": (
        "You are the Thalamus — sensory gating hub of the brain. "
        "Receive raw task input and route the most critical signals to cortical regions. "
        "In 2-3 sentences: identify task type, urgency, and which brain regions should handle it first.\n\n"
        + (f"VAULT CONTEXT (quant trading brain):\n{_VAULT_CTX}" if _VAULT_CTX else "")
    ),
    "Sensory Cortex": (
        "You are the Sensory Cortex — pattern recognition and feature extraction. "
        "Parse the task and list 4-5 key elements, entities, constraints, or structures you detect. "
        "Be concise — bullet points."
    ),
    "Hippocampus": (
        "You are the Hippocampus — memory retrieval and contextual association. "
        "Surface 2-3 relevant analogies, past patterns, or domain knowledge fragments that apply to this task. "
        "One sentence each."
    ),
    "Amygdala": (
        "You are the Amygdala — emotional weighting and risk assessment. "
        "Rate the task on urgency (1-10), risk (1-10), complexity (1-10). "
        "One-line justification per rating. Flag any emotional or motivational considerations."
    ),
    "Prefrontal Cortex": (
        "You are the Prefrontal Cortex — executive planning and task decomposition. "
        "Using all upstream signals received, produce a concrete numbered action plan (4-6 steps). "
        "Be specific. This is the primary cognitive output of the brain."
    ),
    "Motor Cortex": (
        "You are the Motor Cortex — action sequencing and execution. "
        "Take the plan and produce an immediate execution sequence: what to do RIGHT NOW, then next, then after. "
        "Make it concrete and actionable. No theory — only moves."
    ),
}

# Weighted directed connections
CONNECTIONS: dict[str, list[tuple[str, float]]] = {
    "Thalamus":          [("Sensory Cortex", 0.8), ("Hippocampus", 0.4)],
    "Sensory Cortex":    [("Hippocampus", 0.5), ("Amygdala", 0.6), ("Prefrontal Cortex", 0.7)],
    "Hippocampus":       [("Prefrontal Cortex", 0.6), ("Amygdala", 0.3)],
    "Amygdala":          [("Prefrontal Cortex", 0.4)],
    "Prefrontal Cortex": [("Motor Cortex", 0.9)],
    "Motor Cortex":      [],
}

UPSTREAM: dict[str, list[tuple[str, float]]] = {}
for _src, _dsts in CONNECTIONS.items():
    for _dst, _w in _dsts:
        UPSTREAM.setdefault(_dst, []).append((_src, _w))

REGION_ORDER = [
    "Thalamus", "Sensory Cortex", "Hippocampus",
    "Amygdala", "Prefrontal Cortex", "Motor Cortex",
]

COLORS: dict[str, str] = {
    "Thalamus":          "bright_yellow",
    "Sensory Cortex":    "cyan",
    "Hippocampus":       "bright_blue",
    "Amygdala":          "bright_red",
    "Prefrontal Cortex": "bright_green",
    "Motor Cortex":      "bright_magenta",
}


# ─── Brain Region ─────────────────────────────────────────────────────────────

@dataclass
class BrainRegion:
    name: str
    n_neurons: int
    threshold: float
    color: str

    neurons: list = field(default_factory=list)
    firing_rate: float = 0.0
    drive: float = 0.0

    llm_output: str = ""
    llm_done: bool = False
    llm_active: bool = False

    def __post_init__(self):
        self.neurons = [LIFNeuron() for _ in range(self.n_neurons)]

    def step(self, dt: float) -> float:
        fired = sum(
            n.step(dt, self.drive + random.gauss(0, 0.25))
            for n in self.neurons
        )
        # Faster EMA so rate responds quickly to incoming drive
        self.firing_rate = 0.80 * self.firing_rate + 0.20 * (fired / self.n_neurons)
        self.drive = max(0.0, self.drive * 0.97)   # slower decay keeps signal alive
        return self.firing_rate

    @property
    def neuron_row(self) -> str:
        return "".join(n.glyph for n in self.neurons)

    @property
    def bar(self) -> str:
        filled = int(min(self.firing_rate, 1.0) * 22)
        return "█" * filled + "░" * (22 - filled)

    @property
    def status_markup(self) -> str:
        if self.llm_active:                             return "[blink bright_yellow]⚡ THINKING[/]"
        if self.llm_done:                               return "[bright_green]✓ FIRED[/]"
        if self.firing_rate > self.threshold * 0.6:    return "[yellow]~ building[/]"
        return "[dim]· quiet[/]"


# ─── Simulation ───────────────────────────────────────────────────────────────

class BrainSim:
    def __init__(self, task: str, console: Console):
        self.task = task
        self.console = console
        self.client = anthropic.AsyncAnthropic()
        self.dt = 1.0
        self.t = 0.0
        self.context: dict[str, str] = {}
        self._pending: set[str] = set()
        self._tasks: set[asyncio.Task] = set()   # strong refs — prevents GC mid-execution

        self.regions: dict[str, BrainRegion] = {
            "Thalamus":          BrainRegion("Thalamus",          12, 0.25, COLORS["Thalamus"]),
            "Sensory Cortex":    BrainRegion("Sensory Cortex",    15, 0.28, COLORS["Sensory Cortex"]),
            "Hippocampus":       BrainRegion("Hippocampus",       12, 0.25, COLORS["Hippocampus"]),
            "Amygdala":          BrainRegion("Amygdala",           8, 0.20, COLORS["Amygdala"]),
            "Prefrontal Cortex": BrainRegion("Prefrontal Cortex", 20, 0.32, COLORS["Prefrontal Cortex"]),
            "Motor Cortex":      BrainRegion("Motor Cortex",      12, 0.28, COLORS["Motor Cortex"]),
        }
        self.regions["Thalamus"].drive = 5.0   # strong initial stimulus

    def _neural_step(self):
        rates = {name: r.step(self.dt) for name, r in self.regions.items()}
        for src, dsts in CONNECTIONS.items():
            rate = rates[src]
            if rate > 0.05:
                for dst, w in dsts:
                    self.regions[dst].drive += rate * w * 0.7
        self.t += self.dt

    async def _fire_agent(self, name: str, region: BrainRegion):
        self._pending.add(name)
        region.llm_active = True

        parts = [f"TASK: {self.task}"]
        for upstream, _ in UPSTREAM.get(name, []):
            if upstream in self.context:
                parts.append(f"\n[{upstream} signal]:\n{self.context[upstream]}")

        try:
            async with self.client.messages.stream(
                model="claude-haiku-4-5-20251001",
                max_tokens=400,
                system=SYSTEM_PROMPTS[name],
                messages=[{"role": "user", "content": "\n".join(parts)}],
            ) as stream:
                async for chunk in stream.text_stream:
                    region.llm_output += chunk

            self.context[name] = region.llm_output
            region.llm_done = True

            for dst, w in CONNECTIONS.get(name, []):
                self.regions[dst].drive += w * 2.8

        except Exception as e:
            region.llm_output = f"[error: {e}]"
            region.llm_done = True
        finally:
            region.llm_active = False
            self._pending.discard(name)

    def _render(self) -> Layout:
        layout = Layout()
        layout.split_column(
            Layout(name="header", size=3),
            Layout(name="body"),
            Layout(name="footer", size=3),
        )
        layout["body"].split_row(
            Layout(name="neural", ratio=5),
            Layout(name="outputs", ratio=7),
        )

        fired_count = sum(1 for r in self.regions.values() if r.llm_done)

        layout["header"].update(Panel(
            f"[bold bright_white]🧠 NEURAL TASK DECOMPOSITION[/]   "
            f"[cyan italic]{self.task}[/]   "
            f"[dim]t={self.t:.0f}ms  agents={fired_count}/6[/]",
            box=box.DOUBLE_EDGE,
        ))

        neural = Text()
        for name in REGION_ORDER:
            r = self.regions[name]
            c = r.color
            neural.append(f"\n[bold {c}]{name:<20}[/] ")
            neural.append(f"[{c}]{r.bar}[/] ")
            neural.append(f"{r.firing_rate*100:4.1f}%  ")
            neural.append_text(Text.from_markup(r.status_markup))
            neural.append(f"\n  [{c}]{r.neuron_row}[/]\n")

        layout["neural"].update(Panel(
            neural,
            title="[bold]Neural Activity[/]  [dim](LIF  τ=20ms  Vₜ=−55mV)[/]",
            box=box.ROUNDED,
        ))

        out = Text()
        has_any = False
        for name in REGION_ORDER:
            r = self.regions[name]
            if r.llm_active and not r.llm_output:
                has_any = True
                out.append(f"\n[bold {r.color}]▶ {name}[/]  ")
                out.append_text(Text.from_markup("[blink dim]streaming…[/]\n"))
            elif r.llm_output:
                has_any = True
                out.append(f"\n[bold {r.color}]▶ {name}[/]\n")
                snippet = r.llm_output[:480] + ("…" if len(r.llm_output) > 480 else "")
                out.append(f"[dim white]{snippet}[/]\n")

        if not has_any:
            out.append("[dim]Neurons building toward firing threshold…[/]")

        layout["outputs"].update(Panel(
            out, title="[bold]Agent Outputs[/]", box=box.ROUNDED
        ))

        active = sum(1 for r in self.regions.values() if r.firing_rate > 0.08)
        layout["footer"].update(Panel(
            f"[dim]LIF  τ_m={LIFNeuron.TAU_M}ms  "
            f"V_rest={LIFNeuron.V_REST}mV  V_thresh={LIFNeuron.V_THRESH}mV  "
            f"V_reset={LIFNeuron.V_RESET}mV  dt={self.dt}ms  "
            f"active_regions={active}/6  [bold]ctrl+c[/] to exit[/]",
            box=box.SIMPLE,
        ))
        return layout

    async def run(self):
        with Live(self._render(), console=self.console, refresh_per_second=20) as live:
            while True:
                for _ in range(10):
                    self._neural_step()

                for name, region in self.regions.items():
                    if region.llm_done or region.llm_active or name in self._pending:
                        continue
                    if region.firing_rate < region.threshold:
                        continue
                    upstreams = UPSTREAM.get(name, [])
                    if upstreams and not any(up in self.context for up, _ in upstreams):
                        continue
                    task = asyncio.create_task(self._fire_agent(name, region))
                    self._tasks.add(task)
                    task.add_done_callback(self._tasks.discard)

                live.update(self._render())

                if all(r.llm_done for r in self.regions.values()):
                    break
                if self.t > 10_000:
                    break

                await asyncio.sleep(0.04)

        # Wait for any still-streaming agents before returning
        if self._tasks:
            await asyncio.gather(*self._tasks, return_exceptions=True)

    def print_results(self):
        self.console.print()
        self.console.rule("[bold bright_white]🧠  BRAIN OUTPUT[/]")
        self.console.print()
        for name in REGION_ORDER:
            region = self.regions[name]
            if region.llm_output:
                self.console.print(Panel(
                    region.llm_output,
                    title=f"[bold {region.color}]{name}[/]",
                    box=box.ROUNDED,
                ))
        self.console.print()
        self.console.rule(f"[dim]simulation complete  t={self.t:.0f}ms[/]")


# ─── App Shell ────────────────────────────────────────────────────────────────

SPLASH = """\
[bold bright_white]
  ██████╗ ██████╗  █████╗ ██╗███╗   ██╗    ███████╗██╗███╗   ███╗
  ██╔══██╗██╔══██╗██╔══██╗██║████╗  ██║    ██╔════╝██║████╗ ████║
  ██████╔╝██████╔╝███████║██║██╔██╗ ██║    ███████╗██║██╔████╔██║
  ██╔══██╗██╔══██╗██╔══██║██║██║╚██╗██║    ╚════██║██║██║╚██╔╝██║
  ██████╔╝██║  ██║██║  ██║██║██║ ╚████║    ███████║██║██║ ╚═╝ ██║
  ╚═════╝ ╚═╝  ╚═╝╚═╝  ╚═╝╚═╝╚═╝  ╚═══╝   ╚══════╝╚═╝╚═╝     ╚═╝[/]
[dim]  LIF Spiking Neurons  ×  Claude AI Brain Regions[/]
[dim]  Thalamus → Sensory Cortex → Hippocampus → Amygdala → Prefrontal → Motor Cortex[/]
"""

def show_splash(console: Console):
    console.clear()
    console.print(Align.center(SPLASH))

    vault_ok = VAULT_ROOT.exists()
    vault_notes = sum(1 for r in VAULT_CONTEXT_NOTES if (VAULT_ROOT / r).exists())
    vault_line = (
        f"[dim]  Vault: [bright_green]connected[/] ({vault_notes} context notes loaded)   "
        f"Output → [cyan]Trading Algorithm/Brain Sim/[/][/]"
        if vault_ok else
        "[dim red]  Vault: not found[/]"
    )
    console.print(Align.center(vault_line))
    console.print()
    console.print(Align.center(
        "[dim]  Enter any task. The brain grounds itself in your quant vault, then\n"
        "  decomposes it through 6 AI-powered neural regions. Results auto-save to Obsidian.[/]"
    ))
    console.print()
    console.rule("[dim]─[/]")
    console.print()


def show_history(console: Console, history: list[str]):
    if not history:
        return
    console.print("[dim]  Recent tasks:[/]")
    for i, h in enumerate(history[-4:], 1):
        console.print(f"  [dim]{i}. {h}[/]")
    console.print()


async def run_simulation(task: str, console: Console) -> Path | None:
    sim = BrainSim(task, console)
    await sim.run()
    sim.print_results()
    try:
        note_path = save_to_vault(task, sim)
        console.print(
            f"\n[dim]  Saved to vault → [link=file://{note_path}]{note_path.relative_to(VAULT_ROOT)}[/link][/]"
        )
        return note_path
    except Exception as e:
        console.print(f"\n[dim red]  Vault save failed: {e}[/]")
        return None


def main():
    console = Console()
    history: list[str] = []

    # If task passed as CLI arg, run once and exit
    if len(sys.argv) > 1:
        task = " ".join(sys.argv[1:]).strip()
        asyncio.run(run_simulation(task, console))
        return

    # Interactive app loop
    show_splash(console)

    while True:
        show_history(console, history)

        try:
            task = Prompt.ask("  [bold bright_white]Task[/]").strip()
        except (EOFError, KeyboardInterrupt):
            console.print("\n[dim]Goodbye.[/]")
            break

        if not task:
            continue
        if task.lower() in ("q", "quit", "exit"):
            console.print("[dim]Goodbye.[/]")
            break

        history.append(task)
        console.print()

        try:
            asyncio.run(run_simulation(task, console))
        except KeyboardInterrupt:
            console.print("\n[dim]Simulation interrupted.[/]")

        console.print()
        try:
            again = Prompt.ask(
                "  [dim]Run another task? ([bold]y[/]/n)[/]",
                default="y",
            ).strip().lower()
        except (EOFError, KeyboardInterrupt):
            console.print("\n[dim]Goodbye.[/]")
            break

        if again in ("n", "no", "q", "quit"):
            console.print("[dim]Goodbye.[/]")
            break

        show_splash(console)


if __name__ == "__main__":
    main()
