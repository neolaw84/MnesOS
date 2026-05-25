/**
 * ArticulationScramble — a word-ordering persuasion/spell-casting mini-game.
 *
 * Mechanics
 * ---------
 * - The player is shown a randomized grid of word buttons.
 * - They must select words in the correct sequence to form the right sentence.
 * - Includes confuse_words that serve as distractors.
 * - Optional countdown timer via max_time_seconds.
 *
 * Config (from `_pending_interaction.config`)
 * -------------------------------------------
 * difficulty.prompt             — The prompt/instruction text shown to the player
 * difficulty.prefix             — Text prefix shown before the selected words
 * difficulty.correct_sequence   — Array of words in the correct order
 * difficulty.confuse_words      — Array of distractor words
 * difficulty.max_time_seconds   — Optional countdown (auto-submits when expired)
 */

import { useCallback, useEffect, useRef, useState } from "react";
import type { MinigameComponentProps } from "../registry";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/** Shuffle an array using Fisher-Yates. */
function shuffle<T>(arr: T[]): T[] {
  const copy = [...arr];
  for (let i = copy.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1));
    [copy[i], copy[j]] = [copy[j], copy[i]];
  }
  return copy;
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export default function ArticulationScramble({ config, onComplete }: MinigameComponentProps) {
  const difficulty = (config.difficulty ?? {}) as Record<string, unknown>;

  const prompt = (difficulty.prompt as string) ?? "";
  const prefix = (difficulty.prefix as string) ?? "";
  const correctSequence = (difficulty.correct_sequence as string[]) ?? [];
  const confuseWords = (difficulty.confuse_words as string[]) ?? [];
  const maxTimeSeconds = (difficulty.max_time_seconds as number | undefined) ?? null;

  const [allWords] = useState(() => shuffle([...correctSequence, ...confuseWords]));
  const [selectedWords, setSelectedWords] = useState<string[]>([]);
  const [finished, setFinished] = useState(false);
  const startTimeRef = useRef(Date.now());
  const onCompleteRef = useRef(onComplete);
  onCompleteRef.current = onComplete;

  // Timer logic
  useEffect(() => {
    if (maxTimeSeconds == null || finished) return;

    const timer = setTimeout(() => {
      if (!finished) {
        setFinished(true);
        const timeSpent = (Date.now() - startTimeRef.current) / 1000;
        onCompleteRef.current({
          status: "failed",
          metrics: {
            success: false,
            selected_sequence: selectedWords,
            time_spent_seconds: timeSpent,
          },
          minigame_specific_data: { selected_sequence: selectedWords },
        });
      }
    }, maxTimeSeconds * 1000);

    return () => clearTimeout(timer);
  }, [maxTimeSeconds, finished, selectedWords]);

  const handleWordClick = useCallback(
    (word: string) => {
      if (finished) return;
      setSelectedWords((prev) => [...prev, word]);
    },
    [finished],
  );

  const handleDeselectWord = useCallback(
    (index: number) => {
      if (finished) return;
      setSelectedWords((prev) => prev.filter((_, i) => i !== index));
    },
    [finished],
  );

  const handleSubmit = useCallback(() => {
    if (finished) return;
    setFinished(true);

    const timeSpent = (Date.now() - startTimeRef.current) / 1000;
    const isCorrect =
      selectedWords.length === correctSequence.length &&
      selectedWords.every((w, i) => w === correctSequence[i]);

    onCompleteRef.current({
      status: isCorrect ? "completed" : "failed",
      metrics: {
        success: isCorrect,
        selected_sequence: selectedWords,
        time_spent_seconds: timeSpent,
      },
      minigame_specific_data: { selected_sequence: selectedWords },
    });
  }, [finished, selectedWords, correctSequence]);

  return (
    <div className="articulation-scramble-wrapper">
      <div className="articulation-scramble-prompt">
        <p>{prompt}</p>
      </div>

      {prefix && (
        <div className="articulation-scramble-prefix">
          <em>{prefix}</em>
        </div>
      )}

      <div className="articulation-scramble-selected" data-testid="selected-words">
        {selectedWords.map((word, idx) => (
          <button
            key={`${word}-${idx}`}
            className="articulation-scramble-selected-word"
            data-testid={`selected-word-${idx}`}
            onClick={() => handleDeselectWord(idx)}
            disabled={finished}
          >
            {word}
          </button>
        ))}
      </div>

      <div className="articulation-scramble-grid">
        {allWords.map((word) => (
          <button
            key={word}
            className="articulation-scramble-word-btn"
            aria-label={word}
            onClick={() => handleWordClick(word)}
            disabled={finished || selectedWords.includes(word)}
          >
            {word}
          </button>
        ))}
      </div>

      {!finished && (
        <div className="articulation-scramble-footer">
          <button
            className="btn btn-primary"
            onClick={handleSubmit}
          >
            End Response
          </button>
        </div>
      )}
    </div>
  );
}
