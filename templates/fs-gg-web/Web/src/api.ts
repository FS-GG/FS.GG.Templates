export type Message = { message: string };

export async function loadMessage(fetcher: typeof fetch = fetch): Promise<Message> {
  const response = await fetcher("/api/message");
  if (!response.ok) throw new Error(`message request failed: ${response.status}`);
  return response.json() as Promise<Message>;
}
