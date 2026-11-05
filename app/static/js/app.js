(function () {
  "use strict";

  function formatSize(bytes) {
    var value = Number(bytes);
    if (!isFinite(value) || value <= 0) return "";
    var units = ["B", "KB", "MB", "GB", "TB"];
    var index = 0;
    while (value >= 1024 && index < units.length - 1) {
      value /= 1024;
      index += 1;
    }
    return (index === 0 ? Math.round(value) : value.toFixed(1)) + " " + units[index];
  }

  // 1) Selos de disponibilidade dos cards (máximo de 4 requisições paralelas)
  var badges = Array.prototype.slice.call(document.querySelectorAll("[data-check-url]"));
  var cursor = 0;

  function nextBadge() {
    var element = badges[cursor++];
    if (!element) return Promise.resolve();
    return fetch(element.dataset.checkUrl, { headers: { Accept: "application/json" } })
      .then(function (response) { return response.json(); })
      .then(function (data) {
        if (!data.ok) {
          element.className = "badge badge-bad";
          element.textContent = "erro na consulta";
        } else if (!data.available) {
          element.className = "badge badge-bad";
          element.textContent = "sem torrent";
        } else {
          element.className = "badge badge-ok";
          var size = formatSize(data.total_size);
          element.textContent = size ? "torrent · " + size : "torrent disponível";
        }
      })
      .catch(function () {
        element.className = "badge badge-bad";
        element.textContent = "erro na consulta";
      })
      .then(nextBadge);
  }

  for (var i = 0; i < Math.min(4, badges.length); i += 1) nextBadge();

  // 2) Histórico ao vivo
  var historyBody = document.getElementById("history-body");
  if (historyBody) {
    var refresh = function () {
      if (document.hidden) return;
      fetch("/api/history", { headers: { Accept: "text/html" } })
        .then(function (response) {
          if (!response.ok) throw new Error("http " + response.status);
          return response.text();
        })
        .then(function (html) {
          if (historyBody.innerHTML !== html) historyBody.innerHTML = html;
        })
        .catch(function () { /* mantém o último estado conhecido */ });
    };
    window.setInterval(refresh, 5000);
  }

  // 3) Teste de conexão com o qBittorrent
  var testButton = document.getElementById("test-connection");
  if (testButton) {
    testButton.addEventListener("click", function () {
      var output = document.getElementById("test-result");
      output.className = "test-result muted";
      output.textContent = "Testando…";
      fetch(testButton.dataset.url, { method: "POST" })
        .then(function (response) { return response.json(); })
        .then(function (data) {
          if (data.ok) {
            output.className = "test-result ok";
            output.textContent = "Conectado · qBittorrent " + data.version;
          } else {
            output.className = "test-result bad";
            output.textContent = data.error || "Falha na conexão.";
          }
        })
        .catch(function () {
          output.className = "test-result bad";
          output.textContent = "Falha na requisição.";
        });
    });
  }

  // 4) Mostrar/ocultar a senha do qBittorrent
  Array.prototype.forEach.call(document.querySelectorAll("[data-toggle-password]"), function (button) {
    button.addEventListener("click", function () {
      var input = document.getElementById(button.dataset.togglePassword);
      if (!input) return;
      var showing = input.type === "password";
      input.type = showing ? "text" : "password";
      button.textContent = showing ? "ocultar" : "mostrar";
    });
  });

  // 5) Confirmação de remoção (delegação: as linhas do histórico são recarregadas)
  document.addEventListener("submit", function (event) {
    var form = event.target;
    if (form && form.dataset && form.dataset.confirm) {
      if (!window.confirm(form.dataset.confirm)) event.preventDefault();
    }
  });
})();
