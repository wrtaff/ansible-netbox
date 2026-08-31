#!/usr/bin/env python3
# Filename:       dillo-wrapper.py
# Purpose:        Wrapper for Dillo to automatically authenticate against Trac instances.
# Context:        http://trac.gafla.us.com/ticket/4187

import os
import sys
import urllib.parse
import netrc

REAL_DILLO = "/usr/bin/dillo"
TRAC_HOSTS = {
    "trac.gafla.us.com",
    "trac.home.arpa",
    "trac-lxc.home.arpa",
    "192.168.0.99",
}

def get_credentials(hostname):
    """Retrieve username and password for the given host from .netrc, ~/.config/trac/auth, or env."""
    # 1. Check ~/.netrc
    try:
        n = netrc.netrc()
        auth = n.authenticators(hostname)
        if auth:
            return auth[0], auth[2]
        for alias in TRAC_HOSTS:
            auth = n.authenticators(alias)
            if auth:
                return auth[0], auth[2]
    except Exception:
        pass

    # 2. Check environment variables
    user = os.getenv("TRAC_USER", "will")
    password = os.getenv("TRAC_PASSWORD")
    if password:
        return user, password

    # 3. Check ~/.config/trac/auth
    auth_file = os.path.expanduser("~/.config/trac/auth")
    if os.path.exists(auth_file):
        try:
            with open(auth_file, "r", encoding="utf-8") as f:
                content = f.read().strip()
                if ":" in content:
                    u, p = content.split(":", 1)
                    return u.strip(), p.strip()
                elif content:
                    return user, content
        except Exception:
            pass

    return None, None

def transform_arg(arg):
    """If argument is a Trac URL without embedded credentials, inject them."""
    if not (arg.startswith("http://") or arg.startswith("https://")):
        return arg
    try:
        parsed = urllib.parse.urlparse(arg)
        hostname = (parsed.hostname or "").lower()
        if hostname in TRAC_HOSTS and not parsed.username:
            user, password = get_credentials(hostname)
            if user and password:
                quoted_user = urllib.parse.quote(user, safe="")
                quoted_pass = urllib.parse.quote(password, safe="")
                port_str = f":{parsed.port}" if parsed.port else ""
                netloc = f"{quoted_user}:{quoted_pass}@{parsed.hostname}{port_str}"
                return urllib.parse.urlunparse(parsed._replace(netloc=netloc))
    except Exception:
        pass
    return arg

def main():
    real_bin = REAL_DILLO if os.path.exists(REAL_DILLO) else "/usr/bin/dillo"
    args = [real_bin] + [transform_arg(a) for a in sys.argv[1:]]
    try:
        os.execv(real_bin, args)
    except FileNotFoundError:
        print(f"Error: Real Dillo binary not found at {real_bin}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()
