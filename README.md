# DeutscheLeaarn

DeutscheLeaarn is a lightweight, cross-platform desktop game for practicing
German grammar with short multiple-choice questions. It is designed for English
learners and runs on both Linux (Ubuntu) and Windows 10.

## Features

- Simple, intuitive GUI built with Tkinter.
- Mouse-selectable filters for grammar types and difficulty levels.
- A dedicated gender-test practice section.
- Daily and weekly goals to encourage steady practice.
- Long-term milestones to track overall progress.
- Open-data starter question set with room to expand.

## Requirements

- Python 3.10+
- Tkinter (usually bundled with standard Python installs on Linux and Windows)

## Run the game

```bash
python app/main.py
```

## Source code layout

- Application code: `app/main.py`
- Question data: `app/data/questions.json`

## Data and attribution

The starter questions are built from public references and common introductory
German grammar rules. See `app/data/SOURCES.md` for details and links.

## Extending the question set

Add more questions to `app/data/questions.json` using the same schema:

```json
{
  "id": "unique-id",
  "category": "Category Name",
  "difficulty": "Beginner",
  "prompt": "Question prompt",
  "options": ["Option A", "Option B", "Option C"],
  "answer": "Option A",
  "explanation": "Short explanation"
}
```

## Local progress storage

Progress is saved in a JSON file on your machine:

- **Windows 10**: `%APPDATA%\\DeutscheLeaarn\\progress.json`
- **Linux (Ubuntu)**: `$XDG_STATE_HOME/DeutscheLeaarn/progress.json` or
  `~/.local/state/DeutscheLeaarn/progress.json`
