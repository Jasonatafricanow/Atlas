/* 原文册界面。写入都走 ledger.js，页面上没有改第一版原文的路径。 */
(async function () {
  const loaded=await fetch('/api/folio').then(r=>{if(!r.ok)throw Error('原文册不可用');return r.json()});
  window.FOLIO_SEED=loaded.doc;
  var KEY='folio.runtime.'+loaded.scope;
  let revision=loaded.revision;
  let saveChain=Promise.resolve();
  var state = {
    doc: null,
    dirty: false,
    topic: "",
    query: "",
    notesOn: true,
    layers: { demo: true, self: true, ai: true },
    revPick: {},
    sort: "spoken",
    sortInit: false,
    labFor: "",
    labDraft: "",
    marginDraft: "",
    modal: null,
    importText: "",
    importChecked: false,
    showReadout: false,
    didDemo: false,
    focus: "",
    hoverNote: ""
  };

  function esc(s) {
    return String(s == null ? "" : s)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  function clone(o) { return JSON.parse(JSON.stringify(o)); }

  function nowStamp() {
    var d = new Date();
    function p(n) { return String(n).padStart(2, "0"); }
    return d.getFullYear() + "-" + p(d.getMonth() + 1) + "-" + p(d.getDate()) + " " + p(d.getHours()) + ":" + p(d.getMinutes());
  }

  function today() {
    return nowStamp().slice(0, 10);
  }

  function find(id) {
    var list = state.doc.entries;
    for (var i = 0; i < list.length; i++) if (list[i].id === id) return list[i];
    return null;
  }

  function chainNo(entry) {
    return state.doc.entries.findIndex(function (e) { return e.id === entry.id; }) + 1;
  }

  function intact(entry) {
    var i = state.doc.entries.findIndex(function (e) { return e.id === entry.id; });
    var prev = i <= 0 ? Folio.GENESIS : state.doc.entries[i - 1].chain;
    var v1 = Folio.originalOf(entry);
    var sha = Folio.sha256(v1.text);
    return sha === v1.sha256 && entry.chain_prev === prev && entry.chain === Folio.chainLink(prev, sha, entry.id);
  }

  function shortHash(h) {
    if (!h) return "";
    return h.slice(0, 8) + " · " + h.slice(-4);
  }

  function monthName(spoken) {
    var names = ["", "一", "二", "三", "四", "五", "六", "七", "八", "九", "十", "十一", "十二"];
    var y = spoken.slice(0, 4);
    var m = Number(spoken.slice(5, 7));
    if (!y || !m) return "未纪年";
    return y + " · " + names[m] + "月";
  }

  function dayPair(spoken) {
    if (!spoken) return "——";
    return spoken.slice(5, 7) + "/" + spoken.slice(8, 10);
  }

  function formatWhen(entry) {
    var spoken = entry.spoken_at || "";
    var day = spoken.slice(0, 10);
    var clock = spoken.slice(11);
    var line = entry.time_precision === "timestamp"
      ? (day + (clock ? " " + clock : ""))
      : (spoken ? spoken + " 之后" : "时间不详");
    if (entry.diary_date && day && entry.diary_date !== day) {
      line = "日记日 " + entry.diary_date + " · 说于 " + line;
    }
    return line;
  }

  function visibleEntries() {
    var q = state.query.trim().toLowerCase();
    return state.doc.entries.filter(function (e) {
      if (state.topic && e.topic !== state.topic) return false;
      if (!q) return true;
      return (Folio.originalOf(e).text + "\n" + e.title).toLowerCase().indexOf(q) >= 0;
    });
  }

  function route() {
    var hash = (location.hash || "#/read/").replace(/^#/, "");
    var bits = hash.split("/").filter(Boolean);
    var view = bits[0] || "read";
    if (["read", "timeline", "trust", "lab", "new"].indexOf(view) < 0) view = "read";
    var id = bits[1] || "";
    if (!find(id)) id = (state.doc.entries[0] && state.doc.entries[0].id) || "";
    if (!state.sortInit) {
      state.sort = new URLSearchParams(location.search).get("sort") === "diary" ? "diary" : "spoken";
      state.sortInit = true;
    }
    var rev = new URLSearchParams(location.search).get("rev");
    return { view: view, id: id, rev: rev, flip: new URLSearchParams(location.search).get("flip") };
  }

  function go(hash) {
    if (location.hash === hash) render();
    else location.hash = hash;
  }

  function persist() {
    state.dirty = true;
    const snapshot=JSON.parse(JSON.stringify(state.doc));
    saveChain=saveChain.then(async()=>{const response=await fetch('/api/folio',{method:'POST',headers:{'Content-Type':'application/json','X-Atlas-Token':loaded.token},body:JSON.stringify({doc:snapshot,revision})});if(!response.ok)throw Error('保存冲突或原文不可修改，请导出当前副本再刷新');revision=(await response.json()).revision;document.getElementById('foot').textContent='旁注已保存到独立本地存储';}).catch(error=>{document.getElementById('foot').textContent=error.message;});
  }

  function selectedRev(entry, qrev) {
    if (state.revPick[entry.id]) return state.revPick[entry.id];
    var n = Number(qrev);
    if (qrev && entry.versions.some(function (v) { return v.n === n; })) return n;
    return 1;
  }

  function anchoredNotes(text, notes) {
    if (!state.notesOn) return [];
    var out = [];
    (notes || []).forEach(function (note) {
      if (!state.layers[note.layer] || !note.anchor) return;
      var i = text.indexOf(note.anchor);
      if (i < 0) return;
      out.push({ i: i, j: i + note.anchor.length, id: note.id, n: out.length + 1 });
    });
    return out;
  }

  function inlineSlice(slice, base, ranges) {
    var end = base + slice.length;
    var local = [];
    ranges.forEach(function (r) {
      if (r.j <= base || r.i >= end) return;
      local.push({
        i: Math.max(r.i, base) - base,
        j: Math.min(r.j, end) - base,
        id: r.id,
        n: r.n,
        close: r.j <= end && r.j > base
      });
    });
    local.sort(function (a, b) { return a.i - b.i || b.j - a.j; });
    var html = "";
    var cursor = 0;
    local.forEach(function (r) {
      if (r.i < cursor) return;
      html += esc(slice.slice(cursor, r.i));
      html += '<mark data-note="' + esc(r.id) + '">' + esc(slice.slice(r.i, r.j)) +
        (r.close ? '<sup class="pin">' + r.n + "</sup>" : "") + "</mark>";
      cursor = r.j;
    });
    html += esc(slice.slice(cursor));
    return html;
  }

  function proseHtml(text, notes) {
    var ranges = anchoredNotes(text, notes);
    var blocks = Folio.layoutProse(text, ranges);
    return blocks.map(function (block) {
      if (!block.text) return "";
      var cls = block.hard ? "hard" : "soft";
      if (block.hard && block.text.length < 18) cls += " brief";
      return '<p class="' + cls + '">' + inlineSlice(block.text, block.base, ranges) + "</p>";
    }).join("");
  }

  function diffHtml(ops) {
    return (ops || []).map(function (pair) {
      var op = pair[0], s = pair[1];
      var cls = op === "delete" ? "del" : op === "insert" ? "ins" : "eq";
      return '<span class="' + cls + '">' + esc(s) + "</span>";
    }).join("");
  }

  function paintStatus() {
    var errors = Folio.verify(state.doc);
    var el = document.getElementById("chainStatus");
    var pages = state.doc.entries.length;
    var chars = state.doc.entries.reduce(function (n, e) { return n + Folio.originalOf(e).text.length; }, 0);
    var seal = errors.length ? "裂" : "封";
    el.className = "status" + (errors.length ? " bad" : "");
    el.innerHTML = "<i>" + seal + "</i><span>" + pages + " 页 · " + chars + " 字 · " +
      (errors.length ? ("链有 " + errors.length + " 处对不上") : "链完好") +
      (state.dirty ? " · 本机有改动" : "") + "</span>";
    document.documentElement.dataset.chain = errors.length ? "broken" : "ok";
    document.documentElement.dataset.pages = String(pages);
  }

  function paintSpine(currentId) {
    var list = visibleEntries();
    var html = "";
    var month = "";
    if (!list.length) html = '<p class="empty-spine">书脊里没有对得上的页。</p>';
    list.forEach(function (e) {
      var label = monthName(e.spoken_at || e.diary_date || "");
      if (label !== month) {
        month = label;
        html += '<div class="month">' + esc(label) + "</div>";
      }
      var cur = e.id === currentId ? ' aria-current="true"' : "";
      html += '<button type="button" class="spine-item" data-entry="' + esc(e.id) + '"' + cur + ">" +
        '<span class="d">' + esc(dayPair(e.spoken_at)) + "</span>" +
        '<span class="t">' + esc(e.title) + "</span>" +
        '<span class="s">' + esc(e.topic) + (e.status === "tombstone" ? " · 墓碑" : "") + "</span></button>";
    });
    document.getElementById("spineList").innerHTML = html;
    document.getElementById("spineFoot").textContent = state.doc.entries.length + " 页里显示 " + list.length;
    document.querySelectorAll("#filters button").forEach(function (btn) {
      btn.classList.toggle("on", (btn.getAttribute("data-topic") || "") === state.topic);
    });
    var box = document.getElementById("spineList");
    var curBtn = box.querySelector("[aria-current='true']");
    if (curBtn) {
      var narrow = window.matchMedia("(max-width: 860px)").matches;
      if (narrow) {
        var left = curBtn.getBoundingClientRect().left - box.getBoundingClientRect().left + box.scrollLeft;
        box.scrollLeft = Math.max(0, left - 16);
      } else {
        var top = curBtn.offsetTop;
        var bottom = top + curBtn.offsetHeight;
        if (top < box.scrollTop + 4 || bottom > box.scrollTop + box.clientHeight - 4) {
          var target = Math.max(0, top - Math.max(0, (box.clientHeight - curBtn.offsetHeight) / 2));
          var nodes = box.querySelectorAll(".month, .spine-item");
          var snap = 0;
          for (var n = 0; n < nodes.length; n++) {
            if (nodes[n].offsetTop <= target + 1) snap = nodes[n].offsetTop;
          }
          box.scrollTop = snap;
          if (bottom > box.scrollTop + box.clientHeight - 2) box.scrollTop = top;
        }
      }
    }
  }

  function navState(view) {
    document.querySelectorAll(".nav button[data-go]").forEach(function (btn) {
      var dest = btn.getAttribute("data-go") || "";
      var on = dest === "#/" + view || (view === "read" && dest === "#/read");
      if (on) btn.setAttribute("aria-current", "true");
      else btn.removeAttribute("aria-current");
    });
    var notes = document.getElementById("btnNotes");
    notes.textContent = state.notesOn ? "笺注开着" : "笺注关了";
    document.getElementById("btnTheme").textContent = document.documentElement.dataset.theme === "dark" ? "日读" : "夜读";
  }

  function paperHead(kicker, title, meta, entry) {
    var ok = entry ? intact(entry) : Folio.verify(state.doc).length === 0;
    var tomb = entry && entry.status === "tombstone";
    var glyph = !ok ? "裂" : tomb ? "碑" : "封";
    var cap = !ok ? "这一环对不上" : tomb ? "墓碑，链还在" : "链完好";
    return '<header class="paper-head"><div><p class="eyebrow">' + esc(kicker) + "</p><h2>" + esc(title) +
      '</h2><p class="meta">' + meta + '</p></div><div class="sealwrap"><div class="seal' + (ok ? "" : " bad") +
      '">' + glyph + '</div><div class="sealcap">' + cap + "</div></div></header>";
  }

  function renderRead(entry, qrev) {
    var v1 = Folio.originalOf(entry);
    var long = v1.text.length > 360;
    var ribbon = entry.status === "tombstone"
      ? '<div class="ribbon">墓碑 · ' + esc(entry.tombstone_at || "") + " · 正文还在，只是标成撤回</div>" : "";
    var marks = /[`*]/.test(v1.text) ? '<p class="editnote">星号和反引号是原消息里的记号，不是这页后加的格式。</p>' : "";
    var cut = entry.text_note ? '<p class="editnote">' + esc(entry.text_note) + "</p>" : "";
    var timeNote = entry.time_note ? '<p class="editnote">' + esc(entry.time_note) + "</p>" : "";
    var pick = selectedRev(entry, qrev);
    var vers = "";
    if (entry.versions.length > 1) {
      vers = '<div class="vers" role="tablist">' + entry.versions.map(function (v) {
        var label = v.n === 1 ? "第一版 · 原文" : ("第" + v.n + "版 · " + v.author);
        return '<button type="button" class="ver' + (v.n === pick ? " on" : "") + '" data-action="set-rev" data-id="' +
          esc(entry.id) + '" data-rev="' + v.n + '">' + esc(label) + "</button>";
      }).join("") + "</div>";
      if (pick > 1) {
        var v = entry.versions[pick - 1];
        var ops = v.diff_from_original || Folio.diffOps(v1.text, v.text);
        vers += '<section class="diffbox"><header><h3>第 ' + pick + ' 版不替换原文</h3><p>' + esc(v.note || "") +
          '</p></header><div class="revtext">' + esc(v.text) + '</div><div class="legend"><span class="del">原文里有、这一版拿掉的</span><span class="ins">这一版添上的</span></div><div class="diff">' +
          diffHtml(ops) + "</div></section>";
      }
    }
    var i = chainNo(entry) - 1;
    var prev = state.doc.entries[i - 1];
    var next = state.doc.entries[i + 1];
    function cell(k, item, fallback) {
      if (!item) return '<div><span class="k">' + k + '</span><strong>' + fallback + "</strong></div>";
      return '<button type="button" data-entry="' + esc(item.id) + '"><span class="k">' + k + "</span><strong>" +
        esc(item.title) + "</strong><code>" + esc(shortHash(item.chain)) + "</code></button>";
    }
    var meta = esc(formatWhen(entry)) + " · " + esc(entry.topic) + " · " + v1.text.length + " 字 · 题签不进哈希";
    document.getElementById("sheet").innerHTML = '<article class="sheet-inner">' +
      paperHead("第 " + chainNo(entry) + " 环 / " + state.doc.entries.length, entry.title, meta, entry) +
      ribbon + cut + timeNote + marks +
      '<div class="prose' + (long ? " long" : "") + (entry.status === "tombstone" ? " entombed" : "") + '">' +
      proseHtml(v1.text, entry.annotations) + "</div>" +
      '<p class="rhythm">约二十字一行。原文里的换行是大段，长段按句号再松开。这些空隙不进哈希。</p>' +
      '<div class="actions"><button type="button" class="textbtn" data-action="revise" data-id="' + esc(entry.id) +
      '">另起一版</button><button type="button" class="textbtn" data-action="tombstone" data-id="' + esc(entry.id) +
      '"' + (entry.status === "tombstone" ? " disabled" : "") + '>立墓碑</button><button type="button" class="textbtn" data-action="copy" data-id="' +
      esc(entry.id) + '">复制原文</button></div>' + vers +
      '<footer class="colophon">' + cell("上一环", prev, "这是第一环") +
      '<div><span class="k">这一环</span><strong>' + esc(shortHash(entry.chain)) + "</strong></div>" +
      cell("下一环", next, "后面还没写") +
      '<p class="chainline"><span class="k">原文指纹</span><code>' + esc(v1.sha256) + "</code></p></footer></article>";
    renderMarginRead(entry);
    document.title = entry.title + " · 原文册";
  }

  function renderMarginRead(entry) {
    var src = entry.source || {};
    var kind = src.kind === "user-original" ? "用户原创" : "本机写下";
    var pins = anchoredNotes(Folio.originalOf(entry).text, entry.annotations);
    var pinOf = {};
    pins.forEach(function (p) { pinOf[p.id] = p.n; });
    var notes = (entry.annotations || []).filter(function (n) { return state.notesOn && state.layers[n.layer]; });
    var cards = notes.map(function (n) {
      var pin = pinOf[n.id] ? '<sup class="pin">' + pinOf[n.id] + "</sup>" : "";
      var jump = n.anchor ? '<button type="button" class="linkish" data-jump-note="' + esc(n.id) + '">对上正文这句</button>' : "";
      return '<article class="note" data-note-id="' + esc(n.id) + '"><p class="who">' + pin + esc(n.author) + " · " +
        esc(n.layer === "demo" ? "演示" : n.layer === "ai" ? "模型" : "旁注") +
        " · " + esc(shortHash(n.sha256)) + "</p><p>" + esc(n.text) + "</p>" + jump + "</article>";
    }).join("");
    if (!notes.length) {
      cards = '<p class="quiet">' + (state.notesOn ? "这一页还没有笺注。" : "笺注层先揭掉了。正文没有动。") + "</p>";
    }
    var layers = '<div class="layers">' +
      ["demo", "self", "ai"].map(function (key) {
        var label = key === "demo" ? "演示" : key === "self" ? "旁注" : "模型";
        return '<label><input type="checkbox" data-layer="' + key + '"' + (state.layers[key] ? " checked" : "") +
          (state.notesOn ? "" : " disabled") + "> " + label + "</label>";
      }).join("") + "</div>";
    document.getElementById("margin").innerHTML =
      '<p class="kicker">著录</p><div class="src"><p>' + esc(src.session || "本机") + " · " + esc(kind) + "</p>" +
      '<p class="mono break">' + esc(src.file || "不来自摘录") + (src.line ? " · 行 " + src.line : "") + "</p>" +
      "<p>第一版作者 " + esc(Folio.originalOf(entry).author) + " · 出处 " + esc(Folio.originalOf(entry).origin) + "</p></div>" +
      '<p class="kicker">笺注</p><p class="quiet">红圈数字和细线是同一处。点一句，或点右边的注，两边一起亮。</p>' + layers + cards +
      '<form class="composer" data-action="save-note" data-id="' + esc(entry.id) + '"><label class="field"><span>写在边上，不进原文</span>' +
      '<textarea id="marginDraft" placeholder="旁注留在这一层">' + esc(state.marginDraft) + '</textarea></label>' +
      '<button type="submit" class="textbtn">记下旁注</button></form>';
  }

  function renderTimeline() {
    var list = state.doc.entries.slice();
    if (state.sort === "diary") {
      list.sort(function (a, b) {
        return (a.diary_date + " " + a.spoken_at).localeCompare(b.diary_date + " " + b.spoken_at);
      });
    }
    var items = list.map(function (e) {
      var text = Folio.originalOf(e).text;
      var rest = 0;
      var body = text;
      if (text.length > 80) { body = text.slice(0, 80); rest = text.length - 80; }
      return "<li><time>" + esc(formatWhen(e)) + " · 第 " + chainNo(e) + " 环" +
        (e.status === "tombstone" ? " · 墓碑" : "") + '</time><a href="#/read/' + esc(e.id) + '">' + esc(e.title) +
        '</a><p class="open">' + esc(body) + "</p>" +
        (rest ? ('<p class="quiet">余下 ' + rest + " 字在正文。</p>") : "") + "</li>";
    }).join("");
    document.getElementById("sheet").innerHTML = '<article class="sheet-inner">' +
      paperHead("回看", "时间线", "链的顺序是装订顺序。按日记日重排，不会重算旧环。", null) +
      '<div class="sorts"><button type="button" class="textbtn' + (state.sort === "spoken" ? " on" : "") +
      '" data-action="sort" data-sort="spoken">按说出时间</button><button type="button" class="textbtn' +
      (state.sort === "diary" ? " on" : "") + '" data-action="sort" data-sort="diary">按日记日</button></div>' +
      '<ol class="tl">' + items + "</ol></article>";
    document.getElementById("margin").innerHTML =
      '<p class="kicker">怎么读这条线</p><p>每一环的哈希只覆盖那一页的第一版原文。题签、笺注、后来的修订、墓碑，都不进环。</p>' +
      '<p>日记日可以早于说出时间。6 月 22 日那页是 23 日才说出来的，链上仍按说出的次序，不会插队重算。</p>' +
      '<p class="mono">创世 ' + esc(Folio.GENESIS) + "</p>";
    document.title = "时间线 · 原文册";
  }

  function renderTrust() {
    var t = state.doc.trust;
    function box(side, key, label) {
      var on = !!(t[side] && t[side][key]);
      return '<label class="check"><input type="checkbox" data-trust="' + side + "." + key + '"' + (on ? " checked" : "") +
        "><span>" + label + "</span></label>";
    }
    var fear = state.doc.entries[0];
    var epi = fear ? Folio.originalOf(fear).text : "";
    var audit = (state.doc.audit || []).slice(-6).reverse().map(function (ev) {
      var cls = ev.result === "允许" ? "ok" : "no";
      return '<li><span class="' + cls + '">' + esc(ev.result) + "</span> · " + esc(ev.detail) +
        "<br><span class=\"mono\">" + esc(ev.at) + " · " + esc(ev.action) + "</span></li>";
    }).join("");
    var readout = "";
    if (state.showReadout) {
      readout = '<ul class="readout">' + state.doc.entries.map(function (e) {
        var ok = Folio.readableByAi(state.doc, e);
        var preview = ok ? Folio.originalOf(e).text.slice(0, 32) : "正文不在可读范围";
        return "<li><b>" + esc(e.title) + "</b> " + esc(preview) + "</li>";
      }).join("") + "</ul>";
    }
    document.getElementById("sheet").innerHTML = '<article class="sheet-inner">' +
      paperHead("边界", "信任边界", "开关只约束运行时。种子里的演示笺注是装订时放进去的。", null) +
      '<div class="trust-grid"><section><p class="kicker">可以读</p>' +
      box("aiMayRead", "original", "原文") +
      box("aiMayRead", "annotation", "笺注") +
      box("aiMayRead", "tombstoneBody", "墓碑页的正文") +
      box("aiMayRead", "source", "来源和日期") +
      '</section><section><p class="kicker">可以写</p>' +
      '<label class="check locked"><input type="checkbox" disabled><span>原文层 · 没有这条路径</span></label>' +
      box("aiMayWrite", "annotation", "笺注层") +
      box("aiMayWrite", "version", "另起一版") +
      box("aiMayWrite", "meta", "题签和日期") +
      "</section></div>" +
      '<div class="probe"><button type="button" class="textbtn" data-action="ai-original">试探写入原文</button>' +
      '<button type="button" class="textbtn" data-action="ai-note">试探写入笺注</button>' +
      '<button type="button" class="textbtn" data-action="ai-read">按边界列出可读</button></div>' +
      (audit ? '<ul class="audit">' + audit + "</ul>" : '<p class="quiet">还没有试探记录。</p>') +
      readout +
      (epi ? '<blockquote class="epigraph">' + esc(epi) + "</blockquote><p class=\"quiet\">本册第一版原文，作者与时间以来源记录为准。</p>" : "") +
      "</article>";
    document.getElementById("margin").innerHTML =
      '<p class="kicker">执行</p><p>原文层的拒绝不看开关。就算把「可以写」理解成允许，写入原文的函数也会先把这个开关拨回关闭，然后记下一次拒绝。</p>' +
      "<p>墓碑不删除正文。若上面关掉「墓碑页的正文」，列出可读时那一页只显示不可读，哈希仍可自己验。</p>" +
      '<p>另起一版默认关闭。打开之后，模型也只能追加版本，第一版的字和环都不动。</p>' +
      '<p class="quiet"><button type="button" class="textbtn" data-action="reset-ask">恢复装订时的种子</button></p>';
    document.title = "信任边界 · 原文册";
  }

  function ensureLab(entry, flip) {
    if (state.labFor === entry.id) return;
    state.labFor = entry.id;
    var t = Folio.originalOf(entry).text;
    if (flip === "1") t = Folio.tamperOnce(t);
    state.labDraft = t;
  }

  function labChainHtml(entry) {
    var report = Folio.projectTamper(state.doc, entry.id, state.labDraft);
    if (report.same) {
      return '<div class="verdict ok" id="labChain"><b>链还没断</b><p>封存稿一个字都没动。按「模拟篡改」，把第一个「的」换成「得」，再按同一条规则重算后面的环。</p></div>';
    }
    var start = Math.max(0, report.index - 1);
    var end = Math.min(report.rows.length, report.index + 3);
    var items = "";
    for (var i = start; i < end; i++) {
      var row = report.rows[i];
      var tag = row.status === "before" ? "完好" : row.status === "break" ? "裂开" : "接不上";
      var why = "";
      if (row.status === "before") why = "改动在这一环之后，封存值不动。";
      else if (row.status === "break") {
        why = "封存环 <span class=\"mono\">" + esc(shortHash(row.stored)) + "</span><br>演练环 <span class=\"mono\">" +
          esc(shortHash(row.projected)) + "</span><br>原文变了一个字，这一环的哈希换了。";
      } else {
        why = "它记住的上一环 <span class=\"mono\">" + esc(shortHash(row.stored_prev)) + "</span><br>演练递过来的上一环 <span class=\"mono\">" +
          esc(shortHash(row.projected_prev)) + "</span><br>对不上，所以这一环也裂了。";
      }
      items += '<li class="' + row.status + '"><span class="tag">' + tag + '</span><div><b>第 ' + (row.index + 1) +
        " 环 · " + esc(row.title) + "</b><p>" + why + "</p></div></li>";
    }
    var more = report.broken_after - Math.max(0, end - (report.index + 1));
    var tail = more > 0 ? ('<p class="quiet">后面还有 ' + more + " 环同样接不上。</p>") : "";
    return '<div class="verdict bad" id="labChain"><b>从这一环裂开</b><p>演练只改了第 ' + (report.index + 1) +
      " 环的一个字。这一环换了哈希，后面 " + report.broken_after + " 环的上一环都对不上。顶上的封还在，因为没有写回。</p></div>" +
      '<ol class="breaklist">' + items + "</ol>" + tail;
  }

  function labResultHtml(entry) {
    var v1 = Folio.originalOf(entry);
    var same = v1.sha256 === Folio.sha256(state.labDraft);
    var extra = same ? "" : ('<p class="quiet">划掉的是封存稿，底色是演练稿添上的。</p><div class="diff">' +
      diffHtml(Folio.diffOps(v1.text, state.labDraft)) + "</div>");
    return labChainHtml(entry) + extra;
  }

  function renderLab(entry, flip) {
    ensureLab(entry, flip);
    document.getElementById("sheet").innerHTML = '<article class="sheet-inner">' +
      paperHead("沙箱", "篡改演练", "按钮会改一个字，只发生在沙箱里。账本没有写入口。", entry) +
      '<div class="lab-grid"><section class="lab-col"><h3>封存稿 · 只读</h3><p class="frozen">' +
      esc(Folio.originalOf(entry).text) + '</p></section><section class="lab-col"><h3>演练稿</h3>' +
      '<textarea id="labBox">' + esc(state.labDraft) + "</textarea></section></div>" +
      '<div class="actions"><button type="button" class="sealbtn" id="labTamper" data-action="lab-tamper" data-id="' +
      esc(entry.id) + '">模拟篡改</button><button type="button" class="textbtn" data-action="lab-reset" data-id="' +
      esc(entry.id) + '">恢复成封存稿</button><button type="button" class="textbtn" disabled>写回账本</button></div>' +
      '<p class="quiet">写回是灰的。演练不能进链。</p>' +
      '<div id="labResult">' + labResultHtml(entry) + "</div></article>";
    document.getElementById("margin").innerHTML =
      '<p class="kicker">这一页</p><p>' + esc(entry.title) + " · 第 " + chainNo(entry) + " 环</p>" +
      '<p class="mono break">' + esc(entry.chain) + "</p>" +
      "<p>模拟篡改把封存稿里的第一个「的」换成「得」，然后用原来的接法重算后面每一环。左边的封存稿、书脊和顶上的封都不变。</p>" +
      "<p>要真的另存一个说法，回到正文用「另起一版」。那是新版本，第一版的环不动。</p>";
    document.title = "篡改演练 · 原文册";
  }

  function renderNew() {
    document.getElementById("sheet").innerHTML = '<article class="sheet-inner"><form id="newForm">' +
      paperHead("空白", "新的一页", "封存之后第一版就不能改。要改，就另起一版。", null) +
      '<label class="field"><span>日记日</span><input name="date" type="date" value="' + esc(today()) + '" required></label>' +
      '<label class="field"><span>题签 · 不进哈希</span><input name="title" type="text" required maxlength="40" placeholder="给这一页一个短名字"></label>' +
      '<label class="field"><span>归在</span><select name="topic"><option>边界</option><option>架构</option><option>剖析</option><option>手记</option></select></label>' +
      '<label class="field"><span>原文</span><textarea name="text" required placeholder="写下之后，这就是第一版。"></textarea></label>' +
      '<button type="submit" class="textbtn">封存这一页</button></form></article>';
    document.getElementById("margin").innerHTML =
      '<p class="kicker">封存意味着</p><p>字会算进哈希，接到上一环后面。旧页的哈希不变。</p>' +
      "<p>这里没有「让模型起稿到正文」。模型如果要写，只能在信任边界允许的那一层。</p>";
    document.title = "新的一页 · 原文册";
  }

  function renderModal() {
    var root = document.getElementById("modalRoot");
    var m = state.modal;
    if (!m) { root.innerHTML = ""; return; }
    var inner = "";
    if (m.type === "copy") {
      inner = "<h3>原文</h3><p>这是第一版，不含题签和笺注。</p><textarea id=\"copyBox\" readonly>" + esc(m.text) +
        '</textarea><div class="row"><button type="button" class="textbtn" data-action="close-modal">合上</button></div>';
    } else if (m.type === "export") {
      inner = "<h3>导出</h3><p>整本册子的 JSON。可以复制，也可以另存。</p><textarea id=\"exportBox\" readonly>" +
        esc(m.text) + '</textarea><div class="row"><button type="button" class="textbtn" data-action="download">另存文件</button><button type="button" class="textbtn" data-action="close-modal">合上</button></div>';
    } else if (m.type === "import") {
      inner = "<h3>导入</h3><p>先检查链。对得上才允许替换本机册子。替换要再输入「替换」。</p>" +
        '<input id="importFile" type="file" accept="application/json,.json"><textarea id="importBox" placeholder="或把 JSON 贴在这里">' +
        esc(state.importText) + "</textarea><p id=\"importMsg\">" + esc(m.message || "") + "</p>" +
        '<label class="field"><span>确认替换时输入「替换」</span><input id="importPhrase" type="text" autocomplete="off"></label>' +
        '<div class="row"><button type="button" class="textbtn" data-action="import-check">先检查</button><button type="button" class="textbtn" id="importGo" data-action="import-replace"' +
        (state.importChecked ? "" : " disabled") + ">确认替换</button><button type=\"button\" class=\"textbtn\" data-action=\"close-modal\">取消</button></div>";
    } else if (m.type === "tomb") {
      inner = "<h3>立墓碑</h3><p>正文、哈希、这一环都留着。册子只把这一页标成撤回。再输入「墓碑」才算数。</p>" +
        '<label class="field"><span>输入墓碑</span><input id="tombPhrase" type="text" autocomplete="off"></label>' +
        '<div class="row"><button type="button" class="textbtn" id="tombGo" data-action="confirm-tomb" data-id="' + esc(m.id) +
        '" disabled>确认立墓碑</button><button type="button" class="textbtn" data-action="close-modal">取消</button></div>';
    } else if (m.type === "revise") {
      inner = "<h3>另起一版</h3><p>第一版不会被这张纸盖住。新版本附在后面，对照时才看得见差额。</p>" +
        '<label class="field"><span>署名</span><input id="revAuthor" type="text" value="用户"></label>' +
        '<label class="field"><span>这一版</span><textarea id="revText">' + esc(m.text) + "</textarea></label>" +
        '<label class="field"><span>一句说明</span><input id="revNote" type="text" value="自己另起的一版"></label>' +
        '<div class="row"><button type="button" class="textbtn" data-action="confirm-revise" data-id="' + esc(m.id) +
        '">封成新版本</button><button type="button" class="textbtn" data-action="close-modal">取消</button></div>';
    } else if (m.type === "reset") {
      inner = "<h3>恢复种子</h3><p>本机追加的页、墓碑和运行时笺注会从这台浏览器里拿掉。装订时的原文还在种子文件里。输入「恢复」。</p>" +
        '<label class="field"><span>输入恢复</span><input id="resetPhrase" type="text" autocomplete="off"></label>' +
        '<div class="row"><button type="button" class="textbtn" id="resetGo" data-action="confirm-reset" disabled>确认恢复</button><button type="button" class="textbtn" data-action="close-modal">取消</button></div>';
    }
    root.innerHTML = '<div class="modal-back" data-action="close-modal"><div class="modal" role="dialog">' + inner + "</div></div>";
  }

  function render() {
    var test = Folio.selfTest();
    var fatal = document.getElementById("fatal");
    fatal.textContent = test ? ("哈希自检失败：" + test) : "";
    var r = route();
    paintStatus();
    navState(r.view);
    var spineId = (r.view === "read" || r.view === "lab") ? r.id : "";
    paintSpine(spineId);
    var entry = find(r.id);
    if (r.view === "timeline") renderTimeline();
    else if (r.view === "trust") renderTrust();
    else if (r.view === "new") renderNew();
    else if (!entry) {
      document.getElementById("sheet").innerHTML = '<article class="sheet-inner"><p>这本册子是空的。</p></article>';
      document.getElementById("margin").innerHTML = "";
    } else if (r.view === "lab") renderLab(entry, r.flip);
    else renderRead(entry, r.rev);
    renderModal();
    document.getElementById("foot").textContent = "j / k 翻页 · 笺注可以整层揭掉 · 细线对上正文 · 题签和笺注不进哈希 · 本页不访问网络";
    drawLeaders();
    requestAnimationFrame(drawLeaders);
    if (state.focus) {
      var el = document.querySelector(state.focus);
      if (el) el.focus();
      state.focus = "";
    }
  }

  function openModal(modal, focus) {
    state.modal = modal;
    state.focus = focus || "";
    render();
  }

  function onClick(e) {
    if (e.target.id === "q") return;
    var goBtn = e.target.closest("[data-go]");
    if (goBtn && !(e.target.closest(".modal"))) {
      go(goBtn.getAttribute("data-go"));
      return;
    }
    var entryBtn = e.target.closest("[data-entry]");
    if (entryBtn && !e.target.closest(".modal")) {
      go("#/read/" + entryBtn.getAttribute("data-entry"));
      return;
    }
    var topicBtn = e.target.closest("[data-topic]");
    if (topicBtn && topicBtn.closest("#filters")) {
      state.topic = topicBtn.getAttribute("data-topic") || "";
      render();
      return;
    }
    var jump = e.target.closest("[data-jump-note]");
    if (jump) {
      focusPair(jump.getAttribute("data-jump-note"), "mark");
      return;
    }
    var markHit = e.target.closest("mark[data-note]");
    if (markHit) {
      focusPair(markHit.getAttribute("data-note"), "note");
      return;
    }
    var act = e.target.closest("[data-action]");
    if (!act) return;
    var action = act.getAttribute("data-action");
    var id = act.getAttribute("data-id");
    if (action === "toggle-notes") {
      state.notesOn = !state.notesOn;
      render();
    } else if (action === "theme") {
      var next = document.documentElement.dataset.theme === "dark" ? "light" : "dark";
      document.documentElement.dataset.theme = next;
      localStorage.setItem("folio.theme", next);
      render();
    } else if (action === "export") {
      openModal({ type: "export", text: JSON.stringify(state.doc, null, 2) }, "#exportBox");
    } else if (action === "download") {
      var blob = new Blob([state.modal.text], { type: "application/json" });
      var url = URL.createObjectURL(blob);
      var a = document.createElement("a");
      a.href = url;
      a.download = "folio-export.json";
      a.click();
      setTimeout(function () { URL.revokeObjectURL(url); }, 800);
    } else if (action === "import") {
      state.importText = "";
      state.importChecked = false;
      openModal({ type: "import", message: "" }, "#importBox");
    } else if (action === "import-check") {
      runImportCheck();
    } else if (action === "import-replace") {
      var phrase = document.getElementById("importPhrase");
      if (!state.importChecked || !phrase || phrase.value !== "替换") {
        state.modal.message = "还没检查通过，或确认词不是「替换」。";
        render();
        return;
      }
      try {
        state.doc = JSON.parse(state.importText);
        state.doc.trust.aiMayWrite.original = false;
        persist();
        state.modal = null;
        go("#/read/" + (state.doc.entries[0] ? state.doc.entries[0].id : ""));
      } catch (err) {
        state.modal.message = "替换失败。";
        render();
      }
    } else if (action === "close-modal") {
      if (e.target.closest(".modal") && e.target.classList.contains("modal-back") === false && action === "close-modal" && e.target !== act) return;
      state.modal = null;
      render();
    } else if (action === "revise") {
      var entry = find(id);
      openModal({ type: "revise", id: id, text: Folio.originalOf(entry).text }, "#revText");
    } else if (action === "confirm-revise") {
      var text = document.getElementById("revText").value;
      var author = document.getElementById("revAuthor").value.trim() || "用户";
      var note = document.getElementById("revNote").value.trim();
      if (!text.trim()) return;
      if (author === "用户") author = "用户";
      var made = Folio.revise(state.doc, id, text, author === "用户" ? "用户" : author, note, nowStamp(), "local");
      state.revPick[id] = made.n;
      persist();
      state.modal = null;
      render();
    } else if (action === "tombstone") {
      openModal({ type: "tomb", id: id }, "#tombPhrase");
    } else if (action === "confirm-tomb") {
      var word = document.getElementById("tombPhrase").value;
      try {
        Folio.tombstone(state.doc, id, word, nowStamp());
        persist();
        state.modal = null;
        render();
      } catch (err) {
        return;
      }
    } else if (action === "copy") {
      openModal({ type: "copy", text: Folio.originalOf(find(id)).text }, "#copyBox");
    } else if (action === "set-rev") {
      state.revPick[id] = Number(act.getAttribute("data-rev"));
      render();
    } else if (action === "sort") {
      state.sort = act.getAttribute("data-sort");
      render();
    } else if (action === "ai-original") {
      Folio.aiWrite(state.doc, "original", (state.doc.entries[0] ? state.doc.entries[0].id : ""), "这句不该出现", nowStamp());
      persist();
      render();
    } else if (action === "ai-note") {
      if (!state.doc.entries.length) return;
      var target = state.doc.entries[0].id;
      Folio.aiWrite(state.doc, "annotation", target, "这是运行时写进笺注的一句。正文的哈希不应变化。", nowStamp());
      persist();
      render();
    } else if (action === "ai-read") {
      state.showReadout = true;
      render();
    } else if (action === "lab-tamper") {
      var labEntry = find(id);
      state.labFor = id;
      state.labDraft = Folio.tamperOnce(Folio.originalOf(labEntry).text);
      render();
    } else if (action === "lab-reset") {
      state.labFor = "";
      ensureLab(find(id), null);
      render();
    } else if (action === "reset-ask") {
      openModal({ type: "reset" }, "#resetPhrase");
    } else if (action === "confirm-reset") {
      var rp = document.getElementById("resetPhrase");
      if (!rp || rp.value !== "恢复") return;
      localStorage.removeItem(KEY);
      state.doc = clone(window.FOLIO_SEED);
      state.dirty = false;
      state.revPick = {};
      state.modal = null;
      render();
    }
  }

  function runImportCheck() {
    var box = document.getElementById("importBox");
    var file = document.getElementById("importFile");
    function finish(text) {
      state.importText = text;
      try {
        var doc = JSON.parse(text);
        var errors = Folio.verify(doc);
        state.importChecked = errors.length === 0;
        state.modal.message = errors.length ? ("对不上：" + errors.slice(0, 4).join("；")) : ("链完好，" + doc.entries.length + " 页。可以替换。");
      } catch (err) {
        state.importChecked = false;
        state.modal.message = "这不是一本册子的 JSON。";
      }
      render();
    }
    if (file && file.files && file.files[0]) {
      var reader = new FileReader();
      reader.onload = function () { finish(String(reader.result || "")); };
      reader.readAsText(file.files[0], "utf-8");
      return;
    }
    finish(box ? box.value : "");
  }

  function onInput(e) {
    if (e.target.id === "q") {
      state.query = e.target.value;
      var r = route();
      paintSpine((r.view === "read" || r.view === "lab") ? r.id : "");
      return;
    }
    if (e.target.id === "labBox") {
      state.labDraft = e.target.value;
      var entry = find(route().id);
      var slot = document.getElementById("labResult");
      if (slot && entry) slot.innerHTML = labResultHtml(entry);
      return;
    }
    if (e.target.id === "marginDraft") state.marginDraft = e.target.value;
    if (e.target.id === "tombPhrase") {
      var goBtn = document.getElementById("tombGo");
      if (goBtn) goBtn.disabled = e.target.value !== "墓碑";
    }
    if (e.target.id === "resetPhrase") {
      var rg = document.getElementById("resetGo");
      if (rg) rg.disabled = e.target.value !== "恢复";
    }
    if (e.target.id === "importPhrase") {
      var ig = document.getElementById("importGo");
      if (ig) ig.disabled = !(state.importChecked && e.target.value === "替换");
    }
    if (e.target.id === "importBox") {
      state.importText = e.target.value;
      state.importChecked = false;
    }
  }

  function onChange(e) {
    if (e.target.getAttribute("data-trust")) {
      var parts = e.target.getAttribute("data-trust").split(".");
      if (parts[0] === "aiMayWrite" && parts[1] === "original") return;
      state.doc.trust[parts[0]][parts[1]] = e.target.checked;
      state.doc.trust.aiMayWrite.original = false;
      persist();
      render();
      return;
    }
    if (e.target.getAttribute("data-layer")) {
      state.layers[e.target.getAttribute("data-layer")] = e.target.checked;
      render();
    }
  }

  function onSubmit(e) {
    var form = e.target;
    if (form.id === "newForm") {
      e.preventDefault();
      var data = new FormData(form);
      var text = String(data.get("text") || "");
      var title = String(data.get("title") || "").trim();
      if (!text.trim() || !title) return;
      var id = "local-" + Folio.sha256(text).slice(0, 8);
      var n = 2;
      while (find(id)) { id = "local-" + Folio.sha256(text + String(n)).slice(0, 8); n++; }
      var at = String(data.get("date")) + " 00:00";
      Folio.appendEntry(state.doc, {
        id: id,
        diaryDate: String(data.get("date")),
        at: at,
        text: text,
        title: title,
        topic: String(data.get("topic"))
      });
      persist();
      go("#/read/" + id);
      return;
    }
    if (form.getAttribute("data-action") === "save-note") {
      e.preventDefault();
      var draft = state.marginDraft.trim();
      if (!draft) return;
      Folio.humanNote(state.doc, form.getAttribute("data-id"), state.marginDraft, nowStamp());
      state.marginDraft = "";
      persist();
      render();
    }
  }

  function onKey(e) {
    if (e.key === "Escape" && state.modal) {
      state.modal = null;
      render();
      return;
    }
    if (e.target.closest("input, textarea, select")) return;
    var vis = visibleEntries();
    var r = route();
    var idx = vis.findIndex(function (item) { return item.id === r.id; });
    if (e.key === "j" && idx >= 0 && idx < vis.length - 1) go("#/read/" + vis[idx + 1].id);
    if (e.key === "k" && idx > 0) go("#/read/" + vis[idx - 1].id);
  }

  function focusPair(id, scrollTo) {
    state.hoverNote = id || "";
    paintPair(id);
    if (!id) return;
    var target = scrollTo === "note"
      ? document.querySelector('.note[data-note-id="' + CSS.escape(id) + '"]')
      : document.querySelector('mark[data-note="' + CSS.escape(id) + '"]');
    if (target) target.scrollIntoView({ block: "center" });
    paintPair(id);
  }

  function paintPair(id) {
    document.querySelectorAll("mark[data-note], .note[data-note-id]").forEach(function (el) {
      var mine = (el.getAttribute("data-note") || el.getAttribute("data-note-id")) === id;
      el.classList.toggle("lit", !!id && mine);
    });
    drawLeaders();
  }

  function drawLeaders() {
    var svg = document.getElementById("leaders");
    var desk = document.querySelector(".desk");
    if (!svg || !desk) return;
    var deskBox = desk.getBoundingClientRect();
    var width = Math.max(1, deskBox.width);
    var height = Math.max(1, desk.offsetHeight || deskBox.height);
    svg.setAttribute("viewBox", "0 0 " + width + " " + height);
    svg.setAttribute("width", String(width));
    svg.setAttribute("height", String(height));
    var hover = state.hoverNote;
    var parts = [];
    var marks = document.querySelectorAll("mark[data-note]");
    marks.forEach(function (mark) {
      var id = mark.getAttribute("data-note");
      var note = document.querySelector('.note[data-note-id="' + CSS.escape(id) + '"]');
      var prose = mark.closest(".prose");
      if (!note || !prose) return;
      var a = mark.getBoundingClientRect();
      var b = note.getBoundingClientRect();
      var viewTop = 0;
      var viewBottom = window.innerHeight || document.documentElement.clientHeight;
      if (a.bottom < viewTop + 4 || a.top > viewBottom - 4) return;
      if (b.bottom < viewTop + 4 || b.top > viewBottom - 4) return;
      var pr = prose.getBoundingClientRect();
      var x1 = pr.right - deskBox.left;
      var y1 = (a.top + a.height / 2) - deskBox.top;
      var x2 = b.left - deskBox.left;
      var y2 = (b.top + Math.min(22, b.height / 2)) - deskBox.top;
      var cls = !hover ? "leader" : (hover === id ? "leader on" : "leader dim");
      var rail = x2 - 12;
      if (y2 > y1 + 28 && x2 < x1 - 8) rail = Math.min(width - 8, Math.max(x1, x2) + 14);
      if (rail < x1 + 6) rail = x1 + 6;
      if (rail > width - 4) rail = width - 4;
      var d = "M" + x1.toFixed(1) + "," + y1.toFixed(1) + " H" + rail.toFixed(1) + " V" + y2.toFixed(1) + " H" + x2.toFixed(1);
      parts.push('<path class="' + cls + '" d="' + d + '"></path>');
      parts.push('<circle class="' + cls + '" cx="' + x1.toFixed(1) + '" cy="' + y1.toFixed(1) + '" r="2.4"></circle>');
      parts.push('<circle class="' + cls + '" cx="' + x2.toFixed(1) + '" cy="' + y2.toFixed(1) + '" r="2.4"></circle>');
    });
    svg.innerHTML = parts.join("");
  }

  function boot() {
    var frame = Number(new URLSearchParams(location.search).get("vw"));
    if (frame >= 320 && frame <= 1600) {
      document.documentElement.style.width = frame + "px";
      document.body.style.width = frame + "px";
    }
    if (!window.Folio || !window.FOLIO_SEED) {
      document.getElementById("fatal").textContent = "册子脚本没有装上。";
      return;
    }
    var q = new URLSearchParams(location.search);
    var theme = q.get("theme") || localStorage.getItem("folio.theme") || "light";
    document.documentElement.dataset.theme = theme === "dark" ? "dark" : "light";
    var raw = null;
    raw = null; // The server sidecar is authoritative for annotations.
    if (raw) {
      try {
        state.doc = JSON.parse(raw);
        state.dirty = true;
      } catch (err2) {
        state.doc = clone(window.FOLIO_SEED);
      }
    } else {
      state.doc = clone(window.FOLIO_SEED);
    }
    state.doc.trust = state.doc.trust || clone(window.FOLIO_SEED.trust);
    state.doc.trust.aiMayWrite = state.doc.trust.aiMayWrite || {};
    state.doc.trust.aiMayWrite.original = false;
    if (!location.hash && state.doc.entries.length) location.hash = "#/read/"+encodeURIComponent(state.doc.entries[0].id);
    if (q.get("demo") === "refuse" && !state.didDemo) {
      state.didDemo = true;
      Folio.aiWrite(state.doc, "original", (state.doc.entries[0] ? state.doc.entries[0].id : ""), "这句不该出现", nowStamp());
      persist();
    }
    document.body.addEventListener("click", onClick);
    document.body.addEventListener("input", onInput);
    document.body.addEventListener("change", onChange);
    document.body.addEventListener("submit", onSubmit);
    document.addEventListener("keydown", onKey);
    document.body.addEventListener("mouseover", function (e) {
      var host = e.target.closest("mark[data-note], .note[data-note-id]");
      var id = host ? (host.getAttribute("data-note") || host.getAttribute("data-note-id")) : "";
      if (id === state.hoverNote) return;
      state.hoverNote = id;
      paintPair(id);
    });
    window.addEventListener("hashchange", render);
    window.addEventListener("resize", drawLeaders);
    window.addEventListener("scroll", drawLeaders, true);
    var margin = document.getElementById("margin");
    if (margin) margin.addEventListener("scroll", drawLeaders);
    if (document.fonts && document.fonts.ready) document.fonts.ready.then(drawLeaders);
    render();
  }

  boot();
})().catch(error=>{document.getElementById('fatal').textContent=error.message;});
