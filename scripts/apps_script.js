/**
 * DocIntel AI Google Sheets Integration
 * 
 * Instructions:
 * 1. Open your Google Sheet linked to the Google Form submissions.
 * 2. Click on Extensions -> Apps Script.
 * 3. Delete any code in the editor, and paste this entire script.
 * 4. Update the API_URL constant below with your actual deployed Vercel URL.
 * 5. Click Save.
 * 6. Set up a Time-Driven Trigger:
 *    - Click on the clock icon (Triggers) on the left sidebar.
 *    - Click "+ Add Trigger".
 *    - Choose "processNewSubmissions" as the function to run.
 *    - Select "Time-driven" as the event source.
 *    - Choose "Minutes timer" and select "Every 10 minutes".
 *    - Click Save (authorize any permissions requested).
 */

// Production API Endpoint URL
var API_URL = "https://docintel-ai-peach.vercel.app/api/resume-fit";

function processNewSubmissions() {
  var sheet = SpreadsheetApp.getActiveSpreadsheet().getSheetByName("Submissions");
  if (!sheet) {
    // Fallback to the first sheet if "Submissions" name isn't found
    sheet = SpreadsheetApp.getActiveSpreadsheet().getSheets()[0];
  }
  
  var lastRow = sheet.getLastRow();
  if (lastRow < 2) {
    Logger.log("No rows to process.");
    return;
  }
  
  // Columns Mapping (1-based index)
  // A: Timestamp, B: Name, C: Email, D: Resume File, E: Job Description,
  // F: Status, G: Matched Keywords, H: Missing Keywords, I: Match Score, J: Notes
  var COL_RESUME = 4;       // Column D
  var COL_JOB_DESC = 5;     // Column E
  var COL_STATUS = 6;       // Column F
  var COL_MATCHED_KW = 7;   // Column G
  var COL_MISSING_KW = 8;   // Column H
  var COL_MATCH_SCORE = 9;  // Column I
  var COL_NOTES = 10;       // Column J
  
  // Read all rows starting from row 2 (header is row 1)
  var range = sheet.getRange(2, 1, lastRow - 1, 10);
  var values = range.getValues();
  
  for (var i = 0; i < values.length; i++) {
    var rowNum = i + 2;
    var status = values[i][COL_STATUS - 1];
    
    if (status === "New" || status === "") {
      var resumeUrl = values[i][COL_RESUME - 1];
      var jobDesc = values[i][COL_JOB_DESC - 1];
      
      Logger.log("Processing Row " + rowNum + " - Resume: " + resumeUrl);
      
      if (!resumeUrl || !jobDesc) {
        sheet.getRange(rowNum, COL_STATUS).setValue("Processed");
        sheet.getRange(rowNum, COL_NOTES).setValue("Skipped: Missing resume URL or job description.");
        continue;
      }
      
      var fileId = getFileIdFromUrl(resumeUrl);
      if (!fileId) {
        sheet.getRange(rowNum, COL_STATUS).setValue("Processed");
        sheet.getRange(rowNum, COL_NOTES).setValue("Error: Invalid Google Drive file URL.");
        continue;
      }
      
      try {
        // Fetch file blob from Google Drive
        var file = DriveApp.getFileById(fileId);
        var fileBlob = file.getBlob();
        
        // Call the DocIntel API
        var apiResult = callDocIntelApi(fileBlob, jobDesc);
        
        if (apiResult.error) {
          throw new Error(apiResult.error);
        }
        
        // Format columns
        var matchedKwStr = (apiResult.matched_keywords || []).join(", ");
        var missingKwStr = (apiResult.missing_keywords || []).join(", ");
        
        // Write as decimal percentage for formatting inside sheets (e.g. 0.75 for 75%)
        var matchScoreDec = 0.0;
        if (apiResult.match_score !== undefined) {
          matchScoreDec = apiResult.match_score / 100.0;
        } else {
          // Fallback if match_score is missing
          var totalKw = (apiResult.matched_keywords || []).length + (apiResult.missing_keywords || []).length;
          matchScoreDec = totalKw > 0 ? (apiResult.matched_keywords || []).length / totalKw : 0.0;
        }
        
        // Update Sheet Row
        sheet.getRange(rowNum, COL_MATCHED_KW).setValue(matchedKwStr);
        sheet.getRange(rowNum, COL_MISSING_KW).setValue(missingKwStr);
        sheet.getRange(rowNum, COL_MATCH_SCORE).setValue(matchScoreDec);
        sheet.getRange(rowNum, COL_STATUS).setValue("Processed");
        sheet.getRange(rowNum, COL_NOTES).setValue(apiResult.match_category + ": " + apiResult.explanation);
        
        Logger.log("Row " + rowNum + " successfully processed.");
        
      } catch (err) {
        Logger.log("Error processing Row " + rowNum + ": " + err.message);
        sheet.getRange(rowNum, COL_STATUS).setValue("Processed");
        sheet.getRange(rowNum, COL_NOTES).setValue("Error: " + err.message);
      }
    }
  }
}

/**
 * Extract file ID from a standard Google Drive upload or share URL.
 */
function getFileIdFromUrl(url) {
  if (!url) return null;
  // Match standard file ID regex pattern (25 to 50 characters)
  var match = url.match(/[-\w]{25,}(?!.*[-\w]{25,})/);
  return match ? match[0] : null;
}

/**
 * Call the DocIntel API using UrlFetchApp to submit multipart/form-data.
 */
function callDocIntelApi(fileBlob, jobDescription) {
  // UrlFetchApp automatically formats payload as multipart/form-data
  // if fields are nested with blobs.
  var payload = {
    "resume": fileBlob,
    "job_description": jobDescription
  };
  
  var options = {
    "method": "post",
    "payload": payload,
    "muteHttpExceptions": true
  };
  
  var response = UrlFetchApp.fetch(API_URL, options);
  var responseCode = response.getResponseCode();
  var contentText = response.getContentText();
  
  if (responseCode >= 200 && responseCode < 300) {
    return JSON.parse(contentText);
  } else {
    var errorMsg = "API call failed with status " + responseCode;
    try {
      var errObj = JSON.parse(contentText);
      if (errObj.detail) {
        errorMsg += ": " + errObj.detail;
      }
    } catch (e) {
      errorMsg += ": " + contentText;
    }
    return { "error": errorMsg };
  }
}
