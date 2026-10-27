"""Config loading. The core ships NO default data paths: they must come from
the config file or environment variables (ATLAS_DATA_DIR, ATLAS_OUT_DIR)."""
import os, json, sys
try:
    import tomllib
except ImportError:  # py<3.11
    tomllib = None

class ConfigError(Exception):
    pass

def _load_dotenv(path):
    if not os.path.exists(path):
        return
    for line in open(path, encoding="utf-8"):
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip())

def load(path):
    _load_dotenv(os.path.join(os.path.dirname(os.path.abspath(path)), ".env"))
    _load_dotenv(".env")
    raw = open(path, "rb").read()
    cfg = tomllib.loads(raw.decode("utf-8")) if path.endswith(".toml") else json.loads(raw)
    base = os.path.dirname(os.path.abspath(path))
    def resolve(key, env):
        v = os.environ.get(env) or cfg.get("paths", {}).get(key)
        if not v:
            raise ConfigError(f"missing {key}: set {env} or [paths].{key} in config (core has no default)")
        v = os.path.expandvars(os.path.expanduser(v))
        return v if os.path.isabs(v) else os.path.normpath(os.path.join(base, v))
    cfg["data_dir"] = resolve("data_dir", "ATLAS_DATA_DIR")
    cfg["out_dir"] = resolve("out_dir", "ATLAS_OUT_DIR")
    cfg["config_dir"] = base
    return cfg
