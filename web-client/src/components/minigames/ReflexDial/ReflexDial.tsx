/**
 * ReflexDial — a reflex-based QTE mini-game.
 *
 * Mechanics
 * ---------
 * - A needle rotates on a circular dial at `indicator_speed` rotations per second.
 * - Success zones are highlighted arcs on the dial.
 * - The player must click/tap (or press specific keys) when the needle is in the zone.
 * - The game ends when `required_success_hits` are achieved (win) or
 *   after too many total attempts (max_attempts = required_success_hits * 3) (lose).
 *
 * Config (from `_pending_interaction.config`)
 * -------------------------------------------
 * difficulty.indicator_speed       — Rotations per second
 * difficulty.zone_width_degrees    — Width of the success zone in degrees
 * difficulty.required_success_hits — Number of hits needed to win
 * difficulty.key_sequence          — Optional array of key names to press per hit
 */

import { useCallback, useEffect, useRef, useState } from "react";
import type { MinigameComponentProps } from "../registry";

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const TICK_MS = 16; // ~60fps update
const MAX_ATTEMPTS_MULTIPLIER = 3;

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export default function ReflexDial({ config, onComplete }: MinigameComponentProps) {
  const difficulty = (config.difficulty ?? {}) as Record<string, unknown>;

  const indicatorSpeed = (difficulty.indicator_speed as number) ?? 1;
  const zoneWidthDegrees = (difficulty.zone_width_degrees as number) ?? 40;
  const requiredSuccessHits = (difficulty.required_success_hits as number) ?? 3;
  const keySequence = (difficulty.key_sequence as string[] | undefined) ?? null;

  const maxAttempts = requiredSuccessHits * MAX_ATTEMPTS_MULTIPLIER;

  const [angle, setAngle] = useState(0);
  const [hits, setHits] = useState(0);
  const [misses, setMisses] = useState(0);
  const [attempts, setAttempts] = useState(0);
  const [finished, setFinished] = useState(false);
  const [zoneStart, setZoneStart] = useState(() => Math.random() * 360);
  const reactionTimesRef = useRef<number[]>([]);
  const lastZoneEntryRef = useRef<number | null>(null);
  const onCompleteRef = useRef(onComplete);
  onCompleteRef.current = onComplete;

  // Rotation animation
  useEffect(() => {
    if (finished) return;
    const interval = setInterval(() => {
      setAngle((prev) => {
        const next = (prev + (indicatorSpeed * 360 * TICK_MS) / 1000) % 360;
        // Track when needle enters the zone for reaction time measurement
        const inZone = isInZone(next, zoneStart, zoneWidthDegrees);
        const wasInZone = isInZone(prev, zoneStart, zoneWidthDegrees);
        if (inZone && !wasInZone) {
          lastZoneEntryRef.current = Date.now();
        }
        return next;
      });
    }, TICK_MS);
    return () => clearInterval(interval);
  }, [finished, indicatorSpeed, zoneStart, zoneWidthDegrees]);

  // Complete callback
  const completeGame = useCallback(
    (success: boolean, finalHits: number, finalMisses: number) => {
      if (finished) return;
      setFinished(true);
      const avgReaction =
        reactionTimesRef.current.length > 0
          ? reactionTimesRef.current.reduce((a, b) => a + b, 0) / reactionTimesRef.current.length
          : 0;
      onCompleteRef.current({
        status: success ? "completed" : "failed",
        metrics: {
          success,
          hits: finalHits,
          misses: finalMisses,
          avg_reaction_time_ms: Math.round(avgReaction),
        },
        minigame_specific_data: {
          hits: finalHits,
          misses: finalMisses,
          reaction_times: reactionTimesRef.current,
        },
      });
    },
    [finished],
  );

  const handleTap = useCallback(() => {
    if (finished) return;
    const inZone = isInZone(angle, zoneStart, zoneWidthDegrees);
    const newAttempts = attempts + 1;
    setAttempts(newAttempts);

    if (inZone) {
      const newHits = hits + 1;
      setHits(newHits);
      // Record reaction time
      if (lastZoneEntryRef.current !== null) {
        reactionTimesRef.current.push(Date.now() - lastZoneEntryRef.current);
      }
      // Move zone to new random position
      setZoneStart(Math.random() * 360);
      if (newHits >= requiredSuccessHits) {
        completeGame(true, newHits, misses);
      }
    } else {
      const newMisses = misses + 1;
      setMisses(newMisses);
      if (newAttempts >= maxAttempts) {
        completeGame(false, hits, newMisses);
      }
    }
  }, [finished, angle, zoneStart, zoneWidthDegrees, attempts, hits, misses, requiredSuccessHits, maxAttempts, completeGame]);

  // Key sequence handler
  useEffect(() => {
    if (!keySequence || finished) return;
    const currentKeyIndex = hits % keySequence.length;
    const expectedKey = keySequence[currentKeyIndex];

    const handler = (e: KeyboardEvent) => {
      if (e.key === expectedKey) {
        handleTap();
      }
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [keySequence, hits, finished, handleTap]);

  const handleAbort = useCallback(() => {
    if (finished) return;
    setFinished(true);
    onCompleteRef.current({
      status: "aborted",
      metrics: {
        success: false,
        hits,
        misses,
        avg_reaction_time_ms: 0,
      },
      minigame_specific_data: { hits, misses },
    });
  }, [finished, hits, misses]);

  // Compute dial styles
  const needleRotation = angle;
  const zoneStartAngle = zoneStart;
  const zoneEndAngle = (zoneStart + zoneWidthDegrees) % 360;

  return (
    <div className="reflex-dial-wrapper" data-testid="reflex-dial">
      <div className="reflex-dial-stats">
        <span>
          Hits: <strong data-testid="hit-counter">{hits}</strong> /{" "}
          <strong data-testid="hit-target">{requiredSuccessHits}</strong>
        </span>
        <span>Misses: <strong>{misses}</strong></span>
      </div>

      <div
        className="reflex-dial-face"
        data-testid="reflex-dial-tap-area"
        onClick={!keySequence ? handleTap : undefined}
        style={{ position: "relative", width: 200, height: 200, borderRadius: "50%", border: "2px solid #666" }}
      >
        {/* Success zone arc visualization */}
        <div
          className="reflex-dial-zone"
          style={{
            position: "absolute",
            top: 0,
            left: 0,
            width: "100%",
            height: "100%",
            borderRadius: "50%",
            background: `conic-gradient(
              transparent ${zoneStartAngle}deg,
              rgba(0, 200, 0, 0.3) ${zoneStartAngle}deg ${zoneEndAngle > zoneStartAngle ? zoneEndAngle : 360}deg,
              transparent ${zoneEndAngle > zoneStartAngle ? zoneEndAngle : 360}deg
            )`,
          }}
        />
        {/* Needle */}
        <div
          className="reflex-dial-needle"
          style={{
            position: "absolute",
            top: "50%",
            left: "50%",
            width: 2,
            height: "45%",
            background: "red",
            transformOrigin: "bottom center",
            transform: `translate(-50%, -100%) rotate(${needleRotation}deg)`,
          }}
        />
      </div>

      {keySequence && (
        <div className="reflex-dial-key-overlay" data-testid="key-sequence-overlay">
          <span>Press: <strong>{keySequence[hits % keySequence.length]}</strong></span>
          {keySequence.length > 1 && hits + 1 < requiredSuccessHits && (
            <span className="reflex-dial-next-key"> Next: {keySequence[(hits + 1) % keySequence.length]}</span>
          )}
        </div>
      )}

      {!finished && (
        <div className="reflex-dial-footer">
          <button className="btn btn-secondary btn-small" onClick={handleAbort}>
            Abandon
          </button>
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function isInZone(angle: number, zoneStart: number, zoneWidth: number): boolean {
  const zoneEnd = (zoneStart + zoneWidth) % 360;
  if (zoneEnd > zoneStart) {
    return angle >= zoneStart && angle <= zoneEnd;
  }
  // Zone wraps around 360°
  return angle >= zoneStart || angle <= zoneEnd;
}
