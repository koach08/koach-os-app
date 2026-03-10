import { google } from "googleapis";

export function getCalendarClient(accessToken: string) {
  const auth = new google.auth.OAuth2();
  auth.setCredentials({ access_token: accessToken });
  return google.calendar({ version: "v3", auth });
}

export async function listEvents(
  accessToken: string,
  timeMin: string,
  timeMax: string
) {
  const calendar = getCalendarClient(accessToken);
  const res = await calendar.events.list({
    calendarId: "primary",
    timeMin,
    timeMax,
    singleEvents: true,
    orderBy: "startTime",
    maxResults: 200,
  });
  return res.data.items || [];
}

export async function createEvent(
  accessToken: string,
  event: {
    summary: string;
    description?: string;
    start: { dateTime: string; timeZone?: string };
    end: { dateTime: string; timeZone?: string };
    colorId?: string;
    reminders?: {
      useDefault: boolean;
      overrides?: { method: string; minutes: number }[];
    };
  }
) {
  const calendar = getCalendarClient(accessToken);
  const res = await calendar.events.insert({
    calendarId: "primary",
    requestBody: {
      ...event,
      start: { ...event.start, timeZone: event.start.timeZone || "Asia/Tokyo" },
      end: { ...event.end, timeZone: event.end.timeZone || "Asia/Tokyo" },
    },
  });
  return res.data;
}

export async function createEvents(
  accessToken: string,
  events: Parameters<typeof createEvent>[1][]
) {
  const results = [];
  for (const event of events) {
    const result = await createEvent(accessToken, event);
    results.push(result);
  }
  return results;
}

export async function checkConflicts(
  accessToken: string,
  timeMin: string,
  timeMax: string
) {
  const events = await listEvents(accessToken, timeMin, timeMax);
  return events.filter(
    (e) => e.start?.dateTime && e.end?.dateTime
  );
}
