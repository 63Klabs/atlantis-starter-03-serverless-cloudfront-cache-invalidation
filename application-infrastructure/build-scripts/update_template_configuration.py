import re
import os
import sys
# The template-configuration.json file includes parameter and tag values to use during the application stack deployment. Many of the values are dynamically generated using environment variables. Placeholders in the file are in the format of $PLACE_HOLDER$ which are used to replace with the corresponding environment variable. For example $STAGE_ID$ is replaced with the environment variable STAGE_ID.
# First, read in the template-configuration.json file and find all the placeholders.
# Second, do a search/replace of the placeholders by using to corresponding environment variable. For example, if the environment variable STAGE_ID=dev is set, then the placeholder $STAGE_ID$ is replaced with the value dev.
# Third, write the modified file to the current directory as template-configuration.json.
# The template-configuration.json file is used by the build-scripts to generate the application stack deployment parameters and tags.
# read in template-configuration.json from current directory or parent directory
def replace_placeholders(template_config_path):

    try:
        config_file = None

        if os.path.exists(template_config_path):
            config_file = template_config_path
        elif os.path.exists(f'../{template_config_path}'):
            config_file = f'../{template_config_path}'
        
        if config_file:
            with open(config_file, 'r') as f:
                config = f.read()

                # create a back-up copy
                with open(f'{config_file}.bak', 'w') as backup:
                    backup.write(config)

                # Find all the placeholders in the format of $PLACE_HOLDER$
                placeholders = re.findall(r'\$([A-Z_][A-Z0-9_]*)\$', config)
                print(f"Found {len(placeholders)} placeholders in {config_file}")
                # remove duplicates
                placeholders = list(set(placeholders))
                print(f"Unique placeholders {len(placeholders)}: {placeholders}")

                # For each placeholder, replace with the corresponding environment variable
                for placeholder in placeholders:
                    # check to see if environment variable is set
                    if placeholder not in os.environ:
                        print(f"Error: {placeholder} environment variable not set", file=sys.stderr)
                        exit()
                    config = config.replace(f'${placeholder}$', os.environ[placeholder])
            # Write the modified file
            with open(config_file, 'w') as f:
                f.write(config)
        else:
            print(f"Error: {template_config_path} not found", file=sys.stderr)
            exit()
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        exit()

def exit():
    print(f"Exiting {sys.argv[0]}...")
    sys.exit(1)

def main():
    template_config_path = sys.argv[1] if len(sys.argv) > 1 else "template-configuration.json"
    replace_placeholders(template_config_path)
    print(f"Updated {template_config_path} by replacing placeholders with environment variable values")

if __name__ == "__main__":
    main()