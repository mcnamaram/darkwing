/**
 * Google Apps Script doPost handler for DarkWing.
 *
 * Receives a flat JSON object from the Python package and submits it as a
 * Google Form response on behalf of the deploying user.
 *
 * Deploy as Web App:
 *   - Execute as: Me (the deployer)
 *   - Who has access: Anyone with Google account (or "Anyone" if public)
 *   - The Python side sends a Bearer token; the script runs in the
 *     deployer's context so the form submission is authenticated.
 *
 * Expected JSON payload keys (clean, internal names from Python):
 *   - tower_id             (string)
 *   - date                 (string, e.g. "06/15/2026")
 *   - time_of_day          (string, e.g. "06:00")
 *   - adult_swallows_in_chimney (integer)
 *   - nesting_stage        (string)
 *   - bill_use             (string)
 *   - adults_flew_in       (array of strings)
 *   - swallows_near_nest   (integer)
 *   - awake                (string)
 *   - notes                (string)
 *
 * TITLE_MAP below translates these clean keys to the actual Google Form item
 * titles. If a form question is renamed, update TITLE_MAP here — no Python
 * changes needed.
 */

/**
 * Clean payload key → Google Form item title mapping.
 *
 * Update this when form questions are renamed; the Python side never needs
 * to know the long titles.
 */
var TITLE_MAP = {
  "tower_id": "Tower Number",
  "date": "Date of footage being analyzed (please input date in this format M/D/YYYY)",
  "time_of_day": "Approximate minutes after the hour. There should be three entries per hour. If no bird is in the chimney at 00, 20, or 40 then scan ahead, minute-by-minute to the next time when a bird is present.",
  "adult_swallows_in_chimney": "How many adult Swifts are inside the chimney? Give your best guess.",
  "nesting_stage": "Stage in the Nesting Cycle",
  "bill_use": "Do any of the adults have something in their bill, or are using their bill?",
  "adults_flew_in": "Did you observe any flight(s) going in or out of the chimney during the 1-minute video segment you watched? Did you observe any flights of Swifts inside the chimney, such as when they are changing position inside?",
  "swallows_near_nest": "How many adults are within two body-lengths of the nest? Examples include sitting on nest, perched next to it, perched underneath it, or perched above it. If a group of Swifts are perched next to one another, include all of them in your count.",
  "awake": "Are there any adults awake with eyes open?",
  "notes": "Note any interesting behaviors not already included on this form. Include social interactions that could be characterized as courtship or aggressive. Do not try to interpret the behaviors; just state what you observed."
};

/**
 * Handle POST requests from the Python client.
 *
 * @param {Object} e The event object with e.postData.contents containing JSON.
 * @return {ContentService.JsonOutput} JSON response.
 */
function doPost(e) {
  var payload;
  try {
    payload = JSON.parse(e.postData.contents);
  } catch (err) {
    return failResponse("Invalid JSON: " + err.message);
  }

  var form = getForm_();
  if (!form) {
    return failResponse("Form not found. Check FORM_ID in this script's properties.");
  }

  var response = form.createResponse();

  // Walk the form's items and match by clean key → title lookup.
  var items = form.getItems();
  var matched = 0;
  for (var i = 0; i < items.length; i++) {
    var item = items[i];
    var title = item.getTitle();
    // Find the clean key that maps to this title, then look up its value.
    var cleanKey = null;
    for (var key in TITLE_MAP) {
      if (TITLE_MAP[key] === title) {
        cleanKey = key;
        break;
      }
    }
    if (!cleanKey) {
      continue; // Skip items not in TITLE_MAP (e.g. Email, Name)
    }
    var value = payload[cleanKey];

    if (value === undefined || value === null) {
      // Some fields may be optional — skip without error.
      continue;
    }

    try {
      answerItem_(response, item, value);
      matched++;
    } catch (err) {
      return failResponse("Error answering item '" + item.getTitle() + "': " + err.message);
    }
  }

  if (matched === 0) {
    return failResponse("No matching form items found for the provided payload. " +
                        "Payload keys: " + Object.keys(payload).join(", "));
  }

  try {
    response.submit();
    return successResponse({ matched: matched });
  } catch (err) {
    return failResponse("Failed to submit response: " + err.message);
  }
}

/**
 * Answer a single FormApp item with the given value, respecting the item type.
 *
 * @param {FormResponse} response The response builder.
 * @param {FormItem} item The form item.
 * @param {*} value The value to set.
 */
function answerItem_(response, item, value) {
  var type = item.getType();

  switch (type) {
    case FormApp.ItemType.TEXT:
    case FormApp.ItemType.PARAGRAPH_TEXT:
      response.withItemResponse(item.asTextQuestion().createResponse(String(value)));
      break;

    case FormApp.ItemType.MULTIPLE_CHOICE:
      // Try exact match first, then case-insensitive.
      var choice = findChoice_(item.asMultipleChoiceQuestion(), value);
      if (!choice) {
        throw new Error("No matching choice: " + value);
      }
      response.withItemResponse(item.asMultipleChoiceQuestion().createResponse(choice));
      break;

    case FormApp.ItemType.CHECKBOX:
      // value is an array of strings
      if (!Array.isArray(value)) {
        value = [value];
      }
      var choices = value.map(function(v) {
        var c = findChoice_(item.asCheckboxQuestion(), v);
        if (!c) throw new Error("No matching checkbox choice: " + v);
        return c;
      });
      response.withItemResponse(item.asCheckboxQuestion().createResponse(choices));
      break;

    case FormApp.ItemType.LIST:
      var choice = findChoice_(item.asListItemQuestion(), value);
      if (!choice) {
        throw new Error("No matching list choice: " + value);
      }
      response.withItemResponse(item.asListItemQuestion().createResponse(choice));
      break;

    case FormApp.ItemType.DATE:
      // Expect "MM/DD/YYYY" — Apps Script date items take a Date object.
      response.withItemResponse(
        item.asDateQuestion().createResponse(parseDate_(value))
      );
      break;

    case FormApp.ItemType.TIME:
      // Expect "HH:MM" — create a Date at epoch + the time offset.
      response.withItemResponse(
        item.asTimeQuestion().createResponse(parseTime_(value))
      );
      break;

    case FormApp.ItemType.DATE_TIME:
      // Accept either "MM/DD/YYYY HH:MM" or handle as combined.
      response.withItemResponse(
        item.asDateTimeQuestion().createResponse(parseDateTime_(value))
      );
      break;

    default:
      // For unknown types, try treating as text.
      response.withItemResponse(item.asTextQuestion().createResponse(String(value)));
      break;
  }
}

/**
 * Find a choice by value, case-insensitive.
 *
 * @param {MultipleChoiceQuestion} question
 * @param {string} value
 * @return {string|null} The matching choice text, or null.
 */
function findChoice_(question, value) {
  var choices = question.getChoices();
  for (var i = 0; i < choices.length; i++) {
    if (choices[i].getValue().toLowerCase() === value.toLowerCase()) {
      return choices[i].getValue();
    }
  }
  return null;
}

/**
 * Parse "MM/DD/YYYY" into a Date object (noon UTC to avoid timezone shifts).
 */
function parseDate_(str) {
  var parts = str.split("/");
  if (parts.length !== 3) throw new Error("Bad date format: " + str);
  var month = parseInt(parts[0], 10) - 1; // JS months are 0-based
  var day = parseInt(parts[1], 10);
  var year = parseInt(parts[2], 10);
  return new Date(Date.UTC(year, month, day));
}

/**
 * Parse "HH:MM" into a Date object (today's date, given time).
 */
function parseTime_(str) {
  var parts = str.split(":");
  if (parts.length !== 2) throw new Error("Bad time format: " + str);
  var now = new Date();
  return new Date(
    now.getFullYear(), now.getMonth(), now.getDate(),
    parseInt(parts[0], 10), parseInt(parts[1], 10), 0
  );
}

/**
 * Parse "MM/DD/YYYY HH:MM" into a Date object.
 */
function parseDateTime_(str) {
  var parts = str.trim().split(/\s+/);
  if (parts.length !== 2) throw new Error("Bad datetime format: " + str);
  var date = parseDate_(parts[0]);
  var timeParts = parts[1].split(":");
  date.setUTCHours(parseInt(timeParts[0], 10), parseInt(timeParts[1], 10), 0);
  return date;
}

/**
 * Get the Google Form from script properties.
 * FORM_ID must be set in the script's project properties.
 */
function getForm_() {
  var props = PropertiesService.getScriptProperties();
  var formId = props.getProperty("FORM_ID");
  if (!formId) {
    Logger.log("FORM_ID not set in script properties");
    return null;
  }
  return FormApp.openById(formId);
}

/**
 * Return a success JSON response.
 */
function successResponse(data) {
  return ContentService.createTextOutput(JSON.stringify({
    status: "success",
    response: data || {}
  })).setMimeType(ContentService.MimeType.JSON);
}

/**
 * Return an error JSON response.
 */
function failResponse(message) {
  return ContentService.createTextOutput(JSON.stringify({
    status: "error",
    message: message
  })).setMimeType(ContentService.MimeType.JSON);
}
