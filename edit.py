import yaml

with open('./config/config.yaml', 'r') as file:
    config = yaml.safe_load(file)

"""with open('config.yaml', 'w') as file_to_write_to:
    yaml.dump(loaded, file_to_write_to)
"""
print(config)