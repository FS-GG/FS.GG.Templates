import "./site.css";

type Message = { message: string };

export async function loadMessage(fetcher: typeof fetch = fetch): Promise<Message> {
  const response = await fetcher("/api/message");
  if (!response.ok) throw new Error(`message request failed: ${response.status}`);
  return response.json() as Promise<Message>;
}

const target = document.querySelector<HTMLParagraphElement>("#message");
if (target) loadMessage().then(value => target.textContent = value.message).catch(error => target.textContent = error.message);
