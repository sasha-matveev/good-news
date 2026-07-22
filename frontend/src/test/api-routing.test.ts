import { readFileSync } from "node:fs";
import { resolve } from "node:path";

afterEach(() => {
  vi.restoreAllMocks();
  vi.unstubAllEnvs();
  vi.resetModules();
});

describe("production strangler operation routing", () => {
  test("assigns every exported API operation explicitly and defaults all owners to Python", async () => {
    const api = await import("../lib/api");
    const source = readFileSync(resolve(process.cwd(), "src/lib/api.ts"), "utf8");
    const exportedOperations = [...source.matchAll(/export async function\s+(\w+)/g)]
      .map((match) => match[1])
      .sort();

    expect(Object.keys(api.API_OPERATION_OWNERS).sort()).toEqual(exportedOperations);
    expect(new Set(Object.values(api.API_OPERATION_OWNERS))).toEqual(new Set(["python"]));
  });

  test("routes through the Python origin in production even if an override is injected", async () => {
    vi.stubEnv("VITE_CONTENT_API_ORIGIN", "https://python.example/");
    vi.stubEnv("VITE_JAVA_API_ORIGIN", "https://java.example/");
    vi.stubEnv("VITE_DEPLOY_ENV", "production");
    vi.stubEnv("VITE_API_BACKEND_OVERRIDE", "java");
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValueOnce(new Response(JSON.stringify([]), { status: 200 }))
    );

    const { listPosts } = await import("../lib/api");
    await listPosts();

    expect(fetch).toHaveBeenCalledWith("https://python.example/api/posts", { method: "GET" });
  });

  test("allows a whole-app Java override in staging for diagnostics", async () => {
    vi.stubEnv("VITE_CONTENT_API_ORIGIN", "https://python.example");
    vi.stubEnv("VITE_JAVA_API_ORIGIN", "https://java.example");
    vi.stubEnv("VITE_DEPLOY_ENV", "staging");
    vi.stubEnv("VITE_API_BACKEND_OVERRIDE", "java");
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValueOnce(new Response(JSON.stringify([]), { status: 200 }))
    );

    const { listSources } = await import("../lib/api");
    await listSources();

    expect(fetch).toHaveBeenCalledWith("https://java.example/api/sources", { method: "GET" });
  });
});
