export default {
  /**
   * carisyou-proxy — 카이즈유(CloudFront 뒤)가 GitHub Actions·클라우드 IP를
   * 403 차단하므로 Cloudflare 엣지에서 우회 fetch. 2026-11-09 deal 부활용.
   *
   * 라우트 (workers.dev):
   *   /m/car/7830   → https://m.carisyou.com/car/7830
   *   /w/car/7830   → https://www.carisyou.com/car/7830
   *   /f/upload/... → http://file.carisyou.com/upload/...
   * {id}는 숫자만 허용 (오픈프록시 최소화).
   */
  async fetch(request) {
    const url = new URL(request.url);
    const seg = url.pathname.split("/").filter(Boolean);
    if (seg.length < 2) {
      return new Response("bad route", { status: 400 });
    }
    const kind = seg[0]; // m | w | f
    const rest = seg.slice(1).join("/");
    if (kind === "m" || kind === "w") {
      if (!/^car\/\d+$/.test(rest)) {
        return new Response("bad route", { status: 400 });
      }
    } else if (kind === "f") {
      if (rest.length < 5) {
        return new Response("bad route", { status: 400 });
      }
    } else {
      return new Response("bad route", { status: 400 });
    }
    const host =
      kind === "m" ? "https://m.carisyou.com"
      : kind === "w" ? "https://www.carisyou.com"
      : "http://file.carisyou.com";
    const upstream = `${host}/${rest}${url.search}`;
    const r = await fetch(upstream, {
      method: "GET",
      headers: {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)",
        "Accept": "*/*",
        "Accept-Language": "ko-KR,ko;q=0.9,en;q=0.8",
        "Referer": "https://www.carisyou.com/",
      },
      redirect: "follow",
      cf: { cacheTtl: 0 },
    });
    return new Response(r.body, {
      status: r.status,
      headers: {
        "content-type": r.headers.get("content-type") || "text/html",
        "cache-control": "no-store",
      },
    });
  },
};
