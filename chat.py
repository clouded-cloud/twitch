#!/usr/bin/env python3
"""
Minimal Twitch chat-bot (IRC/TLS) – no external deps.
Now also auto-posts random phrases every N seconds.
"""

import os
import socket
import ssl
import re
import random
import threading
import time
import logging

# 
# CONFIGURATION – edit these four items
# 
CONFIG = {
    "server": "irc.chat.twitch.tv",
    "port": 6697,                       # 6697 = TLS; 6667 = plain
    "nickname": "my_bot_account",       
    "token": "oauth:mgx9vrwf4oref1cfew3klggoqftenx",   
    "channel": "#sdfr4k"                
}

# 
# Auto-spam phrases & timing
# 
RANDOM_PHRASES = [
    "Follow for more amazing content!",
    "Type !discord for our server link!",
    "Have a great day everyone 🌞",
    "Hi class",
    "Welcome new viewers! Say hi 👋",  # Fixed: Added comma here
    "Hi girlfriend",
    "Baddie",
    "chrisssssss",
]
POST_INTERVAL_MIN = 20   # Minimum seconds between auto-messages
POST_INTERVAL_MAX = 40   # Maximum seconds between auto-messages

# 
# Helper: send raw IRC line
# 
def send(sock, msg):
    sock.send((msg + "\r\n").encode("utf-8"))

# 
# Main bot class
# 
class TwitchBot:
    def __init__(self, conf):
        self.conf = conf
        self.sock = None
        self.running = False
        # Set up basic logging
        logging.basicConfig(level=logging.INFO, format='[%(levelname)s] %(message)s')
        self.logger = logging.getLogger(__name__)

    def connect(self):
        try:
            plain_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.sock = ssl.create_default_context().wrap_socket(
                plain_sock, server_hostname=self.conf["server"]
            )
            self.sock.connect((self.conf["server"], self.conf["port"]))

            # --- IRC handshake ---
            send(self.sock, f"PASS {self.conf['token']}")
            send(self.sock, f"NICK {self.conf['nickname']}")
            send(self.sock, f"JOIN {self.conf['channel']}")

            self.logger.info(f"Connected and joined {self.conf['channel']}")
            return True
        except Exception as e:
            self.logger.error(f"Connection failed: {e}")
            return False

    def send_chat(self, text):
        """Send a PRIVMSG to the configured channel."""
        send(self.sock, f"PRIVMSG {self.conf['channel']} :{text}")

    def parse_privmsg(self, line):
        """
        Parse a PRIVMSG line to extract username and message.
        More robust than regex-only approach.
        """
        if "PRIVMSG" not in line:
            return None, None
            
        try:
            # Split into parts using colon as delimiter
            parts = line.split(":", 2)
            if len(parts) < 3:
                return None, None
                
            # Extract username from the first part
            username_part = parts[1].split("!")[0]
            message = parts[2].strip()
            
            return username_part, message
        except (IndexError, ValueError):
            return None, None

    def handle_command(self, username, command, args):
        """
        Handle chat commands in a dedicated function for better organization.
        """
        command = command.lower().strip()
        
        if command == "!hello":
            self.send_chat(f"Hello, {username}!")
            
        elif command == "!dice":
            roll = random.randint(1, 6)
            self.send_chat(f"{username} rolled a {roll} 🎲")
            
        # Add more commands here as needed

    def handle_line(self, line):
        """
        Parse one IRC line and react if needed.
        """
        # keep-alive
        if line.startswith("PING"):
            send(self.sock, "PONG :tmi.twitch.tv")
            return

        # Handle PRIVMSG using more robust parsing
        username, msg = self.parse_privmsg(line)
        
        if not username or not msg:
            return  # not a valid chat message

        # ignore own messages
        if username.lower() == self.conf["nickname"].lower():
            return

        # --- command handling ----------------------------------------
        # Check if message starts with a command prefix
        if msg.startswith("!"):
            # Split command and arguments
            parts = msg.split(maxsplit=1)
            command = parts[0]
            args = parts[1] if len(parts) > 1 else ""
            
            self.handle_command(username, command, args)

    def auto_speaker(self):
        """Background thread that posts random phrases at random intervals."""
        while self.running:
            # Use random interval for more natural behavior
            interval = random.randint(POST_INTERVAL_MIN, POST_INTERVAL_MAX)
            time.sleep(interval)
            
            if self.running and self.sock:  # Check if still connected
                try:
                    phrase = random.choice(RANDOM_PHRASES)
                    self.send_chat(phrase)
                    self.logger.info(f"[auto] Sent: {phrase}")
                except Exception as e:
                    self.logger.error(f"Auto-speaker error: {e}")

    def run_forever(self):
        self.running = True
        
        # Connection/reconnection loop
        while self.running:
            if self.connect():
                # Start the auto-spam thread
                threading.Thread(target=self.auto_speaker, daemon=True).start()

                buffer = ""
                try:
                    while self.running:
                        try:
                            data = self.sock.recv(2048).decode("utf-8", errors="ignore")
                            if not data:
                                raise ConnectionError("Connection closed by server")
                                
                            buffer += data
                            
                            while "\r\n" in buffer:
                                line, buffer = buffer.split("\r\n", 1)
                                self.handle_line(line.strip())
                                
                        except (ConnectionError, OSError) as e:
                            self.logger.error(f"Connection error: {e}")
                            break
                            
                except Exception as e:
                    self.logger.error(f"Unexpected error: {e}")
                    
                finally:
                    if self.sock:
                        self.sock.close()
                    self.logger.info("Disconnected.")
                    
                    # Attempt reconnect after a delay if still running
                    if self.running:
                        self.logger.info("Attempting to reconnect in 5 seconds...")
                        time.sleep(5)
            else:
                # Connection failed, wait before retry
                if self.running:
                    self.logger.info("Connection failed. Retrying in 10 seconds...")
                    time.sleep(10)

# 
# Entry point
# 
if __name__ == "__main__":
    bot = TwitchBot(CONFIG)

    # Graceful Ctrl-C handling
    try:
        bot.run_forever()
    except KeyboardInterrupt:
        print("\n[bot] Shutting down...")
        bot.running = False