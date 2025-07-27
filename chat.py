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
    "Welcome new viewers! Say hi 👋"
    "Hi girlfriend",
    "Baddie",
    "chrisssssss",
]
POST_INTERVAL = 30   # seconds between auto-messages

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

    # 
    def connect(self):
        plain_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock = ssl.create_default_context().wrap_socket(
            plain_sock, server_hostname=self.conf["server"]
        )
        self.sock.connect((self.conf["server"], self.conf["port"]))

        # --- IRC handshake ---
        send(self.sock, f"PASS {self.conf['token']}")
        send(self.sock, f"NICK {self.conf['nickname']}")
        send(self.sock, f"JOIN {self.conf['channel']}")

        print("[bot] Connected and joined", self.conf["channel"])

    # -
    def send_chat(self, text):
        """Send a PRIVMSG to the configured channel."""
        send(self.sock, f"PRIVMSG {self.conf['channel']} :{text}")

    # -
    def handle_line(self, line):
        """
        Parse one IRC line and react if needed.
        Examples:
          :user!user@user.tmi.twitch.tv PRIVMSG #channel :actual message
          PING :tmi.twitch.tv
        """
        # keep-alive
        if line.startswith("PING"):
            send(self.sock, "PONG :tmi.twitch.tv")
            return

        # parse PRIVMSG
        match = re.match(
            r":([^!]+)!.* PRIVMSG ([^ ]+) :(.*)", line
        )
        if not match:
            return  # not a chat message

        username, channel, msg = match.groups()
        msg = msg.strip()

        # ignore own messages
        if username.lower() == self.conf["nickname"].lower():
            return

        # --- commands ------------------------------------------------
        if msg == "!hello":
            self.send_chat(f"Hello, {username}!")

        elif msg == "!dice":
            roll = random.randint(1, 6)
            self.send_chat(f"{username} rolled a {roll} 🎲")

    # Background thread that posts a random phrase every POST_INTERVAL.
    def auto_speaker(self):
        """Background thread that posts a random phrase every POST_INTERVAL."""
        while self.running:
            time.sleep(POST_INTERVAL)
            if self.running:  # still connected?
                phrase = random.choice(RANDOM_PHRASES)
                self.send_chat(phrase)
                print(f"[auto] Sent: {phrase}")

    # 
    def run_forever(self):
        self.running = True
        self.connect()

        # Start the auto-spam thread
        threading.Thread(target=self.auto_speaker, daemon=True).start()

        buffer = ""
        while self.running:
            try:
                buffer += self.sock.recv(2048).decode("utf-8", errors="ignore")
            except OSError:
                break

            while "\r\n" in buffer:
                line, buffer = buffer.split("\r\n", 1)
                self.handle_line(line.strip())

        self.sock.close()
        print("[bot] Disconnected.")

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