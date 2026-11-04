/* 原文册规则。与 folio_model.py 对齐：链只覆盖第一版原文，原文层不可写。 */
(function (root, factory) {
  var api = factory();
  if (typeof module === "object" && module.exports) module.exports = api;
  root.Folio = api;
})(typeof globalThis !== "undefined" ? globalThis : this, function () {
  var GENESIS = "GENESIS";
  var TOMBSTONE_PHRASE = "墓碑";
  var SHA_ABC = "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad";
  var SHA_EMPTY = "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855";

  var K = [
    0x428a2f98, 0x71374491, 0xb5c0fbcf, 0xe9b5dba5, 0x3956c25b, 0x59f111f1, 0x923f82a4, 0xab1c5ed5,
    0xd807aa98, 0x12835b01, 0x243185be, 0x550c7dc3, 0x72be5d74, 0x80deb1fe, 0x9bdc06a7, 0xc19bf174,
    0xe49b69c1, 0xefbe4786, 0x0fc19dc6, 0x240ca1cc, 0x2de92c6f, 0x4a7484aa, 0x5cb0a9dc, 0x76f988da,
    0x983e5152, 0xa831c66d, 0xb00327c8, 0xbf597fc7, 0xc6e00bf3, 0xd5a79147, 0x06ca6351, 0x14292967,
    0x27b70a85, 0x2e1b2138, 0x4d2c6dfc, 0x53380d13, 0x650a7354, 0x766a0abb, 0x81c2c92e, 0x92722c85,
    0xa2bfe8a1, 0xa81a664b, 0xc24b8b70, 0xc76c51a3, 0xd192e819, 0xd6990624, 0xf40e3585, 0x106aa070,
    0x19a4c116, 0x1e376c08, 0x2748774c, 0x34b0bcb5, 0x391c0cb3, 0x4ed8aa4a, 0x5b9cca4f, 0x682e6ff3,
    0x748f82ee, 0x78a5636f, 0x84c87814, 0x8cc70208, 0x90befffa, 0xa4506ceb, 0xbef9a3f7, 0xc67178f2
  ];

  function rotr(x, n) {
    return (x >>> n) | (x << (32 - n));
  }

  function utf8(str) {
    var out = [];
    for (var i = 0; i < str.length; i++) {
      var c = str.charCodeAt(i);
      if (c >= 0xd800 && c <= 0xdbff && i + 1 < str.length) {
        var n = str.charCodeAt(i + 1);
        if (n >= 0xdc00 && n <= 0xdfff) {
          c = 0x10000 + ((c - 0xd800) << 10) + (n - 0xdc00);
          i++;
        }
      }
      if (c < 0x80) out.push(c);
      else if (c < 0x800) out.push(0xc0 | (c >> 6), 0x80 | (c & 0x3f));
      else if (c < 0x10000) out.push(0xe0 | (c >> 12), 0x80 | ((c >> 6) & 0x3f), 0x80 | (c & 0x3f));
      else out.push(0xf0 | (c >> 18), 0x80 | ((c >> 12) & 0x3f), 0x80 | ((c >> 6) & 0x3f), 0x80 | (c & 0x3f));
    }
    return out;
  }

  function sha256(str) {
    if (typeof str !== "string") throw new Error("hash input must be string");
    var bytes = utf8(str);
    var bitLen = bytes.length * 8;
    bytes.push(0x80);
    while (bytes.length % 64 !== 56) bytes.push(0);
    var hi = Math.floor(bitLen / 0x100000000);
    var lo = bitLen >>> 0;
    for (var s = 24; s >= 0; s -= 8) bytes.push((hi >>> s) & 0xff);
    for (s = 24; s >= 0; s -= 8) bytes.push((lo >>> s) & 0xff);

    var H = [
      0x6a09e667, 0xbb67ae85, 0x3c6ef372, 0xa54ff53a,
      0x510e527f, 0x9b05688c, 0x1f83d9ab, 0x5be0cd19
    ];
    var w = new Array(64);
    for (var off = 0; off < bytes.length; off += 64) {
      for (var t = 0; t < 16; t++) {
        var p = off + t * 4;
        w[t] = ((bytes[p] << 24) | (bytes[p + 1] << 16) | (bytes[p + 2] << 8) | bytes[p + 3]) >>> 0;
      }
      for (t = 16; t < 64; t++) {
        var x = w[t - 15];
        var y = w[t - 2];
        var s0 = (rotr(x, 7) ^ rotr(x, 18) ^ (x >>> 3)) >>> 0;
        var s1 = (rotr(y, 17) ^ rotr(y, 19) ^ (y >>> 10)) >>> 0;
        w[t] = (w[t - 16] + s0 + w[t - 7] + s1) >>> 0;
      }
      var a = H[0], b = H[1], c = H[2], d = H[3], e = H[4], f = H[5], g = H[6], h = H[7];
      for (t = 0; t < 64; t++) {
        var S1 = (rotr(e, 6) ^ rotr(e, 11) ^ rotr(e, 25)) >>> 0;
        var ch = ((e & f) ^ (~e & g)) >>> 0;
        var temp1 = (h + S1 + ch + K[t] + w[t]) >>> 0;
        var S0 = (rotr(a, 2) ^ rotr(a, 13) ^ rotr(a, 22)) >>> 0;
        var maj = ((a & b) ^ (a & c) ^ (b & c)) >>> 0;
        var temp2 = (S0 + maj) >>> 0;
        h = g; g = f; f = e;
        e = (d + temp1) >>> 0;
        d = c; c = b; b = a;
        a = (temp1 + temp2) >>> 0;
      }
      H[0] = (H[0] + a) >>> 0;
      H[1] = (H[1] + b) >>> 0;
      H[2] = (H[2] + c) >>> 0;
      H[3] = (H[3] + d) >>> 0;
      H[4] = (H[4] + e) >>> 0;
      H[5] = (H[5] + f) >>> 0;
      H[6] = (H[6] + g) >>> 0;
      H[7] = (H[7] + h) >>> 0;
    }
    var hex = "";
    for (var i = 0; i < 8; i++) hex += H[i].toString(16).padStart(8, "0");
    return hex;
  }

  function chainLink(prev, originalSha, entryId) {
    return sha256(prev + "\n" + originalSha + "\n" + entryId);
  }

  function tamperOnce(text) {
    if (typeof text !== "string") throw new Error("tamper input must be string");
    var i = text.indexOf("的");
    if (i >= 0) return text.slice(0, i) + "得" + text.slice(i + 1);
    if (text.charAt(text.length - 1) === "。") return text.slice(0, -1) + "，";
    return text + "。";
  }

  function projectTamper(doc, entryId, tamperedText) {
    var entries = (doc && doc.entries) || [];
    var index = -1;
    for (var n = 0; n < entries.length; n++) if (entries[n].id === entryId) index = n;
    if (index < 0) throw new Error("missing " + entryId);
    var original = entries[index].versions[0].text;
    var prev = GENESIS;
    var changed = tamperedText !== original;
    var rows = [];
    for (n = 0; n < entries.length; n++) {
      var entry = entries[n];
      var text = n === index ? tamperedText : entry.versions[0].text;
      var digest = sha256(text);
      var link = chainLink(prev, digest, entry.id);
      var status = n < index ? "before" : n === index ? (changed ? "break" : "same") : (changed ? "after" : "before");
      rows.push({
        index: n,
        id: entry.id,
        title: entry.title || "",
        status: status,
        stored: entry.chain,
        projected: link,
        stored_prev: entry.chain_prev,
        projected_prev: prev,
        matches_stored: link === entry.chain
      });
      prev = link;
    }
    var brokenAfter = 0;
    for (n = 0; n < rows.length; n++) if (rows[n].status === "after" && !rows[n].matches_stored) brokenAfter++;
    return { index: index, same: !changed, broken_after: brokenAfter, rows: rows };
  }

  function layoutProse(text, ranges) {
    ranges = ranges || [];
    function cuts(abs) {
      for (var r = 0; r < ranges.length; r++) {
        if (abs > ranges[r].i && abs < ranges[r].j) return true;
      }
      return false;
    }
    function splitSoft(para, base) {
      if (!para) return [];
      var sentences = [];
      var i = 0;
      while (i < para.length) {
        var j = i;
        while (j < para.length && "。！？".indexOf(para.charAt(j)) < 0) j++;
        if (j < para.length) j++;
        sentences.push({ text: para.slice(i, j), start: i });
        i = j;
      }
      var chunks = [];
      var buf = "";
      var bufStart = 0;
      function flush() {
        if (!buf) return;
        chunks.push({ text: buf, base: base + bufStart });
        buf = "";
      }
      for (var s = 0; s < sentences.length; s++) {
        var sent = sentences[s];
        if (!buf) {
          buf = sent.text;
          bufStart = sent.start;
          continue;
        }
        if (buf.length >= 52 && !cuts(base + bufStart + buf.length)) {
          flush();
          buf = sent.text;
          bufStart = sent.start;
        } else buf += sent.text;
      }
      flush();
      if (chunks.length >= 2) {
        var tail = chunks[chunks.length - 1];
        var prev = chunks[chunks.length - 2];
        if (tail.text.length < 18 && !cuts(tail.base)) {
          prev.text += tail.text;
          chunks.pop();
        }
      }
      return chunks;
    }
    var blocks = [];
    var pos = 0;
    while (pos <= text.length) {
      var nl = text.indexOf("\n", pos);
      var end = nl < 0 ? text.length : nl;
      var para = text.slice(pos, end);
      var sep = "";
      var next = end;
      if (nl >= 0) {
        next = nl;
        while (next < text.length && text.charAt(next) === "\n") next++;
        sep = text.slice(nl, next);
      }
      var soft = splitSoft(para, pos);
      if (!soft.length && sep) {
        if (blocks.length) blocks[blocks.length - 1].sep += sep;
        else blocks.push({ text: "", base: pos, hard: true, sep: sep });
      }
      for (var s = 0; s < soft.length; s++) {
        blocks.push({
          text: soft[s].text,
          base: soft[s].base,
          hard: s === 0,
          sep: s === soft.length - 1 ? sep : ""
        });
      }
      if (nl < 0) break;
      pos = next;
      if (pos >= text.length) break;
    }
    if (!blocks.length) blocks.push({ text: "", base: 0, hard: true, sep: "" });
    return blocks;
  }

  function tokenize(text) {
    var stops = { "，": 1, "。": 1, "！": 1, "？": 1, "、": 1, "；": 1, "：": 1 };
    var out = [];
    var i = 0;
    while (i < text.length) {
      if (text.charAt(i) === "\n") {
        var j = i + 1;
        while (j < text.length && text.charAt(j) === "\n") j++;
        out.push(text.slice(i, j));
        i = j;
        continue;
      }
      j = i;
      while (j < text.length && !stops[text.charAt(j)] && text.charAt(j) !== "\n") j++;
      if (j < text.length && stops[text.charAt(j)]) j++;
      out.push(text.slice(i, j));
      i = j;
    }
    return out;
  }

  function diffOps(a, b) {
    if (a === b) return a ? [["equal", a]] : [];
    return diffSeq(tokenize(a), tokenize(b));
  }

  function diffSeq(a, b) {
    var n = a.length, m = b.length;
    if (n * m > 1500000) {
      var rough = [];
      if (n) rough.push(["delete", a.join("")]);
      if (m) rough.push(["insert", b.join("")]);
      return rough;
    }
    var dp = new Array(n + 1);
    for (var i = 0; i <= n; i++) dp[i] = new Uint16Array(m + 1);
    for (i = n - 1; i >= 0; i--) {
      var ai = a[i];
      var row = dp[i];
      var nxt = dp[i + 1];
      for (var j = m - 1; j >= 0; j--) {
        if (ai === b[j]) row[j] = nxt[j + 1] + 1;
        else row[j] = nxt[j] >= row[j + 1] ? nxt[j] : row[j + 1];
      }
    }
    var ops = [];
    function push(op, ch) {
      if (ops.length && ops[ops.length - 1][0] === op) ops[ops.length - 1][1] += ch;
      else ops.push([op, ch]);
    }
    i = 0; j = 0;
    while (i < n && j < m) {
      if (a[i] === b[j]) { push("equal", a[i]); i++; j++; }
      else if (dp[i + 1][j] >= dp[i][j + 1]) { push("delete", a[i]); i++; }
      else { push("insert", b[j]); j++; }
    }
    while (i < n) { push("delete", a[i]); i++; }
    while (j < m) { push("insert", b[j]); j++; }
    return ops;
  }

  function applyOps(ops) {
    var out = "";
    for (var i = 0; i < ops.length; i++) {
      var op = ops[i][0], s = ops[i][1];
      if (op === "equal" || op === "insert") out += s;
    }
    return out;
  }

  function originalOf(entry) {
    var v = entry.versions && entry.versions[0];
    if (!v || v.role !== "original") throw new Error((entry.id || "?") + ": missing original");
    return v;
  }

  function verify(doc) {
    var errors = [];
    var prev = (doc && doc.genesis) || GENESIS;
    if (prev !== GENESIS) {
      errors.push("genesis must be GENESIS");
      prev = GENESIS;
    }
    var write = ((doc.trust || {}).aiMayWrite) || {};
    if (write.original !== false) errors.push("trust.aiMayWrite.original must be false");
    var entries = doc.entries || [];
    for (var n = 0; n < entries.length; n++) {
      var entry = entries[n];
      var eid = entry.id || "?";
      var v1;
      try { v1 = originalOf(entry); }
      catch (err) { errors.push(err.message); continue; }
      if (v1.origin !== "verbatim" && v1.origin !== "local") errors.push(eid + ": original origin");
      if (typeof v1.author !== "string" || !v1.author.trim()) errors.push(eid + ": original author missing");
      var digest = sha256(v1.text || "");
      if (digest !== v1.sha256) errors.push(eid + ": original sha mismatch");
      var expect = chainLink(prev, digest, eid);
      if (entry.chain_prev !== prev) errors.push(eid + ": chain_prev mismatch");
      if (entry.chain !== expect) errors.push(eid + ": chain mismatch");
      prev = entry.chain || expect;
      if (entry.status !== "live" && entry.status !== "tombstone") errors.push(eid + ": bad status");
      if (entry.status === "tombstone" && !entry.tombstone_at) errors.push(eid + ": tombstone missing time");
      for (var vi = 1; vi < entry.versions.length; vi++) {
        var version = entry.versions[vi];
        if (version.role === "original") errors.push(eid + ": second original");
        if (sha256(version.text || "") !== version.sha256) errors.push(eid + ": revision sha mismatch");
      }
      var notes = entry.annotations || [];
      for (var ai = 0; ai < notes.length; ai++) {
        if (sha256(notes[ai].text || "") !== notes[ai].sha256) errors.push(eid + ": annotation sha mismatch");
        if (notes[ai].anchor && v1.text.indexOf(notes[ai].anchor) < 0) errors.push(eid + ": anchor not in original");
      }
    }
    return errors;
  }

  function findEntry(doc, id) {
    for (var i = 0; i < doc.entries.length; i++) if (doc.entries[i].id === id) return doc.entries[i];
    throw new Error("missing " + id);
  }

  function revise(doc, entryId, text, author, note, at, origin) {
    var entry = findEntry(doc, entryId);
    var before = originalOf(entry).text;
    var version = {
      n: entry.versions.length + 1,
      role: "revision",
      origin: origin,
      author: author,
      text: text,
      sha256: sha256(text),
      at: at,
      note: note,
      diff_from_original: diffOps(before, text)
    };
    entry.versions.push(version);
    if (originalOf(entry).text !== before) throw new Error("original mutated");
    return version;
  }

  function tombstone(doc, entryId, phrase, at) {
    if (phrase !== TOMBSTONE_PHRASE) throw new Error("二次确认未通过");
    var entry = findEntry(doc, entryId);
    var before = originalOf(entry).text;
    var beforeSha = originalOf(entry).sha256;
    var beforeChain = entry.chain;
    entry.status = "tombstone";
    entry.tombstone_at = at;
    if (originalOf(entry).text !== before || originalOf(entry).sha256 !== beforeSha || entry.chain !== beforeChain) {
      throw new Error("tombstone mutated chain");
    }
    return entry;
  }

  function aiWrite(doc, target, entryId, text, at) {
    doc.trust = doc.trust || {};
    doc.trust.aiMayWrite = doc.trust.aiMayWrite || {};
    doc.trust.aiMayWrite.original = false;
    doc.audit = doc.audit || [];
    var event;
    if (target === "original") {
      event = { at: at, action: "write-original", result: "拒绝", detail: "原文层不可写" };
      doc.audit.push(event);
      return event;
    }
    if (target === "annotation") {
      if (!doc.trust.aiMayWrite.annotation) {
        event = { at: at, action: "write-annotation", result: "拒绝", detail: "信任边界未允许笺注" };
        doc.audit.push(event);
        return event;
      }
      var entry = findEntry(doc, entryId);
      entry.annotations.push({
        id: entryId + "-ai-" + (entry.annotations.length + 1),
        layer: "ai",
        author: "模型笺注",
        text: text,
        anchor: "",
        at: at,
        sha256: sha256(text)
      });
      event = { at: at, action: "write-annotation", result: "允许", detail: "写在笺注层" };
      doc.audit.push(event);
      return event;
    }
    if (target === "version") {
      if (!doc.trust.aiMayWrite.version) {
        event = { at: at, action: "write-version", result: "拒绝", detail: "信任边界未允许新版本" };
        doc.audit.push(event);
        return event;
      }
      revise(doc, entryId, text, "模型修订", "运行时新版本，原文未改。", at, "ai");
      event = { at: at, action: "write-version", result: "允许", detail: "另起一版" };
      doc.audit.push(event);
      return event;
    }
    event = { at: at, action: target, result: "拒绝", detail: "未知写入目标" };
    doc.audit.push(event);
    return event;
  }

  function humanNote(doc, entryId, text, at) {
    var entry = findEntry(doc, entryId);
    var note = {
      id: entryId + "-self-" + (entry.annotations.length + 1),
      layer: "self",
      author: "用户",
      text: text,
      anchor: "",
      at: at,
      sha256: sha256(text)
    };
    entry.annotations.push(note);
    if (originalOf(entry).text !== originalOf(entry).text) throw new Error("note mutated");
    return note;
  }

  function appendEntry(doc, fields) {
    var text = fields.text;
    var at = fields.at;
    var id = fields.id;
    var originalSha = sha256(text);
    var prev = doc.entries.length ? doc.entries[doc.entries.length - 1].chain : GENESIS;
    var entry = {
      id: id,
      diary_date: fields.diaryDate,
      spoken_at: at,
      time_precision: "local",
      time_note: "本机写下的一页。",
      title: fields.title,
      topic: fields.topic,
      status: "live",
      tombstone_at: null,
      cut: false,
      text_note: "",
      source: { session: "本机", file: "", line: null, kind: "user-original" },
      chain_prev: prev,
      chain: chainLink(prev, originalSha, id),
      versions: [{
        n: 1, role: "original", origin: "local", author: "用户",
        text: text, sha256: originalSha, at: at, note: ""
      }],
      annotations: []
    };
    doc.entries.push(entry);
    return entry;
  }

  function readableByAi(doc, entry) {
    var read = ((doc.trust || {}).aiMayRead) || {};
    if (entry.status === "tombstone" && !read.tombstoneBody) return false;
    return read.original !== false;
  }

  function selfTest() {
    if (sha256("abc") !== SHA_ABC) return "abc";
    if (sha256("") !== SHA_EMPTY) return "empty";
    var ops = diffOps("日记原文", "日记摘要");
    if (applyOps(ops) !== "日记摘要") return "diff-apply";
    var walked = "";
    for (var i = 0; i < ops.length; i++) if (ops[i][0] !== "insert") walked += ops[i][1];
    if (walked !== "日记原文") return "diff-base";
    return "";
  }

  return {
    GENESIS: GENESIS,
    TOMBSTONE_PHRASE: TOMBSTONE_PHRASE,
    SHA_ABC: SHA_ABC,
    sha256: sha256,
    chainLink: chainLink,
    tamperOnce: tamperOnce,
    projectTamper: projectTamper,
    layoutProse: layoutProse,
    diffOps: diffOps,
    applyOps: applyOps,
    verify: verify,
    revise: revise,
    tombstone: tombstone,
    aiWrite: aiWrite,
    humanNote: humanNote,
    appendEntry: appendEntry,
    readableByAi: readableByAi,
    originalOf: originalOf,
    selfTest: selfTest
  };
});
