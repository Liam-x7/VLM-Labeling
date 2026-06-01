from __future__ import annotations

import argparse
from http.server import ThreadingHTTPServer

from backend.config import HOST, PORT
from backend.server import create_server


def main() -> None:
    parser = argparse.ArgumentParser(description="LabelOps Studio backend")
    parser.add_argument("--host", default=HOST)
    parser.add_argument("--port", type=int, default=PORT)
    args = parser.parse_args()

    server = create_server(args.host, args.port)
    print(f"LabelOps Studio running at http://{args.host}:{args.port}")
    print("Press Ctrl+C to stop")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nBackend stopped")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
