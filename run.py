import os
import sys
import signal
import subprocess
import datetime, time
import yaml

class RunningExceptions(Exception):
    def __init__(self, message):
        self.message = message
        super().__init__(self.message)

with open('./config/config.yaml', 'r') as file:
    config = yaml.safe_load(file)

with open('./lavalink-server/application.yml', 'r') as lavalink_file:
    lavalink_config = yaml.safe_load(lavalink_file)

if config["symphsonic"]["mafic_ip"] is None:
    raise RunningExceptions("No IP-address provided for discord bot.")

if config["symphsonic"]["mafic_port"] is None:
    raise RunningExceptions("No port provided for discord bot.")

use_local_lavalink = config["symphsonic"]["use_local_lavalink"]

#Load the lavalink's application.yml file and edit it.
if use_local_lavalink is True:
    lavalink_config["server"]["address"] = config["symphsonic"]["mafic_ip"]
    lavalink_config["server"]["port"] = config["symphsonic"]["mafic_port"]
    lavalink_config["lavalink"]["password"] = config["symphsonic"]["lavalink_password"]

    with open("./lavalink-server/application.yml", 'w') as lavalink_file:
        yaml.dump(lavalink_config, lavalink_file)

subprocesses = []

if use_local_lavalink is True:
    lavalink = subprocess.Popen(["java", "-jar", "./Lavalink.jar"], cwd="./lavalink-server/", stdout=subprocess.PIPE)
    subprocesses.append(lavalink)

    for line in iter(lavalink.stdout.readline, b''):
        line_str = line.decode("utf-8")
        print(line_str)
        if "Lavalink is ready to accept connections." in line_str:
            break
        elif "Application failed" in line_str:
            sys.exit(1)

bot = subprocess.Popen(["python3", "./bot.py"], cwd="./discord-bot/")
subprocesses.append(bot)

def signal_handler(sig, frame):
    print('\nShutting down SymphSonic.')
    for subprocess in subprocesses:
        #subprocess.send_signal(signal.SIGTERM)
        subprocess.wait(timeout=None)
    sys.exit(0)

while True:
    signal.signal(signal.SIGINT, signal_handler)
