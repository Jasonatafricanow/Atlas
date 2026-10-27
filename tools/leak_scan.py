"""Scan tracked files (or given paths) for personal-data leaks. Exit 1 on any hit.
Usage: python tools/leak_scan.py [--all-files] [paths...]
Private terms (real names, chat titles...) are read from $ATLAS_LEAK_DENYLIST,
a file that lives OUTSIDE the repo, so the denylist itself never leaks."""
import os, re, sys, subprocess

PATTERNS = {
    "windows_abs_path": r"\b[A-Za-z]:[\\/](?:Users|projects|WeChat|Documents)",
    "wechat_export": r"WeChatExport|微信聊天记录导出|\[ME\]",
    "cn_mobile": r"(?<!\d)1[3-9]\d{9}(?!\d)",
    "intl_phone": r"\+\d{1,3}[ -]?\d{2,4}[ -]?\d{3,4}[ -]?\d{3,4}",
    "cn_id_card": r"(?<!\d)\d{17}[\dXx](?!\d)",
    "email": r"[\w.+-]+@(?!example\.(?:com|org))[\w-]+\.[\w.]+",
    "bank_card": r"(?<!\d)\d{16,19}(?!\d)",
    "secret_like": r"(?i)(api[_-]?key|secret|token|password)\s*[:=]\s*['\"][^'\"]{8,}",
    "private_data_files": r"PORTRAIT_v\d|kg_full\.json|trades\.json",
}
SKIP_EXT = {".png", ".jpg", ".gif", ".ico", ".pdf", ".zip"}
SELF = os.path.normpath("tools/leak_scan.py")

def files(args):
    if args:
        return args
    try:
        out = subprocess.run(["git", "ls-files", "-co", "--exclude-standard"], capture_output=True, text=True, check=True).stdout
        return [f for f in out.splitlines() if f]
    except Exception:
        return [os.path.join(r, f) for r, d, fs in os.walk(".") if ".git" not in r for f in fs]

def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    rx = {k: re.compile(v) for k, v in PATTERNS.items()}
    deny = []
    p = os.environ.get("ATLAS_LEAK_DENYLIST")
    if p and os.path.exists(p):
        deny = [l.strip() for l in open(p, encoding="utf-8") if l.strip() and not l.startswith("#")]
    hits = 0
    for f in files(args):
        if os.path.splitext(f)[1].lower() in SKIP_EXT or os.path.normpath(f) == SELF or not os.path.isfile(f):
            continue
        if f.endswith(".sqlite") or os.path.basename(f) == ".env":
            print(f"{f}: forbidden file type in repo"); hits += 1; continue
        try:
            text = open(f, encoding="utf-8").read()
        except UnicodeDecodeError:
            continue
        for n, line in enumerate(text.splitlines(), 1):
            for k, r in rx.items():
                if r.search(line):
                    print(f"{f}:{n}: [{k}]"); hits += 1
            for t in deny:
                if t in line:
                    print(f"{f}:{n}: [denylist term #{deny.index(t)+1}]"); hits += 1  # never echo the term
    print(f"leak_scan: {hits} hit(s), denylist terms loaded: {len(deny)}")
    sys.exit(1 if hits else 0)

if __name__ == "__main__":
    main()
