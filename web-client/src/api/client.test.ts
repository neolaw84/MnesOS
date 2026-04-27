/**
 * Unit tests for the MnesOS API client wrapper.
 *
 * All localStorage access is handled by vitest's jsdom environment.
 * All fetch calls are intercepted via vi.stubGlobal / mockResolvedValue.
 */

import { describe, it, expect, beforeEach, vi, afterEach } from "vitest";
import {
  getOpenRouterKey,
  setOpenRouterKey,
  getUserId,
  setUserId,
  getInstanceId,
  setInstanceId,
  processTurn,
  injectState,
  createGameInstance,
  listInstances,
  deleteInstance,
  createSave,
  listSaves,
  getGameState,
  createCartridge,
  listCartridges,
  getCartridge,
  deleteCartridge,
  updateCartridge,
  listCartridgeVersions,
  getCartridgeVersion,
  uploadCartridgeVersion,
  listPersonas,
  createPersona,
  getPersona,
  updatePersona,
  deletePersona,
} from "./client";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function mockFetchOk(body: unknown) {
  return vi.fn().mockResolvedValue({
    ok: true,
    json: () => Promise.resolve(body),
    text: () => Promise.resolve(JSON.stringify(body)),
  });
}

function mockFetchError(status = 400, message = "Bad Request") {
  return vi.fn().mockResolvedValue({
    ok: false,
    status,
    text: () => Promise.resolve(message),
  });
}

// ---------------------------------------------------------------------------
// localStorage key helpers
// ---------------------------------------------------------------------------

describe("localStorage key helpers", () => {
  beforeEach(() => {
    localStorage.clear();
  });

  it("getOpenRouterKey returns empty string when nothing is set", () => {
    expect(getOpenRouterKey()).toBe("");
  });

  it("setOpenRouterKey / getOpenRouterKey round-trips correctly", () => {
    setOpenRouterKey("or-test-key");
    expect(getOpenRouterKey()).toBe("or-test-key");
  });

  it("getUserId returns empty string when nothing is set", () => {
    expect(getUserId()).toBe("");
  });

  it("setUserId / getUserId round-trips correctly", () => {
    setUserId("user-abc");
    expect(getUserId()).toBe("user-abc");
  });

  it("getInstanceId returns empty string when nothing is set", () => {
    expect(getInstanceId()).toBe("");
  });

  it("setInstanceId / getInstanceId round-trips correctly", () => {
    setInstanceId("inst-xyz");
    expect(getInstanceId()).toBe("inst-xyz");
  });
});

// ---------------------------------------------------------------------------
// apiFetch (tested indirectly through API wrappers)
// ---------------------------------------------------------------------------

describe("apiFetch header injection", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
    localStorage.clear();
  });

  it("attaches X-OpenRouter-Key header when key is set", async () => {
    setOpenRouterKey("my-or-key");
    const mockFetch = mockFetchOk([]);
    vi.stubGlobal("fetch", mockFetch);

    await listCartridges();

    const [, init] = mockFetch.mock.calls[0];
    expect((init.headers as Record<string, string>)["X-OpenRouter-Key"]).toBe(
      "my-or-key",
    );
  });

  it("does not attach X-OpenRouter-Key when key is empty", async () => {
    const mockFetch = mockFetchOk([]);
    vi.stubGlobal("fetch", mockFetch);

    await listCartridges();

    const [, init] = mockFetch.mock.calls[0];
    expect(
      (init.headers as Record<string, string>)["X-OpenRouter-Key"],
    ).toBeUndefined();
  });

  it("attaches X-User-Id header when user ID is set", async () => {
    setUserId("user-123");
    const mockFetch = mockFetchOk([]);
    vi.stubGlobal("fetch", mockFetch);

    await listCartridges();

    const [, init] = mockFetch.mock.calls[0];
    expect((init.headers as Record<string, string>)["X-User-Id"]).toBe(
      "user-123",
    );
  });

  it("throws an error when response is not ok", async () => {
    vi.stubGlobal("fetch", mockFetchError(500, "Internal Server Error"));

    await expect(listCartridges()).rejects.toThrow("API 500: Internal Server Error");
  });
});

// ---------------------------------------------------------------------------
// Turn / instance API
// ---------------------------------------------------------------------------

describe("processTurn", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
    localStorage.clear();
  });

  it("calls the correct endpoint and returns the response", async () => {
    const mockResponse = { turn_id: "t1", bot_response: "Hello!" };
    const mockFetch = mockFetchOk(mockResponse);
    vi.stubGlobal("fetch", mockFetch);

    const result = await processTurn("inst-1", {
      user_input: "Hi",
      turn_id: undefined,
    } as never);

    expect(mockFetch).toHaveBeenCalledWith(
      "/api/instances/inst-1/turn",
      expect.objectContaining({ method: "POST" }),
    );
    expect(result).toEqual(mockResponse);
  });
});

describe("injectState", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
    localStorage.clear();
  });

  it("calls the correct endpoint", async () => {
    const mockFetch = mockFetchOk({ injected: true });
    vi.stubGlobal("fetch", mockFetch);

    await injectState("inst-1", { state: {} } as never);

    expect(mockFetch).toHaveBeenCalledWith(
      "/api/instances/inst-1/inject",
      expect.objectContaining({ method: "POST" }),
    );
  });
});

describe("createGameInstance", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
    localStorage.clear();
  });

  it("calls POST /api/instances", async () => {
    const mockFetch = mockFetchOk({ instance_id: "new-inst" });
    vi.stubGlobal("fetch", mockFetch);

    await createGameInstance({ cartridge_id: "cart-1" } as never);

    expect(mockFetch).toHaveBeenCalledWith(
      "/api/instances",
      expect.objectContaining({ method: "POST" }),
    );
  });
});

describe("listInstances", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
    localStorage.clear();
  });

  it("calls GET /api/instances", async () => {
    const mockFetch = mockFetchOk([]);
    vi.stubGlobal("fetch", mockFetch);

    const result = await listInstances();

    expect(mockFetch).toHaveBeenCalledWith(
      "/api/instances",
      expect.objectContaining({ method: "GET" }),
    );
    expect(result).toEqual([]);
  });
});

describe("deleteInstance", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
    localStorage.clear();
  });

  it("calls DELETE /api/instances/:id on success", async () => {
    const mockFetch = vi.fn().mockResolvedValue({ ok: true });
    vi.stubGlobal("fetch", mockFetch);

    await deleteInstance("inst-del");

    expect(mockFetch).toHaveBeenCalledWith(
      "/api/instances/inst-del",
      expect.objectContaining({ method: "DELETE" }),
    );
  });

  it("attaches X-User-Id when set", async () => {
    setUserId("user-99");
    const mockFetch = vi.fn().mockResolvedValue({ ok: true });
    vi.stubGlobal("fetch", mockFetch);

    await deleteInstance("inst-del");

    const [, init] = mockFetch.mock.calls[0];
    expect((init.headers as Record<string, string>)["X-User-Id"]).toBe("user-99");
  });

  it("throws when response is not ok", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: false,
        status: 404,
        text: () => Promise.resolve("Not Found"),
      }),
    );

    await expect(deleteInstance("ghost")).rejects.toThrow("API 404: Not Found");
  });
});

// ---------------------------------------------------------------------------
// Save API
// ---------------------------------------------------------------------------

describe("createSave", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
    localStorage.clear();
  });

  it("calls POST /api/instances/:id/saves", async () => {
    const mockFetch = mockFetchOk({ save_id: "save-1" });
    vi.stubGlobal("fetch", mockFetch);

    await createSave("inst-1", { label: "Quick Save" } as never);

    expect(mockFetch).toHaveBeenCalledWith(
      "/api/instances/inst-1/saves",
      expect.objectContaining({ method: "POST" }),
    );
  });
});

describe("listSaves", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
    localStorage.clear();
  });

  it("calls GET /api/instances/:id/saves", async () => {
    const mockFetch = mockFetchOk([]);
    vi.stubGlobal("fetch", mockFetch);

    await listSaves("inst-1");

    expect(mockFetch).toHaveBeenCalledWith(
      "/api/instances/inst-1/saves",
      expect.objectContaining({ method: "GET" }),
    );
  });
});

describe("getGameState", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
    localStorage.clear();
  });

  it("calls GET without query param when turnLogId is omitted", async () => {
    const mockFetch = mockFetchOk({ state: {} });
    vi.stubGlobal("fetch", mockFetch);

    await getGameState("inst-1");

    const [url] = mockFetch.mock.calls[0];
    expect(url).toBe("/api/instances/inst-1/state");
  });

  it("appends turn_log_id query param when turnLogId is provided", async () => {
    const mockFetch = mockFetchOk({ state: {} });
    vi.stubGlobal("fetch", mockFetch);

    await getGameState("inst-1", "turn-42");

    const [url] = mockFetch.mock.calls[0];
    expect(url).toBe("/api/instances/inst-1/state?turn_log_id=turn-42");
  });
});

// ---------------------------------------------------------------------------
// Cartridge API
// ---------------------------------------------------------------------------

describe("createCartridge", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
    localStorage.clear();
  });

  it("calls POST /api/cartridges", async () => {
    const mockFetch = mockFetchOk({ cartridge_id: "c1" });
    vi.stubGlobal("fetch", mockFetch);

    await createCartridge({ name: "My Cartridge" } as never);

    expect(mockFetch).toHaveBeenCalledWith(
      "/api/cartridges",
      expect.objectContaining({ method: "POST" }),
    );
  });
});

describe("listCartridges", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
    localStorage.clear();
  });

  it("calls GET /api/cartridges", async () => {
    const mockFetch = mockFetchOk([]);
    vi.stubGlobal("fetch", mockFetch);

    const result = await listCartridges();

    expect(mockFetch).toHaveBeenCalledWith(
      "/api/cartridges",
      expect.objectContaining({ method: "GET" }),
    );
    expect(result).toEqual([]);
  });
});

describe("getCartridge", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
    localStorage.clear();
  });

  it("calls GET /api/cartridges/:id", async () => {
    const mockFetch = mockFetchOk({ cartridge_id: "c1" });
    vi.stubGlobal("fetch", mockFetch);

    await getCartridge("c1");

    expect(mockFetch).toHaveBeenCalledWith(
      "/api/cartridges/c1",
      expect.objectContaining({ method: "GET" }),
    );
  });
});

describe("deleteCartridge", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
    localStorage.clear();
  });

  it("calls DELETE /api/cartridges/:id", async () => {
    const mockFetch = vi.fn().mockResolvedValue({ ok: true });
    vi.stubGlobal("fetch", mockFetch);

    await deleteCartridge("c1");

    expect(mockFetch).toHaveBeenCalledWith(
      "/api/cartridges/c1",
      expect.objectContaining({ method: "DELETE" }),
    );
  });

  it("attaches X-User-Id when set", async () => {
    setUserId("u-del");
    const mockFetch = vi.fn().mockResolvedValue({ ok: true });
    vi.stubGlobal("fetch", mockFetch);

    await deleteCartridge("c1");

    const [, init] = mockFetch.mock.calls[0];
    expect((init.headers as Record<string, string>)["X-User-Id"]).toBe("u-del");
  });

  it("throws when response is not ok", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: false,
        status: 404,
        text: () => Promise.resolve("Not Found"),
      }),
    );

    await expect(deleteCartridge("ghost")).rejects.toThrow("API 404: Not Found");
  });
});

describe("updateCartridge", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
    localStorage.clear();
  });

  it("calls PUT /api/cartridges/:id", async () => {
    const mockFetch = mockFetchOk({ cartridge_id: "c1" });
    vi.stubGlobal("fetch", mockFetch);

    await updateCartridge("c1", { name: "Updated" } as never);

    expect(mockFetch).toHaveBeenCalledWith(
      "/api/cartridges/c1",
      expect.objectContaining({ method: "PUT" }),
    );
  });
});

describe("listCartridgeVersions", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
    localStorage.clear();
  });

  it("calls GET /api/cartridges/:id/versions", async () => {
    const mockFetch = mockFetchOk([]);
    vi.stubGlobal("fetch", mockFetch);

    await listCartridgeVersions("c1");

    expect(mockFetch).toHaveBeenCalledWith(
      "/api/cartridges/c1/versions",
      expect.objectContaining({ method: "GET" }),
    );
  });
});

describe("getCartridgeVersion", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
    localStorage.clear();
  });

  it("calls GET /api/cartridges/:cid/versions/:vid", async () => {
    const mockFetch = mockFetchOk({ version_id: "v1" });
    vi.stubGlobal("fetch", mockFetch);

    await getCartridgeVersion("c1", "v1");

    expect(mockFetch).toHaveBeenCalledWith(
      "/api/cartridges/c1/versions/v1",
      expect.objectContaining({ method: "GET" }),
    );
  });
});

describe("uploadCartridgeVersion", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
    localStorage.clear();
  });

  it("calls POST /api/cartridges/:id/versions with a zip file", async () => {
    const mockFetch = vi.fn().mockResolvedValue({
      ok: true,
      json: () => Promise.resolve({ version_id: "v2" }),
    });
    vi.stubGlobal("fetch", mockFetch);

    const zipFile = new File(["zip-content"], "game.zip", {
      type: "application/zip",
    });
    const result = await uploadCartridgeVersion("c1", "1.0.0", { zipFile });

    const [url, init] = mockFetch.mock.calls[0];
    expect(url).toBe("/api/cartridges/c1/versions");
    expect(init.method).toBe("POST");
    expect(init.body).toBeInstanceOf(FormData);
    expect(result).toEqual({ version_id: "v2" });
  });

  it("calls POST with individual files when no zip is provided", async () => {
    const mockFetch = vi.fn().mockResolvedValue({
      ok: true,
      json: () => Promise.resolve({ version_id: "v3" }),
    });
    vi.stubGlobal("fetch", mockFetch);

    const yareFile = new File(["yare"], "game.yare", { type: "text/plain" });
    await uploadCartridgeVersion("c1", "1.0.1", { yareFile });

    const [, init] = mockFetch.mock.calls[0];
    expect(init.body).toBeInstanceOf(FormData);
  });

  it("attaches API key and user ID headers", async () => {
    setOpenRouterKey("key-up");
    setUserId("user-up");
    const mockFetch = vi.fn().mockResolvedValue({
      ok: true,
      json: () => Promise.resolve({}),
    });
    vi.stubGlobal("fetch", mockFetch);

    await uploadCartridgeVersion("c1", "2.0.0", {});

    const [, init] = mockFetch.mock.calls[0];
    expect((init.headers as Record<string, string>)["X-OpenRouter-Key"]).toBe("key-up");
    expect((init.headers as Record<string, string>)["X-User-Id"]).toBe("user-up");
  });

  it("throws when response is not ok", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: false,
        status: 413,
        text: () => Promise.resolve("Payload Too Large"),
      }),
    );

    await expect(uploadCartridgeVersion("c1", "3.0.0", {})).rejects.toThrow(
      "API 413: Payload Too Large",
    );
  });
});

// ---------------------------------------------------------------------------
// Persona API
// ---------------------------------------------------------------------------

describe("listPersonas", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
    localStorage.clear();
  });

  it("calls GET /api/personas", async () => {
    const mockFetch = mockFetchOk([]);
    vi.stubGlobal("fetch", mockFetch);

    await listPersonas();

    expect(mockFetch).toHaveBeenCalledWith(
      "/api/personas",
      expect.objectContaining({ method: "GET" }),
    );
  });
});

describe("createPersona", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
    localStorage.clear();
  });

  it("calls POST /api/personas", async () => {
    const mockFetch = mockFetchOk({ persona_id: "p1" });
    vi.stubGlobal("fetch", mockFetch);

    await createPersona({ name: "Hero" } as never);

    expect(mockFetch).toHaveBeenCalledWith(
      "/api/personas",
      expect.objectContaining({ method: "POST" }),
    );
  });
});

describe("getPersona", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
    localStorage.clear();
  });

  it("calls GET /api/personas/:id", async () => {
    const mockFetch = mockFetchOk({ persona_id: "p1" });
    vi.stubGlobal("fetch", mockFetch);

    await getPersona("p1");

    expect(mockFetch).toHaveBeenCalledWith(
      "/api/personas/p1",
      expect.objectContaining({ method: "GET" }),
    );
  });
});

describe("updatePersona", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
    localStorage.clear();
  });

  it("calls PUT /api/personas/:id", async () => {
    const mockFetch = mockFetchOk({ persona_id: "p1" });
    vi.stubGlobal("fetch", mockFetch);

    await updatePersona("p1", { name: "Updated Hero" } as never);

    expect(mockFetch).toHaveBeenCalledWith(
      "/api/personas/p1",
      expect.objectContaining({ method: "PUT" }),
    );
  });
});

describe("deletePersona", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
    localStorage.clear();
  });

  it("calls DELETE /api/personas/:id", async () => {
    const mockFetch = vi.fn().mockResolvedValue({ ok: true });
    vi.stubGlobal("fetch", mockFetch);

    await deletePersona("p1");

    expect(mockFetch).toHaveBeenCalledWith(
      "/api/personas/p1",
      expect.objectContaining({ method: "DELETE" }),
    );
  });

  it("attaches X-User-Id when set", async () => {
    setUserId("u-persona");
    const mockFetch = vi.fn().mockResolvedValue({ ok: true });
    vi.stubGlobal("fetch", mockFetch);

    await deletePersona("p1");

    const [, init] = mockFetch.mock.calls[0];
    expect((init.headers as Record<string, string>)["X-User-Id"]).toBe("u-persona");
  });

  it("throws when response is not ok", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: false,
        status: 403,
        text: () => Promise.resolve("Forbidden"),
      }),
    );

    await expect(deletePersona("p1")).rejects.toThrow("API 403: Forbidden");
  });
});
