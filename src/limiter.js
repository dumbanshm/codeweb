// Simple in-memory token-bucket rate limiter, keyed by client IP + bucket name.
// Fine for a single Render instance — no need for Redis/shared state here.

const BUCKETS = {
  "analyze-github": { limit: 5, windowMs: 60 * 60 * 1000 },   // 5 analyses / hour / IP
  "explain-node": { limit: 30, windowMs: 60 * 60 * 1000 }     // 30 explanations / hour / IP
};

const hits = new Map(); // key: `${bucketName}:${clientKey}` -> number[] (timestamps)

export function getClientKey(req) {
  const forwarded = req.headers["x-forwarded-for"];
  if (typeof forwarded === "string" && forwarded.length > 0) {
    return forwarded.split(",")[0].trim();
  }
  return req.socket?.remoteAddress || "unknown";
}

export function checkRateLimit(clientKey, bucketName) {
  const bucket = BUCKETS[bucketName];
  if (!bucket) return true;

  const key = `${bucketName}:${clientKey}`;
  const now = Date.now();
  const timestamps = (hits.get(key) || []).filter((t) => now - t < bucket.windowMs);

  if (timestamps.length >= bucket.limit) {
    hits.set(key, timestamps);
    return false;
  }

  timestamps.push(now);
  hits.set(key, timestamps);
  return true;
}

// Periodic cleanup so the map doesn't grow unbounded over a long-running process.
setInterval(() => {
  const now = Date.now();
  for (const [key, timestamps] of hits.entries()) {
    const bucketName = key.split(":")[0];
    const windowMs = BUCKETS[bucketName]?.windowMs || 60 * 60 * 1000;
    const fresh = timestamps.filter((t) => now - t < windowMs);
    if (fresh.length === 0) hits.delete(key);
    else hits.set(key, fresh);
  }
}, 10 * 60 * 1000).unref();
