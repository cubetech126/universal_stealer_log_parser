from log_parser_body import extract_passwords_all
from cc_parser import process_cc, process_cc_v2

def main():
    output_file_all = "Treated_passwords_all.txt"
    main_folder = input("Specify the main folder: ")
    print(f"The main folder is: {main_folder}")
    output_folder = main_folder
    # process_cc(main_folder)
    # process_cc_v2(main_folder)
    extract_passwords_all(main_folder, output_folder, output_file_all)

if __name__ == "__main__":
    main()