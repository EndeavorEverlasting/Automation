function addNewDay() {
  var sheet = SpreadsheetApp.getActiveSpreadsheet().getActiveSheet();
  
  // Prompt the user to confirm starting a new day
  var ui = SpreadsheetApp.getUi();
  var response = ui.alert('Start a new day?', ui.ButtonSet.YES_NO);
  
  // Exit if the user cancels the operation
  if (response != ui.Button.YES) {
    return;
  }
  
  // Get the current date
  var currentDate = new Date();
  
  // Get existing data below row 2 (excluding header and example rows)
  var existingDataRange = sheet.getRange(3, 1, sheet.getLastRow() - 2, sheet.getLastColumn());
  var existingData = existingDataRange.getValues();
  
  // Shift existing data down by 25 rows
  var numRowsToShift = 25;
  var newDataRange = sheet.getRange(28 + numRowsToShift, 1, sheet.getLastRow() - 2 - numRowsToShift, sheet.getLastColumn());
  existingDataRange.copyTo(newDataRange);
  
  // Clear the old data above row 28
  existingDataRange.clear();
  
  // Set the date for the new day
  sheet.getRange("A3").setValue(currentDate);
  
  // Inform the user
  ui.alert('New day started successfully!');
}
