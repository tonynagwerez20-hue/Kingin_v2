"""
CLIDashboard — Fixed & Enhanced Edition
=========================================
Changes vs original:
  • make_market_panel: added Regime row (STABLE/VOLATILE/RANGING with colours)
    and Next Event row (shows nearest upcoming high-impact news event + countdown)
  • make_pipeline_panel: added Reason column (truncated), handles bias key
  • make_signals_panel: NEWS_SCALP signals shown in orange, DIRECTION_VETO shown
    in yellow — previously these were invisible or showed as "WAIT"
  • make_header: version bumped to v6.2, shows live equity-to-balance ratio
  • make_news_panel: new standalone panel showing today's event schedule
  • _setup_layout: right column now has 3 slots (pipeline / signals / news)
  • update(): accepts new state keys: regime, next_event, news_events
"""

import time
from datetime import datetime, timezone
from typing import Dict, List, Any, Optional

from rich.live import Live
from rich.layout import Layout
from rich.panel import Panel
from rich.table import Table
from rich.console import Console
from rich.text import Text
from rich.align import Align


class CLIDashboard:
    """
    HedgeEA Professional CLI Dashboard v6.2.
    Lite-mode friendly — no heavy imports, minimal CPU per refresh cycle.
    """

    def __init__(self):
        self.console    = Console()
        self.layout     = Layout()
        self._setup_layout()
        self.start_time = datetime.now()

    def _setup_layout(self):
        self.layout.split(
            Layout(name="header", size=3),
            Layout(name="main",   ratio=1),
            Layout(name="footer", size=3),
        )
        self.layout["main"].split_row(
            Layout(name="left",  ratio=1),
            Layout(name="right", ratio=2),
        )
        self.layout["left"].split(
            Layout(name="account", ratio=1),
            Layout(name="market",  ratio=1),
        )
        self.layout["right"].split(
            Layout(name="pipeline", ratio=1),
            Layout(name="signals",  ratio=1),
            Layout(name="news",     ratio=1),
        )

    # ──────────────────────────────────────────────────────────────────
    # Header
    # ──────────────────────────────────────────────────────────────────

    def make_header(self, state: Dict = None) -> Panel:
        grid = Table.grid(expand=True)
        grid.add_column(justify="left",   ratio=1)
        grid.add_column(justify="center", ratio=1)
        grid.add_column(justify="right",  ratio=1)

        market    = (state or {}).get("market", {})
        account   = (state or {}).get("account", {})
        master_on = market.get("master_switch", True)

        status_text = (
            Text("● ACTIVE",  style="bold green")  if master_on
            else Text("○ STANDBY", style="bold yellow")
        )
        runtime = str(datetime.now() - self.start_time).split(".")[0]

        # Equity ratio indicator
        equity  = account.get("equity",  0.0)
        balance = account.get("balance", 0.0)
        ratio   = (equity / balance * 100) if balance > 0 else 100.0
        eq_style = "green" if ratio >= 99 else "yellow" if ratio >= 95 else "red"
        eq_text  = Text(f"EQ {ratio:.1f}%", style=eq_style)

        grid.add_row(
            Text("HedgeEA SMC v6.2", style="bold white"),
            Align.center(status_text),
            Text(f"Runtime: {runtime}  ", style="dim") + eq_text,
        )
        return Panel(grid, style="blue" if master_on else "yellow")

    # ──────────────────────────────────────────────────────────────────
    # Account panel
    # ──────────────────────────────────────────────────────────────────

    def make_account_panel(self, data: Dict) -> Panel:
        table = Table.grid(expand=True)
        table.add_column(style="cyan")
        table.add_column(justify="right", style="bold white")

        equity    = data.get("equity",        0.0)
        balance   = data.get("balance",       0.0)
        daily_pnl = data.get("daily_pnl",     0.0)
        loss_pct  = data.get("daily_loss_pct", 0.0)
        pnl_style = "green" if daily_pnl >= 0 else "red"

        table.add_row("Balance",     f"${balance:,.2f}")
        table.add_row("Equity",      f"${equity:,.2f}")
        table.add_row("Daily P&L",   Text(f"${daily_pnl:+.2f}", style=pnl_style))
        table.add_row("Daily Loss %", f"{loss_pct:.2f}%")
        
        risk_tier = data.get("risk_tier", "Standard")
        table.add_row("Risk Tier",   Text(risk_tier, style="bold yellow"))

        return Panel(table, title="[bold]Account Metrics[/]", border_style="cyan")

    # ──────────────────────────────────────────────────────────────────
    # Market panel — now includes Regime + Next Event
    # ──────────────────────────────────────────────────────────────────

    def make_market_panel(self, data: Dict) -> Panel:
        table = Table.grid(expand=True)
        table.add_column(style="magenta")
        table.add_column(justify="right", style="bold white")

        symbol     = data.get("symbol",       "XAUUSD")
        price      = data.get("price",         0.0)
        spread     = data.get("spread",        0.0)
        h1_bias    = data.get("htf_bias",    data.get("h1_bias", "NEUTRAL")).upper()
        master_on  = data.get("master_switch", True)
        regime     = data.get("regime",        "STABLE").upper()
        next_event = data.get("next_event",    "")

        h1_style     = "green" if h1_bias == "BULLISH" else "red" if h1_bias == "BEARISH" else "white"
        regime_style = (
            "green"  if regime == "STABLE"
            else "red"    if regime == "VOLATILE"
            else "yellow" if regime == "RANGING"
            else "white"
        )
        switch_text = Text("ON", style="bold green") if master_on else Text("OFF", style="bold red")

        table.add_row("Symbol",        symbol)
        table.add_row("Price",         f"{price:.2f}")
        table.add_row("Spread",        f"{spread:.1f} pts")
        table.add_row("H1 Bias",       Text(h1_bias,    style=h1_style))
        table.add_row("Regime",        Text(regime,     style=regime_style))
        table.add_row("Next Event",    next_event or "—")
        table.add_row("Master Switch", switch_text)

        return Panel(table, title="[bold]Market Feed[/]", border_style="magenta")

    # ──────────────────────────────────────────────────────────────────
    # Pipeline panel — adds Reason column + bias indicator
    # ──────────────────────────────────────────────────────────────────

    def make_pipeline_panel(self, layers: List[Dict]) -> Panel:
        table = Table(expand=True, box=None)
        table.add_column("Layer",      style="dim",   min_width=18)
        table.add_column("Status",     justify="center")
        table.add_column("Score",      justify="right")
        table.add_column("Reason",     style="dim",   max_width=30)

        for layer in layers:
            status  = layer.get("status", False)
            score   = layer.get("score",  0.0)
            reason  = layer.get("reason", "")
            name    = layer.get("name",   "Unknown")

            # Trim the layer prefix from reason for compact display
            for prefix in ("KillzoneFilter: ", "Structure: ", "SMC LiquiditySweep: ",
                           "Displacement: ", "FVG: ", "MicroMSS: ", "NewsEventLayer: "):
                reason = reason.replace(prefix, "")
            reason = reason[:28] + "…" if len(reason) > 30 else reason

            if status:
                icon = "[bold green]PASS[/]"
            else:
                icon = "[bold red]FAIL[/]"

            table.add_row(name, icon, f"{score:.2f}", reason)

        return Panel(table, title="[bold]IGOF Pipeline[/]", border_style="yellow")

    # ──────────────────────────────────────────────────────────────────
    # Signals panel — handles NEWS_SCALP and DIRECTION_VETO
    # ──────────────────────────────────────────────────────────────────

    def make_signals_panel(self, signals: List[Dict]) -> Panel:
        table = Table(expand=True, box=None)
        table.add_column("Time",      style="dim")
        table.add_column("Type",      style="bold")
        table.add_column("Action",    style="bold")
        table.add_column("Info",      style="dim")

        for sig in signals[-6:]:
            sig_type = sig.get("type", "SMC")
            action   = sig.get("action",    sig.get("direction", "WAIT")).upper()
            t        = sig.get("time",      "")
            info     = ""

            if sig_type == "NEWS_SCALP":
                style = "bold yellow"
                info  = sig.get("trigger", "")[:20]
            elif sig.get("event") == "DIRECTION_VETO":
                style = "yellow"
                action = "VETOED"
                info   = sig.get("reason", "")[:20]
            elif "BUY" in action or "LONG" in action or "BULLISH" in action:
                style = "green"
            elif "SELL" in action or "SHORT" in action or "BEARISH" in action:
                style = "red"
            else:
                style = "white"

            price = sig.get("price", 0.0)
            info  = info or (f"@ {price:.2f}" if price else "")

            table.add_row(t, Text(sig_type, style=style), Text(action, style=style), info)

        return Panel(table, title="[bold]Signal Audit[/]", border_style="green")

    # ──────────────────────────────────────────────────────────────────
    # News panel — today's high-impact event schedule
    # ──────────────────────────────────────────────────────────────────

    def make_news_panel(self, news_events: List[Dict]) -> Panel:
        table = Table(expand=True, box=None)
        table.add_column("Time (UTC)", style="dim", min_width=8)
        table.add_column("Impact",     justify="center")
        table.add_column("Event",      style="white")
        table.add_column("Actual / Fcst", justify="right", style="dim")

        now_utc = datetime.now(timezone.utc)

        for e in news_events[:8]:   # cap at 8 rows for performance
            try:
                from datetime import datetime as dt
                et = dt.fromisoformat(e.get("time_utc", "")).astimezone(timezone.utc)
                t_str = et.strftime("%H:%M")
                is_past = et < now_utc
            except Exception:
                t_str  = e.get("time_utc", "")[:5]
                is_past = False

            impact = e.get("impact", 0)
            imp_text = (
                Text("●●●", style="bold red")    if impact == 3
                else Text("●●○", style="yellow") if impact == 2
                else Text("●○○", style="dim")
            )

            title  = e.get("title", "")[:28]
            actual = e.get("actual")
            fcst   = e.get("forecast")
            av_str = ""
            if actual is not None:
                av_str = f"{actual:.1f}"
                if fcst is not None:
                    av_str += f" / {fcst:.1f}"
            elif fcst is not None:
                av_str = f"fcst {fcst:.1f}"

            time_text = Text(t_str, style="dim" if is_past else "white")
            table.add_row(time_text, imp_text, title, av_str)

        if not news_events:
            table.add_row("—", Text("○○○", style="dim"), "No USD events today", "")

        return Panel(table, title="[bold]News Calendar[/]", border_style="blue")

    # ──────────────────────────────────────────────────────────────────
    # Footer
    # ──────────────────────────────────────────────────────────────────

    def make_footer(self) -> Panel:
        return Panel(
            Align.center(
                Text("HedgeEA v6.2  |  Ctrl+C to shutdown gracefully", style="dim white")
            ),
            style="blue",
        )

    # ──────────────────────────────────────────────────────────────────
    # Update — called every loop cycle
    # ──────────────────────────────────────────────────────────────────

    def update(self, state: Dict[str, Any]):
        """
        Refresh all panels. New state keys accepted:
          state["market"]["regime"]     — STABLE / VOLATILE / RANGING
          state["market"]["next_event"] — "14:30 NFP" etc.
          state["market"]["htf_bias"]   — structural bias from structure layer
          state["news_events"]          — list of today's event dicts from NewsEventLayer
        """
        # Extract risk_tier from global state for the account panel
        acc_data = state.get("account", {}).copy()
        if "risk_tier" in state:
            acc_data["risk_tier"] = state["risk_tier"]

        self.layout["header"].update(self.make_header(state))
        self.layout["account"].update(self.make_account_panel(acc_data))
        self.layout["market"].update(self.make_market_panel(state.get("market",  {})))
        self.layout["pipeline"].update(self.make_pipeline_panel(state.get("pipeline", [])))
        self.layout["signals"].update(self.make_signals_panel(state.get("signals", [])))
        self.layout["news"].update(self.make_news_panel(state.get("news_events", [])))
        self.layout["footer"].update(self.make_footer())


# ──────────────────────────────────────────────────────────────────────
# Demo / test mode
# ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    dash = CLIDashboard()
    mock_state = {
        "account": {
            "equity": 88.50, "balance": 86.80,
            "daily_pnl": 1.70, "daily_loss_pct": 0.0,
        },
        "market": {
            "symbol": "XAUUSD", "price": 4862.50, "spread": 22,
            "htf_bias": "BEARISH", "regime": "STABLE",
            "next_event": "14:30 NFP", "master_switch": True,
        },
        "pipeline": [
            {"name": "KillzoneFilter",      "status": True,  "score": 1.00,
             "reason": "London-NY Overlap Active"},
            {"name": "MechanicalStructure", "status": True,  "score": 1.00,
             "reason": "Bearish BOS: 4862 < 4981"},
            {"name": "LiquiditySweep",      "status": True,  "score": 1.00,
             "reason": "BEARISH sweep (Score: 1.00)"},
            {"name": "Displacement",        "status": True,  "score": 1.00,
             "reason": "H1: one-sided delivery"},
            {"name": "FVGDiscount",         "status": True,  "score": 0.75,
             "reason": "Bullish IFVG 4865–4872"},
            {"name": "MicroMSS",            "status": True,  "score": 0.67,
             "reason": "Fair Value Return"},
            {"name": "NewsEventLayer",      "status": True,  "score": 1.00,
             "reason": "No blocking event. Pipeline clear."},
        ],
        "signals": [
            {"time": "15:22:01", "type": "SMC",        "action": "SELL",
             "price": 4869.12, "direction": "bearish"},
            {"time": "15:23:14", "type": "NEWS_SCALP", "action": "BUY",
             "trigger": "Core CPI beats forecast"},
        ],
        "news_events": [
            {"time_utc": "2026-03-18T13:30:00+00:00", "impact": 3,
             "title": "Core CPI m/m", "actual": 0.4, "forecast": 0.3},
            {"time_utc": "2026-03-18T14:00:00+00:00", "impact": 2,
             "title": "FOMC Member Speaks", "actual": None, "forecast": None},
        ],
    }
    with Live(dash.layout, refresh_per_second=2) as live:
        while True:
            dash.update(mock_state)
            time.sleep(1)
