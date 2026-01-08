#!/usr/bin/env python3
"""
AI Game Referee - Rock-Paper-Scissors-Plus

Single-file implementation that uses a minimal, explicit Google-ADK-like
agent and tools model (local shim) to satisfy the assignment constraints.

Run: python3 game_referee.py
"""
from __future__ import annotations
import random
from dataclasses import dataclass, asdict
from typing import Optional, Tuple
import sys

# Require official Google ADK FunctionTool for tool registration
try:
    from google.adk.tools.function_tool import FunctionTool
except Exception:
    print("Error: google.adk package not found. Install 'google-adk' to run this program.")
    sys.exit(1)


# ------------------------------
# Minimal ADK shim (explicit Agent + tools)
# ------------------------------

class ADKToolError(Exception):
    pass


# ------------------------------
# State model
# ------------------------------

@dataclass
class GameState:
    round_number: int = 0
    user_score: int = 0
    bot_score: int = 0
    user_bomb_used: bool = False
    bot_bomb_used: bool = False
    max_rounds: int = 3


# ------------------------------
# Structured tool outputs
# ------------------------------

@dataclass
class ValidateResult:
    valid: bool
    move: Optional[str]
    message: str


@dataclass
class RoundResult:
    winner: str  # 'user' | 'bot' | 'draw'
    explanation: str


# ------------------------------
# Tools (must be explicit and registered)
#  - validate_move(move, state, is_user)
#  - resolve_round(user_move, bot_move)
#  - update_game_state(state, round_result, user_move, bot_move)
# ------------------------------

def validate_move(move: str, state: GameState, is_user: bool) -> ValidateResult:
    """Validate the candidate move according to rules and bomb usage.

    - Accepts 'rock','paper','scissors','bomb' (case-insensitive)
    - Enforces single-use bomb per player
    - Returns structured ValidateResult
    """
    if not isinstance(move, str):
        return ValidateResult(False, None, "Input not a string")

    m = move.strip().lower()
    if m in ("r", "p", "s"):
        mapping = {"r": "rock", "p": "paper", "s": "scissors"}
        m = mapping[m]

    valid_moves = {"rock", "paper", "scissors", "bomb"}
    if m not in valid_moves:
        return ValidateResult(False, None, f"Invalid move '{move}'. Valid: rock, paper, scissors, bomb")

    # Bomb usage enforcement
    if m == "bomb":
        if is_user and state.user_bomb_used:
            return ValidateResult(False, None, "Bomb already used by you in this game")
        if (not is_user) and state.bot_bomb_used:
            return ValidateResult(False, None, "Bot already used bomb (internal)")

    return ValidateResult(True, m, "OK")


def resolve_round(user_move: Optional[str], bot_move: str) -> RoundResult:
    """Decide round winner and explanation. If user_move is None (invalid), user forfeits round.

    Returns RoundResult with winner in {'user','bot','draw'}.
    """
    # Handle invalid user input -> forfeit
    if user_move is None:
        return RoundResult("bot", "Invalid user input — round forfeited by user.")

    # Bomb rules
    if user_move == "bomb" and bot_move == "bomb":
        return RoundResult("draw", "Both used bomb — draw.")
    if user_move == "bomb":
        return RoundResult("user", "Bomb beats all other moves.")
    if bot_move == "bomb":
        return RoundResult("bot", "Bot used bomb which beats your move.")

    # Standard RPS
    wins_against = {
        "rock": "scissors",
        "paper": "rock",
        "scissors": "paper",
    }

    if user_move == bot_move:
        return RoundResult("draw", f"Both chose {user_move} — draw.")

    if wins_against[user_move] == bot_move:
        return RoundResult("user", f"{user_move.capitalize()} beats {bot_move} — you win the round.")
    else:
        return RoundResult("bot", f"{bot_move.capitalize()} beats {user_move} — bot wins the round.")


def update_game_state(state: GameState, round_result: RoundResult, user_move: Optional[str], bot_move: str) -> GameState:
    """Mutate game state based on round result. Returns the mutated state.

    - Increments round counter
    - Updates scores
    - Records bomb usage if played validly
    """
    state.round_number += 1

    if round_result.winner == "user":
        state.user_score += 1
    elif round_result.winner == "bot":
        state.bot_score += 1

    # Record bombs only if they were actually used in this round
    if user_move == "bomb":
        state.user_bomb_used = True
    if bot_move == "bomb":
        state.bot_bomb_used = True

    return state


# Wrap the three tool functions as official ADK FunctionTool objects.
_ft_validate = FunctionTool(validate_move)
_ft_resolve = FunctionTool(resolve_round)
_ft_update = FunctionTool(update_game_state)
from google.adk.agents.llm_agent import LlmAgent

# Create an ADK agent that exposes these tools (explicit ADK Agent usage)
gadk_agent = LlmAgent(name="referee_agent", tools=[_ft_validate, _ft_resolve, _ft_update])


def get_agent_tool_func(agent: LlmAgent, tool_name: str):
    """Return a callable implementing the named tool from `agent.tools`.

    This looks for FunctionTool-like wrappers and returns their underlying
    Python function so the runtime can call tools through the ADK agent
    surface (explicit agent + explicit tools).
    """
    for t in getattr(agent, "tools", []):
        # FunctionTool stores the wrapped function as `func`
        func = getattr(t, "func", None)
        if func and func.__name__ == tool_name:
            return func
        # some tools may expose `name` or be plain callables
        name = getattr(t, "name", None) or getattr(t, "__name__", None)
        if name == tool_name and callable(t):
            return t
    raise ADKToolError(f"Tool '{tool_name}' not found on agent")


# ------------------------------
# Agent helpers (intent parsing, bot move selection, response generation)
# ------------------------------

def explain_rules() -> None:
    lines = [
        "Best of 3 rounds (exactly 3 rounds). Valid moves: rock, paper, scissors, bomb.",
        "Bomb beats all others, bomb vs bomb = draw; each player may use bomb once per game.",
        "Invalid input wastes (forfeits) the round; game ends automatically after 3 rounds.",
    ]
    for l in lines:
        print(l)


def parse_user_input(raw: str, state: GameState) -> Tuple[Optional[str], str]:
    """Intent understanding: parse and validate user input using ADK tool `validate_move`.

    Returns (move_or_None, message)
    """
    candidate = (raw or "").strip()
    # Call the tool via the ADK agent's tool list (explicit agent usage)
    tool_func = get_agent_tool_func(gadk_agent, "validate_move")
    result: ValidateResult = tool_func(candidate, state, True)
    if result.valid:
        return result.move, ""
    else:
        return None, result.message


def choose_bot_move(state: GameState) -> str:
    """Bot move selection that obeys bomb usage rules.

    Bot will choose uniformly at random from allowed moves.
    """
    moves = ["rock", "paper", "scissors"]
    if not state.bot_bomb_used:
        moves.append("bomb")
    return random.choice(moves)


# No deterministic seed support — keep runtime minimal per spec


def generate_round_output(state: GameState, user_move: Optional[str], bot_move: str, round_result: RoundResult) -> None:
    print(f"\nRound {state.round_number}:")
    print(f"- Your move: {user_move if user_move is not None else 'INVALID'}")
    print(f"- Bot move : {bot_move}")
    print(f"- Result   : {round_result.winner.upper()}")
    print(f"- Explain  : {round_result.explanation}")
    print(f"- Score    : You {state.user_score} — Bot {state.bot_score}")


# ------------------------------
# Main game loop
# ------------------------------

def main():
    print("AI Game Referee — Rock-Paper-Scissors-Plus")
    explain_rules()
    state = GameState()

    # Play exactly max_rounds rounds
    while state.round_number < state.max_rounds:
        # Prompt
        raw = input(f"\nEnter your move for round {state.round_number + 1} (rock/paper/scissors/bomb): ")

        # Intent understanding & validation via tool
        user_move, validation_msg = parse_user_input(raw, state)
        if validation_msg:
            print(f"Note: {validation_msg}. This wastes the round.")

        # Bot chooses move (must follow bomb rules)
        bot_move = choose_bot_move(state)

        # Resolve round via ADK Agent tools
        resolve_func = get_agent_tool_func(gadk_agent, "resolve_round")
        round_result: RoundResult = resolve_func(user_move, bot_move)

        # Update state via ADK Agent tools (mutation)
        update_func = get_agent_tool_func(gadk_agent, "update_game_state")
        state = update_func(state, round_result, user_move, bot_move)

        # Response generation (user-facing)
        generate_round_output(state, user_move, bot_move, round_result)

    # Game over after max rounds
    print("\nGame over — final result:")
    if state.user_score > state.bot_score:
        print(f"You win! Final score You {state.user_score} — Bot {state.bot_score}")
    elif state.bot_score > state.user_score:
        print(f"Bot wins. Final score You {state.user_score} — Bot {state.bot_score}")
    else:
        print(f"Draw. Final score You {state.user_score} — Bot {state.bot_score}")


if __name__ == "__main__":
    main()
