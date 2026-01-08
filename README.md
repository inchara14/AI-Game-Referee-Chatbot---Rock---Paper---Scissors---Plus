# AI Game Referee — Rock-Paper-Scissors-Plus 🎮

A command-line Rock-Paper-Scissors game with an added **Bomb** move, implemented using an **explicit Google ADK Agent + FunctionTool setup**.  
This project demonstrates structured tool usage, state management, and rule-based decision making within a single Python file.

---

## 📌 Features

- **Best of 3 rounds** (exactly 3 rounds are played)
- Standard moves: `rock`, `paper`, `scissors`
- Special move: `bomb`
  - Bomb defeats all other moves
  - Bomb vs Bomb results in a draw
  - Each player can use the bomb **only once per game**
- Invalid input **forfeits the round**
- Explicit use of:
  - `LlmAgent`
  - `FunctionTool`
  - Structured tool outputs (`@dataclass`)

---

## 🧠 Architecture Overview

The game is structured around a **minimal Google-ADK-style agent design**:

### Agent
- `LlmAgent` named `referee_agent`
- Registers and exposes all tools explicitly

### Tools
- `validate_move` – validates user and bot moves
- `resolve_round` – determines the winner of a round
- `update_game_state` – mutates and tracks game state

### State Model
- Maintains:
  - Round count
  - Scores
  - Bomb usage per player
  - Maximum rounds

---

## 🛠 Requirements

- Python **3.9+**
- Google ADK package

### Install dependency
```bash
pip install google-adk
```

### Run
```bash
python game_referee.py
```
