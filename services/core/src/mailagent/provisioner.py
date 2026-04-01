from __future__ import annotations

import base64
import fcntl
import hashlib
import logging
import os
from pathlib import Path

logger = logging.getLogger(__name__)

DEFAULT_DMS_CONFIG_DIR = "/app/dms-config"
ACCOUNTS_FILE = "postfix-accounts.cf"


class Provisioner:
    """Manages docker-mailserver accounts via postfix-accounts.cf.

    Writes directly to the accounts file with file locking.
    docker-mailserver watches this file and reloads automatically.
    """

    def __init__(self, dms_config_dir: str = DEFAULT_DMS_CONFIG_DIR):
        self._config_dir = Path(dms_config_dir)
        self._accounts_path = self._config_dir / ACCOUNTS_FILE

    @property
    def available(self) -> bool:
        return self._config_dir.exists()

    def add_account(self, email: str, password: str) -> None:
        email = email.lower()
        if self._account_exists(email):
            logger.info("Account already exists in mailserver: %s", email)
            return

        hashed = _sha512_crypt(password)
        line = f"{email}|{{SHA512-CRYPT}}{hashed}\n"

        with open(self._accounts_path, "a", encoding="utf-8") as f:
            fcntl.flock(f.fileno(), fcntl.LOCK_EX)
            try:
                f.write(line)
            finally:
                fcntl.flock(f.fileno(), fcntl.LOCK_UN)

        logger.info("Provisioned mailbox: %s", email)

    def remove_account(self, email: str) -> None:
        email = email.lower()
        if not self._accounts_path.exists():
            return

        with open(self._accounts_path, "r+", encoding="utf-8") as f:
            fcntl.flock(f.fileno(), fcntl.LOCK_EX)
            try:
                lines = f.readlines()
                filtered = [l for l in lines if not l.startswith(f"{email}|")]
                f.seek(0)
                f.writelines(filtered)
                f.truncate()
            finally:
                fcntl.flock(f.fileno(), fcntl.LOCK_UN)

        logger.info("Removed mailbox: %s", email)

    def _account_exists(self, email: str) -> bool:
        if not self._accounts_path.exists():
            return False
        content = self._accounts_path.read_text(encoding="utf-8")
        return any(line.startswith(f"{email}|") for line in content.splitlines())

    def list_accounts(self) -> list[str]:
        if not self._accounts_path.exists():
            return []
        content = self._accounts_path.read_text(encoding="utf-8")
        return [
            line.split("|")[0]
            for line in content.splitlines()
            if "|" in line and line.strip()
        ]


# SHA-512 crypt implementation compatible with glibc/docker-mailserver
# Uses the $6$ format: $6$<salt>$<hash>
_SHA512_ROUNDS = 5000  # default rounds per spec


def _sha512_crypt(password: str, salt: str | None = None) -> str:
    """Generate a SHA-512 crypt hash compatible with /etc/shadow format."""
    if salt is None:
        salt = base64.b64encode(os.urandom(12), altchars=b"./").decode("ascii")[:16]

    try:
        import warnings

        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)
            import crypt as _crypt

        return _crypt.crypt(password, f"$6${salt}")
    except (ImportError, ModuleNotFoundError):
        pass

    # Pure-Python fallback implementing SHA-512 crypt ($6$)
    pwd = password.encode("utf-8")
    slt = salt.encode("utf-8")

    # Step 1-3: Compute digest B
    b = hashlib.sha512(pwd + slt + pwd).digest()

    # Step 4-8: Compute digest A
    a_ctx = hashlib.sha512(pwd + slt)
    plen = len(pwd)
    while plen > 64:
        a_ctx.update(b)
        plen -= 64
    a_ctx.update(b[:plen])
    plen = len(pwd)
    while plen > 0:
        if plen & 1:
            a_ctx.update(b)
        else:
            a_ctx.update(pwd)
        plen >>= 1
    a = a_ctx.digest()

    # Step 12: Compute digest DP (password hash)
    dp_ctx = hashlib.sha512()
    for _ in range(len(pwd)):
        dp_ctx.update(pwd)
    dp = dp_ctx.digest()

    # Step 13: Produce P string
    p = b""
    plen = len(pwd)
    while plen > 64:
        p += dp
        plen -= 64
    p += dp[:plen]

    # Step 14: Compute digest DS (salt hash)
    ds_ctx = hashlib.sha512()
    for _ in range(16 + a[0]):
        ds_ctx.update(slt)
    ds = ds_ctx.digest()

    # Step 15: Produce S string
    s = b""
    slen = len(slt)
    while slen > 64:
        s += ds
        slen -= 64
    s += ds[:slen]

    # Step 16: 5000 rounds
    c = a
    for i in range(_SHA512_ROUNDS):
        ctx = hashlib.sha512()
        if i & 1:
            ctx.update(p)
        else:
            ctx.update(c)
        if i % 3:
            ctx.update(s)
        if i % 7:
            ctx.update(p)
        if i & 1:
            ctx.update(c)
        else:
            ctx.update(p)
        c = ctx.digest()

    # Step 17: Encode to base64
    _b64 = "./0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz"

    def _encode_triple(b1: int, b2: int, b3: int, n: int) -> str:
        v = (b1 << 16) | (b2 << 8) | b3
        result = ""
        for _ in range(n):
            result += _b64[v & 0x3F]
            v >>= 6
        return result

    encoded = (
        _encode_triple(c[0], c[21], c[42], 4)
        + _encode_triple(c[22], c[43], c[1], 4)
        + _encode_triple(c[44], c[2], c[23], 4)
        + _encode_triple(c[3], c[24], c[45], 4)
        + _encode_triple(c[25], c[46], c[4], 4)
        + _encode_triple(c[47], c[5], c[26], 4)
        + _encode_triple(c[6], c[27], c[48], 4)
        + _encode_triple(c[28], c[49], c[7], 4)
        + _encode_triple(c[50], c[8], c[29], 4)
        + _encode_triple(c[9], c[30], c[51], 4)
        + _encode_triple(c[31], c[52], c[10], 4)
        + _encode_triple(c[53], c[11], c[32], 4)
        + _encode_triple(c[12], c[33], c[54], 4)
        + _encode_triple(c[34], c[55], c[13], 4)
        + _encode_triple(c[56], c[14], c[35], 4)
        + _encode_triple(c[15], c[36], c[57], 4)
        + _encode_triple(c[37], c[58], c[16], 4)
        + _encode_triple(c[59], c[17], c[38], 4)
        + _encode_triple(c[18], c[39], c[60], 4)
        + _encode_triple(c[40], c[61], c[19], 4)
        + _encode_triple(c[62], c[20], c[41], 4)
        + _encode_triple(0, 0, c[63], 2)
    )

    return f"$6${salt}${encoded}"
