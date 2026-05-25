import { describe, it, expect } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { YarePlaypen } from "../../components/YarePlaypen";

describe("YarePlaypen", () => {
  it("renders the playpen with editor and output areas", () => {
    render(<YarePlaypen />);
    expect(screen.getByLabelText(/yare js editor/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/mock state/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /run/i })).toBeInTheDocument();
    expect(screen.getByLabelText(/output/i)).toBeInTheDocument();
  });

  it("executes JS code against mock state and shows output", async () => {
    const user = userEvent.setup();
    render(<YarePlaypen />);

    const editor = screen.getByLabelText(/yare js editor/i);
    const stateInput = screen.getByLabelText(/mock state/i);
    const runBtn = screen.getByRole("button", { name: /run/i });

    // Set mock state using fireEvent to avoid userEvent brace parsing
    fireEvent.change(stateInput, { target: { value: '{"player": {"hp": 100}}' } });

    // Write JS rule code
    fireEvent.change(editor, { target: { value: 'state.player.hp = state.player.hp - 20; return state;' } });

    // Run
    await user.click(runBtn);

    // Check output
    await waitFor(() => {
      const output = screen.getByLabelText(/output/i);
      expect(output.textContent).toContain("80");
    });
  });

  it("shows error messages for invalid JS", async () => {
    const user = userEvent.setup();
    render(<YarePlaypen />);

    const editor = screen.getByLabelText(/yare js editor/i);
    const runBtn = screen.getByRole("button", { name: /run/i });

    fireEvent.change(editor, { target: { value: "this is not valid {{{{ javascript" } });
    await user.click(runBtn);

    await waitFor(() => {
      const output = screen.getByLabelText(/output/i);
      expect(output.textContent).toMatch(/error/i);
    });
  });

  it("shows error for invalid JSON state", async () => {
    const user = userEvent.setup();
    render(<YarePlaypen />);

    const stateInput = screen.getByLabelText(/mock state/i);
    const runBtn = screen.getByRole("button", { name: /run/i });

    fireEvent.change(stateInput, { target: { value: "not-json" } });
    await user.click(runBtn);

    await waitFor(() => {
      const output = screen.getByLabelText(/output/i);
      expect(output.textContent).toMatch(/error|invalid/i);
    });
  });
});
