import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import { MinigameDirectory } from "../../components/MinigameDirectory";

// Mock the fetch call for /api/minigames
const mockMinigames = [
  {
    minigame_id: "lights_out",
    difficulty_schema: {
      type: "object",
      properties: {
        grid_size: { type: "integer", minimum: 3, maximum: 7, default: 4 },
      },
    },
    output_schema: {
      type: "object",
      properties: {
        moves_made: { type: "integer" },
      },
    },
  },
];

describe("MinigameDirectory", () => {
  beforeEach(() => {
    vi.stubGlobal(
      "fetch",
      vi.fn(() =>
        Promise.resolve({
          ok: true,
          json: () => Promise.resolve(mockMinigames),
        })
      ) as unknown as typeof fetch
    );
  });

  it("renders loading state initially", () => {
    render(<MinigameDirectory />);
    expect(screen.getByText(/loading/i)).toBeInTheDocument();
  });

  it("displays minigame entries after loading", async () => {
    render(<MinigameDirectory />);
    await waitFor(() => {
      expect(screen.getByText("lights_out")).toBeInTheDocument();
    });
  });

  it("shows difficulty parameters for each minigame", async () => {
    render(<MinigameDirectory />);
    await waitFor(() => {
      expect(screen.getByText(/grid_size/)).toBeInTheDocument();
    });
  });

  it("shows output schema for each minigame", async () => {
    render(<MinigameDirectory />);
    await waitFor(() => {
      expect(screen.getByText(/moves_made/)).toBeInTheDocument();
    });
  });

  it("handles fetch error gracefully", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(() => Promise.resolve({ ok: false, status: 500 })) as unknown as typeof fetch
    );
    render(<MinigameDirectory />);
    await waitFor(() => {
      expect(screen.getByText(/error|failed/i)).toBeInTheDocument();
    });
  });
});
