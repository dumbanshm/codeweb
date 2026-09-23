// Thin wrapper around Groq's OpenAI-compatible chat completions API.
// Groq's free tier is used deliberately: fast + no billing setup required.
// Get a key at https://console.groq.com/keys

const GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions";
const DEFAULT_MODEL = process.env.GROQ_MODEL || "openai/gpt-oss-20b";
const MAX_OUTPUT_TOKENS = 400;

export function isLlmConfigured() {
  return Boolean(process.env.GROQ_API_KEY);
}

export async function explainWithLlm(systemPrompt, userPrompt) {
  const apiKey = process.env.GROQ_API_KEY;
  if (!apiKey) {
    throw new Error("LLM is not configured (missing GROQ_API_KEY).");
  }

  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 15000);

  try {
    const response = await fetch(GROQ_API_URL, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${apiKey}`
      },
      body: JSON.stringify({
        model: DEFAULT_MODEL,
        max_tokens: MAX_OUTPUT_TOKENS,
        temperature: 0.3,
        messages: [
          { role: "system", content: systemPrompt },
          { role: "user", content: userPrompt }
        ]
      }),
      signal: controller.signal
    });

    if (!response.ok) {
      const body = await response.text().catch(() => "");
      throw new Error(`Groq API returned ${response.status}: ${body.slice(0, 300)}`);
    }

    const data = await response.json();
    const text = data.choices?.[0]?.message?.content;
    if (!text) {
      throw new Error("Groq API returned no content.");
    }
    return text.trim();
  } finally {
    clearTimeout(timeout);
  }
}
