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

  // Opening a petition used to be a full page load — same page, new URL, but
  // you could see the repaint. Now the card is fetched on its own and spliced
  // into the table. The links keep their real hrefs, so without JavaScript (or
  // on middle-click, or with the fetch failing) the old navigation still works.
  var table = document.querySelector('table.ledger');
  if (table && window.fetch && window.history && window.history.pushState) {
    table.addEventListener('click', function (event) {
      var link = event.target.closest('a[data-petition]');
      if (!link) return;
      // Let the browser handle new-tab and modified clicks.
      if (event.metaKey || event.ctrlKey || event.shiftKey || event.button !== 0) return;
      event.preventDefault();

      var id = link.dataset.petition;
      var opening = link.dataset.action === 'open';
      var row = link.closest('tr');

      closeAll();
      if (!opening) {
        history.pushState({}, '', link.getAttribute('href').split('#')[0]);
        return;
      }

      var href = link.getAttribute('href').split('#')[0];
      row.classList.add('open-row');
      fetch('/petitions/' + id + '/card?back=' + encodeURIComponent(href), {
        headers: { 'X-Requested-With': 'fetch' }
      })
        .then(function (response) {
          if (!response.ok) throw new Error(response.status);
          return response.text();
        })
        .then(function (html) {
          var tr = document.createElement('tr');
          tr.className = 'card-row';
          tr.dataset.for = id;
          var td = document.createElement('td');
          td.colSpan = 6;
          td.style.padding = '0 0 16px';
          td.innerHTML = html;
          tr.appendChild(td);
          row.parentNode.insertBefore(tr, row.nextSibling);
          setToggles(id, 'close');
          history.pushState({}, '', href);
        })
        .catch(function () {
          // Fall back to the ordinary navigation rather than failing silently.
          window.location.href = href;
        });
    });

    // The browser's back button should collapse the card, not refetch the page.
    window.addEventListener('popstate', function () {
      var wanted = new URLSearchParams(window.location.search).get('open');
      closeAll();
      if (wanted) {
        var link = table.querySelector('a[data-petition="' + wanted + '"]');
        if (link) link.click();
      }
    });
  }

  function closeAll() {
    Array.prototype.forEach.call(table.querySelectorAll('tr.card-row'), function (tr) {
      setToggles(tr.dataset.for, 'open');
      tr.parentNode.removeChild(tr);
    });
    Array.prototype.forEach.call(table.querySelectorAll('tr.open-row'), function (tr) {
      tr.classList.remove('open-row');
    });
  }

  function setToggles(id, action) {
    Array.prototype.forEach.call(
      table.querySelectorAll('a[data-petition="' + id + '"]'),
      function (link) {
        link.dataset.action = action;
        var button = link.querySelector('button');
        if (button) button.textContent = action === 'close' ? 'Close' : 'Read';
        var href = link.getAttribute('href').split('#')[0];
        var url = new URL(href, window.location.origin);
        if (action === 'close') {
          url.searchParams.set('open', id);
        } else {
          url.searchParams.delete('open');
        }
        link.setAttribute('href', url.pathname + url.search + '#p' + id);
      }
    );
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
