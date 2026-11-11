// Certification requirements, one entry per test case (from the Tripjack self-certification table)
const TEST_CASES = [
  { n: 1,  autoCancel: true, desc: "Auto cancellation of booking in ON HOLD status (unconfirmed case)", city: "Domestic", adults: "1", children: "0", rooms: "1",
    note: "Do not leave the booking ON HOLD. Do not confirm it; let it be auto-cancelled, then call Booking Detail: it must show UNCONFIRMED or CANCELLED. CANCELLATION_PENDING is accepted in UAT; in production keep calling Booking Detail until it shows CANCELLED." },
  { n: 2,  desc: "Instant booking", city: "Domestic", adults: "4", children: "2", rooms: "1" },
  { n: 3,  desc: "Hold booking, then confirm booking", city: "Domestic", adults: "2, 3, 2", children: "2, 1, 1", rooms: "3" },
  { n: 4,  cancel: true, desc: "Create a booking within the cancellation deadline and cancel it", city: "Domestic", adults: "1, 2, 1, 1, 1", children: "2, 1, 1, 0, 0", rooms: "5" },
  { n: 5,  cancel: true, desc: "Create a booking outside the cancellation deadline and cancel it", city: "International", adults: "4", children: "2", rooms: "1" },
  { n: 6,  cancel: true, desc: "Cancel booking in ON HOLD status (without confirming it)", city: "International", adults: "2, 3, 2", children: "2, 1, 1 (room 3 may be 2)", rooms: "3" },
  { n: 7,  desc: "Instant booking", city: "International", adults: "1, 2, 1, 1, 1", children: "2, 1, 1, 0, 0", rooms: "5" },
  { n: 8,  desc: "Instant booking", city: "International", adults: "3, 3", children: "0, 0", rooms: "2" },
  { n: 9,  desc: "Cancellation rules and policies are displayed in your application", infoOnly: true,
    note: "Policy-only case: no booking is needed, but the Search, Detail, Review request + response and the Cancellation Policy response are required." },
  { n: 10, desc: "Same PAN for all rooms", city: "Domestic / International", adults: "2, 2", children: "1, 0", rooms: "2", note: "Indian nationals only (nationality 106). In the Book request, the lead guest of every room must have the same PAN (the lead guest's PAN)." },
  { n: 11, desc: "Same PAN for all guests", city: "Domestic / International", adults: "2", children: "1", rooms: "1", note: "Indian nationals only (nationality 106). In the Book request, every adult guest must have the same PAN (the lead guest's PAN)." },
  { n: 12, desc: "Booking using PASSPORT", city: "Domestic / International", adults: "2", children: "1", rooms: "1", note: "Non-Indian nationality (any code except 106, which is India) with a valid passport number (if applicable). The Book request must contain a valid passport number for the guests." },
  { n: 13, desc: "Booking with corporate PAN", city: "Domestic / International", adults: "2", children: "1", rooms: "1", note: "Indian nationals only (if applicable). A corporate PAN (Permanent Account Number) follows the standard 10-character alphanumeric structure AAAAA0000A issued by the Income Tax Department of India, where the fourth character denotes the entity type as 'C' for Company." },
  { n: 14, desc: "Cancel all test bookings made during certification", infoOnly: true,
    note: "Cancel every test booking, then add the Booking Detail response of EVERY test booking showing status CANCELLED to this folder (all bookings from all test cases)." },
];

// Booking Detail requirement shown on every booking test case
function bookingDetailNote(tc) {
  if (tc.infoOnly) return "";
  let t = "After the booking is made, call Booking Detail and add its request and response. The status must be the updated booking status.";
  if (tc.cancel) t += " After cancelling, call Booking Detail again and add that request and response too; it must show the updated status CANCELLED (CANCELLATION_PENDING is accepted in UAT; in production keep calling Booking Detail until it shows CANCELLED).";
  return t;
}

// Plain-language name and "what to do" for each check
const RULES = {
  CORRELATION_ID: ["Correlation ID", "Use the same correlationId in the Search, Detail and Review requests."],
  DETAIL_ONE_HOTEL: ["One hotel in Detail", "Search may list many hotels, but the Detail request must be for exactly one hotel (one hid)."],
  SAME_PAN: ["Same PAN", "Use one PAN for the whole booking: the lead guest of every room (TC10) or every adult guest (TC11) must carry the same PAN."],
  NATIONALITY: ["Nationality", "Test Case 12 needs a non-Indian nationality: use any nationality code except 106 (India) in Search and Detail."],
  TJ_HOTEL: ["TJ test hotel", "Use only TJ test hotels: every hotel ID (hids / hid) must start with 10."],
  FILE_PAIR: ["Request / response pair", "Every API call in the folder needs both its request and its response file."],
  HOLD_AUTO_CANCEL: ["ON HOLD auto-cancel", "The ON HOLD booking must not be left on hold: the Booking Detail must show UNCONFIRMED or CANCELLED."],
  AFTER_CANCEL: ["Booking Detail after cancel", "After cancelling, call Booking Detail again and add its response; it must show status CANCELLED."],
  BOOKING_ID: ["Booking ID", "All requests of one booking must use the same bookingId (from the Review response)."],
  TIMEOUT_MS: ["timeoutMs", "Add \"timeoutMs\" (for example \"timeoutMs\": 30000) to the Search and Detail requests. It is mandatory."],
  SEARCH_DETAIL_DATES: ["Dates / nationality / currency", "Keep checkIn, checkOut, nationality and currency identical in Search and Detail."],
  ROOM_COMBO: ["Room setup", "Keep the rooms (adults, children, child ages) identical in Search and Detail."],
  HOTEL_ID: ["Hotel ID", "Use the same hotel ID from Search through to Review."],
  REVIEW_HASH: ["Review hash", "Send the reviewHash from the Detail response unchanged in the Review request."],
  OPTION_ID: ["Option ID", "Pick an optionId that was returned in the Detail response."],
  OPTION_CONSISTENCY: ["Room / price consistency", "Room, price and currency must match between Detail and Review."],
  TRAVELLER_ROOMS: ["Guests per room", "Guests in the Hold/Book request must match the rooms you searched."],
  PAN: ["PAN / passport", "Add PAN (or passport details for non-Indian guests) for every room."],
  PAYMENT_INFO: ["Payment amount", "paymentInfos amount must equal the totalPrice from the Review response."],
  TEST_CASE_SPEC: ["Test case requirement", "Rooms, adults and children must match the requirement shown for this test case."],
  JSON_PARSE: ["Invalid JSON", "Open the file named here and fix the JSON at the line shown (missing comma, extra comma, unclosed bracket or quote, or a cut-off file). Check it with any JSON validator, then upload again."],
  FILES: ["Missing file", "Add the missing request/response file to this test case folder."],
  CANCEL_ALL: ["Cancelled bookings", "Add the Booking Detail response showing status CANCELLED for every test booking to the Test Case 14 folder."],
  FLOW_SEQUENCE: ["Booking flow", "Add the missing request/response files for this flow."],
};

// ---- Plain-language "what is wrong" + "how to fix" for each error ----
const STEP_NAMES = { search: "Search", detail: "Detail", review: "Review", hold: "Hold", book: "Book" };
const roomNo = (m) => `Room ${parseInt(m, 10) + 1}`;

function explain(f) {
  const msg = String(f.message);
  const first = msg.split("\n")[0];
  const field = (name) => { const m = msg.match(new RegExp("^" + name + "\\s*:\\s*(.*)$", "mi")); return m ? m[1].replace(/\s*\[[^\]]*\]\s*$/, "").trim() : ""; };
  let m;
  switch (f.rule) {
    case "DETAIL_ONE_HOTEL": {
      const ids = (first.match(/\(([^)]*)\)/) || [])[1] || "";
      return { problem: `The Detail request asks for more than one hotel (${ids}). Search can list many hotels, but Detail must be for exactly one hotel.`,
               fix: `Pick one hotel from the Search response and send only its ID in the Detail request, e.g. "hid": "${ids.split(",")[0].trim() || "100000000991"}".` };
    }
    case "SAME_PAN": {
      if (/^PAN missing/.test(first)) return {
        problem: `The Book request has no PAN for ${first.replace(/^PAN missing for: /, "").replace(/ \(Book request.*$/, "")}. This test case needs the same PAN for every guest listed.`,
        fix: "Add the lead guest's PAN to each of these guests in the Book request (roomTravellerInfo → travellerInfo → pan). Use the same PAN for all of them." };
      if (/^Different PANs/.test(first)) return {
        problem: `Different PANs are used in the Book request (${first.split(": ").slice(1).join(": ")}). This test case needs one PAN for the whole booking.`,
        fix: "Use the lead guest's PAN for all rooms/guests in the Book request, so every pan value is identical." };
      if (/^Invalid PAN/.test(first)) return {
        problem: `${first}.`,
        fix: "A PAN has 10 characters: 5 letters, 4 digits, 1 letter (e.g. ABCPE1234F)." };
      return { problem: "The Book request has no PAN. This test case needs the same PAN across the booking.",
               fix: "Add the lead guest's PAN to the travellers in the Book request." };
    }
    case "NATIONALITY": {
      if (/Indian nationals only/.test(first)) {
        const step = (first.match(/^(Search|Detail) request/) || [])[1] || "Search/Detail";
        return { problem: `The ${step} request does not use nationality 106 (India). This test case is for Indian nationals only.`,
                 fix: `Set "nationality": "106" in the Search and Detail requests.` };
      }
      const step = (first.match(/^(Search|Detail) request/) || [])[1] || "Search/Detail";
      return /missing/.test(first)
        ? { problem: `The ${step} request has no nationality. This test case needs a non-Indian nationality.`,
            fix: `Add "nationality" with a non-Indian code (anything except 106) to the ${step} request, e.g. "nationality": "231".` }
        : { problem: `The ${step} request uses nationality 106 (India). Test Case 12 is a passport booking and needs a non-Indian nationality; otherwise certification fails.`,
            fix: `Use a non-Indian nationality code (anything except 106, e.g. 231) in the Search and Detail requests, and book with the guest's passport details.` };
    }
    case "TJ_HOTEL": {
      const step = (first.match(/^(Search|Detail|Review) request/) || [])[1] || "a";
      const ids = first.split(": ").pop();
      return { problem: `The ${step} request uses a hotel that is not a TJ test hotel (${ids}). Only TJ test hotels, whose ID starts with 10, are allowed; otherwise certification fails.`,
               fix: `Search and book only TJ test hotels. Use hotel IDs that start with 10 (e.g. 100000000991) in the Search, Detail and Review requests.` };
    }
    case "TIMEOUT_MS": {
      const step = (first.match(/^(Search|Detail) request/) || [])[1] || "Search/Detail";
      return /missing/.test(first)
        ? { problem: `The ${step} request does not contain "timeoutMs". It is mandatory in the Search and Detail requests; without it certification fails.`,
            fix: `Add "timeoutMs": 30000 to the ${step} request body and run the case again.` }
        : { problem: `The ${step} request has an invalid timeoutMs value (${first.split("got ")[1] || "?"}).`,
            fix: `Set "timeoutMs" to a positive number in milliseconds, e.g. 30000.` };
    }
    case "CORRELATION_ID": {
      const pairs = [...msg.matchAll(/'(\w+)':\s*'([^']*)'/g)].map((x) => [STEP_NAMES[x[1]] || x[1], x[2]]);
      const base = pairs.length ? pairs[0][1] : "";
      const diff = pairs.filter(([, v]) => v !== base).map(([k]) => k);
      return {
        problem: diff.length ? `A different correlationId was used in the ${diff.join(", ")} request. Search, Detail and Review must all use the same one.`
                             : "correlationId is not the same in Search, Detail and Review.",
        fix: base ? `Use the same correlationId (${base}) in the Search, Detail and Review requests.` : "Use the same correlationId in the Search, Detail and Review requests.",
      };
    }
    case "SEARCH_DETAIL_DATES":
      if ((m = first.match(/^(\w+): search (.*) vs detail (.*)$/)))
        return { problem: `${m[1]} is different in Search (${m[2]}) and Detail (${m[3]}).`, fix: `Send the same ${m[1]} in the Search and Detail requests.` };
      break;
    case "ROOM_COMBO":
      return { problem: "The rooms (adults / children / child ages) in the Detail request are different from the Search request.", fix: "Send exactly the same rooms[] in the Detail request as in the Search request." };
    case "HOTEL_ID":
      if ((m = first.match(/^(.+?) -> (.+?) mismatch: '?([^']*)'? vs '?([^']*)'?$/)))
        return { problem: `The hotel ID changed: ${m[1]} has ${m[3]} but ${m[2]} has ${m[4]}.`, fix: `Use hotel ID ${m[3]} (from ${m[1]}) in the ${m[2]}. Keep the same hotel from Search to Review.` };
      break;
    case "REVIEW_HASH":
      if (/not found/i.test(first)) return { problem: "reviewHash is missing in the Review request.", fix: "Copy the reviewHash from the Detail response into the Review request." };
      return { problem: "The reviewHash in the Review request is not the one returned in the Detail response.",
               fix: field("Detail Response") ? `Send this reviewHash from the Detail response: ${field("Detail Response")}` : "Send the reviewHash from the Detail response unchanged." };
    case "FILE_PAIR":
      if ((m = first.match(/^Missing file: (.+?) \(the folder has the (.+?), so/)))
        return { problem: `The ${m[1]} file is missing. The folder has the ${m[2]}, so its matching ${/Response$/.test(m[1]) ? "response" : "request"} must be included too.`,
                 fix: `Add the ${m[1]} file for this call to the test case folder, then upload again.` };
      break;
    case "HOLD_AUTO_CANCEL": {
      if (/accepted in UAT/.test(first)) return {
        problem: `The Booking Detail shows ${(first.match(/shows (\S+):/) || [])[1] || "CANCELLATION_PENDING"}. That is fine in UAT, so this test case passes.`,
        fix: "Production tip: never leave an ON HOLD booking as it is. Keep calling Booking Detail until the status is CANCELLED (or UNCONFIRMED), and only then treat the booking as cancelled." };
      if (/^No Booking Detail/.test(first))
        return { problem: "There is no Booking Detail response showing what happened to the ON HOLD booking.",
                 fix: "After the hold, wait for the booking to be auto-cancelled (do not confirm it), call Booking Detail and add the response that shows UNCONFIRMED or CANCELLED." };
      const st = (first.match(/Booking Detail shows (.+?), expected/) || [])[1] || "ON_HOLD";
      return { problem: `The booking was left ON HOLD: the Booking Detail shows ${st}. In this test case the ON HOLD booking must end as UNCONFIRMED or CANCELLED.`,
               fix: "Do not confirm the hold and do not leave it on hold. Wait until it is auto-cancelled (or cancel it), call Booking Detail again and add the response that shows UNCONFIRMED or CANCELLED (CANCELLATION_PENDING is accepted in UAT)." };
    }
    case "AFTER_CANCEL": {
      if (/accepted in UAT/.test(first)) return {
        problem: `The Booking Detail after cancel shows ${(first.match(/shows (\S+):/) || [])[1] || "CANCELLATION_PENDING"}. That is fine in UAT, so this test case passes.`,
        fix: "Production tip: cancellation can take a while to complete. Keep calling Booking Detail (e.g. every few minutes) until the status is CANCELLED, and only then show the booking as cancelled to your customer." };
      if (/^Missing file/.test(first))
        return { problem: "The Booking Detail response after the cancel is missing. After cancelling, Booking Detail must be called again to show the updated status (CANCELLED).",
                 fix: "After the Cancel call, call Booking Detail again for this bookingId and add its response to this folder (e.g. \"TJ test hotel detail after cancel Response.json\")." };
      const st = (first.match(/shows status (\S+)/) || [])[1] || "";
      return { problem: `The Booking Detail after cancel shows status ${st}, but it must show CANCELLED.`,
               fix: /PENDING/i.test(st) ? "The cancellation is still being processed. Wait a few minutes, call Booking Detail again until it shows CANCELLED, and add that response."
                                        : "Make sure the booking was really cancelled, then call Booking Detail again and add the response that shows CANCELLED." };
    }
    case "FLOW_SEQUENCE": {
      if ((m = first.match(/^Missing flow file: (.+?) \(this test case needs: (.*)\)$/)))
        return { problem: `The ${m[1]} file is missing. This test case needs the full flow: ${m[2]}.`,
                 fix: `Add the ${m[1]} file to this test case folder (run that API call and save its ${/Response$/.test(m[1]) ? "response" : "request"}), then upload again.` };
      break;
    }
    case "BOOKING_ID": {
      if ((m = first.match(/^bookingId missing: (.*) has no bookingId(?: \(expected (\S+)\))?/)))
        return { problem: `${m[1]} does not contain a bookingId. Every request after Review (Hold / Book / Confirm / Booking Detail / Cancel) must send the bookingId of this booking.`,
                 fix: `Add "bookingId": "${m[2] || "<bookingId from the Review response>"}" to ${m[1]}.` };
      const exp = (first.match(/expected (\S+);/) || [])[1] || "";
      const where = first.split("; ").slice(1).join("; ");
      return { problem: `Booking ID mismatch: ${where}, but the rest of this booking uses ${exp}. Every request of one booking (Hold / Book / Confirm / Booking Detail / Cancel) must use the same bookingId.`,
               fix: `Use bookingId ${exp} (the one from the Review response) in every request of this test case. A different ID usually means a file from another booking was copied in; run the flow again and save the right files.` };
    }
    case "OPTION_ID":
      if (/not found/i.test(first)) return { problem: "optionId is missing in the Review request.", fix: "Send the optionId of the room you picked from the Detail response in the Review request." };
      return { problem: "The optionId in the Review request was not returned in the Detail response.", fix: "Pick an optionId from the Detail response and send it unchanged in the Review request." };
    case "OPTION_CONSISTENCY":
      return { problem: `Room / price changed between Detail and Review: ${first}`, fix: "Review the same option (room, price, currency) that you selected from the Detail response." };
    case "TRAVELLER_ROOMS":
      if ((m = first.match(/room count: search\/detail (\d+) vs hold\/book (\d+)/)))
        return { problem: `You searched ${m[1]} room(s), but the Hold/Book request has guests for ${m[2]} room(s).`, fix: `Send guests for exactly ${m[1]} room(s) in the Hold/Book request, one room entry per searched room.` };
      if ((m = first.match(/room\[(\d+)\] child ages: searched \[([^\]]*)\], (.*)$/))) {
        const missing = /no child age/.test(m[3]);
        return { problem: missing ? `${roomNo(m[1])}: you searched children aged ${m[2]}, but the Hold/Book request does not send the children's age.`
                                  : `${roomNo(m[1])}: you searched children aged ${m[2]}, but the Hold/Book request has ${m[3].replace("Hold/Book has ", "ages ")}.`,
                 fix: `Send each child's age (${m[2]}) in the Hold/Book travellers for ${roomNo(m[1])}, matching the search.` };
      }
      if ((m = first.match(/room\[(\d+)\] (adults|children): expected (\d+) got (\d+)/)))
        return { problem: `${roomNo(m[1])}: you searched ${m[3]} ${m[2]}, but the Hold/Book request has ${m[4]}.`, fix: `Add ${m[3]} ${m[2]} for ${roomNo(m[1])} in the Hold/Book request.` };
      break;
    case "PAN":
      if ((m = first.match(/room\[(\d+)\]/)))
        return { problem: `${roomNo(m[1])}: PAN / passport is required but not sent.`, fix: `Add the PAN (or passport for non-Indian guests) for ${roomNo(m[1])} in the Hold/Book request.` };
      return { problem: "This hotel needs a PAN, but no PAN was sent in the Hold/Book request.", fix: "Add the PAN for the lead guest (or each room) in the Hold/Book request." };
    case "PAYMENT_INFO":
      if ((m = first.match(/Amount MISMATCH: (.+?) has (\S+) but Review Response totalPrice is (\S+)/)))
        return { problem: `The payment amount ${m[2]} in the ${m[1]} does not match the Review price ${m[3]}.`, fix: `Send paymentInfos amount = ${m[3]} (totalPrice from the Review response).` };
      if (/not found/.test(first))
        return { problem: "The payment amount (paymentInfos) is missing in the Book request.", fix: "Add paymentInfos with amount = totalPrice from the Review response." };
      break;
    case "TEST_CASE_SPEC": {
      if (/Passport required/.test(first)) return { problem: "A passport number is required, but no passport (pNum) was sent for the guests.", fix: "Add a valid passport number (pNum) for the guests in the Book request." };
      if (/PAN required/.test(first)) return { problem: "PAN is required for this test case, but no PAN was sent.", fix: "Add the PAN for the guests in the Book request." };
      const src = (first.split(" — ")[0] || "").trim();
      const need = field("Expected"), got = field("Got");
      if (need || got)
        return { problem: `The ${src || "request"} does not match this test case. Required: ${need || "?"}. You sent: ${got || "?"}.`, fix: `Redo this test case with exactly: ${need}.` };
      return { problem: first, fix: "Rooms, adults and children must match the requirement for this test case." };
    }
    case "CANCEL_ALL":
      if (/accepted in UAT/.test(first)) return {
        problem: `${first.split(":")[0]}. That is fine in UAT, so it counts as cancelled.`,
        fix: "Production tip: keep calling Booking Detail until the status is CANCELLED before you treat the booking as cancelled." };
      if (/^No Booking Detail response/.test(first))
        return { problem: "No Booking Detail response was added to this folder.", fix: "Cancel every test booking, call Booking Detail for each one and add the responses (showing CANCELLED) here." };
      if ((m = first.match(/^Booking (\S+) has status (\S+), expected CANCELLED \(([^)]*)\)/)))
        return { problem: `Booking ${m[1]} is still ${m[2]}, not CANCELLED (${m[3]}).`,
                 fix: /PENDING/.test(m[2]) ? `Wait until the cancellation finishes, call Booking Detail for ${m[1]} again and add the response showing CANCELLED.`
                                           : `Cancel booking ${m[1]}, then call Booking Detail and add the response showing CANCELLED.` };
      if ((m = first.match(/^(\d+) test booking/))) {
        const ids = msg.split("\n").slice(1).map((l) => l.replace(/\s*\[[^\]]*\]\s*$/, "").replace(" : created in ", " (") + ")").filter((l) => l.length > 2);
        return { problem: `${m[1]} test booking(s) have no Booking Detail showing CANCELLED: ${ids.join(", ")}.`, fix: "Cancel these bookings, call Booking Detail for each and add the responses (showing CANCELLED) to the Test Case 14 folder." };
      }
      break;
    case "JSON_PARSE": {
      const file = first.split(":")[0];
      const where = field("Where"), why = field("Problem"), text = field("Text");
      return { problem: `The file "${file}" is not valid JSON${where ? ` (${where})` : ""}${why ? `: ${why}` : ""}.`,
               fix: text ? `Open "${file}" and fix the JSON near: ${text}` : `Open "${file}" and fix the JSON, or replace it with the correct response.` };
    }
  }
  return { problem: first, fix: (RULES[f.rule] || [, ""])[1] || "" };
}

const BINARY_EXTS = new Set([
  "jpg","jpeg","png","gif","bmp","ico","svg","webp","tiff",
  "mp3","mp4","mov","avi","mkv","wav","flac",
  "pdf","doc","docx","xls","xlsx","ppt","pptx",
  "zip","rar","7z","tar","gz","bz2",
  "exe","dll","so","dylib","bin","dat","db","sqlite","mdb",
  "class","jar","pyc","o","a",
]);

const $ = (id) => document.getElementById(id);
let lastResults = null; // [{tc, row, state, errors, notes}]

function esc(s) {
  return String(s).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
}

function caseNumber(name) {
  const s = String(name);
  // Prefer the number that follows "case" / "tc" / "test" (e.g. "UAT V3 Test Case 05" -> 5)
  let m = s.match(/(?:case|tc|test)[\s_-]*0*(\d{1,2})(?!\d)/i);
  if (m) return parseInt(m[1], 10);
  // Otherwise use the last number in the name
  const all = s.match(/\d{1,2}(?!\d)/g);
  return all ? parseInt(all[all.length - 1], 10) : null;
}

// Combine the fixed requirement list with the server's results
function buildModel(payload) {
  const byNum = new Map();
  const extras = [];
  (payload ? payload.results : []).forEach((row) => {
    const n = caseNumber(row.case);
    if (n && TEST_CASES.some((t) => t.n === n) && !byNum.has(n)) byNum.set(n, row);
    else extras.push(row);
  });

  const model = TEST_CASES.map((tc) => {
    const row = byNum.get(tc.n) || null;
    return evaluate(tc, row);
  });
  extras.forEach((row) => {
    model.push(evaluate({ n: null, title: row.case, desc: "Extra folder (not part of the 14 certification cases)" }, row));
  });
  return model;
}

function evaluate(tc, row) {
  if (!row) return { tc, row: null, state: "missing", errors: [], notes: [] };
  const errors = row.findings.filter((f) => f.severity === "ERROR");
  // Policy-only / cleanup cases are not expected to have a full booking flow
  const notes = row.findings.filter((f) => f.severity === "WARN" && (!tc.infoOnly || /accepted in UAT/.test(f.message)));
  return { tc, row, state: errors.length ? "fail" : "pass", errors, notes };
}

function problemHtml(f) {
  const { problem, fix } = explain(f);
  const rows = kvRowsHtml(f);
  return `<li><span class="msg">${esc(problem)}</span>` + (fix ? `<span class="fix"><b>How to fix:</b> ${esc(fix)}</span>` : "")
    + (rows ? `<div class="kvs in-problem">${rows}</div>` : "") + `</li>`;
}

// ---- Simple error report: only what is wrong and how to fix it ----
function errorReportItems() {
  const out = [];
  (lastResults && lastResults.model || []).forEach((m) => {
    const name = m.tc.n ? `Test Case ${m.tc.n}` : m.tc.title;
    if (m.state === "missing") out.push({ m, name, items: [{ problem: "This test case folder was not found in your upload.", fix: `Add a folder named "${name}" with its request and response files.` }] });
    else if (m.errors.length) out.push({ m, name, items: m.errors.map(explain) });
  });
  return out;
}

function renderErrorReport() {
  const groups = errorReportItems();
  const total = groups.reduce((n, g) => n + g.items.length, 0);
  if (!groups.length) {
    const mail = lastResults && lastResults.payload && lastResults.payload.certification_mail;
    const next = mail === "sent" && lastResults.payload.certified ? "The Tripjack certification team has been informed and will contact you."
      : "You are ready to submit for certification.";
    $("errorReport").innerHTML = `<div class="er-ok"><div class="er-ok-icon">✓</div><div><b>No errors found.</b><br>All 14 test cases passed. ${next}</div></div>`;
    return;
  }
  $("errorReport").innerHTML = `<p class="er-sum"><b>${plural(total, "error")}</b> in <b>${plural(groups.length, "test case")}</b>. Fix each one as shown, then upload again.</p>` +
    groups.map((g) => `<div class="er-group">
      <div class="er-head"><span class="badge ${g.m.state}">${g.m.state === "missing" ? "NOT UPLOADED" : "FAIL"}</span><b>${esc(g.name)}</b><span class="er-desc">${esc(g.m.tc.desc)}</span></div>
      <ol class="er-list">${g.items.map((it) => `<li>
        <div class="er-problem"><span class="er-tag bad">Error</span>${esc(it.problem)}</div>
        ${it.fix ? `<div class="er-fix"><span class="er-tag good">How to fix</span>${esc(it.fix)}</div>` : ""}
      </li>`).join("")}</ol>
    </div>`).join("");
}

let currentView = "errors";
function setView(v, remember = true) {
  if (remember) currentView = v;
  $("errorView").classList.toggle("hidden", v !== "errors");
  $("casesView").classList.toggle("hidden", v !== "cases");
  document.querySelectorAll("#viewTabs .vtab").forEach((b) => b.classList.toggle("active", b.dataset.view === v));
}

// Compact problem for the card; full text is in "View details"
function shortProblemHtml(f) {
  const { problem, fix } = explain(f);
  return `<li><span class="msg">${esc(problem)}</span>` + (fix ? `<span class="fix">✔ ${esc(fix)}</span>` : "") + `</li>`;
}

const nums = (s) => (String(s || "").match(/\d+/g) || []).map(Number);
const plural = (n, w, ws) => `${n} ${n === 1 ? w : ws || w + "s"}`;

// Requirement vs what the partner actually sent, with a tick where they can be compared
function compareHtml(tc, row) {
  const q = row && row.request && (row.request.check_in || (row.request.rooms || []).length) ? row.request : null;
  const rooms = q ? q.rooms || [] : [];
  const tick = (ok) => ok == null ? "" : ok ? '<span class="ok">✓</span>' : '<span class="bad">✗</span>';
  const same = (a, b) => a.length === b.length && a.every((x, i) => x === b[i]);
  const exact = (txt) => !/\(/.test(txt || "");

  const lines = [];
  if (tc.city) lines.push(["Search", tc.city, null, null, true]);
  if (tc.rooms) lines.push(["Rooms", tc.rooms, q ? String(rooms.length) : null, q ? Number(tc.rooms) === rooms.length : null]);
  if (tc.adults) {
    const got = rooms.map((r) => r.adults);
    lines.push(["Adults", tc.adults, q ? got.join(", ") : null, q && exact(tc.adults) ? same(nums(tc.adults), got) : null]);
  }
  if (tc.children) {
    const got = rooms.map((r) => r.children);
    const ages = rooms.some((r) => r.childAge && r.childAge.length)
      ? " (ages " + rooms.map((r) => (r.childAge || []).join("/") || "-").join(", ") + ")" : "";
    lines.push(["Children", tc.children, q ? got.join(", ") + ages : null, q && exact(tc.children) ? same(nums(tc.children), got) : null]);
  }
  if (q) {
    const nights = q.nights != null && q.nights >= 0 ? ` (${plural(q.nights, "night")})` : "";
    lines.push(["Check-in / out", "", `${q.check_in || "-"} → ${q.check_out || "-"}${nights}`, null]);
    const extra = [q.nationality ? `Nationality ${q.nationality}` : "", q.currency || ""].filter(Boolean).join(" · ");
    if (extra) lines.push(["Nationality / currency", "", extra, null]);
  }
  if (!lines.length) return "";

  if (!q) {
    return `<div class="section-label">Requirement</div><table class="compare"><tbody>` +
      lines.map(([k, need]) => `<tr><td>${esc(k)}</td><td class="val">${esc(need)}</td></tr>`).join("") + `</tbody></table>`;
  }
  return `<div class="section-label">Requirement vs your request</div><table class="compare">
    <thead><tr><th></th><th>Required</th><th>You sent</th><th></th></tr></thead><tbody>` +
    lines.map(([k, need, got, ok, wide]) => wide ? `<tr><td>${esc(k)}</td><td class="val" colspan="3">${esc(need)}</td></tr>` : `<tr><td>${esc(k)}</td><td class="val">${esc(need || "—")}</td>
      <td class="val">${esc(got || "—")}</td><td class="tk">${tick(ok)}</td></tr>`).join("") + `</tbody></table>`;
}

function statusPill(status, wantCancelled) {
  const s = String(status).toUpperCase();
  const good = wantCancelled ? /CANCEL+ED/.test(s) : !/FAIL|PENDING|REJECT/.test(s);
  return `<span class="status-pill ${good ? "good" : "bad"}">${esc(s)}</span>`;
}

let currentFilter = "all";

function applyFilter() {
  let shown = 0;
  document.querySelectorAll("#cases .case").forEach((el) => {
    const on = currentFilter === "all" || el.dataset.state === currentFilter;
    el.classList.toggle("hidden", !on);
    if (on) shown++;
  });
  document.querySelectorAll("#filters .filter").forEach((b) => b.classList.toggle("active", b.dataset.filter === currentFilter));
  $("emptyFilter").classList.toggle("hidden", shown > 0);
}

function renderCases() {
  const model = buildModel(lastResults ? lastResults.payload : null);
  const uploaded = !!(lastResults && lastResults.payload);
  lastResults = { payload: lastResults ? lastResults.payload : null, model };

  $("cases").innerHTML = model.map((m, idx) => {
    const { tc, row, state } = m;
    const label = { pass: "✓ PASS", fail: "✗ FAIL", missing: uploaded ? "NOT UPLOADED" : "WAITING" }[state];

    let body = compareHtml(tc, row);
    if (tc.note) body += `<p class="callout tip">${esc(tc.note)}</p>`;
    if (bookingDetailNote(tc)) body += `<p class="callout info">${esc(bookingDetailNote(tc))}</p>`;

    let footer = "";
    if (row) {
      const facts = [
        row.hotel_name ? `<div>Hotel: <b>${esc(row.hotel_name)}</b></div>` : "",
        row.booking_status ? `<div>Booking status: ${statusPill(row.booking_status, false)}</div>` : "",
        row.booking_status_after_cancel ? `<div>After cancel: ${statusPill(row.booking_status_after_cancel, true)}</div>` : "",
      ].filter(Boolean).join("");
      if (facts) body += `<div class="section-label">Booking</div><div class="facts" style="margin-top:0">${facts}</div>`;

      if (m.errors.length) {
        body += `<div class="section-label">${plural(m.errors.length, "thing")} to fix</div><ul class="problems">${m.errors.slice(0, 3).map(shortProblemHtml).join("")}</ul>` +
          (m.errors.length > 3 ? `<div class="more">+ ${plural(m.errors.length - 3, "more issue")} — see details</div>` : "");
      } else {
        body += `<div class="allgood">✓ All checks passed${m.notes.length ? ` (${plural(m.notes.length, "note")})` : ""}</div>`;
      }

      const passed = row.findings.filter((f) => f.severity === "INFO").length;
      footer = `<div class="case-foot">
        <span class="counts">${plural(passed, "check")} passed${m.notes.length ? ` · ${plural(m.notes.length, "note")}` : ""}</span>
        <button type="button" class="btn small" data-idx="${idx}">View details →</button>
      </div>`;
    } else {
      body += `<div class="waiting">${uploaded ? "No folder for this test case was found in your upload." : "Upload your files to check this test case."}</div>`;
    }

    return `<article class="case ${state}" data-state="${state}">
      <div class="case-top">
        <div class="case-num">${tc.n || "+"}</div>
        <div class="case-head"><div class="case-no">${tc.n ? "TEST CASE " + tc.n : esc(tc.title)}</div><h3 class="case-title">${esc(tc.desc)}</h3></div>
        <span class="badge ${state}">${label}</span>
      </div>
      ${body}
      ${footer}
    </article>`;
  }).join("");

  const count = (s) => model.filter((m) => m.state === s).length;
  const pass = count("pass");
  $("nAll").textContent = model.length;
  $("nPass").textContent = pass;
  $("nFail").textContent = count("fail");
  $("nMissing").textContent = count("missing");
  $("progressText").textContent = `${pass} of ${TEST_CASES.length}`;
  $("progressBar").style.width = `${Math.min(100, (pass / TEST_CASES.length) * 100)}%`;
  applyFilter();
  renderErrorReport();
  $("viewTabs").classList.toggle("hidden", !uploaded);
  setView(uploaded ? currentView : "cases", false);
}


// ---- Details pop-up ----
// "label : value [matched]" lines under a finding's first line, as a table with ✓ / ✗
function kvRowsHtml(f) {
  return String(f.message).split("\n").slice(1).filter((l) => l.trim()).map((line) => {
    let key, val;
    const i = line.indexOf(" : ");
    const j = line.indexOf(" — ");
    if (i !== -1) { key = line.slice(0, i); val = line.slice(i + 3); }
    else if (j !== -1) { key = line.slice(0, j); val = line.slice(j + 3); }
    else return `<div class="kv plain">${esc(line.trim())}</div>`;
    const tag = /\[(matched|MATCH)\]/i.test(val) ? "ok" : /\[(unmatched|MISMATCH|NOT FOUND)\]/i.test(val) ? "bad" : "";
    val = val.replace(/\s*\[(matched|unmatched|MATCH|MISMATCH|NOT FOUND)\]/gi, "");
    return `<div class="kv"><span class="k">${esc(key.trim())}</span><span class="v">${esc(val.trim())}</span>${tag ? `<span class="tick ${tag}">${tag === "ok" ? "✓" : "✗"}</span>` : ""}</div>`;
  }).join("");
}

function checkHtml(f) {
  const label = (RULES[f.rule] || [f.rule])[0];
  const first = String(f.message).split("\n")[0];
  const rows = kvRowsHtml(f);
  const bad = rows.includes('tick bad');
  return `<div class="check"><div class="check-head"><span class="tick ${bad ? "bad" : "ok"}">${bad ? "✗" : "✓"}</span><b>${esc(label)}</b><span class="check-sum">${esc(first)}</span></div>${rows ? `<div class="kvs">${rows}</div>` : ""}</div>`;
}

function openDetails(idx) {
  const m = lastResults.model[idx];
  const { tc, row } = m;
  const infos = row.findings.filter((f) => f.severity === "INFO");
  $("modalTitle").textContent = tc.n ? `Test Case ${tc.n} — ${tc.desc}` : `${tc.title}`;
  let html = "";
  if (m.errors.length) html += `<h4>Problems</h4><ul class="problems">${m.errors.map(problemHtml).join("")}</ul>`;
  if (m.notes.length) html += `<h4>Notes (not blocking)</h4><ul class="problems notes">${m.notes.map(problemHtml).join("")}</ul>`;
  html += `<h4>Checks passed (${infos.length})</h4>${infos.map(checkHtml).join("") || '<p class="note">None</p>'}`;
  $("modalBody").innerHTML = html;
  $("modal").classList.remove("hidden");
}
function closeDetails() { $("modal").classList.add("hidden"); }

function showStatus(msg, isError, busy) {
  const el = $("status");
  el.textContent = msg;
  el.classList.toggle("hidden", !msg);
  el.classList.toggle("error", !!isError);
  el.classList.toggle("busy", !!busy);
}

function setBusy(on) {
  $("folderBtn").disabled = on;
}

async function send(url, options, busyMsg, sourceName) {
  setBusy(true);
  showStatus(busyMsg, false, true);
  // Drop the previous upload so old data can never be mistaken for the new one
  lastResults = null;
  $("overview").classList.add("hidden");
  renderCases();
  try {
    const res = await fetch(url, options);
    const data = await res.json().catch(() => ({}));
    if (res.status === 401) throw new Error("Your sign-in has expired. Refresh the page and sign in again.");
    if (res.status === 413) throw new Error("The folder is too large to upload (max about 4 MB). Remove files that are not test case requests/responses and try again.");
    if (!res.ok) throw new Error(data.error || res.statusText);
    lastResults = { payload: data };
    currentView = "errors";
    $("source").textContent = `Results for: ${sourceName || data.source_folder || "your upload"}`;
    $("overview").classList.remove("hidden");
    renderCases();
    showStatus("", false);
    $("overview").scrollIntoView({ behavior: "smooth", block: "start" });
  } catch (err) {
    showStatus(`Could not check your files: ${err.message}`, true);
  } finally {
    setBusy(false);
  }
}

function uploadZip(file) {
  if (!file) return;
  if (!file.name.toLowerCase().endsWith(".zip")) return showStatus("Please choose a .zip file.", true);
  if (file.size > 100 * 1024 * 1024) return showStatus("ZIP is too large (max 100 MB).", true);
  send("/api/upload-zip", { method: "POST", headers: { "Content-Type": "application/zip" }, body: file }, "Checking your ZIP…", file.name);
}

function uploadFolder(files) {
  const usable = Array.from(files).filter((f) => {
    if (/^[.~$]/.test(f.name)) return false;
    const ext = f.name.includes(".") ? f.name.split(".").pop().toLowerCase() : "";
    return !BINARY_EXTS.has(ext);
  });
  if (!usable.length) return showStatus("No usable files found in that folder.", true);
  if (!partner) return showStatus("Please fill in your details first.", true);
  const form = new FormData();
  Object.entries(partner).forEach(([k, v]) => form.append(k, v));
  usable.forEach((f) => form.append("files", f, f._relPath || f.webkitRelativePath || f.name));
  send("/api/upload_folder", { method: "POST", body: form }, `Checking ${usable.length} files…`,
    (usable[0]._relPath || usable[0].webkitRelativePath || "").split("/")[0] || "your folder");
}

function csvCell(v) {
  const s = String(v == null ? "" : v);
  return /[",\n\r]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
}

function saveCsv(rows, name) {
  const csv = "\uFEFF" + rows.map((r) => r.map(csvCell).join(",")).join("\r\n");
  const a = document.createElement("a");
  a.href = URL.createObjectURL(new Blob([csv], { type: "text/csv;charset=utf-8" }));
  a.download = `${name}_${new Date().toISOString().slice(0, 10)}.csv`;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(a.href);
}

// Simple report: only the errors and how to fix them
function downloadErrorReport() {
  if (!lastResults || !lastResults.model) return;
  const rows = [["Test Case", "Description", "Result", "No.", "What is wrong", "How to fix"]];
  const groups = errorReportItems();
  groups.forEach((g) => g.items.forEach((it, i) =>
    rows.push([g.name, g.m.tc.desc, g.m.state === "missing" ? "NOT UPLOADED" : "FAIL", i + 1, it.problem, it.fix])));
  lastResults.model.filter((m) => m.state === "pass").forEach((m) =>
    rows.push([m.tc.n ? `Test Case ${m.tc.n}` : m.tc.title, m.tc.desc, "PASS", "", "No errors", ""]));
  saveCsv([...partnerRows(), ...rows], "hotel_certification_errors");
}

// Detailed report: one row per check (problem / note / passed) for every test case
function downloadReport() {
  if (!lastResults || !lastResults.model) return;
  const header = [
    "Test Case", "Description", "Search City", "Rooms", "Adults", "Children", "Requirement Note",
    "Check-in (your request)", "Check-out (your request)", "Nights", "Rooms (your request)", "Guests per room (your request)",
    "Result", "Hotel", "Booking Status", "Booking Status After Cancel",
    "Severity", "Check", "Details", "How To Fix",
  ];
  const rows = [header];
  const label = (rule) => (RULES[rule] || [rule])[0];

  lastResults.model.forEach(({ tc, row, state, errors, notes }) => {
    const base = [
      tc.n ? `Test Case ${tc.n}` : tc.title, tc.desc, tc.city || "", tc.rooms || "", tc.adults || "", tc.children || "", [tc.note, bookingDetailNote(tc)].filter(Boolean).join(" "),
      ...(() => { const q = (row && row.request) || {}; const rs = q.rooms || [];
        return [q.check_in || "", q.check_out || "", q.nights != null ? q.nights : "", rs.length || "",
          rs.map((x, i) => `Room ${i + 1}: ${x.adults}A ${x.children}C${x.childAge && x.childAge.length ? " (ages " + x.childAge.join("/") + ")" : ""}`).join(" | ")]; })(),
      state === "missing" ? "NOT UPLOADED" : state.toUpperCase(),
      row && row.hotel_name || "", row && row.booking_status || "", row && row.booking_status_after_cancel || "",
    ];
    if (!row) {
      rows.push([...base, "", "", "No folder for this test case was found in the upload", "Upload this test case folder"]);
      return;
    }
    const add = (sev, f) => {
      const ex = sev === "PASSED" ? null : explain(f);
      rows.push([...base, sev, label(f.rule), ex ? `${ex.problem}\n\n${f.message}` : f.message, ex ? ex.fix : ""]);
    };
    errors.forEach((f) => add("ERROR", f));
    notes.forEach((f) => add("NOTE", f));
    row.findings.filter((f) => f.severity === "INFO").forEach((f) => add("PASSED", f));
  });

  saveCsv([...partnerRows(), ...rows], "hotel_certification_report");
}

// ---- Partner details: filled in once before the upload ----
const DETAIL_FIELDS = [
  ["name", "Full name"], ["company", "Company name"], ["tjUserId", "TJ user ID"], ["phone", "Phone number"], ["email", "Email ID"],
];
let partner = null;

function checkDetails(d) {
  const bad = {};
  if (d.name.length < 2) bad.name = "Enter your full name.";
  if (d.company.length < 2) bad.company = "Enter your company name.";
  if (!/^[A-Za-z0-9._-]{3,40}$/.test(d.tjUserId)) bad.tjUserId = "Enter a valid TJ user ID (letters and numbers only).";
  const digits = d.phone.replace(/[\s()-]/g, "").replace(/^(\+91|0091|0)/, "");
  if (!/^[6-9]\d{9}$/.test(digits)) bad.phone = "Enter a valid 10-digit mobile number.";
  if (!/^[^\s@]+@[^\s@]+\.[^\s@]{2,}$/.test(d.email)) bad.email = "Enter a valid email ID.";
  return bad;
}

// Everyone who has registered on this browser, keyed by email, so a returning
// user signs straight back in instead of filling the form again.
// Details are locked once submitted: there is no edit, and registering the same
// email again keeps the first details.
function loadAccounts() {
  try {
    const all = JSON.parse(localStorage.getItem("tjAccounts") || "{}");
    const old = JSON.parse(localStorage.getItem("tjPartner") || "null");  // details saved before this list existed
    if (old && old.email && !all[old.email.toLowerCase()]) all[old.email.toLowerCase()] = old;
    return Object.fromEntries(Object.entries(all).filter(([, d]) => d && !Object.keys(checkDetails(d)).length));
  } catch (_) { return {}; }
}
function saveAccounts(all) { try { localStorage.setItem("tjAccounts", JSON.stringify(all)); } catch (_) {} }
function rememberAccount(d) {
  const all = loadAccounts();
  const key = d.email.toLowerCase();
  if (!all[key]) { all[key] = d; saveAccounts(all); }
  return all[key];
}
function signInAs(d) {
  partner = d;
  try { localStorage.setItem("tjPartner", JSON.stringify(d)); } catch (_) {}
  showPartner();
}

function renderKnownAccounts(show) {
  const box = $("knownAccounts");
  const list = Object.values(loadAccounts());
  box.classList.toggle("hidden", !show || !list.length);
  if (!show || !list.length) { box.innerHTML = ""; return; }
  box.innerHTML = `<div class="known-title">Already registered? Continue as</div>` + list.map((d, i) => `
    <div class="known-row">
      <button type="button" class="known-go" data-i="${i}"><span class="who-icon">👤</span>
        <span><b>${esc(d.name)}</b> · ${esc(d.company)}<small>${esc(d.email)} · TJ ID ${esc(d.tjUserId)}</small></span></button>
    </div>`).join("") + `<div class="known-or">or register a new user below</div>`;
  box.querySelectorAll(".known-go").forEach((b) => { b.onclick = () => signInAs(list[+b.dataset.i]); });
}

// Typing an email that is already registered shows its saved (locked) details
$("detailsForm").elements.email.addEventListener("change", (e) => {
  const d = loadAccounts()[e.target.value.trim().toLowerCase()];
  if (!d) return;
  DETAIL_FIELDS.forEach(([k]) => { e.target.form.elements[k].value = d[k]; });
});

// Without Google/Microsoft sign-in, the details form is the sign-in page:
// until it is submitted, only the form is shown (no upload box or results).
function showPartner() {
  const on = !!partner;
  const signedOut = !on && !authUser;
  document.body.classList.toggle("signed-out", signedOut);
  $("detailsTitle").textContent = signedOut ? "Sign in to continue" : "Your details";
  $("detailsHint").textContent = signedOut
    ? "Enter your details to start checking your Hotel API V3 UAT test cases. Fields marked * are required."
    : "Fill this in once before you upload. Fields marked * are required.";
  $("detailsSubmit").textContent = signedOut ? "Sign in →" : "Submit & continue to upload →";
  renderKnownAccounts(signedOut);
  $("detailsSection").classList.toggle("hidden", on);
  $("whoBar").classList.toggle("hidden", !on);
  $("dropZone").classList.toggle("hidden", !on);
  if (on) $("whoText").innerHTML = `Uploading as <b>${esc(partner.name)}</b> · ${esc(partner.company)} <span>· TJ ID ${esc(partner.tjUserId)} · ${esc(partner.phone)} · ${esc(partner.email)}</span>`;
  updateUserChip();
}

// Top-bar account chip with Log out: shown when signed in, or once details are submitted
function updateUserChip() {
  const who = authUser ? authUser.email : partner ? partner.email : "";
  $("userEmail").textContent = who;
  $("userChip").classList.toggle("hidden", !who);
}

function partnerRows() {
  if (!partner) return [];
  return [...DETAIL_FIELDS.map(([k, label]) => [label, partner[k]]), ["Checked on", new Date().toLocaleString()], []];
}

$("detailsForm").addEventListener("submit", (e) => {
  e.preventDefault();
  const form = e.target;
  const d = {};
  DETAIL_FIELDS.forEach(([k]) => { d[k] = form.elements[k].value.trim(); });
  const bad = checkDetails(d);
  DETAIL_FIELDS.forEach(([k]) => form.elements[k].classList.toggle("invalid", !!bad[k]));
  const msgs = Object.values(bad);
  $("detailsError").textContent = msgs.join(" ");
  $("detailsError").classList.toggle("hidden", !msgs.length);
  if (msgs.length) { form.elements[Object.keys(bad)[0]].focus(); return; }
  signInAs(rememberAccount(d));  // an already-registered email keeps its first details
  $("dropZone").scrollIntoView({ behavior: "smooth", block: "start" });
});

// Saved details are reused only for the same signed-in account
function restorePartner() {
  try {
    if (authUser) {
      // Google / Microsoft account: reuse the details registered for that email
      partner = loadAccounts()[authUser.email.toLowerCase()] || null;
    } else {
      const saved = JSON.parse(localStorage.getItem("tjPartner") || "null");
      if (saved && !Object.keys(checkDetails(saved)).length) partner = saved;
    }
  } catch (_) {}
  const form = $("detailsForm");
  if (authUser) {
    if (!form.elements.name.value) form.elements.name.value = authUser.name || "";
    form.elements.email.value = authUser.email;
    form.elements.email.readOnly = true;
  }
  showPartner();
}

// ---- Sign in with Google / Microsoft (OpenID Connect, id_token) ----
let authUser = null;
const AUTH_URLS = {
  google: "https://accounts.google.com/o/oauth2/v2/auth",
  microsoft: "https://login.microsoftonline.com/common/oauth2/v2.0/authorize",
};

function randomHex() {
  const a = new Uint8Array(16);
  crypto.getRandomValues(a);
  return Array.from(a, (b) => b.toString(16).padStart(2, "0")).join("");
}

function startLogin(provider, clientId) {
  const nonce = randomHex();
  const state = `${provider}.${randomHex()}`;
  try { sessionStorage.setItem("tjAuth", JSON.stringify({ provider, nonce, state })); } catch (_) {}
  const q = new URLSearchParams({
    client_id: clientId, redirect_uri: location.origin + "/", response_type: "id_token",
    scope: "openid email profile", nonce, state, prompt: "select_account",
  });
  if (provider === "microsoft") q.set("response_mode", "fragment");
  location.assign(`${AUTH_URLS[provider]}?${q}`);
}

// Back from Google / Microsoft with #id_token=…: let the server check it and set the session cookie
async function finishLogin() {
  const h = new URLSearchParams(location.hash.slice(1));
  if (!h.has("id_token") && !h.has("error")) return;
  history.replaceState(null, "", location.pathname + location.search);
  let saved = null;
  try { saved = JSON.parse(sessionStorage.getItem("tjAuth") || "null"); sessionStorage.removeItem("tjAuth"); } catch (_) {}
  if (h.has("error")) throw new Error(h.get("error_description") || h.get("error"));
  if (!saved || saved.state !== h.get("state")) throw new Error("The sign-in took too long or was opened in another tab. Please try again.");
  const res = await fetch("/api/login", {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ provider: saved.provider, id_token: h.get("id_token"), nonce: saved.nonce }),
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.error || res.statusText);
}

function showLogin(cfg, error) {
  $("appMain").classList.add("hidden");
  $("loginScreen").classList.remove("hidden");
  [["google", cfg.google_client_id], ["microsoft", cfg.microsoft_client_id]].forEach(([p, id]) => {
    const b = $(`${p}Btn`);
    b.classList.toggle("hidden", !id);
    b.onclick = () => { b.disabled = true; startLogin(p, id); };
  });
  $("loginError").textContent = error ? `Sign-in failed: ${error}` : "";
  $("loginError").classList.toggle("hidden", !error);
}

function showApp() {
  $("loginScreen").classList.add("hidden");
  $("appMain").classList.remove("hidden");
  restorePartner();
}

// Log out: end the session. Registered details stay, so next time it is one click
// ("Continue as …"); the × next to a name forgets it on this browser.
$("signOutBtn").addEventListener("click", async () => {
  if (!confirm("Log out?")) return;
  try { localStorage.removeItem("tjPartner"); } catch (_) {}
  await fetch("/api/logout", { method: "POST" }).catch(() => {});
  location.reload();
});

(async function initAuth() {
  let cfg = { auth: false };
  try { const r = await fetch("/api/config"); if (r.ok) cfg = await r.json(); } catch (_) {}
  if (!cfg.auth) return showApp();  // sign-in not configured: open access
  let error = "";
  try { await finishLogin(); } catch (e) { error = e.message; }
  const res = await fetch("/api/me").catch(() => null);
  authUser = res && res.ok ? (await res.json()).user : null;
  if (!authUser) return showLogin(cfg, error);
  showApp();
})();

// Explain the browser's own "Upload N files?" prompt before it appears
const openFolderModal = () => { $("folderModal").classList.remove("hidden"); $("fmGo").focus(); };
const closeFolderModal = () => $("folderModal").classList.add("hidden");
$("folderBtn").addEventListener("click", openFolderModal);
$("fmCancel").addEventListener("click", closeFolderModal);
$("fmGo").addEventListener("click", () => { closeFolderModal(); $("folderInput").click(); });
$("folderModal").addEventListener("click", (e) => { if (e.target === $("folderModal")) closeFolderModal(); });
$("folderInput").addEventListener("change", (e) => { uploadFolder(e.target.files); e.target.value = ""; });
$("downloadBtn").addEventListener("click", downloadErrorReport);
$("downloadFullBtn").addEventListener("click", downloadReport);
$("viewTabs").addEventListener("click", (e) => {
  const b = e.target.closest("[data-view]");
  if (b) setView(b.dataset.view);
});

const dz = $("dropZone");
dz.addEventListener("dragover", (e) => { e.preventDefault(); dz.classList.add("dragover"); });
dz.addEventListener("dragleave", () => dz.classList.remove("dragover"));
// Read every file inside a dropped folder (drag & drop does not show the browser's "Upload N files?" prompt)
function readEntry(entry, path, out) {
  if (entry.isFile) {
    return new Promise((res) => entry.file((f) => { f._relPath = path + f.name; out.push(f); res(); }, () => res()));
  }
  if (!entry.isDirectory) return Promise.resolve();
  const reader = entry.createReader();
  const all = [];
  const next = () => new Promise((res) => reader.readEntries((batch) => res(batch), () => res([])));
  return (async () => {
    for (let batch = await next(); batch.length; batch = await next()) all.push(...batch);
    await Promise.all(all.map((c) => readEntry(c, path + entry.name + "/", out)));
  })();
}

dz.addEventListener("drop", async (e) => {
  e.preventDefault();
  dz.classList.remove("dragover");
  const entries = Array.from(e.dataTransfer.items || [])
    .map((it) => (it.webkitGetAsEntry ? it.webkitGetAsEntry() : null)).filter(Boolean);
  if (entries.some((en) => en.isDirectory)) {
    showStatus("Reading your folder…", false, true);
    const files = [];
    await Promise.all(entries.map((en) => readEntry(en, "", files)));
    uploadFolder(files);
  } else {
    showStatus("Please unzip your file first, then drag or choose the unzipped folder.", true);
  }
});

renderCases();

$("cases").addEventListener("click", (e) => {
  const b = e.target.closest("[data-idx]");
  if (b) openDetails(parseInt(b.dataset.idx, 10));
});
$("filters").addEventListener("click", (e) => {
  const b = e.target.closest("[data-filter]");
  if (b) { currentFilter = b.dataset.filter; applyFilter(); }
});
$("modalClose").addEventListener("click", closeDetails);
$("modal").addEventListener("click", (e) => { if (e.target === $("modal")) closeDetails(); });
document.addEventListener("keydown", (e) => { if (e.key === "Escape") { closeDetails(); closeFolderModal(); } });
