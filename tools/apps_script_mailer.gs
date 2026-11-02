// Tripjack Certification V3 Hotel: email + log each upload from your own Google account.
// Setup: script.google.com → New project → paste this → Deploy → New deployment → Web app
//   Execute as: Me, Who has access: Anyone → Deploy → copy the /exec URL into CERT_WEBHOOK_URL.
const SHEET_NAME = "Hotel V3 certification submissions";

function doPost(e) {
  const d = JSON.parse(e.postData.contents);
  MailApp.sendEmail({
    to: d.to || Session.getEffectiveUser().getEmail(),
    subject: d.subject,
    body: d.text,
    replyTo: d.email || undefined,
    name: "Tripjack Certification",
  });
  logRow(d);
  return ContentService.createTextOutput(JSON.stringify({ ok: true }))
    .setMimeType(ContentService.MimeType.JSON);
}

function logRow(d) {
  const props = PropertiesService.getScriptProperties();
  let ss;
  const id = props.getProperty("SHEET_ID");
  if (id) ss = SpreadsheetApp.openById(id);
  else {
    ss = SpreadsheetApp.create(SHEET_NAME);
    props.setProperty("SHEET_ID", ss.getId());
    ss.getSheets()[0].appendRow(["Time", "Name", "Company", "TJ user ID", "Phone", "Email", "Result"]);
  }
  ss.getSheets()[0].appendRow([new Date(), d.name, d.company, d.tjUserId, d.phone, d.email, d.outcome]);
}
