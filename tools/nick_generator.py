#!/usr/bin/env python3
import random

PREFIXES = [
    "Random", "Stray", "Bot", "Guest", "Radio", "That", "Duty", "Signal",
    "Captain", "Hacker", "Sysadmin", "Penguin", "Doctor", "Cyber", "Ether",
    "Baron", "Knight", "Tracer", "Null", "Script", "Bug", "Frame", "Packet",
    "Demon", "Virtual", "Noise", "Provider", "Deep", "Quantum", "Digital",
    "Wireless", "Local", "Network", "Background", "Edge",
]

SUFFIXES = [
    "WithShovel", "Passerby", "Alix3000", "FromFuture", "Lover",
    "WithSpeaker", "ByServer", "Petrovich", "Obvious", "OnVacation",
    "FromMorning", "InOvercoat", "Beat", "Shaman", "Wanderer",
    "VonLag", "GreenScreen", "InDark", "Unit", "Kiddie",
    "Hunter", "Drop", "Monk", "Latency", "Vagabond",
    "Trooper", "Monday", "Signal", "Noise", "Code",
    "Byte", "Node", "Bridge", "Link", "Packet", "Lag",
]


def generate_nick() -> str:
    prefix = random.choice(PREFIXES)
    suffix = random.choice(SUFFIXES)
    return f"{prefix}_{suffix}"


if __name__ == "__main__":
    for _ in range(10):
        print(generate_nick())
