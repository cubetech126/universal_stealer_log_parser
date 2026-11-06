import os
import json
import re
import uuid
import time
from urllib.parse import urlsplit


# Lowercase names only. Keep vendor rules specific to avoid matching unrelated
# application cookies just because their names contain words like "session".
SKIPPED_COOKIE_NAMES = frozenset({
    # Cloudflare: bot checks, routing, rate limiting, and waiting room.
    "cf_clearance", "__cf_bm", "__cflb", "__cfruid", "_cfuvid",
    "cf_ob_info", "cf_use_ob", "__cfwaitingroom",
    # Akamai: bot management and edge performance.
    "_abck", "ak_bmsc", "bm_sv", "bm_sz", "aka_a2",
    # Google Analytics (including older versions) and advertising.
    "_ga", "_gid", "_gat", "__utma", "__utmb", "__utmc", "__utmt",
    "__utmv", "__utmz", "__utmx", "__utmxx", "_gcl_au",
    "ide", "dsid", "anid",
    # Meta advertising and Microsoft advertising/Clarity analytics.
    "_fbp", "_fbc", "_uetsid", "_uetvid", "_clck", "_clsk", "muid", "clid",
    # Adobe Analytics.
    "s_cc", "s_sq", "s_vi", "s_fid", "s_ecid",
    # HubSpot analytics and tracking consent.
    "__hstc", "hubspotutk", "__hssc", "__hssrc", "__hs_opt_out",
    "__hs_do_not_track", "__hs_initial_opt_in", "__hs_cookie_cat_pref",
    # Hotjar analytics, sampling, and survey preferences.
    "_hjid", "_hjfirstseen", "_hjabsolutesessioninprogress", "_hjtldtest",
    "_hjincludedinpageviewsample", "_hjincludedinsessionsample",
    "_hjminimizedpolls", "_hjdonepolls", "_hjclosedinteractions",
    "_hjsessiontoolarge", "_hjsessionrejected", "_hjsessionresumed",
    # Matomo tracking and consent.
    "_pk_testcookie", "mtm_consent_removed", "mtm_cookie_consent",
    # Consent banners and existing display preferences.
    "optanonconsent", "optanonalertboxclosed", "euconsent-v2",
    "cookieconsent", "cookiecontrol", "cookieconsent_status",
    "language", "dark_mode",
})

# Only known vendor prefixes; identifiers after these vary by site/property.
SKIPPED_COOKIE_PREFIXES = (
    "cf_chl_",
    "_ga_", "_gat_", "_gac_", "_gcl_",
    "_pk_id.", "_pk_ses.", "_pk_ref.", "_pk_cvar.", "_pk_hsr.", "_pk_uid.",
    "_hjsession_", "_hjsessionuser_", "_hjincludedinsessionsample_",
    "amcv_", "amcvs_",
)


def _should_skip_cookie(name):
    normalized_name = name.lower()
    return (
        normalized_name in SKIPPED_COOKIE_NAMES
        or normalized_name.startswith(SKIPPED_COOKIE_PREFIXES)
    )


def extract_cookies_all(main_folder, output_folder, output_file_all):
    # Print saying that the cookies are being extracted
    print("Extracting cookies...")

    # Track duplicates only during this run
    seen_entries = set()

    # Loop through all subdirectories in the main folder
    for subdir, dirs, files in os.walk(main_folder):
        for file in files:
            file_lower = file.lower()
            # Process any .txt file (case-insensitive)
            if file_lower.endswith(".txt"):
                file_path = os.path.join(subdir, file)
                file_uuid = str(uuid.uuid4())
                try:
                    try:
                        with open(file_path, "r", encoding="utf-8") as f:
                            lines = f.readlines()
                    except UnicodeDecodeError:
                        with open(file_path, "r", encoding="latin-1") as f:
                            lines = f.readlines()
                except OSError as exc:
                    print(f"Error: Unable to read file {file_path!r}: {exc}. Skipping...")
                    continue

                for raw_line in lines:
                    line = raw_line.strip()

                    if not line or line.startswith("#"):
                        continue

                    # Netscape cookie format typically uses 7 TAB-separated fields
                    parts = line.split("\t")
                    if len(parts) != 7:
                        continue

                    domain, include_subdomains_str, path, secure_str, expires_str, name, value = parts

                    # Validate domain strictly
                    if not re.fullmatch(r"^\.?[A-Za-z0-9.-]+$", domain):
                        continue

                    if _should_skip_cookie(name):
                        print(f"Skipping cookie {name} because it is blacklisted.")
                        continue

                    include_subdomains = include_subdomains_str.upper() == "TRUE"
                    secure = secure_str.upper() == "TRUE"

                    # Keep expiration exactly as provided (no ms conversion)
                    try:
                        expires_num = int(expires_str)
                    except ValueError:
                        continue
                    expires_value = expires_num

                    # ToDo: If domain is facebook.com, and cookie name is `xs``, find the corresponding `c_user` and append to the value like this: xs|c_user

                    json_entry = json.dumps(
                        {
                            "machine_id": file_uuid,
                            "domain": domain,
                            "include_subdomains": include_subdomains,
                            "path": path,
                            "secure": secure,
                            "expires_epoch_ms": expires_value,
                            "name": name,
                            "value": value,
                        },
                        ensure_ascii=False,
                    )

                    if ("arthouse" in domain.lower() or "arthouse" in name.lower() or "arthouse" in value.lower()):
                        continue

                    # If expires_value (epoch ms) is in the past, skip
                    if expires_value < time.time():
                       print(f"Skipping cookie {name} because it has expired on [{expires_value}]")
                       continue

                    # Deduplicate identical cookie records
                    normalized_key = f"{domain}|{name}|{value}|{expires_value}|"
                    if normalized_key not in seen_entries:
                        with open(os.path.join(output_folder, output_file_all), "a", encoding="utf-8") as out_f:
                            out_f.write(json_entry + "\n")
                        seen_entries.add(normalized_key)
