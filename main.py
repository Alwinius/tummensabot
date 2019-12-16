#!/usr/bin/env python3

import sys

from tummensabot import mensa


def usage():
    print(f"TUMMensaBot\nUsage: {sys.argv[0]} <daemon|notifications>", file=sys.stderr)
    sys.exit(1)


if __name__ == '__main__':
    if len(sys.argv) != 2:
        usage()

    if sys.argv[1] == "daemon":
        mensa.run_daemon()
    elif sys.argv[1] == "notifications":
        mensa.send_notifications()
    elif sys.argv[1] in ("-h", "--help", "help"):
        usage()
    else:
        print("Unknown parameter:", sys.argv[1], file=sys.stderr)
        sys.exit(1)
