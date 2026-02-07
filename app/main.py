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
from tkinter import messagebox, ttk

APP_NAME = "DeutscheLeaarn"
DATA_PATH = Path(__file__).parent / "data" / "questions.json"

DAILY_GOAL = 10
WEEKLY_GOAL = 50
MILESTONES = (100, 250, 500)
GROUP_SIZE = 10


@dataclass(frozen=True)
class Question:
    """Represents a single question."""

    qid: str
    category: str
    difficulty: str
    complexity: str
    qtype: str
    prompt: str
    german_text: str
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
                complexity=item["complexity"],
                qtype=item["type"],
                prompt=item["prompt"],
                german_text=item["german_text"],
                options=tuple(item.get("options", [])),
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
        self._group_index = 0

    @property
    def categories(self) -> list[str]:
        return sorted({question.category for question in self._questions})

    @property
    def difficulties(self) -> list[str]:
        return sorted({question.difficulty for question in self._questions})

    @property
    def complexities(self) -> list[str]:
        return sorted({question.complexity for question in self._questions})

    def set_filters(self, category: str, difficulty: str, complexity: str) -> bool:
        filtered = self._questions
        if category != "All":
            filtered = [q for q in filtered if q.category == category]
        if difficulty != "All":
            filtered = [q for q in filtered if q.difficulty == difficulty]
        if complexity != "All":
            filtered = [q for q in filtered if q.complexity == complexity]
        if not filtered:
            return False
        self._filtered = filtered
        self._queue = []
        self._group_index = 0
        return True

    def _build_group(self) -> None:
        shuffled = self._filtered.copy()
        random.shuffle(shuffled)
        start = self._group_index * GROUP_SIZE
        group = shuffled[start : start + GROUP_SIZE]
        if not group:
            self._group_index = 0
            start = 0
            group = shuffled[start : start + GROUP_SIZE]
        self._queue = list(reversed(group))

    def next_question(self) -> Question:
        if not self._queue:
            self._build_group()
        return self._queue.pop()

    def advance_group(self) -> None:
        self._group_index += 1
        self._queue = []

    def group_label(self) -> str:
        total_groups = max(1, (len(self._filtered) + GROUP_SIZE - 1) // GROUP_SIZE)
        return f"Group {self._group_index + 1} of {total_groups}"

    def group_remaining(self) -> int:
        return len(self._queue)


class GrammarGameApp(ttk.Frame):
    """Main GUI for the German grammar game."""

    def __init__(self, master: tk.Tk, bank: QuestionBank, store: ProgressStore) -> None:
        super().__init__(master, padding=16)
        self._bank = bank
        self._store = store
        self._progress = self._refresh_progress(store.load())
        self._category_filter = tk.StringVar(value="All")
        self._difficulty_filter = tk.StringVar(value="All")
        self._complexity_filter = tk.StringVar(value="All")
        self._current = self._bank.next_question()
        self._history: list[Question] = []
        self._selected = tk.StringVar(value="")
        self._text_answer = tk.StringVar(value="")
        self._feedback_text = tk.StringVar(value="")
        self._group_label = tk.StringVar(value="")

        self._build_layout()
        self._render_question()
        self._update_progress_labels()

    def _build_layout(self) -> None:
        self.grid(sticky="nsew")
        self.columnconfigure(0, weight=1)

        title = ttk.Label(self, text=APP_NAME, font=("Helvetica", 18, "bold"))
        title.grid(row=0, column=0, sticky="w")

        instructions = (
            "Choose a section and level, answer the questions, then move through each group of 10. "
            "Use 'Hear German' to listen to the prompt when available."
        )
        instructions_label = ttk.Label(self, text=instructions, wraplength=600)
        instructions_label.grid(row=1, column=0, sticky="w", pady=(4, 12))

        filter_frame = ttk.LabelFrame(self, text="Practice Filters")
        filter_frame.grid(row=2, column=0, sticky="nsew", pady=(0, 12))
        filter_frame.columnconfigure(5, weight=1)

        ttk.Label(filter_frame, text="Section:").grid(row=0, column=0, sticky="w", padx=12, pady=8)
        categories = ["All", *self._bank.categories]
        self._category_select = ttk.Combobox(
            filter_frame,
            values=categories,
            textvariable=self._category_filter,
            state="readonly",
            width=18,
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
            width=10,
        )
        self._difficulty_select.grid(row=0, column=3, sticky="w", padx=(0, 12))
        self._difficulty_select.bind("<<ComboboxSelected>>", self._on_filter_change)

        ttk.Label(filter_frame, text="Complexity:").grid(row=0, column=4, sticky="w", padx=(0, 8))
        complexities = ["All", *self._bank.complexities]
        self._complexity_select = ttk.Combobox(
            filter_frame,
            values=complexities,
            textvariable=self._complexity_filter,
            state="readonly",
            width=10,
        )
        self._complexity_select.grid(row=0, column=5, sticky="w")
        self._complexity_select.bind("<<ComboboxSelected>>", self._on_filter_change)

        self._question_frame = ttk.LabelFrame(self, text="Question")
        self._question_frame.grid(row=3, column=0, sticky="nsew", pady=(0, 12))
        self._question_frame.columnconfigure(0, weight=1)

        self._meta_label = ttk.Label(self._question_frame, text="")
        self._meta_label.grid(row=0, column=0, sticky="w", padx=12, pady=(8, 2))

        self._prompt_label = ttk.Label(self._question_frame, text="", wraplength=600)
        self._prompt_label.grid(row=1, column=0, sticky="w", padx=12)

        self._options_frame = ttk.Frame(self._question_frame)
        self._options_frame.grid(row=2, column=0, sticky="w", padx=12, pady=(8, 8))

        self._entry_frame = ttk.Frame(self._question_frame)
        self._entry_frame.grid(row=3, column=0, sticky="w", padx=12, pady=(0, 8))

        self._feedback_label = ttk.Label(self._question_frame, textvariable=self._feedback_text, wraplength=600)
        self._feedback_label.grid(row=4, column=0, sticky="w", padx=12, pady=(4, 8))

        actions = ttk.Frame(self)
        actions.grid(row=4, column=0, sticky="w")
        submit_btn = ttk.Button(actions, text="Check Answer", command=self._check_answer)
        submit_btn.grid(row=0, column=0, padx=(0, 8))
        back_btn = ttk.Button(actions, text="Back", command=self._go_back)
        back_btn.grid(row=0, column=1, padx=(0, 8))
        next_btn = ttk.Button(actions, text="Next Question", command=self._next_question)
        next_btn.grid(row=0, column=2, padx=(0, 8))
        group_btn = ttk.Button(actions, text="Next Group", command=self._next_group)
        group_btn.grid(row=0, column=3)

        audio_btn = ttk.Button(actions, text="Hear German", command=self._speak_german)
        audio_btn.grid(row=0, column=4, padx=(8, 0))

        self._group_status = ttk.Label(self, textvariable=self._group_label)
        self._group_status.grid(row=5, column=0, sticky="w", pady=(8, 0))

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
        self._meta_label.config(
            text=(
                f"Section: {self._current.category} | "
                f"Difficulty: {self._current.difficulty} | "
                f"Complexity: {self._current.complexity}"
            )
        )
        self._prompt_label.config(text=self._current.prompt)
        self._feedback_text.set("")
        self._selected.set("")
        self._text_answer.set("")

        for child in self._options_frame.winfo_children():
            child.destroy()
        for child in self._entry_frame.winfo_children():
            child.destroy()

        if self._current.qtype == "multiple_choice":
            for index, option in enumerate(self._current.options):
                btn = ttk.Radiobutton(
                    self._options_frame,
                    text=option,
                    value=option,
                    variable=self._selected,
                )
                btn.grid(row=index, column=0, sticky="w")
        else:
            if self._current.qtype == "word_order":
                words = " ".join(self._current.options)
                ttk.Label(self._entry_frame, text=f"Words: {words}").grid(row=0, column=0, sticky="w")
            entry = ttk.Entry(self._entry_frame, textvariable=self._text_answer, width=60)
            entry.grid(row=1, column=0, sticky="w", pady=(4, 0))
            entry.focus_set()

        remaining = self._bank.group_remaining()
        self._group_label.set(f"{self._bank.group_label()} | Questions left in group: {remaining}")

    def _check_answer(self) -> None:
        if self._current.qtype == "multiple_choice":
            choice = self._selected.get()
            if not choice:
                self._feedback_text.set("Pick an option to check your answer.")
                return
            is_correct = choice == self._current.answer
            response = choice
        else:
            response = self._text_answer.get().strip()
            if not response:
                self._feedback_text.set("Type your answer to check it.")
                return
            is_correct = response.casefold() == self._current.answer.casefold()

        if is_correct:
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
        self._history.append(self._current)
        self._current = self._bank.next_question()
        self._render_question()

    def _go_back(self) -> None:
        if not self._history:
            self._feedback_text.set("You're at the first question in this flow.")
            return
        self._current = self._history.pop()
        self._render_question()

    def _next_group(self) -> None:
        self._bank.advance_group()
        self._history.clear()
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
        if not self._bank.set_filters(
            self._category_filter.get(),
            self._difficulty_filter.get(),
            self._complexity_filter.get(),
        ):
            self._feedback_text.set("No questions match those filters yet. Try another combination.")
            self._category_filter.set("All")
            self._difficulty_filter.set("All")
            self._complexity_filter.set("All")
            self._bank.set_filters("All", "All", "All")
        self._history.clear()
        self._current = self._bank.next_question()
        self._render_question()

    def _speak_german(self) -> None:
        try:
            import pyttsx3
        except ImportError:
            messagebox.showinfo(
                "Audio unavailable",
                "Install the optional 'pyttsx3' package to enable speech output.",
            )
            return

        engine = pyttsx3.init()
        engine.say(self._current.german_text)
        engine.runAndWait()


def main() -> None:
    if not DATA_PATH.exists():
        raise FileNotFoundError(f"Missing data file at {DATA_PATH}")

    root = tk.Tk()
    root.title(APP_NAME)
    root.geometry("720x680")
    root.minsize(720, 680)
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
