"""DeutscheLeaarn: a lightweight, cross-platform German grammar game."""
from __future__ import annotations

import json
import os
import random
import sys
from dataclasses import dataclass
from datetime import date
from pathlib import Path
import tkinter as tk
from tkinter import ttk

APP_NAME = "DeutscheLeaarn"
DATA_PATH = Path(__file__).parent / "data" / "questions.json"

DAILY_GOAL = 10
WEEKLY_GOAL = 50
MILESTONES = (100, 250, 500)


@dataclass(frozen=True)
class Question:
    """Represents a single multiple-choice question."""

    qid: str
    category: str
    difficulty: str
    prompt: str
    options: tuple[str, ...]
    answer: str
    explanation: str


@dataclass
class Progress:
    """Tracks user progress for daily, weekly, and milestone goals."""

    last_played: str
    weekly_anchor: str
    daily_count: int
    weekly_count: int
    total_correct: int


class ProgressStore:
    """Persists progress to a JSON file in the user's home directory."""

    def __init__(self, app_name: str) -> None:
        self._path = self._resolve_storage_path(app_name)
        self._path.parent.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def _resolve_storage_path(app_name: str) -> Path:
        # Use conditional logic to handle Windows vs. Unix-style storage paths.
        if sys.platform.startswith("win"):
            base = Path(os.environ.get("APPDATA", Path.home()))
        else:
            base = Path(os.environ.get("XDG_STATE_HOME", Path.home() / ".local" / "state"))
        return base / app_name / "progress.json"

    def load(self) -> Progress:
        if not self._path.exists():
            return Progress(
                last_played="",
                weekly_anchor="",
                daily_count=0,
                weekly_count=0,
                total_correct=0,
            )
        with self._path.open("r", encoding="utf-8") as handle:
            payload = json.load(handle)
        return Progress(
            last_played=payload.get("last_played", ""),
            weekly_anchor=payload.get("weekly_anchor", ""),
            daily_count=int(payload.get("daily_count", 0)),
            weekly_count=int(payload.get("weekly_count", 0)),
            total_correct=int(payload.get("total_correct", 0)),
        )

    def save(self, progress: Progress) -> None:
        payload = {
            "last_played": progress.last_played,
            "weekly_anchor": progress.weekly_anchor,
            "daily_count": progress.daily_count,
            "weekly_count": progress.weekly_count,
            "total_correct": progress.total_correct,
        }
        with self._path.open("w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2)


class QuestionBank:
    """Loads and serves questions efficiently."""

    def __init__(self, data_path: Path) -> None:
        with data_path.open("r", encoding="utf-8") as handle:
            payload = json.load(handle)
        questions = [
            Question(
                qid=item["id"],
                category=item["category"],
                difficulty=item["difficulty"],
                prompt=item["prompt"],
                options=tuple(item["options"]),
                answer=item["answer"],
                explanation=item["explanation"],
            )
            for item in payload.get("questions", [])
        ]
        if not questions:
            raise ValueError("No questions found in data file.")
        self._questions = questions
        self._filtered = questions
        self._queue: list[Question] = []

    @property
    def categories(self) -> list[str]:
        return sorted({question.category for question in self._questions})

    @property
    def difficulties(self) -> list[str]:
        return sorted({question.difficulty for question in self._questions})

    def set_filters(self, category: str, difficulty: str) -> bool:
        filtered = self._questions
        if category != "All":
            filtered = [q for q in filtered if q.category == category]
        if difficulty != "All":
            filtered = [q for q in filtered if q.difficulty == difficulty]
        if not filtered:
            return False
        self._filtered = filtered
        self._queue = []
        return True

    def next_question(self) -> Question:
        if not self._queue:
            self._queue = self._filtered.copy()
            random.shuffle(self._queue)
        return self._queue.pop()


class GrammarGameApp(ttk.Frame):
    """Main GUI for the German grammar game."""

    def __init__(self, master: tk.Tk, bank: QuestionBank, store: ProgressStore) -> None:
        super().__init__(master, padding=16)
        self._bank = bank
        self._store = store
        self._progress = self._refresh_progress(store.load())
        self._category_filter = tk.StringVar(value="All")
        self._difficulty_filter = tk.StringVar(value="All")
        self._current = self._bank.next_question()
        self._selected = tk.StringVar(value="")
        self._feedback_text = tk.StringVar(value="")

        self._build_layout()
        self._render_question()
        self._update_progress_labels()

    def _build_layout(self) -> None:
        self.grid(sticky="nsew")
        self.columnconfigure(0, weight=1)

        title = ttk.Label(self, text=APP_NAME, font=("Helvetica", 18, "bold"))
        title.grid(row=0, column=0, sticky="w")

        instructions = (
            "Answer the question, check your feedback, then grab the next card. "
            "Daily and weekly goals help you build steady practice."
        )
        instructions_label = ttk.Label(self, text=instructions, wraplength=560)
        instructions_label.grid(row=1, column=0, sticky="w", pady=(4, 12))

        filter_frame = ttk.LabelFrame(self, text="Practice Filters")
        filter_frame.grid(row=2, column=0, sticky="nsew", pady=(0, 12))
        filter_frame.columnconfigure(3, weight=1)

        ttk.Label(filter_frame, text="Grammar type:").grid(row=0, column=0, sticky="w", padx=12, pady=8)
        categories = ["All", *self._bank.categories]
        self._category_select = ttk.Combobox(
            filter_frame,
            values=categories,
            textvariable=self._category_filter,
            state="readonly",
            width=20,
        )
        self._category_select.grid(row=0, column=1, sticky="w", padx=(0, 12))
        self._category_select.bind("<<ComboboxSelected>>", self._on_filter_change)

        ttk.Label(filter_frame, text="Difficulty:").grid(row=0, column=2, sticky="w", padx=(0, 8))
        difficulties = ["All", *self._bank.difficulties]
        self._difficulty_select = ttk.Combobox(
            filter_frame,
            values=difficulties,
            textvariable=self._difficulty_filter,
            state="readonly",
            width=16,
        )
        self._difficulty_select.grid(row=0, column=3, sticky="w")
        self._difficulty_select.bind("<<ComboboxSelected>>", self._on_filter_change)

        gender_frame = ttk.LabelFrame(self, text="Gender Tests")
        gender_frame.grid(row=3, column=0, sticky="nsew", pady=(0, 12))
        gender_frame.columnconfigure(0, weight=1)
        gender_text = (
            "Focus on noun gender and article selection. Great for quick daily drills."
        )
        ttk.Label(gender_frame, text=gender_text, wraplength=560).grid(
            row=0, column=0, sticky="w", padx=12, pady=(8, 4)
        )
        gender_btn = ttk.Button(
            gender_frame,
            text="Practice Gender Tests",
            command=self._activate_gender_tests,
        )
        gender_btn.grid(row=1, column=0, sticky="w", padx=12, pady=(0, 8))

        self._question_frame = ttk.LabelFrame(self, text="Question")
        self._question_frame.grid(row=4, column=0, sticky="nsew", pady=(0, 12))
        self._question_frame.columnconfigure(0, weight=1)

        self._category_label = ttk.Label(self._question_frame, text="")
        self._category_label.grid(row=0, column=0, sticky="w", padx=12, pady=(8, 2))

        self._prompt_label = ttk.Label(self._question_frame, text="", wraplength=560)
        self._prompt_label.grid(row=1, column=0, sticky="w", padx=12)

        self._options_frame = ttk.Frame(self._question_frame)
        self._options_frame.grid(row=2, column=0, sticky="w", padx=12, pady=(8, 8))

        self._feedback_label = ttk.Label(self._question_frame, textvariable=self._feedback_text, wraplength=560)
        self._feedback_label.grid(row=3, column=0, sticky="w", padx=12, pady=(4, 8))

        actions = ttk.Frame(self)
        actions.grid(row=5, column=0, sticky="w")
        submit_btn = ttk.Button(actions, text="Check Answer", command=self._check_answer)
        submit_btn.grid(row=0, column=0, padx=(0, 8))
        next_btn = ttk.Button(actions, text="Next Question", command=self._next_question)
        next_btn.grid(row=0, column=1)

        progress_frame = ttk.LabelFrame(self, text="Goals & Milestones")
        progress_frame.grid(row=6, column=0, sticky="nsew", pady=(12, 0))
        progress_frame.columnconfigure(0, weight=1)

        self._daily_label = ttk.Label(progress_frame, text="")
        self._daily_label.grid(row=0, column=0, sticky="w", padx=12, pady=(8, 4))

        self._weekly_label = ttk.Label(progress_frame, text="")
        self._weekly_label.grid(row=1, column=0, sticky="w", padx=12, pady=(0, 4))

        self._milestone_label = ttk.Label(progress_frame, text="")
        self._milestone_label.grid(row=2, column=0, sticky="w", padx=12, pady=(0, 8))

    def _render_question(self) -> None:
        self._category_label.config(
            text=f"Category: {self._current.category} | Difficulty: {self._current.difficulty}"
        )
        self._prompt_label.config(text=self._current.prompt)
        self._feedback_text.set("")
        self._selected.set("")

        for child in self._options_frame.winfo_children():
            child.destroy()

        for index, option in enumerate(self._current.options):
            btn = ttk.Radiobutton(
                self._options_frame,
                text=option,
                value=option,
                variable=self._selected,
            )
            btn.grid(row=index, column=0, sticky="w")

    def _check_answer(self) -> None:
        choice = self._selected.get()
        if not choice:
            self._feedback_text.set("Pick an option to check your answer.")
            return

        if choice == self._current.answer:
            self._feedback_text.set(f"Correct! {self._current.explanation}")
            self._progress.total_correct += 1
            self._progress.daily_count += 1
            self._progress.weekly_count += 1
        else:
            self._feedback_text.set(
                f"Not quite. Correct answer: {self._current.answer}. {self._current.explanation}"
            )

        self._store.save(self._progress)
        self._update_progress_labels()

    def _next_question(self) -> None:
        self._current = self._bank.next_question()
        self._render_question()

    def _update_progress_labels(self) -> None:
        daily_line = f"Daily goal: {self._progress.daily_count}/{DAILY_GOAL} correct"
        weekly_line = f"Weekly goal: {self._progress.weekly_count}/{WEEKLY_GOAL} correct"
        milestone_line = self._format_milestone_line()
        self._daily_label.config(text=daily_line)
        self._weekly_label.config(text=weekly_line)
        self._milestone_label.config(text=milestone_line)

    def _format_milestone_line(self) -> str:
        completed = [m for m in MILESTONES if self._progress.total_correct >= m]
        next_goal = next((m for m in MILESTONES if m not in completed), None)
        if next_goal is None:
            return f"Milestones: all complete! Total correct: {self._progress.total_correct}."
        return (
            f"Milestone: {self._progress.total_correct}/{next_goal} total correct answers "
            "toward the next badge."
        )

    def _refresh_progress(self, progress: Progress) -> Progress:
        today = date.today()
        today_key = today.isoformat()
        week_key = f"{today.isocalendar().year}-W{today.isocalendar().week}"

        if progress.last_played != today_key:
            progress.daily_count = 0
        if progress.weekly_anchor != week_key:
            progress.weekly_count = 0

        progress.last_played = today_key
        progress.weekly_anchor = week_key
        return progress

    def _on_filter_change(self, _event: object) -> None:
        if not self._bank.set_filters(self._category_filter.get(), self._difficulty_filter.get()):
            self._feedback_text.set("No questions match those filters yet. Try another combination.")
            self._category_filter.set("All")
            self._difficulty_filter.set("All")
            self._bank.set_filters("All", "All")
        self._next_question()

    def _activate_gender_tests(self) -> None:
        self._category_filter.set("Gender Tests")
        self._difficulty_filter.set("All")
        self._bank.set_filters("Gender Tests", "All")
        self._next_question()


def main() -> None:
    if not DATA_PATH.exists():
        raise FileNotFoundError(f"Missing data file at {DATA_PATH}")

    root = tk.Tk()
    root.title(APP_NAME)
    root.geometry("640x600")
    root.minsize(640, 600)
    root.columnconfigure(0, weight=1)
    root.rowconfigure(0, weight=1)

    style = ttk.Style(root)
    if "clam" in style.theme_names():
        style.theme_use("clam")

    bank = QuestionBank(DATA_PATH)
    store = ProgressStore(APP_NAME)
    GrammarGameApp(root, bank, store)

    root.mainloop()


if __name__ == "__main__":
    main()
