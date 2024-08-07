import yaml

def read_config_file():
    # Path to the YAML file
    yaml_file_path = 'config.yml'
    
    # Reading the YAML file
    while True:
        try:
            with open(yaml_file_path, 'r') as file:
                config = yaml.safe_load(file)
                print("YAML content:")
                print(config)
        except FileNotFoundError:
            print(f"The file {yaml_file_path} does not exist.")
        except yaml.YAMLError as e:
            print(f"Error parsing YAML file: {e}")
            
        time.sleep(2)

def read_alarm_state():
    # do smomething
    while True:
        pass