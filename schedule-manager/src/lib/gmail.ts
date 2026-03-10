import { google } from "googleapis";

export async function searchEmails(
  accessToken: string,
  query: string,
  maxResults: number = 20
) {
  const auth = new google.auth.OAuth2();
  auth.setCredentials({ access_token: accessToken });
  const gmail = google.gmail({ version: "v1", auth });

  const listRes = await gmail.users.messages.list({
    userId: "me",
    q: query,
    maxResults,
  });

  const messageIds = listRes.data.messages || [];
  const emails = [];

  for (const msg of messageIds) {
    if (!msg.id) continue;
    const detail = await gmail.users.messages.get({
      userId: "me",
      id: msg.id,
      format: "full",
    });

    const headers = detail.data.payload?.headers || [];
    const subject =
      headers.find((h) => h.name?.toLowerCase() === "subject")?.value || "";
    const from =
      headers.find((h) => h.name?.toLowerCase() === "from")?.value || "";
    const date =
      headers.find((h) => h.name?.toLowerCase() === "date")?.value || "";

    // Extract body text
    let body = "";
    const parts = detail.data.payload?.parts || [];
    if (parts.length > 0) {
      const textPart = parts.find((p) => p.mimeType === "text/plain");
      if (textPart?.body?.data) {
        body = Buffer.from(textPart.body.data, "base64").toString("utf-8");
      }
    } else if (detail.data.payload?.body?.data) {
      body = Buffer.from(detail.data.payload.body.data, "base64").toString(
        "utf-8"
      );
    }

    emails.push({
      id: msg.id,
      subject,
      from,
      date,
      body: body.slice(0, 3000),
      snippet: detail.data.snippet || "",
    });
  }

  return emails;
}
