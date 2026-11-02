/* Majeirkn AI - interface web. Fala com o llama-server na mesma origem. */
(function () {
  "use strict";

  var STORE_CONVS = "majeirkn.convs.v1";
  var STORE_SETTINGS = "majeirkn.settings.v1";
  var STORE_CURRENT = "majeirkn.current.v1";
  // Limita o historico enviado: prompt grande = resposta lenta no celular.
  var MAX_HISTORY = 20;

  var SYSTEM_FALLBACK =
    "Voce e Majeirkn AI, um assistente de inteligencia artificial local. " +
    "Responda sempre em portugues do Brasil, com clareza e precisao. " +
    "Quando nao souber algo, diga que nao sabe e nao invente informacoes.";

  var systemPrompt = SYSTEM_FALLBACK;

  var state = {
    convs: [],
    currentId: null,
    settings: { temperature: 0.7, top_p: 0.8, max_tokens: 512 },
    busy: false,
    abort: null
  };

  var el = {};
  ["chat", "empty", "input", "btn-send", "btn-stop", "btn-new", "btn-menu",
   "drawer", "conv-list", "btn-close-drawer", "btn-settings", "settings",
   "btn-close-settings", "status", "toast", "model-info"].forEach(function (id) {
    el[id] = document.getElementById(id);
  });

  /* ------------------------------------------------------------- utilidades */

  function uid() {
    return Date.now().toString(36) + "-" + Math.random().toString(36).slice(2, 7);
  }

  function escapeHtml(text) {
    return text.replace(/[&<>"']/g, function (ch) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[ch];
    });
  }

  function toast(message) {
    el.toast.textContent = message;
    el.toast.hidden = false;
    clearTimeout(toast.timer);
    toast.timer = setTimeout(function () { el.toast.hidden = true; }, 5000);
  }

  /* ------------------------------------------------------------ markdown-lite
     Escapa tudo e depois inserte tags: nada de HTML do modelo executado. */
  function renderMarkdown(src) {
    var blocks = src.split(/```/);
    var out = "";
    for (var i = 0; i < blocks.length; i++) {
      if (i % 2 === 1) {
        var code = blocks[i].replace(/^[a-z]*\n/i, "");
        out += "<pre><code>" + escapeHtml(code.replace(/\n$/, "")) + "</code></pre>";
        continue;
      }
      var lines = blocks[i].split("\n");
      var list = null;
      for (var j = 0; j < lines.length; j++) {
        var line = lines[j].trim();
        var item = /^[-*+]\s+(.*)$/.exec(line);
        var ordered = /^\d+[.)]\s+(.*)$/.exec(line);
        var heading = /^(#{1,4})\s+(.*)$/.exec(line);
        if (heading) {
          if (list) { out += list === "ul" ? "</ul>" : "</ol>"; list = null; }
          var level = Math.min(3, heading[1].length);
          out += "<h" + level + ">" + inline(heading[2]) + "</h" + level + ">";
        } else if (item) {
          if (list !== "ul") { if (list) { out += "</ol>"; } out += "<ul>"; list = "ul"; }
          out += "<li>" + inline(item[1]) + "</li>";
        } else if (ordered) {
          if (list !== "ol") { if (list) { out += "</ul>"; } out += "<ol>"; list = "ol"; }
          out += "<li>" + inline(ordered[1]) + "</li>";
        } else if (line === "") {
          if (list) { out += list === "ul" ? "</ul>" : "</ol>"; list = null; }
        } else {
          if (list) { out += list === "ul" ? "</ul>" : "</ol>"; list = null; }
          out += "<p>" + inline(line) + "</p>";
        }
      }
      if (list) { out += list === "ul" ? "</ul>" : "</ol>"; }
    }
    return out;
  }

  function inline(text) {
    return "<span>" + escapeHtml(text)
      .replace(/`([^`]+)`/g, "<code>$1</code>")
      .replace(/\*\*([^*]+)\*\*/g, "<b>$1</b>")
      .replace(/(^|[^*])\*([^*]+)\*/g, "$1<i>$2</i>")
      + "</span>";
  }

  /* ----------------------------------------------------------- conversas */

  function loadConvs() {
    try { return JSON.parse(localStorage.getItem(STORE_CONVS)) || []; }
    catch (err) { return []; }
  }

  function saveConvs() {
    try { localStorage.setItem(STORE_CONVS, JSON.stringify(state.convs)); }
    catch (err) { /* modo privado do navegador: segue sem persistir */ }
  }

  function loadSettings() {
    try {
      var saved = JSON.parse(localStorage.getItem(STORE_SETTINGS));
      if (saved) { state.settings = saved; }
    } catch (err) { /* ignora */ }
  }

  function saveSettings() {
    try { localStorage.setItem(STORE_SETTINGS, JSON.stringify(state.settings)); }
    catch (err) { /* ignora */ }
  }

  function currentConv() {
    for (var i = 0; i < state.convs.length; i++) {
      if (state.convs[i].id === state.currentId) { return state.convs[i]; }
    }
    return null;
  }

  function newConv() {
    var conv = { id: uid(), title: "Nova conversa", messages: [], updated: Date.now() };
    state.convs.unshift(conv);
    state.currentId = conv.id;
    saveConvs();
    renderAll();
    return conv;
  }

  /* --------------------------------------------------------------- render */

  function renderAll() {
    renderMessages();
    renderConvList();
    el.empty.hidden = currentConv() && currentConv().messages.length > 0;
  }

  function renderConvList() {
    el["conv-list"].innerHTML = "";
    state.convs.slice(0, 30).forEach(function (conv) {
      var li = document.createElement("li");
      if (conv.id === state.currentId) { li.className = "active"; }
      var title = document.createElement("div");
      title.className = "t";
      title.textContent = conv.title;
      var meta = document.createElement("div");
      meta.className = "m";
      var count = conv.messages.filter(function (m) { return m.role === "user"; }).length;
      meta.textContent = count + (count === 1 ? " pergunta" : " perguntas");
      li.appendChild(title);
      li.appendChild(meta);
      li.onclick = function () {
        state.currentId = conv.id;
        try { localStorage.setItem(STORE_CURRENT, conv.id); } catch (err) { /* ignora */ }
        renderAll();
        el.drawer.hidden = true;
      };
      el["conv-list"].appendChild(li);
    });
  }

  function bubble(role, text, pending) {
    var wrap = document.createElement("div");
    wrap.className = "msg " + (role === "user" ? "me" : "ai") + (pending ? " pending" : "");
    var label = document.createElement("div");
    label.className = "role";
    label.textContent = role === "user" ? "Voce" : "Majeirkn AI";
    var body = document.createElement("div");
    body.className = "bubble";
    body.innerHTML = renderMarkdown(text);
    wrap.appendChild(label);
    wrap.appendChild(body);
    return { wrap: wrap, body: body };
  }

  function renderMessages() {
    el.chat.innerHTML = "";
    var conv = currentConv();
    if (!conv) { return; }
    conv.messages.forEach(function (msg) {
      if (msg.role === "system") { return; }
      var node = bubble(msg.role, msg.content, false);
      el.chat.appendChild(node.wrap);
    });
    scrollToEnd();
  }

  function scrollToEnd() {
    requestAnimationFrame(function () {
      el.chat.scrollTop = el.chat.scrollHeight;
    });
  }

  function setBusy(busy) {
    state.busy = busy;
    el["btn-send"].hidden = busy;
    el["btn-stop"].hidden = !busy;
    el.input.disabled = false;
  }

  /* ------------------------------------------------------------------- API */

  function loadSystemPrompt() {
    return fetch("./system.txt", { cache: "no-cache" })
      .then(function (res) { return res.ok ? res.text() : Promise.reject(); })
      .then(function (text) { if (text.trim()) { systemPrompt = text.trim(); } })
      .catch(function () { /* usa o texto padrao */ });
  }

  function checkHealth() {
    return fetch("/health")
      .then(function (res) {
        el.status.dataset.state = res.ok ? "ok" : "down";
        el.status.textContent = res.ok ? "pronto" : "fora do ar";
      })
      .catch(function () {
        el.status.dataset.state = "down";
        el.status.textContent = "servidor desligado";
      });
  }

  function loadModelInfo() {
    return fetch("/props")
      .then(function (res) { return res.ok ? res.json() : null; })
      .then(function (props) {
        if (!props) { return; }
        var path = props.model_path || "";
        var name = path.split("/").pop() || "modelo";
        var ctx = props.n_ctx || "?";
        el["model-info"].textContent =
          "Modelo: " + name + "\nContexto: " + ctx + " tokens\nExecucao: local, offline";
      })
      .catch(function () { /* sem info */ });
  }

  function streamChat(messages, signal, onDelta) {
    var payload = {
      messages: messages,
      stream: true,
      stream_options: { include_usage: true },
      temperature: state.settings.temperature,
      top_p: state.settings.top_p,
      max_tokens: state.settings.max_tokens,
      cache_prompt: true
    };

    return fetch("/v1/chat/completions", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
      signal: signal
    }).then(function (res) {
      if (!res.ok || !res.body) {
        return res.text().then(function (body) {
          throw new Error("servidor respondeu " + res.status + ": " + body.slice(0, 160));
        });
      }
      var reader = res.body.getReader();
      var decoder = new TextDecoder();
      var buffer = "";
      var info = {};

      function pump() {
        return reader.read().then(function (chunk) {
          if (chunk.done) { return info; }
          buffer += decoder.decode(chunk.value, { stream: true });
          var index;
          while ((index = buffer.indexOf("\n")) >= 0) {
            var line = buffer.slice(0, index).trim();
            buffer = buffer.slice(index + 1);
            if (line.indexOf("data:") !== 0) { continue; }
            var data = line.slice(5).trim();
            if (data === "[DONE]") { return info; }
            var parsed;
            try { parsed = JSON.parse(data); } catch (err) { continue; }
            if (parsed.usage) { info.usage = parsed.usage; }
            if (parsed.timings) { info.timings = parsed.timings; }
            var delta = (parsed.choices || [{}])[0].delta || {};
            if (delta.content) { onDelta(delta.content); }
          }
          return pump();
        });
      }
      return pump();
    });
  }

  /* ------------------------------------------------------------------ acoes */

  function send() {
    var text = el.input.value.trim();
    if (!text || state.busy) { return; }

    var conv = currentConv() || newConv();
    if (conv.title === "Nova conversa" && conv.messages.length === 0) {
      conv.title = text.split("\n")[0].slice(0, 50);
    }
    conv.messages.push({ role: "user", content: text });
    conv.updated = Date.now();

    el.input.value = "";
    autoGrow();
    setBusy(true);
    renderAll();

    var pendingNode = bubble("assistant", "", true);
    el.chat.appendChild(pendingNode.wrap);
    scrollToEnd();

    var messages = [{ role: "system", content: systemPrompt }]
      .concat(conv.messages.slice(-MAX_HISTORY));
    var controller = new AbortController();
    state.abort = controller;
    var answer = "";

    streamChat(messages, controller.signal, function (piece) {
      answer += piece;
      pendingNode.body.innerHTML = renderMarkdown(answer);
      scrollToEnd();
    }).then(function (info) {
      conv.messages.push({ role: "assistant", content: answer });
      conv.updated = Date.now();
      saveConvs();
      renderAll();
      var speed = info.timings && info.timings.predicted_per_second;
      if (speed) {
        var line = document.createElement("div");
        line.className = "timing";
        line.textContent = parseFloat(speed).toFixed(1) + " tok/s";
        pendingNode.wrap.appendChild(line);
      }
    }).catch(function (err) {
      pendingNode.wrap.remove();
      if (err && err.name === "AbortError") {
        toast("Geracao parada.");
        if (answer) { conv.messages.push({ role: "assistant", content: answer }); }
      } else {
        toast(err && err.message ? err.message : "Falha ao conversar com o servidor.");
        conv.messages.pop(); // remove a pergunta que nao obteve resposta
      }
      saveConvs();
      renderAll();
    }).then(function () {
      setBusy(false);
      state.abort = null;
      el.input.focus();
    });
  }

  function stop() {
    if (state.abort) { state.abort.abort(); }
  }

  function autoGrow() {
    el.input.style.height = "auto";
    el.input.style.height = Math.min(140, el.input.scrollHeight) + "px";
  }

  function bindSettings() {
    ["temperature", "top_p", "max_tokens"].forEach(function (key) {
      var input = document.getElementById("opt-" + key);
      var label = document.getElementById("val-" + key);
      input.value = state.settings[key];
      label.textContent = key === "max_tokens" ? state.settings[key]
        : parseFloat(state.settings[key]).toFixed(2);
      input.oninput = function () {
        state.settings[key] = key === "max_tokens"
          ? parseInt(input.value, 10)
          : parseFloat(input.value);
        label.textContent = key === "max_tokens" ? state.settings[key]
          : state.settings[key].toFixed(2);
        saveSettings();
      };
    });
  }

  function openPanel(panel) {
    el.drawer.hidden = panel !== "drawer";
    el.settings.hidden = panel !== "settings";
  }

  /* ------------------------------------------------------------------- init */

  function init() {
    state.convs = loadConvs();
    loadSettings();
    try { state.currentId = localStorage.getItem(STORE_CURRENT); } catch (err) { /* ignora */ }

    if (!currentConv()) {
      var last = state.convs[0];
      state.currentId = last ? last.id : newConv().id;
    }

    bindSettings();
    renderAll();
    loadSystemPrompt().then(checkHealth).then(loadModelInfo);
    setInterval(checkHealth, 20000);
    document.addEventListener("visibilitychange", function () {
      if (!document.hidden) { checkHealth(); }
    });

    el["btn-send"].onclick = send;
    el["btn-stop"].onclick = stop;
    el["btn-new"].onclick = function () { newConv(); el.input.focus(); };
    el["btn-menu"].onclick = function () { openPanel("drawer"); };
    el["btn-close-drawer"].onclick = function () { el.drawer.hidden = true; };
    el["btn-settings"].onclick = function () { openPanel("settings"); };
    el["btn-close-settings"].onclick = function () { el.settings.hidden = true; };

    el.input.addEventListener("input", autoGrow);
    el.input.addEventListener("keydown", function (event) {
      if (event.key === "Enter" && !event.shiftKey) {
        event.preventDefault();
        send();
      }
    });

    document.querySelectorAll(".suggestion").forEach(function (button) {
      button.onclick = function () {
        el.input.value = button.textContent;
        autoGrow();
        send();
      };
    });

    if ("serviceWorker" in navigator) {
      navigator.serviceWorker.register("./sw.js").catch(function () { /* sem SW */ });
    }
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
