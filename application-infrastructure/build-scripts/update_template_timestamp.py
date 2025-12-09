#!/usr/bin/env python3
import re
import datetime
import sys

def update_timestamp(template_path):
    # Generate current timestamp in YYYYMMDDTHHMM format
    current_timestamp = datetime.datetime.now().strftime("%Y%m%dT%H%M")
    
    # Read the template file
    with open(template_path, 'r') as file:
        content = file.read()
    
    # Replace the AutoPublishCodeSha256 value with the new timestamp
    updated_content = re.sub(
        r'(AutoPublishCodeSha256:\s*)"[^"]*"',
        r'\1"' + current_timestamp + '"',
        content
    )
    
    # Update VersionDescription to append timestamp
    updated_content = re.sub(
        r'(VersionDescription:\s*)"([^"]*?)"',
        r'\1"\2 - ' + current_timestamp + '"',
        updated_content
    )

    # Write the updated content back to the file
    with open(template_path, 'w') as file:
        file.write(updated_content)
    
    print(f"Updated AutoPublishCodeSha256 to {current_timestamp}")
    print(f"Updated VersionDescription with timestamp {current_timestamp}")

if __name__ == "__main__":
    template_path = sys.argv[1] if len(sys.argv) > 1 else "template.yml"
    update_timestamp(template_path)