import os
import json
import re
from urllib.parse import urlsplit

MAIL_SOFTWARE_KEYWORDS = (
    "thunderbird", "outlook", "foxmail", "the bat", "mailbird",
    "em client", "opera mail", "windows mail", "incredimail",
    "postbox", "claws mail", "zimbra", "eudora",
)

MAIL_PROTOCOL_KEYWORDS = ("imap", "smtp", "pop3", "pop")

MAIL_SCHEMES = ("imap://", "smtp://", "pop3://", "pop://")

MAIL_PORTS = {
    143: "imap",
    993: "imap",
    25: "smtp",
    465: "smtp",
    587: "smtp",
    110: "pop3",
    995: "pop3",
}

HOST_PREFIX_TO_PROTOCOL = (
    ("imap.", "imap"),
    ("imaps.", "imap"),
    ("smtp.", "smtp"),
    ("smtps.", "smtp"),
    ("pop.", "pop3"),
    ("pop3.", "pop3"),
    ("mail.", None),
)


def extract_imap_smtp_all(main_folder, output_folder, output_file_all):
    print("Extracting IMAP / SMTP / POP3 credentials...")

    seen_entries = set()

    text_files = {
        'all_passwords.txt',
        'passwords.txt',
        'password list.txt',
        '_allpasswords_list.txt',
        'all passwords.txt',
        'found_credentials.txt',
        'credentials.txt',
        'passwords_soft.txt',
        'email_credentials.txt',
        'emails.txt',
        'app_outlook.txt',
        'app_thunderbird.txt',
        'app_foxmail.txt',
    }
    json_files = {'passwords.json'}
    tsv_files = {'passwords.tsv'}
    mail_only_files = {
        'email_credentials.txt', 'emails.txt',
        'app_outlook.txt', 'app_thunderbird.txt', 'app_foxmail.txt',
    }
    supported_files = text_files | json_files | tsv_files

    for subdir, dirs, files in os.walk(main_folder):
        for file in files:
            file_lower = file.lower()
            if file_lower not in supported_files:
                continue

            file_path = os.path.join(subdir, file)
            dir_is_mail = any(kw in subdir.lower() for kw in MAIL_SOFTWARE_KEYWORDS)

            if file_lower in json_files:
                entries = _parse_json_file(file_path, dir_is_mail=dir_is_mail)
            elif file_lower in tsv_files:
                entries = _parse_tsv_file(file_path)
            else:
                entries = _parse_text_file(
                    file_path,
                    mail_only=(file_lower in mail_only_files),
                    dir_is_mail=dir_is_mail,
                )

            for entry in entries:
                dedup_key = (
                    entry["host"],
                    # entry.get("port"),
                    entry.get("protocol"),
                    entry.get("username"),
                    entry["password"],
                )
                if dedup_key in seen_entries:
                    continue
                seen_entries.add(dedup_key)

                json_line = json.dumps(entry, ensure_ascii=False)
                with open(os.path.join(output_folder, output_file_all), "a", encoding="utf-8") as f:
                    f.write(json_line + "\n")


def _infer_protocol(host, port, scheme=""):
    """Best-effort protocol detection from host prefix, port, or URL scheme."""
    scheme_lower = scheme.lower()
    for s, proto in (("imap", "imap"), ("smtp", "smtp"), ("pop3", "pop3"), ("pop", "pop3")):
        if scheme_lower.startswith(s):
            return proto

    if port and port in MAIL_PORTS:
        return MAIL_PORTS[port]

    host_lower = host.lower()
    for prefix, proto in HOST_PREFIX_TO_PROTOCOL:
        if host_lower.startswith(prefix):
            return proto

    return None


def _is_mail_host(host):
    """Check whether a hostname looks like a mail server."""
    host_lower = host.lower()
    for prefix, _ in HOST_PREFIX_TO_PROTOCOL:
        if host_lower.startswith(prefix):
            return True
    return False


def _parse_tsv_file(file_path):
    """Parse tab-separated files with url\\tlogin\\tpassword lines."""
    entries = []
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            contents = f.read()
    except UnicodeDecodeError:
        try:
            with open(file_path, "r", encoding="latin-1") as f:
                contents = f.read()
        except Exception as e:
            print(f"Error reading {file_path}: {e}")
            return entries
    except (FileNotFoundError, OSError) as e:
        print(f"Error reading {file_path}: {e}")
        return entries

    for line in contents.splitlines():
        line = line.strip()
        if not line:
            continue

        parts = line.split("\t")
        if len(parts) < 3:
            continue

        url, username, password = parts[0].strip(), parts[1].strip(), parts[2].strip()

        if not url.lower().startswith(MAIL_SCHEMES):
            continue
        if not password:
            continue

        host = ""
        port = None
        scheme = ""
        try:
            parsed = urlsplit(url)
            host = parsed.hostname or ""
            port = parsed.port
            scheme = parsed.scheme
        except ValueError:
            continue

        if not host:
            continue

        if "NOT_SAVED" in password:
            continue
        if any(
            kw in val
            for val in (host.lower(), username.lower(), password.lower())
            for kw in ("arthouse", "cloud_arthouse", "@cloud_arthouse", "@arthouse_full_bot")
        ):
            continue

        protocol = _infer_protocol(host, port, scheme)

        entries.append({
            "host": host,
            "protocol": protocol,
            "username": username or None,
            "password": password,
        })

    return entries


def _parse_json_file(file_path, dir_is_mail=False):
    """Parse JSON credential files (e.g. Thunderbird Passwords.json)."""
    entries = []
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except UnicodeDecodeError:
        try:
            with open(file_path, "r", encoding="latin-1") as f:
                data = json.load(f)
        except (json.JSONDecodeError, Exception):
            return _parse_text_file(file_path, mail_only=False, dir_is_mail=dir_is_mail)
    except json.JSONDecodeError:
        return _parse_text_file(file_path, mail_only=False, dir_is_mail=dir_is_mail)
    except (FileNotFoundError, OSError) as e:
        print(f"Error reading JSON {file_path}: {e}")
        return entries

    if not isinstance(data, list):
        return entries

    for item in data:
        if not isinstance(item, dict):
            continue

        hostname = (item.get("Hostname") or item.get("hostname") or "").strip()
        username = (item.get("Username") or item.get("username") or "").strip()
        password = (item.get("Password") or item.get("password") or "").strip()

        if not hostname or not password:
            continue

        host = ""
        port = None
        scheme = ""

        hostname_lower = hostname.lower()
        if hostname_lower.startswith(("http://", "https://")):
            continue

        for mail_scheme in MAIL_SCHEMES:
            if hostname_lower.startswith(mail_scheme):
                try:
                    parsed = urlsplit(hostname)
                    host = parsed.hostname or ""
                    port = parsed.port
                    scheme = parsed.scheme
                except ValueError:
                    pass
                break
        else:
            parts = hostname.rsplit(":", 1)
            if len(parts) == 2 and parts[1].isdigit():
                host = parts[0]
                port = int(parts[1])
            else:
                host = hostname

        if not host:
            continue

        protocol = _infer_protocol(host, port, scheme)

        is_mail = dir_is_mail
        if hostname_lower.startswith(MAIL_SCHEMES):
            is_mail = True
        if _is_mail_host(host):
            is_mail = True
        if port and port in MAIL_PORTS:
            is_mail = True
        if not is_mail:
            continue

        if "NOT_SAVED" in password:
            continue
        if any(
            kw in val
            for val in (host.lower(), str(port or "").lower(), username.lower(), password.lower())
            for kw in ("arthouse", "cloud_arthouse", "@cloud_arthouse", "@arthouse_full_bot")
        ):
            continue

        entries.append({
            "host": host,
            # "port": port,
            "protocol": protocol,
            "username": username or None,
            "password": password,
        })

    return entries


def _parse_text_file(file_path, mail_only=False, dir_is_mail=False):
    entries = []
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            contents = f.read()
    except UnicodeDecodeError:
        try:
            with open(file_path, "r", encoding="latin-1") as f:
                contents = f.read()
        except Exception as e:
            print(f"Error reading {file_path}: {e}")
            return entries
    except (FileNotFoundError, OSError) as e:
        print(f"Error reading {file_path}: {e}")
        return entries

    blocks = re.split(r'(?:\n\n|\n[━=\-_*]{5,}\n)', contents)

    for block in blocks:
        block = block.strip()
        if not block:
            continue

        records = []
        current = {}

        for line in block.split("\n"):
            if ":" not in line:
                continue
            key, value = line.split(":", 1)
            key = key.strip()
            if key.startswith('"') and key.endswith('"'):
                key = key[1:-1]
            key = key.lower()
            value = value.strip().rstrip(",")
            if value.startswith('"') and value.endswith('"'):
                value = value[1:-1]

            if key in ("host", "hostname"):
                if current.get("host_raw"):
                    records.append(current)
                    current = {"soft": current.get("soft", ""), "email": current.get("email", "")}
                current["host_raw"] = value
            elif key in ("smtp server", "imap server", "pop3 server"):
                if current.get("host_raw"):
                    records.append(current)
                    current = {"soft": current.get("soft", ""), "email": current.get("email", "")}
                current["host_raw"] = value
                current["protocol_hint"] = key.split()[0]
            elif key in ("soft", "application", "browser"):
                if current.get("host_raw") or current.get("url"):
                    records.append(current)
                    current = {}
                current["soft"] = value
            elif key == "port":
                current["port_raw"] = value
            elif key in ("user", "login", "username", "user login",
                         "smtp user", "imap user", "pop3 user"):
                current["username"] = value
            elif key in ("pass", "password", "user password",
                         "smtp password", "imap password", "pop3 password"):
                current["password"] = value
            elif key == "email":
                current["email"] = value
                if not current.get("username"):
                    current["username"] = value
            elif key == "url":
                if current.get("url"):
                    records.append(current)
                    current = {"soft": current.get("soft", "")}
                current["url"] = value

        if current.get("host_raw") or current.get("url"):
            records.append(current)

        for rec in records:
            soft = rec.get("soft", "")
            host_raw = rec.get("host_raw", "")
            port_raw = rec.get("port_raw", "")
            username = rec.get("username", "") or rec.get("email", "")
            password = rec.get("password", "")
            url = rec.get("url", "")
            protocol_hint = rec.get("protocol_hint", "")

            host = ""
            port = None
            scheme = ""

            for mail_scheme in MAIL_SCHEMES:
                if url.lower().startswith(mail_scheme):
                    try:
                        parsed = urlsplit(url)
                        host = parsed.hostname or ""
                        port = parsed.port
                        scheme = parsed.scheme
                    except ValueError:
                        pass
                    break

            if host_raw:
                host_lower = host_raw.lower()
                if host_lower.startswith(("http://", "https://")):
                    continue
                matched_scheme = False
                for mail_scheme in MAIL_SCHEMES:
                    if host_lower.startswith(mail_scheme):
                        matched_scheme = True
                        try:
                            parsed_h = urlsplit(host_raw)
                            host = parsed_h.hostname or ""
                            if parsed_h.port:
                                port = parsed_h.port
                            if not scheme:
                                scheme = parsed_h.scheme
                        except ValueError:
                            host = host_raw
                        break

                if not matched_scheme:
                    parts = host_raw.rsplit(":", 1)
                    if len(parts) == 2 and parts[1].isdigit():
                        host = parts[0]
                        port = int(parts[1])
                    else:
                        host = host_raw

            if port_raw:
                try:
                    port = int(port_raw)
                except ValueError:
                    pass

            if not host or not password:
                continue

            protocol = protocol_hint or _infer_protocol(host, port, scheme)

            if not mail_only:
                is_mail = dir_is_mail

                soft_lower = soft.lower()
                if any(kw in soft_lower for kw in MAIL_SOFTWARE_KEYWORDS):
                    is_mail = True
                if any(kw in soft_lower for kw in MAIL_PROTOCOL_KEYWORDS):
                    is_mail = True

                if url.lower().startswith(MAIL_SCHEMES):
                    is_mail = True
                if host_raw.lower().startswith(MAIL_SCHEMES):
                    is_mail = True

                if _is_mail_host(host):
                    is_mail = True

                if port and port in MAIL_PORTS:
                    is_mail = True

                if not is_mail:
                    continue

            if "NOT_SAVED" in password:
                continue
            elif any(
                kw in val
                for val in (host.lower(), str(port or "").lower(), (username or "").lower(), password.lower())
                for kw in ("arthouse", "cloud_arthouse", "@cloud_arthouse", "@arthouse_full_bot", "u2fp29gkufkzz", "5sbwt2_xek3mgjh", "ih73k1u", "rrntiqwtg0fjztkx")
            ):
                continue

            entries.append({
                "host": host,
                # "port": port,
                "protocol": protocol,
                "username": username or None,
                "password": password,
            })

    return entries