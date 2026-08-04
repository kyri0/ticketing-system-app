// Progressive enhancement for the sifting panel.
//
// Without JavaScript the form is an ordinary GET with a submit button, and
// everything still works. With it, the button disappears and any change to a
// filter re-sifts the ledger immediately.
(function () {
  var form = document.getElementById('sift');
  if (!form) return;

  var panel = document.getElementById('panel');
  var button = document.getElementById('sift-go');
  if (button) button.hidden = true;

  // Remember which dropdown is open so the reload can reopen it. Without this
  // you would have to reopen the panel after every single tick.
  var dropdowns = form.querySelectorAll('details[data-panel]');
  Array.prototype.forEach.call(dropdowns, function (details) {
    details.addEventListener('toggle', function () {
      if (details.open) {
        panel.value = details.dataset.panel;
        // Only one open at a time, or they overlap the fields below.
        Array.prototype.forEach.call(dropdowns, function (other) {
          if (other !== details) other.open = false;
        });
      } else if (panel.value === details.dataset.panel) {
        panel.value = '';
      }
    });
  });

  // 'change' covers checkboxes and selects immediately, and text inputs on
  // blur or Enter — never mid-keystroke, so the caret is not yanked away.
  form.addEventListener('change', function () {
    form.submit();
  });
})();
