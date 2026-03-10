export async function parseDocument(
  buffer: Buffer,
  mimeType: string
): Promise<string> {
  if (mimeType === "application/pdf") {
    // eslint-disable-next-line @typescript-eslint/no-require-imports
    const pdfParse = require("pdf-parse") as (buf: Buffer) => Promise<{ text: string }>;
    const data = await pdfParse(buffer);
    return data.text;
  }

  if (
    mimeType === "text/plain" ||
    mimeType === "text/csv" ||
    mimeType === "text/markdown"
  ) {
    return buffer.toString("utf-8");
  }

  // For Excel/Word, extract as best-effort text
  if (
    mimeType ===
      "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet" ||
    mimeType === "application/vnd.ms-excel"
  ) {
    // Simple text extraction from xlsx
    return buffer.toString("utf-8").replace(/[^\x20-\x7E\u3000-\u9FFF\uFF00-\uFFEF\n\r\t]/g, " ");
  }

  if (
    mimeType ===
      "application/vnd.openxmlformats-officedocument.wordprocessingml.document" ||
    mimeType === "application/msword"
  ) {
    return buffer.toString("utf-8").replace(/[^\x20-\x7E\u3000-\u9FFF\uFF00-\uFFEF\n\r\t]/g, " ");
  }

  throw new Error(`Unsupported file type: ${mimeType}`);
}
