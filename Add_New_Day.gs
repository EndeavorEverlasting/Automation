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
  
  // Move existing data down
  sheet.insertRowsAfter(2, 1);
  
  // Set the date for the new day
  sheet.getRange("A3").setValue(currentDate);
  
  // Populate cells with "25" starting from column 3
  var numColumns = sheet.getLastColumn() - 2; // Excluding the first two columns
  var valueArray = [];
  for (var i = 0; i < numColumns; i++) {
    valueArray.push(["25"]);
  }
  sheet.getRange("C3").offset(0, 0, 1, numColumns).setValues(valueArray);
  
  // Inform the user
  ui.alert('New day started successfully!');
}
