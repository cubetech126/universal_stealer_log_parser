import os
import json
import re
import base64
import xml.etree.ElementTree as ET
from urllib.parse import urlsplit

FTP_SOFTWARE_KEYWORDS = ("filezilla", "winscp", "ftp", "sftp", "coreftp", "smartftp", "flashfxp", "cyberduck")

def extract_ftp_all(main_folder, output_folder, output_file_all):
    print("Extracting FTP credentials...")

    seen_entries = set()

    xml_files = {'sitemanager.xml', 'recentservers.xml'}
    text_files = {
        'all_passwords.txt',
        'passwords.txt',
        'password list.txt',
        '_allpasswords_list.txt',
        'all passwords.txt',
        'found_credentials.txt',
        'credentials.txt',
        'passwords_soft.txt',
        'filezilla_credentials.txt',
    }
    ftp_only_files = {'filezilla_credentials.txt'}
    supported_files = xml_files | text_files

    for subdir, dirs, files in os.walk(main_folder):
        for file in files:
            file_lower = file.lower()
            if file_lower not in supported_files:
                continue

            file_path = os.path.join(subdir, file)

            if file_lower in xml_files:
                entries = _parse_filezilla_xml(file_path)
            else:
                dir_is_ftp = any(kw in subdir.lower() for kw in FTP_SOFTWARE_KEYWORDS)
                entries = _parse_text_file(file_path, ftp_only=(file_lower in ftp_only_files), dir_is_ftp=dir_is_ftp)

            for entry in entries:
                dedup_key = (entry["host"], entry.get("port"), entry.get("username"), entry["password"])
                if dedup_key in seen_entries:
                    continue
                seen_entries.add(dedup_key)

                json_line = json.dumps(entry, ensure_ascii=False)
                with open(os.path.join(output_folder, output_file_all), "a", encoding="utf-8") as f:
                    f.write(json_line + "\n")


def _decode_pass_element(pass_el):
    """Decode a FileZilla <Pass> element, handling optional base64 encoding."""
    if pass_el is None or not pass_el.text:
        return ""
    raw = pass_el.text.strip()
    if pass_el.get("encoding") == "base64":
        try:
            return base64.b64decode(raw).decode("utf-8")
        except Exception:
            return raw
    return raw


def _parse_filezilla_xml(file_path):
    """Parse sitemanager.xml / recentservers.xml for <Server> entries."""
    entries = []
    try:
        with open(file_path, "r", encoding="utf-8", errors="replace") as f:
            raw = f.read()
    except (FileNotFoundError, OSError) as e:
        print(f"Error reading XML {file_path}: {e}")
        return entries

    # Strip junk (ads/branding) that some stealers prepend before the XML
    xml_start = raw.find("<?xml")
    if xml_start == -1:
        xml_start = raw.find("<FileZilla3")
    if xml_start == -1:
        xml_start = raw.find("<Server")
    if xml_start != -1:
        raw = raw[xml_start:]

    try:
        tree = ET.ElementTree(ET.fromstring(raw))
    except ET.ParseError as e:
        print(f"Error parsing XML {file_path}: {e}")
        return entries

    for server in tree.iter("Server"):
        host = (server.findtext("Host") or "").strip()
        port_str = (server.findtext("Port") or "").strip()
        username = (server.findtext("User") or "").strip()
        password = _decode_pass_element(server.find("Pass"))

        if not host or not password:
            continue

        port = None
        if port_str:
            try:
                port = int(port_str)
            except ValueError:
                pass

        entries.append({
            "host": host,
            "port": port,
            "username": username or None,
            "password": password,
        })

    return entries


def _parse_text_file(file_path, ftp_only=False, dir_is_ftp=False):
    """Parse text credential files, extracting FTP entries only."""
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

        # Split block into per-entry records; a new record starts on each Host/Hostname key
        records = []
        current = {}

        for line in block.split("\n"):
            if ":" not in line:
                continue
            key, value = line.split(":", 1)
            key = key.strip().lower()
            value = value.strip()

            if key in ("host", "hostname"):
                if current.get("host_raw"):
                    records.append(current)
                    current = {"soft": current.get("soft", "")}
                current["host_raw"] = value
            elif key in ("soft", "application"):
                current["soft"] = value
            elif key == "port":
                current["port_raw"] = value
            elif key in ("user", "login", "username", "user login"):
                current["username"] = value
            elif key in ("pass", "password", "user password"):
                current["password"] = value
            elif key == "url":
                current["url"] = value

        if current.get("host_raw") or current.get("url"):
            records.append(current)

        for rec in records:
            soft = rec.get("soft", "")
            host_raw = rec.get("host_raw", "")
            port_raw = rec.get("port_raw", "")
            username = rec.get("username", "")
            password = rec.get("password", "")
            url = rec.get("url", "")

            # --- Resolve host & port ---
            host = ""
            port = None

            if url and url.lower().startswith(("ftp://", "sftp://")):
                try:
                    parsed = urlsplit(url)
                    host = parsed.hostname or ""
                    port = parsed.port
                except ValueError:
                    pass

            if host_raw:
                host_lower = host_raw.lower()
                if host_lower.startswith(("http://", "https://")):
                    continue
                if host_lower.startswith(("ftp://", "sftp://")):
                    try:
                        parsed_h = urlsplit(host_raw)
                        host = parsed_h.hostname or ""
                        if parsed_h.port:
                            port = parsed_h.port
                    except ValueError:
                        host = host_raw
                else:
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

            # --- FTP filtering ---
            if not ftp_only:
                is_ftp = dir_is_ftp
                soft_lower = soft.lower()
                if any(kw in soft_lower for kw in FTP_SOFTWARE_KEYWORDS):
                    is_ftp = True
                if url.lower().startswith(("ftp://", "sftp://")):
                    is_ftp = True
                if not is_ftp:
                    continue

            if "NOT_SAVED" in password:
                continue
            elif any(
                kw in val
                for val in (host.lower(), str(port or "").lower(), (username or "").lower(), password.lower())
                for kw in ("arthouse", "cloud_arthouse", "@cloud_arthouse", "@arthouse_full_bot")
            ):
                continue

            entries.append({
                "host": host,
                "port": port,
                "username": username or None,
                "password": password,
            })

    return entries