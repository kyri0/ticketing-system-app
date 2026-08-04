// Progressive enhancement for the sifting panel.
//
// Without JavaScript the form is an ordinary GET with a submit button, and
// everything still works. With it, the button disappears and any change to a
// filter re-sifts the ledger immediately.
(function () {
  // The create panel opens as a modal so the Petition field gets a full line.
  // It is rendered inline (<dialog open>) when a submission failed validation,
  // so the typed values survive even if this script never runs.
  var dialog = document.getElementById('scriptorium');
  var summon = document.getElementById('summon');
  if (dialog && summon && typeof dialog.showModal === 'function') {
    var wasOpen = dialog.hasAttribute('open');
    if (wasOpen) dialog.close();
    summon.addEventListener('click', function () { dialog.showModal(); });
    var dismiss = document.getElementById('dismiss');
    if (dismiss) dismiss.addEventListener('click', function () { dialog.close(); });
    // Clicking the backdrop closes it; clicks inside the panel must not.
    dialog.addEventListener('click', function (event) {
      if (event.target === dialog) dialog.close();
    });
    if (wasOpen) dialog.showModal();
  }

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
