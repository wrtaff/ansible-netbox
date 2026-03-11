(function() {
  // 1. Extract the Title
  var title = '';
  var titleEl = document.querySelector('input[aria-label="Title"], input[placeholder="Add title"], input[jsname="V67oZd"]');
  if (titleEl && titleEl.value) {
    title = titleEl.value;
  } else {
    title = document.title.replace(/\s-\sGoogle\sCalendar$/, '');
  }

  // 2. Extract Date and Check for All Day
  var dateStr = '';
  var timeStr = '';
  var dateEl = document.querySelector('input[aria-label="Start date"]');
  var allDayEl = document.querySelector('input[aria-label="All day"]');
  var isAllDay = allDayEl ? allDayEl.checked : false;

  if (dateEl && dateEl.value) {
    var d = new Date(dateEl.value);
    if (!isNaN(d.getTime())) {
      var days = ['Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday'];
      var months = ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December'];
      
      var dayName = days[d.getDay()];
      var dayNum = String(d.getDate()).padStart(2, '0');
      var monthName = months[d.getMonth()];
      var year = d.getFullYear();
      
      dateStr = dayName + ' ' + dayNum + ' ' + monthName + ' ' + year;
    } else {
      dateStr = dateEl.value; // Fallback to raw text if parsing fails
    }
  }

  // 3. Extract Time (if not an all-day event)
  if (!isAllDay) {
    var timeEl = document.querySelector('input[aria-label="Start time"]');
    if (timeEl && timeEl.value) {
      // Regex to handle "9:30 AM", "09:30", "21:30", etc.
      var tMatch = timeEl.value.match(/(\d+):(\d+)\s*(AM|PM)?/i);
      if (tMatch) {
        var hours = parseInt(tMatch[1]);
        var minutes = tMatch[2];
        var ampm = tMatch[3];
        if (ampm) {
          if (ampm.toUpperCase() === 'PM' && hours < 12) hours += 12;
          if (ampm.toUpperCase() === 'AM' && hours === 12) hours = 0;
        }
        timeStr = String(hours).padStart(2, '0') + minutes.padStart(2, '0') + ' ';
      }
    }
  }

  // 4. Construct Result
  var url = window.location.href;
  var result = "'''[" + url + " gCal Event: " + title + " " + timeStr + dateStr + "]'''";
  // Clean up any double spaces caused by missing pieces
  result = result.replace(/\s{2,}/g, ' ');

  // 5. Copy and Prompt
  if (navigator.clipboard && navigator.clipboard.writeText) {
    navigator.clipboard.writeText(result).catch(function(err) {
      console.error('Unable to copy to clipboard', err);
    });
  }
  prompt("MediaWiki Link (Copied to Clipboard):", result);
})();
