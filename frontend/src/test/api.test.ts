import { setReadLater, recordArticleOpen } from "../lib/api";

beforeEach(() => {
  vi.restoreAllMocks();
});

describe("setReadLater", () => {
  test("posts to /api/posts/{id}/read-later with saved=true and returns read_later", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValueOnce(
        new Response(JSON.stringify({ post_id: 42, read_later: true }), { status: 200 })
      )
    );

    const result = await setReadLater(42, true);

    expect(result).toEqual({ post_id: 42, read_later: true });
    const [url, init] = (fetch as ReturnType<typeof vi.fn>).mock.calls[0] as [string, RequestInit];
    expect(url).toBe("/api/posts/42/read-later");
    expect(init.method).toBe("POST");
    expect(JSON.parse(init.body as string)).toEqual({ saved: true });
  });

  test("posts saved=false and returns read_later false", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValueOnce(
        new Response(JSON.stringify({ post_id: 7, read_later: false }), { status: 200 })
      )
    );

    const result = await setReadLater(7, false);

    expect(result).toEqual({ post_id: 7, read_later: false });
    const [, init] = (fetch as ReturnType<typeof vi.fn>).mock.calls[0] as [string, RequestInit];
    expect(JSON.parse(init.body as string)).toEqual({ saved: false });
  });
});

describe("recordArticleOpen", () => {
  test("posts to /api/posts/{id}/open and returns opened true", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValueOnce(
        new Response(JSON.stringify({ opened: true }), { status: 200 })
      )
    );

    const result = await recordArticleOpen(5);

    expect(result).toEqual({ opened: true });
    const [url, init] = (fetch as ReturnType<typeof vi.fn>).mock.calls[0] as [string, RequestInit];
    expect(url).toBe("/api/posts/5/open");
    expect(init.method).toBe("POST");
  });
});
