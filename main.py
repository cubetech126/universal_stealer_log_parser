from log_parser_body import extract_passwords_all
from cookie_parser_body import extract_cookies_all
from ftp_parser_body import extract_ftp_all
from imap_smtp_parser_body import extract_imap_smtp_all

from cc_parser import process_cc, process_cc_v2

def main():
    output_file_all = "Treated_passwords_all.txt"
    output_file_all_cookies = "Treated_cookies_all.txt"
    output_file_all_cc = "Treated_cc_all.txt"
    output_file_all_ftp = "Treated_ftp_all.txt"
    output_file_all_imap_smtp = "Treated_imap_smtp_all.txt"

    main_folder = input("Specify the main folder: ")
    print(f"The main folder is: {main_folder}")

    output_folder = main_folder
    # process_cc(main_folder)
    # process_cc_v2(main_folder)
    
    extract_ftp_all(main_folder, output_folder, output_file_all_ftp)
    extract_imap_smtp_all(main_folder, output_folder, output_file_all_imap_smtp)
    extract_passwords_all(main_folder, output_folder, output_file_all)
    extract_cookies_all(main_folder, output_folder, output_file_all_cookies)

if __name__ == "__main__":
    main()