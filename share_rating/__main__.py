"""Command line: `python -m share_rating auth` and `python -m share_rating serve`."""

import argparse
import sys
import threading
import webbrowser

from share_rating import db
from share_rating.config import ConfigError, load_config
from share_rating.trakt import TraktAuthError, TraktClient
from share_rating.web import create_app


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m share_rating")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("auth", help="log in to Trakt (device code)")
    serve = sub.add_parser("serve", help="start the local web page")
    serve.add_argument("--no-browser", action="store_true", help="do not open a browser tab")
    args = parser.parse_args(argv)

    try:
        config = load_config()
    except ConfigError as e:
        print(e, file=sys.stderr)
        return 2

    if args.command == "auth":
        conn = db.connect(config.db_path)
        db.init_db(conn)
        try:
            TraktClient(config, conn).device_auth()
        except TraktAuthError as e:
            print(e, file=sys.stderr)
            return 1
        finally:
            conn.close()
        return 0

    url = f"http://127.0.0.1:{config.port}/"
    if not args.no_browser:
        threading.Timer(1.0, webbrowser.open, args=(url,)).start()
    print(f"Serving on {url}")
    create_app(config).run(host="127.0.0.1", port=config.port)
    return 0


if __name__ == "__main__":
    sys.exit(main())
