import { afterEach, describe, expect, it, vi } from "vitest";

afterEach(() => {
  vi.unstubAllEnvs();
});

describe("resolveMediaUrl", () => {
  it("keeps local cover paths", async () => {
    vi.stubEnv("VITE_API_BASE_URL", "/api/v1");
    vi.resetModules();
    const { resolveMediaUrl } = await import("./media");
    expect(resolveMediaUrl("/api/v1/media/covers/elden-ring")).toBe(
      "/api/v1/media/covers/elden-ring",
    );
  });

  it("rejects absolute and traversal URLs", async () => {
    vi.stubEnv("VITE_API_BASE_URL", "/api/v1");
    vi.resetModules();
    const { resolveMediaUrl } = await import("./media");
    expect(resolveMediaUrl("https://evil.example/track.gif")).toBeUndefined();
    expect(resolveMediaUrl("/api/v1/media/covers/../secret")).toBeUndefined();
    expect(resolveMediaUrl("/etc/passwd")).toBeUndefined();
  });
});
