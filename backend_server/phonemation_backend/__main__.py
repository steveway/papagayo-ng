import argparse
import json
import logging

import uvicorn

from .api import create_backend_app
from .environment import format_environment_summary, get_environment_info
from .service import BackendConfig, PhonemationBackend


def parse_args():
    parser = argparse.ArgumentParser(description="Run the standalone Phonemation backend")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--phoneme-model", dest="phoneme_model_path")
    parser.add_argument("--emotion-model", dest="emotion_model_path")
    parser.add_argument("--host-api")
    parser.add_argument("--input-device")
    parser.add_argument("--output-device")
    parser.add_argument("--enable-output", action="store_true")
    parser.add_argument("--vad-system", default="volume", choices=["volume", "energy", "silero"])
    parser.add_argument("--volume-threshold", type=float, default=0.05)
    parser.add_argument("--autoload", action="store_true")
    parser.add_argument("--ui", action="store_true", help="Launch the Tkinter UI instead of running CLI server")
    parser.add_argument("--environment", action="store_true", help="Print runtime and resource information as JSON, then exit")
    return parser.parse_args()


def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    args = parse_args()
    environment = get_environment_info()
    if args.environment:
        print(json.dumps(environment, indent=2))
        return
    logging.info("Environment: %s", format_environment_summary(environment))

    if args.ui:
        from .ui import run_ui
        run_ui()
        return

    backend = None
    if args.autoload:
        if not args.phoneme_model_path or not args.emotion_model_path:
            raise SystemExit("--autoload requires --phoneme-model and --emotion-model")
        backend = PhonemationBackend(
            BackendConfig(
                phoneme_model_path=args.phoneme_model_path,
                emotion_model_path=args.emotion_model_path,
                host_api=args.host_api,
                input_device=args.input_device,
                output_device=args.output_device,
                enable_output=args.enable_output,
                vad_system=args.vad_system,
                volume_level_threshold=args.volume_threshold,
            )
        )
        backend.start()

    app = create_backend_app(backend)
    config = uvicorn.Config(app, host=args.host, port=args.port, log_level="info")
    server = uvicorn.Server(config)
    # Expose the server so the /shutdown endpoint can terminate the process.
    app.state.server = server
    server.run()


if __name__ == "__main__":
    main()
